"""
Script de test MANUEL combinant Camera + FaceDetector.
À lancer soi-même en local — n'est PAS un test automatisé.

Usage : python edge/tests/test_detection_manual.py
Appuie sur 'q' pour quitter.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
from capture.camera import Camera
from detection.face_detector import FaceDetector


def draw_detections(frame, detections):
    """Dessine les bounding boxes et scores de confiance sur la frame."""
    for face in detections:
        x, y, w, h = face["bbox"]
        confidence = face["confidence"]

        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        label = f"{confidence:.2f}"
        cv2.putText(
            frame, label, (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )

        for point in face["landmarks"]:
            cv2.circle(frame, tuple(point), 2, (0, 0, 255), -1)

    return frame


def main():
    camera = Camera(source=0)
    detector = FaceDetector()

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée. Appuie sur 'q' pour quitter.")

    try:
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)
            frame = draw_detections(frame, detections)

            cv2.imshow("Test Detection - appuie sur 'q' pour quitter", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("Caméra arrêtée proprement.")


if __name__ == "__main__":
    main()
    