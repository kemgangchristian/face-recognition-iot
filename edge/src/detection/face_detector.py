"""
Module de détection de visage via YuNet (OpenCV).
Story 1.2 - Epic 1.
"""

import os
import threading

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

        self._model_path = model_path
        self.confidence_threshold = confidence_threshold
        self._input_size = (320, 320)  # taille par défaut, ajustée dynamiquement dans detect()
        self._detector = cv2.FaceDetectorYN.create(
            model=model_path,
            config="",
            input_size=self._input_size,
            score_threshold=confidence_threshold,
        )
        # Protège l'instance YuNet, partagée entre le thread du flux vidéo
        # (résolution caméra, en continu) et les requêtes /enroll et /verify
        # (résolution de la photo uploadée, ponctuelles). Sans ce verrou, un
        # changement de taille déclenché par l'un peut remplacer
        # self._detector pendant qu'un appel detect() de l'autre est en
        # cours, provoquant un mismatch de forme dans le graphe interne
        # (cv2.error: ... buf.shape() == m.shape() in function
        # 'forwardGraph' -- bug du moteur DNN "graphe" d'OpenCV >= 4.10/5.0
        # quand setInputSize() change la taille sur une instance déjà
        # utilisée).
        self._lock = threading.Lock()

    def detect(self, frame):
        """
        Détecte les visages dans une frame.

        Args:
            frame: image numpy.ndarray (format BGR, issue de Camera.read_frame()
                   ou d'une image uploadée décodée en BGR).

        Returns:
            list[dict]: une entrée par visage détecté, avec les clés :
                - "bbox": (x, y, largeur, hauteur)
                - "confidence": score de confiance (float)
                - "landmarks": liste de 5 points (yeux, nez, coins de bouche)
        """
        height, width = frame.shape[:2]

        with self._lock:
            if (width, height) != self._input_size:
                self._input_size = (width, height)
                self._detector = cv2.FaceDetectorYN.create(
                    model=self._model_path,
                    config="",
                    input_size=self._input_size,
                    score_threshold=self.confidence_threshold,
                )

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
        