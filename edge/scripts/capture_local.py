#!/usr/bin/env python3
"""
Capture guidée d'un jeu de test de calibration depuis la webcam locale
(validation du flux AVANT déploiement sur le Pi).

La webcam d'un laptop n'a pas le meme capteur que le Pi. Les seuils
obtenus ici ne valident que le flux. Recalibrer sur le Pi.

Usage (depuis edge/) :
    python -m scripts.capture_local
    python -m scripts.capture_local --genuine christian marie --count 6 --impostors-count 5

Résultat :
    edge/captures/
      genuine/<nom>/photo1.jpg ...
      impostors/photo1.jpg ...
"""

import argparse
import time
from pathlib import Path

import cv2

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "captures"


def capture_batch(cap, out_dir: Path, count: int, interval: float, label: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = len(list(out_dir.glob("photo*.jpg")))
    saved = 0
    while saved < count:
        print(f"  [{label}] photo {saved + 1}/{count} dans {interval:.0f} s, change légèrement de pose...")
        time.sleep(interval)
        ok, frame = cap.read()
        if not ok:
            print("  Lecture webcam échouée, nouvel essai.")
            continue
        out = out_dir / f"photo{existing + saved + 1}.jpg"
        cv2.imwrite(str(out), frame)
        print(f"  Sauvegardé : {out}")
        saved += 1
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--genuine", nargs="+", default=["christian", "personne2"],
                        help="noms des personnes autorisées (un dossier chacune)")
    parser.add_argument("--count", type=int, default=6, help="photos par personne autorisée")
    parser.add_argument("--impostors-count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(
            "Webcam inaccessible. Autorise ton terminal dans Réglages Système > "
            "Confidentialité et sécurité > Caméra, puis relance."
        )
    for _ in range(15):  # laisse l'exposition se stabiliser
        cap.read()

    try:
        for name in args.genuine:
            input(f"\n>>> Prépare '{name}' devant la caméra, puis appuie sur Entrée...")
            capture_batch(cap, args.output / "genuine" / name, args.count, args.interval, name)

        input("\n>>> Prépare une PERSONNE NON ENRÔLÉE (imposteur), puis appuie sur Entrée...")
        capture_batch(cap, args.output / "impostors", args.impostors_count, args.interval, "imposteur")
    finally:
        cap.release()

    print(f"\nTerminé. Jeu de test dans : {args.output}")
    print("Étape suivante : python -m scripts.calibrate_threshold --site-dir captures/")


if __name__ == "__main__":
    main()
    