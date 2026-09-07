"""
Matching d'un visage capturé contre la base d'identités enrôlées.
Story 4.1 — Epic 4.
"""

import numpy as np


class FaceMatcher:
    """Compare un embedding capturé à tous les embeddings enrôlés (brute-force),
    et retourne la meilleure correspondance si elle dépasse le seuil de confiance."""

    def __init__(self, enrollment_service, embedder, threshold: float = 0.5):
        """
        Args:
            enrollment_service: instance EnrollmentService (accès à get_all_embeddings()).
            embedder: instance FaceEmbedder (utilisé pour compare()).
            threshold: score cosinus minimum pour valider une identification.
                       Valeur par défaut basée sur nos tests empiriques Story 2.3
                       (même personne ~0.8-1.0, personnes différentes ~0.2-0.4) ;
                       à recalibrer rigoureusement en Story 4.3 avec un vrai jeu de test.
        """
        self.enrollment_service = enrollment_service
        self.embedder = embedder
        self.threshold = threshold

    def match(self, query_embedding: np.ndarray) -> dict:
        """
        Cherche la meilleure correspondance pour un embedding donné.

        Args:
            query_embedding: vecteur (128-d) issu de FaceEmbedder.extract().

        Returns:
            dict: {
                "matched": bool,
                "identity_id": int ou None,
                "full_name": str ou None,
                "confidence": float (meilleur score trouvé, même si sous le seuil)
            }
        """
        known_embeddings = self.enrollment_service.get_all_embeddings()

        if not known_embeddings:
            return {
                "matched": False,
                "identity_id": None,
                "full_name": None,
                "confidence": 0.0,
            }

        best_score = -1.0
        best_entry = None

        for entry in known_embeddings:
            score = self.embedder.compare(query_embedding, entry["vector"])
            if score > best_score:
                best_score = score
                best_entry = entry

        is_match = best_score >= self.threshold

        return {
            "matched": is_match,
            "identity_id": best_entry["identity_id"] if is_match else None,
            "full_name": best_entry["full_name"] if is_match else None,
            "confidence": best_score,
        }
    