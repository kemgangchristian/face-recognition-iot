"""
API locale FastAPI : enrolement, verification, dashboard, streaming camera.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import threading
import asyncio

import numpy as np
import cv2
from fastapi import FastAPI, Security, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from access.access_controller import AccessController, AccessConfig
from access.door_actuator import build_actuator_from_env
from capture.camera import Camera
from detection.face_detector import FaceDetector
from detection.face_readiness import FaceReadinessAssessor
from detection.liveness import LivenessChecker
from detection.quality_filter import QualityFilter
from recognition.face_embedder import build_embedder
from storage.database import Database
from storage.encryption import EncryptionManager
from storage.enrollment import EnrollmentService
from matching.matcher import FaceMatcher
from mqtt.publisher import EventPublisher
from api.auth import verify_api_key
from api.session_auth import create_session, destroy_session, verify_session_or_api_key
from api.streaming import register_streaming_routes

app = FastAPI(title="Face Recognition IoT - API Edge", version="0.1.0")

# CORS : nécessaire en développement quand le dashboard tourne via `next dev`
# (localhost:3000) et appelle directement le Pi. En production, FastAPI sert
# les fichiers statiques exportés : même origine, pas de CORS requis.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+):3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Instanciation unique au démarrage ---------------------------------
# Coûteux à charger (modèles ML, connexion caméra) : fait une seule fois,
# réutilisé par toutes les requêtes.
camera = Camera()
camera.start()
detector = FaceDetector()
quality_filter = QualityFilter()
embedder = build_embedder()
readiness = FaceReadinessAssessor(detector, quality_filter)

db = Database()
db.connect()
db.init_schema()
encryption = EncryptionManager()
enrollment = EnrollmentService(db, encryption)

# Protège les accès concurrents à la connexion SQLite partagée entre
# threads (FastAPI exécute chaque requête dans un thread du pool, et le
# contrôleur d'accès tourne dans le sien).
db_lock = threading.Lock()


def _load_calibrated_thresholds() -> dict:
    """Charge les seuils calibrés sur données réelles du site
    (edge/scripts/calibrate_threshold.py) s'ils existent, sinon retombe
    sur les valeurs par défaut historiques (jamais mesurées sur ce site --
    voir l'avertissement dans matcher.py)."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "storage_data", "thresholds.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        print(f"Seuils calibrés chargés depuis {path} "
              f"(statut : {data.get('status', 'inconnu')}).")
        return {
            "threshold": data["threshold"],
            "threshold_low": data.get("threshold_low"),
            "min_margin": float(data.get("min_margin", 0.0)),
        }
    print(f"Aucun fichier de calibration ({path}). "
          f"Seuil par defaut 0.5. Lancer scripts/calibrate_threshold.py.")
    return {"threshold": 0.5, "threshold_low": None, "min_margin": 0.0}


def _build_liveness() -> LivenessChecker:
    """Construit le vérificateur de vivacité depuis l'environnement :
    LIVENESS_MODE (parallax | movement | off), LIVENESS_MIN_PARALLAX,
    LIVENESS_WINDOW_SECONDS, LIVENESS_MAX_SPECTRAL_PEAK (désactivé par défaut)."""
    peak = os.environ.get("LIVENESS_MAX_SPECTRAL_PEAK")
    liveness = LivenessChecker(
        window_seconds=float(os.environ.get("LIVENESS_WINDOW_SECONDS", "3.0")),
        min_parallax=float(os.environ.get("LIVENESS_MIN_PARALLAX", "0.12")),
        mode=os.environ.get("LIVENESS_MODE", "parallax"),
        max_spectral_peak=float(peak) if peak else None,
    )
    if liveness.mode != "parallax":
        print(f"LIVENESS_MODE={liveness.mode} : protection anti-photo affaiblie. "
              "A reserver aux demonstrations, pas a une porte reelle.")
    return liveness


event_publisher = EventPublisher()
matcher = FaceMatcher(enrollment, embedder, **_load_calibrated_thresholds())

# Contrôleur d'accès : boucle de reconnaissance en arrière-plan (caméra ->
# détection -> suivi -> reconnaissance -> vivacité -> porte), indépendante de
# tout navigateur connecté. Démarré dans l'événement `startup` ci-dessous.
door_actuator = build_actuator_from_env()
access_controller = AccessController(
    camera=camera,
    detector=detector,
    quality_filter=quality_filter,
    embedder=embedder,
    matcher=matcher,
    enrollment=enrollment,
    db_lock=db_lock,
    liveness=_build_liveness(),
    actuator=door_actuator,
    publisher=event_publisher,
    config=AccessConfig.from_env(),
)

# Le flux /stream/detected diffuse la vue du contrôleur.
register_streaming_routes(app, camera, access_controller)

RETENTION_DAYS = int(os.environ.get("ACCESS_LOGS_RETENTION_DAYS", "90"))


async def periodic_purge():
    """Purge quotidienne des logs d'acces plus anciens que RETENTION_DAYS."""
    while True:
        with db_lock:
            deleted = enrollment.purge_old_logs(RETENTION_DAYS)
        if deleted > 0:
            print(f"Purge automatique : {deleted} log(s) supprimé(s) (> {RETENTION_DAYS} jours).")
        await asyncio.sleep(24 * 60 * 60)


@app.on_event("startup")
async def start_background_tasks():
    access_controller.start()
    asyncio.create_task(periodic_purge())


@app.on_event("shutdown")
async def stop_background_tasks():
    # Arrête la boucle et VERROUILLE la porte (actionneur fermé proprement).
    access_controller.stop()


# --- Fonctions utilitaires ----------------------------------------------

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
            detail="Aucun visage exploitable détecté (absent, trop petit, ou flou).",
        )

    return valid_detections[0]


# --- Santé du service -----------------------------------------------------

@app.get("/health")
def health_check():
    """Vérifie que le service est opérationnel. Endpoint public, sans
    authentification, pour la supervision externe. `status` vaut "degraded"
    si la boucle de contrôle d'accès ne produit plus de résultats (caméra ou
    modèle en panne) : l'API répond alors, mais la porte ne s'ouvrira pas."""
    controller_status = access_controller.status()
    return {
        "status": "ok" if controller_status["healthy"] else "degraded",
        "matcher_threshold": matcher.threshold,
        "matcher_threshold_low": matcher.threshold_low,
        "access_controller": controller_status,
    }


# --- Authentification dashboard -------------------------------------------

@app.post("/login")
def login(response: Response, password: str = Form(...)):
    """
    Authentifie l'accès au dashboard web via mot de passe et pose un
    cookie de session HttpOnly. Ce cookie n'est jamais lisible par le
    JavaScript du navigateur, contrairement à une clé embarquée dans le
    bundle — voir session_auth.py pour le détail de ce choix.
    """
    create_session(response, password)
    return {"authenticated": True}


@app.post("/logout")
def logout(request: Request, response: Response):
    """Invalide immédiatement la session en cours (déconnexion réelle,
    pas une simple attente d'expiration)."""
    destroy_session(request, response)
    return {"logged_out": True}


# --- Aide à la capture d'enrôlement -----------------------------------------

@app.get("/camera/face-status")
def camera_face_status(_: None = Security(verify_session_or_api_key)):
    """
    Indique si la personne devant la caméra est bien placée pour une
    capture d'enrôlement (voir FaceReadinessAssessor). Appelé par la page
    d'enrôlement du dashboard pour n'activer le bouton « Capturer » que
    lorsque le visage est bien visible. Lecture seule : rien n'est
    enregistré, la frame est analysée puis jetée.
    """
    frame = camera.read_frame()
    face, reason = readiness.assess(frame)
    return {"ready": face is not None, "reason": reason}


# --- Enrôlement et vérification ---------------------------------------------

@app.post("/enroll")
def enroll(
    full_name: str = Form(...),
    image: UploadFile = File(...),
    _: None = Security(verify_session_or_api_key),
):
    """
    Enrôle une nouvelle identité à partir d'**une seule** image uploadée.

    La même exigence de qualité que l'indicateur du dashboard est
    revérifiée ici côté serveur : l'interface ne peut pas être contournée.

    Args:
        full_name: nom complet de la personne.
        image: fichier image (JPEG/PNG) contenant un visage exploitable.
    """
    frame = decode_image(image.file.read())
    face, reason = readiness.assess(frame)
    if face is None:
        raise HTTPException(status_code=422, detail=reason)
    embedding = embedder.extract(frame, face)

    identity_id = None
    try:
        with db_lock:
            identity_id = enrollment.enroll_identity(full_name)
            enrollment.add_embedding(identity_id, embedding)
    except Exception:
        # Rollback explicite : jamais d'identité sans embedding en base.
        if identity_id is not None:
            with db_lock:
                enrollment.delete_identity(identity_id)
        raise HTTPException(
            status_code=500,
            detail="Échec de l'enrôlement, aucune donnée enregistrée.",
        )

    return {
        "identity_id": identity_id,
        "full_name": full_name,
        "message": "Identité enrôlée avec succès.",
    }


@app.post("/verify")
def verify(
    image: UploadFile = File(...),
    _: None = Security(verify_session_or_api_key),
):
    """
    Identifie la personne présente sur une image uploadée (vérification
    ponctuelle, à la demande — par opposition à l'identification continue
    du contrôleur d'accès, voir access/access_controller.py).

    Cet endpoint identifie. Il n'ouvre pas la porte et ne verifie pas la
    vivacite (une image seule n'en porte pas la preuve). Seul le controleur
    d'acces actionne la porte.

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


# --- Journal d'accès --------------------------------------------------------

@app.get("/logs")
def get_logs(limit: int = 100, _: None = Security(verify_session_or_api_key)):
    """Récupère l'historique des tentatives de reconnaissance, du plus
    récent au plus ancien.

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
    sans attendre le cycle automatique de 24h). Réservé à l'administration
    technique : protégé par clé API uniquement, jamais appelé depuis le
    dashboard.
    """
    with db_lock:
        deleted = enrollment.purge_old_logs(RETENTION_DAYS)

    return {"deleted_count": deleted, "retention_days": RETENTION_DAYS}


# --- Gestion des identités ---------------------------------------------------

@app.get("/identities")
def get_identities(_: None = Security(verify_session_or_api_key)):
    """Liste toutes les identités enrôlées, sans jamais exposer les
    vecteurs d'embedding (données biométriques sensibles)."""
    with db_lock:
        identities = enrollment.list_identities()

    return {"count": len(identities), "identities": identities}


@app.delete("/identities/{identity_id}")
def delete_identity_endpoint(
    identity_id: int,
    _: None = Security(verify_session_or_api_key),
):
    """
    Supprime une identite et ses embeddings (droit a l'effacement).
    Expose depuis le dashboard.
    """
    with db_lock:
        deleted = enrollment.delete_identity(identity_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Identité introuvable.")

    return {"deleted": True, "identity_id": identity_id}


# --- Statistiques -----------------------------------------------------------

@app.get("/stats")
def get_stats(_: None = Security(verify_session_or_api_key)):
    """Statistiques agrégées pour les cartes du dashboard : nombre
    d'identités enrôlées, accès du jour, taux de reconnaissance."""
    with db_lock:
        stats = enrollment.get_stats()

    return stats


# --- Dashboard statique (export Next.js) ------------------------------------
# Monté en dernier : les routes API ci-dessus restent prioritaires.

_dashboard_dir = Path(
    os.environ.get("DASHBOARD_STATIC_DIR", "/app/dashboard_static")
)
if _dashboard_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=_dashboard_dir, html=True),
        name="dashboard",
    )
    