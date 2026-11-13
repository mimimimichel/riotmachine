"""Connexion SQLite. Toute écriture de données passe par `store` (R-A4)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import settings


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else settings.db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def open_db(path: Path | str | None = None) -> sqlite3.Connection:
    """Connexion à une base à jour : les migrations en attente sont appliquées (R-G3)."""
    from . import migrate
    conn = connect(path)
    migrate.migrate(conn)
    return conn
