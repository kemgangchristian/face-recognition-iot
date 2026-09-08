"""
Script de test MANUEL combinant Camera + FaceDetector + QualityFilter.
À lancer soi-même en local — n'est PAS un test automatisé.

Usage : python edge/tests/test_detection_manual.py
Appuie sur 'q' pour quitter.

Affichage :
- Rectangle VERT = visage accepté (passe le filtre qualité)
- Rectangle ROUGE = visage rejeté (raison affichée à côté)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
from capture.camera import Camera
from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter


def get_rejection_reason(frame, detection, quality_filter):
    """Détermine pourquoi une détection a été rejetée (pour affichage debug)."""
    x, y, w, h = detection["bbox"]

    if detection["confidence"] < quality_filter.min_confidence:
        return f"confiance faible ({detection['confidence']:.2f})"

    if w < quality_filter.min_face_size or h < quality_filter.min_face_size:
        return f"trop petit ({w}x{h}px)"

    y_end = min(y + h, frame.shape[0])
    x_end = min(x + w, frame.shape[1])
    face_crop = frame[max(y, 0):y_end, max(x, 0):x_end]

    if face_crop.size == 0:
        return "hors cadre"

    sharpness = quality_filter._compute_sharpness(face_crop)
    if sharpness < quality_filter.min_sharpness:
        return f"flou (nettete={sharpness:.1f})"

    return "inconnu"


def draw_detections(frame, detections, quality_filter):
    """Dessine les détections : vert si acceptée, rouge avec raison si rejetée."""
    for face in detections:
        x, y, w, h = face["bbox"]
        is_valid = quality_filter.is_valid(frame, face)

        color = (0, 255, 0) if is_valid else (0, 0, 255)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        if is_valid:
            label = f"OK {face['confidence']:.2f}"
        else:
            reason = get_rejection_reason(frame, face, quality_filter)
            label = f"REJET: {reason}"

        cv2.putText(
            frame, label, (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
        )

    return frame


def main():
    camera = Camera(source=0)
    detector = FaceDetector()
    quality_filter = QualityFilter()

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée. Appuie sur 'q' pour quitter.")

    try:
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)

            # Diagnostic console : affiche le détail de chaque détection
            for face in detections:
                is_valid = quality_filter.is_valid(frame, face)
                if not is_valid:
                    reason = get_rejection_reason(frame, face, quality_filter)
                    print(f"REJETÉ — {reason} | confiance={face['confidence']:.2f} | bbox={face['bbox']}")

            frame = draw_detections(frame, detections, quality_filter)

            cv2.imshow("Test Quality Filter - appuie sur 'q' pour quitter", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("Caméra arrêtée proprement.")


if __name__ == "__main__":
    main()
