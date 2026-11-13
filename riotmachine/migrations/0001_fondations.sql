-- Lot 1 : fondations. Révisions et historique (R-A4, R-T6), clips, blocs, plans,
-- retours avec la baseline de Michael à part (R-A3), générations à clé unique
-- (R-T5), trace de l'import de la base v1 (D15).
-- Les autres tables naissent avec leur lot.

CREATE TABLE revisions (
    id INTEGER PRIMARY KEY,
    author TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    undoes INTEGER REFERENCES revisions(id),
    undone_by INTEGER REFERENCES revisions(id)
);

CREATE TABLE changes (
    id INTEGER PRIMARY KEY,
    revision_id INTEGER NOT NULL REFERENCES revisions(id),
    object_type TEXT NOT NULL,
    object_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    before TEXT,
    after TEXT,
    author TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_changes_object ON changes(object_type, object_id, id);
CREATE INDEX idx_changes_revision ON changes(revision_id);

CREATE TABLE clips (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    brief TEXT,                       -- baseline de Michael
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE blocks (
    id INTEGER PRIMARY KEY,
    clip_id INTEGER NOT NULL REFERENCES clips(id),
    num INTEGER NOT NULL,
    name TEXT NOT NULL,
    intention TEXT,                   -- baseline de Michael
    production_notes TEXT,            -- écrit par les agents, à côté
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX idx_blocks_clip ON blocks(clip_id, num);

CREATE TABLE shots (
    id INTEGER PRIMARY KEY,
    clip_id INTEGER NOT NULL REFERENCES clips(id),
    block_id INTEGER REFERENCES blocks(id),
    num INTEGER NOT NULL,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    words TEXT,                       -- baseline de Michael : les mots du plan
    production_text TEXT,             -- version de production, écrite par les agents
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    CHECK (t_end > t_start)
);
CREATE INDEX idx_shots_clip ON shots(clip_id, num);

CREATE TABLE feedback (
    id INTEGER PRIMARY KEY,
    object_type TEXT NOT NULL,        -- clip | block | shot
    object_id INTEGER NOT NULL,
    text TEXT NOT NULL,               -- baseline de Michael
    route TEXT,
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX idx_feedback_object ON feedback(object_type, object_id);

CREATE TABLE generations (
    id INTEGER PRIMARY KEY,
    idem_key TEXT NOT NULL UNIQUE,    -- clé unique : un double clic ou une reprise ne crée rien de plus
    object_type TEXT NOT NULL,
    object_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    est_cost REAL NOT NULL DEFAULT 0,
    real_cost REAL,
    status TEXT NOT NULL DEFAULT 'prevue'
        CHECK (status IN ('prevue','envoi','envoyee','recue','refusee','echec','a_verifier')),
    request_id TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX idx_generations_status ON generations(status);
CREATE INDEX idx_generations_object ON generations(object_type, object_id);

CREATE TABLE import_v1 (
    id INTEGER PRIMARY KEY,
    step TEXT NOT NULL,
    legacy_key TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    UNIQUE (step, legacy_key)
);
