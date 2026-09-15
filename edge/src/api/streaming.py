"""
Endpoints de streaming vidéo MJPEG (flux brut et flux avec détections).
Utilisé par le dashboard pour l'affichage en direct.
"""

import time
import cv2
from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import StreamingResponse
import secrets
import os

router = APIRouter()

FRAME_DELAY = 0.05  # ~20 fps max, évite de saturer le CPU du Pi


def _verify_stream_api_key(api_key: str) -> None:
    valid_key = os.environ.get("FACE_RECOGNITION_API_KEY")
    if not valid_key or not api_key or not secrets.compare_digest(api_key, valid_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clé API invalide ou manquante.")


def register_streaming_routes(app, camera, detector, quality_filter):
    def generate_raw():
        while True:
            frame = camera.read_frame()
            _, jpeg = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
            time.sleep(FRAME_DELAY)

    def generate_detected():
        while True:
            frame = camera.read_frame()
            detections = detector.detect(frame)
            for face in detections:
                x, y, w, h = face["bbox"]
                is_valid = quality_filter.is_valid(frame, face)
                color = (0, 255, 0) if is_valid else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                label = f"{face['confidence']:.2f}"
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            _, jpeg = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
            time.sleep(FRAME_DELAY)

    @router.get("/stream/raw")
    def stream_raw(api_key: str = Query(...)):
        _verify_stream_api_key(api_key)
        return StreamingResponse(generate_raw(), media_type="multipart/x-mixed-replace; boundary=frame")

    @router.get("/stream/detected")
    def stream_detected(api_key: str = Query(...)):
        _verify_stream_api_key(api_key)
        return StreamingResponse(generate_detected(), media_type="multipart/x-mixed-replace; boundary=frame")

    app.include_router(router)
    