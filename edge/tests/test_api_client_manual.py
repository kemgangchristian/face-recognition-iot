"""
Script client MANUEL pour tester l'API via la caméra en direct.
Nécessite que le serveur API tourne déjà (uvicorn edge.src.api.main:app --port 8000).

Usage : python edge/tests/test_api_client_manual.py
- 'e' : capturer la frame actuelle et l'envoyer à /enroll
- 'v' : capturer la frame actuelle et l'envoyer à /verify
- 'q' : quitter
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
import requests
from capture.camera import Camera

API_URL = "http://127.0.0.1:8000"


def frame_to_jpeg_bytes(frame):
    """Encode une frame OpenCV (numpy array) en bytes JPEG, format attendu
    par l'upload multipart de l'API."""
    success, encoded = cv2.imencode(".jpg", frame)
    if not success:
        raise RuntimeError("Échec de l'encodage JPEG.")
    return encoded.tobytes()


def main():
    camera = Camera(source=0)

    print("Démarrage de la caméra...")
    camera.start()
    print("Caméra démarrée.")
    print("'e' = enrôler, 'v' = vérifier, 'q' = quitter.")

    try:
        while True:
            frame = camera.read_frame()
            cv2.imshow("Test API Client - 'e'=enroler 'v'=verifier 'q'=quitter", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("e"):
                name = input("\nNom à enrôler : ").strip()
                if name:
                    jpeg_bytes = frame_to_jpeg_bytes(frame)
                    response = requests.post(
                        f"{API_URL}/enroll",
                        data={"full_name": name},
                        files={"image": ("frame.jpg", jpeg_bytes, "image/jpeg")},
                    )
                    print(f"Statut : {response.status_code}")
                    print(f"Réponse : {response.json()}\n")

            elif key == ord("v"):
                jpeg_bytes = frame_to_jpeg_bytes(frame)
                response = requests.post(
                    f"{API_URL}/verify",
                    files={"image": ("frame.jpg", jpeg_bytes, "image/jpeg")},
                )
                print(f"Statut : {response.status_code}")
                print(f"Réponse : {response.json()}\n")

    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("Caméra arrêtée proprement.")


if __name__ == "__main__":
    main()
    