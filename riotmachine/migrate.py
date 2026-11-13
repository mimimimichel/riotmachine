"""Migrations numérotées et rejouables (R-G3).

Chaque fichier `migrations/NNNN_nom.sql` est appliqué une seule fois, dans une
transaction. Avant d'appliquer quoi que ce soit à une base qui contient déjà des
tables, une copie est faite dans `backups/` à côté de la base. Une migration
ne supprime jamais de données : pas de DROP ni de DELETE (vérifié par un test).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .db import now
from .errors import RiotError

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

_TABLE = """CREATE TABLE IF NOT EXISTS schema_migrations (
    num INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    backup_path TEXT
)"""


@dataclass(frozen=True)
class Migration:
    num: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()[:16]


def available(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    out = []
    for f in sorted(directory.glob("*.sql")):
        m = _NAME.match(f.name)
        if not m:
            raise RiotError(f"Migration mal nommée : {f.name} (attendu NNNN_nom.sql)")
        out.append(Migration(int(m.group(1)), m.group(2), f.read_text(encoding="utf-8")))
    nums = [m.num for m in out]
    if len(set(nums)) != len(nums):
        raise RiotError("Deux migrations portent le même numéro : renumérote la plus récente")
    return out


def _db_file(conn: sqlite3.Connection) -> Path | None:
    for r in conn.execute("PRAGMA database_list"):
        if r[1] == "main" and r[2]:
            return Path(r[2])
    return None


def _has_data_tables(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT IN ('schema_migrations') "
        "AND name NOT LIKE 'sqlite_%' LIMIT 1").fetchone() is not None


def backup(conn: sqlite3.Connection, label: str) -> Path | None:
    """Copie à chaud de la base dans backups/ (API de sauvegarde SQLite)."""
    src = _db_file(conn)
    if src is None:
        return None
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = now().replace(":", "").replace("-", "").replace(".", "")
    dest = dest_dir / f"{src.stem}-{stamp}-{label}.db"
    target = sqlite3.connect(dest)
    try:
        conn.backup(target)
    finally:
        target.close()
    return dest


def applied(conn: sqlite3.Connection) -> dict[int, str]:
    conn.execute(_TABLE)
    return {r[0]: r[1] for r in conn.execute("SELECT num, checksum FROM schema_migrations")}


def migrate(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> dict:
    """Applique les migrations en attente. Rejouable : sans migration en attente, ne fait rien."""
    done = applied(conn)
    todo = []
    for m in available(directory):
        if m.num in done:
            if done[m.num] != m.checksum:
                raise RiotError(f"La migration {m.num:04d} a été modifiée après avoir été appliquée. "
                                "Ne modifie jamais une migration appliquée : écris-en une nouvelle.")
            continue
        todo.append(m)
    if not todo:
        return {"applied": [], "backup": None}
    saved = backup(conn, f"avant-{todo[0].num:04d}") if _has_data_tables(conn) else None
    for m in todo:
        try:
            conn.executescript(f"BEGIN IMMEDIATE;\n{m.sql}\n;")
            conn.execute("INSERT INTO schema_migrations (num, name, checksum, applied_at, backup_path) "
                         "VALUES (?,?,?,?,?)", (m.num, m.name, m.checksum, now(), str(saved) if saved else None))
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise RiotError(f"La migration {m.num:04d} ({m.name}) a échoué : {exc}. La base est restée "
                            f"dans son état d'avant{' ; copie de sauvegarde : ' + str(saved) if saved else ''}.") from exc
    return {"applied": [m.num for m in todo], "backup": str(saved) if saved else None}
