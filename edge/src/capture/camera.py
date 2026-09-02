"""
Module de capture vidéo depuis la caméra CSI du Raspberry Pi.
Story 1.1 — Epic 1.
"""

import cv2


class Camera:
    """Gère l'ouverture, la lecture et la fermeture du flux caméra."""

    def __init__(self, source: int = 0):
        """
        Args:
            source: index du périphérique vidéo. 0 = caméra par défaut
                    (module CSI sur Raspberry Pi correctement configuré).
        """
        self.source = source
        self._capture = None

    def start(self) -> None:
        """Ouvre la connexion à la caméra."""
        self._capture = cv2.VideoCapture(self.source)
        if not self._capture.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la caméra (source={self.source})")

    def read_frame(self):
        """
        Lit une frame depuis le flux vidéo.

        Returns:
            numpy.ndarray: l'image capturée (format BGR, standard OpenCV).

        Raises:
            RuntimeError: si la caméra n'est pas démarrée ou si la lecture échoue.
        """
        if self._capture is None:
            raise RuntimeError("La caméra n'est pas démarrée. Appelle start() d'abord.")

        success, frame = self._capture.read()
        if not success:
            raise RuntimeError("Échec de lecture de la frame caméra.")

        return frame

    def stop(self) -> None:
        """Ferme proprement la connexion à la caméra."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            