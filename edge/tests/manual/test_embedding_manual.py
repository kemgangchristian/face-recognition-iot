"""
Script de test MANUEL pour FaceEmbedder.
Capture un embedding de référence (touche 'c'), puis compare en continu
chaque visage détecté à cette référence.

Usage : python edge/tests/test_embedding_manual.py
- 'c' : capturer le visage actuel comme référence
- 'q' : quitter
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
from capture.camera import Camera
from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter
from recognition.face_embedder import FaceEmbedder


def main():
    camera = Camera(source=0)
    detector = FaceDetector()
    quality_filter = QualityFilter()
    embedder = FaceEmbedder()

    reference_embedding = None

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée.")
    print("Appuie sur 'c' pour capturer une référence, 'q' pour quitter.")

    try:
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)
            valid_detections = quality_filter.filter(frame, detections)

            display_frame = frame.copy()

            if valid_detections:
                first_face = valid_detections[0]
                x, y, w, h = first_face["bbox"]

                current_embedding = embedder.extract(frame, first_face)

                if reference_embedding is not None:
                    score = embedder.compare(reference_embedding, current_embedding)
                    label = f"Similarite: {score:.3f}"
                    color = (0, 255, 0) if score > 0.5 else (0, 0, 255)
                else:
                    label = "Pas de reference (appuie sur 'c')"
                    color = (255, 255, 0)

                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(
                    display_frame, label, (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

            cv2.imshow("Test Embedding - 'c'=capturer ref, 'q'=quitter", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("c") and valid_detections:
                reference_embedding = embedder.extract(frame, valid_detections[0])
                print("Référence capturée.")

    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("Caméra arrêtée proprement.")


if __name__ == "__main__":
    main()
    