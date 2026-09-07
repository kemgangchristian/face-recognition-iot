"""
API locale FastAPI — endpoints enrôlement, vérification, santé.
Story 5.1 — Epic 5.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import threading
import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException

from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter
from recognition.face_embedder import FaceEmbedder
from storage.database import Database
from storage.encryption import EncryptionManager
from storage.enrollment import EnrollmentService
from matching.matcher import FaceMatcher
from mqtt.publisher import EventPublisher


app = FastAPI(title="Face Recognition IoT - API Edge", version="0.1.0")

# Instanciation unique au démarrage — cohérent avec le pattern déjà utilisé
# dans tous nos scripts (coûteux à charger, on le fait une seule fois).
detector = FaceDetector()
quality_filter = QualityFilter()
embedder = FaceEmbedder()

db = Database()
db.connect()
db.init_schema()
encryption = EncryptionManager()
enrollment = EnrollmentService(db, encryption)
# Protège les accès concurrents à la connexion SQLite partagée entre threads
# (FastAPI exécute chaque requête dans un thread différent du pool).
db_lock = threading.Lock()
event_publisher = EventPublisher()
matcher = FaceMatcher(enrollment, embedder, threshold=0.5)


def decode_image(file_bytes: bytes) -> np.ndarray:
    """Décode une image uploadée (bytes JPEG/PNG) en tableau numpy BGR,
    format attendu par tous nos modules OpenCV."""
    array = np.frombuffer(file_bytes, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Image invalide ou illisible.")
    return frame


def detect_single_valid_face(frame: np.ndarray) -> dict:
    """Détecte et filtre les visages d'une frame, retourne le premier
    visage valide ou lève une erreur explicite sinon."""
    detections = detector.detect(frame)
    valid_detections = quality_filter.filter(frame, detections)

    if not valid_detections:
        raise HTTPException(
            status_code=422,
            detail="Aucun visage exploitable détecté (absent, trop petit, ou flou)."
        )

    return valid_detections[0]


@app.get("/health")
def health_check():
    """Vérifie que le service est opérationnel."""
    return {"status": "ok"}


@app.post("/enroll")
def enroll(full_name: str = Form(...), image: UploadFile = File(...)):
    """
    Enrôle une nouvelle identité à partir d'une image uploadée.

    Args:
        full_name: nom complet de la personne (champ de formulaire).
        image: fichier image (JPEG/PNG) contenant un visage exploitable.
    """
    frame = decode_image(image.file.read())
    face = detect_single_valid_face(frame)

    embedding = embedder.extract(frame, face)

    with db_lock:
        identity_id = enrollment.enroll_identity(full_name)
        enrollment.add_embedding(identity_id, embedding)

    return {
        "identity_id": identity_id,
        "full_name": full_name,
        "message": "Identité enrôlée avec succès.",
    }


@app.post("/verify")
def verify(image: UploadFile = File(...)):
    """
    Identifie la personne présente sur une image uploadée.

    Args:
        image: fichier image (JPEG/PNG) contenant un visage exploitable.
    """
    frame = decode_image(image.file.read())
    face = detect_single_valid_face(frame)

    embedding = embedder.extract(frame, face)

    with db_lock:
        result = matcher.match(embedding)

    event_publisher.publish_verification_event(
        matched=result["matched"],
        full_name=result["full_name"],
        confidence=result["confidence"],
    )

    return result
