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
    dest = _free_name(absp(e["dir"]) / folder / f"{slugify(src.stem) or 'image'}{src.suffix.lower()}")
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
                 approved: bool = False) -> dict:
    """Génère l'image HD de l'élément, à partir de l'image de départ de Michael quand il y en a une.

    Références envoyées : l'image de départ de cet état, puis les images HD déjà gardées
    (l'état de base garde le lieu identique d'un état à l'autre)."""
    e = _element(conn, element_id)
    clip = db.get_clip(conn, e["clip_slug"])
    key, mcfg, cost = hd_model()
    drafts = _draft_for_state(conn, element_id, state)
    if not drafts and state:
        drafts = _draft_for_state(conn, element_id, None)
    refs = (drafts[-1:] + _refs(conn, element_id, state, limit=2))[:3]   # une seule image de départ : sa composition
    text = prompt or generation_prompt(e, state, from_draft=bool(drafts))
    if _needs_approval(mcfg.get("provider", "fal"), cost, False, approved):
        return _ask_spend(conn, "element_image", {"element_id": element_id, "state": state, "prompt": prompt},
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
DRAFT_CHAIN = [("huggingface", "qwen-edit-2511", "Qwen Image Edit (Hugging Face)"),
               ("huggingface", "flux2-dev", "FLUX.2 dev (Hugging Face)"),
               ("cloudflare", "klein-9b", "FLUX.2 klein 9B (Cloudflare)"),
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


def _run_drafts(element_id: int, ids: list[int], text: str, inspi: list[Path], w: int, h: int) -> None:
    from .providers._http import ProviderError
    conn = db.connect()
    e = _element(conn, element_id)
    dead: set[tuple] = set()
    made, errors = 0, []
    for image_id in ids:
        out = _free_name(absp(e["dir"]) / "brouillons" / f"brouillon-{db.now()[:10]}.png")
        done = False
        for b in draft_backends():
            if b in dead:
                continue
            try:
                _draft_one(b, text, inspi, out, w, h)
            except (ProviderError, OSError, subprocess.CalledProcessError, ValueError) as exc:
                dead.add(b)
                errors.append(f"{b[2]} : {exc}")
                continue
            conn.execute("UPDATE element_images SET status='proposed', path=?, model_key=?, label=? WHERE id=?",
                         (rel(out), f"{b[0]}:{b[1]}", f"brouillon · {b[2]}", image_id))
            conn.commit()
            done, made = True, made + 1
            break
        if not done:
            conn.execute("UPDATE element_images SET status='failed', error=? WHERE id=?",
                         ("; ".join(errors[-3:])[:500] or "aucune option gratuite disponible", image_id))
            conn.commit()
    db.log_event(conn, e["clip_slug"], "decors",
                 f"{made} brouillon(s) gratuit(s) : {e['name']}" + (f" ({len(ids) - made} en échec)" if made < len(ids) else ""))
    conn.commit()


def launch_drafts(conn: sqlite3.Connection, element_id: int, brief: str | None = None, n: int = 2,
                  background: bool = True) -> dict:
    """Brouillons gratuits à partir des images et de l'instruction de Michael.

    Les images arrivent en arrière-plan (de quelques secondes à deux minutes), à choisir ensuite."""
    e = _element(conn, element_id)
    if brief is not None:
        set_brief(conn, element_id, brief)
        e = _element(conn, element_id)
    if not draft_backends():
        raise ProductionError("Aucune option gratuite de brouillon n'est branchée (page Fournisseurs)")
    inspi = [p for p in (absp(r["path"]) for r in conn.execute(
        "SELECT path FROM element_images WHERE element_id=? AND role='inspi' AND status='kept' AND path IS NOT NULL "
        "ORDER BY id", (element_id,)).fetchall()) if p and p.is_file()][:4]
    if not inspi and not (e.get("brief") or "").strip():
        raise ProductionError("Ajoute des images ou écris ton instruction")
    text = draft_prompt(e, e.get("brief") or "", len(inspi))
    w, h = DRAFT_SIZE[e["kind"]]
    ids = []
    with db.tx(conn):
        for _ in range(max(1, min(n, 4))):
            cur = conn.execute(
                "INSERT INTO element_images (element_id, source, label, prompt, model_key, cost_usd, funding, status, "
                "role, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (element_id, "gen", "brouillon", text, "gratuit", 0, "free", "generating", "draft", db.now()))
            ids.append(cur.lastrowid)
    if background:
        import threading
        threading.Thread(target=_run_drafts, args=(element_id, ids, text, inspi, w, h), daemon=True).start()
    else:
        _run_drafts(element_id, ids, text, inspi, w, h)
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


def link(conn: sqlite3.Connection, shot_ids: list[int], element_id: int, state: str | None = None) -> int:
    e = _element(conn, element_id)
    n = 0
    for sid in shot_ids:
        shot = db.get_shot(conn, sid)
        if shot["clip_slug"] != e["clip_slug"]:
            raise ProductionError(f"Le plan {sid} n'est pas dans le clip {e['clip_slug']}")
        conn.execute("INSERT INTO shot_elements (shot_id, element_id, state) VALUES (?,?,?) "
                     "ON CONFLICT(shot_id, element_id) DO UPDATE SET state=excluded.state", (sid, element_id, state))
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
        d["refs"] = [rel(p) for p in _refs(conn, d["id"], d["shot_state"], limit=2)]
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
            "SELECT id, state, source, role, path, label, status, cost_usd, model_key, error FROM element_images "
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
        thumb = _refs(conn, r["id"], None, limit=1) or _refs(conn, r["id"], None, limit=1, role="draft")
        out.append({"id": r["id"], "kind": r["kind"], "slug": r["slug"], "name": r["name"],
                    "states": json.loads(r["states"] or "[]"), "thumb": rel(thumb[0]) if thumb else None})
    return out


MENTION = re.compile(r"@([a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9])")


def link_mentions(conn: sqlite3.Connection, shot_id: int) -> list[str]:
    """Chaque @slug écrit dans la ligne ou le prompt détaillé d'un plan relie ce plan à l'élément.
    Un lien existant garde son état ; retirer la mention ne retire pas le lien (le panneau du plan le fait)."""
    shot = db.get_shot(conn, shot_id)
    text = f"{shot.get('description') or ''}\n{shot.get('detail') or ''}".lower()
    linked = []
    for slug in dict.fromkeys(MENTION.findall(text)):
        r = conn.execute("SELECT id FROM elements WHERE clip_slug=? AND slug=?", (shot["clip_slug"], slug)).fetchone()
        if r:
            conn.execute("INSERT OR IGNORE INTO shot_elements (shot_id, element_id, state) VALUES (?,?,NULL)",
                         (shot_id, r["id"]))
            linked.append(slug)
    return linked


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
