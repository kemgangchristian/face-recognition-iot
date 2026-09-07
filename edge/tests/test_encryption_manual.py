"""
Script de test MANUEL pour EncryptionManager.
Usage : python edge/tests/test_encryption_manual.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
from storage.encryption import EncryptionManager


def main():
    print("Initialisation du gestionnaire de chiffrement...")
    manager = EncryptionManager()
    print(f"Fichier de clé : {manager.key_path}")

    # Simule un vrai embedding (vecteur 128-d, comme retourné par FaceEmbedder).
    fake_embedding = np.random.rand(128).astype(np.float32)
    original_bytes = fake_embedding.tobytes()

    print(f"Taille des données originales : {len(original_bytes)} bytes")

    encrypted = manager.encrypt(original_bytes)
    print(f"Données chiffrées (extrait) : {encrypted[:50]}...")
    print(f"Taille chiffrée : {len(encrypted)} bytes")

    decrypted = manager.decrypt(encrypted)
    recovered_embedding = np.frombuffer(decrypted, dtype=np.float32)

    # Vérifie que le vecteur récupéré après déchiffrement est identique à l'original.
    if np.array_equal(fake_embedding, recovered_embedding):
        print(" Déchiffrement conforme : les données récupérées sont identiques à l'original.")
    else:
        print(" ERREUR : les données récupérées diffèrent de l'original.")


if __name__ == "__main__":
    main()
