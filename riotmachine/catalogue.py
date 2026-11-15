"""Le catalogue des offres vidéo (PRODUCTION-PLANS-v3 §6, R-H3).

Une offre = un modèle chez un fournisseur, avec ses prix (config/models.yaml) et
ses capacités (config/capacites.yaml). Ce module ne contient aucune règle propre
à un modèle : il lit les deux fichiers et répond aux questions du planificateur.

Les réserves (R-H9) sont les enveloppes de crédits déclarées dans models.yaml
(`providers.<p>.credits`) : solde = enveloppe − dépenses rangées en base − ce qui
a été consommé hors régie (réglage `reserve_offset:<fournisseur>`).
"""

from __future__ import annotations

import sqlite3
from datetime import date
from functools import lru_cache
from typing import Any

import yaml

from . import credits, routing
from .settings import get_settings, load_models

# Profils, du moins au plus exigeant (PRODUCTION-PLANS-v3 §7)
PROFILE_ORDER = ["decor", "action", "multi_personnages", "composition_stricte", "jeu", "chant_serre", "chant_danse_large"]
PROFILE_LABEL = {"decor": "décor", "action": "action", "multi_personnages": "plusieurs personnages",
                 "composition_stricte": "composition stricte", "jeu": "jeu d'acteur", "chant_serre": "chant serré",
                 "chant_danse_large": "chant et danse en large"}
# Profils qui exigent des références de personnage
NEEDS_REFS = {"action", "multi_personnages", "jeu", "chant_serre", "chant_danse_large"}
MODE_LABEL = {"references": "à partir des références", "image_start": "image de départ", "text": "texte seul",
              "first_last": "première et dernière image"}
FUNDING_RANK = {"free": 0, "reserve": 1, "cash": 2}


@lru_cache(maxsize=1)
def capacities() -> dict:
    path = get_settings().repo_root / "config" / "capacites.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def reset() -> None:
    capacities.cache_clear()


def cfg_defaults() -> dict:
    return capacities().get("defaults") or {}


def _caps(key: str, m: dict) -> dict:
    """Capacités déclarées, ou capacités minimales déduites de models.yaml (image de départ seule)."""
    c = (capacities().get("models") or {}).get(key)
    if c:
        return c
    durs = m.get("durations") or []
    return {"modes": {"image_start": {"durations": durs}}, "profiles": {}, "prompt_dialect": "generic",
            "source": "déduit de models.yaml, capacités non déclarées"}


def prices(m: dict) -> dict[str, float]:
    """Prix à la seconde par résolution. Un prix unique (sans résolution) vaut pour la résolution par défaut."""
    ps = (m.get("price") or {}).get("per_second")
    if isinstance(ps, (int, float)):
        res = (m.get("draft_params") or {}).get("resolution") or "720p"
        return {str(res): float(ps)}
    return {str(k): float(v) for k, v in (ps or {}).items()}


def _res_key(r: str) -> int:
    try:
        return int(str(r).rstrip("p"))
    except ValueError:
        return 0


def offers() -> list[dict[str, Any]]:
    """Toutes les offres vidéo, branchées ou non, avec prix et capacités."""
    usable = {p["key"]: p["usable"] for p in routing.providers()}
    provs = load_models().get("providers") or {}
    out = []
    stale = int(cfg_defaults().get("stale_days", 45))
    for key, m in (load_models().get("models") or {}).items():
        if m.get("kind") != "video" or not prices(m):
            continue
        caps = _caps(key, m)
        verified = caps.get("verified_at")
        age = (date.today() - date.fromisoformat(str(verified))).days if verified else None
        out.append({
            "key": key, "label": m.get("label", key), "provider": m.get("provider", "fal"),
            "provider_label": (provs.get(m.get("provider", "fal")) or {}).get("label", m.get("provider")),
            "usable": bool(usable.get(m.get("provider", "fal"))),
            "prices": prices(m), "resolutions": sorted(prices(m), key=_res_key),
            "modes": caps.get("modes") or {}, "multi_shot": caps.get("multi_shot"),
            "profiles": caps.get("profiles") or {}, "dialect": caps.get("prompt_dialect", "generic"),
            "refusals_billed": bool(caps.get("refusals_billed", True)),
            "extend": bool(caps.get("extend")), "continue_from_frame": bool(caps.get("continue_from_frame")),
            "edit_object": bool(caps.get("edit_object")),
            "verified_at": str(verified) if verified else None, "stale": age is None or age > stale,
            "source": caps.get("source", ""),
        })
    return out


def offer(key: str) -> dict[str, Any]:
    for o in offers():
        if o["key"] == key:
            return o
    raise LookupError(f"Offre inconnue : {key}")


def profile_note(o: dict, profile: str) -> str:
    """ok | weak | no | unknown"""
    return str(o["profiles"].get(profile, "unknown")).lower() if o["profiles"] else "unknown"


def max_duration(o: dict, mode: str) -> float:
    durs = (o["modes"].get(mode) or {}).get("durations") or []
    return float(max(durs)) if durs else 0.0


def fit_duration(o: dict, mode: str, seconds: float) -> float | None:
    """Plus petite durée permise qui couvre `seconds` (None si aucune)."""
    for d in sorted((o["modes"].get(mode) or {}).get("durations") or []):
        if d + 1e-6 >= seconds:
            return float(d)
    return None


def resolution_for(o: dict, quality: str, wanted: str | None = None) -> str:
    if wanted and wanted in o["prices"]:
        return wanted
    rule = (cfg_defaults().get("quality_resolution") or {}).get(quality or "brouillon", "lowest")
    res = o["resolutions"]
    return res[-1] if rule == "highest" else res[0]


# --- réserves (R-H9) ------------------------------------------------------------------

def reserves(conn: sqlite3.Connection) -> dict[str, dict]:
    """Solde de chaque enveloppe de crédits, par fournisseur."""
    out = {}
    for prov, st in credits.status(conn).items():
        takes = conn.execute("SELECT COALESCE(SUM(COALESCE(cost_usd, est_usd)),0) FROM takes WHERE funding=? "
                             "AND status IN ('queued','running','done')", (f"reserve:{prov}",)).fetchone()[0]
        off = conn.execute("SELECT value FROM settings_kv WHERE key=?", (f"reserve_offset:{prov}",)).fetchone()
        offset = float(off[0]) if off else 0.0
        remaining = round(st["usd"] - st["spent"] - float(takes) - offset, 2)
        days = (date.fromisoformat(st["expires"]) - date.today()).days if st.get("expires") else None
        out[prov] = {"provider": prov, "label": st["label"], "total": st["usd"], "remaining": max(0.0, remaining),
                     "expires": st.get("expires"), "expires_soon": days is not None and days < 15,
                     "outside_usd": offset}
    return out


def funding_for(o: dict, cost: float, reserves_: dict[str, dict]) -> tuple[str, str]:
    """(source, libellé) : gratuit, réserve détenue, ou paiement direct."""
    if cost <= 0:
        return "free", "gratuit"
    r = reserves_.get(o["provider"])
    if r and r["remaining"] >= cost:
        return f"reserve:{o['provider']}", r["label"]
    return "cash", "paiement direct"


def funding_rank(source: str) -> int:
    return FUNDING_RANK["reserve" if source.startswith("reserve") else source]
