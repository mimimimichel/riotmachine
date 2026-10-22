"""Choix du modèle et construction des requêtes, à partir de config/models.yaml.

Le routage est déterministe : l'agent routeur décrit le plan (cadrage,
mouvement, nombre de personnages...), ces règles choisissent le palier
(eco / standard / premium) et donc le modèle. L'agent peut forcer un palier
en le justifiant, et chaque retour « rendu pas assez bon » fait monter d'un cran.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .settings import load_models


class RoutingError(Exception):
    pass


def models_cfg() -> dict[str, Any]:
    return load_models()


def model(key: str) -> dict[str, Any]:
    cfg = models_cfg()["models"]
    if key not in cfg:
        raise RoutingError(f"Modèle inconnu dans config/models.yaml : {key}")
    return {"key": key, **cfg[key]}


def tier_order() -> list[str]:
    return list(models_cfg()["tier_order"])


def tier_model_key(tier: str) -> str:
    tiers = models_cfg()["tiers"]
    if tier not in tiers:
        raise RoutingError(f"Palier inconnu : {tier} (paliers : {', '.join(tiers)})")
    return tiers[tier]["model"]


def classify(features: dict[str, Any]) -> tuple[str, str]:
    """Retourne (palier, règle appliquée) pour un plan décrit par ses caractéristiques."""
    motion = features.get("motion") or "low"
    framing = features.get("framing") or "MS"
    n_chars = len(features.get("characters") or [])
    for i, rule in enumerate(models_cfg()["routing"]["rules"]):
        when = rule.get("when") or {}
        if "motion" in when and motion not in when["motion"]:
            continue
        if "framing" in when and framing not in when["framing"]:
            continue
        if "min_characters" in when and n_chars < int(when["min_characters"]):
            continue
        if "singing" in when and bool(features.get("singing")) != bool(when["singing"]):
            continue
        return rule["tier"], rule.get("why") or f"règle {i + 1}"
    return tier_order()[0], "défaut"


def upgrade_tier(tier: str | None) -> str:
    order = tier_order()
    if tier not in order:
        return order[0]
    return order[min(order.index(tier) + 1, len(order) - 1)]


def choose_duration(model_cfg: dict[str, Any], shot_seconds: float) -> int:
    """Durée générée : la plus petite durée autorisée qui couvre le plan."""
    allowed = sorted(int(d) for d in model_cfg.get("durations", [5]))
    for d in allowed:
        if d + 1e-6 >= shot_seconds:
            return d
    return allowed[-1]


def _price_for(model_cfg: dict[str, Any], mode: str) -> float:
    price = model_cfg.get("price") or {}
    params = model_cfg.get(f"{mode}_params") or {}
    for unit in ("per_second", "per_image", "per_run"):
        value = price.get(unit)
        if value is None:
            continue
        if isinstance(value, dict):
            res = str(params.get("resolution", "default"))
            value = value.get(res, value.get("default", max(value.values())))
        return float(value)
    return 0.0


def estimate_cost(model_cfg: dict[str, Any], seconds: float = 0.0, mode: str = "draft") -> float:
    unit_price = _price_for(model_cfg, mode)
    price = model_cfg.get("price") or {}
    if "per_second" in price:
        return round(unit_price * max(seconds, 1.0), 4)
    return round(unit_price, 4)


def build_payload(
    model_cfg: dict[str, Any],
    *,
    prompt: str | None = None,
    image_urls: list[str] | None = None,
    video_url: str | None = None,
    audio_url: str | None = None,
    duration: int | None = None,
    seed: int | None = None,
    negative_prompt: str | None = None,
    aspect_ratio: str | None = None,
    mode: str = "draft",
) -> dict[str, Any]:
    """Traduit nos champs génériques vers les noms de paramètres du modèle."""
    mapping: dict[str, str] = model_cfg.get("input") or {}
    payload: dict[str, Any] = dict(model_cfg.get("defaults") or {})
    payload.update(model_cfg.get(f"{mode}_params") or {})

    def put(field: str, value: Any) -> None:
        target = mapping.get(field)
        if target and value is not None:
            payload[target] = value

    put("prompt", prompt)
    if image_urls:
        target = mapping.get("images") or mapping.get("image")
        if mapping.get("images"):
            max_refs = int(model_cfg.get("max_refs", 14))
            payload[mapping["images"]] = image_urls[:max_refs]
        elif target:
            payload[target] = image_urls[0]
    put("video", video_url)
    put("audio", audio_url)
    if duration is not None and mapping.get("duration"):
        fmt = model_cfg.get("duration_format", "int")
        if fmt == "str":
            payload[mapping["duration"]] = str(duration)
        elif fmt == "str_s":
            payload[mapping["duration"]] = f"{duration}s"
        else:
            payload[mapping["duration"]] = int(duration)
    put("seed", seed)
    put("negative_prompt", negative_prompt)
    if aspect_ratio and mapping.get("aspect_ratio") and mapping["aspect_ratio"] not in (model_cfg.get(f"{mode}_params") or {}):
        payload[mapping["aspect_ratio"]] = aspect_ratio
    return payload


_PATH_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def extract_output(result: dict[str, Any], path: str) -> str:
    """Lit l'URL du fichier produit, ex. 'video.url' ou 'images[0].url'."""
    node: Any = result
    for name, index in _PATH_TOKEN.findall(path):
        try:
            node = node[int(index)] if index else node[name]
        except (KeyError, IndexError, TypeError) as exc:
            raise RoutingError(f"Sortie introuvable '{path}' dans la réponse : {str(result)[:300]}") from exc
    if not isinstance(node, str):
        raise RoutingError(f"La sortie '{path}' n'est pas une URL : {node!r}")
    return node


def shot_seconds(shot: dict[str, Any]) -> float:
    return max(0.5, float(shot["t_end"]) - float(shot["t_start"]))


# Fournisseurs dont l'appel est écrit dans le code. Les autres sont déclarés
# dans models.yaml mais attendent leur branchement.
IMPLEMENTED_PROVIDERS = {"fal"}


def providers() -> list[dict[str, Any]]:
    """État de chaque fournisseur : branché dans le code, clé présente, utilisable."""
    import os
    from .settings import get_settings
    out = []
    for key, cfg in (models_cfg().get("providers") or {}).items():
        implemented = key in IMPLEMENTED_PROVIDERS
        has_key = bool(os.environ.get(cfg.get("env", ""), ""))
        simulated = key == "fal" and get_settings().fal_mock
        out.append({
            "key": key, "label": cfg.get("label", key), "note": cfg.get("note", ""), "env": cfg.get("env"),
            "implemented": implemented, "has_key": has_key,
            "usable": implemented and (has_key or simulated), "simulated": simulated,
        })
    return out


def provider_usable(key: str) -> bool:
    return any(p["key"] == key and p["usable"] for p in providers())


def video_models() -> list[dict[str, Any]]:
    tiers = {v["model"]: t for t, v in models_cfg()["tiers"].items()}
    out = []
    for key, cfg in models_cfg()["models"].items():
        if cfg.get("kind") != "video":
            continue
        prov = cfg.get("provider", "fal")
        out.append({"key": key, "label": cfg.get("label", key), "provider": prov,
                    "use_for": cfg.get("use_for", ""), "tier": tiers.get(key),
                    "usable": provider_usable(prov)})
    return out


def model_options(shot: dict[str, Any]) -> list[dict[str, Any]]:
    """Chaque modèle vidéo avec son coût estimé pour ce plan (pour le choix de Michael)."""
    opts = []
    for m in video_models():
        est = route_shot(shot, model_key=m["key"])
        opts.append({**m, "cost_total_usd": est["cost_total_usd"], "duration": est["duration"]})
    return opts


def route_shot(shot: dict[str, Any], force_tier: str | None = None,
               model_key: str | None = None) -> dict[str, Any]:
    """Résumé du routage d'un plan : palier, modèle, durée générée, coût estimé."""
    if model_key:
        tiers = {v["model"]: t for t, v in models_cfg()["tiers"].items()}
        tier, why = tiers.get(model_key, shot.get("tier") or "standard"), "modèle choisi"
        key = model_key
    elif force_tier:
        tier, why = force_tier, "palier forcé"
        key = tier_model_key(tier)
    else:
        tier, why = classify(shot)
        key = tier_model_key(tier)
    cfg = model(key)
    seconds = shot_seconds(shot)
    duration = choose_duration(cfg, seconds)
    draft_cost = estimate_cost(cfg, duration, "draft")
    final_mode = cfg.get("final_mode", "upscale")
    if final_mode == "upscale":
        up = model(models_cfg()["upscale"])
        final_cost = estimate_cost(up, duration, "final")
    elif final_mode == "keep":
        final_cost = 0.0   # la vidéo draft est déjà en qualité finale
    else:
        final_cost = estimate_cost(cfg, duration, "final")
    lipsync_cost = 0.0
    if shot.get("singing"):
        lipsync_cost = estimate_cost(model(models_cfg()["lipsync"]), seconds, "final")
    return {
        "tier": tier,
        "why": why,
        "model_key": key,
        "model_label": cfg.get("label", key),
        "provider": cfg.get("provider", "fal"),
        "duration": duration,
        "shot_seconds": round(seconds, 2),
        "final_mode": final_mode,
        "cost_draft_usd": draft_cost,
        "cost_final_usd": final_cost,
        "cost_lipsync_usd": lipsync_cost,
        "cost_total_usd": round(draft_cost + final_cost + lipsync_cost, 3),
    }


def ceil_seconds(x: float) -> int:
    return int(math.ceil(x))
