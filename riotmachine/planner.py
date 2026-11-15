"""Le planificateur (PRODUCTION-PLANS-v3 §8, R-H4, R-H5, R-H28).

Fonction pure : mêmes plans, même offre, mêmes options → mêmes prises. Aucun
appel à un modèle ni à un agent. Il regroupe les plans d'une séquence en prises,
choisit la durée et la résolution, chiffre, signale ce qui coince, et compare
les offres entre elles. `impact` dit, avant que Michael ne change une option, ce
que ce changement oblige à refaire (règle D35).
"""

from __future__ import annotations

from typing import Any

from . import catalogue as cat

CLOSE = {"ECU", "CU", "MCU", "BCU"}
EPS = 0.05


def shot_profile(s: dict) -> str:
    chars = s.get("characters") or []
    if not chars:
        return "decor"
    if s.get("singing"):
        return "chant_serre" if (s.get("framing") or "").upper() in CLOSE else "chant_danse_large"
    if len(chars) >= 2:
        return "multi_personnages"
    if s.get("jeu") == "porteur":
        return "jeu"
    return "action"


def sequence_profile(shots: list[dict], forced: str | None = None) -> str:
    if forced:
        return forced
    profs = [shot_profile(s) for s in shots] or ["decor"]
    return max(profs, key=cat.PROFILE_ORDER.index)


def _dur(s: dict) -> float:
    return round(float(s["t_end"]) - float(s["t_start"]), 3)


def _alone(s: dict) -> bool:
    return s.get("jeu") == "porteur" or shot_profile(s) == "chant_serre"


def choose_mode(o: dict, profile: str, wanted: str | None) -> str | None:
    modes = o["modes"]
    if wanted and wanted in modes:
        return wanted
    for m in ("references", "text", "image_start"):
        if m in modes:
            return m
    return None


def _groups(shots: list[dict], o: dict, mode: str) -> list[tuple[str, list[dict]]]:
    """Regroupe les plans (triés) en prises : continue (même axe), multi-plans (plans qui se suivent), seul."""
    maxd = cat.max_duration(o, mode)
    ms = o.get("multi_shot") or {}
    max_shots = int(ms.get("max_shots") or 1)
    margin = float(cat.cfg_defaults().get("cut_margin_s", 0.5)) if ms.get("cuts") == "approximate" else 0.0
    out: list[tuple[str, list[dict]]] = []
    i = 0
    while i < len(shots):
        s = shots[i]
        grp = [s]
        if not _alone(s):
            # même axe, plans qui se suivent : une prise continue
            if s.get("axe"):
                j = i + 1
                while (j < len(shots) and shots[j].get("axe") == s["axe"] and not _alone(shots[j])
                       and abs(float(shots[j]["t_start"]) - float(shots[j - 1]["t_end"])) < EPS
                       and sum(_dur(x) for x in grp) + _dur(shots[j]) <= maxd + EPS):
                    grp.append(shots[j])
                    j += 1
                if len(grp) > 1:
                    out.append(("continuous", grp))
                    i = j
                    continue
            # plans qui se suivent dans le morceau : une prise multi-plans si l'offre le permet
            j = i + 1
            while (max_shots > 1 and j < len(shots) and len(grp) < max_shots and not _alone(shots[j])
                   and abs(float(shots[j]["t_start"]) - float(shots[j - 1]["t_end"])) < EPS
                   and sum(_dur(x) for x in grp) + _dur(shots[j]) + margin * len(grp) <= maxd + EPS):
                grp.append(shots[j])
                j += 1
            if len(grp) > 1:
                out.append(("multi", grp))
                i = j
                continue
        out.append(("single", grp))
        i += 1
    return out


def plan_sequence(shots: list[dict], o: dict, *, quality: str = "brouillon", options: dict | None = None,
                  reserves: dict | None = None, profile: str | None = None, has_refs: bool = True) -> dict[str, Any]:
    """Prises proposées pour les plans tournables d'une séquence, avec cette offre."""
    options = options or {}
    reserves = reserves or {}
    shots = sorted(shots, key=lambda s: float(s["t_start"]))
    prof = sequence_profile(shots, profile)
    mode = choose_mode(o, prof, options.get("mode"))
    warnings: list[dict] = []
    note = cat.profile_note(o, prof)
    if note == "no":
        warnings.append({"kind": "profile_no", "level": "bad",
                         "text": f"{o['label']} ne sait pas faire le profil « {cat.PROFILE_LABEL[prof]} »."})
    elif note in ("weak", "unknown"):
        warnings.append({"kind": "profile_weak", "level": "warn",
                         "text": f"{o['label']} est {'faible' if note == 'weak' else 'non évalué'} en « {cat.PROFILE_LABEL[prof]} »."})
    if not o["usable"]:
        warnings.append({"kind": "not_connected", "level": "bad",
                         "text": f"{o['provider_label']} n'est pas branché : ajoute sa clé dans Fournisseurs pour tourner."})
    if o["stale"]:
        warnings.append({"kind": "unverified", "level": "info",
                         "text": f"Capacités de {o['label']} non vérifiées par un essai depuis plus de "
                                 f"{cat.cfg_defaults().get('stale_days', 45)} jours ({o['source'] or 'source inconnue'})."})
    if mode is None:
        return {"offer": o["key"], "offer_label": o["label"], "mode": None, "profile": prof, "takes": [],
                "total_usd": 0.0, "warnings": warnings + [{"kind": "no_mode", "level": "bad",
                                                            "text": f"{o['label']} n'a aucun mode de génération déclaré."}],
                "blocking": True}
    if prof in cat.NEEDS_REFS and mode != "references":
        warnings.append({"kind": "no_refs", "level": "warn",
                         "text": f"{o['label']} ne prend pas de références en mode {cat.MODE_LABEL.get(mode, mode)} : "
                                 "le personnage sera décrit par le texte seul."})
    if mode == "references" and not has_refs:
        warnings.append({"kind": "refs_missing", "level": "bad",
                         "text": "Aucune image de référence acceptée par ce fournisseur : choisis-en une dans la séquence."})
    if mode == "image_start" and not options.get("start_image"):
        warnings.append({"kind": "start_missing", "level": "bad",
                         "text": "Ce mode demande une image de départ (image maîtresse) : il n'y en a pas encore."})
    res = cat.resolution_for(o, quality, options.get("resolution"))
    price = o["prices"][res]
    ms = o.get("multi_shot") or {}
    margin = float(cat.cfg_defaults().get("cut_margin_s", 0.5)) if ms.get("cuts") == "approximate" else 0.0
    unused_alert = float(cat.cfg_defaults().get("unused_alert", 0.4))
    takes = []
    blocking = any(w["level"] == "bad" for w in warnings)
    for n, (form, grp) in enumerate(_groups(shots, o, mode)):
        gap = 0.0 if form == "continuous" else margin
        need = sum(_dur(s) for s in grp) + gap * (len(grp) - 1)
        dur = cat.fit_duration(o, mode, need)
        alerts = []
        if dur is None:
            dur = cat.max_duration(o, mode)
            s = grp[0]
            alerts.append({"kind": "too_long", "level": "bad", "shot_id": s["id"],
                           "text": f"Le plan {s['num']} dure {_dur(s):.1f} s, {o['label']} tient {dur:.0f} s au plus "
                                   f"en mode {cat.MODE_LABEL.get(mode, mode)}. Il faut le recouper (le script-doctor propose) "
                                   "ou prendre une offre qui tient cette durée."})
            blocking = True
        windows, t = [], 0.0
        for s in grp:
            d = min(_dur(s), dur - t) if dur - t > 0 else _dur(s)
            windows.append({"shot_id": s["id"], "num": s["num"], "t_in": round(t, 2), "t_out": round(t + d, 2),
                            "duration": _dur(s)})
            t += d + gap
        used = sum(_dur(s) for s in grp)
        if dur and (dur - used) / dur > unused_alert:
            alerts.append({"kind": "unused", "level": "info",
                           "text": f"{dur - used:.1f} s payées non utilisées sur {dur:.0f} s."})
        cost = round(dur * price, 2)
        takes.append({"n": n + 1, "form": form, "mode": mode, "duration_s": dur, "resolution": res, "est_usd": cost,
                      "shots": windows, "alerts": alerts})
    total = round(sum(t["est_usd"] for t in takes), 2)
    source, label = cat.funding_for(o, total, reserves)
    return {"offer": o["key"], "offer_label": o["label"], "provider": o["provider"], "usable": o["usable"],
            "mode": mode, "profile": prof, "resolution": res, "price_per_s": price, "takes": takes,
            "total_usd": total, "funding": source, "funding_label": label, "warnings": warnings,
            "blocking": blocking}


def rank(plans: list[dict], offers: list[dict]) -> list[dict]:
    """Classe des plans chiffrés, le recommandé en tête (R-H5).

    Branchée d'abord ; profil tenu (« non » en dernier) ; pas de plan trop long ;
    source de paiement (gratuit, réserve, direct) ; profil « ok » avant « faible » ; coût total.
    """
    by = {o["key"]: o for o in offers}

    def key(p: dict) -> tuple:
        note = cat.profile_note(by[p["offer"]], p["profile"])
        return (not p.get("usable", False), note == "no", p.get("mode") is None,
                any(a["kind"] == "too_long" for t in p["takes"] for a in t["alerts"]),
                cat.funding_rank(p.get("funding", "cash")), note != "ok", p["total_usd"], p["offer"])
    return sorted(plans, key=key)


def candidates(shots: list[dict], offers: list[dict], **kw: Any) -> list[dict]:
    """Toutes les offres chiffrées pour ces plans (sans résolution imposée), la recommandée en tête."""
    opts = {k: v for k, v in (kw.pop("options", None) or {}).items() if k != "resolution"}
    return rank([plan_sequence(shots, o, options=opts, **kw) for o in offers], offers)


def impact(current: dict | None, alt: dict, *, shot_taken: dict[int, str] | None = None) -> list[str]:
    """Ce que change le passage de `current` à `alt`, en phrases, avant que Michael ne décide (D35).

    `shot_taken` : plans qui ont déjà une prise gardée ou à dérusher -> clé de l'offre qui l'a tournée.
    """
    lines: list[str] = []
    shot_taken = shot_taken or {}
    if current:
        d = round(alt["total_usd"] - current["total_usd"], 2)
        sign = "+" if d > 0 else ""
        lines.append(f"Coût : {current['total_usd']:.2f} $ → {alt['total_usd']:.2f} $ ({sign}{d:.2f} $).")
        if len(current["takes"]) != len(alt["takes"]):
            lines.append(f"Prises : {len(current['takes'])} → {len(alt['takes'])}.")
        if current.get("funding") != alt.get("funding"):
            lines.append(f"Paiement : {current.get('funding_label')} → {alt.get('funding_label')}.")
    else:
        lines.append(f"Coût : {alt['total_usd']:.2f} $ en {len(alt['takes'])} prise(s), {alt.get('funding_label', '')}.")
    old_long = {a.get("shot_id") for t in (current or {}).get("takes", []) for a in t["alerts"] if a["kind"] == "too_long"}
    for t in alt["takes"]:
        for a in t["alerts"]:
            if a["kind"] == "too_long" and a.get("shot_id") not in old_long:
                lines.append("À recouper avant de tourner : " + a["text"])
    redo = [sid for sid, k in shot_taken.items() if k != alt["offer"]]
    if redo:
        lines.append(f"{len(redo)} plan(s) déjà tournés avec une autre offre seront à retourner ; "
                     "les anciennes prises restent gardables.")
    if shot_taken and any(k != alt["offer"] for k in shot_taken.values()) and any(k == alt["offer"] for k in shot_taken.values()):
        lines.append("Mélange de modèles dans la séquence : les raccords peuvent se voir.")
    for w in alt["warnings"]:
        if w["level"] in ("bad", "warn") and w["kind"] != "not_connected":
            lines.append(w["text"])
    if not alt.get("usable", True):
        lines.append("Fournisseur non branché : rien ne peut partir tant que sa clé n'est pas ajoutée.")
    return lines
