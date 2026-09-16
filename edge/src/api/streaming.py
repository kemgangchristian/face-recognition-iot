"""
Endpoints de streaming vidéo MJPEG avec identification faciale en direct.

Deux flux exposés :
  - /stream/raw       : image brute, sans traitement (capture d'enrôlement,
                         évite de photographier les rectangles de détection)
  - /stream/detected  : détection + identification en direct, nom affiché
                         sur l'image, journalisation avec cooldown

Le flux vidéo (balise <img>) n'est PAS proxifié par le frontend Next.js
(voir dashboard/lib/api.ts) : un flux MJPEG continu à travers une route
serverless/edge est atypique et fragile (limites de durée de connexion,
mise en tampon). Le navigateur contacte donc directement le Pi pour ces
deux routes, avec `credentials: "include"` pour transmettre le cookie de
session malgré l'origine différente.
"""

import os
import time

import cv2
from fastapi import APIRouter, Query, Request, HTTPException, status
from fastapi.responses import StreamingResponse

from api.session_auth import is_session_valid
from api.auth import check_api_key

router = APIRouter()

FRAME_DELAY_DETECTED = 0.1  # ~10 fps — l'identification est coûteuse en CPU
FRAME_DELAY_RAW = 0.1
LOG_COOLDOWN_SECONDS = 30  # évite d'inonder access_logs si une personne reste devant la caméra

# En-têtes anti-cache : un flux MJPEG ne doit jamais être mis en cache par
# le navigateur ou un proxy intermédiaire.
_STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

# Mémorise le dernier moment de journalisation par identité (ou "unknown"
# partagé pour tous les visages non reconnus), pour appliquer le cooldown.
_last_logged: dict = {}


def _verify_stream_access(request: Request, api_key: str | None) -> None:
    """
    Autorise l'accès au flux via cookie de session (dashboard) ou clé API
    en paramètre d'URL (les balises <img> ne peuvent pas envoyer de header
    personnalisé, d'où le passage par query string pour ce cas précis).
    """
    if is_session_valid(request):
        return
    if check_api_key(api_key):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Accès non autorisé.")


def _should_log(identity_key) -> bool:
    """Retourne True si le cooldown de journalisation est écoulé pour
    cette identité (ou "unknown" pour un visage non reconnu)."""
    now = time.time()
    last = _last_logged.get(identity_key, 0)
    if now - last >= LOG_COOLDOWN_SECONDS:
        _last_logged[identity_key] = now
        return True
    return False


def register_streaming_routes(app, camera, detector, quality_filter, embedder, matcher, enrollment, db_lock):
    """Enregistre les routes de streaming sur l'app FastAPI, en réutilisant
    les instances de service déjà chargées au démarrage (aucun rechargement
    de modèle par requête)."""

    def generate_raw():
        while True:
            frame = camera.read_frame()
            _, jpeg = cv2.imencode(".jpg", frame)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            time.sleep(FRAME_DELAY_RAW)

    def generate_detected():
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)

            for face in detections:
                x, y, w, h = face["bbox"]
                is_valid = quality_filter.is_valid(frame, face)

                if is_valid:
                    embedding = embedder.extract(frame, face)
                    with db_lock:
                        result = matcher.match(embedding)

                    matched = result["matched"]
                    name = result["full_name"] if matched else "Inconnu"
                    color = (0, 255, 0) if matched else (0, 0, 255)

                    # Journalise au plus une fois par cooldown, par identité
                    # (ou "unknown" partagé) — évite de saturer access_logs
                    # si une personne reste immobile devant la caméra.
                    log_key = result["identity_id"] if matched else "unknown"
                    if _should_log(log_key):
                        with db_lock:
                            enrollment.log_access_attempt(
                                identity_id=result["identity_id"],
                                matched=matched,
                                confidence=result["confidence"],
                            )

                    label = f"{name} ({result['confidence']:.2f})"
                else:
                    color = (0, 165, 255)  # orange : visage détecté mais qualité insuffisante
                    label = "Qualite insuffisante"

                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            _, jpeg = cv2.imencode(".jpg", frame)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            time.sleep(FRAME_DELAY_DETECTED)

    @router.get("/stream/raw")
    def stream_raw(request: Request, api_key: str | None = Query(None)):
        """Flux vidéo brut, sans overlay — utilisé pour la capture d'enrôlement."""
        _verify_stream_access(request, api_key)
        return StreamingResponse(
            generate_raw(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers=_STREAM_HEADERS,
        )

    @router.get("/stream/detected")
    def stream_detected(request: Request, api_key: str | None = Query(None)):
        """Flux vidéo avec détection et identification en direct."""
        _verify_stream_access(request, api_key)
        return StreamingResponse(
            generate_detected(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers=_STREAM_HEADERS,
        )

    app.include_router(router)
    