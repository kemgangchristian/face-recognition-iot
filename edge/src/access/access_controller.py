"""
Contrôleur d'accès : boucle de reconnaissance EN ARRIÈRE-PLAN, indépendante
de tout client connecté.

Avant ce module, la décision d'accès n'était calculée que tant qu'un
navigateur avait le flux /stream/detected ouvert. Un contrôleur de porte doit
au contraire fonctionner seul : c'est ce thread qui lit la caméra, détecte,
suit, reconnaît, vérifie la vivacité, ouvre la porte (actionneur) et publie
les événements. Le flux vidéo n'est plus qu'une VUE de ce qu'il produit : N
spectateurs ne multiplient plus les traitements et ne partagent plus d'état
mutable.

Garanties :
  - aucune image n'est jamais enregistrée (les frames ne servent qu'au calcul
    en mémoire et à l'affichage) ;
  - aucun traitement lourd (embedding, comparaison) tant que le visage n'est
    pas bien visible (filtre qualité) ;
  - une fois l'accès accordé, le visage suivi n'est plus retraité à chaque
    frame : une seule re-vérification d'identité toutes les
    `reverify_seconds` ;
  - l'autorisation est RÉVOQUÉE si la personne change, si le visage reste
    illisible trop longtemps, ou si la continuité du suivi est rompue
    (disparition, saut de taille/position : main, photo présentée à la place) ;
  - à vide, la cadence tombe à `idle_fps` (économie CPU/chaleur du Pi) et
    remonte dès qu'un visage apparaît ou qu'un spectateur regarde le flux ;
  - FAIL-CLOSED : toute erreur (caméra, modèle, base) n'ouvre jamais la porte.
"""

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2

from access.face_tracker import FaceTracker
from matching.matcher import MultiFrameConsensus

COLOR_GRANTED = (0, 255, 0)
COLOR_WARNING = (0, 165, 255)
COLOR_PENDING = (0, 200, 255)
COLOR_DENIED = (0, 0, 255)


@dataclass
class AccessConfig:
    frames_required: int = 3
    frames_window: int = 5
    reverify_seconds: float = 3.0
    grant_max_unverified_seconds: Optional[float] = None  # défaut : 3 x reverify_seconds
    active_fps: float = 10.0
    idle_fps: float = 3.0
    idle_after_seconds: float = 5.0
    log_cooldown_seconds: float = 30.0
    spoof_log_after_seconds: float = 3.0   # refus de vivacité persistant avant journalisation
    viewer_timeout_seconds: float = 3.0    # au-delà, plus de spectateur : on n'encode plus de JPEG

    def __post_init__(self):
        if self.grant_max_unverified_seconds is None:
            self.grant_max_unverified_seconds = self.reverify_seconds * 3

    @classmethod
    def from_env(cls, env=None) -> "AccessConfig":
        env = os.environ if env is None else env
        return cls(
            frames_required=int(env.get("ACCESS_FRAMES_REQUIRED", "3")),
            frames_window=int(env.get("ACCESS_FRAMES_WINDOW", "5")),
            reverify_seconds=float(env.get("ACCESS_REVERIFY_SECONDS", "3.0")),
            active_fps=float(env.get("ACCESS_ACTIVE_FPS", "10")),
            idle_fps=float(env.get("ACCESS_IDLE_FPS", "3")),
            idle_after_seconds=float(env.get("ACCESS_IDLE_AFTER_SECONDS", "5")),
            log_cooldown_seconds=float(env.get("ACCESS_LOG_COOLDOWN_SECONDS", "30")),
        )


class AccessController:
    def __init__(
        self,
        camera,
        detector,
        quality_filter,
        embedder,
        matcher,
        enrollment,
        db_lock,
        liveness,
        actuator,
        publisher=None,
        tracker: Optional[FaceTracker] = None,
        config: Optional[AccessConfig] = None,
        clock=time.time,
    ):
        self.camera = camera
        self.detector = detector
        self.quality_filter = quality_filter
        self.embedder = embedder
        self.matcher = matcher
        self.enrollment = enrollment
        self.db_lock = db_lock
        self.liveness = liveness
        self.actuator = actuator
        self.publisher = publisher
        self.config = config or AccessConfig()
        self._clock = clock

        self.tracker = tracker or FaceTracker(clock=clock)
        self.consensus = MultiFrameConsensus(
            frames_required=self.config.frames_required,
            frames_window=self.config.frames_window,
        )

        self._known_tracks: set = set()
        self._granted: dict = {}        # track_id -> {identity_id, full_name, confidence, verified_at}
        self._suspect_since: dict = {}  # track_id -> instant du premier refus de vivacité
        self._last_logged: dict = {}    # clé d'audit -> dernier instant journalisé

        self._last_face_time = 0.0
        self._last_viewer_time = 0.0
        self._last_ok_time = 0.0
        self._last_error_print = 0.0
        self._frames_processed = 0

        self._frame_cond = threading.Condition()
        self._frame_seq = 0
        self._frame_jpeg: Optional[bytes] = None

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="access-controller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        try:
            self.actuator.close()
        except Exception as exc:
            print(f"[accès] erreur à la fermeture de l'actionneur : {exc}")

    def _run(self) -> None:
        while not self._stop.is_set():
            started = self._clock()
            try:
                frame = self.camera.read_frame()
                self.process_frame(frame)
                self._last_ok_time = self._clock()
            except Exception as exc:
                # Fail-closed : une erreur n'ouvre jamais la porte. On limite
                # le bruit dans les logs et on réessaie après une courte pause.
                if started - self._last_error_print > 30:
                    print(f"[accès] erreur dans la boucle de reconnaissance : {exc!r}")
                    self._last_error_print = started
                self._stop.wait(0.5)
                continue

            period = 1.0 / self._current_fps(started)
            self._stop.wait(max(0.0, period - (self._clock() - started)))

    def _current_fps(self, now: float) -> float:
        busy = (
            now - self._last_face_time < self.config.idle_after_seconds
            or now - self._last_viewer_time < self.config.viewer_timeout_seconds
        )
        return self.config.active_fps if busy else self.config.idle_fps

    # ------------------------------------------------------------------
    # Traitement d'une frame
    # ------------------------------------------------------------------

    def process_frame(self, frame) -> list:
        """Traite une frame : détection, suivi, décision, actionneur, vue.

        Returns:
            liste de dicts {track_id, bbox, state, color, label} -- `state`
            vaut "granted", "pending", "unknown", "second_factor",
            "liveness", "quality".
        """
        now = self._clock()
        detections = self.detector.detect(frame)
        if detections:
            self._last_face_time = now
        tracked = self.tracker.update(detections)
        self._release_vanished_tracks()

        results = []
        for track_id, face in tracked:
            self._known_tracks.add(track_id)
            state, color, label = self._evaluate_face(track_id, frame, face, now)
            results.append({
                "track_id": track_id,
                "bbox": face["bbox"],
                "state": state,
                "color": color,
                "label": label,
            })

        self._frames_processed += 1
        self._publish_view(frame, results, now)
        return results

    def _release_vanished_tracks(self) -> None:
        """Libère tout l'état des visages qui ne sont plus suivis : la
        personne est partie, le prochain visage repart d'un cycle complet."""
        active = self.tracker.active_track_ids()
        for tid in list(self._known_tracks):
            if tid not in active:
                self._known_tracks.discard(tid)
                self._granted.pop(tid, None)
                self._suspect_since.pop(tid, None)
                self.consensus.reset(tid)
                self.liveness.reset(tid)

    def _revoke(self, track_id) -> None:
        """Annule l'autorisation d'un visage suivi et repart de zéro pour lui."""
        self._granted.pop(track_id, None)
        self._suspect_since.pop(track_id, None)
        self.consensus.reset(track_id)
        self.liveness.reset(track_id)

    @staticmethod
    def _granted_view(grant: dict) -> tuple:
        return "granted", COLOR_GRANTED, f"Acces autorise : {grant['full_name']} ({grant['confidence']:.2f})"

    def _evaluate_face(self, track_id, frame, face, now: float) -> tuple:
        """Décide de l'état d'un visage suivi pour cette frame.

        Returns:
            (état, couleur BGR, libellé).
        """
        cfg = self.config
        grant = self._granted.get(track_id)

        # Accès déjà accordé et encore frais : aucun retraitement.
        if grant is not None and now - grant["verified_at"] < cfg.reverify_seconds:
            return self._granted_view(grant)

        # Aucun traitement tant que le visage n'est pas bien visible.
        if not self.quality_filter.is_valid(frame, face):
            if grant is not None:
                if now - grant["verified_at"] < cfg.grant_max_unverified_seconds:
                    return self._granted_view(grant)
                self._revoke(track_id)
            return "quality", COLOR_WARNING, "Qualite insuffisante"

        embedding = self.embedder.extract(frame, face)
        with self.db_lock:
            result = self.matcher.match(embedding)

        # Re-vérification d'une autorisation existante : même personne ?
        if grant is not None:
            if result["matched"] and result["identity_id"] == grant["identity_id"]:
                grant["verified_at"] = now
                grant["confidence"] = result["confidence"]
                return self._granted_view(grant)
            # Une autre personne (ou un inconnu) occupe désormais ce suivi.
            self._revoke(track_id)

        self.liveness.observe(track_id, frame, face)
        live = self.liveness.assess(track_id)
        decision = self.consensus.observe(track_id, result)

        if decision["granted"] and live.live:
            return self._grant(track_id, decision, now)

        if decision["granted"]:
            return self._refuse_liveness(track_id, decision, live, now)

        self._suspect_since.pop(track_id, None)

        if decision["second_factor_required"]:
            self._audit_unknown(result, now)
            return "second_factor", COLOR_WARNING, f"Second facteur requis ({decision['confidence']:.2f})"
        if result["matched"]:
            return (
                "pending", COLOR_PENDING,
                f"Analyse en cours ({decision['consensus_count']}/{self.config.frames_required})",
            )

        self._audit_unknown(result, now)
        return "unknown", COLOR_DENIED, "Inconnu"

    # ------------------------------------------------------------------
    # Décisions et effets de bord (journal, porte, MQTT)
    # ------------------------------------------------------------------

    def _grant(self, track_id, decision: dict, now: float) -> tuple:
        grant = {
            "identity_id": decision["identity_id"],
            "full_name": decision["full_name"],
            "confidence": decision["confidence"],
            "verified_at": now,
        }
        self._granted[track_id] = grant
        self._suspect_since.pop(track_id, None)

        # Journal d'audit : UNE ligne « accès accordé » par passage.
        with self.db_lock:
            self.enrollment.log_access_attempt(
                identity_id=grant["identity_id"], matched=True, confidence=grant["confidence"],
            )
        self._notify(True, grant["full_name"], grant["confidence"])

        try:
            self.actuator.unlock(grant["full_name"])
        except Exception as exc:
            # Fail-closed : une panne de l'actionneur ne doit jamais bloquer
            # la boucle ni laisser un état ambigu.
            print(f"[accès] échec de l'actionneur de porte : {exc!r}")

        return self._granted_view(grant)

    def _refuse_liveness(self, track_id, decision: dict, live, now: float) -> tuple:
        """Identité reconnue mais vivacité non établie : pas d'accès.
        Si cela persiste, c'est une tentative suspecte (photo, écran) :
        journalisée comme refus, au nom de la personne usurpée."""
        since = self._suspect_since.setdefault(track_id, now)
        if now - since >= self.config.spoof_log_after_seconds:
            self._audit(
                f"suspect:{decision['identity_id']}", now,
                identity_id=decision["identity_id"], matched=False,
                confidence=decision["confidence"], notify_name=decision["full_name"],
            )

        if live.needs_head_turn:
            label = f"Tournez la tete ({live.parallax:.2f}/{self.liveness.min_parallax:.2f})"
        else:
            label = f"Vivacite non confirmee ({live.reason})"
        return "liveness", COLOR_WARNING, label

    def _audit_unknown(self, result: dict, now: float) -> None:
        self._audit("unknown", now, identity_id=None, matched=False, confidence=result["confidence"])

    def _audit(self, key, now: float, identity_id, matched: bool, confidence: float, notify_name=None) -> None:
        """Journalise avec un délai de réserve par clé, pour ne pas inonder
        la base quand une personne reste devant la caméra."""
        last = self._last_logged.get(key, float("-inf"))
        if now - last < self.config.log_cooldown_seconds:
            return
        self._last_logged[key] = now
        with self.db_lock:
            self.enrollment.log_access_attempt(
                identity_id=identity_id, matched=matched, confidence=confidence,
            )
        self._notify(matched, notify_name, confidence)

    def _notify(self, matched: bool, full_name, confidence: float) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher.publish_verification_event(
                matched=matched, full_name=full_name, confidence=confidence,
            )
        except Exception as exc:
            print(f"[accès] publication MQTT impossible : {exc!r}")

    # ------------------------------------------------------------------
    # Vue vidéo pour le dashboard
    # ------------------------------------------------------------------

    def touch_viewer(self) -> None:
        """Signale qu'un spectateur regarde le flux (active l'encodage JPEG)."""
        self._last_viewer_time = self._clock()

    def _publish_view(self, frame, results: list, now: float) -> None:
        if now - self._last_viewer_time >= self.config.viewer_timeout_seconds:
            return  # personne ne regarde : on n'annote ni n'encode rien

        for item in results:
            x, y, w, h = item["bbox"]
            cv2.rectangle(frame, (x, y), (x + w, y + h), item["color"], 2)
            cv2.putText(frame, item["label"], (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, item["color"], 2)

        ok, jpeg = cv2.imencode(".jpg", frame)
        if not ok:
            return
        with self._frame_cond:
            self._frame_seq += 1
            self._frame_jpeg = jpeg.tobytes()
            self._frame_cond.notify_all()

    def wait_for_frame(self, last_seq: int, timeout: float = 1.0):
        """Attend une frame annotée plus récente que `last_seq`.

        Returns:
            (numéro, octets JPEG), ou None si rien de nouveau avant `timeout`.
        """
        with self._frame_cond:
            if self._frame_seq <= last_seq:
                self._frame_cond.wait(timeout)
            if self._frame_seq <= last_seq or self._frame_jpeg is None:
                return None
            return self._frame_seq, self._frame_jpeg

    # ------------------------------------------------------------------
    # Supervision
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Instantané pour /health : permet de superviser à distance que la
        boucle de contrôle tourne vraiment (et pas seulement l'API)."""
        now = self._clock()
        thread_alive = self._thread is not None and self._thread.is_alive()
        age = None if self._last_ok_time == 0.0 else round(now - self._last_ok_time, 1)
        return {
            "running": thread_alive,
            "healthy": thread_alive and age is not None and age < 5.0,
            "last_frame_age_seconds": age,
            "mode": "active" if self._current_fps(now) == self.config.active_fps else "idle",
            "granted_now": len(self._granted),
            "door_actuator": getattr(self.actuator, "name", "unknown"),
            "liveness_mode": getattr(self.liveness, "mode", "unknown"),
        }
        