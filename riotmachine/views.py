"""Lectures. Toutes les vues lisent les mêmes lignes (R-A1) : aucune copie d'un plan."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import store
from .errors import RiotError


def _rows(cur) -> list[dict[str, Any]]:
    return [dict(r) for r in cur]


def clip_id(conn: sqlite3.Connection, slug: str) -> int:
    r = conn.execute("SELECT id FROM clips WHERE slug=?", (slug,)).fetchone()
    if r is None:
        raise RiotError(f"Clip inconnu : {slug}")
    return r["id"]


def decoupage(conn: sqlite3.Connection, clip: int) -> list[dict[str, Any]]:
    """Les blocs du clip, chacun avec ses plans, hors éléments retirés."""
    blocks = _rows(conn.execute("SELECT * FROM blocks WHERE clip_id=? AND deleted_at IS NULL ORDER BY num", (clip,)))
    shots = _rows(conn.execute("SELECT * FROM shots WHERE clip_id=? AND deleted_at IS NULL ORDER BY num", (clip,)))
    for b in blocks:
        b["shots"] = [s for s in shots if s["block_id"] == b["id"]]
    return blocks


def shot_page(conn: sqlite3.Connection, shot_id: int) -> dict[str, Any]:
    """La page d'un plan : le plan, son bloc, le brief du clip, ses retours, son historique."""
    s = conn.execute("SELECT * FROM shots WHERE id=?", (shot_id,)).fetchone()
    if s is None:
        raise RiotError(f"Plan {shot_id} introuvable.")
    shot = dict(s)
    block = conn.execute("SELECT * FROM blocks WHERE id=?", (shot["block_id"],)).fetchone()
    clip = conn.execute("SELECT id, slug, title, brief FROM clips WHERE id=?", (shot["clip_id"],)).fetchone()
    return {
        "shot": shot,
        "block": dict(block) if block else None,
        "clip": dict(clip),
        "feedback": _rows(conn.execute(
            "SELECT * FROM feedback WHERE object_type='shots' AND object_id=? AND deleted_at IS NULL ORDER BY id",
            (shot_id,))),
        "generations": _rows(conn.execute(
            "SELECT * FROM generations WHERE object_type='shots' AND object_id=? ORDER BY id", (shot_id,))),
        "history": store.history(conn, "shots", shot_id),
    }
