"""
Détection de vivacité par PARALLAXE 3D, caméra RGB uniquement — rejette les
attaques par présentation PLANES : photo imprimée, photo affichée sur un
téléphone/tablette, écran montrant une image fixe.

Principe (voir `shape_coords`) : un visage réel est en relief (le bout du nez
est ~25 mm en avant du plan des yeux), une photo est plate. Exprimons la
position du nez dans le repère formé par l'axe des yeux et l'axe
yeux→bouche : pour un objet PLAN, ces deux coordonnées (a, b) sont
INVARIANTES par toute transformation affine (translation, rotation,
agrandissement, inclinaison, tremblement de la main qui tient la photo) ;
pour un visage en 3D, elles changent dès que la tête tourne (le nez se
déplace par rapport aux yeux et à la bouche). On exige donc que (a, b)
varie d'au moins `min_parallax` sur la fenêtre d'observation : la personne
doit tourner légèrement la tête (~8-10°). Une photo, même agitée, reste
sous le plancher de bruit du détecteur.

Mesures de référence (modèle géométrique 3D, voir tests/test_liveness.py) :
  - photo, quel que soit le mouvement : parallaxe 0.02-0.08 selon le bruit
    de détection des repères (0.5 à 2 px) ;
  - visage réel tournant de ±10° : ~0.16 ; de ±5° : ~0.08-0.10.
Seuil par défaut 0.12. À RECALIBRER sur la caméra réelle : l'étiquette
affichée dans le flux montre la valeur mesurée (« Tournez la tete (0.05/0.12) »).

⚠️ LIMITES ASSUMÉES -- à ne pas perdre de vue :
  - Ce module protège contre les supports PLANS. Un REJEU VIDÉO (vidéo d'une
    personne qui tourne la tête, affichée sur un écran) montre un vrai
    mouvement 3D filmé : il passerait la parallaxe. Aucune méthode RGB seule
    ne le détecte de façon fiable. Pour une porte à enjeu réel, ajouter une
    caméra infrarouge ou de profondeur.
  - Un masque 3D ou un visage moulé n'est pas détecté non plus.
  - Une détection spectrale de moiré est disponible mais DÉSACTIVÉE par
    défaut (`max_spectral_peak=None`) : elle doit être calibrée sur la
    caméra réelle, la compression JPEG de la caméra produisant elle-même des
    pics périodiques.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class LivenessResult:
    """Résultat d'une évaluation de vivacité pour un visage suivi."""
    live: bool
    reason: str
    parallax: Optional[float] = None   # None tant que les mesures sont insuffisantes
    needs_head_turn: bool = False      # True : seul le mouvement de tête manque


def shape_coords(landmarks) -> Optional[tuple]:
    """Coordonnées (a, b) du nez dans le repère (axe des yeux, axe
    yeux→bouche), invariantes par transformation affine d'un objet plan.

    Args:
        landmarks: 5 points (x, y) dans l'ordre YuNet : œil droit, œil
            gauche, bout du nez, coin droit de la bouche, coin gauche.

    Returns:
        (a, b), ou None si le repère est dégénéré (visage de profil, points
        confondus).
    """
    pts = np.asarray(landmarks, dtype=np.float64).reshape(5, 2)
    right_eye, left_eye, nose, right_mouth, left_mouth = pts
    eye_mid = (right_eye + left_eye) / 2.0
    mouth_mid = (right_mouth + left_mouth) / 2.0
    basis = np.column_stack([left_eye - right_eye, mouth_mid - eye_mid])
    if abs(np.linalg.det(basis)) < 1e-6:
        return None
    a, b = np.linalg.solve(basis, nose - eye_mid)
    return float(a), float(b)


class LivenessChecker:
    """Maintient un historique glissant par visage suivi et décide si les
    mesures sont compatibles avec un visage en relief plutôt qu'un support
    plat."""

    MODES = ("parallax", "movement", "off")

    def __init__(
        self,
        window_seconds: float = 3.0,
        min_parallax: float = 0.12,
        min_samples: int = 5,
        mode: str = "parallax",
        min_movement_ratio: float = 0.02,
        max_spectral_peak: Optional[float] = None,
        clock=time.time,
    ):
        """
        Args:
            window_seconds: durée de la fenêtre d'observation.
            min_parallax: variation minimale de (a, b) sur la fenêtre pour
                conclure à un visage en relief (voir l'en-tête du module).
            min_samples: nombre minimal de mesures avant de statuer.
            mode: "parallax" (défaut, recommandé) ; "movement" (ANCIEN test
                de simple mouvement des repères, FAIBLE : une photo agitée à
                la main le franchit) ; "off" (vivacité désactivée, démo
                uniquement -- ne jamais utiliser sur une porte réelle).
            min_movement_ratio: seuil du mode "movement".
            max_spectral_peak: si défini, rejette les visages dont le
                spectre présente un pic périodique supérieur (moiré
                d'écran). None = désactivé (non calibré).
            clock: source de temps injectable (tests).
        """
        if mode not in self.MODES:
            raise ValueError(f"mode doit être l'un de {self.MODES}")
        self.window_seconds = window_seconds
        self.min_parallax = min_parallax
        self.min_samples = min_samples
        self.mode = mode
        self.min_movement_ratio = min_movement_ratio
        self.max_spectral_peak = max_spectral_peak
        self._clock = clock
        self._history: dict = {}

    @staticmethod
    def _spectral_peak_ratio(face_crop) -> float:
        """Rapport pic/médiane du spectre haute fréquence d'un visage
        recadré : un écran filmé produit des pics isolés (trame, moiré) que
        la texture naturelle d'un visage n'a pas. Retourne 0 si inexploitable."""
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
        gray -= gray.mean()
        gray *= np.outer(np.hanning(96), np.hanning(96)).astype(np.float32)
        magnitude = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
        yy, xx = np.indices(magnitude.shape)
        radius = np.hypot(yy - 48, xx - 48)
        band = magnitude[(radius > 12) & (radius < 46)]
        median = float(np.median(band))
        return float(band.max() / median) if median > 1e-6 else 0.0

    def observe(self, track_id, frame, detection: dict) -> None:
        """Enregistre une mesure pour ce visage suivi. À appeler à chaque
        frame traitée où ce visage est détecté, même avant de statuer."""
        if self.mode == "off":
            return

        landmarks = np.asarray(detection["landmarks"], dtype=np.float64).reshape(5, 2)
        coords = shape_coords(landmarks)
        if coords is None:
            return

        spectral = None
        if self.max_spectral_peak is not None:
            x, y, w, h = detection["bbox"]
            y0, y1 = max(y, 0), min(y + h, frame.shape[0])
            x0, x1 = max(x, 0), min(x + w, frame.shape[1])
            face_crop = frame[y0:y1, x0:x1]
            if face_crop.size == 0:
                return
            spectral = self._spectral_peak_ratio(face_crop)

        now = self._clock()
        hist = self._history.setdefault(track_id, deque())
        hist.append({"t": now, "landmarks": landmarks, "coords": coords, "spectral": spectral})

        cutoff = now - self.window_seconds
        while hist and hist[0]["t"] < cutoff:
            hist.popleft()

    @staticmethod
    def _parallax(coords: np.ndarray) -> float:
        """Étendue robuste de (a, b) : médiane glissante sur 3 mesures
        (écrête le bruit ponctuel du détecteur) puis écart des percentiles
        10-90 sur chaque axe."""
        if len(coords) >= 3:
            coords = np.array([np.median(coords[i:i + 3], axis=0) for i in range(len(coords) - 2)])
        spread = np.percentile(coords, 90, axis=0) - np.percentile(coords, 10, axis=0)
        return float(np.hypot(spread[0], spread[1]))

    def parallax(self, track_id) -> Optional[float]:
        """Parallaxe mesurée sur la fenêtre courante (None si trop peu de mesures)."""
        hist = self._history.get(track_id)
        if not hist or len(hist) < self.min_samples:
            return None
        return self._parallax(np.array([h["coords"] for h in hist]))

    def assess(self, track_id) -> LivenessResult:
        """Évalue la vivacité d'un visage suivi.

        Une réponse `live=False` avec `needs_head_turn=False` et la raison
        "pas assez de mesures" signifie « pas encore de décision » -- à
        distinguer d'un vrai refus par l'appelant.
        """
        if self.mode == "off":
            return LivenessResult(True, "vivacite desactivee")

        hist = self._history.get(track_id)
        if not hist or len(hist) < self.min_samples:
            return LivenessResult(False, "pas assez de mesures")

        if self.max_spectral_peak is not None:
            peaks = [h["spectral"] for h in hist if h["spectral"] is not None]
            if peaks and float(np.mean(peaks)) > self.max_spectral_peak:
                return LivenessResult(False, "texture suspecte (ecran probable)")

        if self.mode == "movement":
            series = np.stack([h["landmarks"] for h in hist])
            eye_ref = np.linalg.norm(series[0, 1] - series[0, 0]) or 1.0
            displacement = np.linalg.norm(series.max(axis=0) - series.min(axis=0), axis=1).mean()
            ratio = float(displacement / eye_ref)
            if ratio < self.min_movement_ratio:
                return LivenessResult(False, "aucun mouvement detecte", ratio)
            return LivenessResult(True, "ok", ratio)

        parallax = self._parallax(np.array([h["coords"] for h in hist]))
        if parallax < self.min_parallax:
            return LivenessResult(
                False,
                f"tournez la tete ({parallax:.2f}/{self.min_parallax:.2f})",
                parallax,
                needs_head_turn=True,
            )
        return LivenessResult(True, "ok", parallax)

    def is_live(self, track_id) -> tuple:
        """Compatibilité : (vivant, raison)."""
        result = self.assess(track_id)
        return result.live, result.reason

    def reset(self, track_id) -> None:
        self._history.pop(track_id, None)
        