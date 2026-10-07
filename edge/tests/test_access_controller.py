"""
Tests du contrôleur d'accès (boucle de porte) — caméra, détecteur, embedder,
matcher, base et porte SIMULÉS ; temps simulé (aucune attente réelle). Le
suivi, le consensus multi-frame et la vivacité sont les VRAIS composants.

Couvre : accès accordé et porte ouverte une seule fois, aucun retraitement
d'un visage déjà autorisé, re-vérification d'identité, rejet d'une photo de
la personne autorisée, changement de personne, rupture de continuité,
filtrage qualité, comportement fail-closed, cadence au repos, et vue vidéo
(aucun encodage sans spectateur).
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from access.access_controller import AccessConfig, AccessController
from detection.liveness import LivenessChecker

FRAME = np.zeros((480, 640, 3), np.uint8)
BBOX = (200, 150, 120, 140)

# --- Modèle géométrique 3D (mêmes hypothèses que test_liveness.py) ----------
LIVE_FACE = np.array([[-31.5, 0, 0], [31.5, 0, 0], [0, 38, 25], [-25, 65, 3], [25, 65, 3]], float)
PHOTO_FACE = LIVE_FACE.copy()
PHOTO_FACE[:, 2] = 0.0


def project(points, yaw=0.0, pitch=0.0, shift=(0.0, 0.0)):
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    r = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    pivot = np.array([0.0, 0.0, -90.0])
    moved = (points - pivot) @ r.T + pivot
    z = 500.0 - moved[:, 2]
    return np.column_stack([520 * moved[:, 0] / z, 520 * moved[:, 1] / z]) + [320.0, 240.0] + np.array(shift)


class Scene:
    """Fabrique les repères faciaux vus par le détecteur, frame après frame."""

    def __init__(self, seed=0):
        self.rng = np.random.default_rng(seed)
        self.index = 0
        self.kind = "live"        # "live" (tourne la tête), "still" (immobile), "photo" (agitée)
        self.present = True

    def detections(self):
        if not self.present:
            return []
        self.index += 1
        if self.kind == "live":
            yaw = np.deg2rad(12) * np.sin(2 * np.pi * self.index / 20.0)
            lm = project(LIVE_FACE, yaw=yaw)
        elif self.kind == "still":
            lm = project(LIVE_FACE)
        else:  # photo tenue à la main : inclinée, déplacée, agitée
            yaw, pitch = np.deg2rad(self.rng.uniform(-25, 25, 2))
            lm = project(PHOTO_FACE, yaw=yaw, pitch=pitch, shift=self.rng.normal(0, 3, 2))
        lm = lm + self.rng.normal(0, 0.8, (5, 2))
        return [{"bbox": BBOX, "confidence": 0.95, "landmarks": lm.round().astype(int).tolist()}]


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeCamera:
    def read_frame(self):
        return FRAME.copy()


class FakeDetector:
    def __init__(self, scene):
        self.scene = scene

    def detect(self, frame):
        return self.scene.detections()


class FakeQuality:
    valid = True

    def is_valid(self, frame, detection):
        return self.valid


class FakeEmbedder:
    def __init__(self):
        self.calls = 0

    def extract(self, frame, detection):
        self.calls += 1
        return np.zeros(128, np.float32)


class FakeMatcher:
    def __init__(self):
        self.identity = {"id": 1, "name": "Christian"}   # None = inconnu

    def match(self, embedding):
        if self.identity is None:
            return {"matched": False, "second_factor_required": False, "identity_id": None,
                    "full_name": None, "confidence": 0.2}
        return {"matched": True, "second_factor_required": False, "identity_id": self.identity["id"],
                "full_name": self.identity["name"], "confidence": 0.82}


class FakeEnrollment:
    def __init__(self):
        self.logs = []

    def log_access_attempt(self, identity_id, matched, confidence):
        self.logs.append({"identity_id": identity_id, "matched": matched, "confidence": confidence})


class FakeActuator:
    name = "fake"

    def __init__(self):
        self.unlocks = []
        self.fail = False
        self.closed = False

    def unlock(self, who=None):
        if self.fail:
            raise OSError("relais HS")
        self.unlocks.append(who)

    def lock(self):
        pass

    def close(self):
        self.closed = True


class FakePublisher:
    def __init__(self):
        self.events = []

    def publish_verification_event(self, matched, full_name=None, confidence=0.0):
        self.events.append((matched, full_name))


class Rig:
    """Assemble un contrôleur avec ses doublures et un temps simulé."""

    def __init__(self, config=None, liveness_mode="parallax"):
        self.clock = FakeClock()
        self.scene = Scene()
        self.quality = FakeQuality()
        self.embedder = FakeEmbedder()
        self.matcher = FakeMatcher()
        self.enrollment = FakeEnrollment()
        self.actuator = FakeActuator()
        self.publisher = FakePublisher()
        self.camera = FakeCamera()
        self.controller = AccessController(
            camera=self.camera,
            detector=FakeDetector(self.scene),
            quality_filter=self.quality,
            embedder=self.embedder,
            matcher=self.matcher,
            enrollment=self.enrollment,
            db_lock=threading.Lock(),
            liveness=LivenessChecker(clock=self.clock, mode=liveness_mode),
            actuator=self.actuator,
            publisher=self.publisher,
            config=config or AccessConfig(),
            clock=self.clock,
        )

    def run(self, seconds, fps=10):
        """Fait tourner `seconds` secondes simulées ; retourne la dernière sortie."""
        last = []
        for _ in range(int(seconds * fps)):
            last = self.controller.process_frame(FRAME.copy())
            self.clock.now += 1.0 / fps
        return last

    def run_until_granted(self, max_seconds=10, fps=10):
        """Avance jusqu'à l'instant où l'accès est accordé (phase connue)."""
        for _ in range(int(max_seconds * fps)):
            last = self.controller.process_frame(FRAME.copy())
            self.clock.now += 1.0 / fps
            if last and last[0]["state"] == "granted":
                return
        raise AssertionError("accès jamais accordé")

    def granted_logs(self):
        return [log for log in self.enrollment.logs if log["matched"]]


# --- Accès accordé -----------------------------------------------------------

def test_live_authorized_person_is_granted_and_the_door_opens_once():
    rig = Rig()
    last = rig.run(6)
    assert last[0]["state"] == "granted"
    assert rig.actuator.unlocks == ["Christian"]
    assert len(rig.granted_logs()) == 1
    assert (True, "Christian") in rig.publisher.events


def test_person_standing_there_does_not_reopen_nor_relog_nor_reprocess():
    rig = Rig()
    rig.run_until_granted()
    embeddings_after_grant = rig.embedder.calls

    rig.run(2.8)   # < reverify (3 s) après l'octroi : aucun traitement du tout
    assert rig.embedder.calls == embeddings_after_grant

    rig.run(60)    # présence prolongée : re-vérifications espacées, jamais de nouvelle ouverture
    assert rig.actuator.unlocks == ["Christian"]
    assert len(rig.granted_logs()) == 1
    # ~1 embedding toutes les 3 s au lieu de 10 par seconde
    assert rig.embedder.calls - embeddings_after_grant <= 25


# --- Photo / écran -----------------------------------------------------------

def test_photo_of_the_authorized_person_never_opens_the_door():
    rig = Rig()
    rig.scene.kind = "photo"
    last = rig.run(15)
    assert last[0]["state"] == "liveness"
    assert "Tournez la tete" in last[0]["label"]
    assert rig.actuator.unlocks == []
    assert rig.granted_logs() == []


def test_photo_attempt_is_audited_as_a_refusal_in_the_victims_name():
    rig = Rig()
    rig.scene.kind = "photo"
    rig.run(15)
    suspects = [log for log in rig.enrollment.logs if log["identity_id"] == 1 and not log["matched"]]
    assert len(suspects) == 1                       # une seule ligne grâce au délai de réserve
    assert (False, "Christian") in rig.publisher.events


def test_person_standing_still_is_asked_to_turn_the_head_and_not_logged_as_suspect_early():
    rig = Rig()
    rig.scene.kind = "still"
    last = rig.run(2)
    assert last[0]["state"] == "liveness"
    assert rig.actuator.unlocks == []
    assert rig.enrollment.logs == []                # pas encore suspect : moins de 3 s


def test_person_who_then_turns_the_head_is_granted():
    rig = Rig()
    rig.scene.kind = "still"
    rig.run(2)
    rig.scene.kind = "live"
    rig.run(5)
    assert rig.actuator.unlocks == ["Christian"]


def test_with_liveness_off_a_photo_is_accepted_which_is_why_the_default_is_parallax():
    rig = Rig(liveness_mode="off")
    rig.scene.kind = "photo"
    rig.run(3)
    assert rig.actuator.unlocks == ["Christian"]


# --- Continuité et changement de personne -----------------------------------

def test_another_person_taking_the_place_revokes_the_grant():
    rig = Rig()
    rig.run(6)
    assert rig.actuator.unlocks == ["Christian"]

    rig.matcher.identity = {"id": 2, "name": "Marie"}
    rig.run(6)    # re-vérification : ce n'est plus Christian
    assert rig.actuator.unlocks == ["Christian", "Marie"]     # nouveau cycle complet, nouvelle ouverture


def test_a_photo_replacing_the_authorized_person_is_not_granted():
    rig = Rig()
    rig.run(6)
    assert rig.actuator.unlocks == ["Christian"]

    rig.scene.kind = "photo"
    rig.scene.present = False
    rig.run(1.0)        # la personne disparaît (main, photo qui passe devant) > 0,7 s
    rig.scene.present = True
    rig.run(10)
    assert rig.actuator.unlocks == ["Christian"]              # pas de seconde ouverture
    assert rig.controller.status()["granted_now"] == 0        # l'ancienne autorisation est tombée


def test_a_photo_swapped_in_with_a_size_jump_is_not_granted():
    rig = Rig()
    rig.run(6)

    big = (170, 120, 200, 230)

    class BigPhotoDetector:
        def __init__(self, scene):
            self.scene = scene

        def detect(self, frame):
            return [dict(d, bbox=big) for d in self.scene.detections()]

    rig.scene.kind = "photo"
    rig.controller.detector = BigPhotoDetector(rig.scene)
    rig.run(10)
    assert rig.actuator.unlocks == ["Christian"]


def test_person_leaving_then_returning_gets_a_fresh_cycle_and_a_new_opening():
    rig = Rig()
    rig.run(6)
    rig.scene.present = False
    rig.run(3)                                                 # > timeout du suivi
    assert rig.controller.status()["granted_now"] == 0
    rig.scene.present = True
    rig.run(6)
    assert rig.actuator.unlocks == ["Christian", "Christian"]


def test_face_unreadable_for_too_long_loses_its_grant():
    rig = Rig()
    rig.run(6)
    rig.quality.valid = False
    rig.run(12)       # > 3 x reverify_seconds sans re-vérification possible
    assert rig.controller.status()["granted_now"] == 0


# --- Économie de traitement ---------------------------------------------------

def test_no_embedding_while_the_face_is_not_clearly_visible():
    rig = Rig()
    rig.quality.valid = False
    last = rig.run(5)
    assert rig.embedder.calls == 0
    assert last[0]["state"] == "quality"


def test_unknown_face_is_denied_and_audited_once_per_cooldown():
    rig = Rig()
    rig.matcher.identity = None
    last = rig.run(20)
    assert last[0]["state"] == "unknown"
    assert rig.actuator.unlocks == []
    assert len(rig.enrollment.logs) == 1        # cooldown 30 s
    rig.run(15)
    assert len(rig.enrollment.logs) == 2


def test_idle_rate_drops_when_nobody_is_there_and_rises_when_someone_comes():
    rig = Rig()
    rig.scene.present = False
    rig.run(8)
    assert rig.controller.status()["mode"] == "idle"
    rig.scene.present = True
    rig.run(1)
    assert rig.controller.status()["mode"] == "active"


# --- Robustesse (fail-closed) -------------------------------------------------

def test_actuator_failure_does_not_break_the_loop_or_the_audit_trail():
    rig = Rig()
    rig.actuator.fail = True
    rig.run(6)
    assert len(rig.granted_logs()) == 1
    assert rig.controller.status()["granted_now"] == 1


def test_camera_errors_never_open_the_door_and_the_loop_recovers():
    config = AccessConfig(active_fps=100, idle_fps=100)
    rig = Rig(config=config)
    failures = {"left": 5}

    def flaky_read():
        if failures["left"] > 0:
            failures["left"] -= 1
            raise RuntimeError("caméra débranchée")
        return FRAME.copy()

    rig.camera.read_frame = flaky_read
    rig.scene.present = False
    # Boucle réelle (thread) avec l'horloge réelle.
    rig.controller._clock = time.time
    rig.controller.tracker._clock = time.time
    rig.controller.liveness._clock = time.time
    rig.controller.start()
    try:
        deadline = time.time() + 6
        while time.time() < deadline and not rig.controller.status()["healthy"]:
            time.sleep(0.05)
        assert rig.controller.status()["healthy"] is True
    finally:
        rig.controller.stop()
    assert rig.actuator.unlocks == []
    assert rig.actuator.closed is True            # arrêt : porte verrouillée, relais libéré


def test_status_reports_unhealthy_before_any_frame():
    rig = Rig()
    status = rig.controller.status()
    assert status["healthy"] is False and status["running"] is False
    assert status["door_actuator"] == "fake" and status["liveness_mode"] == "parallax"


# --- Vue vidéo -------------------------------------------------------------------

def test_no_jpeg_is_encoded_while_nobody_watches():
    rig = Rig()
    rig.run(1)
    assert rig.controller.wait_for_frame(0, timeout=0.01) is None


def test_viewer_gets_annotated_frames_and_labels_are_drawn():
    rig = Rig()
    rig.controller.touch_viewer()
    rig.run(0.3)
    seq, jpeg = rig.controller.wait_for_frame(0, timeout=0.01)
    assert seq >= 1 and jpeg[:2] == b"\xff\xd8"          # un vrai JPEG
    import cv2
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert image[BBOX[1] - 1: BBOX[1] + 3, BBOX[0]: BBOX[0] + BBOX[2]].any()   # rectangle dessiné


def test_viewer_timeout_stops_encoding_again():
    rig = Rig()
    rig.controller.touch_viewer()
    rig.run(0.2)
    seq, _ = rig.controller.wait_for_frame(0, timeout=0.01)
    rig.clock.now += 10          # le spectateur est parti
    rig.run(1)
    assert rig.controller.wait_for_frame(seq, timeout=0.01) is None
    