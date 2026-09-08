"""
Tests automatisés pour EncryptionManager — aucune dépendance matérielle.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
from storage.encryption import EncryptionManager


def test_encrypt_decrypt_roundtrip():
    """Des données chiffrées puis déchiffrées doivent être identiques à l'original."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        key_path = os.path.join(tmp_dir, "test.key")
        manager = EncryptionManager(key_path=key_path)

        original = np.random.rand(128).astype(np.float32).tobytes()
        encrypted = manager.encrypt(original)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == original


def test_encrypted_data_differs_from_original():
    """Les données chiffrées ne doivent jamais être identiques aux données brutes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        key_path = os.path.join(tmp_dir, "test.key")
        manager = EncryptionManager(key_path=key_path)

        original = b"donnee_sensible_test"
        encrypted = manager.encrypt(original)

        assert encrypted != original


def test_key_file_created_with_restricted_permissions():
    """Le fichier de clé généré doit avoir des permissions restreintes (0600)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        key_path = os.path.join(tmp_dir, "test.key")
        EncryptionManager(key_path=key_path)

        assert os.path.exists(key_path)
        permissions = oct(os.stat(key_path).st_mode)[-3:]
        assert permissions == "600"


def test_existing_key_is_reused_not_regenerated():
    """Si le fichier de clé existe déjà, il doit être réutilisé (pas régénéré),
    sinon les données déjà chiffrées deviendraient illisibles."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        key_path = os.path.join(tmp_dir, "test.key")

        manager_1 = EncryptionManager(key_path=key_path)
        encrypted_by_first = manager_1.encrypt(b"test_data")

        manager_2 = EncryptionManager(key_path=key_path)
        decrypted_by_second = manager_2.decrypt(encrypted_by_first)

        assert decrypted_by_second == b"test_data"
        