"""
Endpoints de streaming vidéo MJPEG avec identification en direct.
Le flux détecte ET identifie chaque visage, avec un cooldown de
journalisation pour éviter de saturer access_logs (une personne qui reste
devant la caméra ne doit pas générer des centaines d'entrées par minute).
"""

import time
import cv2
from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import StreamingResponse
import secrets
import os

router = APIRouter()

FRAME_DELAY = 0.1  # ~10 fps — l'identification est plus coûteuse que la
                    # simple détection, on réduit la cadence pour le CPU du Pi
LOG_COOLDOWN_SECONDS = 30

# Mémorise le dernier moment où chaque identité a été journalisée, pour
# appliquer le cooldown (dict simple, en mémoire, pas besoin de DB pour ça).
_last_logged: dict = {}


def _verify_stream_api_key(api_key: str) -> None:
    valid_key = os.environ.get("FACE_RECOGNITION_API_KEY")
    if not valid_key or not api_key or not secrets.compare_digest(api_key, valid_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clé API invalide ou manquante.")


def _should_log(identity_key) -> bool:
    """Retourne True si ça fait plus de LOG_COOLDOWN_SECONDS depuis le
    dernier log pour cette identité (ou 'unknown' pour les inconnus)."""
    now = time.time()
    last = _last_logged.get(identity_key, 0)
    if now - last >= LOG_COOLDOWN_SECONDS:
        _last_logged[identity_key] = now
        return True
    return False


def register_streaming_routes(app, camera, detector, quality_filter, embedder, matcher, enrollment, db_lock):
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

                    # Cooldown par identité (ou "unknown" partagé pour tous
                    # les inconnus, pour éviter un flot d'entrées "Inconnu")
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
                    color = (0, 165, 255)  # orange : détecté mais qualité insuffisante
                    label = "Qualite insuffisante"

                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            _, jpeg = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
            time.sleep(FRAME_DELAY)

    def generate_raw():
        while True:
            frame = camera.read_frame()
            _, jpeg = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
            time.sleep(0.1)

    @router.get("/stream/raw")
    def stream_raw(api_key: str = Query(...)):
        _verify_stream_api_key(api_key)
        return StreamingResponse(generate_raw(), media_type="multipart/x-mixed-replace; boundary=frame")

    
    @router.get("/stream/detected")
    def stream_detected(api_key: str = Query(...)):
        _verify_stream_api_key(api_key)
        return StreamingResponse(generate_detected(), media_type="multipart/x-mixed-replace; boundary=frame")

    app.include_router(router)
