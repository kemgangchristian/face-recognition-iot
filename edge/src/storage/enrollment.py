"""
Enrôlement d'identités : orchestration embedding + chiffrement + stockage.
Story 3.1 — Epic 3.
"""

import numpy as np
from .database import Database
from .encryption import EncryptionManager


class EnrollmentService:
    """Gère l'ajout de nouvelles identités et de leurs embeddings en base,
    avec chiffrement systématique des vecteurs avant stockage."""

    def __init__(self, database: Database, encryption_manager: EncryptionManager):
        """
        Args:
            database: instance Database déjà connectée (connect() + init_schema() appelés).
            encryption_manager: instance EncryptionManager pour chiffrer les embeddings.
        """
        self.db = database
        self.encryption = encryption_manager

    def enroll_identity(self, full_name: str, site_id: str = None) -> int:
        """
        Crée une nouvelle identité (sans embedding pour l'instant).

        Args:
            full_name: nom complet de la personne enrôlée.
            site_id: identifiant du site d'enrôlement (préparation multi-sites).

        Returns:
            int: l'id de l'identité créée, à réutiliser pour add_embedding().
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO identities (full_name, site_id) VALUES (?, ?)",
            (full_name, site_id)
        )
        conn.commit()
        return cursor.lastrowid

    def add_embedding(self, identity_id: int, embedding: np.ndarray) -> None:
        """
        Ajoute un embedding (une pose) à une identité existante, chiffré au repos.

        Args:
            identity_id: id retourné par enroll_identity().
            embedding: vecteur numpy (128-d, float32) issu de FaceEmbedder.extract().
        """
        raw_bytes = embedding.astype(np.float32).tobytes()
        encrypted_bytes = self.encryption.encrypt(raw_bytes)

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO embeddings (identity_id, vector) VALUES (?, ?)",
            (identity_id, encrypted_bytes)
        )
        conn.commit()

    def get_all_embeddings(self) -> list[dict]:
        """
        Récupère tous les embeddings de la base, déchiffrés, avec l'identité associée.
        Utilisé par le module de matching (Epic 4).

        Returns:
            list[dict]: chaque entrée contient "identity_id", "full_name", "vector"
                        (numpy.ndarray déchiffré, prêt à comparer).
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT embeddings.identity_id, identities.full_name, embeddings.vector
            FROM embeddings
            JOIN identities ON embeddings.identity_id = identities.id
            """
        )

        results = []
        for identity_id, full_name, encrypted_vector in cursor.fetchall():
            decrypted_bytes = self.encryption.decrypt(encrypted_vector)
            vector = np.frombuffer(decrypted_bytes, dtype=np.float32)
            results.append({
                "identity_id": identity_id,
                "full_name": full_name,
                "vector": vector,
            })

        return results

    
    def delete_identity(self, identity_id: int) -> bool:
        """
        Supprime une identité et tous ses embeddings associés (droit à
        l'effacement RGPD). Les embeddings sont supprimés automatiquement
        via ON DELETE CASCADE défini dans le schéma. Les logs d'accès
        associés sont conservés mais anonymisés (identity_id mis à NULL
        via ON DELETE SET NULL) pour préserver l'audit de sécurité.

        Args:
            identity_id: id de l'identité à supprimer.

        Returns:
            bool: True si une identité a bien été supprimée, False si
                  aucune identité ne correspondait à cet id.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM identities WHERE id = ?", (identity_id,))
        conn.commit()

        return cursor.rowcount > 0


    
    def log_access_attempt(self, identity_id, matched: bool, confidence: float) -> None:
        """
        Enregistre une tentative de reconnaissance dans l'historique d'audit.

        Args:
            identity_id: id de l'identité reconnue, ou None si inconnu.
            matched: True si une identité a été reconnue.
            confidence: score de confiance du matching.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO access_logs (identity_id, matched, confidence_score) VALUES (?, ?, ?)",
            (identity_id, matched, confidence)
        )
        conn.commit()

    def get_access_logs(self, limit: int = 100) -> list[dict]:
        """
        Récupère l'historique des tentatives de reconnaissance, du plus récent
        au plus ancien. Utilise un LEFT JOIN (pas INNER JOIN) pour continuer
        à afficher les logs même si l'identité associée a été supprimée
        depuis (droit à l'effacement RGPD, Story 3.3) — le nom apparaît
        alors comme None plutôt que de faire disparaître le log d'audit.

        Args:
            limit: nombre maximum de logs à retourner.

        Returns:
            list[dict]: logs avec id, full_name (ou None), matched,
                        confidence_score, timestamp.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT access_logs.id, identities.full_name, access_logs.matched,
                   access_logs.confidence_score, access_logs.timestamp
            FROM access_logs
            LEFT JOIN identities ON access_logs.identity_id = identities.id
            ORDER BY access_logs.timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )

        return [
            {
                "id": row[0],
                "full_name": row[1],
                "matched": bool(row[2]),
                "confidence": row[3],
                "timestamp": row[4],
            }
            for row in cursor.fetchall()
        ]


    def purge_old_logs(self, retention_days: int = 90) -> int:
        """
        Supprime les logs d'accès plus anciens que la durée de rétention.
        Story 9.1 — Epic 9 (conformité RGPD, minimisation des données).

        Args:
            retention_days: nombre de jours au-delà desquels un log est purgé.

        Returns:
            int: nombre de lignes supprimées.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM access_logs WHERE timestamp < datetime('now', ?)",
            (f"-{retention_days} days",)
        )
        conn.commit()
        return cursor.rowcount
    