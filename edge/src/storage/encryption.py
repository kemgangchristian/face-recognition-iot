"""
Chiffrement au repos des embeddings biométriques (AES via Fernet).
Story 3.4 — Epic 3.

ATTENTION : le fichier de clé (storage_data/encryption.key) est critique.
S'il est perdu, toutes les données chiffrées deviennent illisibles.
S'il est compromis, toutes les données chiffrées sont compromises.
Pour une V1 edge, un fichier local à permissions restreintes est acceptable
(le Pi est supposé physiquement sécurisé) ; une vraie mise en production
devrait envisager un gestionnaire de secrets dédié (ex: HashiCorp Vault,
AWS KMS) — noté comme amélioration future, pas nécessaire pour le MVP.
"""

import os
from cryptography.fernet import Fernet


class EncryptionManager:
    """Gère le chiffrement/déchiffrement AES des données sensibles au repos."""

    def __init__(self, key_path: str = None):
        """
        Args:
            key_path: chemin vers le fichier contenant la clé de chiffrement.
                      Généré automatiquement à la première utilisation s'il
                      n'existe pas encore.
        """
        if key_path is None:
            base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "storage_data")
            os.makedirs(base_dir, exist_ok=True)
            key_path = os.path.join(base_dir, "encryption.key")

        self.key_path = key_path
        self._fernet = self._load_or_create_key()

    def _load_or_create_key(self) -> Fernet:
        """Charge la clé existante, ou en génère une nouvelle si absente."""
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as f:
                f.write(key)
            # Restreint les permissions au propriétaire uniquement (lecture/écriture) —
            # bonne pratique standard pour un fichier de clé sur un système Unix.
            os.chmod(self.key_path, 0o600)

        return Fernet(key)

    def encrypt(self, data: bytes) -> bytes:
        """Chiffre des données brutes (ex: bytes d'un vecteur numpy)."""
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        """Déchiffre des données précédemment chiffrées par cette instance."""
        return self._fernet.decrypt(token)
    