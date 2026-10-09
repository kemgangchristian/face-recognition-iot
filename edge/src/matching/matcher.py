"""
Comparaison 1:N d'un embedding capture contre la galerie enrolee.

Regle d'ouverture :
  score du 1er >= seuil
  et (1er - 2e) >= min_margin

Un seul seuil, pas de classificateur de masque. Les valeurs viennent de
storage_data/thresholds.json (calibrate_threshold.py sur la camera du site).
"""

from collections import deque
import numpy as np


class FaceMatcher:
    """Parcourt tous les embeddings enroles (brute-force, volume local)."""

    def __init__(
        self,
        enrollment_service,
        embedder,
        threshold: float = 0.5,
        threshold_low: float = None,
        min_margin: float = 0.0,
    ):
        self.enrollment_service = enrollment_service
        self.embedder = embedder
        # 0.5 n'est qu'un repli si aucune calibration n'a encore ete faite.
        self.threshold = threshold
        self.threshold_low = (
            threshold_low if threshold_low is not None else max(0.0, threshold - 0.15)
        )
        # 0 desactive la marge. Utile des qu'il y a au moins deux identites.
        self.min_margin = min_margin

    def match(self, query_embedding: np.ndarray) -> dict:
        """Retourne la meilleure identite si le score et la marge passent."""
        known_embeddings = self.enrollment_service.get_all_embeddings()

        if not known_embeddings:
            return {
                "matched": False,
                "second_factor_required": False,
                "identity_id": None,
                "full_name": None,
                "confidence": 0.0,
            }

        ranked = []
        for entry in known_embeddings:
            score = self.embedder.compare(query_embedding, entry["vector"])
            ranked.append((score, entry))
        ranked.sort(key=lambda item: item[0], reverse=True)

        best_score, best_entry = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else -1.0
        margin = best_score - second_score

        is_match = best_score >= self.threshold and margin >= self.min_margin
        # Zone grise : assez proche pour un second facteur, pas pour ouvrir.
        needs_second_factor = (not is_match) and best_score >= self.threshold_low

        return {
            "matched": is_match,
            "second_factor_required": needs_second_factor,
            "identity_id": best_entry["identity_id"] if is_match else None,
            "full_name": best_entry["full_name"] if is_match else None,
            "confidence": best_score,
        }


class MultiFrameConsensus:
    """N'ouvre que si la meme identite est reconnue plusieurs fois de suite.

    Evite qu'une frame isolee (flou, angle, imposteur au seuil) declenche
    la gache. track_id doit rester stable pour un meme visage dans le cadre.
    """

    def __init__(self, frames_required: int = 3, frames_window: int = 5):
        if frames_required > frames_window:
            raise ValueError("frames_required ne peut pas depasser frames_window.")
        self.frames_required = frames_required
        self.frames_window = frames_window
        self._history: dict = {}

    def observe(self, track_id, match_result: dict) -> dict:
        """Ajoute la frame courante et decide si l'acces est accorde maintenant."""
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
        """Oublie le suivi quand le visage quitte le cadre."""
        self._history.pop(track_id, None)
