"""
Connexion et initialisation de la base de données SQLite locale.
Story 3.5 — Epic 3.

Note : le chiffrement des données (Story 3.4) sera ajouté dans une étape
dédiée suivante — volontairement séparé pour garder ce module simple et
testable indépendamment.
"""

import sqlite3
import os


class Database:
    """Gère la connexion à la base SQLite locale et l'initialisation du schéma."""

    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: chemin vers le fichier .sqlite. Par défaut, un fichier
                     local dans edge/storage_data/ (créé si absent).
        """
        if db_path is None:
            base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "storage_data")
            os.makedirs(base_dir, exist_ok=True)
            db_path = os.path.join(base_dir, "face_recognition.sqlite")

        self.db_path = db_path
        self._connection = None

    def connect(self) -> None:
        """Ouvre la connexion à la base et active les contraintes de clé étrangère."""
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        # SQLite désactive les FOREIGN KEY par défaut, contrairement à
        # PostgreSQL — sans cette ligne, ON DELETE CASCADE/SET NULL du
        # schéma seraient silencieusement ignorés.
        self._connection.execute("PRAGMA foreign_keys = ON")

    def init_schema(self, schema_path: str = None) -> None:
        """
        Exécute le fichier schema.sql pour créer les tables si elles n'existent
        pas déjà (CREATE TABLE IF NOT EXISTS, donc idempotent).

        Args:
            schema_path: chemin vers schema.sql. Par défaut, le fichier
                         situé dans le même dossier que ce module.
        """
        if self._connection is None:
            raise RuntimeError("Base non connectée. Appelle connect() d'abord.")

        if schema_path is None:
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

        with open(schema_path, "r") as f:
            schema_sql = f.read()

        self._connection.executescript(schema_sql)
        self._connection.commit()

    def get_connection(self) -> sqlite3.Connection:
        """Retourne la connexion active, pour usage par d'autres modules (Story 3.1+)."""
        if self._connection is None:
            raise RuntimeError("Base non connectée. Appelle connect() d'abord.")
        return self._connection

    def close(self) -> None:
        """Ferme proprement la connexion."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
