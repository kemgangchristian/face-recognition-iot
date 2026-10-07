"""
Aide à la capture d'enrôlement : décide si une frame est une BONNE capture
(une seule personne, visage net, assez grand, entièrement dans le cadre et à
peu près centré). Aucune image n'est conservée : la frame n'est analysée
qu'en mémoire.
"""

import os


class FaceReadinessAssessor:
    """Évalue si une frame convient à un enrôlement."""

    def __init__(
        self,
        detector,
        quality_filter,
        min_width_ratio: float = None,
        edge_margin_ratio: float = 0.02,
    ):
        """
        Args:
            detector: FaceDetector (ou équivalent avec .detect(frame)).
            quality_filter: QualityFilter (ou équivalent avec .is_valid()).
            min_width_ratio: largeur minimale du visage en proportion de la
                largeur de l'image. Défaut : variable d'environnement
                ENROLL_MIN_FACE_WIDTH_RATIO, sinon 0.18.
            edge_margin_ratio: marge minimale entre le visage et le bord.
        """
        self.detector = detector
        self.quality_filter = quality_filter
        self.min_width_ratio = (
            min_width_ratio
            if min_width_ratio is not None
            else float(os.environ.get("ENROLL_MIN_FACE_WIDTH_RATIO", "0.18"))
        )
        self.edge_margin_ratio = edge_margin_ratio

    def assess(self, frame) -> tuple:
        """
        Returns:
            (face, raison) : `face` est la détection retenue (dict de
            FaceDetector.detect()) ou None si la capture doit être refusée ;
            `raison` explique la décision, en français, affichable telle quelle.
        """
        img_h, img_w = frame.shape[:2]

        detections = self.detector.detect(frame)
        if not detections:
            return None, "Aucun visage détecté dans le cadre."
        if len(detections) > 1:
            return None, "Plusieurs visages détectés : une seule personne à la fois devant la caméra."

        face = detections[0]
        if not self.quality_filter.is_valid(frame, face):
            return None, "Visage trop flou ou peu net : améliore l'éclairage et reste immobile."

        x, y, w, h = face["bbox"]
        if w < img_w * self.min_width_ratio:
            return None, "Visage trop loin : rapproche-toi de la caméra."

        margin_x = img_w * self.edge_margin_ratio
        margin_y = img_h * self.edge_margin_ratio
        if x < margin_x or y < margin_y or x + w > img_w - margin_x or y + h > img_h - margin_y:
            return None, "Visage coupé par le bord du cadre : recentre-toi."

        center_x, center_y = x + w / 2, y + h / 2
        if not (0.25 * img_w <= center_x <= 0.75 * img_w and 0.20 * img_h <= center_y <= 0.80 * img_h):
            return None, "Place le visage au centre du cadre."

        return face, "Visage bien placé : prêt à capturer."
        