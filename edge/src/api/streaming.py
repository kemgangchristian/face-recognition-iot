"""
Endpoints de streaming vidéo MJPEG avec identification faciale en direct.

Deux flux exposés :
  - /stream/raw       : image brute, sans traitement (capture d'enrôlement,
                         évite de photographier les rectangles de détection)
  - /stream/detected  : détection + identification en direct, nom affiché
                         sur l'image, journalisation avec cooldown

Le flux vidéo (balise <img>) contacte directement le Pi (voir
dashboard/lib/api.ts). En production, le dashboard est servi par FastAPI
(même origine). En développement (`next dev`), CORS + cookie de session
permettent l'authentification malgré l'origine différente.

v2 (retouche production) :
- L'ouverture d'accès n'est plus décidée sur une seule frame : un suivi
  positionnel simple (par recouvrement de bbox, suffisant pour un usage
  mono-visage de porte d'accès) alimente un MultiFrameConsensus, qui exige
  plusieurs détections concordantes avant "granted".
- Un LivenessChecker (signaux RGB faibles -- voir detection/liveness.py et
  son avertissement) doit aussi être positif avant que l'accès ne soit
  effectivement accordé. Sans lui, seul le second facteur reste proposé.
- Les états affichés distinguent désormais : qualité insuffisante,
  inconnu, second facteur requis, vivacité non confirmée, en cours
  d'analyse (n/N), et accès autorisé.
"""

import os
import time

import cv2
from fastapi import APIRouter, Query, Request, HTTPException, status
from fastapi.responses import StreamingResponse

from api.session_auth import is_session_valid
from api.auth import check_api_key
from matching.matcher import MultiFrameConsensus
from detection.liveness import LivenessChecker

router = APIRouter()

FRAME_DELAY_DETECTED = 0.1  # ~10 fps — l'identification est coûteuse en CPU
FRAME_DELAY_RAW = 0.1
LOG_COOLDOWN_SECONDS = 30  # évite d'inonder access_logs si une personne reste devant la caméra
TRACK_TIMEOUT_SECONDS = 2.0  # au-delà, une bbox non revue est considérée comme un visage disparu
TRACK_IOU_THRESHOLD = 0.3    # recouvrement minimal pour associer une détection à un suivi existant

FRAMES_REQUIRED = int(os.environ.get("ACCESS_FRAMES_REQUIRED", "3"))
FRAMES_WINDOW = int(os.environ.get("ACCESS_FRAMES_WINDOW", "5"))

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


def _bbox_iou(a, b) -> float:
    """Intersection sur union de deux bbox (x, y, w, h)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix0, iy0 = max(ax, bx), max(ay, by)
    ix1, iy1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    intersection = iw * ih
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


class SimpleFaceTracker:
    """Suivi positionnel minimal, PAR RECOUVREMENT DE BBOX d'une frame à
    l'autre -- volontairement simple, adapté à un usage mono-visage (porte
    d'accès à faible affluence). Pour plusieurs visages simultanés
    fréquents, remplacer par un vrai tracker (centroïdes + association
    hongroise, ou un tracker OpenCV dédié)."""

    def __init__(self, iou_threshold=TRACK_IOU_THRESHOLD, timeout_seconds=TRACK_TIMEOUT_SECONDS):
        self.iou_threshold = iou_threshold
        self.timeout_seconds = timeout_seconds
        self._tracks: dict = {}  # track_id -> {"bbox": ..., "last_seen": ...}
        self._next_id = 0

    def update(self, detections: list) -> list:
        """
        Args:
            detections: liste de dicts (sortie de FaceDetector.detect()).

        Returns:
            liste de (track_id, detection) dans le même ordre que `detections`.
        """
        now = time.time()
        # Purge les suivis trop anciens (visage sorti du cadre).
        stale = [tid for tid, t in self._tracks.items() if now - t["last_seen"] > self.timeout_seconds]
        for tid in stale:
            del self._tracks[tid]

        assigned = []
        for det in detections:
            best_tid, best_iou = None, 0.0
            for tid, t in self._tracks.items():
                iou = _bbox_iou(det["bbox"], t["bbox"])
                if iou > best_iou:
                    best_tid, best_iou = tid, iou

            if best_tid is not None and best_iou >= self.iou_threshold:
                tid = best_tid
            else:
                tid = self._next_id
                self._next_id += 1

            self._tracks[tid] = {"bbox": det["bbox"], "last_seen": now}
            assigned.append((tid, det))

        return assigned

    def active_track_ids(self) -> set:
        return set(self._tracks.keys())


def register_streaming_routes(app, camera, detector, quality_filter, embedder, matcher, enrollment, db_lock):
    """Enregistre les routes de streaming sur l'app FastAPI, en réutilisant
    les instances de service déjà chargées au démarrage (aucun rechargement
    de modèle par requête)."""

    tracker = SimpleFaceTracker()
    consensus = MultiFrameConsensus(frames_required=FRAMES_REQUIRED, frames_window=FRAMES_WINDOW)
    liveness = LivenessChecker()
    _granted_logged: set = set()  # track_id déjà journalisés comme "accès autorisé" pour ce passage

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
            tracked = tracker.update(detections)

            active_ids = tracker.active_track_ids()
            for tid in list(_granted_logged):
                if tid not in active_ids:
                    _granted_logged.discard(tid)
                    consensus.reset(tid)
                    liveness.reset(tid)

            for track_id, face in tracked:
                x, y, w, h = face["bbox"]
                is_valid = quality_filter.is_valid(frame, face)

                if is_valid:
                    embedding = embedder.extract(frame, face)
                    with db_lock:
                        result = matcher.match(embedding)

                    liveness.observe(track_id, frame, face)
                    is_live, live_reason = liveness.is_live(track_id)
                    decision = consensus.observe(track_id, result)

                    # Journalisation "vue" (audit léger, cooldown existant) --
                    # inchangé, indépendant de la décision d'accès.
                    log_key = result["identity_id"] if result["matched"] else "unknown"
                    if _should_log(log_key):
                        with db_lock:
                            enrollment.log_access_attempt(
                                identity_id=result["identity_id"],
                                matched=result["matched"],
                                confidence=result["confidence"],
                            )

                    if decision["granted"] and is_live:
                        color = (0, 255, 0)
                        label = f"Acces autorise : {decision['full_name']} ({decision['confidence']:.2f})"
                        if track_id not in _granted_logged:
                            _granted_logged.add(track_id)
                            # Décision d'accès effective -- événement distinct de la
                            # journalisation "vue" ci-dessus, pour un audit qui
                            # distingue clairement "détecté" de "accès accordé".
                            with db_lock:
                                enrollment.log_access_attempt(
                                    identity_id=decision["identity_id"],
                                    matched=True,
                                    confidence=decision["confidence"],
                                )
                    elif decision["granted"] and not is_live:
                        color = (0, 165, 255)
                        label = f"Vivacite non confirmee ({live_reason})"
                    elif decision["second_factor_required"]:
                        color = (0, 165, 255)
                        label = f"Second facteur requis ({decision['confidence']:.2f})"
                    elif result["matched"]:
                        color = (0, 200, 255)
                        label = f"Analyse en cours ({decision['consensus_count']}/{FRAMES_REQUIRED})"
                    else:
                        color = (0, 0, 255)
                        label = "Inconnu"
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
    