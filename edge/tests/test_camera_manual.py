"""
Script de test MANUEL pour la classe Camera.
À lancer soi-même en local — n'est PAS un test automatisé (pas de pytest,
ne doit jamais tourner dans le pipeline CI/CD qui n'a pas de caméra).

Usage : python edge/tests/test_camera_manual.py
Appuie sur 'q' pour quitter la fenêtre d'affichage.
"""

import sys
import os

# Permet d'importer le module capture/ depuis la racine du projet
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
from capture.camera import Camera


def main():
    camera = Camera(source=0)

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée. Appuie sur 'q' pour quitter.")

    try:
        while True:
            frame = camera.read_frame()
            cv2.imshow("Test Camera - appuie sur 'q' pour quitter", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("Caméra arrêtée proprement.")


if __name__ == "__main__":
    main()