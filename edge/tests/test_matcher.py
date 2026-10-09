"""
Tests automatisés pour FaceMatcher — dépendances simulées (mocks),
aucune vraie base de données ni caméra nécessaire.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
from matching.matcher import FaceMatcher


class FakeEnrollmentService:
    """Doublure de test simulant EnrollmentService, sans vraie base SQLite."""

    def __init__(self, embeddings_data):
        self._embeddings_data = embeddings_data

    def get_all_embeddings(self):
        return self._embeddings_data


class FakeEmbedder:
    """Doublure de test simulant FaceEmbedder. Le score de similarité est
    calculé de façon simple et prévisible : identique = 1.0, sinon 0.0 —
    suffisant pour tester la LOGIQUE de FaceMatcher, pas la qualité réelle
    du modele SFace."""

    def compare(self, embedding_a, embedding_b):
        return 1.0 if np.array_equal(embedding_a, embedding_b) else 0.0


def test_no_match_when_database_empty():
    """Sans aucune identité enrôlée, le matching doit retourner matched=False."""
    fake_service = FakeEnrollmentService(embeddings_data=[])
    matcher = FaceMatcher(fake_service, FakeEmbedder(), threshold=0.5)

    query = np.array([1.0, 2.0, 3.0])
    result = matcher.match(query)

    assert result["matched"] is False
    assert result["identity_id"] is None


def test_match_found_above_threshold():
    """Un embedding identique à une entrée connue doit être reconnu."""
    known_vector = np.array([1.0, 2.0, 3.0])
    fake_service = FakeEnrollmentService(embeddings_data=[
        {"identity_id": 1, "full_name": "Alice", "vector": known_vector}
    ])
    matcher = FaceMatcher(fake_service, FakeEmbedder(), threshold=0.5)

    result = matcher.match(known_vector)

    assert result["matched"] is True
    assert result["full_name"] == "Alice"
    assert result["confidence"] == 1.0


def test_no_match_below_threshold():
    """Un embedding différent de toutes les entrées connues ne doit pas
    être reconnu, même s'il existe des identités en base."""
    known_vector = np.array([1.0, 2.0, 3.0])
    different_vector = np.array([9.0, 9.0, 9.0])

    fake_service = FakeEnrollmentService(embeddings_data=[
        {"identity_id": 1, "full_name": "Alice", "vector": known_vector}
    ])
    matcher = FaceMatcher(fake_service, FakeEmbedder(), threshold=0.5)

    result = matcher.match(different_vector)

    assert result["matched"] is False
    assert result["identity_id"] is None


def test_returns_best_match_among_multiple():
    """Avec plusieurs identités connues, le matching doit retourner celle
    qui correspond exactement, pas une autre."""
    vector_alice = np.array([1.0, 2.0, 3.0])
    vector_bob = np.array([4.0, 5.0, 6.0])

    fake_service = FakeEnrollmentService(embeddings_data=[
        {"identity_id": 1, "full_name": "Alice", "vector": vector_alice},
        {"identity_id": 2, "full_name": "Bob", "vector": vector_bob},
    ])
    matcher = FaceMatcher(fake_service, FakeEmbedder(), threshold=0.5)

    result = matcher.match(vector_bob)

    assert result["matched"] is True
    assert result["full_name"] == "Bob"


class RankEmbedder:
    """Scores fixes par identité, pour tester la marge 1er/2e."""

    def __init__(self, scores_by_id: dict):
        self.scores_by_id = scores_by_id

    def compare(self, query_embedding, gallery_embedding):
        key = tuple(gallery_embedding.tolist())
        return self.scores_by_id[key]


def test_min_margin_rejects_when_top_two_are_too_close():
    alice = np.array([1.0, 0.0], dtype=np.float32)
    bob = np.array([0.0, 1.0], dtype=np.float32)
    fake_service = FakeEnrollmentService(embeddings_data=[
        {"identity_id": 1, "full_name": "Alice", "vector": alice},
        {"identity_id": 2, "full_name": "Bob", "vector": bob},
    ])
    embedder = RankEmbedder({tuple(alice.tolist()): 0.91, tuple(bob.tolist()): 0.89})
    matcher = FaceMatcher(fake_service, embedder, threshold=0.5, min_margin=0.05)

    result = matcher.match(np.array([1.0, 1.0], dtype=np.float32))

    assert result["matched"] is False
    assert result["confidence"] == 0.91


def test_min_margin_allows_clear_winner():
    alice = np.array([1.0, 0.0], dtype=np.float32)
    bob = np.array([0.0, 1.0], dtype=np.float32)
    fake_service = FakeEnrollmentService(embeddings_data=[
        {"identity_id": 1, "full_name": "Alice", "vector": alice},
        {"identity_id": 2, "full_name": "Bob", "vector": bob},
    ])
    embedder = RankEmbedder({tuple(alice.tolist()): 0.91, tuple(bob.tolist()): 0.70})
    matcher = FaceMatcher(fake_service, embedder, threshold=0.5, min_margin=0.05)

    result = matcher.match(np.array([1.0, 1.0], dtype=np.float32))

    assert result["matched"] is True
    assert result["full_name"] == "Alice"
    