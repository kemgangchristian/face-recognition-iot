"""
Module de capture vidéo.
Story 1.1 — Epic 1.

Deux implémentations selon la plateforme :
- Sur macOS/Linux desktop : cv2.VideoCapture standard (webcam).
- Sur Raspberry Pi (caméra CSI) : appel à rpicam-still en sous-processus,
  car picamera2 (librairie officielle) est lié à la version Python système
  du Pi, incompatible avec notre Python 3.11.9 (pyenv) utilisé sur tout
  le projet. Un exécutable binaire externe n'a aucune dépendance à la
  version Python qui l'appelle — ça évite ce conflit à la racine.
"""

import platform
import subprocess
import tempfile
import os
import cv2


def _is_raspberry_pi() -> bool:
    """Détecte si le code tourne sur un Raspberry Pi (Linux + modèle Pi)."""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/device-tree/model", "r") as f:
            return "raspberry pi" in f.read().lower()
    except FileNotFoundError:
        return False


class Camera:
    """Gère l'ouverture, la lecture et la fermeture du flux caméra.
    Bascule automatiquement entre webcam standard (macOS/Linux desktop)
    et module CSI Raspberry Pi selon la plateforme détectée."""

    def __init__(self, source: int = 0):
        """
        Args:
            source: index du périphérique vidéo, utilisé uniquement sur
                    plateforme non-Pi (webcam standard).
        """
        self.source = source
        self._capture = None
        self._is_pi = _is_raspberry_pi()

    def start(self) -> None:
        """Ouvre la connexion à la caméra."""
        if self._is_pi:
            result = subprocess.run(
                ["which", "rpicam-still"], capture_output=True
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "rpicam-still introuvable. Installe rpicam-apps : "
                    "sudo apt install -y rpicam-apps"
                )
        else:
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
        if self._is_pi:
            return self._read_frame_pi()

        if self._capture is None:
            raise RuntimeError("La caméra n'est pas démarrée. Appelle start() d'abord.")

        success, frame = self._capture.read()
        if not success:
            raise RuntimeError("Échec de lecture de la frame caméra.")

        return frame

    def _read_frame_pi(self):
        """Capture une image via rpicam-still (sous-processus), vers un
        fichier temporaire, puis la charge avec OpenCV."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [
                    "rpicam-still",
                    "-o", tmp_path,
                    "--timeout", "500",
                    "--nopreview",
                    "--width", "640",
                    "--height", "480",
                ],
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Échec de capture rpicam-still : {result.stderr.decode()}"
                )

            frame = cv2.imread(tmp_path)
            if frame is None:
                raise RuntimeError("Image capturée illisible par OpenCV.")

            return frame

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def stop(self) -> None:
        """Ferme proprement la connexion à la caméra."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
