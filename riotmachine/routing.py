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
    price = model_cfg.get("price") or {}
    if "per_video" in price:
        # prix par vidéo, selon la résolution puis la durée : {"1080P": {"6": 0.33}}
        res = str((model_cfg.get(f"{mode}_params") or {}).get("resolution", "default"))
        table = price["per_video"].get(res) or next(iter(price["per_video"].values()))
        key = str(int(math.ceil(seconds - 1e-6))) if seconds else next(iter(table))
        return round(float(table.get(key, max(table.values()))), 4)
    unit_price = _price_for(model_cfg, mode)
    if price.get("round_to"):
        # facturé par tranches (ex. lip-sync Kling : tranches de 5 s)
        step = float(price["round_to"])
        seconds = math.ceil(max(seconds, 1.0) / step) * step
    if "per_second" in price:
        extra = float(price.get("per_run") or 0) if not isinstance(price.get("per_run"), dict) else 0.0
        return round(unit_price * max(seconds, 1.0) + extra, 4)
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
IMPLEMENTED_PROVIDERS = {"fal", "vertex", "kling", "runway", "gemini", "minimax", "atlas", "replicate", "evolink", "cloudflare"}


def _forced_simulation() -> bool:
    import os
    return os.environ.get("RIOT_FAL_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def provider_has_key(key: str) -> bool:
    import os
    cfg = (models_cfg().get("providers") or {}).get(key) or {}
    env_all = cfg.get("env") or []
    env_all = [env_all] if isinstance(env_all, str) else env_all
    env_any = cfg.get("env_any") or []
    return all(os.environ.get(e, "").strip() for e in env_all) and (
        not env_any or any(os.environ.get(e, "").strip() for e in env_any))


def providers() -> list[dict[str, Any]]:
    from . import provider_keys
    """État de chaque fournisseur : branché dans le code, clés présentes, utilisable.

    Un fournisseur sans clé n'est pas utilisable : aucun fichier factice n'est
    produit. Seuls les tests automatiques simulent tout (RIOT_FAL_MOCK=1).
    """
    forced = _forced_simulation()
    keys = {k: provider_has_key(k) for k in (models_cfg().get("providers") or {})}
    out = []
    for key, cfg in (models_cfg().get("providers") or {}).items():
        env_all = cfg.get("env") or []
        env_all = [env_all] if isinstance(env_all, str) else env_all
        env_any = cfg.get("env_any") or []
        has_key = keys[key] and not forced
        implemented = key in IMPLEMENTED_PROVIDERS
        enabled = key not in provider_keys.disabled()
        out.append({
            "key": key, "label": cfg.get("label", key), "note": cfg.get("note", ""),
            "env": env_all + ([" ou ".join(env_any)] if env_any else []),
            "keys": [{"name": n, "required": n in env_all, "masked": provider_keys.masked(n)}
                     for n in env_all + list(env_any)],
            "any_of": list(env_any),
            "implemented": implemented, "has_key": has_key, "enabled": enabled,
            "usable": implemented and enabled and (has_key or forced), "simulated": forced,
        })
    return out


def pick_model(role: str, section: str = "image") -> str:
    """Premier modèle de la liste `image.<role>` dont le fournisseur est utilisable."""
    choice = (models_cfg().get(section) or {}).get(role)
    choices = choice if isinstance(choice, list) else [choice]
    for key in choices:
        if key and provider_usable(models_cfg()["models"][key].get("provider", "fal")):
            return key
    return choices[0]


def provider_usable(key: str) -> bool:
    return any(p["key"] == key and p["usable"] for p in providers())


def default_video_model() -> str:
    """Le modèle vidéo proposé par défaut pour un plan (models.yaml : video_default),
    ou le premier de la liste dont le fournisseur est branché."""
    choice = models_cfg().get("video_default")
    choices = choice if isinstance(choice, list) else [choice] if choice else []
    for key in choices:
        if key in models_cfg()["models"] and provider_usable(models_cfg()["models"][key].get("provider", "fal")):
            return key
    return choices[0] if choices else tier_model_key(tier_order()[0])


def duration_fit(cfg: dict[str, Any], seconds: float) -> dict[str, Any]:
    """Écart entre la durée du plan et ce que le modèle sait générer.

    level : ok, warn (on paie nettement plus que ce qu'on garde), bad (plan trop
    long pour le modèle : à couper ou à confier à un autre modèle).
    """
    allowed = sorted(int(d) for d in cfg.get("durations", [5]))
    gen = choose_duration(cfg, seconds)
    waste = round(max(0.0, gen - seconds), 2)
    label = cfg.get("label", cfg.get("key", ""))
    allowed_txt = ", ".join(str(d) for d in allowed) if len(allowed) <= 4 else f"{allowed[0]} à {allowed[-1]}"
    if seconds > allowed[-1] + 0.05:
        return {"level": "bad", "generated": gen, "waste": 0.0,
                "text": f"Trop long pour {label} ({allowed[-1]} s maximum) : à couper ou à confier à un autre modèle"}
    if waste >= 1.5:
        return {"level": "warn", "generated": gen, "waste": waste,
                "text": f"{label} génère {gen} s pour {seconds:.1f} s gardées ({allowed_txt} s possibles) : "
                        f"{waste:.1f} s payées pour rien"}
    return {"level": "ok", "generated": gen, "waste": waste, "text": f"{label} génère {gen} s"}


def video_models() -> list[dict[str, Any]]:
    tiers = {v["model"]: t for t, v in models_cfg()["tiers"].items()}
    out = []
    for key, cfg in models_cfg()["models"].items():
        if cfg.get("kind") != "video":
            continue
        prov = cfg.get("provider", "fal")
        out.append({"key": key, "label": cfg.get("label", key), "provider": prov,
                    "use_for": cfg.get("use_for", ""), "tier": tiers.get(key), "tiers": cfg.get("tiers") or [],
                    "aspects": cfg.get("aspects"), "to_test": bool(cfg.get("to_test")),
                    "max_seconds": max(int(d) for d in cfg.get("durations", [5])),
                    "durations": [int(d) for d in cfg.get("durations", [5])],
                    "lipsync": cfg.get("lipsync"), "multishot": bool(cfg.get("multishot")),
                    "price_s": _price_for(cfg, "final") if "per_second" in (cfg.get("price") or {}) else None,
                    "usable": provider_usable(prov)})
    return out


def _credits() -> dict[str, dict]:
    try:
        from .credits import status
        return status()
    except Exception:   # base indisponible (tests unitaires du routage) : pas de crédits
        return {}


def effective_cost(model_key: str, cost: float, credit_status: dict[str, dict] | None = None) -> float:
    """Ce que l'offre coûte vraiment : 0 si les crédits du fournisseur la couvrent."""
    prov = model(model_key).get("provider", "fal")
    st = (credit_status if credit_status is not None else _credits()).get(prov)
    return 0.0 if st and st["remaining"] >= cost else cost


def fits_shot(cfg: dict[str, Any], shot: dict[str, Any], tier: str) -> bool:
    """Le modèle tient-il ce palier, le format du clip et la durée du plan ?"""
    if tier not in (cfg.get("tiers") or []):
        return False
    aspect = shot.get("aspect_ratio")
    if aspect and cfg.get("aspects") and aspect not in cfg["aspects"]:
        return False
    longest = max(int(d) for d in cfg.get("durations", [5]))
    return longest + 0.05 >= shot_seconds(shot)


def cheapest_for(tier: str, shot: dict[str, Any]) -> tuple[str, int]:
    """L'offre utilisable la moins chère qui tient ce palier, pour la durée de ce plan.
    Les offres couvertes par des crédits gratuits passent devant (coût effectif 0)."""
    credit_status = _credits()
    fits = []
    for key, cfg in models_cfg()["models"].items():
        if cfg.get("kind") != "video" or cfg.get("to_test") or not fits_shot(cfg, shot, tier):
            continue
        if not provider_usable(cfg.get("provider", "fal")):
            continue
        cost = route_shot(shot, model_key=key)["cost_total_usd"]
        fits.append((effective_cost(key, cost, credit_status), cost, key))
    if not fits:
        return tier_model_key(tier), 0
    fits.sort()
    return fits[0][2], len(fits)


def model_options(shot: dict[str, Any]) -> list[dict[str, Any]]:
    """Chaque modèle vidéo avec son coût estimé pour ce plan (pour le choix de Michael)."""
    need = shot.get("tier") or classify(shot)[0]
    credit_status = _credits()
    opts = []
    for m in video_models():
        est = route_shot(shot, model_key=m["key"])
        eff = effective_cost(m["key"], est["cost_total_usd"], credit_status)
        opts.append({**m, "cost_total_usd": est["cost_total_usd"], "duration": est["duration"],
                     "effective_usd": eff, "on_credits": eff == 0 and est["cost_total_usd"] > 0,
                     "fits": fits_shot(models_cfg()["models"][m["key"]], shot, need)})
    return opts


def route_shot(shot: dict[str, Any], force_tier: str | None = None,
               model_key: str | None = None) -> dict[str, Any]:
    """Résumé du routage d'un plan : palier, modèle, durée générée, coût estimé."""
    if model_key:
        tiers = {v["model"]: t for t, v in models_cfg()["tiers"].items()}
        tier, why = tiers.get(model_key, shot.get("tier") or "standard"), "modèle choisi"
        key = model_key
    else:
        if force_tier:
            tier, why = force_tier, "palier forcé"
        else:
            tier, why = classify(shot)
        key, n_fit = cheapest_for(tier, shot)
        if n_fit > 1:
            why = f"{why} ; le moins cher des {n_fit} modèles adaptés"
        prov = model(key).get("provider", "fal")
        st = _credits().get(prov)
        if st and st["remaining"] > 0:
            why = f"{why} ; payé par {st['label']} (reste {st['remaining']:.0f} $)"
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
    if shot.get("singing") and not native_lipsync(key):
        lipsync_cost = estimate_cost(model(lipsync_model_key(seconds, shot.get("lipsync_key"))), seconds, "final")
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


def lipsync_options() -> list[dict[str, Any]]:
    cfg = models_cfg()
    keys = cfg.get("lipsync_models") or [cfg["lipsync"], cfg.get("lipsync_fallback")]
    out = []
    for k in [k for k in keys if k]:
        m = model(k)
        out.append({"key": k, "label": m.get("label", k), "provider": m.get("provider", "fal"),
                    "usable": provider_usable(m.get("provider", "fal")),
                    "min_seconds": m.get("min_seconds"), "max_seconds": m.get("max_seconds")})
    return out


def native_lipsync(video_key: str | None) -> bool:
    """Le modèle vidéo cale lui-même la bouche sur la voix (pas d'étape lip-sync)."""
    return bool(video_key) and model(video_key).get("lipsync") == "native"


def lipsync_model_key(seconds: float, chosen: str | None = None) -> str:
    """Le lip-sync choisi par Michael, sinon le premier branché qui accepte cette durée."""
    if chosen:
        return chosen
    opts = lipsync_options()
    fits = [o for o in opts if float(o["min_seconds"] or 0) <= seconds <= float(o["max_seconds"] or 1e9)]
    for o in fits + opts:
        if o["usable"]:
            return o["key"]
    return (fits or opts)[0]["key"]


def ceil_seconds(x: float) -> int:
    return int(math.ceil(x))
