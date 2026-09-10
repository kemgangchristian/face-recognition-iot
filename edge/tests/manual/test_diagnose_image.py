"""
Script de diagnostic : analyse une image fixe pour voir exactement
pourquoi elle est acceptée ou rejetée par le pipeline détection + filtre qualité.

Usage : python edge/tests/manual/test_diagnose_image.py chemin/vers/image.jpg
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import cv2
from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter


def main():
    if len(sys.argv) < 2:
        print("Usage : python test_diagnose_image.py chemin/vers/image.jpg")
        return

    image_path = sys.argv[1]
    frame = cv2.imread(image_path)

    if frame is None:
        print(f"Impossible de lire l'image : {image_path}")
        return

    print(f"Image chargee : {frame.shape[1]}x{frame.shape[0]} pixels")

    detector = FaceDetector()
    quality_filter = QualityFilter()

    detections = detector.detect(frame)
    print(f"\nNombre de visages detectes par YuNet (avant filtre qualite) : {len(detections)}")

    if not detections:
        print("YuNet ne detecte AUCUN visage dans cette image.")
        return

    for i, face in enumerate(detections):
        x, y, w, h = face["bbox"]
        confidence = face["confidence"]

        y_end = min(y + h, frame.shape[0])
        x_end = min(x + w, frame.shape[1])
        crop = frame[max(y, 0):y_end, max(x, 0):x_end]
        sharpness = quality_filter._compute_sharpness(crop) if crop.size > 0 else -1

        is_valid = quality_filter.is_valid(frame, face)

        print(f"\nVisage {i+1} :")
        print(f"  bbox={face['bbox']} | confiance={confidence:.2f} | nettete={sharpness:.1f}")
        print(f"  Seuils actuels : min_confidence={quality_filter.min_confidence}, "
              f"min_face_size={quality_filter.min_face_size}, "
              f"min_sharpness={quality_filter.min_sharpness}")
        print(f"  -> Valide selon le filtre qualite : {is_valid}")


if __name__ == "__main__":
    main()
