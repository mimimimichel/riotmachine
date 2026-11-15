"""Base SQLite : schéma, connexion et petites fonctions d'accès.

La base est la source de vérité des statuts (clips, plans, versions, validations).
Les fichiers (images, vidéos, fiches personnages) vivent dans studio/.
Pour passer plus tard à une base hébergée (Turso = SQLite en ligne), seul ce
module change.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .settings import get_settings

# Schéma versionné (R-G3) : `BASELINE_VERSION` est le schéma d'avant les migrations
# numérotées (SCHEMA + LATER_COLUMNS, idempotents). Chaque version suivante est une
# fonction de MIGRATIONS, rejouable sans effet, précédée d'une sauvegarde de la base.
BASELINE_VERSION = 4
SCHEMA_VERSION = 10

# --- Cycle de vie ---------------------------------------------------------

CLIP_STAGES = [
    "script",            # concept, dossier, paroles et découpage en préparation
    "decoupage_review",  # découpage (blocs et plans) complété, attend Michael
    "production",        # plans en production (images -> vidéos -> finals)
    "done",              # tous les plans validés en final
]

SHOT_STATUSES = [
    "image_todo",        # le storyboard doit écrire le prompt et lancer l'image de travail
    "image_gen",         # génération de l'image de travail en cours
    "image_qc",          # contrôle cohérence personnage par l'agent
    "image_review",      # attend Michael : image de travail
    "hd_todo",           # image validée : passage en haute définition (automatique)
    "hd_gen",            # agrandissement en cours
    "hd_qc",             # l'agent vérifie que la HD est fidèle à l'image validée
    "hd_review",         # écart signalé sur la HD : Michael tranche
    "prompt_todo",       # routeur (fournisseur + modèle) puis prompteur (prompt vidéo)
    "video_review",      # attend Michael : prompt, modèle et coût avant toute dépense vidéo
    "draft_todo",        # plan vidéo validé : brouillon à lancer (automatique)
    "draft_gen",         # brouillon vidéo en cours
    "draft_qc",          # contrôle du brouillon par l'agent
    "draft_review",      # attend Michael : brouillon vidéo
    "final_todo",        # brouillon validé : rendu final à lancer (automatique)
    "final_gen",         # rendu final / upscale en cours
    "lipsync_todo",      # plan chanté : lip-sync à lancer (automatique)
    "lipsync_gen",       # lip-sync en cours
    "final_review",      # attend Michael : final
    "done",              # validé
    "change_requested",  # Michael a demandé une modif, à trier par l'orchestrateur
    "failed",            # erreur à traiter
]

REVIEW_STATUSES = {
    "image_review": "images",
    "hd_review": "hd",
    "video_review": "videoplan",
    "draft_review": "drafts",
    "final_review": "finals",
}

# R-F1 : un responsable unique par statut, celui qui est attendu. Les cas particuliers
# (bloc non validé, dépense en attente, références à vérifier, routeur puis prompteur,
# finition) sont tranchés par production.shot_owner. La régie affiche « En attente de : … ».
STATUS_OWNER = {
    "image_todo": "agent:storyboard",
    "image_gen": "fournisseur",
    "image_qc": "agent:controleur",
    "image_review": "michael",
    "hd_todo": "worker",
    "hd_gen": "fournisseur",
    "hd_qc": "agent:controleur",
    "hd_review": "michael",
    "prompt_todo": "agent:routeur",
    "video_review": "michael",
    "draft_todo": "worker",
    "draft_gen": "fournisseur",
    "draft_qc": "agent:controleur",
    "draft_review": "michael",
    "final_todo": "worker",
    "final_gen": "fournisseur",
    "lipsync_todo": "worker",
    "lipsync_gen": "fournisseur",
    "final_review": "michael",
    "done": "personne",
    "change_requested": "agent:orchestrateur",
    "failed": "agent:orchestrateur",
}
OWNER_LABEL = {
    "michael": "toi",
    "worker": "le worker",
    "fournisseur": "le fournisseur",
    "personne": "personne",
    "agent:orchestrateur": "l'orchestrateur",
    "agent:script-doctor": "le scénariste",
    "agent:storyboard": "le storyboard",
    "agent:controleur": "le contrôleur",
    "agent:routeur": "le routeur",
    "agent:prompteur": "le prompteur",
    "agent:finition": "la finition",
}

# Statuts qui demandent un agent Claude (le worker réveille l'orchestrateur)
AGENT_STATUSES = ("image_todo", "image_qc", "hd_qc", "prompt_todo", "draft_qc", "change_requested", "failed")

# Statuts traités par le worker sans jugement
AUTO_STATUSES = ("hd_todo", "draft_todo", "final_todo", "lipsync_todo")

FRAMINGS = ["ECU", "CU", "MCU", "MS", "MWS", "WS", "EWS"]
MOTIONS = ["static", "low", "medium", "high"]

# source : conversation, transcription ou notes de travail que le script doctor relit en entier
CLIP_FILE_KINDS = ["song", "vocals", "dossier", "lyrics", "reference", "source"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    notes TEXT,
    canon_version INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_versions (
    id INTEGER PRIMARY KEY,
    character_slug TEXT NOT NULL REFERENCES characters(slug),
    version INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validated','archived')),
    dir TEXT NOT NULL,
    notes TEXT,
    instructions TEXT,
    pack_status TEXT NOT NULL DEFAULT 'none',
    created_at TEXT NOT NULL,
    UNIQUE (character_slug, version)
);

CREATE TABLE IF NOT EXISTS character_assets (
    id INTEGER PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES character_versions(id),
    kind TEXT NOT NULL,
    label TEXT,
    path TEXT,
    remote_url TEXT,
    prompt TEXT,
    model_key TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    funding TEXT NOT NULL DEFAULT 'cash',
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('generating','proposed','kept','rejected','failed')),
    error TEXT,
    parent_id INTEGER,
    comment TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS looks (
    id INTEGER PRIMARY KEY,
    character_slug TEXT NOT NULL REFERENCES characters(slug),
    slug TEXT NOT NULL,
    description TEXT,
    dir TEXT NOT NULL,
    UNIQUE (character_slug, slug)
);

CREATE TABLE IF NOT EXISTS groups_ (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS group_members (
    group_slug TEXT NOT NULL REFERENCES groups_(slug),
    character_slug TEXT NOT NULL REFERENCES characters(slug),
    version INTEGER,
    role TEXT,
    PRIMARY KEY (group_slug, character_slug)
);

CREATE TABLE IF NOT EXISTS clips (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    dir TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'script',
    song_path TEXT,
    vocals_path TEXT,
    script_path TEXT,
    bpm REAL,
    duration_s REAL,
    aspect_ratio TEXT NOT NULL DEFAULT '16:9',
    budget_usd REAL,
    pitch TEXT,
    concept TEXT,
    brief_ready INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clip_files (
    id INTEGER PRIMARY KEY,
    clip_slug TEXT NOT NULL REFERENCES clips(slug),
    kind TEXT NOT NULL,
    label TEXT,
    path TEXT NOT NULL,
    text_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY,
    clip_slug TEXT NOT NULL REFERENCES clips(slug),
    num INTEGER NOT NULL,
    name TEXT NOT NULL,
    intention TEXT,
    UNIQUE (clip_slug, num)
);

CREATE TABLE IF NOT EXISTS castings (
    clip_slug TEXT NOT NULL REFERENCES clips(slug),
    character_slug TEXT NOT NULL REFERENCES characters(slug),
    version INTEGER NOT NULL,
    look_slug TEXT,
    PRIMARY KEY (clip_slug, character_slug)
);

CREATE TABLE IF NOT EXISTS shots (
    id INTEGER PRIMARY KEY,
    clip_slug TEXT NOT NULL REFERENCES clips(slug),
    num INTEGER NOT NULL,
    block_id INTEGER,
    section TEXT,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    description TEXT NOT NULL,
    framing TEXT,
    motion TEXT,
    camera TEXT,
    characters TEXT NOT NULL DEFAULT '[]',
    singing INTEGER NOT NULL DEFAULT 0,
    tier TEXT,
    model_key TEXT,
    route_reason TEXT,
    seed INTEGER,
    image_prompt TEXT,
    video_prompt TEXT,
    negative_prompt TEXT,
    status TEXT NOT NULL DEFAULT 'image_todo',
    qc_retries INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (clip_slug, num)
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    shot_id INTEGER NOT NULL REFERENCES shots(id),
    kind TEXT NOT NULL CHECK (kind IN ('image','image_hd','draft','final','lipsync')),
    version INTEGER NOT NULL,
    path TEXT,
    remote_url TEXT,
    prompt TEXT,
    model_key TEXT,
    seed INTEGER,
    params TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    funding TEXT NOT NULL DEFAULT 'cash',
    status TEXT NOT NULL DEFAULT 'generating'
        CHECK (status IN ('generating','ready','validated','rejected','failed','superseded')),
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    target_table TEXT NOT NULL CHECK (target_table IN ('assets','character_assets','element_images')),
    target_id INTEGER NOT NULL,
    endpoint TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'fal',
    request_id TEXT,
    status_url TEXT,
    response_url TEXT,
    output_path TEXT,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    clip_slug TEXT NOT NULL,
    shot_id INTEGER,
    asset_id INTEGER,
    gate TEXT NOT NULL CHECK (gate IN ('decoupage','images','hd','videoplan','drafts','finals','casting')),
    decision TEXT NOT NULL CHECK (decision IN ('approve','change')),
    comment TEXT,
    route TEXT,
    handled INTEGER NOT NULL DEFAULT 0,
    handled_note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    clip_slug TEXT,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Décors, objets clés et figurants d'un clip : des références visuelles validées
-- par Michael, réutilisées à chaque visuel de plan pour garder la cohérence.
CREATE TABLE IF NOT EXISTS elements (
    id INTEGER PRIMARY KEY,
    clip_slug TEXT NOT NULL REFERENCES clips(slug),
    kind TEXT NOT NULL CHECK (kind IN ('decor','objet','figurant')),
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,                 -- la fiche : ce qui ne change jamais
    states TEXT NOT NULL DEFAULT '[]',-- JSON : états du lieu (ex. « jardin vide au retour »)
    dir TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'michael',
    created_at TEXT NOT NULL,
    UNIQUE (clip_slug, slug)
);

CREATE TABLE IF NOT EXISTS element_images (
    id INTEGER PRIMARY KEY,
    element_id INTEGER NOT NULL REFERENCES elements(id),
    state TEXT,                       -- NULL = état de base
    source TEXT NOT NULL DEFAULT 'gen' CHECK (source IN ('michael','gen')),
    path TEXT,
    remote_url TEXT,
    label TEXT,
    prompt TEXT,
    model_key TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    funding TEXT NOT NULL DEFAULT 'cash',
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('generating','proposed','kept','rejected','failed')),
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shot_elements (
    shot_id INTEGER NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    element_id INTEGER NOT NULL REFERENCES elements(id) ON DELETE CASCADE,
    state TEXT,
    PRIMARY KEY (shot_id, element_id)
);

-- Images d'une tenue : les photos de Michael (tenue portée) et la feuille de référence générée.
CREATE TABLE IF NOT EXISTS look_images (
    id INTEGER PRIMARY KEY,
    look_id INTEGER NOT NULL REFERENCES looks(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('photo','sheet')),
    status TEXT NOT NULL CHECK (status IN ('generating','proposed','kept','rejected','failed')),
    path TEXT,
    prompt TEXT,
    model_key TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);

-- Dépenses en attente de l'accord de Michael : rien de payant ne part sans lui.
CREATE TABLE IF NOT EXISTS spend_requests (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,             -- image | image_hd | canon_hd | character_asset
    args TEXT NOT NULL,               -- JSON : arguments pour relancer l'action
    dedupe TEXT NOT NULL,             -- même demande = même clé (pas de doublon)
    label TEXT NOT NULL,
    detail TEXT,
    clip_slug TEXT,
    character_slug TEXT,
    shot_id INTEGER,
    model_key TEXT,
    provider TEXT,
    est_usd REAL NOT NULL DEFAULT 0,
    funding TEXT NOT NULL DEFAULT 'cash',
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | refused | done | failed
    note TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_spend_status ON spend_requests(status);

-- Historique des remarques sur un plan : rien n'écrase le retour de Michael.
CREATE TABLE IF NOT EXISTS shot_notes (
    id INTEGER PRIMARY KEY,
    shot_id INTEGER NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
    author TEXT NOT NULL,             -- michael | controleur | machine | orchestrateur
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shot_notes ON shot_notes(shot_id, id);

CREATE TABLE IF NOT EXISTS notifications (
    key TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY,
    clip_slug TEXT,
    reason TEXT NOT NULL,
    fingerprint TEXT,
    pid INTEGER,
    log_path TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    exit_code INTEGER
);

-- Versions du schéma appliquées à cette base, avec la sauvegarde faite avant (R-G3)
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    backup_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_shots_clip ON shots(clip_slug, num);
CREATE INDEX IF NOT EXISTS idx_assets_shot ON assets(shot_id, kind, version);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_reviews_pending ON reviews(handled, clip_slug);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def age_seconds(stamp: str) -> float:
    """Secondes écoulées depuis un horodatage produit par now()."""
    t = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds()


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or get_settings().db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Amène la base au schéma courant. Rejouable : sans effet si elle y est déjà.

    Une base existante en retard est d'abord sauvegardée dans `backups/` à côté
    du fichier. Puis : schéma de base (idempotent), colonnes ajoutées après coup,
    et les migrations numérotées manquantes, chacune enregistrée dans `schema_version`.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    has_tables = conn.execute("SELECT 1 FROM sqlite_master WHERE name='clips'").fetchone()
    backup = _backup_before_migration(conn, version) if has_tables and version < SCHEMA_VERSION else None
    if has_tables and version < 2:
        _migrate_v2(conn)
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    _widen_jobs_targets(conn)
    conn.execute("INSERT OR IGNORE INTO schema_version (version, applied_at, backup_path) VALUES (?,?,?)",
                 (BASELINE_VERSION, now(), backup if version < BASELINE_VERSION else None))
    for target in range(max(version, BASELINE_VERSION) + 1, SCHEMA_VERSION + 1):
        with tx(conn):
            MIGRATIONS[target](conn)
            conn.execute("INSERT OR REPLACE INTO schema_version (version, applied_at, backup_path) VALUES (?,?,?)",
                         (target, now(), backup))
        conn.execute(f"PRAGMA user_version={target}")
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"La base est au schéma {version}, ce code ne connaît que le {SCHEMA_VERSION} : mets le code à jour")


def _db_file(conn: sqlite3.Connection) -> Path | None:
    for r in conn.execute("PRAGMA database_list"):
        if r[1] == "main":
            return Path(r[2]) if r[2] else None
    return None


def _backup_before_migration(conn: sqlite3.Connection, version: int) -> str | None:
    """Copie à chaud de la base avant une migration : `backups/riot-<date>-v<version>.db`."""
    src = _db_file(conn)
    if src is None:
        return None   # base en mémoire
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{src.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-v{version}.db"
    target = sqlite3.connect(dest)
    with target:
        conn.backup(target)
    target.close()
    return str(dest)


def schema_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Version du schéma, migrations appliquées et sauvegardes présentes (`riot db status`)."""
    src = _db_file(conn)
    backups_dir = src.parent / "backups" if src else None
    saved = sorted(backups_dir.glob("*.db")) if backups_dir and backups_dir.is_dir() else []
    return {
        "base": str(src) if src else None,
        "version": conn.execute("PRAGMA user_version").fetchone()[0],
        "version_code": SCHEMA_VERSION,
        "migrations": rows(conn.execute("SELECT * FROM schema_version ORDER BY version").fetchall()),
        "sauvegardes": [{"fichier": str(p), "octets": p.stat().st_size} for p in saved],
    }


# --- Migrations numérotées (R-G3) : chacune est rejouable sans effet -------------

def _migrate_v5(conn: sqlite3.Connection) -> None:
    """Schéma versionné : la table schema_version existe (créée par SCHEMA). Rien d'autre."""


def _migrate_v6(conn: sqlite3.Connection) -> None:
    """R-A4 : historique des changements, un enregistrement par champ modifié."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY,
            table_name TEXT NOT NULL,
            row_id TEXT NOT NULL,
            field TEXT NOT NULL,
            old TEXT,
            new TEXT,
            author TEXT NOT NULL,       -- michael | agent:<nom> | worker | machine
            reason TEXT,
            created_at TEXT NOT NULL
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_changes_row ON changes(table_name, row_id, id)")


def _migrate_v7(conn: sqlite3.Connection) -> None:
    """R-A2 : suppression logique d'un plan qui a des assets (deleted_at), restaurable."""
    if "deleted_at" not in _columns(conn, "shots"):
        conn.execute("ALTER TABLE shots ADD COLUMN deleted_at TEXT")


def _migrate_v8(conn: sqlite3.Connection) -> None:
    """R-A3 : la baseline de Michael (shots.script, blocks.brief) à part de la version de production."""
    cols = _columns(conn, "shots")
    if "script" not in cols:
        conn.execute("ALTER TABLE shots ADD COLUMN script TEXT")
        conn.execute("UPDATE shots SET script=description")
    if "prod_outdated" not in cols:
        conn.execute("ALTER TABLE shots ADD COLUMN prod_outdated INTEGER NOT NULL DEFAULT 0")
    if "brief" not in _columns(conn, "blocks"):
        conn.execute("ALTER TABLE blocks ADD COLUMN brief TEXT")
        conn.execute("UPDATE blocks SET brief=intention")


def _migrate_v9(conn: sqlite3.Connection) -> None:
    """R-T1, R-T4 : les agents attendent l'accord de Michael ; coût et jetons de chaque passage."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings_kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_queue (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL,            -- clip ou personnage:<slug>
            command TEXT NOT NULL,        -- /prod <clip>, /casting <slug>
            reasons TEXT NOT NULL,        -- JSON
            fingerprint TEXT,
            est_usd REAL,
            status TEXT NOT NULL,         -- pending | approved | refused | launched | obsolete
            decided_by TEXT,
            run_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_queue ON agent_queue(status, key)")
    cols = _columns(conn, "agent_runs")
    for name, decl in (("command_kind", "TEXT"), ("est_usd", "REAL"), ("cost_usd", "REAL"), ("turns", "INTEGER"),
                       ("tokens_in", "INTEGER"), ("tokens_out", "INTEGER"), ("requested_by", "TEXT")):
        if name not in cols:
            conn.execute(f"ALTER TABLE agent_runs ADD COLUMN {name} {decl}")
    conn.execute("UPDATE agent_runs SET command_kind = CASE WHEN clip_slug LIKE 'personnage:%' THEN '/casting' "
                 "ELSE '/prod' END WHERE command_kind IS NULL")


def _run_statements(conn: sqlite3.Connection, script: str) -> None:
    """Exécute un script SQL instruction par instruction (executescript validerait la transaction en cours)."""
    for stmt in script.split(";"):
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            conn.execute(body)


def _migrate_v10(conn: sqlite3.Connection) -> None:
    """R-H1, R-H2 (v3) : séquences, prises, fenêtres, lots d'accord, statut des références par fournisseur."""
    _run_statements(conn, """
        CREATE TABLE IF NOT EXISTS sequences (
            id INTEGER PRIMARY KEY,
            clip_slug TEXT NOT NULL REFERENCES clips(slug),
            num INTEGER NOT NULL,
            name TEXT NOT NULL,
            fiche TEXT,                   -- lieu, heure, lumière, palette, figurants (texte injecté mot pour mot)
            profile TEXT,                 -- NULL = calculé depuis les plans
            offer_key TEXT,               -- NULL = choix du planificateur
            options TEXT NOT NULL DEFAULT '{}',   -- JSON : résolution, mode, références choisies
            master_path TEXT,             -- image maîtresse validée
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (clip_slug, num)
        );
        CREATE TABLE IF NOT EXISTS shoot_lots (
            id INTEGER PRIMARY KEY,
            clip_slug TEXT NOT NULL,
            sequence_id INTEGER,
            total_usd REAL NOT NULL,
            status TEXT NOT NULL,         -- approved | done | partial
            decided_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS takes (
            id INTEGER PRIMARY KEY,
            clip_slug TEXT NOT NULL,
            sequence_id INTEGER,
            lot_id INTEGER,
            offer_key TEXT NOT NULL,
            mode TEXT NOT NULL,           -- references | image_start | text | first_last
            form TEXT NOT NULL,           -- single | multi | continuous
            duration_s REAL NOT NULL,
            resolution TEXT,
            prompt TEXT NOT NULL,
            refs TEXT NOT NULL DEFAULT '[]',
            est_usd REAL NOT NULL DEFAULT 0,
            cost_usd REAL,
            funding TEXT,                 -- free | reserve:<fournisseur> | cash
            status TEXT NOT NULL,         -- queued | submitting | running | done | failed | blocked | check
            idem_key TEXT UNIQUE,
            provider TEXT,
            request_id TEXT,
            status_url TEXT,
            response_url TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            path TEXT,
            error TEXT,
            retries INTEGER NOT NULL DEFAULT 0,
            parent_take_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_takes_seq ON takes(sequence_id, status);
        CREATE TABLE IF NOT EXISTS take_shots (
            take_id INTEGER NOT NULL REFERENCES takes(id),
            shot_id INTEGER NOT NULL REFERENCES shots(id),
            ord INTEGER NOT NULL,
            t_in REAL NOT NULL,           -- fenêtre dans la prise
            t_out REAL NOT NULL,
            speed REAL NOT NULL DEFAULT 1.0,
            kept INTEGER NOT NULL DEFAULT 0,
            verdict TEXT,                 -- keep | redo
            motive TEXT,
            note TEXT,
            decided_at TEXT,
            PRIMARY KEY (take_id, shot_id)
        );
        CREATE TABLE IF NOT EXISTS ref_status (
            path TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL,         -- accepted | refused_in | refused_out
            note TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (path, provider)
        );
    """)
    if "quality" not in _columns(conn, "clips"):
        conn.execute("ALTER TABLE clips ADD COLUMN quality TEXT NOT NULL DEFAULT 'brouillon'")
    cols = _columns(conn, "shots")
    for name, decl in (("sequence_id", "INTEGER"), ("jeu", "TEXT NOT NULL DEFAULT 'present'"),
                       ("axe", "TEXT"), ("composition", "TEXT NOT NULL DEFAULT 'libre'"),
                       ("role_ab", "TEXT NOT NULL DEFAULT 'A'"), ("action_en", "TEXT"), ("action_edited", "INTEGER NOT NULL DEFAULT 0")):
        if name not in cols:
            conn.execute(f"ALTER TABLE shots ADD COLUMN {name} {decl}")
    # Une séquence par bloc pour commencer (Michael la découpe ensuite) ; plans sans personnage : jeu « aucun ».
    for b in conn.execute("SELECT * FROM blocks ORDER BY clip_slug, num").fetchall():
        has = conn.execute("SELECT 1 FROM shots WHERE block_id=? AND sequence_id IS NOT NULL", (b["id"],)).fetchone()
        n_shots = conn.execute("SELECT COUNT(*) FROM shots WHERE block_id=? AND deleted_at IS NULL", (b["id"],)).fetchone()[0]
        if has or not n_shots:
            continue
        num = (conn.execute("SELECT COALESCE(MAX(num),0) FROM sequences WHERE clip_slug=?", (b["clip_slug"],)).fetchone()[0]) + 1
        cur = conn.execute("INSERT INTO sequences (clip_slug, num, name, created_at, updated_at) VALUES (?,?,?,?,?)",
                           (b["clip_slug"], num, b["name"], now(), now()))
        conn.execute("UPDATE shots SET sequence_id=? WHERE block_id=?", (cur.lastrowid, b["id"]))
    conn.execute("UPDATE shots SET jeu='aucun' WHERE characters IN ('[]', '') OR characters IS NULL")
    # Ce que Google a accepté ou refusé lors du test des modes de Veo (11 et 12/11/2026, RAPPORT.md)
    for path, st, note in (
            ("characters/jj/v2/canon.png", "refused_out", "vidéo filtrée en sortie (visage), test Veo du 11/11"),
            ("characters/jj/v2/canon/tshirt-blanc-rousseur.png", "refused_out", "refusée avec la tenue, filtrée seule, test du 11/11"),
            ("characters/jj/v2/details/ancienne-canon-7.png", "accepted", "acceptée en Fast et en Standard, test du 11/11"),
            ("characters/jj/looks/black-tailor/inspiration/11008-2.png", "refused_in", "refusée à l'entrée, test du 11/11"),
            ("clips/nobody-saw/decors/porte-document/inspiration/11005-192213.jpg", "accepted", "acceptée, test du 11/11")):
        conn.execute("INSERT OR IGNORE INTO ref_status (path, provider, status, note, updated_at) VALUES (?,?,?,?,?)",
                     (path, "vertex", st, note, now()))


MIGRATIONS = {
    5: _migrate_v5,
    6: _migrate_v6,
    7: _migrate_v7,
    8: _migrate_v8,
    9: _migrate_v9,
    10: _migrate_v10,
}


# Colonnes ajoutées après coup : ajoutées si elles manquent (sans effet sinon).
LATER_COLUMNS = {
    "jobs": [("provider", "TEXT NOT NULL DEFAULT 'fal'")],
    "assets": [("funding", "TEXT NOT NULL DEFAULT 'cash'")],
    "character_assets": [("funding", "TEXT NOT NULL DEFAULT 'cash'")],
    "clips": [("decors_status", "TEXT NOT NULL DEFAULT 'todo'"),   # todo | requested | done
              ("scenario_status", "TEXT NOT NULL DEFAULT 'none'"),  # none | requested | proposed
              # mémoire de réalisation (script/memoire.md) : none | requested (le script doctor relit les sources)
              ("memoire_status", "TEXT NOT NULL DEFAULT 'none'"),
              ("memoire_sources", "TEXT"),   # ids (JSON) des sources déjà lues par le script doctor
              ("da", "TEXT"),    # direction artistique écrite par Michael : fait foi sur tout le reste
              ("style_image", "TEXT"),   # style photo ajouté à chaque prompt d'image (vide : style par défaut)
              ("visual_hd", "INTEGER NOT NULL DEFAULT 0")],   # 1 : visuel HD avant la vidéo ; 0 : le visuel validé suffit
    # detail : le prompt détaillé du plan (description courte = `description`)
    # detail_edited : 1 quand Michael l'a modifié à la main (les agents ne le réécrivent plus)
    # failed_step : l'étape qui a échoué, pour relancer au bon endroit
    "shots": [("detail", "TEXT"), ("detail_edited", "INTEGER NOT NULL DEFAULT 0"), ("failed_step", "TEXT"),
              ("lipsync_key", "TEXT"),    # lip-sync choisi par Michael pour ce plan
              ("cut_ok", "INTEGER NOT NULL DEFAULT 0"),   # plan validé par Michael dans le découpage
              ("looks", "TEXT"),    # tenue de chaque personnage dans ce plan (JSON {personnage: tenue}), par @
              ("refs_ok", "INTEGER NOT NULL DEFAULT 0"),   # Michael confirme : pas de référence @ voulue
              ("looks_manual", "INTEGER NOT NULL DEFAULT 0")],   # tenue posée sans @ (scripte, panneau) : gardée
    # looks : clip_slug = le clip pour lequel la tenue a été créée (vide : tenue signature du personnage)
    "looks": [("clip_slug", "TEXT"), ("name", "TEXT")],
    "blocks": [("look", "TEXT"),   # lumière et étalonnage communs aux plans du bloc
               ("validated", "INTEGER NOT NULL DEFAULT 0"),   # bloc validé par Michael : ses plans sont en production
               ("refs_checked", "INTEGER NOT NULL DEFAULT 1")],   # 0 : le scripte vérifie les références avant les visuels
    # prompt : le prompt de l'image HD, réécrit par Michael (NULL = prompt par défaut)
    # prompt_agent : le prompt écrit par le décorateur d'après l'image de départ de Michael
    # prompt_status : requested quand une image de départ attend d'être regardée par le décorateur
    # brief : ce que Michael veut tirer de ses images d'inspiration (texte des brouillons)
    # canon_status : requested (le directeur de casting prépare l'étape suivante de la canon), review (Michael choisit)
    # canon_model : modèle d'image choisi par Michael pour préparer la canon
    "character_versions": [("canon_status", "TEXT NOT NULL DEFAULT 'none'"), ("canon_model", "TEXT")],
    # manual : 0 = né d'un @ du texte (suit le texte), 1 = ajouté à la main, 2 = posé par le décorateur
    "shot_elements": [("manual", "INTEGER NOT NULL DEFAULT 0")],
    "elements": [("prompt", "TEXT"), ("prompt_agent", "TEXT"), ("prompt_status", "TEXT NOT NULL DEFAULT 'none'"),
                 ("brief", "TEXT")],
    # role : inspi = image d'inspiration (trouvée par Michael), draft = image de départ (déposée, ou brouillon
    # généré puis gardé), hd = référence des visuels de plan
    "element_images": [("role", "TEXT NOT NULL DEFAULT 'hd'"),
                       ("from_ids", "TEXT")],   # brouillon : ids (JSON) des images de Michael qui ont servi
}


def _widen_jobs_targets(conn: sqlite3.Connection) -> None:
    """Bases créées avant les décors : la contrainte de jobs.target_table est élargie."""
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()
    if not sql or "element_images" in sql[0]:
        return
    cols = ", ".join(sorted(_columns(conn, "jobs")))
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN")
    conn.execute("ALTER TABLE jobs RENAME TO jobs_old")
    create = "CREATE TABLE IF NOT EXISTS jobs" + SCHEMA.split("CREATE TABLE IF NOT EXISTS jobs", 1)[1].split(");", 1)[0] + ")"
    conn.execute(create)
    conn.execute(f"INSERT INTO jobs ({cols}) SELECT {cols} FROM jobs_old")
    conn.execute("DROP TABLE jobs_old")
    conn.execute("COMMIT")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)   # index de jobs recréés


def _ensure_columns(conn: sqlite3.Connection) -> None:
    for table, cols in LATER_COLUMNS.items():
        have = _columns(conn, table)
        for name, decl in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _rebuild(conn: sqlite3.Connection, table: str, old: str, new: str) -> None:
    """Remplace une contrainte CHECK en recréant la table (SQLite ne sait pas la modifier)."""
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
    if new in sql:
        return
    cols = ", ".join(_columns(conn, table))
    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
    conn.execute(sql.replace(old, new))
    conn.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {table}_old")
    conn.execute(f"DROP TABLE {table}_old")


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """Passage au schéma 2 : blocs, dossier du clip, image HD, plan vidéo, canon HD."""
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        add = {
            "clips": [("pitch", "TEXT"), ("concept", "TEXT"), ("brief_ready", "INTEGER NOT NULL DEFAULT 0")],
            "shots": [("block_id", "INTEGER"), ("route_reason", "TEXT")],
            "character_versions": [("instructions", "TEXT"), ("pack_status", "TEXT NOT NULL DEFAULT 'none'")],
            "character_assets": [("parent_id", "INTEGER"), ("comment", "TEXT")],
        }
        for table, cols in add.items():
            have = _columns(conn, table)
            for name, decl in cols:
                if name not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        _rebuild(conn, "assets", "('image','draft','final','lipsync')", "('image','image_hd','draft','final','lipsync')")
        _rebuild(conn, "reviews", "('decoupage','images','drafts','finals','casting')",
                 "('decoupage','images','hd','videoplan','drafts','finals','casting')")
        # Un clip existant déjà découpé a forcément été envoyé au script doctor
        conn.execute("UPDATE clips SET brief_ready=1 WHERE script_path IS NOT NULL")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    if "characters" in d and isinstance(d["characters"], str):
        try:
            d["characters"] = json.loads(d["characters"])
        except json.JSONDecodeError:
            d["characters"] = []
    if "params" in d and isinstance(d["params"], str):
        try:
            d["params"] = json.loads(d["params"])
        except json.JSONDecodeError:
            pass
    return d


def rows(rs: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row(r) for r in rs]  # type: ignore[misc]


def log_event(conn: sqlite3.Connection, clip_slug: str | None, kind: str, message: str) -> None:
    conn.execute(
        "INSERT INTO events (clip_slug, kind, message, created_at) VALUES (?,?,?,?)",
        (clip_slug, kind, message, now()),
    )


# --- Accès courants --------------------------------------------------------

def add_note(conn: sqlite3.Connection, shot_id: int, author: str, text: str) -> None:
    """Ajoute une remarque à l'historique du plan (sans effacer les précédentes)."""
    if text and text.strip():
        conn.execute("INSERT INTO shot_notes (shot_id, author, text, created_at) VALUES (?,?,?,?)",
                     (shot_id, author, text.strip()[:2000], now()))


def shot_notes(conn: sqlite3.Connection, shot_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return rows(conn.execute("SELECT author, text, created_at FROM shot_notes WHERE shot_id=? ORDER BY id DESC LIMIT ?",
                             (shot_id, limit)).fetchall())


def get_clip(conn: sqlite3.Connection, slug: str) -> dict[str, Any]:
    clip = row(conn.execute("SELECT * FROM clips WHERE slug=?", (slug,)).fetchone())
    if clip is None:
        raise LookupError(f"Clip inconnu : {slug}")
    return clip


def get_shot(conn: sqlite3.Connection, shot_id: int) -> dict[str, Any]:
    shot = row(conn.execute("SELECT * FROM shots WHERE id=?", (shot_id,)).fetchone())
    if shot is None:
        raise LookupError(f"Plan inconnu : {shot_id}")
    return shot


LIVE = "deleted_at IS NULL"   # plans présents dans le découpage (R-A2 : un plan retiré avec assets reste en base)


def set_shot_status(conn: sqlite3.Connection, shot_id: int, status: str, by: str | None = None,
                    reason: str | None = None) -> None:
    if status not in SHOT_STATUSES:
        raise ValueError(f"Statut de plan invalide : {status}")
    update(conn, "shots", shot_id, {"status": status}, by=by, reason=reason)


# --- Historique des changements (R-A4) -----------------------------------------
#
# Les tables suivies ne s'écrivent que par `update` (ou `update_where`) : chaque
# champ modifié donne une ligne dans `changes` (avant, après, auteur, raison).
# Un test lit le code source et refuse tout `UPDATE` direct sur ces tables hors de ce module.

TRACKED = ("clips", "blocks", "shots", "characters", "character_versions", "elements", "sequences")
_KEYS = {"clips": "slug", "characters": "slug"}
_ACTOR = "machine"


def set_actor(name: str) -> None:
    """Qui écrit dans ce processus : michael (régie), worker, agent:<nom> (CLI)."""
    global _ACTOR
    _ACTOR = name


def actor() -> str:
    return _ACTOR


def _same(a: Any, b: Any) -> bool:
    if a == b:
        return True
    if a is None or b is None:
        return False
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def _text(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def update(conn: sqlite3.Connection, table: str, key: Any, fields: dict[str, Any], *,
           by: str | None = None, reason: str | None = None) -> dict[str, Any]:
    """Écrit les champs qui changent et journalise chacun. Retourne les champs réellement modifiés."""
    if table not in TRACKED:
        raise ValueError(f"Table non suivie : {table}")
    pk = _KEYS.get(table, "id")
    cur = conn.execute(f"SELECT * FROM {table} WHERE {pk}=?", (key,)).fetchone()
    if cur is None:
        raise LookupError(f"{table} {key} : inconnu")
    cols = cur.keys()
    changed: dict[str, Any] = {}
    for k, v in fields.items():
        if k not in cols:
            raise ValueError(f"{table}.{k} : colonne inconnue")
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        if not _same(cur[k], v):
            changed[k] = v
    if not changed:
        return {}
    sets = [f"{k}=?" for k in changed]
    params: list[Any] = list(changed.values())
    if "updated_at" in cols and "updated_at" not in changed:
        sets.append("updated_at=?")
        params.append(now())
    conn.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE {pk}=?", (*params, key))
    stamp = now()
    conn.executemany(
        "INSERT INTO changes (table_name, row_id, field, old, new, author, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
        [(table, str(key), k, _text(cur[k]), _text(v), by or _ACTOR, reason, stamp)
         for k, v in changed.items() if k != "updated_at"])
    return changed


def update_where(conn: sqlite3.Connection, table: str, where: str, params: tuple, fields: dict[str, Any], *,
                 by: str | None = None, reason: str | None = None) -> int:
    """Même chose pour toutes les lignes d'une condition. Retourne le nombre de lignes modifiées."""
    pk = _KEYS.get(table, "id")
    keys = [r[0] for r in conn.execute(f"SELECT {pk} FROM {table} WHERE {where}", params).fetchall()]
    return sum(1 for k in keys if update(conn, table, k, fields, by=by, reason=reason))


def free_numbers(conn: sqlite3.Connection, table: str, clip_slug: str) -> None:
    """Étape transitoire d'une renumérotation (num unique par clip) : pas un changement, pas journalisée."""
    assert table in ("shots", "blocks")
    conn.execute(f"UPDATE {table} SET num=-id WHERE clip_slug=?", (clip_slug,))


def renumber(conn: sqlite3.Connection, table: str, row_id: int, num: int, old_num: int | None,
             by: str | None = None) -> None:
    """Pose le numéro final après `free_numbers` ; journalisé seulement s'il a changé."""
    assert table in ("shots", "blocks")
    conn.execute(f"UPDATE {table} SET num=? WHERE id=?", (num, row_id))
    if old_num is not None and old_num != num:
        conn.execute("INSERT INTO changes (table_name, row_id, field, old, new, author, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
                     (table, str(row_id), "num", str(old_num), str(num), by or _ACTOR, "renuméroté", now()))


def touch(conn: sqlite3.Connection, table: str, key: Any) -> None:
    """Met à jour updated_at seul (une pièce jointe, un fichier) : pas un changement de champ."""
    pk = _KEYS.get(table, "id")
    conn.execute(f"UPDATE {table} SET updated_at=? WHERE {pk}=?", (now(), key))


def history(conn: sqlite3.Connection, table: str, key: Any, limit: int = 200) -> list[dict[str, Any]]:
    """Les changements d'un objet, du plus récent au plus ancien."""
    return rows(conn.execute("SELECT * FROM changes WHERE table_name=? AND row_id=? ORDER BY id DESC LIMIT ?",
                             (table, str(key), limit)).fetchall())


def latest_asset(conn: sqlite3.Connection, shot_id: int, kind: str) -> dict[str, Any] | None:
    return row(
        conn.execute(
            "SELECT * FROM assets WHERE shot_id=? AND kind=? AND status!='superseded' "
            "ORDER BY version DESC LIMIT 1",
            (shot_id, kind),
        ).fetchone()
    )


def next_asset_version(conn: sqlite3.Connection, shot_id: int, kind: str) -> int:
    r = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM assets WHERE shot_id=? AND kind=?",
        (shot_id, kind),
    ).fetchone()
    return int(r[0])


def clip_cost(conn: sqlite3.Connection, slug: str, funding: str = "cash") -> float:
    """Dépense d'un clip : en argent ('cash', ce qui compte pour le budget) ou en crédits ('credits')."""
    r = conn.execute(
        "SELECT COALESCE(SUM(a.cost_usd),0) FROM assets a JOIN shots s ON s.id=a.shot_id "
        "WHERE s.clip_slug=? AND a.funding=?",
        (slug, funding),
    ).fetchone()
    return float(r[0])


def casting_for_clip(conn: sqlite3.Connection, slug: str) -> list[dict[str, Any]]:
    return rows(
        conn.execute(
            "SELECT c.*, cv.dir AS version_dir, cv.status AS version_status, ch.name "
            "FROM castings c "
            "JOIN characters ch ON ch.slug=c.character_slug "
            "JOIN character_versions cv ON cv.character_slug=c.character_slug AND cv.version=c.version "
            "WHERE c.clip_slug=?",
            (slug,),
        ).fetchall()
    )
