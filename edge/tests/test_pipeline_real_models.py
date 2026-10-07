"""
Test de bout en bout avec les VRAIS modèles (YuNet + SFace) et une VRAIE
photo de visage : le pipeline complet de détection, d'alignement,
d'embedding, de comparaison, de suivi et de vivacité est exercé sans
doublure -- seuls la caméra, la base et la porte sont simulés.

Ignoré automatiquement quand les modèles (edge/models/*.onnx, téléchargés au
build Docker, non versionnés) ou scikit-image (image de test) sont absents :
c'est le cas dans le pipeline CI, pas sur un poste de développement ou sur
le Pi (`pip install scikit-image` pour l'activer en local).

Scénario clé : une PHOTO de la personne autorisée, tenue à la main devant la
caméra (inclinée, agitée, compressée en JPEG), est RECONNUE par SFace mais ne
fait JAMAIS ouvrir la porte. La vivacité est mesurée sur les repères
réellement produits par YuNet, donc avec son vrai bruit de détection.
"""

import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
skimage_data = pytest.importorskip("skimage.data")

MODELS = os.path.join(os.path.dirname(__file__), "..", "models")
for name in ("face_detection_yunet.onnx", "face_recognition_sface.onnx"):
    if not os.path.exists(os.path.join(MODELS, name)):
        pytest.skip(f"modèle {name} absent (voir edge/models/README.md)", allow_module_level=True)

from access.access_controller import AccessController
from detection.face_detector import FaceDetector
from detection.face_readiness import FaceReadinessAssessor
from detection.liveness import LivenessChecker
from detection.quality_filter import QualityFilter
from matching.matcher import FaceMatcher
from recognition.face_embedder import FaceEmbedder

WIDTH, HEIGHT = 640, 480


@pytest.fixture(scope="module")
def photo():
    return cv2.cvtColor(skimage_data.astronaut(), cv2.COLOR_RGB2BGR)


@pytest.fixture(scope="module")
def detector():
    return FaceDetector()


@pytest.fixture(scope="module")
def embedder():
    return FaceEmbedder()


def face_center_in(photo, detector):
    x, y, w, h = detector.detect(photo)[0]["bbox"]
    return x + w / 2, y + h / 2, w


def place(photo, center, face_width, target_width=150, shift=(0, 0)):
    """Photo mise à l'échelle pour que le visage mesure `target_width` px,
    centrée sur le cadre (modifiable par `shift`)."""
    scale = target_width / face_width
    matrix = np.array([[scale, 0, WIDTH / 2 - scale * center[0] + shift[0]],
                       [0, scale, HEIGHT / 2 - scale * center[1] + shift[1]],
                       [0, 0, 1]], dtype=np.float64)
    return matrix


def render(photo, matrix, rng=None, jpeg_quality=85):
    background = np.full((HEIGHT, WIDTH, 3), 118, np.uint8)
    frame = cv2.warpPerspective(photo, matrix, (WIDTH, HEIGHT), dst=background,
                                borderMode=cv2.BORDER_TRANSPARENT)
    if rng is not None:
        frame = np.clip(frame.astype(np.int16) + rng.normal(0, 2.0, frame.shape), 0, 255).astype(np.uint8)
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    return cv2.imdecode(jpeg, cv2.IMREAD_COLOR)


def shaken_photo_matrix(base, rng):
    """Photo tenue à la main : tremblement, rotation, zoom, inclinaison
    (perspective) différents à chaque frame."""
    center = np.array([WIDTH / 2, HEIGHT / 2])
    angle = np.deg2rad(rng.uniform(-8, 8))
    scale = rng.uniform(0.96, 1.04)
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]) * scale
    corners = np.float32([[0, 0], [WIDTH, 0], [WIDTH, HEIGHT], [0, HEIGHT]])
    tilted = (corners - center) @ rotation.T + center + rng.normal(0, 4, (4, 2))
    tilted += rng.uniform(-18, 18, (4, 2))     # inclinaison : chaque coin bouge indépendamment
    perspective = cv2.getPerspectiveTransform(corners, tilted.astype(np.float32))
    return perspective @ base


class FakeClock:
    def __init__(self):
        self.now = 5000.0

    def __call__(self):
        return self.now


class FakeEnrollment:
    def __init__(self, embedding):
        self.embedding = embedding
        self.logs = []

    def get_all_embeddings(self):
        return [{"identity_id": 1, "full_name": "Astronaute", "vector": self.embedding}]

    def log_access_attempt(self, identity_id, matched, confidence):
        self.logs.append({"identity_id": identity_id, "matched": matched, "confidence": confidence})


class RecordingActuator:
    name = "recording"

    def __init__(self):
        self.unlocks = []

    def unlock(self, who=None):
        self.unlocks.append(who)

    def lock(self):
        pass

    def close(self):
        pass


def build_controller(detector, embedder, enrolled_embedding, clock):
    enrollment = FakeEnrollment(enrolled_embedding)
    actuator = RecordingActuator()
    controller = AccessController(
        camera=None,
        detector=detector,
        quality_filter=QualityFilter(),
        embedder=embedder,
        matcher=FaceMatcher(enrollment, embedder, threshold=0.5),
        enrollment=enrollment,
        db_lock=threading.Lock(),
        liveness=LivenessChecker(clock=clock),
        actuator=actuator,
        clock=clock,
    )
    controller.tracker._clock = clock
    return controller, enrollment, actuator


# --- Détecteur : plusieurs tailles d'image, sans le bug du moteur DNN -------

def test_detector_handles_alternating_image_sizes(photo, detector):
    """Cas de /enroll (image uploadée) pendant que le flux caméra tourne à
    une autre résolution : jamais d'erreur, visage retrouvé à chaque taille."""
    sizes = [(640, 480), (800, 600), (640, 480), (320, 240), (800, 600), (640, 480)]
    center = face_center_in(photo, detector)
    for width, height in sizes * 3:
        matrix = place(photo, center[:2], center[2], target_width=width * 0.25)
        scaled = np.diag([width / WIDTH, height / HEIGHT, 1.0]) @ matrix
        frame = cv2.warpPerspective(photo, scaled, (width, height))
        assert len(detector.detect(frame)) == 1, f"visage perdu en {width}x{height}"


def test_readiness_accepts_a_centered_face_and_refuses_one_on_the_edge(photo, detector):
    center = face_center_in(photo, detector)
    assessor = FaceReadinessAssessor(detector, QualityFilter())
    good = render(photo, place(photo, center[:2], center[2], target_width=160))
    assert assessor.assess(good)[0] is not None

    edge = render(photo, place(photo, center[:2], center[2], target_width=160, shift=(250, 0)))
    face, reason = assessor.assess(edge)
    assert face is None


# --- Le scénario clé : la photo de la personne autorisée ---------------------

def test_hand_held_photo_of_an_enrolled_person_is_recognized_but_never_opens_the_door(photo, detector, embedder):
    center = face_center_in(photo, detector)
    base = place(photo, center[:2], center[2], target_width=150)

    # Enrôlement propre (comme /enroll) : l'identité est connue du système.
    enrolled = embedder.extract(render(photo, base), detector.detect(render(photo, base))[0])

    clock = FakeClock()
    controller, enrollment, actuator = build_controller(detector, embedder, enrolled, clock)
    rng = np.random.default_rng(42)

    states, parallaxes = [], []
    for _ in range(80):       # 8 s de photo agitée devant la caméra
        frame = render(photo, shaken_photo_matrix(base, rng), rng)
        results = controller.process_frame(frame)
        clock.now += 0.1
        if results:
            states.append(results[0]["state"])
        parallaxes.append(controller.liveness.parallax(0))

    measured = [p for p in parallaxes if p is not None]
    assert actuator.unlocks == [], f"PORTE OUVERTE par une photo ! états={set(states)}"
    assert "granted" not in states
    assert "liveness" in states, "la photo n'a même pas été reconnue : test sans valeur"
    assert max(measured) < controller.liveness.min_parallax, (
        f"parallaxe max {max(measured):.3f} >= seuil {controller.liveness.min_parallax}"
    )
    # À titre indicatif : avec une agitation volontairement brutale (coins de la
    # photo déplacés de +-18 px à chaque frame), le vrai YuNet donne ~0.07-0.09
    # contre un seuil de 0.12 -- marge réelle mais pas énorme, à vérifier
    # sur la caméra du site (voir l'étiquette « Tournez la tete (x/y) »).
    print(f"\n[photo agitée] parallaxe mesurée avec le vrai YuNet : max={max(measured):.3f} "
          f"(seuil {controller.liveness.min_parallax})")


def test_same_photo_pipeline_does_grant_when_the_face_is_genuinely_3d(photo, detector, embedder):
    """Contre-épreuve : même pipeline, mais les repères reflètent un vrai
    visage qui tourne la tête (modèle 3D) -> accès accordé. Prouve que le
    rejet de la photo vient bien de la vivacité, pas d'un défaut ailleurs."""
    center = face_center_in(photo, detector)
    base = place(photo, center[:2], center[2], target_width=150)
    frame = render(photo, base)
    detection = detector.detect(frame)[0]
    enrolled = embedder.extract(frame, detection)

    clock = FakeClock()
    controller, enrollment, actuator = build_controller(detector, embedder, enrolled, clock)

    live_face = np.array([[-31.5, 0, 0], [31.5, 0, 0], [0, 38, 25], [-25, 65, 3], [25, 65, 3]], float)

    def project(yaw):
        c, s = np.cos(yaw), np.sin(yaw)
        pivot = np.array([0.0, 0.0, -90.0])
        moved = (live_face - pivot) @ np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]).T + pivot
        z = 500.0 - moved[:, 2]
        return np.column_stack([520 * moved[:, 0] / z, 520 * moved[:, 1] / z])

    # Le détecteur « voit » ces repères 3D ; l'image (donc l'embedding) reste celle de la personne.
    real_detect = detector.detect

    class TurningHeadDetector:
        index = 0

        def detect(self, f):
            TurningHeadDetector.index += 1
            yaw = np.deg2rad(12) * np.sin(2 * np.pi * TurningHeadDetector.index / 20.0)
            found = real_detect(f)
            relative = project(yaw) - project(0)
            for det in found:
                det["landmarks"] = (np.array(detection["landmarks"]) + relative).round().astype(int).tolist()
            return found

    controller.detector = TurningHeadDetector()
    for _ in range(60):
        controller.process_frame(render(photo, base, np.random.default_rng(1)))
        clock.now += 0.1
    assert actuator.unlocks == ["Astronaute"]
    