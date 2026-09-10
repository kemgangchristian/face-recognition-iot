"""
Module de capture vidéo.
Story 1.1 — Epic 1. Optimisé en Story 1.4 pour la latence Raspberry Pi.

Deux implémentations selon la plateforme :
- macOS/Linux desktop : cv2.VideoCapture standard (webcam).
- Raspberry Pi (caméra CSI) : flux vidéo continu via rpicam-vid, lu par un
  thread d'arrière-plan. Remplace l'approche initiale (un rpicam-still par
  frame, Story 1.4) qui coûtait ~1065ms/frame à cause de la réinitialisation
  du capteur à chaque appel. Le flux continu ne paie ce coût qu'une seule
  fois au démarrage, ramenant read_frame() à quelques millisecondes.
"""

import platform
import subprocess
import threading
import time
import numpy as np
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
    et flux continu CSI Raspberry Pi selon la plateforme détectée."""

    def __init__(self, source: int = 0, width: int = 640, height: int = 480):
        self.source = source
        self.width = width
        self.height = height

        self._capture = None
        self._is_pi = _is_raspberry_pi()

        self._process = None
        self._reader_thread = None
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        """Ouvre la connexion à la caméra."""
        if self._is_pi:
            self._start_pi_stream()
        else:
            self._capture = cv2.VideoCapture(self.source)
            if not self._capture.isOpened():
                raise RuntimeError(f"Impossible d'ouvrir la caméra (source={self.source})")

    def _start_pi_stream(self) -> None:
        """Lance rpicam-vid en flux continu MJPEG, et démarre le thread
        qui lit ce flux en arrière-plan."""
        self._process = subprocess.Popen(
            [
                "rpicam-vid",
                "--codec", "mjpeg",
                "-o", "-",
                "-t", "0",
                "--width", str(self.width),
                "--height", str(self.height),
                "--nopreview",
                "--framerate", "15",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

        self._running = True
        self._reader_thread = threading.Thread(target=self._read_mjpeg_stream, daemon=True)
        self._reader_thread.start()

        self._wait_for_first_frame(timeout_seconds=5)

    def _read_mjpeg_stream(self) -> None:
        """Lit en continu le flux MJPEG brut depuis stdout de rpicam-vid,
        extrait chaque image JPEG complète, la décode, et la stocke comme
        dernière frame disponible."""
        buffer = b""
        jpeg_start = b"\xff\xd8"
        jpeg_end = b"\xff\xd9"

        while self._running:
            chunk = self._process.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk

            start_idx = buffer.find(jpeg_start)
            end_idx = buffer.find(jpeg_end)

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                jpeg_data = buffer[start_idx:end_idx + 2]
                buffer = buffer[end_idx + 2:]

                frame = cv2.imdecode(
                    np.frombuffer(jpeg_data, dtype=np.uint8), cv2.IMREAD_COLOR
                )
                if frame is not None:
                    with self._frame_lock:
                        self._latest_frame = frame

    def _wait_for_first_frame(self, timeout_seconds: float) -> None:
        """Bloque jusqu'à ce qu'une première frame soit disponible."""
        start = time.time()
        while time.time() - start < timeout_seconds:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return
            time.sleep(0.05)

        raise RuntimeError(
            f"Timeout : aucune frame reçue depuis rpicam-vid après {timeout_seconds}s."
        )

    def read_frame(self):
        """Lit la dernière frame disponible."""
        if self._is_pi:
            with self._frame_lock:
                if self._latest_frame is None:
                    raise RuntimeError("Aucune frame disponible. Appelle start() d'abord.")
                return self._latest_frame.copy()

        if self._capture is None:
            raise RuntimeError("La caméra n'est pas démarrée. Appelle start() d'abord.")

        success, frame = self._capture.read()
        if not success:
            raise RuntimeError("Échec de lecture de la frame caméra.")

        return frame

    def stop(self) -> None:
        """Ferme proprement la connexion à la caméra."""
        if self._is_pi:
            self._running = False
            if self._process is not None:
                self._process.terminate()
                self._process.wait(timeout=5)
            if self._reader_thread is not None:
                self._reader_thread.join(timeout=5)
        elif self._capture is not None:
            self._capture.release()
            self._capture = None
