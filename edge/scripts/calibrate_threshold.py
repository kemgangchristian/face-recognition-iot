"""
Calibre le seuil et la marge 1:N sur des photos prises par LA camera du site.

Cible production : au plus 0,1 % d'intrus. On privilegie le refus des
inconnus ; un autorise masque peut etre refuse.

Usage :
    python -m scripts.calibrate_threshold --site-dir captures/

Arborescence :
    captures/genuine/<personne>/*.jpg
    captures/impostors/*.jpg
"""

import argparse
import itertools
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter
from recognition.face_embedder import build_embedder

# Borne d'intrus. Pas de cible 99 % d'autorises : un faux acces est pire qu'un refus.
TARGET_FPIR = 0.001
TARGET_FAR_GREY = 0.05
MARGIN_GRID = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15)


def extract_all_embeddings(image_paths, detector, quality_filter, embedder):
    embeddings = []
    skipped = 0
    for path in image_paths:
        frame = cv2.imread(str(path))
        if frame is None:
            skipped += 1
            continue
        detections = quality_filter.filter(frame, detector.detect(frame))
        if not detections:
            skipped += 1
            continue
        embeddings.append(embedder.extract(frame, detections[0]))
    if skipped:
        print(f"  ({skipped} image(s) ignoree(s), aucun visage exploitable)")
    return embeddings


def _unit(vec: np.ndarray) -> np.ndarray:
    return vec / (np.linalg.norm(vec) + 1e-9)


def onen_protocol(identities: dict, impostor_embeddings: list):
    """Leave-one-out 1:N : chaque photo vs la galerie (sans elle-meme)."""
    names = sorted(identities)
    best, second, is_gen, correct = [], [], [], []

    def gallery_templates(skip_name=None, skip_idx=None):
        mats, used = [], []
        for name in names:
            embs = identities[name]
            if name == skip_name:
                others = [e for i, e in enumerate(embs) if i != skip_idx]
                if not others:
                    continue
                mats.append(_unit(np.mean(np.stack(others), axis=0)))
            else:
                mats.append(_unit(np.mean(np.stack(embs), axis=0)))
            used.append(name)
        if not mats:
            return used, np.zeros((0, 1))
        return used, np.stack(mats)

    for name in names:
        embs = identities[name]
        if len(embs) < 2:
            continue
        for i, probe in enumerate(embs):
            used, gallery = gallery_templates(skip_name=name, skip_idx=i)
            if gallery.shape[0] == 0:
                continue
            scores = _unit(probe) @ gallery.T
            order = np.argsort(scores)
            best.append(float(scores[order[-1]]))
            second.append(float(scores[order[-2]]) if len(scores) > 1 else -1.0)
            is_gen.append(True)
            correct.append(used[int(order[-1])] == name)

    used_full, gallery_full = gallery_templates()
    for probe in impostor_embeddings:
        if gallery_full.shape[0] == 0:
            break
        scores = _unit(probe) @ gallery_full.T
        order = np.argsort(scores)
        best.append(float(scores[order[-1]]))
        second.append(float(scores[order[-2]]) if len(scores) > 1 else -1.0)
        is_gen.append(False)
        correct.append(False)

    return {
        "best": np.array(best, dtype=np.float64),
        "second": np.array(second, dtype=np.float64),
        "is_gen": np.array(is_gen, dtype=bool),
        "correct": np.array(correct, dtype=bool),
    }


def rates_at(P, T, M):
    auto = (P["best"] >= T) & ((P["best"] - P["second"]) >= M)
    n_gen = int(P["is_gen"].sum())
    n_imp = int((~P["is_gen"]).sum())
    n_fp = int((auto & ~P["is_gen"]).sum())
    n_ok = int((auto & P["correct"]).sum())
    n_mis = int((auto & P["is_gen"] & ~P["correct"]).sum())
    return dict(
        T=float(T),
        min_margin=float(M),
        grant=n_ok / max(n_gen, 1),
        fpir=n_fp / max(n_imp, 1),
        misid=n_mis / max(n_gen, 1),
        n_fp=n_fp,
        n_imp=n_imp,
        n_ok=n_ok,
        n_gen=n_gen,
        n_mis=n_mis,
    )


def search_operating_point(P):
    """Parmi les points a FPIR <= 0,1 %, retient le plus strict (FPIR min, puis grant)."""
    imp = P["best"][~P["is_gen"]]
    if len(imp) < 10:
        raise RuntimeError("Pas assez d'intrus pour calibrer un FPIR 1:N.")
    thresholds = np.unique(np.quantile(imp, np.linspace(0.90, 0.999, 50), method="higher"))
    best = None
    for margin in MARGIN_GRID:
        for threshold in thresholds:
            stats = rates_at(P, float(threshold), margin)
            under_fpir = stats["fpir"] <= TARGET_FPIR and stats["misid"] <= TARGET_FPIR
            if best is None:
                best = (stats, under_fpir)
                continue
            best_stats, best_ok = best
            if under_fpir and not best_ok:
                best = (stats, True)
            elif under_fpir and best_ok:
                if stats["fpir"] < best_stats["fpir"] - 1e-12:
                    best = (stats, True)
                elif abs(stats["fpir"] - best_stats["fpir"]) <= 1e-12 and stats["grant"] > best_stats["grant"]:
                    best = (stats, True)
            elif not under_fpir and not best_ok and stats["fpir"] < best_stats["fpir"]:
                best = (stats, False)
    return best[0]


def genuine_pairs_scores(identities: dict, embedder) -> list:
    scores = []
    for embs in identities.values():
        for a, b in itertools.combinations(embs, 2):
            scores.append(embedder.compare(a, b))
    return scores


def impostor_pair_scores(identities: dict, impostor_embeddings: list, embedder) -> list:
    scores = []
    ids = list(identities.keys())
    for i, id_a in enumerate(ids):
        for id_b in ids[i + 1:]:
            for a in identities[id_a]:
                for b in identities[id_b]:
                    scores.append(embedder.compare(a, b))
    for emb in [e for embs in identities.values() for e in embs]:
        for imp in impostor_embeddings:
            scores.append(embedder.compare(emb, imp))
    return scores


def threshold_at_far(scores: list, far: float) -> float:
    arr = np.sort(np.array(scores))[::-1]
    idx = max(0, int(len(arr) * far) - 1)
    return float(arr[idx]) if len(arr) else 0.5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "storage_data" / "thresholds.json",
    )
    args = parser.parse_args()

    genuine_dir = args.site_dir / "genuine"
    impostor_dir = args.site_dir / "impostors"
    if not genuine_dir.is_dir():
        sys.exit(f"Dossier introuvable : {genuine_dir}")

    detector = FaceDetector()
    quality_filter = QualityFilter()
    embedder = build_embedder()

    identities = {}
    for person_dir in sorted(p for p in genuine_dir.iterdir() if p.is_dir()):
        images = sorted(person_dir.glob("*.jpg")) + sorted(person_dir.glob("*.jpeg"))
        print(f"Extraction -- {person_dir.name} ({len(images)} image(s))")
        embs = extract_all_embeddings(images, detector, quality_filter, embedder)
        if len(embs) < 2:
            print(f"  {person_dir.name} : moins de 2 images exploitables, ignoree.")
            continue
        identities[person_dir.name] = embs

    impostor_images = (
        sorted(impostor_dir.glob("*.jpg")) + sorted(impostor_dir.glob("*.jpeg"))
        if impostor_dir.is_dir() else []
    )
    print(f"\nExtraction -- imposteurs ({len(impostor_images)} image(s))")
    impostor_embeddings = extract_all_embeddings(
        impostor_images, detector, quality_filter, embedder
    )

    n_genuine_people = len(identities)
    print(f"\n{n_genuine_people} personne(s), {len(impostor_embeddings)} image(s) d'imposteurs.")
    if n_genuine_people < 10:
        print("Moins de 10 personnes : calibration peu fiable, a refaire.")

    P = onen_protocol(identities, impostor_embeddings)
    if int((~P["is_gen"]).sum()) >= 10 and int(P["is_gen"].sum()) >= 10:
        chosen = search_operating_point(P)
        i_scores = impostor_pair_scores(identities, impostor_embeddings, embedder)
        threshold_low = (
            threshold_at_far(i_scores, TARGET_FAR_GREY)
            if i_scores else max(0.0, chosen["T"] - 0.15)
        )
        print(f"\n1:N  seuil={chosen['T']:.4f}  min_margin={chosen['min_margin']:.3f}")
        print(f"  autorises {chosen['n_ok']}/{chosen['n_gen']} = {chosen['grant']:.2%}")
        print(f"  intrus    {chosen['n_fp']}/{chosen['n_imp']} = {chosen['fpir']:.3%}  (cible <= {TARGET_FPIR:.1%})")
        print(f"  confusions {chosen['n_mis']}/{chosen['n_gen']} = {chosen['misid']:.3%}")
        held = chosen["fpir"] <= TARGET_FPIR
        if not held:
            print("Cible 0,1 % d'intrus non tenue sur ce jeu. Ajouter des photos d'imposteurs.")
        payload = {
            "threshold": round(chosen["T"], 4),
            "threshold_low": round(threshold_low, 4),
            "min_margin": round(chosen["min_margin"], 4),
            "calibrated_on": {
                "protocol": "1:N leave-one-out",
                "n_identities": n_genuine_people,
                "target_fpir": TARGET_FPIR,
                "measured_tar": chosen["grant"],
                "measured_fpir": chosen["fpir"],
                "measured_misid": chosen["misid"],
                "fpir_target_held": held,
            },
            "status": (
                "calibre sur la camera du site"
                if n_genuine_people >= 10 and held
                else "provisoire -- trop peu de personnes ou FPIR > 0,1 %"
            ),
        }
    else:
        print("\nTrop peu de sondes 1:N : repli sur des paires 1:1 (moins fidele a la porte).")
        g_scores = genuine_pairs_scores(identities, embedder)
        i_scores = impostor_pair_scores(identities, impostor_embeddings, embedder)
        threshold_strict = threshold_at_far(i_scores, TARGET_FPIR)
        threshold_low = threshold_at_far(i_scores, TARGET_FAR_GREY)
        measured_far = float(np.mean(np.array(i_scores) >= threshold_strict)) if i_scores else float("nan")
        measured_tar = float(np.mean(np.array(g_scores) >= threshold_strict)) if g_scores else float("nan")
        print(f"Seuil 1:1 (FAR <= {TARGET_FPIR:.1%}) : {threshold_strict:.4f}")
        print(f"FAR mesure : {measured_far:.3%}   TAR mesure : {measured_tar:.3%}")
        payload = {
            "threshold": round(threshold_strict, 4),
            "threshold_low": round(threshold_low, 4),
            "min_margin": 0.0,
            "calibrated_on": {
                "protocol": "1:1 pairs (repli)",
                "n_identities": n_genuine_people,
                "measured_far": measured_far,
                "measured_tar": measured_tar,
            },
            "status": "provisoire -- calibration 1:1, a refaire en 1:N",
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nEcrit : {args.output}")
    print("Redemarrer le service edge pour appliquer les seuils.")


if __name__ == "__main__":
    main()
