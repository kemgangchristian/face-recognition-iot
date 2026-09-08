"""
Tests automatisés pour QualityFilter — aucune dépendance matérielle,
exécutable en CI/CD (Jenkins).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
from detection.quality_filter import QualityFilter


def make_fake_frame(size=(480, 640, 3)):
    """Crée une image factice (bruit aléatoire) pour les tests, sans caméra."""
    return np.random.randint(0, 255, size, dtype=np.uint8)


def test_rejects_low_confidence():
    """Une détection avec un score de confiance trop faible doit être rejetée."""
    quality_filter = QualityFilter(min_confidence=0.7)
    frame = make_fake_frame()
    detection = {"bbox": (100, 100, 100, 100), "confidence": 0.5, "landmarks": []}

    assert quality_filter.is_valid(frame, detection) is False


def test_rejects_small_face():
    """Un visage plus petit que min_face_size doit être rejeté."""
    quality_filter = QualityFilter(min_confidence=0.5, min_face_size=50)
    frame = make_fake_frame()
    detection = {"bbox": (100, 100, 20, 20), "confidence": 0.9, "landmarks": []}

    assert quality_filter.is_valid(frame, detection) is False


def test_accepts_valid_detection():
    """Une détection avec bonne confiance, bonne taille, et un crop non vide
    doit passer les critères de base (confiance + taille)."""
    quality_filter = QualityFilter(min_confidence=0.5, min_face_size=50, min_sharpness=0.0)
    frame = make_fake_frame()
    detection = {"bbox": (100, 100, 150, 150), "confidence": 0.9, "landmarks": []}

    assert quality_filter.is_valid(frame, detection) is True


def test_filter_returns_only_valid_detections():
    """filter() doit retourner uniquement le sous-ensemble des détections valides."""
    quality_filter = QualityFilter(min_confidence=0.7, min_face_size=50, min_sharpness=0.0)
    frame = make_fake_frame()

    detections = [
        {"bbox": (100, 100, 150, 150), "confidence": 0.9, "landmarks": []},  # valide
        {"bbox": (100, 100, 10, 10), "confidence": 0.9, "landmarks": []},    # trop petit
        {"bbox": (100, 100, 150, 150), "confidence": 0.3, "landmarks": []},  # confiance faible
    ]

    result = quality_filter.filter(frame, detections)
    assert len(result) == 1
    