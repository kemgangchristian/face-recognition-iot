"""
Tests de l'aide à la capture d'enrôlement — détecteur et filtre qualité
simulés. Vérifie qu'on refuse tout sauf une capture propre.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

from detection.face_readiness import FaceReadinessAssessor

FRAME = np.zeros((480, 640, 3), np.uint8)


class FakeDetector:
    def __init__(self, detections):
        self.detections = detections

    def detect(self, frame):
        return self.detections


class FakeQuality:
    def __init__(self, valid=True):
        self.valid = valid

    def is_valid(self, frame, detection):
        return self.valid


def face(x, y, w, h):
    return {"bbox": (x, y, w, h), "confidence": 0.9, "landmarks": []}


def assess(detections, valid=True):
    return FaceReadinessAssessor(FakeDetector(detections), FakeQuality(valid), min_width_ratio=0.18).assess(FRAME)


def test_well_placed_face_is_accepted():
    result, reason = assess([face(240, 150, 150, 180)])
    assert result is not None and "prêt" in reason


def test_no_face():
    result, reason = assess([])
    assert result is None and "Aucun visage" in reason


def test_two_faces_are_refused():
    result, reason = assess([face(240, 150, 150, 180), face(10, 10, 100, 100)])
    assert result is None and "Plusieurs visages" in reason


def test_blurry_face_is_refused():
    result, reason = assess([face(240, 150, 150, 180)], valid=False)
    assert result is None and "flou" in reason


def test_face_too_far_is_refused():
    result, reason = assess([face(280, 200, 60, 70)])
    assert result is None and "loin" in reason


def test_face_cut_by_the_edge_is_refused():
    result, reason = assess([face(520, 150, 120, 150)])
    assert result is None and "bord" in reason


def test_off_center_face_is_refused():
    result, reason = assess([face(20, 150, 130, 160)])
    assert result is None and "centre" in reason
    