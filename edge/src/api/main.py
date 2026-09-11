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
import asyncio
from fastapi import FastAPI, Security, UploadFile, File, Form, HTTPException
from detection.face_detector import FaceDetector
from detection.quality_filter import QualityFilter
from recognition.face_embedder import FaceEmbedder
from storage.database import Database
from storage.encryption import EncryptionManager
from storage.enrollment import EnrollmentService
from matching.matcher import FaceMatcher
from mqtt.publisher import EventPublisher
from api.auth import verify_api_key


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
RETENTION_DAYS = int(os.environ.get("ACCESS_LOGS_RETENTION_DAYS", "90"))

async def periodic_purge():
    """
    Tâche de fond : purge automatiquement les logs d'accès expirés,
    une fois par jour. Story 9.1 — conformité RGPD (minimisation des données).
    """
    while True:
        with db_lock:
            deleted = enrollment.purge_old_logs(RETENTION_DAYS)
        if deleted > 0:
            print(f"Purge automatique : {deleted} log(s) supprimé(s) (> {RETENTION_DAYS} jours).")
        await asyncio.sleep(24 * 60 * 60)  # 24 heures


@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(periodic_purge())

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
def enroll(full_name: str = Form(...), image: UploadFile = File(...), _: None = Security(verify_api_key)):
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
def verify(image: UploadFile = File(...), _: None = Security(verify_api_key)):
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
        enrollment.log_access_attempt(
            identity_id=result["identity_id"],
            matched=result["matched"],
            confidence=result["confidence"],
        )

    event_publisher.publish_verification_event(
        matched=result["matched"],
        full_name=result["full_name"],
        confidence=result["confidence"],
    )

    return result



@app.get("/logs")
def get_logs(limit: int = 100, _: None = Security(verify_api_key)):
    """
    Récupère l'historique des tentatives de reconnaissance, du plus récent
    au plus ancien.

    Args:
        limit: nombre maximum de logs à retourner (défaut 100).
    """
    with db_lock:
        logs = enrollment.get_access_logs(limit=limit)

    return {"count": len(logs), "logs": logs}



@app.post("/admin/purge-logs")
def trigger_purge_now(_: None = Security(verify_api_key)):
    """
    Déclenche une purge immédiate des logs expirés (utile pour tester
    sans attendre le cycle automatique de 24h).
    """
    with db_lock:
        deleted = enrollment.purge_old_logs(RETENTION_DAYS)

    return {"deleted_count": deleted, "retention_days": RETENTION_DAYS}
