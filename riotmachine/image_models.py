"""Modèles d'image : catalogue, recommandation par tâche, et lancement sur le modèle choisi.

Michael choisit le modèle à chaque génération. La régie présélectionne le premier modèle
branché de la recommandation (config/models.yaml, `recommandations`). Le modèle choisi est
le seul essayé : s'il échoue, l'erreur s'affiche telle quelle, sans repli silencieux.

Identifiants : `fournisseur:modèle` pour les gratuits (ex. cloudflare:klein-9b), la clé de
config/models.yaml pour les payants (ex. nano-banana-pro).
"""

from __future__ import annotations

from pathlib import Path

from . import routing

TASKS = {
    "visuel": "Visuel d'un plan",
    "feuille_tenue": "Feuille de référence d'une tenue",
    "personnage": "Personnage (canon, pack)",
    "decor": "Décor",
    "objet": "Objet",
    "figurant": "Figurant",
}


class ModelError(Exception):
    pass


def is_free(model_id: str) -> bool:
    return ":" in (model_id or "")


def _free_cfg() -> dict:
    return routing.models_cfg().get("images_gratuites") or {}


def catalog() -> list[dict]:
    """Tous les modèles d'image proposables, gratuits puis payants (jamais Vertex : crédits réservés à la vidéo)."""
    out = []
    for mid, c in _free_cfg().items():
        provider = mid.split(":")[0]
        out.append({"id": mid, "label": c.get("label", mid), "free": True, "provider": provider,
                    "usable": routing.provider_usable(provider), "cost_usd": 0.0, "refs": int(c.get("refs", 1)),
                    "forces": c.get("forces", ""), "limites": c.get("limites", ""), "vitesse": c.get("vitesse", "")})
    for key, m in (routing.models_cfg().get("models") or {}).items():
        if m.get("kind") != "image" or m.get("provider") == "vertex":
            continue
        out.append({"id": key, "label": m.get("label", key), "free": False, "provider": m.get("provider", "fal"),
                    "usable": routing.provider_usable(m.get("provider", "fal")),
                    "cost_usd": round(routing.estimate_cost(m, mode="draft"), 3), "refs": int(m.get("max_refs", 1)),
                    "forces": m.get("forces", ""), "limites": m.get("limites", ""), "vitesse": ""})
    return out


def options(task: str) -> dict:
    """Les modèles pour une tâche : conseillés d'abord (avec la raison), puis les autres ; le défaut est le
    premier conseillé qui est branché."""
    reco = (routing.models_cfg().get("recommandations") or {}).get(task) or []
    by_id = {m["id"]: m for m in catalog()}
    out, seen = [], set()
    for rank, (mid, why) in enumerate(reco, 1):
        if mid in by_id:
            out.append({**by_id[mid], "rank": rank, "why": why})
            seen.add(mid)
    for m in by_id.values():
        if m["id"] not in seen:
            out.append({**m, "rank": None, "why": "Pas conseillé pour ça. " + (m["limites"] or "")})
    default = next((m["id"] for m in out if m["rank"] and m["usable"]), None) or \
        next((m["id"] for m in out if m["usable"]), None)
    return {"task": task, "label": TASKS.get(task, task), "default": default, "models": out}


def default(task: str) -> str | None:
    return options(task)["default"]


def get(model_id: str) -> dict:
    m = next((x for x in catalog() if x["id"] == model_id), None)
    if m is None:
        raise ModelError(f"Modèle d'image inconnu : {model_id}")
    return m


def check(model_id: str) -> dict:
    """Le modèle existe et son fournisseur est branché ; sinon un message clair."""
    m = get(model_id)
    if not m["usable"]:
        raise ModelError(f"{m['label']} n'est pas branché (page Fournisseurs : ajoute la clé de {m['provider']})")
    return m


def run_free(model_id: str, prompt: str, refs: list[Path], out: Path, width: int, height: int) -> None:
    """Une image sur le modèle gratuit choisi, et lui seul. Lève ModelError avec un message lisible."""
    from . import elements
    from .providers._http import ProviderError
    import subprocess
    m = check(model_id)
    provider, name = model_id.split(":", 1)
    try:
        elements._draft_one((provider, name, m["label"]), prompt, refs, out, width, height)
    except ProviderError as exc:
        raise ModelError(f"{m['label']} : {exc}. Choisis un autre modèle et relance.") from exc
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        raise ModelError(f"{m['label']} : erreur ({exc}). Choisis un autre modèle et relance.") from exc
