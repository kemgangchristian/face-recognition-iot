"""
Module de détection de visage via YuNet (OpenCV).
Story 1.2 - Epic 1.
"""

import os
import cv2


class FaceDetector:
    """Détecte les visages présents dans une image via le modèle YuNet."""

    def __init__(
        self,
        model_path: str = None,
        confidence_threshold: float = 0.7,
    ):
        """
        Args:
            model_path: chemin vers le fichier .onnx du modèle YuNet.
                        Par défaut : edge/models/face_detection_yunet.onnx
            confidence_threshold: score minimum (0-1) pour qu'une détection
                                   soit considérée valide.
        """
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "models", "face_detection_yunet.onnx"
            )

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Modèle introuvable : {model_path}. "
                f"Voir edge/models/README.md pour le télécharger."
            )

        self.confidence_threshold = confidence_threshold
        self._detector = cv2.FaceDetectorYN.create(
            model=model_path,
            config="",
            input_size=(320, 320),  # taille par défaut, ajustée dynamiquement dans detect()
            score_threshold=confidence_threshold,
        )

    def detect(self, frame):
        """
        Détecte les visages dans une frame.

        Args:
            frame: image numpy.ndarray (format BGR, issue de Camera.read_frame()).

        Returns:
            list[dict]: une entrée par visage détecté, avec les clés :
                - "bbox": (x, y, largeur, hauteur)
                - "confidence": score de confiance (float)
                - "landmarks": liste de 5 points (yeux, nez, coins de bouche)
        """
        height, width = frame.shape[:2]
        self._detector.setInputSize((width, height))

        _, faces = self._detector.detect(frame)

        results = []
        if faces is not None:
            for face in faces:
                x, y, w, h = face[0:4].astype(int)
                landmarks = face[4:14].reshape(5, 2).astype(int).tolist()
                confidence = float(face[14])

                results.append({
                    "bbox": (int(x), int(y), int(w), int(h)),
                    "confidence": confidence,
                    "landmarks": landmarks,
                })

        return results