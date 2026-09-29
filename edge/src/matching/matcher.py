"""
Matching d'un visage capturé contre la base d'identités enrôlées.
Story 4.1 — Epic 4.
"""

from collections import deque
import numpy as np


class FaceMatcher:
    """Compare un embedding capturé à tous les embeddings enrôlés (brute-force),
    et retourne la meilleure correspondance si elle dépasse le seuil de confiance."""

    def __init__(self, enrollment_service, embedder, threshold: float = 0.5, threshold_low: float = None):
        """
        Args:
            enrollment_service: instance EnrollmentService (accès à get_all_embeddings()).
            embedder: instance FaceEmbedder (utilisé pour compare()).
            threshold: score cosinus minimum pour une autorisation automatique.
                    Valeur par défaut basée sur nos tests empiriques Story 2.3
                    (même personne ~0.8-1.0, personnes différentes ~0.2-0.4) ;
                    à recalibrer rigoureusement avec un vrai jeu de test réel.
            threshold_low: score minimum pour proposer un second facteur plutôt
                        qu'un refus direct. Par défaut, threshold - 0.15
                        (marge arbitraire tant qu'aucune calibration réelle
                        n'a été faite).
        """
        self.enrollment_service = enrollment_service
        self.embedder = embedder
        self.threshold = threshold
        self.threshold_low = threshold_low if threshold_low is not None else max(0.0, threshold - 0.15)

    def match(self, query_embedding: np.ndarray) -> dict:
        """
        Cherche la meilleure correspondance pour un embedding donné.

        Args:
            query_embedding: vecteur (128-d) issu de FaceEmbedder.extract().

        Returns:
            dict: {
                "matched": bool (score >= threshold : autorisation),
                "second_factor_required": bool (threshold_low <= score < threshold),
                "identity_id": int ou None,
                "full_name": str ou None,
                "confidence": float (meilleur score trouvé, même si sous le seuil)
            }
        """
        known_embeddings = self.enrollment_service.get_all_embeddings()

        if not known_embeddings:
            return {
                "matched": False,
                "second_factor_required": False,
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
        needs_second_factor = (not is_match) and best_score >= self.threshold_low

        return {
            "matched": is_match,
            "second_factor_required": needs_second_factor,
            "identity_id": best_entry["identity_id"] if is_match else None,
            "full_name": best_entry["full_name"] if is_match else None,
            "confidence": best_score,
        }


class MultiFrameConsensus:
    """Exige plusieurs détections concordantes sur une fenêtre glissante avant
    de considérer qu'un accès peut être accordé sur le flux caméra continu.

    Réduit le risque qu'une seule image bruitée (angle, éclairage, ou même
    une tentative furtive) déclenche une ouverture : il faut `frames_required`
    détections de LA MÊME identité parmi les `frames_window` dernières
    observations de ce visage suivi.

    NB : nécessite un identifiant de suivi (`track_id`) stable d'une frame à
    l'autre pour un même visage physique -- voir `streaming.py` (étape 3)
    pour un suivi positionnel simple, suffisant pour une porte mono-visage.
    """

    def __init__(self, frames_required: int = 3, frames_window: int = 5):
        if frames_required > frames_window:
            raise ValueError("frames_required ne peut pas dépasser frames_window.")
        self.frames_required = frames_required
        self.frames_window = frames_window
        self._history: dict = {}

    def observe(self, track_id, match_result: dict) -> dict:
        """
        Enregistre le résultat de matching de cette frame pour ce visage
        suivi, et retourne la décision consolidée sur la fenêtre.

        Args:
            track_id: identifiant du visage suivi.
            match_result: résultat de FaceMatcher.match() pour cette frame.

        Returns:
            dict: {
                "granted": bool,             # accès à accorder MAINTENANT
                "identity_id", "full_name", "confidence": du dernier résultat,
                "second_factor_required": bool (repris du dernier résultat),
                "consensus_count": nombre d'accords sur la fenêtre actuelle,
            }
        """
        hist = self._history.setdefault(track_id, deque(maxlen=self.frames_window))
        hist.append(match_result["identity_id"] if match_result["matched"] else None)

        consensus_count = 0
        if match_result["matched"]:
            consensus_count = sum(1 for h in hist if h == match_result["identity_id"])

        granted = match_result["matched"] and consensus_count >= self.frames_required

        return {
            "granted": granted,
            "identity_id": match_result["identity_id"],
            "full_name": match_result["full_name"],
            "confidence": match_result["confidence"],
            "second_factor_required": match_result["second_factor_required"],
            "consensus_count": consensus_count,
        }

    def reset(self, track_id) -> None:
        """Oublie l'historique d'un visage suivi (ex. quand il quitte le cadre)."""
        self._history.pop(track_id, None)
        