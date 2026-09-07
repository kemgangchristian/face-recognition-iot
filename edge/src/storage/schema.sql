-- =============================================================================
-- Schéma de base de données — Module Edge
-- Story 3.5 — Epic 3
-- =============================================================================

-- Une ligne par personne enrôlée.
CREATE TABLE IF NOT EXISTS identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
    site_id TEXT
    -- site_id : préparation pour l'architecture multi-sites (Epic 7),
    -- permet de savoir sur quel Pi/site la personne a été enrôlée initialement.
);

-- Plusieurs embeddings par identité (plusieurs poses, cf. Story 3.2).
-- Le vecteur est stocké en BLOB (format binaire brut d'un array numpy).
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER NOT NULL,
    vector BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE CASCADE
    -- ON DELETE CASCADE : si une identité est supprimée (droit à l'effacement
    -- RGPD, Story 3.3), ses embeddings sont automatiquement supprimés aussi.
);

-- Historique des tentatives de reconnaissance (alimenté à partir de l'Epic 5).
CREATE TABLE IF NOT EXISTS access_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER,
    matched BOOLEAN NOT NULL,
    confidence_score REAL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE SET NULL
    -- ON DELETE SET NULL (pas CASCADE) : si une identité est supprimée, on
    -- garde une trace anonymisée du log d'audit plutôt que de le perdre —
    -- utile pour la conformité/audit sans conserver la donnée identifiante.
);

-- Index pour accélérer les recherches d'embeddings par identité (fréquent
-- lors du matching et de la gestion des enrôlements).
CREATE INDEX IF NOT EXISTS idx_embeddings_identity ON embeddings(identity_id);
