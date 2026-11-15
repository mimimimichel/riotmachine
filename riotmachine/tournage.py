"""Tournage v3 : séquences, références, prompt assemblé, plan de tournage, prises.

PRODUCTION-PLANS-v3 §4 à §13. Les calculs sont dans `planner` (pur) et
`catalogue` (configuration) ; ce module lit et écrit la base.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any

from . import catalogue as cat
from . import db, planner, production

SHOT_ATTRS = {"jeu": ("aucun", "present", "porteur"), "composition": ("libre", "stricte"), "role_ab": ("A", "B")}
SEQ_FIELDS = {"name", "fiche", "profile", "offer_key", "options", "master_path"}


class TournageError(Exception):
    pass


# --- lecture ------------------------------------------------------------------------

def _json(v: Any, default: Any) -> Any:
    if v is None or v == "":
        return default
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (TypeError, json.JSONDecodeError):
        return default


def seq_row(conn: sqlite3.Connection, seq_id: int) -> dict:
    r = db.row(conn.execute("SELECT * FROM sequences WHERE id=?", (seq_id,)).fetchone())
    if not r:
        raise TournageError(f"Séquence {seq_id} inconnue")
    r["options"] = _json(r["options"], {})
    return r


def seq_shots(conn: sqlite3.Connection, seq_id: int) -> list[dict]:
    shots = db.rows(conn.execute(
        "SELECT s.*, b.num AS block_num, b.name AS block_name, COALESCE(b.validated,0) AS block_validated "
        "FROM shots s LEFT JOIN blocks b ON b.id=s.block_id WHERE s.sequence_id=? AND s.deleted_at IS NULL "
        "ORDER BY s.t_start", (seq_id,)).fetchall())
    for s in shots:
        s["looks"] = _json(s.get("looks"), {})
        s["shootable"] = bool(s["block_validated"])
    return shots


def _quality(conn: sqlite3.Connection, slug: str) -> str:
    r = conn.execute("SELECT quality FROM clips WHERE slug=?", (slug,)).fetchone()
    return (r["quality"] if r else None) or "brouillon"


def shot_taken(conn: sqlite3.Connection, shot_ids: list[int]) -> dict[int, str]:
    """Plans qui ont déjà une prise tournée (gardée ou à dérusher) -> offre de cette prise."""
    if not shot_ids:
        return {}
    marks = ",".join("?" * len(shot_ids))
    out = {}
    for r in conn.execute(f"SELECT ts.shot_id, t.offer_key FROM take_shots ts JOIN takes t ON t.id=ts.take_id "
                          f"WHERE ts.shot_id IN ({marks}) AND t.status='done' AND COALESCE(ts.verdict,'')!='redo' "
                          f"ORDER BY t.id", shot_ids):
        out[r["shot_id"]] = r["offer_key"]
    return out


# --- références (R-H7) -----------------------------------------------------------------

REF_PRIORITY = {"visage": 0, "maitresse": 1, "pied": 2, "tenue": 3, "objet": 4, "decor": 5, "autre": 6}
CHAR_KIND = {"canon": "visage", "details": "visage", "expressions": "visage", "fullbody": "pied", "canon_body": "pied",
             "turnaround": "pied", "sheet": "pied", "lighting": "autre"}


def ref_status(conn: sqlite3.Connection, path: str, provider: str) -> str:
    r = conn.execute("SELECT status FROM ref_status WHERE path=? AND provider=?", (path, provider)).fetchone()
    return r["status"] if r else "untested"


def set_ref_status(conn: sqlite3.Connection, path: str, provider: str, status: str, note: str = "") -> None:
    conn.execute("INSERT INTO ref_status (path, provider, status, note, updated_at) VALUES (?,?,?,?,?) "
                 "ON CONFLICT(path, provider) DO UPDATE SET status=excluded.status, note=excluded.note, "
                 "updated_at=excluded.updated_at", (path, provider, status, note, db.now()))


def ref_candidates(conn: sqlite3.Connection, seq: dict, shots: list[dict], provider: str) -> list[dict]:
    """Images que Michael a choisies pour ce clip et qui peuvent partir en référence.
    Jamais une image « inspiration seulement » (R-L3, R-H7)."""
    slug = seq["clip_slug"]
    out: list[dict] = []
    seen: set[str] = set()

    def add(path: str | None, kind: str, who: str, label: str) -> None:
        if not path or path in seen or "/inspiration/" in path:
            return
        p = production.absp(path)
        if not p or not p.is_file():
            return
        seen.add(path)
        out.append({"path": path, "kind": kind, "who": who, "label": label,
                    "status": ref_status(conn, path, provider)})

    if seq.get("master_path"):
        add(seq["master_path"], "maitresse", "séquence", "image maîtresse")
    chars = sorted({c for s in shots for c in (s.get("characters") or [])})
    casting = {r["character_slug"]: r for r in conn.execute("SELECT * FROM castings WHERE clip_slug=?", (slug,))}
    for ch in chars:
        cast = casting.get(ch)
        if not cast:
            continue
        v = conn.execute("SELECT id FROM character_versions WHERE character_slug=? AND version=?",
                         (ch, cast["version"])).fetchone()
        if v:
            for a in conn.execute("SELECT kind, path FROM character_assets WHERE version_id=? AND status='kept' "
                                  "AND path IS NOT NULL ORDER BY id", (v["id"],)):
                add(a["path"], CHAR_KIND.get(a["kind"], "autre"), ch, f"{ch} v{cast['version']} · {a['kind']}")
        looks = {s["looks"].get(ch) for s in shots if s["looks"].get(ch)} | ({cast["look_slug"]} if cast["look_slug"] else set())
        for lk in sorted(x for x in looks if x):
            from . import look_sheets
            for p in look_sheets.refs(conn, ch, lk):
                add(production.rel(p), "tenue", ch, f"tenue {lk}")
    ids = [s["id"] for s in shots]
    if ids:
        marks = ",".join("?" * len(ids))
        for e in conn.execute(f"SELECT DISTINCT e.id, e.kind, e.name, e.slug FROM shot_elements se JOIN elements e "
                              f"ON e.id=se.element_id WHERE se.shot_id IN ({marks}) ORDER BY e.kind, e.name", ids):
            for i in conn.execute("SELECT path FROM element_images WHERE element_id=? AND status='kept' "
                                  "AND COALESCE(role,'')!='inspi' ORDER BY id DESC", (e["id"],)):
                add(i["path"], "objet" if e["kind"] == "objet" else "decor" if e["kind"] == "decor" else "autre",
                    e["slug"], e["name"])
    out.sort(key=lambda r: (REF_PRIORITY.get(r["kind"], 9), r["who"], r["path"]))
    return out


def element_gaps(conn: sqlite3.Connection, shots: list[dict]) -> list[str]:
    """Objets et décors liés aux plans qui n'ont aucune image utilisable (seulement de l'inspiration)."""
    ids = [s["id"] for s in shots]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    out = []
    for e in conn.execute(f"SELECT DISTINCT e.id, e.name FROM shot_elements se JOIN elements e ON e.id=se.element_id "
                          f"WHERE se.shot_id IN ({marks})", ids):
        ok = conn.execute("SELECT 1 FROM element_images WHERE element_id=? AND status='kept' AND COALESCE(role,'')!='inspi'",
                          (e["id"],)).fetchone()
        if not ok:
            out.append(f"{e['name']} n'a pas d'image de référence (seulement de l'inspiration, ou rien) : "
                       "dans Références, choisis « Utiliser telle quelle » pour l'envoyer.")
    return out


def look_gaps(conn: sqlite3.Connection, shots: list[dict]) -> list[str]:
    """Plans où un personnage qui a des tenues n'en porte aucune : le modèle l'habillerait au hasard."""
    with_looks = {r[0] for r in conn.execute("SELECT DISTINCT character_slug FROM looks")}
    casting = {}
    if shots:
        casting = {r["character_slug"]: r["look_slug"] for r in conn.execute(
            "SELECT character_slug, look_slug FROM castings WHERE clip_slug=?", (shots[0]["clip_slug"],))}
    miss: dict[str, list[int]] = {}
    for s in shots:
        for ch in s.get("characters") or []:
            if ch in with_looks and not s["looks"].get(ch) and not casting.get(ch):
                miss.setdefault(ch, []).append(s["num"])
    return [f"{ch} n'a pas de tenue sur le{'s' if len(n) > 1 else ''} plan{'s' if len(n) > 1 else ''} "
            f"{', '.join(map(str, n))} : sans tenue, le modèle l'habille au hasard. Choisis-la dans le plan."
            for ch, n in miss.items()]


def pick_refs(cands: list[dict], max_refs: int, chosen: list[str] | None) -> list[dict]:
    """Sélection : le choix de Michael s'il existe, sinon par priorité ; jamais une image refusée."""
    usable = [c for c in cands if c["status"] not in ("refused_in", "refused_out")]
    if chosen:
        by = {c["path"]: c for c in usable}
        return [by[p] for p in chosen if p in by][:max_refs]
    picked, kinds = [], set()
    for c in usable:                      # un de chaque sorte d'abord (visage, maîtresse, pied, objet…)
        if c["kind"] not in kinds and len(picked) < max_refs:
            picked.append(c)
            kinds.add(c["kind"])
    for c in usable:
        if c not in picked and len(picked) < max_refs:
            picked.append(c)
    picked.sort(key=lambda r: REF_PRIORITY.get(r["kind"], 9))
    return picked


# --- prompt (R-H6) --------------------------------------------------------------------

DEFAULT_TRAPS = ["lock", "padlock", "shoot", "fire", "crash", "strike", "cast", "gun", "kill", "blow"]
DEFAULT_NEGATIVE = "extra hands, extra fingers, text, watermark, subtitles, morphing face, blurry, padlock"


def traps(text: str, words: list[str] | None = None) -> list[str]:
    words = words or DEFAULT_TRAPS
    found = []
    for w in words:
        if re.search(rf"\b{re.escape(w)}\w*", text or "", re.I):
            found.append(w)
    return found


def _mentions(conn: sqlite3.Connection, slug: str, text: str) -> str:
    names = {r["slug"]: r["name"] for r in conn.execute("SELECT slug, name FROM elements WHERE clip_slug=?", (slug,))}
    names.update({r["slug"]: r["name"] for r in conn.execute("SELECT slug, name FROM characters")})

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key in names:
            return names[key]
        if "-" in key and key.split("-", 1)[0] in names:   # @jj-black-tailor -> tenue de JJ
            return f"{names[key.split('-', 1)[0]]}'s {key.split('-', 1)[1].replace('-', ' ')} outfit"
        return key.replace("-", " ")
    return re.sub(r"@([a-z0-9][a-z0-9-]*)", sub, text or "")


def shot_action(conn: sqlite3.Connection, s: dict) -> str:
    """Bloc Action d'un plan : celui du prompteur ou de Michael, sinon le prompt détaillé du plan."""
    return (s.get("action_en") or _mentions(conn, s["clip_slug"], s.get("detail") or s.get("description") or "")).strip()


def _identity(conn: sqlite3.Connection, slug: str, shots: list[dict]) -> list[dict]:
    blocks = []
    chars = sorted({c for s in shots for c in (s.get("characters") or [])})
    casting = {r["character_slug"]: r for r in conn.execute("SELECT * FROM castings WHERE clip_slug=?", (slug,))}
    for ch in chars:
        cast = casting.get(ch)
        if not cast:
            continue
        txt = production.resume_text(conn, ch, cast["version"]) or _adn_identity(production.adn_text(conn, ch, cast["version"]))
        if txt:
            blocks.append({"block": "Identité", "who": ch, "source": "référentiel", "text": txt.strip()})
        looks = {s["looks"].get(ch) for s in shots if s["looks"].get(ch)}
        for lk in sorted(x for x in looks if x):
            r = conn.execute("SELECT description FROM looks WHERE character_slug=? AND slug=?", (ch, lk)).fetchone()
            if r and r["description"]:
                blocks.append({"block": "Tenue", "who": ch, "source": "référentiel", "text": r["description"].strip()})
    return blocks


def _adn_identity(adn: str) -> str:
    """Le paragraphe « Identité » de adn.md (texte à injecter), ou le premier paragraphe."""
    m = re.search(r"##\s*Identit[ée][^\n]*\n+(.+?)(\n##|\Z)", adn or "", re.S)
    return (m.group(1) if m else (adn or "")).strip()


def _objects(conn: sqlite3.Connection, shots: list[dict]) -> list[dict]:
    ids = [s["id"] for s in shots]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    out = []
    for e in conn.execute(f"SELECT DISTINCT e.kind, e.name, COALESCE(NULLIF(e.prompt,''), e.description) AS d "
                          f"FROM shot_elements se JOIN elements e ON e.id=se.element_id WHERE se.shot_id IN ({marks}) "
                          f"AND e.kind IN ('objet','decor') ORDER BY e.kind DESC, e.name", ids):
        if e["d"]:
            out.append({"block": "Objets" if e["kind"] == "objet" else "Décor", "who": e["name"],
                        "source": "référentiel", "text": f"{e['name']}: {e['d'].strip()}"})
    return out


def _camera(s: dict) -> str:
    parts = [x for x in (s.get("framing"), s.get("camera")) if x]
    return ", ".join(parts)


def _ts(t: float) -> str:
    return f"00:{int(t):02d}"


def build_prompt(conn: sqlite3.Connection, seq: dict, take: dict, shots_by_id: dict[int, dict], o: dict) -> dict:
    """Prompt d'une prise : blocs du référentiel (non éditables par un agent) + action et caméra par plan,
    mis au format du modèle par son dialecte."""
    shots = [shots_by_id[w["shot_id"]] for w in take["shots"]]
    blocks = _identity(conn, seq["clip_slug"], shots) + _objects(conn, shots)
    if seq.get("fiche"):
        blocks.append({"block": "Séquence", "who": seq["name"], "source": "fiche de séquence", "text": seq["fiche"].strip()})
    per_shot = []
    for w in take["shots"]:
        s = shots_by_id[w["shot_id"]]
        per_shot.append({"shot_id": s["id"], "num": s["num"], "t_in": w["t_in"], "t_out": w["t_out"],
                         "action": shot_action(conn, s), "camera": _camera(s),
                         "action_source": "toi" if s.get("action_edited") else "prompteur" if s.get("action_en") else "prompt détaillé du plan"})
    dialect = o.get("dialect", "generic")
    head = "\n".join(b["text"] for b in blocks)
    if len(per_shot) == 1:
        body = per_shot[0]["action"] + (f" Camera: {per_shot[0]['camera']}." if per_shot[0]["camera"] else "")
    elif dialect == "veo":
        body = "\n".join(f"[{_ts(p['t_in'])}-{_ts(max(p['t_out'], p['t_in'] + 1))}] {p['action']}"
                         + (f" Camera: {p['camera']}." if p["camera"] else "") for p in per_shot)
        if take["form"] == "continuous":
            body = "One continuous take, no cut.\n" + body
        else:
            body = f"{len(per_shot)} shots with hard cuts at the given times.\n" + body
    else:
        body = "\n".join(f"Shot {i + 1} ({p['t_out'] - p['t_in']:.1f} s): {p['action']}"
                         + (f" Camera: {p['camera']}." if p["camera"] else "") for i, p in enumerate(per_shot))
    text = (head + "\n\n" + body).strip()
    agent_text = " ".join(p["action"] for p in per_shot)
    return {"blocks": blocks, "shots": per_shot, "text": text, "negative": DEFAULT_NEGATIVE,
            "traps": traps(agent_text)}


# --- vue d'une séquence ------------------------------------------------------------

def sequence_view(conn: sqlite3.Connection, seq_id: int, detail: bool = True) -> dict:
    from . import derush
    seq = seq_row(conn, seq_id)
    shots = seq_shots(conn, seq_id)
    for x in shots:
        x["state"] = derush.shot_state(conn, x)
        x["state_label"] = derush.STATE_LABEL[x["state"]]
    # le plan de tournage ne porte que les plans qui ont besoin d'une prise (jamais tournés, à refaire, bloqués)
    shootable = [s for s in shots if s["shootable"] and s["state"] in ("pret", "a_refaire", "bloque")]
    offers = cat.offers()
    reserves = cat.reserves(conn)
    quality = _quality(conn, seq["clip_slug"])
    opts = {k: v for k, v in seq["options"].items() if k in ("mode", "start_image")}
    ranked = []
    for o in offers:
        has_refs = bool(pick_refs(ref_candidates(conn, seq, shootable, o["provider"]), 3, None)) if detail else True
        ranked.append(planner.plan_sequence(shootable, o, quality=quality, options=opts, reserves=reserves,
                                            profile=seq.get("profile"), has_refs=has_refs))
    ranked = planner.rank(ranked, offers)
    recommended = ranked[0] if ranked else None
    chosen_key = seq.get("offer_key") or (recommended["offer"] if recommended else None)
    o = next((x for x in offers if x["key"] == chosen_key), None)
    out: dict[str, Any] = {"sequence": seq, "shots": shots, "quality": quality,
                           "profile": planner.sequence_profile(shootable, seq.get("profile")),
                           "profile_label": cat.PROFILE_LABEL[planner.sequence_profile(shootable, seq.get("profile"))],
                           "recommended": recommended["offer"] if recommended else None,
                           "chosen_by_michael": bool(seq.get("offer_key")),
                           "waiting_blocks": sorted({s["block_num"] for s in shots if not s["shootable"] and s["block_num"]}),
                           "reserves": reserves}
    if not o:
        out.update({"plan": None, "badge": "aucune offre", "alternatives": []})
        return out
    refs = ref_candidates(conn, seq, shootable, o["provider"])
    mode_refs = (o["modes"].get("references") or {}).get("max_refs", 0)
    chosen_refs = pick_refs(refs, int(mode_refs or 0), seq["options"].get("refs"))
    plan = planner.plan_sequence(shootable, o, quality=quality, options=seq["options"], reserves=reserves,
                                 profile=seq.get("profile"), has_refs=bool(chosen_refs))
    taken = shot_taken(conn, [s["id"] for s in shootable])
    by_id = {s["id"]: s for s in shots}
    if plan["mode"] == "references":
        for t in plan["takes"]:
            t_shots = [by_id[w["shot_id"]] for w in t["shots"]]
            t["refs"] = pick_refs(ref_candidates(conn, seq, t_shots, o["provider"]), int(mode_refs or 0),
                                  seq["options"].get("refs"))
    for t in plan["takes"]:
        if detail:
            t["prompt"] = build_prompt(conn, seq, t, by_id, o)
        t["already"] = [w["num"] for w in t["shots"] if w["shot_id"] in taken]
    out["plan"] = plan
    out["badge"] = (f"{cat.PROFILE_LABEL[plan['profile']]} · {plan['offer_label']} · {len(plan['takes'])} prise"
                    f"{'s' if len(plan['takes']) > 1 else ''} · {plan['total_usd']:.2f} $ · {plan['funding_label']}"
                    if shootable else ("tous les plans validés sont tournés" if any(x["shootable"] for x in shots)
                                       else "aucun plan d'un bloc validé"))
    if detail:
        out["refs"] = [{**r, "selected": any(c["path"] == r["path"] for c in chosen_refs)} for r in refs]
        out["max_refs"] = mode_refs
        out["gaps"] = look_gaps(conn, shootable) + element_gaps(conn, shootable)
        chars = sorted({c for x in shots for c in (x.get("characters") or [])})
        out["looks"] = {ch: [{"slug": r["slug"], "name": r["name"] or r["slug"]} for r in conn.execute(
            "SELECT slug, name FROM looks WHERE character_slug=? ORDER BY slug", (ch,))] for ch in chars}
        for x in shots:
            x["action"] = shot_action(conn, x)
            x["traps"] = traps(x["action"])
        out["alternatives"] = [{"offer": p["offer"], "label": p["offer_label"], "provider": p.get("provider"),
                                "usable": p.get("usable"), "total_usd": p["total_usd"], "takes": len(p["takes"]),
                                "funding_label": p.get("funding_label"), "mode": p["mode"],
                                "resolution": p.get("resolution"), "blocking": p["blocking"],
                                "recommended": p["offer"] == out["recommended"],
                                "impact": planner.impact(plan, p, shot_taken=taken)}
                               for p in ranked if p["offer"] != o["key"]]
        out["options"] = {"modes": [{"key": m, "label": cat.MODE_LABEL.get(m, m),
                                     "durations": (o["modes"][m] or {}).get("durations")} for m in o["modes"]],
                          "resolutions": [{"key": r, "price_per_s": o["prices"][r]} for r in o["resolutions"]]}
        out["option_impacts"] = _option_impacts(conn, seq, shootable, o, plan, quality, reserves, bool(chosen_refs), taken)
    return out


def _option_impacts(conn, seq, shootable, o, plan, quality, reserves, has_refs, taken) -> dict:
    """Pour chaque autre mode et chaque autre résolution : ce que le changement donnerait (D35)."""
    out: dict[str, dict] = {"mode": {}, "resolution": {}}
    for m in o["modes"]:
        if m == plan["mode"]:
            continue
        alt = planner.plan_sequence(shootable, o, quality=quality, options={**seq["options"], "mode": m},
                                    reserves=reserves, profile=seq.get("profile"), has_refs=has_refs)
        out["mode"][m] = {"total_usd": alt["total_usd"], "impact": planner.impact(plan, alt, shot_taken=taken)}
    for r in o["resolutions"]:
        if r == plan.get("resolution"):
            continue
        alt = planner.plan_sequence(shootable, o, quality=quality, options={**seq["options"], "resolution": r},
                                    reserves=reserves, profile=seq.get("profile"), has_refs=has_refs)
        out["resolution"][r] = {"total_usd": alt["total_usd"], "impact": planner.impact(plan, alt, shot_taken=taken)}
    return out


def ensure_sequences(conn: sqlite3.Connection, slug: str) -> None:
    """Un bloc dont aucun plan n'a de séquence reçoit une séquence à son nom (Michael la découpe ensuite)."""
    for b in conn.execute("SELECT b.id, b.name FROM blocks b WHERE b.clip_slug=? AND EXISTS (SELECT 1 FROM shots s "
                          "WHERE s.block_id=b.id AND s.deleted_at IS NULL AND s.sequence_id IS NULL) AND NOT EXISTS "
                          "(SELECT 1 FROM shots s WHERE s.block_id=b.id AND s.sequence_id IS NOT NULL) ORDER BY b.num",
                          (slug,)).fetchall():
        with db.tx(conn):
            num = conn.execute("SELECT COALESCE(MAX(num),0)+1 FROM sequences WHERE clip_slug=?", (slug,)).fetchone()[0]
            cur = conn.execute("INSERT INTO sequences (clip_slug, num, name, created_at, updated_at) VALUES (?,?,?,?,?)",
                               (slug, num, b["name"], db.now(), db.now()))
            for r in conn.execute("SELECT id FROM shots WHERE block_id=? AND deleted_at IS NULL", (b["id"],)).fetchall():
                db.update(conn, "shots", r["id"], {"sequence_id": cur.lastrowid}, by="code:tournage",
                          reason="séquence par défaut du bloc")


def clip_sequences(conn: sqlite3.Connection, slug: str) -> dict:
    ensure_sequences(conn, slug)
    seqs = [r["id"] for r in conn.execute("SELECT id FROM sequences WHERE clip_slug=? ORDER BY num", (slug,))]
    views = [sequence_view(conn, sid, detail=False) for sid in seqs]
    loose = db.rows(conn.execute("SELECT id, num, t_start, t_end, description FROM shots WHERE clip_slug=? "
                                 "AND deleted_at IS NULL AND sequence_id IS NULL ORDER BY t_start", (slug,)).fetchall())
    return {"sequences": [{"id": v["sequence"]["id"], "num": v["sequence"]["num"], "name": v["sequence"]["name"],
                           "badge": v["badge"], "profile": v["profile"],
                           "total_usd": (v["plan"] or {}).get("total_usd", 0),
                           "blocking": (v["plan"] or {}).get("blocking", True),
                           "waiting_blocks": v["waiting_blocks"],
                           "shots": [{"id": s["id"], "num": s["num"], "t_start": s["t_start"], "t_end": s["t_end"],
                                      "description": s["description"], "shootable": s["shootable"],
                                      "block_num": s["block_num"], "jeu": s["jeu"], "axe": s["axe"], "state_label": s["state_label"]}
                                     for s in v["shots"]]} for v in views],
            "loose_shots": loose, "reserves": cat.reserves(conn), "quality": _quality(conn, slug)}


# --- écritures de Michael -----------------------------------------------------------

def create_sequence(conn: sqlite3.Connection, slug: str, name: str, shot_ids: list[int] | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise TournageError("Donne un nom à la séquence")
    with db.tx(conn):
        num = conn.execute("SELECT COALESCE(MAX(num),0)+1 FROM sequences WHERE clip_slug=?", (slug,)).fetchone()[0]
        cur = conn.execute("INSERT INTO sequences (clip_slug, num, name, created_at, updated_at) VALUES (?,?,?,?,?)",
                           (slug, num, name, db.now(), db.now()))
        sid = cur.lastrowid
        for shot in shot_ids or []:
            _move(conn, shot, sid, slug)
    return seq_row(conn, sid)


def _move(conn: sqlite3.Connection, shot_id: int, seq_id: int | None, slug: str) -> None:
    s = db.get_shot(conn, shot_id)
    if s["clip_slug"] != slug:
        raise TournageError(f"Le plan {shot_id} n'est pas dans ce clip")
    db.update(conn, "shots", shot_id, {"sequence_id": seq_id}, reason="séquence")


def move_shots(conn: sqlite3.Connection, shot_ids: list[int], seq_id: int) -> dict:
    seq = seq_row(conn, seq_id)
    with db.tx(conn):
        for sid in shot_ids:
            _move(conn, sid, seq_id, seq["clip_slug"])
        _drop_empty(conn, seq["clip_slug"])
    return seq


def _drop_empty(conn: sqlite3.Connection, slug: str) -> None:
    """Une séquence vidée de ses plans et sans prise disparaît (rien de généré n'est perdu)."""
    for r in conn.execute("SELECT id FROM sequences WHERE clip_slug=? AND id NOT IN (SELECT sequence_id FROM shots "
                          "WHERE sequence_id IS NOT NULL AND deleted_at IS NULL) AND id NOT IN "
                          "(SELECT sequence_id FROM takes WHERE sequence_id IS NOT NULL)", (slug,)).fetchall():
        conn.execute("DELETE FROM sequences WHERE id=?", (r["id"],))


def update_sequence(conn: sqlite3.Connection, seq_id: int, **fields: Any) -> dict:
    seq = seq_row(conn, seq_id)
    bad = set(fields) - SEQ_FIELDS
    if bad:
        raise TournageError(f"Champ inconnu : {', '.join(sorted(bad))}")
    if "offer_key" in fields and fields["offer_key"]:
        cat.offer(fields["offer_key"])
    if "profile" in fields and fields["profile"] and fields["profile"] not in cat.PROFILE_ORDER:
        raise TournageError("Profil inconnu")
    if "options" in fields:
        opts = {**seq["options"], **(fields["options"] or {})}
        fields["options"] = json.dumps({k: v for k, v in opts.items() if v not in (None, "", [])}, ensure_ascii=False)
    fields["updated_at"] = db.now()
    db.update(conn, "sequences", seq_id, fields, reason="Michael")
    return seq_row(conn, seq_id)


def set_shot_attrs(conn: sqlite3.Connection, shot_id: int, **fields: Any) -> dict:
    clean = {}
    for k, v in fields.items():
        if k in SHOT_ATTRS:
            if v not in SHOT_ATTRS[k]:
                raise TournageError(f"{k} : valeur attendue parmi {', '.join(SHOT_ATTRS[k])}")
            clean[k] = v
        elif k == "axe":
            clean[k] = (v or "").strip() or None
        elif k == "action_en":
            clean[k] = (v or "").strip() or None
            clean["action_edited"] = 1 if clean[k] and db.actor() == "michael" else 0
        else:
            raise TournageError(f"Attribut inconnu : {k}")
    return db.update(conn, "shots", shot_id, clean, reason="attributs v3")


def set_quality(conn: sqlite3.Connection, slug: str, quality: str) -> None:
    if quality not in ("brouillon", "final"):
        raise TournageError("Qualité : brouillon ou final")
    db.update(conn, "clips", slug, {"quality": quality}, reason="qualité du clip")


def idem_key(*parts: Any) -> str:
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]
