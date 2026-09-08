"""
Script de test MANUEL du pipeline d'enrôlement complet :
Capture -> Détection -> Embedding -> Chiffrement -> Stockage -> Relecture -> Comparaison.

Usage : python edge/tests/test_enrollment_manual.py
Appuie sur 'e' pour enrôler le visage actuel, 'q' pour quitter.
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

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée.")
    print("Appuie sur 'e' pour enrôler le visage actuel, 'q' pour quitter.")

    try:
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)
            valid_detections = quality_filter.filter(frame, detections)

            display_frame = frame.copy()
            if valid_detections:
                x, y, w, h = valid_detections[0]["bbox"]
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.imshow("Test Enrollment - 'e'=enroler, 'q'=quitter", display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("e") and valid_detections:
                print("\n--- Enrôlement en cours ---")

                embedding = embedder.extract(frame, valid_detections[0])
                print(f"1. Embedding extrait ({len(embedding)} dimensions)")

                identity_id = enrollment.enroll_identity("Test User Enrollment")
                print(f"2. Identité créée en base (id={identity_id})")

                enrollment.add_embedding(identity_id, embedding)
                print("3. Embedding chiffré et stocké")

                all_embeddings = enrollment.get_all_embeddings()
                print(f"4. Relecture base : {len(all_embeddings)} embedding(s) déchiffré(s) trouvé(s)")

                stored_entry = next(
                    (e for e in all_embeddings if e["identity_id"] == identity_id), None
                )
                if stored_entry is not None:
                    score = embedder.compare(embedding, stored_entry["vector"])
                    print(f"5. Comparaison original vs relu-déchiffré : score={score:.4f}")
                    if score > 0.99:
                        print(" Pipeline complet validé : le vecteur relu est identique à l'original.")
                    else:
                        print(" ATTENTION : le vecteur relu diffère de l'original.")

                print("--- Fin enrôlement ---\n")

    finally:
        camera.stop()
        db.close()
        cv2.destroyAllWindows()
        print("Caméra et base fermées proprement.")


if __name__ == "__main__":
    main()
