"""
Script de test MANUEL du pipeline de reconnaissance complet.
Capture -> Détection -> Matching contre la base -> Affichage du nom reconnu.

Usage : python edge/tests/test_matching_manual.py
- 'e' : enrôler le visage actuel (demande un nom dans le terminal)
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
from storage.database import Database
from storage.encryption import EncryptionManager
from storage.enrollment import EnrollmentService
from matching.matcher import FaceMatcher


def main():
    camera = Camera(source=0)
    detector = FaceDetector()
    quality_filter = QualityFilter()
    embedder = FaceEmbedder()

    db = Database()
    db.connect()
    db.init_schema()
    encryption = EncryptionManager()
    enrollment = EnrollmentService(db, encryption)
    matcher = FaceMatcher(enrollment, embedder, threshold=0.5)

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée.")
    print("Appuie sur 'e' pour enrôler, 'q' pour quitter.")

    try:
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)
            valid_detections = quality_filter.filter(frame, detections)

            display_frame = frame.copy()

            if valid_detections:
                first_face = valid_detections[0]
                x, y, w, h = first_face["bbox"]
                embedding = embedder.extract(frame, first_face)

                result = matcher.match(embedding)

                if result["matched"]:
                    label = f"{result['full_name']} ({result['confidence']:.2f})"
                    color = (0, 255, 0)
                else:
                    label = f"Inconnu ({result['confidence']:.2f})"
                    color = (0, 0, 255)

                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(
                    display_frame, label, (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
                )

            cv2.imshow("Test Matching - 'e'=enroler, 'q'=quitter", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("e") and valid_detections:
                name = input("\nNom de la personne à enrôler : ").strip()
                if name:
                    embedding = embedder.extract(frame, valid_detections[0])
                    identity_id = enrollment.enroll_identity(name)
                    enrollment.add_embedding(identity_id, embedding)
                    print(f"'{name}' enrôlé (id={identity_id}).\n")

    finally:
        camera.stop()
        db.close()
        cv2.destroyAllWindows()
        print("Caméra et base fermées proprement.")


if __name__ == "__main__":
    main()
    