"""
Détection de vivacité passive (caméra RGB uniquement) — mitigation
PARTIELLE contre les attaques par présentation (photo imprimée, écran de
téléphone/tablette montrant une personne autorisée).

LIMITE ASSUMÉE : sans caméra infrarouge ou de profondeur, aucune méthode
purement RGB ne peut garantir une protection réelle contre une attaque de
rejeu soignée (vidéo tenue à distance, masque 3D...). Ce module réduit le
risque contre les attaques les plus simples (photo statique immobile, écran
affichant une image fixe) ; il ne remplace PAS un capteur dédié.

Deux signaux faibles, combinés :
1. Mouvement naturel des repères du visage sur quelques secondes (une
   photo imprimée parfaitement immobile ne bouge pas du tout).
2. Score de texture haute fréquence (un écran filmé produit un motif de
   moiré caractéristique, absent d'un vrai visage ou d'une impression papier
   mate).
"""

import time
from collections import deque

import cv2
import numpy as np

class LivenessChecker:
    """Maintient un historique glissant de mesures par visage suivi et
    décide si les signaux collectés sont compatibles avec une présence
    vivante plutôt qu'une photo ou un écran statique."""

    def __init__(
        self,
        window_seconds: float = 3.0,
        min_movement_ratio: float = 0.02,
        max_texture_score: float = 3.0,
        min_samples: int = 3,
    ):
        """
        Args:
            window_seconds: durée de la fenêtre d'observation avant de statuer.
            min_movement_ratio: variation relative minimale de la position des
                repères faciaux sur la fenêtre pour écarter une photo figée.
                À CALIBRER sur le site réel (le bruit de détection lui-même
                crée une variation non nulle).
            max_texture_score: score de moiré/texture maximal toléré avant de
                suspecter un écran. À CALIBRER sur le site réel (dépend de la
                caméra et de l'éclairage).
            min_samples: nombre minimal de mesures avant de pouvoir statuer.
        """
        self.window_seconds = window_seconds
        self.min_movement_ratio = min_movement_ratio
        self.max_texture_score = max_texture_score
        self.min_samples = min_samples
        self._history: dict = {}

    @staticmethod
    def _texture_score(face_crop) -> float:
        """Énergie moyenne du spectre de Fourier du visage recadré — un
        écran filmé produit typiquement des hautes fréquences régulières
        (trame, moiré) qu'un visage réel n'a pas."""
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        spectrum = np.fft.fftshift(np.fft.fft2(gray))
        magnitude = np.log(np.abs(spectrum) + 1.0)
        return float(magnitude.mean())

    def observe(self, track_id, frame, detection: dict) -> None:
        """Enregistre une mesure pour ce visage suivi. À appeler à chaque
        frame où ce visage est détecté, même avant de statuer."""
        x, y, w, h = detection["bbox"]
        y0, y1 = max(y, 0), min(y + h, frame.shape[0])
        x0, x1 = max(x, 0), min(x + w, frame.shape[1])
        face_crop = frame[y0:y1, x0:x1]
        if face_crop.size == 0:
            return

        landmarks = np.array(detection["landmarks"], dtype=np.float32)
        now = time.time()

        hist = self._history.setdefault(track_id, deque())
        hist.append({
            "t": now,
            "landmarks": landmarks,
            "texture": self._texture_score(face_crop),
        })

        cutoff = now - self.window_seconds
        while hist and hist[0]["t"] < cutoff:
            hist.popleft()

    def is_live(self, track_id) -> tuple:
        """
        Returns:
            (bool, str): (vivacité plausible, raison). `False` avec la raison
            "pas assez de mesures" signifie "pas encore de décision" --
            à distinguer d'un vrai refus par l'appelant (ne pas journaliser
            comme une tentative d'intrusion tant que la fenêtre n'est pas pleine).
        """
        hist = self._history.get(track_id)
        if not hist or len(hist) < self.min_samples:
            return False, "pas assez de mesures"

        landmark_series = np.stack([h["landmarks"] for h in hist])  # (n, 5, 2)
        face_width_ref = np.linalg.norm(landmark_series[0, 1] - landmark_series[0, 0]) or 1.0
        displacement = np.linalg.norm(
            landmark_series.max(axis=0) - landmark_series.min(axis=0), axis=1
        ).mean()
        movement_ratio = float(displacement / face_width_ref)

        avg_texture = float(np.mean([h["texture"] for h in hist]))

        if avg_texture > self.max_texture_score:
            return False, "texture suspecte (écran probable)"
        if movement_ratio < self.min_movement_ratio:
            return False, "aucun mouvement détecté (photo figée probable)"
        return True, "ok"

    def reset(self, track_id) -> None:
        self._history.pop(track_id, None)
    