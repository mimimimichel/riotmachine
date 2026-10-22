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

SCHEMA_VERSION = 4

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

# Statuts qui demandent un agent Claude (le worker réveille l'orchestrateur)
AGENT_STATUSES = ("image_todo", "image_qc", "hd_qc", "prompt_todo", "draft_qc", "change_requested", "failed")

# Statuts traités par le worker sans jugement
AUTO_STATUSES = ("hd_todo", "draft_todo", "final_todo", "lipsync_todo")

FRAMINGS = ["ECU", "CU", "MCU", "MS", "MWS", "WS", "EWS"]
MOTIONS = ["static", "low", "medium", "high"]

CLIP_FILE_KINDS = ["song", "vocals", "dossier", "lyrics", "reference"]

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
    target_table TEXT NOT NULL CHECK (target_table IN ('assets','character_assets')),
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
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    has_tables = conn.execute("SELECT 1 FROM sqlite_master WHERE name='clips'").fetchone()
    if has_tables and version < 2:
        _migrate_v2(conn)
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


# Colonnes ajoutées après coup : ajoutées si elles manquent (sans effet sinon).
LATER_COLUMNS = {
    "jobs": [("provider", "TEXT NOT NULL DEFAULT 'fal'")],
    "assets": [("funding", "TEXT NOT NULL DEFAULT 'cash'")],
    "character_assets": [("funding", "TEXT NOT NULL DEFAULT 'cash'")],
}


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


def set_shot_status(conn: sqlite3.Connection, shot_id: int, status: str) -> None:
    if status not in SHOT_STATUSES:
        raise ValueError(f"Statut de plan invalide : {status}")
    conn.execute("UPDATE shots SET status=?, updated_at=? WHERE id=?", (status, now(), shot_id))


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
