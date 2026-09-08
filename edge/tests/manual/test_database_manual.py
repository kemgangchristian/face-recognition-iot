"""
Script de test MANUEL pour Database (connexion + initialisation du schéma).
Usage : python edge/tests/test_database_manual.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.database import Database


def main():
    print("Initialisation de la base de données...")
    db = Database()
    print(f"Fichier de base : {db.db_path}")

    db.connect()
    db.init_schema()
    print("Schéma initialisé.")

    conn = db.get_connection()
    cursor = conn.cursor()

    # Vérifie que les 3 tables attendues existent bien.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables présentes : {tables}")

    expected_tables = {"identities", "embeddings", "access_logs"}
    if expected_tables.issubset(set(tables)):
        print(" Toutes les tables attendues sont présentes.")
    else:
        print(f" Tables manquantes : {expected_tables - set(tables)}")

    # Test d'insertion/lecture simple pour valider que la base est fonctionnelle.
    cursor.execute(
        "INSERT INTO identities (full_name, site_id) VALUES (?, ?)",
        ("Test User", "site_test")
    )
    conn.commit()

    cursor.execute("SELECT id, full_name, site_id FROM identities WHERE full_name = ?", ("Test User",))
    result = cursor.fetchone()
    print(f"Ligne insérée et relue : {result}")

    # Nettoyage : on supprime la donnée de test pour ne pas polluer la base.
    cursor.execute("DELETE FROM identities WHERE full_name = ?", ("Test User",))
    conn.commit()
    print("Donnée de test nettoyée.")

    db.close()
    print("Connexion fermée proprement.")


if __name__ == "__main__":
    main()
