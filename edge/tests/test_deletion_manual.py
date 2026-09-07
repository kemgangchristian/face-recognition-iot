"""
Script de test MANUEL de la suppression d'identité (Story 3.3, RGPD).
Vérifie que la suppression est bien en cascade sur les embeddings.

Usage : python edge/tests/test_deletion_manual.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
from storage.database import Database
from storage.encryption import EncryptionManager
from storage.enrollment import EnrollmentService


def count_embeddings_for_identity(db, identity_id):
    """Compte directement en base (requête brute) le nombre d'embeddings
    liés à une identité — bypass volontaire du service, pour vérifier
    l'état réel de la base sans dépendre du code qu'on teste."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM embeddings WHERE identity_id = ?", (identity_id,))
    return cursor.fetchone()[0]


def identity_exists(db, identity_id):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM identities WHERE id = ?", (identity_id,))
    return cursor.fetchone()[0] > 0


def main():
    db = Database()
    db.connect()
    db.init_schema()
    encryption = EncryptionManager()
    enrollment = EnrollmentService(db, encryption)

    print("--- Préparation : enrôlement d'une identité de test ---")
    identity_id = enrollment.enroll_identity("Test User Deletion")
    fake_embedding = np.random.rand(128).astype(np.float32)
    enrollment.add_embedding(identity_id, fake_embedding)
    enrollment.add_embedding(identity_id, fake_embedding)  # 2 embeddings, comme un vrai enrôlement multi-poses

    print(f"Identité créée (id={identity_id})")
    print(f"Identité existe en base : {identity_exists(db, identity_id)}")
    print(f"Nombre d'embeddings avant suppression : {count_embeddings_for_identity(db, identity_id)}")

    print("\n--- Suppression de l'identité ---")
    deleted = enrollment.delete_identity(identity_id)
    print(f"Suppression réussie : {deleted}")

    print(f"Identité existe en base après suppression : {identity_exists(db, identity_id)}")
    print(f"Nombre d'embeddings après suppression : {count_embeddings_for_identity(db, identity_id)}")

    print("\n--- Test suppression d'un id inexistant ---")
    deleted_fake = enrollment.delete_identity(99999)
    print(f"Suppression d'un id inexistant retourne bien False : {deleted_fake == False}")

    # Verdict final
    if (not identity_exists(db, identity_id)
            and count_embeddings_for_identity(db, identity_id) == 0
            and not deleted_fake):
        print("\n Suppression en cascade validée : identité et embeddings supprimés correctement.")
    else:
        print("\n ATTENTION : la suppression en cascade ne fonctionne pas comme attendu.")

    db.close()


if __name__ == "__main__":
    main()
