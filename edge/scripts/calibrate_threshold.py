"""
Calibration des seuils (strict / second facteur) sur des données RÉELLES
du site, capturées par la caméra de l'appareil -- transpose sur SFace la
même méthodologie que le Notebook 2 (calibration sur un jeu de validation
distinct des identités enrôlées, avec marge de sécurité), plutôt que de
garder le seuil 0.5 d'origine, qui n'a jamais été mesuré empiriquement sur
ce site (cf. le commentaire de matcher.py : "à recalibrer rigoureusement").

Usage :
    python -m scripts.calibrate_threshold --site-dir captures/

Structure attendue de --site-dir :
    captures/
      genuine/<identifiant_personne>/*.jpg   # plusieurs photos par personne
                                              # AUTORISÉE, prises par LA caméra
                                              # du site (pas des photos LFW)
      impostors/*.jpg                        # photos de personnes NON
                                              # autorisées (ou variées), pour
                                              # mesurer le taux de fausses
                                              # acceptations

Le script :
1. extrait les embeddings SFace de toutes les images (mêmes FaceDetector +
   FaceEmbedder que la production -- garantit une calibration cohérente
   avec le pipeline réel, contrairement à une calibration faite sur LFW),
2. calcule un seuil strict tel que le taux de fausses acceptations mesuré
   soit <= TARGET_FAR / SAFETY_FACTOR (marge de sécurité, comme en
   Notebook 2 -- un seuil pile sur la cible se dégrade sur de nouvelles
   personnes non vues pendant la calibration),
3. calcule un seuil bas (second facteur) pour TARGET_FAR_GREY,
4. écrit edge/storage_data/thresholds.json, lu par l'API au démarrage.

⚠️ Avec seulement quelques dizaines de personnes de calibration, la borne
statistique sur le taux de fausses acceptations reste large (même limite
que celle rencontrée avec LFW dans le Notebook 2) -- à refaire/élargir
périodiquement à mesure que plus de monde passe devant la caméra.
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
from recognition.face_embedder import FaceEmbedder

TARGET_FAR = 0.001       # 0.1 % de fausses acceptations visé (cf. Notebook 2)
SAFETY_FACTOR = 5        # calibré à TARGET_FAR / 5 = 0.02 %, marge de sécurité
TARGET_FAR_GREY = 0.05   # seuil bas : jusqu'à 5 % de zone grise tolérée


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
        print(f"  ({skipped} image(s) ignorée(s) -- aucun visage exploitable)")
    return embeddings


def genuine_pairs_scores(identities: dict, embedder) -> list:
    """Scores des paires (même personne, images différentes)."""
    scores = []
    for embs in identities.values():
        for a, b in itertools.combinations(embs, 2):
            scores.append(embedder.compare(a, b))
    return scores


def impostor_scores(identities: dict, impostor_embeddings: list, embedder) -> list:
    """Scores des paires (personnes différentes) : entre identités
    enrôlées entre elles, et contre le jeu d'imposteurs dédié."""
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
    """Plus petit seuil tel que le taux de scores >= seuil reste <= far."""
    arr = np.sort(np.array(scores))[::-1]
    idx = max(0, int(len(arr) * far) - 1)
    return float(arr[idx]) if len(arr) else 0.5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", required=True, type=Path)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[1] / "storage_data" / "thresholds.json",
    )
    args = parser.parse_args()

    genuine_dir = args.site_dir / "genuine"
    impostor_dir = args.site_dir / "impostors"
    if not genuine_dir.is_dir():
        sys.exit(f"Dossier introuvable : {genuine_dir}")

    detector = FaceDetector()
    quality_filter = QualityFilter()
    embedder = FaceEmbedder()

    identities = {}
    for person_dir in sorted(p for p in genuine_dir.iterdir() if p.is_dir()):
        images = sorted(person_dir.glob("*.jpg")) + sorted(person_dir.glob("*.jpeg"))
        print(f"Extraction -- {person_dir.name} ({len(images)} image(s))")
        embs = extract_all_embeddings(images, detector, quality_filter, embedder)
        if len(embs) < 2:
            print(f"  ⚠️ {person_dir.name} : moins de 2 images exploitables, ignorée pour le calcul intra-identité.")
            continue
        identities[person_dir.name] = embs

    impostor_images = sorted(impostor_dir.glob("*.jpg")) + sorted(impostor_dir.glob("*.jpeg")) if impostor_dir.is_dir() else []
    print(f"\nExtraction -- imposteurs ({len(impostor_images)} image(s))")
    impostor_embeddings = extract_all_embeddings(impostor_images, detector, quality_filter, embedder)

    n_genuine_people = len(identities)
    print(f"\n{n_genuine_people} personne(s) exploitable(s) pour la calibration, "
          f"{len(impostor_embeddings)} image(s) d'imposteurs.")
    if n_genuine_people < 10:
        print("⚠️ Moins de 10 personnes : la calibration sera très peu fiable statistiquement. "
              "Continue seulement pour un premier réglage grossier, à refaire avec plus de monde.")

    g_scores = genuine_pairs_scores(identities, embedder)
    i_scores = impostor_scores(identities, impostor_embeddings, embedder)
    print(f"{len(g_scores)} paires même-personne, {len(i_scores)} paires personnes-différentes.")

    calib_far = TARGET_FAR / SAFETY_FACTOR
    threshold_strict = threshold_at_far(i_scores, calib_far)
    threshold_low = threshold_at_far(i_scores, TARGET_FAR_GREY)

    measured_far = float(np.mean(np.array(i_scores) >= threshold_strict)) if i_scores else float("nan")
    measured_tar = float(np.mean(np.array(g_scores) >= threshold_strict)) if g_scores else float("nan")

    print(f"\nSeuil strict calibré (cible {calib_far:.3%})     : {threshold_strict:.4f}")
    print(f"Seuil second facteur calibré (cible {TARGET_FAR_GREY:.1%}) : {threshold_low:.4f}")
    print(f"FAR mesuré au seuil strict  : {measured_far:.3%}")
    print(f"TAR mesuré au seuil strict  : {measured_tar:.3%}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump({
            "threshold": round(threshold_strict, 4),
            "threshold_low": round(threshold_low, 4),
            "calibrated_on": {
                "n_identities": n_genuine_people,
                "n_genuine_pairs": len(g_scores),
                "n_impostor_pairs": len(i_scores),
                "measured_far": measured_far,
                "measured_tar": measured_tar,
            },
            "status": "CALIBRÉ SUR DONNÉES RÉELLES DU SITE" if n_genuine_people >= 10
                      else "PROVISOIRE -- trop peu de personnes, à refaire",
        }, f, indent=2, ensure_ascii=False)
    print(f"\nÉcrit : {args.output}")
    print("Redémarre le service edge pour appliquer les nouveaux seuils.")


if __name__ == "__main__":
    main()
    