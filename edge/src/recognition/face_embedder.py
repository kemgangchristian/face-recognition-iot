"""
Extraction d'un embedding 128-d avec SFace (OpenCV Zoo, Apache-2.0).

Le Pi n'utilise que ce modele. L'alignement passe par alignCrop natif de
SFace, comme a l'entrainement d'origine.
"""

import os

import numpy as np
import cv2


class FaceEmbedder:
    """Pipeline production : recadrage YuNet -> SFace -> vecteur 128-d."""

    def __init__(self, model_path: str = None):
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "models",
                "face_recognition_sface.onnx",
            )

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Modele introuvable : {model_path}. "
                "Voir edge/models/README.md pour le telecharger."
            )

        self._recognizer = cv2.FaceRecognizerSF.create(model_path, "")

    def _to_yunet_raw_format(self, detection: dict) -> np.ndarray:
        """Reconstruit le tenseur YuNet (bbox + 5 landmarks + score) attendu par alignCrop."""
        x, y, w, h = detection["bbox"]
        landmarks_flat = [coord for point in detection["landmarks"] for coord in point]
        raw = [x, y, w, h] + landmarks_flat + [detection["confidence"]]
        return np.array(raw, dtype=np.float32).reshape(1, -1)

    def extract(self, frame, detection: dict) -> np.ndarray:
        """Aligne le visage detecte et retourne l'embedding float32 (128,)."""
        raw_face = self._to_yunet_raw_format(detection)
        aligned_face = self._recognizer.alignCrop(frame, raw_face)
        return self._recognizer.feature(aligned_face).flatten().astype(np.float32)

    def compare(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        """Similarite cosinus. Proche de 1 = meme personne, bas = personnes differentes."""
        return float(self._recognizer.match(
            embedding_a.reshape(1, -1),
            embedding_b.reshape(1, -1),
            cv2.FaceRecognizerSF_FR_COSINE,
        ))


def build_embedder(model_path: str = None) -> FaceEmbedder:
    """Point d'entree unique pour l'API et les scripts (toujours SFace)."""
    return FaceEmbedder(model_path)
