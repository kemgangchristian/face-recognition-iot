"""
Script de test MANUEL pour FaceAligner.
Affiche le flux complet avec détection, et une fenêtre séparée montrant
le visage aligné (112x112) du premier visage détecté.

Usage : python edge/tests/test_alignment_manual.py
Appuie sur 'q' pour quitter.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
from capture.camera import Camera
from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter
from recognition.face_aligner import FaceAligner


def main():
    camera = Camera(source=0)
    detector = FaceDetector()
    quality_filter = QualityFilter()
    aligner = FaceAligner()

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée. Appuie sur 'q' pour quitter.")

    try:
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)
            valid_detections = quality_filter.filter(frame, detections)

            # Dessine les rectangles sur le flux principal
            for face in valid_detections:
                x, y, w, h = face["bbox"]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.imshow("Flux principal - appuie sur 'q' pour quitter", frame)

            # Aligne et affiche le premier visage valide détecté
            if valid_detections:
                first_face = valid_detections[0]
                aligned = aligner.align(frame, first_face["landmarks"])
                # Agrandi x3 pour être plus visible à l'écran (112px natif = petit)
                aligned_display = cv2.resize(aligned, (336, 336))
                cv2.imshow("Visage aligné (112x112)", aligned_display)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("Caméra arrêtée proprement.")


if __name__ == "__main__":
    main()
    