"""Décors, objets clés et figurants d'un clip.

Un visuel de plan n'est cohérent avec les autres que si le lieu, les objets et les
personnages secondaires sont toujours les mêmes. Chaque élément a donc :
- une fiche (description fixe : plan des lieux, matières, couleurs, lumière) ;
- des états quand il change (ex. jardin « intact le matin », « vide au retour ») ;
- des images : celles que Michael dépose (source) et celles générées à partir de
  la fiche et de ses images ; Michael garde les bonnes (status 'kept') ;
- les plans où il apparaît (shot_elements).

Quand un visuel de plan est généré, les images gardées de ses éléments partent en
référence et leurs fiches sont ajoutées au prompt (voir production.launch_image).
Si Michael ne fournit rien, l'agent décorateur repère les éléments du découpage,
écrit leurs fiches et relie les plans ; les images attendent ensuite son accord.
"""

from __future__ import annotations

import json
import shutil
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


def add_image(conn: sqlite3.Connection, element_id: int, src: str | Path, state: str | None = None,
              label: str | None = None) -> dict:
    """Image déposée par Michael : elle sert de source aux générations, et de référence telle quelle."""
    e = _element(conn, element_id)
    src = Path(src)
    if src.suffix.lower() not in IMAGE_EXT:
        raise ProductionError("Une image est attendue (png, jpg, webp)")
    dest = _free_name(absp(e["dir"]) / "sources" / f"{slugify(src.stem) or 'image'}{src.suffix.lower()}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    cur = conn.execute(
        "INSERT INTO element_images (element_id, state, source, path, label, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (element_id, state or None, "michael", rel(dest), label or src.stem, "kept", db.now()))
    return db.row(conn.execute("SELECT * FROM element_images WHERE id=?", (cur.lastrowid,)).fetchone())


def _refs(conn: sqlite3.Connection, element_id: int, state: str | None, limit: int = 4) -> list[Path]:
    """Images gardées de l'élément : celles de l'état demandé d'abord, puis l'état de base."""
    rows = conn.execute(
        "SELECT path, state, source FROM element_images WHERE element_id=? AND status='kept' AND path IS NOT NULL "
        "ORDER BY (COALESCE(state,'')=COALESCE(?,'')) DESC, (state IS NULL) DESC, (source='gen') DESC, id",
        (element_id, state)).fetchall()
    out = [absp(r["path"]) for r in rows]
    return [p for p in out if p and p.is_file()][:limit]


def generation_prompt(e: dict, state: str | None, extra: str = "") -> str:
    kind = e["kind"]
    what = {"decor": "a photographic reference plate of this location, wide establishing view, no people",
            "objet": "a product-style photographic reference of this object, plain neutral background, whole object visible",
            "figurant": "a photographic character reference of this person or animal, full body, neutral background"}[kind]
    return (f"Create {what}. Photorealistic, natural light, true-to-life colors, consistent with any reference images. "
            f"\n\nDescription (French, authoritative):\n{e['description'] or e['name']}"
            + (f"\n\nState of the place in this image: {state}" if state else "")
            + (f"\n\nDirector's notes: {extra}" if extra else ""))


def launch_image(conn: sqlite3.Connection, element_id: int, state: str | None = None, prompt: str | None = None,
                 approved: bool = False) -> dict:
    """Génère une image de référence de l'élément (accord de Michael d'abord)."""
    e = _element(conn, element_id)
    clip = db.get_clip(conn, e["clip_slug"])
    key = routing.pick_model("casting")
    mcfg = routing.model(key)
    refs = _refs(conn, element_id, state)
    text = prompt or generation_prompt(e, state)
    cost = routing.estimate_cost(mcfg, mode="final")
    if _needs_approval(mcfg.get("provider", "fal"), cost, False, approved):
        return _ask_spend(conn, "element_image", {"element_id": element_id, "state": state, "prompt": prompt},
                          _hash(element_id, state, text, [str(p) for p in refs]),
                          f"{KIND_LABEL[e['kind']]} « {e['name']} »{' (' + state + ')' if state else ''} : image de référence",
                          cost, mcfg, key, detail=text, clip_slug=e["clip_slug"])
    payload = routing.build_payload(mcfg, prompt=text, image_urls=[fal.to_data_uri(p) for p in refs], mode="final",
                                    aspect_ratio=ASPECT[e["kind"]] or clip["aspect_ratio"])
    sub = providers.submit(mcfg, payload, kind="image", label=f"{e['slug']} {state or ''}")
    out = absp(e["dir"]) / f"{slugify(state or 'base')}-{sub['request_id'][-6:]}.png"
    with db.tx(conn):
        cur = conn.execute(
            "INSERT INTO element_images (element_id, state, source, path, label, prompt, model_key, cost_usd, funding, "
            "status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (element_id, state, "gen", rel(out), state or "référence", text, key, cost,
             credits.funding_for(conn, mcfg.get("provider", "fal"), cost), "generating", db.now()))
        _insert_job(conn, "element_images", cur.lastrowid, mcfg["endpoint"], sub, out)
    return {"image_id": cur.lastrowid, "cost_usd": cost}


def pick(conn: sqlite3.Connection, image_id: int, decision: str) -> None:
    """keep : l'image sert de référence. reject : écartée et supprimée (on ne garde que les réussites)."""
    img = db.row(conn.execute("SELECT * FROM element_images WHERE id=?", (image_id,)).fetchone())
    if img is None:
        raise ProductionError(f"Image inconnue : {image_id}")
    if decision == "keep":
        conn.execute("UPDATE element_images SET status='kept' WHERE id=?", (image_id,))
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
        lines.append(f"- {KIND_LABEL[e['kind']]} « {e['name']} »"
                     + (f" ({e['shot_state']})" if e["shot_state"] else "")
                     + f" : {(e['description'] or '').strip()}")
    text = ("\n\nSetting, props and secondary characters (keep them exactly as in their reference images):\n"
            + "\n".join(lines)) if lines else ""
    return refs, text


def missing_refs(conn: sqlite3.Connection, shot_id: int) -> list[str]:
    """Éléments du plan qui n'ont encore aucune image gardée : le visuel du plan doit les attendre."""
    return [e["name"] for e in for_shot(conn, shot_id) if not e["refs"]]


def clip_elements(conn: sqlite3.Connection, clip_slug: str) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM elements WHERE clip_slug=? ORDER BY CASE kind WHEN 'decor' THEN 0 "
                          "WHEN 'figurant' THEN 1 ELSE 2 END, name", (clip_slug,)).fetchall():
        e = dict(r)
        e["states"] = json.loads(e["states"] or "[]")
        e["images"] = db.rows(conn.execute(
            "SELECT id, state, source, path, label, status, cost_usd, model_key FROM element_images "
            "WHERE element_id=? AND status IN ('generating','proposed','kept') ORDER BY id", (e["id"],)).fetchall())
        e["shots"] = [x["num"] for x in conn.execute(
            "SELECT s.num FROM shot_elements se JOIN shots s ON s.id=se.shot_id WHERE se.element_id=? ORDER BY s.num",
            (e["id"],)).fetchall()]
        out.append(e)
    return out


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
