"""
Filtrage qualité des visages détectés (taille, flou, confiance).
Story 1.3 — Epic 1.
"""

import cv2


class QualityFilter:
    """Filtre les détections de visage de faible qualité avant traitement."""

    def __init__(
        self,
        min_face_size: int = 40,
        min_confidence: float = 0.7,
        min_sharpness: float = 5.0,
    ):
        """
        Args:
            min_face_size: largeur/hauteur minimale en pixels pour qu'un
                           visage soit exploitable par l'extraction d'embedding.
            min_confidence: score de confiance minimum accepté.
            min_sharpness: seuil minimum de netteté (variance du Laplacien).
                           En dessous, l'image est considérée trop floue.
        """
        self.min_face_size = min_face_size
        self.min_confidence = min_confidence
        self.min_sharpness = min_sharpness

    def _compute_sharpness(self, face_crop) -> float:
        """Calcule la netteté d'une image via la variance du Laplacien."""
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def is_valid(self, frame, detection: dict) -> bool:
        """
        Vérifie si une détection passe tous les critères de qualité.

        Args:
            frame: l'image complète (numpy.ndarray) d'où provient la détection.
            detection: dict retourné par FaceDetector.detect() (une entrée).

        Returns:
            bool: True si le visage est exploitable, False sinon.
        """
        x, y, w, h = detection["bbox"]

        # Critère 1 : score de confiance
        if detection["confidence"] < self.min_confidence:
            return False

        # Critère 2 : taille minimale
        if w < self.min_face_size or h < self.min_face_size:
            return False

        # Critère 3 : netteté (nécessite de recadrer le visage dans la frame)
        # On sécurise les bornes pour éviter un crop hors image si la bbox
        # déborde légèrement (arrive parfois en bord de cadre).
        y_end = min(y + h, frame.shape[0])
        x_end = min(x + w, frame.shape[1])
        face_crop = frame[max(y, 0):y_end, max(x, 0):x_end]

        if face_crop.size == 0:
            return False

        sharpness = self._compute_sharpness(face_crop)
        if sharpness < self.min_sharpness:
            return False

        return True

    def filter(self, frame, detections: list) -> list:
        """
        Filtre une liste de détections, ne garde que celles jugées valides.

        Args:
            frame: l'image complète.
            detections: liste de dicts retournée par FaceDetector.detect().

        Returns:
            list[dict]: sous-ensemble de detections passant tous les critères.
        """
        return [d for d in detections if self.is_valid(frame, d)]
    