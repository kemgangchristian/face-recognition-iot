"""
Benchmark du pipeline complet sur Raspberry Pi réel.
Story 1.4 — Epic 1 / Story 2.5 — Epic 2.
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from capture.camera import Camera
from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter
from recognition.face_embedder import FaceEmbedder


def benchmark_step(name, func, n_runs=5):
    times = []
    result = None
    for _ in range(n_runs):
        start = time.perf_counter()
        result = func()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    avg = sum(times) / len(times)
    print(f"{name:30s} : {avg:7.1f} ms (min={min(times):.1f}, max={max(times):.1f})")
    return result


def main():
    print("=== Benchmark pipeline complet — Raspberry Pi ===\n")

    camera = Camera()
    detector = FaceDetector()
    quality_filter = QualityFilter()
    embedder = FaceEmbedder()

    camera.start()

    print("Assure-toi d'être bien visible face à la caméra.\n")
    time.sleep(2)

    frame = benchmark_step("1. Capture (rpicam-still)", lambda: camera.read_frame())
    detections = benchmark_step("2. Détection (YuNet)", lambda: detector.detect(frame))

    if not detections:
        print("\n Aucun visage détecté — repositionne-toi et relance le script.")
        camera.stop()
        return

    valid = benchmark_step("3. Filtrage qualité", lambda: quality_filter.filter(frame, detections))

    if not valid:
        print("\n Visage détecté mais rejeté par le filtre qualité — relance le script.")
        camera.stop()
        return

    embedding = benchmark_step(
        "4. Alignement + Embedding (SFace)",
        lambda: embedder.extract(frame, valid[0])
    )

    camera.stop()
    print(f"\nEmbedding extrait : {len(embedding)} dimensions")
    print("\n=== Fin du benchmark ===")


if __name__ == "__main__":
    main()
