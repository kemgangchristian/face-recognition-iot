"""
Tests du suivi de visages : continuité normale, et ruptures de continuité
(disparition, saut de taille ou de position) qui forcent un nouveau cycle de
reconnaissance + vivacité.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from access.face_tracker import FaceTracker


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def det(x, y, w, h):
    return {"bbox": (x, y, w, h), "confidence": 0.9, "landmarks": []}


def make():
    clock = FakeClock()
    return FaceTracker(clock=clock), clock


def test_same_face_keeps_its_id_while_moving_normally():
    tracker, clock = make()
    first = tracker.update([det(200, 150, 120, 140)])[0][0]
    for step in range(1, 20):
        clock.now += 0.1
        # déplacement de 4 px/frame et agrandissement de 1 %/frame : marche normale
        tid = tracker.update([det(200 + 4 * step, 150, int(120 * 1.01 ** step), int(140 * 1.01 ** step))])[0][0]
        assert tid == first


def test_face_that_disappears_longer_than_the_gap_gets_a_new_id():
    """Photo/main passée devant le visage : la continuité est rompue."""
    tracker, clock = make()
    first = tracker.update([det(200, 150, 120, 140)])[0][0]
    clock.now += 1.0   # > max_gap (0.7 s), < timeout (2 s)
    second = tracker.update([det(200, 150, 120, 140)])[0][0]
    assert second != first


def test_short_detection_flicker_keeps_the_same_id():
    tracker, clock = make()
    first = tracker.update([det(200, 150, 120, 140)])[0][0]
    clock.now += 0.5
    assert tracker.update([det(202, 150, 120, 140)])[0][0] == first


def test_sudden_size_jump_breaks_continuity():
    """Une photo de taille différente qui remplace le visage en place."""
    tracker, clock = make()
    first = tracker.update([det(200, 150, 120, 140)])[0][0]
    clock.now += 0.1
    second = tracker.update([det(190, 140, 200, 230)])[0][0]   # aire x2,7, recouvrement fort
    assert second != first


def test_sudden_position_jump_breaks_continuity():
    tracker, clock = make()
    first = tracker.update([det(100, 150, 120, 140)])[0][0]
    clock.now += 0.1
    second = tracker.update([det(170, 150, 120, 140)])[0][0]   # saut de 70 px > 0,5 x largeur
    assert second != first


def test_two_faces_never_share_one_track():
    tracker, clock = make()
    tracker.update([det(100, 150, 120, 140)])
    clock.now += 0.1
    result = tracker.update([det(102, 150, 120, 140), det(104, 152, 120, 140)])
    assert result[0][0] != result[1][0]


def test_stale_tracks_are_released():
    tracker, clock = make()
    tid = tracker.update([det(200, 150, 120, 140)])[0][0]
    assert tid in tracker.active_track_ids()
    clock.now += 2.5
    tracker.update([])
    assert tid not in tracker.active_track_ids()
    