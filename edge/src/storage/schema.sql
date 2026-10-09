-- Base locale du Raspberry Pi (SQLite).
-- Une photo d'enrolement suffit : une ligne embeddings par identite.

CREATE TABLE IF NOT EXISTS identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- Renseigne si plusieurs Pi existent ; ignore en mono-site.
    site_id TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER NOT NULL,
    -- BLOB = array numpy float32 128-d, chiffre par EncryptionManager.
    vector BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS access_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- SET NULL : le log d'audit reste apres suppression RGPD, sans le nom.
    identity_id INTEGER,
    matched BOOLEAN NOT NULL,
    confidence_score REAL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_embeddings_identity ON embeddings(identity_id);
