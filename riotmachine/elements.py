"""Décors, objets clés et figurants d'un clip.

Un visuel de plan n'est cohérent avec les autres que si le lieu, les objets et les
personnages secondaires sont toujours les mêmes. Chaque élément a donc :
- une fiche (description fixe : plan des lieux, matières, couleurs, lumière) ;
- des états quand il change (ex. jardin « intact le matin », « vide au retour ») ;
- des images en deux temps : l'image de départ de Michael (role 'draft', pas encore
  HD) puis l'image HD générée à partir d'elle avec un prompt qu'il peut réécrire
  (role 'hd'). Il peut aussi déposer directement une image HD. Seules les images HD
  gardées servent de référence aux visuels des plans ;
- les plans où il apparaît (shot_elements).

Quand un visuel de plan est généré, les images gardées de ses éléments partent en
référence et leurs fiches sont ajoutées au prompt (voir production.launch_image).
L'agent décorateur repère les éléments du découpage, écrit leurs fiches et relie
les plans ; il ne lance pas d'image. Un plan cite un élément avec @slug.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sqlite3
from pathlib import Path
from typing import Any

from . import credits, db, providers, routing
from .production import (IMAGE_EXT, ProductionError, _ask_spend, _free_name, _hash, _insert_job,
                         _needs_approval, absp, rel, slugify, studio)
from . import fal

KIND_LABEL = {"decor": "Décor", "objet": "Objet", "figurant": "Figurant"}
ASPECT = {"decor": None, "objet": "1:1", "figurant": "3:4"}   # None : format du clip


def _element(conn: sqlite3.Connection, element_id: int) -> dict:
    e = db.row(conn.execute("SELECT * FROM elements WHERE id=?", (element_id,)).fetchone())
    if e is None:
        raise ProductionError(f"Élément inconnu : {element_id}")
    e["states"] = json.loads(e["states"] or "[]")
    return e


def find(conn: sqlite3.Connection, clip_slug: str, ref: str | int) -> dict:
    """Un élément par id ou par slug dans le clip."""
    if str(ref).isdigit():
        return _element(conn, int(ref))
    r = conn.execute("SELECT id FROM elements WHERE clip_slug=? AND slug=?", (clip_slug, slugify(str(ref)))).fetchone()
    if r is None:
        raise ProductionError(f"Élément inconnu dans {clip_slug} : {ref}")
    return _element(conn, r["id"])


def create(conn: sqlite3.Connection, clip_slug: str, kind: str, name: str, description: str = "",
           states: list[str] | None = None, created_by: str = "michael") -> dict:
    if kind not in KIND_LABEL:
        raise ProductionError(f"Type inconnu : {kind} (decor, objet, figurant)")
    clip = db.get_clip(conn, clip_slug)
    slug = slugify(name)
    if not slug:
        raise ProductionError("Donne un nom à l'élément")
    if conn.execute("SELECT 1 FROM elements WHERE clip_slug=? AND slug=?", (clip_slug, slug)).fetchone():
        raise ProductionError(f"« {name} » existe déjà dans ce clip")
    edir = studio() / clip["dir"] / "decors" / slug
    edir.mkdir(parents=True, exist_ok=True)
    states = [s.strip() for s in (states or []) if s and s.strip()]
    cur = conn.execute(
        "INSERT INTO elements (clip_slug, kind, slug, name, description, states, dir, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (clip_slug, kind, slug, name.strip(), description.strip() or None, json.dumps(states, ensure_ascii=False),
         rel(edir), created_by, db.now()))
    db.log_event(conn, clip_slug, "decors", f"{KIND_LABEL[kind]} ajouté : {name}")
    return _element(conn, cur.lastrowid)


def update(conn: sqlite3.Connection, element_id: int, *, name: str | None = None, description: str | None = None,
           states: list[str] | None = None) -> dict:
    e = _element(conn, element_id)
    if name is not None and name.strip():
        conn.execute("UPDATE elements SET name=? WHERE id=?", (name.strip(), element_id))
    if description is not None:
        conn.execute("UPDATE elements SET description=? WHERE id=?", (description.strip() or None, element_id))
    if states is not None:
        conn.execute("UPDATE elements SET states=? WHERE id=?",
                     (json.dumps([s.strip() for s in states if s.strip()], ensure_ascii=False), element_id))
    return _element(conn, e["id"])


def delete(conn: sqlite3.Connection, element_id: int) -> None:
    e = _element(conn, element_id)
    with db.tx(conn):
        conn.execute("DELETE FROM shot_elements WHERE element_id=?", (element_id,))
        conn.execute("DELETE FROM jobs WHERE target_table='element_images' AND target_id IN "
                     "(SELECT id FROM element_images WHERE element_id=?)", (element_id,))
        conn.execute("DELETE FROM element_images WHERE element_id=?", (element_id,))
        conn.execute("DELETE FROM elements WHERE id=?", (element_id,))
        cited = [r["num"] for r in conn.execute(
            "SELECT num FROM shots WHERE clip_slug=? AND (LOWER(description) LIKE ? OR LOWER(detail) LIKE ?) ORDER BY num",
            (e["clip_slug"], f"%@{e['slug']}%", f"%@{e['slug']}%")).fetchall()]
        db.log_event(conn, e["clip_slug"], "decors", f"{KIND_LABEL[e['kind']]} supprimé : {e['name']}"
                     + (f" (encore cité par @{e['slug']} dans les plans {', '.join(map(str, cited))})" if cited else ""))
    shutil.rmtree(absp(e["dir"]), ignore_errors=True)


def cancel_pending(conn: sqlite3.Connection, element_id: int, why: str) -> int:
    """Les demandes d'image en attente de cet élément deviennent caduques (nouvelle source, nouveau prompt)."""
    n = 0
    for r in conn.execute("SELECT id, args FROM spend_requests WHERE action='element_image' AND status='pending'").fetchall():
        if json.loads(r["args"]).get("element_id") == element_id:
            conn.execute("UPDATE spend_requests SET status='refused', note=?, decided_at=? WHERE id=?",
                         (why, db.now(), r["id"]))
            n += 1
    return n


def add_image(conn: sqlite3.Connection, element_id: int, src: str | Path, state: str | None = None,
              label: str | None = None, role: str = "draft") -> dict:
    """Image déposée par Michael.

    - draft : son image de départ (pas encore HD ni photoréaliste). L'image HD en part.
    - hd : une image déjà finie, gardée telle quelle comme référence des visuels de plan.
    """
    if role not in ("draft", "hd", "inspi"):
        raise ProductionError("Rôle d'image : inspi, draft ou hd")
    e = _element(conn, element_id)
    src = Path(src)
    if src.suffix.lower() not in IMAGE_EXT:
        raise ProductionError("Une image est attendue (png, jpg, webp)")
    folder = {"draft": "depart", "inspi": "inspiration"}.get(role, "sources")
    dest = _free_name(absp(e["dir"]) / folder / f"{slugify(src.stem)[:60] or 'image'}-{db.now()[11:19].replace(':', '')}{src.suffix.lower()}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    cur = conn.execute(
        "INSERT INTO element_images (element_id, state, source, path, label, status, role, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (element_id, state or None, "michael", rel(dest), label or src.stem, "kept", role, db.now()))
    if role == "draft":
        cancel_pending(conn, element_id, "remplacée : Michael a déposé son image de départ")
        # le décorateur regarde l'image et écrit la fiche et le prompt HD qui la décrivent
        conn.execute("UPDATE elements SET prompt_status='requested' WHERE id=?", (element_id,))
    return db.row(conn.execute("SELECT * FROM element_images WHERE id=?", (cur.lastrowid,)).fetchone())


def _refs(conn: sqlite3.Connection, element_id: int, state: str | None, limit: int = 4,
          role: str = "hd") -> list[Path]:
    """Images gardées de l'élément (HD par défaut) : celles de l'état demandé d'abord, puis l'état de base."""
    rows = conn.execute(
        "SELECT path, state, source FROM element_images WHERE element_id=? AND status='kept' AND role=? "
        "AND path IS NOT NULL "
        "ORDER BY (COALESCE(state,'')=COALESCE(?,'')) DESC, (state IS NULL) DESC, (source='gen') DESC, id",
        (element_id, role, state)).fetchall()
    out = [absp(r["path"]) for r in rows]
    return [p for p in out if p and p.is_file()][:limit]


def _draft_for_state(conn: sqlite3.Connection, element_id: int, state: str | None) -> list[Path]:
    """Les images de départ de cet état exact (ou de l'état de base pour l'état de base)."""
    rows = conn.execute(
        "SELECT path FROM element_images WHERE element_id=? AND status='kept' AND role='draft' AND path IS NOT NULL "
        "AND COALESCE(state,'')=COALESCE(?,'') ORDER BY id", (element_id, state)).fetchall()
    return [p for p in (absp(r["path"]) for r in rows) if p and p.is_file()]


WHAT = {"decor": "a photographic reference plate of this location, wide establishing view, no people",
        "objet": "a product-style photographic reference of this object, plain neutral background, whole object visible",
        "figurant": "a photographic reference of this person or animal, full body, standing still, neutral background"}


def default_prompt(e: dict, from_draft: bool) -> str:
    """Prompt de secours, avant que le décorateur ait regardé l'image de départ.

    Avec une image de départ, l'image fait foi : la fiche n'est pas recopiée (elle
    pourrait la contredire). Sans image, la fiche décrit seulement l'apparence."""
    if from_draft:
        return (f"Turn the reference image into {WHAT[e['kind']]}. "
                "Keep its exact composition, layout, camera angle, objects, proportions and colour palette. "
                "Only raise the realism: photographic materials and textures, natural light, fine detail, "
                "high definition. Do not add, remove or move anything.")
    return (f"{WHAT[e['kind']][0].upper()}{WHAT[e['kind']][1:]}: {e['name']}. "
            f"{(e['description'] or '').strip()} Photorealistic, natural light, true-to-life colours.").strip()


def proposed_prompt(e: dict, from_draft: bool) -> str:
    """Le prompt proposé à Michael : celui du décorateur s'il a regardé l'image, sinon le prompt de secours."""
    return (e.get("prompt_agent") or "").strip() or default_prompt(e, from_draft)


def generation_prompt(e: dict, state: str | None, extra: str = "", from_draft: bool = False) -> str:
    base = (e.get("prompt") or "").strip() or proposed_prompt(e, from_draft)
    return base + (f"\n\nDirector's notes: {extra}" if extra else "")


def set_prompt(conn: sqlite3.Connection, element_id: int, text: str) -> dict:
    """Michael réécrit le prompt de l'image HD ; un texte vide rend le prompt proposé."""
    e = _element(conn, element_id)
    clean = text.strip()
    if clean and clean in (proposed_prompt(e, True), proposed_prompt(e, False)):
        clean = ""
    conn.execute("UPDATE elements SET prompt=? WHERE id=?", (clean or None, element_id))
    return _element(conn, element_id)


def request_describe(conn: sqlite3.Connection, element_id: int) -> dict:
    """Michael demande au décorateur d'écrire la fiche et le prompt HD d'après ses images de départ."""
    e = _element(conn, element_id)
    if not conn.execute("SELECT 1 FROM element_images WHERE element_id=? AND role='draft' AND status='kept'",
                        (element_id,)).fetchone():
        raise ProductionError("Dépose d'abord ton image de départ")
    conn.execute("UPDATE elements SET prompt_status='requested' WHERE id=?", (element_id,))
    db.log_event(conn, e["clip_slug"], "decors", f"Prompt HD demandé au décorateur : {e['name']}")
    return _element(conn, element_id)


def describe(conn: sqlite3.Connection, element_id: int, prompt: str, description: str | None = None) -> dict:
    """Le décorateur a regardé l'image de départ : fiche (apparence seule) et prompt HD qui décrit l'image."""
    e = _element(conn, element_id)
    if not prompt.strip():
        raise ProductionError("Le prompt est vide")
    with db.tx(conn):
        if description is not None and description.strip():
            conn.execute("UPDATE elements SET description=? WHERE id=?", (description.strip(), element_id))
        conn.execute("UPDATE elements SET prompt_agent=?, prompt_status='none' WHERE id=?", (prompt.strip(), element_id))
        cancel_pending(conn, element_id, "remplacée : le décorateur a écrit le prompt d'après l'image de départ")
        db.log_event(conn, e["clip_slug"], "decors", f"Prompt HD écrit d'après l'image de départ : {e['name']}")
    return _element(conn, element_id)


def hd_model() -> tuple[str, dict, float]:
    key = routing.pick_model("casting")
    mcfg = routing.model(key)
    return key, mcfg, routing.estimate_cost(mcfg, mode="final")


def launch_image(conn: sqlite3.Connection, element_id: int, state: str | None = None, prompt: str | None = None,
                 approved: bool = False, model: str | None = None) -> dict:
    """Génère l'image HD de l'élément, à partir de l'image de départ de Michael quand il y en a une.

    Références envoyées : l'image de départ de cet état, puis les images HD déjà gardées
    (l'état de base garde le lieu identique d'un état à l'autre)."""
    e = _element(conn, element_id)
    clip = db.get_clip(conn, e["clip_slug"])
    key, mcfg, cost = hd_model()
    from . import image_models
    if model and image_models.is_free(model):
        return _launch_free_hd(conn, e, state, prompt, model, clip)
    if model:
        try:
            image_models.check(model)
        except image_models.ModelError as exc:
            raise ProductionError(str(exc)) from exc
        key, mcfg = model, routing.model(model)
        cost = routing.estimate_cost(mcfg, mode="final")
    drafts = _draft_for_state(conn, element_id, state)
    if not drafts and state:
        drafts = _draft_for_state(conn, element_id, None)
    refs = (drafts[-1:] + _refs(conn, element_id, state, limit=2))[:3]   # une seule image de départ : sa composition
    from .production import with_style
    text = with_style(prompt or generation_prompt(e, state, from_draft=bool(drafts)), clip)
    if _needs_approval(mcfg.get("provider", "fal"), cost, False, approved):
        return _ask_spend(conn, "element_image", {"element_id": element_id, "state": state, "prompt": prompt, "model": key},
                          _hash(element_id, state, text, [str(p) for p in refs]),
                          f"{KIND_LABEL[e['kind']]} « {e['name']} »{' (' + state + ')' if state else ''} : image HD",
                          cost, mcfg, key, detail=text, clip_slug=e["clip_slug"])
    payload = routing.build_payload(mcfg, prompt=text, image_urls=[fal.to_data_uri(p) for p in refs], mode="final",
                                    aspect_ratio=ASPECT[e["kind"]] or clip["aspect_ratio"])
    sub = providers.submit(mcfg, payload, kind="image", label=f"{e['slug']} {state or ''}")
    out = absp(e["dir"]) / f"{slugify(state or 'base')}-{sub['request_id'][-6:]}.png"
    with db.tx(conn):
        cancel_pending(conn, element_id, "remplacée par une génération lancée par Michael")
        cur = conn.execute(
            "INSERT INTO element_images (element_id, state, source, path, label, prompt, model_key, cost_usd, funding, "
            "status, role, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (element_id, state, "gen", rel(out), state or "référence", text, key, cost,
             credits.funding_for(conn, mcfg.get("provider", "fal"), cost), "generating", "hd", db.now()))
        _insert_job(conn, "element_images", cur.lastrowid, mcfg["endpoint"], sub, out)
        db.log_event(conn, e["clip_slug"], "decors", f"Image HD lancée : {e['name']}{' (' + state + ')' if state else ''}")
    return {"image_id": cur.lastrowid, "cost_usd": cost}


def _launch_free_hd(conn: sqlite3.Connection, e: dict, state: str | None, prompt: str | None, model: str,
                    clip: dict) -> dict:
    """Image « HD » sur un modèle gratuit choisi par Michael (son clic vaut accord) : proposée à côté des autres."""
    from . import image_models
    from .production import BACKGROUND, with_style
    try:
        m = image_models.check(model)
    except image_models.ModelError as exc:
        raise ProductionError(str(exc)) from exc
    drafts = _draft_for_state(conn, e["id"], state) or _draft_for_state(conn, e["id"], None)
    refs = (drafts[-1:] + _refs(conn, e["id"], state, limit=2))[:min(3, m["refs"])]
    text = with_style(prompt or generation_prompt(e, state, from_draft=bool(drafts)), clip)
    w, h = HD_FREE_SIZE[e["kind"]]
    with db.tx(conn):
        cancel_pending(conn, e["id"], "remplacée par une génération lancée par Michael")
        cur = conn.execute(
            "INSERT INTO element_images (element_id, state, source, label, prompt, model_key, cost_usd, funding, "
            "status, role, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (e["id"], state, "gen", state or "référence", text, model, 0, "free", "generating", "hd", db.now()))
        image_id = cur.lastrowid
        db.log_event(conn, e["clip_slug"], "decors", f"Image HD lancée sur {m['label']} : {e['name']}")
    out = absp(e["dir"]) / f"{slugify(state or 'base')}-gratuit-{image_id}.png"

    def run() -> None:
        c = db.connect()
        try:
            image_models.run_free(model, text, refs, out, w, h)
            c.execute("UPDATE element_images SET status='proposed', path=? WHERE id=?", (rel(out), image_id))
        except image_models.ModelError as exc:
            c.execute("UPDATE element_images SET status='failed', error=? WHERE id=?", (str(exc)[:700], image_id))
        c.commit()

    if BACKGROUND:
        import threading
        threading.Thread(target=run, daemon=True).start()
    else:
        run()
    return {"image_id": image_id, "cost_usd": 0, "free": True}


HD_FREE_SIZE = {"decor": (1280, 720), "objet": (1024, 1024), "figurant": (832, 1216)}
DRAFT_SIZE = {"decor": (1024, 576), "objet": (768, 768), "figurant": (640, 896)}
KIND_EN = {"decor": "location", "objet": "object", "figurant": "person or animal"}


def set_brief(conn: sqlite3.Connection, element_id: int, text: str) -> dict:
    _element(conn, element_id)
    conn.execute("UPDATE elements SET brief=? WHERE id=?", (text.strip() or None, element_id))
    return _element(conn, element_id)


def draft_prompt(e: dict, brief: str, n_refs: int) -> str:
    """Le texte des brouillons : la direction de Michael d'abord, ses images ensuite, la fiche en appui."""
    parts = [f"A single realistic draft photograph of a {KIND_EN[e['kind']]}: {e['name']}."]
    if brief.strip():
        parts.append(f"Director's direction (French, follow it first): {brief.strip()}")
    if n_refs:
        parts.append(f"Use the {n_refs} reference image{'s' if n_refs > 1 else ''} (image 0"
                     + "".join(f", image {i}" for i in range(1, n_refs)) + ") as inspiration: "
                     "combine them into one coherent picture as the direction says.")
    if not n_refs and not brief.strip() and (e.get("description") or "").strip():
        # la fiche ne sert qu'en dernier recours : elle ne doit jamais contredire les images ou l'instruction
        parts.append(f"Appearance notes (French): {e['description'].strip()}")
    parts.append({"decor": "Wide establishing view, no people.",
                  "objet": "The whole object, alone, plain neutral background.",
                  "figurant": "Alone, full body, standing still, neutral background."}[e["kind"]])
    parts.append("Natural light, photographic look. No text, no watermark.")
    return " ".join(parts)


# Brouillons : toutes les options gratuites, de la meilleure à la plus simple. Quand une option
# a épuisé son quota du jour (ou échoue), la suivante prend le relais.
DRAFT_CHAIN = [("cloudflare", "klein-9b", "FLUX.2 klein 9B (Cloudflare)"),
               ("huggingface", "flux2-dev", "FLUX.2 dev (Hugging Face)"),
               ("huggingface", "kontext-dev", "FLUX.1 Kontext (Hugging Face)"),
               ("cloudflare", "flux-2-dev", "FLUX.2 dev (Cloudflare)"),
               ("cloudflare", "klein-4b", "FLUX.2 klein 4B (Cloudflare)")]


def draft_backends() -> list[tuple[str, str, str]]:
    return [b for b in DRAFT_CHAIN if routing.provider_usable(b[0])]


def _draft_one(backend: tuple[str, str, str], text: str, inspi: list[Path], out: Path, w: int, h: int) -> None:
    import random
    from .providers import cloudflare, hfspace
    seed = random.randint(1, 2**31 - 1)
    if backend[0] == "cloudflare":
        cloudflare.generate(text, inspi, out, width=w, height=h, seed=seed, model=backend[1])
    else:
        hfspace.generate(backend[1], text, inspi, out, width=w, height=h, seed=seed)


def _run_drafts(element_id: int, ids: list[int], text: str, inspi: list[Path], w: int, h: int,
                only: str | None = None) -> None:
    """Brouillons sur le modèle choisi par Michael (`only`), et lui seul : en cas d'échec, l'erreur s'affiche."""
    from . import image_models
    conn = db.connect()
    e = _element(conn, element_id)
    model = only or image_models.default(e["kind"]) or "cloudflare:klein-9b"
    label = image_models.get(model)["label"] if model in {m["id"] for m in image_models.catalog()} else model
    made, error = 0, None
    for image_id in ids:
        if error:
            conn.execute("UPDATE element_images SET status='failed', error=? WHERE id=?", (error[:700], image_id))
            conn.commit()
            continue
        out = absp(e["dir"]) / "brouillons" / f"brouillon-{db.now()[:19].replace(':', '').replace('-', '')}-{image_id}.png"
        try:
            image_models.run_free(model, text, inspi, out, w, h)
        except image_models.ModelError as exc:
            error = str(exc)
            conn.execute("UPDATE element_images SET status='failed', error=? WHERE id=?", (error[:700], image_id))
            conn.commit()
            continue
        conn.execute("UPDATE element_images SET status='proposed', path=?, model_key=?, label=? WHERE id=?",
                     (rel(out), model, f"brouillon · {label}", image_id))
        conn.commit()
        made += 1
    db.log_event(conn, e["clip_slug"], "decors",
                 f"{made} brouillon(s) gratuit(s) : {e['name']}" + (f" ({len(ids) - made} en échec : {error[:160]})" if error else ""))
    conn.commit()


def launch_drafts(conn: sqlite3.Connection, element_id: int, brief: str | None = None, n: int = 2,
                  background: bool = True, backend: str | None = None) -> dict:
    """Brouillons gratuits à partir des images et de l'instruction de Michael.

    Les images arrivent en arrière-plan (de quelques secondes à deux minutes), à choisir ensuite."""
    e = _element(conn, element_id)
    if brief is not None:
        set_brief(conn, element_id, brief)
        e = _element(conn, element_id)
    from . import image_models
    backend = backend or image_models.default(e["kind"])
    if not backend:
        raise ProductionError("Aucun modèle d'image branché (page Fournisseurs)")
    try:
        if not image_models.check(backend)["free"]:
            raise ProductionError("Les brouillons passent par un modèle gratuit : choisis-en un (le payant sert à l'image HD)")
    except image_models.ModelError as exc:
        raise ProductionError(str(exc)) from exc
    rows = [r for r in conn.execute(
        "SELECT id, path FROM element_images WHERE element_id=? AND role='inspi' AND status='kept' AND path IS NOT NULL "
        "ORDER BY id DESC", (element_id,)).fetchall() if absp(r["path"]) and absp(r["path"]).is_file()][:4]
    rows.reverse()   # les 4 plus récentes, dans l'ordre où Michael les a déposées
    inspi = [absp(r["path"]) for r in rows]
    used = json.dumps([r["id"] for r in rows])
    if not inspi and not (e.get("brief") or "").strip():
        raise ProductionError("Ajoute des images ou écris ton instruction")
    from .production import with_style
    text = with_style(draft_prompt(e, e.get("brief") or "", len(inspi)), db.get_clip(conn, e["clip_slug"]))
    w, h = DRAFT_SIZE[e["kind"]]
    ids = []
    with db.tx(conn):
        for _ in range(max(1, min(n, 4))):
            cur = conn.execute(
                "INSERT INTO element_images (element_id, source, label, prompt, model_key, cost_usd, funding, status, "
                "role, created_at, from_ids) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (element_id, "gen", "brouillon", text, backend, 0, "free", "generating", "draft", db.now(), used))
            ids.append(cur.lastrowid)
    if background:
        import threading
        threading.Thread(target=_run_drafts, args=(element_id, ids, text, inspi, w, h, backend or None),
                         daemon=True).start()
    else:
        _run_drafts(element_id, ids, text, inspi, w, h, backend or None)
    return {"images": ids, "cost_usd": 0}


def launch_ready(conn: sqlite3.Connection, clip_slug: str) -> dict:
    """Michael lance d'un coup l'image HD de chaque élément qui a une image de départ et pas encore d'HD."""
    n, total = 0, 0.0
    for e in clip_elements(conn, clip_slug):
        if e["step"] == "hd_todo" and e.get("prompt_status") != "requested":
            r = launch_image(conn, e["id"], None, approved=True)
            n += 1
            total += r["cost_usd"]
    return {"launched": n, "cost_usd": round(total, 3)}


def pick(conn: sqlite3.Connection, image_id: int, decision: str) -> None:
    """keep : l'image sert de référence. reject : écartée et supprimée (on ne garde que les réussites)."""
    img = db.row(conn.execute("SELECT * FROM element_images WHERE id=?", (image_id,)).fetchone())
    if img is None:
        raise ProductionError(f"Image inconnue : {image_id}")
    if decision == "keep":
        conn.execute("UPDATE element_images SET status='kept' WHERE id=?", (image_id,))
        if img["role"] == "draft":
            # un brouillon gardé devient l'image de départ : le décorateur écrit le prompt HD d'après lui
            cancel_pending(conn, img["element_id"], "remplacée : nouvelle image de départ")
            conn.execute("UPDATE elements SET prompt_status='requested' WHERE id=?", (img["element_id"],))
    elif decision == "reject":
        p = absp(img["path"])
        if p and p.is_file():
            p.unlink()
        conn.execute("UPDATE element_images SET status='rejected', path=NULL WHERE id=?", (image_id,))
    else:
        raise ProductionError(f"Décision inconnue : {decision}")


def link(conn: sqlite3.Connection, shot_ids: list[int], element_id: int, state: str | None = None,
         manual: bool = False) -> int:
    """Lien posé par le décorateur (gardé) ou à la main dans le panneau du plan (gardé) ; les liens nés
    d'un @ dans le texte suivent le texte (voir link_mentions)."""
    e = _element(conn, element_id)
    n = 0
    for sid in shot_ids:
        shot = db.get_shot(conn, sid)
        if shot["clip_slug"] != e["clip_slug"]:
            raise ProductionError(f"Le plan {sid} n'est pas dans le clip {e['clip_slug']}")
        conn.execute("INSERT INTO shot_elements (shot_id, element_id, state, manual) VALUES (?,?,?,?) "
                     "ON CONFLICT(shot_id, element_id) DO UPDATE SET state=excluded.state, manual=MAX(manual, excluded.manual)",
                     (sid, element_id, state, 1 if manual else 2))
        n += 1
    return n


def unlink(conn: sqlite3.Connection, shot_id: int, element_id: int) -> None:
    conn.execute("DELETE FROM shot_elements WHERE shot_id=? AND element_id=?", (shot_id, element_id))


def for_shot(conn: sqlite3.Connection, shot_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT e.*, se.state AS shot_state FROM shot_elements se JOIN elements e ON e.id=se.element_id "
        "WHERE se.shot_id=? ORDER BY CASE e.kind WHEN 'decor' THEN 0 WHEN 'figurant' THEN 1 ELSE 2 END, e.name",
        (shot_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["states"] = json.loads(d["states"] or "[]")
        # la HD gardée sert de référence ; à défaut, le brouillon gardé (rien n'est bloquant)
        d["refs"] = [rel(p) for p in (_refs(conn, d["id"], d["shot_state"], limit=2)
                                      or _refs(conn, d["id"], d["shot_state"], limit=2, role="draft"))]
        out.append(d)
    return out


def shot_context(conn: sqlite3.Connection, shot_id: int) -> tuple[list[Path], str]:
    """Pour le visuel d'un plan : les images de référence et le texte à ajouter au prompt."""
    refs: list[Path] = []
    lines = []
    for e in for_shot(conn, shot_id):
        refs += [absp(p) for p in e["refs"][: (2 if e["kind"] == "decor" else 1)]]
        lines.append(f"- {KIND_LABEL[e['kind']]} « {e['name']} » (@{e['slug']})"
                     + (f" ({e['shot_state']})" if e["shot_state"] else "")
                     + f" : {(e['description'] or '').strip()}")
    text = ("\n\nSetting, props and secondary characters (keep them exactly as in their reference images):\n"
            + "\n".join(lines)) if lines else ""
    return refs, text


def missing_refs(conn: sqlite3.Connection, shot_id: int) -> list[str]:
    """Éléments du plan qui n'ont encore aucune image HD gardée : le visuel du plan doit les attendre."""
    return [e["name"] for e in for_shot(conn, shot_id) if not e["refs"]]


def _step(images: list[dict]) -> str:
    """Où en est l'élément : start (rien), hd_todo (départ fourni, HD à faire), hd_wait (HD en cours ou à choisir), done."""
    hd_kept = [i for i in images if i["role"] == "hd" and i["status"] == "kept"]
    if hd_kept:
        return "done"
    if any(i["role"] == "hd" and i["status"] in ("generating", "proposed") for i in images):
        return "hd_wait"
    if any(i["role"] == "draft" and i["status"] == "kept" for i in images):
        return "hd_todo"
    if any(i["role"] == "draft" for i in images):
        return "draft_choose"
    return "start"


def clip_elements(conn: sqlite3.Connection, clip_slug: str) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM elements WHERE clip_slug=? ORDER BY CASE kind WHEN 'decor' THEN 0 "
                          "WHEN 'figurant' THEN 1 ELSE 2 END, id", (clip_slug,)).fetchall():
        e = dict(r)
        e["states"] = json.loads(e["states"] or "[]")
        e["images"] = db.rows(conn.execute(
            "SELECT id, state, source, role, path, label, status, cost_usd, model_key, error, from_ids FROM element_images "
            "WHERE element_id=? AND status IN ('generating','proposed','kept','failed') ORDER BY id", (e["id"],)).fetchall())
        e["shots"] = [x["num"] for x in conn.execute(
            "SELECT s.num FROM shot_elements se JOIN shots s ON s.id=se.shot_id WHERE se.element_id=? ORDER BY s.num",
            (e["id"],)).fetchall()]
        has_draft = any(i["role"] == "draft" and i["status"] == "kept" for i in e["images"])
        e["step"] = _step(e["images"])
        e["prompt_default"] = proposed_prompt(e, has_draft)
        e["prompt_text"] = (e.get("prompt") or "").strip() or e["prompt_default"]
        e["prompt_edited"] = bool((e.get("prompt") or "").strip())
        e["prompt_by"] = ("michael" if e["prompt_edited"] else "agent" if (e.get("prompt_agent") or "").strip()
                          else "default")
        e["draft_paths"] = [i["path"] for i in e["images"] if i["role"] == "draft" and i["status"] == "kept"]
        out.append(e)
    return out


def index(conn: sqlite3.Connection, clip_slug: str) -> list[dict]:
    """Liste courte pour les références @ dans les plans."""
    out = []
    for r in conn.execute("SELECT id, kind, slug, name, states FROM elements WHERE clip_slug=? "
                          "ORDER BY CASE kind WHEN 'decor' THEN 0 WHEN 'figurant' THEN 1 ELSE 2 END, id",
                          (clip_slug,)).fetchall():
        hd = _refs(conn, r["id"], None, limit=1)
        thumb = hd or _refs(conn, r["id"], None, limit=1, role="draft")
        # ce qui part au modèle avec ce plan : l'image HD gardée, sinon le brouillon gardé, sinon rien
        out.append({"id": r["id"], "kind": r["kind"], "slug": r["slug"], "name": r["name"],
                    "states": json.loads(r["states"] or "[]"), "thumb": rel(thumb[0]) if thumb else None,
                    "sent": "hd" if hd else "brouillon" if thumb else None})
    return out


MENTION = re.compile(r"@([a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9])")


def link_mentions(conn: sqlite3.Connection, shot_id: int) -> list[str]:
    """Les @ du texte d'un plan (ce qu'on voit, prompt détaillé) font foi : chaque @ cité relie le plan
    à son élément, sa tenue ou son personnage ; un lien qui n'est plus cité est retiré, sauf s'il a été
    ajouté à la main dans le panneau du plan."""
    shot = db.get_shot(conn, shot_id)
    text = f"{shot.get('description') or ''}\n{shot.get('detail') or ''}".lower()
    cited = set(MENTION.findall(text))
    for r in conn.execute("SELECT se.element_id, e.slug FROM shot_elements se JOIN elements e ON e.id=se.element_id "
                          "WHERE se.shot_id=? AND se.manual=0", (shot_id,)).fetchall():
        if r["slug"] not in cited:
            conn.execute("DELETE FROM shot_elements WHERE shot_id=? AND element_id=?", (shot_id, r["element_id"]))
    looks = shot.get("looks")
    looks = json.loads(looks) if isinstance(looks, str) and looks else dict(looks or {})
    kept = looks if shot.get("looks_manual") else {c: l for c, l in looks.items() if f"{c}-{l}" in cited}
    if kept != looks:
        conn.execute("UPDATE shots SET looks=? WHERE id=?", (json.dumps(kept) if kept else None, shot_id))
    linked = []
    for slug in dict.fromkeys(MENTION.findall(text)):
        r = conn.execute("SELECT id FROM elements WHERE clip_slug=? AND slug=?", (shot["clip_slug"], slug)).fetchone()
        if not r and conn.execute("SELECT 1 FROM characters WHERE slug=?", (slug,)).fetchone():
            add_character(conn, shot_id, slug)   # un vrai personnage du studio, pas un figurant
            linked.append(slug)
            continue
        lk = None if r else conn.execute(
            "SELECT character_slug, slug FROM looks WHERE character_slug || '-' || slug = ?", (slug,)).fetchone()
        if lk:   # une tenue : le personnage joue dans le plan, dans cette tenue
            add_character(conn, shot_id, lk["character_slug"])
            set_shot_look(conn, shot_id, lk["character_slug"], lk["slug"])
            linked.append(slug)
            continue
        if r:
            conn.execute("INSERT OR IGNORE INTO shot_elements (shot_id, element_id, state) VALUES (?,?,NULL)",
                         (shot_id, r["id"]))
            linked.append(slug)
    return linked


def add_character(conn: sqlite3.Connection, shot_id: int, slug: str) -> None:
    """Le personnage joue dans ce plan : casté dans le clip si besoin, ajouté aux personnages du plan."""
    from .production import cast_for_mention
    shot = db.get_shot(conn, shot_id)
    cast_for_mention(conn, shot["clip_slug"], slug)
    chars = json.loads(shot.get("characters") or "[]") if isinstance(shot.get("characters"), str) else list(shot.get("characters") or [])
    if slug not in chars:
        chars.append(slug)
        conn.execute("UPDATE shots SET characters=? WHERE id=?", (json.dumps(chars), shot_id))


def set_shot_look(conn: sqlite3.Connection, shot_id: int, character_slug: str, look_slug: str | None) -> None:
    shot = db.get_shot(conn, shot_id)
    looks = shot.get("looks")
    looks = json.loads(looks) if isinstance(looks, str) and looks else dict(looks or {})
    if look_slug:
        looks[character_slug] = look_slug
    else:
        looks.pop(character_slug, None)
    conn.execute("UPDATE shots SET looks=? WHERE id=?", (json.dumps(looks) if looks else None, shot_id))


def remove_character(conn: sqlite3.Connection, shot_id: int, slug: str) -> None:
    shot = db.get_shot(conn, shot_id)
    chars = json.loads(shot.get("characters") or "[]") if isinstance(shot.get("characters"), str) else list(shot.get("characters") or [])
    conn.execute("UPDATE shots SET characters=? WHERE id=?", (json.dumps([c for c in chars if c != slug]), shot_id))


def request(conn: sqlite3.Connection, clip_slug: str) -> None:
    """Michael demande à l'agent décorateur de repérer (ou compléter) les éléments du clip."""
    db.get_clip(conn, clip_slug)
    conn.execute("UPDATE clips SET decors_status='requested', updated_at=? WHERE slug=?", (db.now(), clip_slug))
    db.log_event(conn, clip_slug, "decors", "Repérage des décors demandé")


def done(conn: sqlite3.Connection, clip_slug: str) -> None:
    conn.execute("UPDATE clips SET decors_status='done', updated_at=? WHERE slug=?", (db.now(), clip_slug))
    db.log_event(conn, clip_slug, "decors", "Décors, objets et figurants repérés")


def on_job_done(conn: sqlite3.Connection, job: dict, result: dict) -> None:
    img = db.row(conn.execute("SELECT * FROM element_images WHERE id=?", (job["target_id"],)).fetchone())
    mcfg = routing.model(img["model_key"])
    url = routing.extract_output(result, mcfg["output"])
    dest = absp(job["output_path"])
    providers.download(url, dest, job.get("provider") or "fal")
    with db.tx(conn):
        conn.execute("UPDATE element_images SET status='proposed', path=?, remote_url=? WHERE id=?",
                     (rel(dest), url, img["id"]))
        conn.execute("UPDATE jobs SET status='done', updated_at=? WHERE id=?", (db.now(), job["id"]))
