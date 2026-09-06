"""
Alignement de visage par transformation affine, basé sur les 5 landmarks
retournés par YuNet (yeux, nez, coins de bouche).
Story 2.2 — Epic 2.
"""

import cv2
import numpy as np


class FaceAligner:
    """Aligne un visage détecté vers un crop normalisé 112x112, standard
    pour l'entrée des modèles d'embedding type ArcFace/MobileFaceNet."""

    # Positions de référence standard (5 points) pour un crop 112x112.
    # Ce sont des coordonnées reconnues dans la communauté ArcFace/InsightFace,
    # pas des valeurs inventées — elles garantissent la compatibilité avec
    # des modèles pré-entraînés sur ce même référentiel.
    REFERENCE_LANDMARKS = np.array([
        [38.2946, 51.6963],  # œil gauche
        [73.5318, 51.5014],  # œil droit
        [56.0252, 71.7366],  # nez
        [41.5493, 92.3655],  # coin gauche de la bouche
        [70.7299, 92.2041],  # coin droit de la bouche
    ], dtype=np.float32)

    def __init__(self, output_size: int = 112):
        """
        Args:
            output_size: taille (en pixels, carré) du visage aligné en sortie.
        """
        self.output_size = output_size

    def align(self, frame, landmarks):
        """
        Aligne un visage à partir de ses 5 landmarks détectés.

        Args:
            frame: image complète (numpy.ndarray, format BGR).
            landmarks: liste de 5 points [(x, y), ...] issue de
                       FaceDetector.detect() (clé "landmarks").

        Returns:
            numpy.ndarray: image du visage aligné, taille (output_size, output_size).
        """
        src_points = np.array(landmarks, dtype=np.float32)

        # Calcule la transformation affine optimale (moindres carrés) qui
        # rapproche au mieux les landmarks détectés des positions de référence.
        transform_matrix, _ = cv2.estimateAffinePartial2D(
            src_points, self.REFERENCE_LANDMARKS
        )

        if transform_matrix is None:
            raise RuntimeError("Impossible de calculer la transformation d'alignement.")

        aligned_face = cv2.warpAffine(
            frame, transform_matrix, (self.output_size, self.output_size)
        )

        return aligned_face
    