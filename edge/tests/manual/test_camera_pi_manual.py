"""
Script de test MANUEL pour Camera sur Raspberry Pi (headless, sans écran).
Capture une frame et la sauvegarde en fichier, pour vérification visuelle
après rapatriement sur une machine avec écran.

Usage : python tests/manual/test_camera_pi_manual.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import cv2
from capture.camera import Camera


def main():
    camera = Camera()

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée. Capture d'une frame...")

    try:
        frame = camera.read_frame()
        output_path = "test_capture_pi.jpg"
        cv2.imwrite(output_path, frame)
        print(f"✅ Frame capturée et sauvegardée : {output_path}")
        print(f"Dimensions : {frame.shape}")
    finally:
        camera.stop()
        print("Caméra arrêtée proprement.")


if __name__ == "__main__":
    main()

