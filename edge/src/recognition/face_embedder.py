"""
Extraction d'embedding facial via SFace (OpenCV Zoo).
Story 2.3 — Epic 2.
"""

import os
import numpy as np
import cv2


class FaceEmbedder:
    """Extrait un vecteur d'embedding (128-d) à partir d'un visage détecté,
    via le modèle SFace. Gère aussi l'alignement natif requis par ce modèle."""

    def __init__(self, model_path: str = None):
        """
        Args:
            model_path: chemin vers le fichier .onnx du modèle SFace.
                        Par défaut : edge/models/face_recognition_sface.onnx
        """
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "models", "face_recognition_sface.onnx"
            )

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Modèle introuvable : {model_path}. "
                f"Voir edge/models/README.md pour le télécharger."
            )

        self._recognizer = cv2.FaceRecognizerSF.create(model_path, "")

    def _to_yunet_raw_format(self, detection: dict) -> np.ndarray:
        """
        Reconstruit le format brut attendu par alignCrop() (15 valeurs :
        bbox[4] + landmarks[10] + score[1]) à partir de notre format dict
        simplifié retourné par FaceDetector.detect().

        Args:
            detection: dict avec les clés "bbox", "landmarks", "confidence".

        Returns:
            numpy.ndarray de forme (15,), format attendu par cv2.FaceRecognizerSF.
        """
        x, y, w, h = detection["bbox"]
        landmarks_flat = [coord for point in detection["landmarks"] for coord in point]
        confidence = detection["confidence"]

        raw = [x, y, w, h] + landmarks_flat + [confidence]
        return np.array(raw, dtype=np.float32).reshape(1, -1)

    def extract(self, frame, detection: dict) -> np.ndarray:
        """
        Aligne et extrait l'embedding d'un visage détecté.

        Args:
            frame: image complète (numpy.ndarray, format BGR).
            detection: dict retourné par FaceDetector.detect() (une entrée).

        Returns:
            numpy.ndarray: vecteur d'embedding (128 dimensions, float32).
        """
        raw_face = self._to_yunet_raw_format(detection)

        aligned_face = self._recognizer.alignCrop(frame, raw_face)
        embedding = self._recognizer.feature(aligned_face)

        return embedding.flatten()

    def compare(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        """
        Compare deux embeddings via similarité cosinus.

        Args:
            embedding_a, embedding_b: vecteurs d'embedding (128-d).

        Returns:
            float: score de similarité cosinus (proche de 1 = même personne,
                   proche de 0 ou négatif = personnes différentes).
        """
        return float(self._recognizer.match(
            embedding_a.reshape(1, -1),
            embedding_b.reshape(1, -1),
            cv2.FaceRecognizerSF_FR_COSINE
        ))
    