"""Crédits gratuits ou prépayés chez les fournisseurs (ex. les 300 $ de l'essai Google Cloud).

Chaque fournisseur de config/models.yaml peut déclarer une enveloppe :

    providers:
      google:
        credits: {label: "Essai Google Cloud", usd: 300, start: 2026-10-23, expires: 2027-01-21}

Une génération payée par l'enveloppe est marquée `funding='credits'` : elle ne
compte pas dans le budget en argent du clip. Tant qu'il reste du crédit, le
routage considère que l'offre coûte 0 $ et la met en tête, si elle est adaptée au plan.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from . import db
from .settings import load_models


def _envelope(provider: str) -> dict[str, Any] | None:
    cfg = (load_models().get("providers") or {}).get(provider) or {}
    env = cfg.get("credits")
    if not env or not float(env.get("usd") or 0):
        return None
    today = date.today().isoformat()
    if env.get("start") and str(env["start"]) > today:
        return None
    if env.get("expires") and str(env["expires"]) < today:
        return None
    return env


def _model_keys(provider: str) -> list[str]:
    return [k for k, m in load_models()["models"].items() if m.get("provider", "fal") == provider]


def spent(conn: sqlite3.Connection, provider: str) -> float:
    keys = _model_keys(provider)
    if not keys:
        return 0.0
    marks = ",".join("?" * len(keys))
    total = 0.0
    for table in ("assets", "character_assets"):
        r = conn.execute(f"SELECT COALESCE(SUM(cost_usd),0) FROM {table} WHERE funding='credits' "
                         f"AND model_key IN ({marks})", keys).fetchone()
        total += float(r[0])
    return round(total, 4)


def status(conn: sqlite3.Connection | None = None) -> dict[str, dict[str, Any]]:
    """Enveloppes actives : total, dépensé, reste, échéance."""
    own = conn is None
    conn = conn or db.connect()
    try:
        out = {}
        for provider in (load_models().get("providers") or {}):
            env = _envelope(provider)
            if not env:
                continue
            used = spent(conn, provider)
            out[provider] = {"label": env.get("label", "Crédits"), "usd": float(env["usd"]), "spent": used,
                             "remaining": round(max(0.0, float(env["usd"]) - used), 2),
                             "expires": str(env.get("expires") or "")}
        return out
    finally:
        if own:
            conn.close()


def funding_for(conn: sqlite3.Connection, provider: str, cost: float) -> str:
    """'credits' si l'enveloppe du fournisseur couvre ce coût, sinon 'cash'."""
    st = status(conn).get(provider)
    return "credits" if st and st["remaining"] >= cost else "cash"
