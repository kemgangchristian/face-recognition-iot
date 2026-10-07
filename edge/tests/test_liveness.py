"""
Tests de la vivacité par parallaxe — AUCUN modèle ni caméra nécessaires.

Les mesures sont issues d'un modèle géométrique 3D de visage (bout du nez
~25 mm en avant du plan des yeux) projeté en perspective : un visage RÉEL qui
tourne la tête change la position du nez par rapport aux yeux et à la bouche,
une PHOTO (mêmes points mais coplanaires), même agitée, non. Le bruit de
détection des repères est simulé de 0,5 à 2 px.

Ces tests valident la LOGIQUE et la marge de sécurité du seuil sur ce modèle ;
ils ne remplacent pas un essai sur la caméra réelle (voir l'étiquette
« Tournez la tete (x/y) » qui affiche la valeur mesurée en direct).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import pytest

from detection.liveness import LivenessChecker, shape_coords

# Ordre YuNet : œil droit, œil gauche, nez, coin droit bouche, coin gauche (mm).
LIVE_FACE = np.array([[-31.5, 0, 0], [31.5, 0, 0], [0, 38, 25], [-25, 65, 3], [25, 65, 3]], float)
PHOTO_FACE = LIVE_FACE.copy()
PHOTO_FACE[:, 2] = 0.0  # mêmes points, mais sur un seul plan


def project(points, yaw=0.0, pitch=0.0, pivot_z=-90.0, distance=500.0, focal=520.0, shift=(0.0, 0.0)):
    """Projette en perspective un visage tourné de (yaw, pitch) radians autour
    d'un pivot situé derrière les yeux (le cou)."""
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    r_yaw = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    r_pitch = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    pivot = np.array([0.0, 0.0, pivot_z])
    moved = (points - pivot) @ (r_pitch @ r_yaw).T + pivot
    z = distance - moved[:, 2]
    pixels = np.column_stack([focal * moved[:, 0] / z, focal * moved[:, 1] / z])
    return pixels + np.array([320.0, 240.0]) + np.array(shift)


def detection_from(landmarks):
    pts = np.asarray(landmarks)
    return {"bbox": (200, 150, 120, 140), "confidence": 0.95, "landmarks": pts.tolist()}


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def run_sequence(checker, clock, landmark_frames, fps=10.0, track_id=1):
    frame = np.zeros((480, 640, 3), np.uint8)
    for landmarks in landmark_frames:
        checker.observe(track_id, frame, detection_from(landmarks))
        clock.advance(1.0 / fps)
    return checker.assess(track_id)


def live_frames(amplitude_deg, sigma, rng, n=30):
    yaws = np.deg2rad(amplitude_deg) * np.sin(np.linspace(0, 2 * np.pi, n))
    return [project(LIVE_FACE, yaw=y) + rng.normal(0, sigma, (5, 2)) for y in yaws]


def photo_frames(rng, sigma, n=30, tilt_deg=25, shake_px=6):
    """Photo tenue à la main : inclinée dans tous les sens, déplacée, agitée."""
    frames = []
    for _ in range(n):
        yaw, pitch = np.deg2rad(rng.uniform(-tilt_deg, tilt_deg, 2))
        shift = rng.normal(0, shake_px, 2)
        frames.append(project(PHOTO_FACE, yaw=yaw, pitch=pitch, shift=shift) + rng.normal(0, sigma, (5, 2)))
    return frames


# --- shape_coords : l'invariant mathématique sur lequel tout repose --------

def test_shape_coords_invariant_under_any_affine_transform():
    rng = np.random.default_rng(1)
    base = project(PHOTO_FACE)
    reference = shape_coords(base)
    for _ in range(50):
        matrix = rng.normal(0, 0.5, (2, 2)) + np.eye(2) * 1.5
        moved = base @ matrix.T + rng.normal(0, 40, 2)
        a, b = shape_coords(moved)
        assert abs(a - reference[0]) < 1e-6 and abs(b - reference[1]) < 1e-6


def test_shape_coords_changes_when_a_real_face_turns():
    straight = shape_coords(project(LIVE_FACE))
    turned = shape_coords(project(LIVE_FACE, yaw=np.deg2rad(15)))
    # Modèle : ~0.13 pour une rotation de 15° (contre ~0 pour une photo, cf. test précédent).
    assert np.hypot(turned[0] - straight[0], turned[1] - straight[1]) > 0.10


def test_shape_coords_degenerate_landmarks_return_none():
    same_point = np.tile([100.0, 100.0], (5, 1))
    assert shape_coords(same_point) is None


# --- Décision de vivacité ---------------------------------------------------

@pytest.mark.parametrize("sigma", [0.5, 1.0, 1.5, 2.0])
def test_moving_photo_is_never_live_whatever_the_detector_noise(sigma):
    """Une photo agitée/inclinée à la main reste sous le seuil, même avec
    un détecteur bruité à 2 px."""
    for seed in range(30):
        rng = np.random.default_rng(seed)
        clock = FakeClock()
        checker = LivenessChecker(clock=clock)
        result = run_sequence(checker, clock, photo_frames(rng, sigma))
        assert result.live is False, f"photo acceptée (seed={seed}, sigma={sigma}, parallaxe={result.parallax})"
        assert result.parallax < checker.min_parallax * 0.8, "marge de sécurité insuffisante"


@pytest.mark.parametrize("sigma", [0.5, 1.0, 1.5, 2.0])
def test_real_face_turning_ten_degrees_is_live(sigma):
    for seed in range(30):
        rng = np.random.default_rng(seed)
        clock = FakeClock()
        checker = LivenessChecker(clock=clock)
        result = run_sequence(checker, clock, live_frames(10, sigma, rng))
        assert result.live is True, f"visage réel refusé (seed={seed}, sigma={sigma}, parallaxe={result.parallax})"


def test_real_face_staying_still_is_asked_to_turn_the_head():
    rng = np.random.default_rng(0)
    clock = FakeClock()
    checker = LivenessChecker(clock=clock)
    result = run_sequence(checker, clock, live_frames(0, 1.0, rng))
    assert result.live is False
    assert result.needs_head_turn is True
    assert "tournez la tete" in result.reason


def test_not_enough_samples_is_undecided_not_a_refusal():
    rng = np.random.default_rng(0)
    clock = FakeClock()
    checker = LivenessChecker(clock=clock)
    result = run_sequence(checker, clock, live_frames(15, 0.5, rng, n=3))
    assert result.live is False
    assert result.needs_head_turn is False
    assert result.reason == "pas assez de mesures"
    assert result.parallax is None


def test_old_measurements_leave_the_window():
    """Un mouvement de tête ancien (hors fenêtre) ne vaut plus : une photo
    présentée ensuite ne profite pas du mouvement de la personne réelle."""
    rng = np.random.default_rng(3)
    clock = FakeClock()
    checker = LivenessChecker(clock=clock, window_seconds=3.0)
    assert run_sequence(checker, clock, live_frames(15, 0.5, rng)).live is True
    clock.advance(10.0)
    result = run_sequence(checker, clock, photo_frames(rng, 1.0, n=30))
    assert result.live is False


def test_reset_forgets_a_track():
    rng = np.random.default_rng(0)
    clock = FakeClock()
    checker = LivenessChecker(clock=clock)
    run_sequence(checker, clock, live_frames(15, 0.5, rng))
    checker.reset(1)
    assert checker.assess(1).reason == "pas assez de mesures"


# --- Modes -------------------------------------------------------------------

def test_off_mode_accepts_everything_and_records_nothing():
    clock = FakeClock()
    checker = LivenessChecker(mode="off", clock=clock)
    rng = np.random.default_rng(0)
    assert run_sequence(checker, clock, photo_frames(rng, 1.0)).live is True


def test_movement_mode_is_defeated_by_a_shaken_photo():
    """Documente POURQUOI l'ancien test de mouvement ne suffit pas : une
    photo agitée à la main le franchit. Le mode par défaut (parallaxe) non."""
    rng = np.random.default_rng(0)
    clock = FakeClock()
    weak = LivenessChecker(mode="movement", clock=clock)
    assert run_sequence(weak, clock, photo_frames(rng, 1.0)).live is True

    rng = np.random.default_rng(0)
    clock2 = FakeClock()
    strong = LivenessChecker(mode="parallax", clock=clock2)
    assert run_sequence(strong, clock2, photo_frames(rng, 1.0)).live is False


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        LivenessChecker(mode="magic")


# --- Détection spectrale optionnelle (désactivée par défaut) ---------------

def test_spectral_peak_flags_a_periodic_pattern_but_not_smooth_texture():
    rng = np.random.default_rng(0)
    smooth = np.clip(rng.normal(128, 12, (120, 110)), 0, 255)
    xs = np.arange(110)
    grating = np.clip(smooth + 40 * np.sin(2 * np.pi * xs / 4.0)[None, :], 0, 255)
    to_bgr = lambda g: np.repeat(g.astype(np.uint8)[:, :, None], 3, axis=2)

    assert LivenessChecker._spectral_peak_ratio(to_bgr(grating)) > 3 * LivenessChecker._spectral_peak_ratio(to_bgr(smooth))


def test_spectral_check_is_off_by_default():
    assert LivenessChecker().max_spectral_peak is None
    