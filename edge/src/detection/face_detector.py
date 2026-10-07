"""
Module de détection de visage via YuNet (OpenCV).
Story 1.2 - Epic 1.
"""

import os
import threading
from collections import OrderedDict

import cv2


class FaceDetector:
    """Détecte les visages présents dans une image via le modèle YuNet.

    Une instance YuNet distincte est conservée PAR TAILLE D'ENTRÉE (caméra,
    images uploadées de /enroll et /verify...) et n'est jamais redimensionnée
    une fois créée. Raison : changer la taille d'une instance déjà utilisée
    via setInputSize() fait échouer le moteur DNN « graphe » d'OpenCV >= 4.10/5.0
    (cv2.error: Assertion failed) buf.shape() == m.shape() in function
    'forwardGraph'). Un verrou sérialise les appels : le flux de contrôle
    d'accès, l'aide à la capture et les endpoints partagent cette instance
    depuis des threads différents.
    """

    MAX_CACHED_SIZES = 4  # tailles d'entrée distinctes conservées en mémoire

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
        self._detectors: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

        # Charge une première instance dès maintenant : un modèle absent ou
        # corrompu doit échouer au démarrage, pas à la première détection.
        self._detector_for((320, 320))

    def _detector_for(self, size: tuple):
        """Retourne l'instance YuNet dédiée à cette taille (largeur, hauteur),
        en la créant au besoin. À appeler sous verrou (sauf dans __init__)."""
        detector = self._detectors.get(size)
        if detector is not None:
            self._detectors.move_to_end(size)
            return detector

        detector = cv2.FaceDetectorYN.create(
            model=self._model_path,
            config="",
            input_size=size,
            score_threshold=self.confidence_threshold,
        )
        self._detectors[size] = detector
        while len(self._detectors) > self.MAX_CACHED_SIZES:
            self._detectors.popitem(last=False)
        return detector

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
            detector = self._detector_for((width, height))
            _, faces = detector.detect(frame)

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
        