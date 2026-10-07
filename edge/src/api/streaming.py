"""
Endpoints de streaming vidéo MJPEG.

Deux flux exposés :
  - /stream/raw       : image brute, sans traitement (capture d'enrôlement,
                         évite de photographier les rectangles de détection)
  - /stream/detected  : VUE du contrôleur d'accès (access/access_controller.py)
                         avec rectangles et libellés d'état

Le flux vidéo (balise <img>) contacte directement le Pi (voir
dashboard/lib/api.ts). En production, le dashboard est servi par FastAPI
(même origine). En développement (`next dev`), CORS + cookie de session
permettent l'authentification malgré l'origine différente.

v4 : la reconnaissance ne se fait plus ici. Elle tourne en continu dans le
contrôleur d'accès (thread d'arrière-plan), qu'un navigateur soit connecté
ou non ; /stream/detected ne fait que diffuser ses images annotées. Plusieurs
spectateurs ne multiplient donc ni les traitements ni l'état partagé, et
aucune image n'est enregistrée.
"""

import time

import cv2
from fastapi import APIRouter, Query, Request, HTTPException, status
from fastapi.responses import StreamingResponse

from api.session_auth import is_session_valid
from api.auth import check_api_key

router = APIRouter()

FRAME_DELAY_RAW = 0.1

# En-têtes anti-cache : un flux MJPEG ne doit jamais être mis en cache par
# le navigateur ou un proxy intermédiaire.
_STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


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


def register_streaming_routes(app, camera, controller):
    """Enregistre les routes de streaming sur l'app FastAPI.

    Args:
        camera: caméra partagée (flux brut).
        controller: AccessController dont /stream/detected diffuse la vue.
    """

    def generate_raw():
        while True:
            frame = camera.read_frame()
            _, jpeg = cv2.imencode(".jpg", frame)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            time.sleep(FRAME_DELAY_RAW)

    def generate_detected():
        last_seq = 0
        while True:
            # Signale un spectateur : le contrôleur n'annote et n'encode des
            # JPEG que tant que quelqu'un regarde.
            controller.touch_viewer()
            item = controller.wait_for_frame(last_seq, timeout=1.0)
            if item is None:
                continue
            last_seq, jpeg = item
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"

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
        """Flux vidéo avec détection et identification en direct (vue du
        contrôleur d'accès)."""
        _verify_stream_access(request, api_key)
        return StreamingResponse(
            generate_detected(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers=_STREAM_HEADERS,
        )

    app.include_router(router)
    