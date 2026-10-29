"""Logique de production : clips, plans, générations, validations, personnages.

Tout ce qui est déterministe vit ici (appelé par la CLI `riot`, le worker et la
régie). Les agents Claude ne font que le travail de jugement : analyser le
script, écrire les prompts, décrire les plans, contrôler la cohérence et trier
les retours.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import credits, db, fal, media, notify, providers, routing
from .settings import get_settings, load_models

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
REF_KIND_ORDER = ["canon", "turnaround", "fullbody", "expressions", "lighting", "details"]


class ProductionError(Exception):
    pass


class BudgetError(ProductionError):
    pass


# --- Chemins ---------------------------------------------------------------

def studio() -> Path:
    return get_settings().studio_root


def rel(p: Path | str) -> str:
    """Chemin relatif à studio/ (ce qu'on stocke en base)."""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(studio()))
    except ValueError:
        return str(p)


def absp(p: str | None) -> Path | None:
    if not p:
        return None
    path = Path(p)
    return path if path.is_absolute() else studio() / path


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[àáâãä]", "a", s)
    s = re.sub(r"[èéêë]", "e", s)
    s = re.sub(r"[ìíîï]", "i", s)
    s = re.sub(r"[òóôõö]", "o", s)
    s = re.sub(r"[ùúûü]", "u", s)
    s = re.sub(r"ç", "c", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "clip"


def is_demo(clip_slug: str) -> bool:
    """Les clips « demo-… » sont toujours simulés et ignorés par les agents."""
    return clip_slug.startswith("demo-")


def _ext_from_url(url: str, default: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix and len(suffix) <= 5 else default


# --- Personnages -----------------------------------------------------------

def create_character(conn: sqlite3.Connection, slug: str, name: str, notes: str = "") -> dict:
    slug = slugify(slug)
    (studio() / "characters" / slug / "looks").mkdir(parents=True, exist_ok=True)
    conn.execute(
        "INSERT OR IGNORE INTO characters (slug, name, notes, created_at) VALUES (?,?,?,?)",
        (slug, name, notes, db.now()),
    )
    return db.row(conn.execute("SELECT * FROM characters WHERE slug=?", (slug,)).fetchone())


def new_character_version(conn: sqlite3.Connection, slug: str, notes: str = "") -> dict:
    ch = conn.execute("SELECT * FROM characters WHERE slug=?", (slug,)).fetchone()
    if ch is None:
        raise ProductionError(f"Personnage inconnu : {slug}")
    version = conn.execute(
        "SELECT COALESCE(MAX(version),0)+1 FROM character_versions WHERE character_slug=?", (slug,)
    ).fetchone()[0]
    vdir = studio() / "characters" / slug / f"v{version}"
    for sub in REF_KIND_ORDER[1:]:
        (vdir / sub).mkdir(parents=True, exist_ok=True)
    conn.execute(
        "INSERT INTO character_versions (character_slug, version, status, dir, notes, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (slug, version, "draft", rel(vdir), notes, db.now()),
    )
    db.log_event(conn, None, "casting", f"{slug} : nouvelle version v{version} (brouillon)")
    return character_version(conn, slug, version)


def character_version(conn: sqlite3.Connection, slug: str, version: int) -> dict:
    v = db.row(conn.execute(
        "SELECT * FROM character_versions WHERE character_slug=? AND version=?", (slug, version)
    ).fetchone())
    if v is None:
        raise ProductionError(f"Version inconnue : {slug} v{version}")
    return v


def sync_character_files(conn: sqlite3.Connection, slug: str | None = None) -> int:
    """Enregistre en base les fichiers déposés à la main dans studio/characters/.

    Arborescence attendue : characters/<slug>/v<N>/canon.png, turnaround/*.png...
    Les fichiers ajoutés à la main sont considérés comme retenus (kept).
    """
    added = 0
    base = studio() / "characters"
    if not base.is_dir():
        return 0
    for cdir in sorted(base.iterdir()):
        if not cdir.is_dir() or (slug and cdir.name != slug):
            continue
        meta = _read_character_yaml(cdir)
        create_character(conn, cdir.name, meta.get("name", cdir.name.upper()), meta.get("notes", ""))
        for vdir in sorted(cdir.glob("v[0-9]*")):
            if not vdir.is_dir() or not re.fullmatch(r"v\d+", vdir.name):
                continue
            version = int(vdir.name[1:])
            vmeta = (meta.get("versions") or {}).get(version) or {}
            existing = conn.execute(
                "SELECT id FROM character_versions WHERE character_slug=? AND version=?",
                (cdir.name, version),
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO character_versions (character_slug, version, status, dir, notes, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (cdir.name, version, vmeta.get("status", "draft"), rel(vdir), vmeta.get("notes", ""), db.now()),
                )
                existing = conn.execute(
                    "SELECT id FROM character_versions WHERE character_slug=? AND version=?",
                    (cdir.name, version),
                ).fetchone()
            vid = existing["id"]
            for f in sorted(vdir.rglob("*")):
                if f.suffix.lower() not in IMAGE_EXT or f.name.startswith("."):
                    continue
                kind = "canon" if f.stem == "canon" else (f.parent.name if f.parent != vdir else "details")
                r = rel(f)
                if conn.execute("SELECT 1 FROM character_assets WHERE path=?", (r,)).fetchone():
                    continue
                conn.execute(
                    "INSERT INTO character_assets (version_id, kind, label, path, status, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (vid, kind, f.stem, r, "kept", db.now()),
                )
                added += 1
        canon = meta.get("canon_version")
        if canon:
            conn.execute("UPDATE characters SET canon_version=? WHERE slug=?", (int(canon), cdir.name))
        for ldir in sorted((cdir / "looks").glob("*")):
            if ldir.is_dir():
                desc_file = ldir / "look.md"
                desc = desc_file.read_text(encoding="utf-8") if desc_file.is_file() else ""
                conn.execute(
                    "INSERT OR IGNORE INTO looks (character_slug, slug, description, dir) VALUES (?,?,?,?)",
                    (cdir.name, ldir.name, desc, rel(ldir)),
                )
    return added


def _read_character_yaml(cdir: Path) -> dict:
    f = cdir / "character.yaml"
    if not f.is_file():
        return {}
    import yaml
    return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


def character_refs(conn: sqlite3.Connection, slug: str, version: int, look: str | None = None,
                   limit: int = 6) -> list[Path]:
    """Images de référence à envoyer au modèle : canon d'abord, puis le reste du pack."""
    v = character_version(conn, slug, version)
    assets = db.rows(conn.execute(
        "SELECT * FROM character_assets WHERE version_id=? AND status='kept' AND path IS NOT NULL",
        (v["id"],),
    ).fetchall())
    order = {k: i for i, k in enumerate(REF_KIND_ORDER)}
    assets.sort(key=lambda a: (order.get(a["kind"], 99), a["id"]))
    refs = [absp(a["path"]) for a in assets if absp(a["path"]) and absp(a["path"]).is_file()]
    if look:
        lk = conn.execute("SELECT dir FROM looks WHERE character_slug=? AND slug=?", (slug, look)).fetchone()
        if lk:
            look_imgs = sorted(p for p in absp(lk["dir"]).glob("*") if p.suffix.lower() in IMAGE_EXT)
            # le canon reste en tête, le look passe juste après
            refs = refs[:1] + look_imgs[:2] + refs[1:]
    return refs[:limit]


def adn_text(conn: sqlite3.Connection, slug: str, version: int) -> str:
    v = character_version(conn, slug, version)
    f = absp(v["dir"]) / "adn.md"
    return f.read_text(encoding="utf-8") if f.is_file() else ""


# --- Accord de Michael avant toute dépense -------------------------------------
# Chaque génération payante (crédits gratuits compris) attend son accord dans la
# régie, avec son coût estimé. Les vidéos passent déjà par la validation du plan
# vidéo (prompt, modèle, coût) : elles ne repassent pas par ici.

def _needs_approval(provider: str, cost: float, demo: bool, approved: bool) -> bool:
    if approved or demo or providers.simulated(provider):
        return False
    cfg = load_models().get("approval") or {}
    if not cfg.get("required", True):
        return False
    return cost > float(cfg.get("auto_under_usd", 0) or 0)


def _ask_spend(conn: sqlite3.Connection, action: str, args: dict, dedupe: str, label: str, cost: float,
               mcfg: dict, model_key: str, *, detail: str = "", clip_slug: str | None = None,
               character_slug: str | None = None, shot_id: int | None = None) -> dict:
    """Enregistre la demande (une seule fois) et renvoie son état, sans rien lancer."""
    key = f"{action}:{dedupe}"
    row = db.row(conn.execute(
        "SELECT * FROM spend_requests WHERE dedupe=? AND status IN ('pending','approved','refused') "
        "ORDER BY id DESC LIMIT 1", (key,)).fetchone())
    if row is None:
        provider = mcfg.get("provider", "fal")
        with db.tx(conn):
            cur = conn.execute(
                "INSERT INTO spend_requests (action, args, dedupe, label, detail, clip_slug, character_slug, shot_id, "
                "model_key, provider, est_usd, funding, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (action, json.dumps(args), key, label, detail[:2000] or None, clip_slug, character_slug, shot_id,
                 model_key, provider, round(cost, 4), credits.funding_for(conn, provider, cost), "pending", db.now()))
            db.log_event(conn, clip_slug, "depense", f"À valider : {label} ({cost:.2f} $)")
        row = db.row(conn.execute("SELECT * FROM spend_requests WHERE id=?", (cur.lastrowid,)).fetchone())
    msg = {"pending": "en attente de l'accord de Michael",
           "approved": "accordée, lancement au prochain tour du worker",
           "refused": "refusée par Michael : change la demande (prompt, image) avant de la reproposer"}[row["status"]]
    return {"spend_request": row["id"], "status": row["status"], "est_usd": row["est_usd"],
            "funding": row["funding"], "message": f"Dépense {msg} ({row['est_usd']:.2f} $)"}


def _hash(*parts: Any) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:12]


def spend_requests(conn: sqlite3.Connection, status: str = "pending") -> list[dict]:
    rows = conn.execute("SELECT * FROM spend_requests WHERE status=? ORDER BY id", (status,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["model_label"] = (routing.models_cfg()["models"].get(d["model_key"]) or {}).get("label", d["model_key"])
        if d["shot_id"]:
            sh = conn.execute("SELECT num FROM shots WHERE id=?", (d["shot_id"],)).fetchone()
            d["shot_num"] = sh["num"] if sh else None
        out.append(d)
    return out


def decide_spend(conn: sqlite3.Connection, ids: list[int], decision: str, note: str = "") -> int:
    """Michael accorde (le worker lance) ou refuse une ou plusieurs dépenses."""
    if decision not in ("approve", "refuse"):
        raise ProductionError(f"Décision inconnue : {decision}")
    n = 0
    with db.tx(conn):
        for i in ids:
            r = conn.execute("SELECT * FROM spend_requests WHERE id=? AND status='pending'", (i,)).fetchone()
            if r is None:
                continue
            conn.execute("UPDATE spend_requests SET status=?, note=?, decided_at=? WHERE id=?",
                         ("approved" if decision == "approve" else "refused", note or None, db.now(), i))
            if decision == "refuse" and r["action"] == "image_hd" and r["shot_id"]:
                # pas de HD : le visuel validé sert tel quel pour la vidéo
                conn.execute("UPDATE shots SET status='prompt_todo', updated_at=? WHERE id=? AND status='hd_todo'",
                             (db.now(), r["shot_id"]))
            if decision == "refuse" and r["action"] == "image" and r["shot_id"] and note:
                old = conn.execute("SELECT notes FROM shots WHERE id=?", (r["shot_id"],)).fetchone()["notes"] or ""
                conn.execute("UPDATE shots SET notes=? WHERE id=?",
                             ((old + f"\nVisuel refusé avant génération : {note}").strip(), r["shot_id"]))
            n += 1
    return n


def run_approved_spend(conn: sqlite3.Connection) -> int:
    """Worker : lance les dépenses accordées par Michael."""
    actions = {"image": launch_image, "image_hd": launch_image_hd, "canon_hd": launch_canon_hd,
               "character_asset": launch_character_asset}
    done = 0
    for r in conn.execute("SELECT * FROM spend_requests WHERE status='approved' ORDER BY id").fetchall():
        try:
            actions[r["action"]](conn, **json.loads(r["args"]), approved=True)
            conn.execute("UPDATE spend_requests SET status='done' WHERE id=?", (r["id"],))
            done += 1
        except Exception as exc:  # noqa: BLE001 - l'échec est montré à Michael
            conn.execute("UPDATE spend_requests SET status='failed', note=? WHERE id=?", (str(exc)[:500], r["id"]))
            db.log_event(conn, r["clip_slug"], "error", f"{r['label']} : {exc}")
    return done


def launch_character_asset(conn: sqlite3.Connection, slug: str, version: int, kind: str,
                           label: str, prompt: str, ref_paths: list[str] | None = None,
                           model_key: str | None = None, approved: bool = False) -> dict:
    """Génère une image du pack de référence (agent casting)."""
    v = character_version(conn, slug, version)
    if v["status"] != "draft":
        raise ProductionError(f"{slug} v{version} est {v['status']} : on ne modifie qu'une version brouillon")
    cfg = load_models()
    key = model_key or routing.pick_model("casting")
    mcfg = routing.model(key)
    if ref_paths:
        refs = [Path(p) if Path(p).is_absolute() else studio() / p for p in ref_paths]
    else:
        # la canon de la version en cours prime ; sinon celle de la version validée
        own_canon = conn.execute("SELECT 1 FROM character_assets WHERE version_id=? AND kind='canon' "
                                 "AND status='kept'", (v["id"],)).fetchone()
        ch = conn.execute("SELECT canon_version FROM characters WHERE slug=?", (slug,)).fetchone()
        base_version = version if own_canon or not (ch and ch["canon_version"]) else ch["canon_version"]
        refs = character_refs(conn, slug, base_version, limit=int(mcfg.get("max_refs", 6)))
    image_urls = [fal.to_data_uri(p) for p in refs if p.is_file()]
    payload = routing.build_payload(mcfg, prompt=prompt, image_urls=image_urls, mode="final",
                                    aspect_ratio=_casting_aspect(kind))
    cost = routing.estimate_cost(mcfg, mode="final")
    if _needs_approval(mcfg.get("provider", "fal"), cost, False, approved):
        return _ask_spend(conn, "character_asset",
                          {"slug": slug, "version": version, "kind": kind, "label": label, "prompt": prompt,
                           "ref_paths": ref_paths, "model_key": key},
                          _hash(slug, version, kind, label, prompt, ref_paths, key),
                          f"{slug} v{version} : {kind} « {label} »", cost, mcfg, key,
                          detail=prompt, character_slug=slug)
    sub = providers.submit(mcfg, payload, kind="image", label=f"{slug} {kind} {label}")
    out = absp(v["dir"]) / kind / f"{slugify(label)}-{sub['request_id'][-6:]}.png"
    with db.tx(conn):
        cur = conn.execute(
            "INSERT INTO character_assets (version_id, kind, label, path, prompt, model_key, cost_usd, funding, status, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (v["id"], kind, label, rel(out), prompt, key, cost,
             credits.funding_for(conn, mcfg.get("provider", "fal"), cost), "generating", db.now()),
        )
        _insert_job(conn, "character_assets", cur.lastrowid, mcfg["endpoint"], sub, out)
    return {"asset_id": cur.lastrowid, "request_id": sub["request_id"], "refs": [rel(p) for p in refs], "cost_usd": cost}


def _casting_aspect(kind: str) -> str:
    return {"fullbody": "9:16", "turnaround": "16:9"}.get(kind, "3:4")


def review_character_asset(conn: sqlite3.Connection, asset_id: int, decision: str) -> None:
    """decision : keep, reject ou canon (devient l'image canon de la version)."""
    a = db.row(conn.execute("SELECT * FROM character_assets WHERE id=?", (asset_id,)).fetchone())
    if a is None:
        raise ProductionError(f"Image de référence inconnue : {asset_id}")
    if decision == "reject":
        conn.execute("UPDATE character_assets SET status='rejected' WHERE id=?", (asset_id,))
        return
    if decision == "keep":
        conn.execute("UPDATE character_assets SET status='kept' WHERE id=?", (asset_id,))
        return
    if decision == "canon":
        src = absp(a["path"])
        v = db.row(conn.execute("SELECT * FROM character_versions WHERE id=?", (a["version_id"],)).fetchone())
        vdir = absp(v["dir"])
        dest = vdir / f"canon{src.suffix.lower()}"
        with db.tx(conn):
            # l'ancienne canon et les autres candidates deviennent de simples images « détails »
            others = conn.execute(
                "SELECT id, path, status, parent_id FROM character_assets WHERE version_id=? AND kind='canon' AND id!=?",
                (v["id"], asset_id),
            ).fetchall()
            for o in others:
                if o["status"] != "kept":
                    # candidate non retenue (canon HD en attente, autre proposition) : écartée, pas versée au pack
                    conn.execute("UPDATE character_assets SET status='rejected' WHERE id=?", (o["id"],))
                    continue
                op = absp(o["path"])
                new_path = o["path"]
                if op and op.is_file() and op.resolve() == dest.resolve():
                    archived = vdir / "details" / f"ancienne-canon-{o['id']}{op.suffix}"
                    archived.parent.mkdir(parents=True, exist_ok=True)
                    op.rename(archived)
                    new_path = rel(archived)
                # une ancienne canon n'est plus utilisée comme référence tant que Michael ne la regarde pas
                conn.execute(
                    "UPDATE character_assets SET kind='details', path=?, "
                    "status=CASE WHEN status='kept' THEN 'proposed' ELSE status END WHERE id=?",
                    (new_path, o["id"]),
                )
            for stale in vdir.glob("canon.*"):
                if stale.resolve() != src.resolve():
                    archived = vdir / "details" / f"ancienne-canon-{stale.stem}-{asset_id}{stale.suffix}"
                    archived.parent.mkdir(parents=True, exist_ok=True)
                    stale.rename(archived)
            if src.resolve() != dest.resolve():
                src.rename(dest)
            conn.execute(
                "UPDATE character_assets SET kind='canon', label='canon', path=?, status='kept' WHERE id=?",
                (rel(dest), asset_id),
            )
        return
    raise ProductionError(f"Décision inconnue : {decision}")


def validate_character_version(conn: sqlite3.Connection, slug: str, version: int) -> None:
    """Michael seulement : la version devient la canon du personnage."""
    v = character_version(conn, slug, version)
    has_canon = conn.execute(
        "SELECT 1 FROM character_assets WHERE version_id=? AND kind='canon' AND status='kept'", (v["id"],)
    ).fetchone()
    if not has_canon:
        raise ProductionError("Impossible de valider : la version n'a pas d'image canon")
    with db.tx(conn):
        conn.execute("UPDATE character_versions SET status='validated' WHERE id=?", (v["id"],))
        conn.execute("UPDATE characters SET canon_version=? WHERE slug=?", (version, slug))
        db.log_event(conn, None, "casting", f"{slug} v{version} validée et devient la canon")


def character_snapshot(conn: sqlite3.Connection, slug: str) -> dict:
    ch = db.row(conn.execute("SELECT * FROM characters WHERE slug=?", (slug,)).fetchone())
    if ch is None:
        raise ProductionError(f"Personnage inconnu : {slug}")
    versions = db.rows(conn.execute(
        "SELECT * FROM character_versions WHERE character_slug=? ORDER BY version DESC", (slug,)
    ).fetchall())
    for v in versions:
        v["assets"] = db.rows(conn.execute(
            "SELECT * FROM character_assets WHERE version_id=? ORDER BY kind, id", (v["id"],)
        ).fetchall())
        adn = absp(v["dir"]) / "adn.md"
        v["adn"] = adn.read_text(encoding="utf-8") if adn.is_file() else ""
        v["generating"] = sum(1 for a in v["assets"] if a["status"] == "generating")
        v["essais"] = version_essais(absp(v["dir"]))
    ch["versions"] = versions
    ch["clips"] = db.rows(conn.execute(
        "SELECT clip_slug, version, look_slug FROM castings WHERE character_slug=?", (slug,)
    ).fetchall())
    looks = db.rows(conn.execute("SELECT * FROM looks WHERE character_slug=? ORDER BY slug", (slug,)).fetchall())
    for lk in looks:
        ldir = absp(lk["dir"])
        lk["images"] = [rel(p) for p in sorted(ldir.glob("*")) if p.suffix.lower() in IMAGE_EXT] if ldir.is_dir() else []
        lk["clips"] = [c["clip_slug"] for c in ch["clips"] if c["look_slug"] == lk["slug"]]
    ch["looks"] = looks
    ch["spend"] = spend_requests(conn, "pending")
    ch["spend"] = [r for r in ch["spend"] if r["character_slug"] == slug]
    return ch


VIDEO_EXT = {".mp4", ".mov", ".webm"}


def version_essais(vdir: Path) -> list[dict]:
    """Tout ce qui a été produit pour une version hors du pack : tests, essais, vidéos.
    Rangé dans <version>/essais/, avec une légende par fichier dans legendes.json."""
    edir = vdir / "essais"
    if not edir.is_dir():
        return []
    caps = {}
    if (edir / "legendes.json").is_file():
        caps = json.loads((edir / "legendes.json").read_text(encoding="utf-8"))
    out = []
    for p in sorted(edir.iterdir()):
        ext = p.suffix.lower()
        if ext in IMAGE_EXT or ext in VIDEO_EXT:
            out.append({"path": rel(p), "type": "video" if ext in VIDEO_EXT else "image", "caption": caps.get(p.name, "")})
    return out


def save_adn(conn: sqlite3.Connection, slug: str, version: int, text: str) -> None:
    """Michael corrige la fiche du personnage (texte ajouté à chaque demande d'image)."""
    v = character_version(conn, slug, version)
    if v["status"] != "draft":
        raise ProductionError("Une version validée ne se modifie plus : crée une nouvelle version")
    (absp(v["dir"]) / "adn.md").write_text(text.strip() + "\n", encoding="utf-8")
    db.log_event(conn, None, "casting", f"{slug} v{version} : fiche mise à jour")


def create_look(conn: sqlite3.Connection, slug: str, name: str, description: str = "") -> dict:
    """Une tenue du personnage : un nom, une description, des photos de référence."""
    if not conn.execute("SELECT 1 FROM characters WHERE slug=?", (slug,)).fetchone():
        raise ProductionError(f"Personnage inconnu : {slug}")
    lslug = slugify(name)
    if not lslug:
        raise ProductionError("Donne un nom à la tenue")
    ldir = studio() / "characters" / slug / "looks" / lslug
    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / "look.md").write_text(f"# {name}\n\n{description.strip()}\n", encoding="utf-8")
    conn.execute("INSERT INTO looks (character_slug, slug, description, dir) VALUES (?,?,?,?) "
                 "ON CONFLICT(character_slug, slug) DO UPDATE SET description=excluded.description",
                 (slug, lslug, description.strip() or name, rel(ldir)))
    return {"slug": lslug, "dir": rel(ldir)}


def add_look_image(conn: sqlite3.Connection, slug: str, look: str, src: str | Path) -> str:
    lk = conn.execute("SELECT dir FROM looks WHERE character_slug=? AND slug=?", (slug, look)).fetchone()
    if lk is None:
        raise ProductionError(f"Tenue inconnue : {look}")
    src = Path(src)
    if src.suffix.lower() not in IMAGE_EXT:
        raise ProductionError("Une photo de tenue doit être une image (png, jpg, webp)")
    dest = _free_name(absp(lk["dir"]) / f"{slugify(src.stem) or 'photo'}{src.suffix.lower()}")
    shutil.copy(src, dest)
    return rel(dest)


# --- Personnages : parcours dans la régie -----------------------------------------
#
# 1. Michael dépose le brouillon de la canon (une image qu'il a faite ailleurs).
# 2. La canon HD est générée automatiquement par agrandissement fidèle.
# 3. Michael compare brouillon et HD côte à côte, puis valide la HD, la fait
#    refaire, ou garde le brouillon tel quel.
# 4. Michael écrit ses instructions et lance le pack : l'agent directeur-casting
#    génère les autres images (angles, silhouette, expressions, lumières...).
# 5. Michael garde ou rejette chaque image (avec un commentaire), relance si besoin,
#    puis valide la version.

def new_character(conn: sqlite3.Connection, name: str, notes: str = "") -> dict:
    if not name.strip():
        raise ProductionError("Donne un nom au personnage")
    slug = slugify(name)
    if conn.execute("SELECT 1 FROM characters WHERE slug=?", (slug,)).fetchone():
        raise ProductionError(f"Le personnage {name} existe déjà")
    create_character(conn, slug, name.strip(), notes)
    new_character_version(conn, slug)
    return character_snapshot(conn, slug)


def _draft_version(conn: sqlite3.Connection, slug: str, version: int) -> dict:
    v = character_version(conn, slug, version)
    if v["status"] != "draft":
        raise ProductionError(f"{slug} v{version} est validée : crée une nouvelle version pour la faire évoluer")
    return v


def upload_canon_draft(conn: sqlite3.Connection, slug: str, version: int, src: str | Path) -> dict:
    """Michael dépose le brouillon de la canon ; la canon HD part aussitôt."""
    v = _draft_version(conn, slug, version)
    src = Path(src)
    if src.suffix.lower() not in IMAGE_EXT:
        raise ProductionError("Le brouillon de la canon doit être une image (png, jpg, webp)")
    vdir = absp(v["dir"])
    dest = _free_name(vdir / "brouillons" / f"canon-brouillon{src.suffix.lower()}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    with db.tx(conn):
        conn.execute("UPDATE character_assets SET status='rejected' WHERE version_id=? AND kind='canon_draft' "
                     "AND status='kept'", (v["id"],))
        cur = conn.execute(
            "INSERT INTO character_assets (version_id, kind, label, path, status, created_at) VALUES (?,?,?,?,?,?)",
            (v["id"], "canon_draft", "brouillon canon", rel(dest), "kept", db.now()),
        )
        db.log_event(conn, None, "casting", f"{slug} v{version} : brouillon de canon déposé")
    draft_id = cur.lastrowid
    launch_canon_hd(conn, slug, version)
    return db.row(conn.execute("SELECT * FROM character_assets WHERE id=?", (draft_id,)).fetchone())


def launch_canon_hd(conn: sqlite3.Connection, slug: str, version: int, model_key: str | None = None,
                    approved: bool = False) -> dict:
    v = _draft_version(conn, slug, version)
    draft = db.row(conn.execute(
        "SELECT * FROM character_assets WHERE version_id=? AND kind='canon_draft' AND status='kept' "
        "ORDER BY id DESC LIMIT 1", (v["id"],)).fetchone())
    if draft is None:
        raise ProductionError("Dépose d'abord le brouillon de la canon")
    model_key = model_key or routing.pick_model("canon_hd")
    mcfg = routing.model(model_key)
    payload = routing.build_payload(mcfg, prompt=_canon_hd_prompt(absp(v["dir"])),
                                    image_urls=[fal.to_data_uri(absp(draft["path"]))], mode="final",
                                    aspect_ratio="3:4")
    if _needs_approval(mcfg.get("provider", "fal"), routing.estimate_cost(mcfg, mode="final"), False, approved):
        tries = conn.execute("SELECT COUNT(*) FROM character_assets WHERE parent_id=?", (draft["id"],)).fetchone()[0]
        return _ask_spend(conn, "canon_hd", {"slug": slug, "version": version, "model_key": model_key},
                          _hash(slug, version, draft["id"], tries), f"{slug} v{version} : canon HD photoréaliste",
                          routing.estimate_cost(mcfg, mode="final"), mcfg, model_key,
                          detail=f"À partir du brouillon {draft['path']}", character_slug=slug)
    sub = providers.submit(mcfg, payload, kind="image", label=f"{slug} canon HD")
    out = absp(v["dir"]) / "brouillons" / f"canon-hd-{sub['request_id'][-6:]}.png"
    with db.tx(conn):
        cur = conn.execute(
            "INSERT INTO character_assets (version_id, kind, label, path, model_key, cost_usd, funding, status, "
            "parent_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (v["id"], "canon", "canon HD", rel(out), model_key, routing.estimate_cost(mcfg, mode="final"),
             credits.funding_for(conn, mcfg.get("provider", "fal"), routing.estimate_cost(mcfg, mode="final")),
             "generating", draft["id"], db.now()),
        )
        _insert_job(conn, "character_assets", cur.lastrowid, mcfg["endpoint"], sub, out)
        db.log_event(conn, None, "casting", f"{slug} v{version} : canon HD lancée ({mcfg.get('label', model_key)})")
    return {"asset_id": cur.lastrowid, "model_key": model_key}


def _canon_hd_prompt(vdir: Path) -> str:
    """Prompt de la canon HD : le brouillon de Michael devient une photo réaliste, même personnage."""
    adn = (vdir / "adn.md").read_text(encoding="utf-8") if (vdir / "adn.md").is_file() else ""
    instr = (vdir / "instructions.md").read_text(encoding="utf-8") if (vdir / "instructions.md").is_file() else ""
    return ("Turn the reference image into a true photograph of the same person: keep exactly the same face shape, "
            "eyes (shape and color), nose, lips, skin tone, freckles, hair (texture, length, volume, color), "
            "outfit and pose. Do not beautify, do not change identity. Real skin texture with visible pores and fine "
            "vellus hair, slight natural asymmetry, no retouching. Portrait photography, 85mm lens, f/2.8, soft "
            "natural light, neutral background, true-to-life colors, high resolution."
            + (f"\n\nCharacter sheet (French, authoritative):\n{adn.strip()}" if adn.strip() else "")
            + (f"\n\nDirector's notes (French):\n{instr.strip()}" if instr.strip() else ""))


def review_canon_hd(conn: sqlite3.Connection, asset_id: int, decision: str, comment: str = "") -> None:
    """approve : la HD devient la canon. redo : on refait la HD (autre outil).
    use_draft : le brouillon devient la canon tel quel."""
    a = db.row(conn.execute("SELECT * FROM character_assets WHERE id=?", (asset_id,)).fetchone())
    if a is None or a["kind"] != "canon" or not a.get("parent_id"):
        raise ProductionError("Ce n'est pas une canon HD")
    v = db.row(conn.execute("SELECT * FROM character_versions WHERE id=?", (a["version_id"],)).fetchone())
    if decision == "approve":
        review_character_asset(conn, asset_id, "canon")
        return
    if decision == "redo":
        conn.execute("UPDATE character_assets SET status='rejected', comment=? WHERE id=?", (comment or None, asset_id))
        launch_canon_hd(conn, v["character_slug"], v["version"])
        return
    if decision == "use_draft":
        draft = db.row(conn.execute("SELECT * FROM character_assets WHERE id=?", (a["parent_id"],)).fetchone())
        src = absp(draft["path"])
        copy = src.with_name(f"canon-depuis-brouillon-{asset_id}{src.suffix}")
        shutil.copy(src, copy)
        with db.tx(conn):
            conn.execute("UPDATE character_assets SET status='rejected', comment=? WHERE id=?",
                         (comment or "Brouillon gardé tel quel", asset_id))
            cur = conn.execute(
                "INSERT INTO character_assets (version_id, kind, label, path, status, parent_id, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (v["id"], "canon", "canon (brouillon)", rel(copy), "proposed", draft["id"], db.now()),
            )
        review_character_asset(conn, cur.lastrowid, "canon")
        return
    raise ProductionError("Décision : approve, redo ou use_draft")


def set_instructions(conn: sqlite3.Connection, slug: str, version: int, text: str) -> None:
    v = _draft_version(conn, slug, version)
    conn.execute("UPDATE character_versions SET instructions=? WHERE id=?", (text.strip(), v["id"]))
    (absp(v["dir"]) / "instructions.md").write_text(text.strip() + "\n", encoding="utf-8")


def request_pack(conn: sqlite3.Connection, slug: str, version: int) -> None:
    """Michael lance la génération du pack d'après ses instructions (agent directeur-casting)."""
    v = _draft_version(conn, slug, version)
    if not conn.execute("SELECT 1 FROM character_assets WHERE version_id=? AND kind='canon' AND status='kept'",
                        (v["id"],)).fetchone():
        raise ProductionError("Valide d'abord la canon HD")
    if not (v.get("instructions") or "").strip():
        raise ProductionError("Écris d'abord tes instructions pour le pack")
    with db.tx(conn):
        conn.execute("UPDATE character_versions SET pack_status='requested' WHERE id=?", (v["id"],))
        db.log_event(conn, None, "casting", f"{slug} v{version} : pack demandé")


def pack_done(conn: sqlite3.Connection, slug: str, version: int) -> None:
    """L'agent a lancé toutes les images du pack demandé."""
    v = character_version(conn, slug, version)
    conn.execute("UPDATE character_versions SET pack_status='done' WHERE id=?", (v["id"],))
    db.log_event(conn, None, "casting", f"{slug} v{version} : pack lancé par le directeur de casting")


def comment_character_asset(conn: sqlite3.Connection, asset_id: int, comment: str) -> None:
    conn.execute("UPDATE character_assets SET comment=? WHERE id=?", (comment.strip() or None, asset_id))


def characters_needing_agent(conn: sqlite3.Connection) -> list[dict]:
    """Versions brouillon dont Michael a demandé le pack (le worker réveille /casting)."""
    out = []
    for v in db.rows(conn.execute(
            "SELECT * FROM character_versions WHERE status='draft' AND pack_status='requested'").fetchall()):
        fp = hashlib.sha1(json.dumps([v["id"], v.get("instructions"), "pack"]).encode()).hexdigest()[:16]
        out.append({"slug": v["character_slug"], "version": v["version"], "fingerprint": fp})
    return out


# --- Clips ------------------------------------------------------------------

def create_clip(conn: sqlite3.Connection, title: str, *, slug: str | None = None,
                song: str | Path | None = None, vocals: str | Path | None = None,
                script_text: str | None = None, script_file: str | Path | None = None,
                bpm: float | None = None, aspect: str = "16:9", budget_usd: float | None = None,
                characters: list[str] | None = None, pitch: str | None = None,
                concept: str | None = None, lyrics_text: str | None = None,
                dossier: list[str | Path] | None = None, lyrics_files: list[str | Path] | None = None) -> dict:
    slug = slugify(slug or title)
    cdir = studio() / "clips" / slug
    if conn.execute("SELECT 1 FROM clips WHERE slug=?", (slug,)).fetchone():
        raise ProductionError(f"Le clip {slug} existe déjà")
    for sub in ("song", "script", "dossier", "storyboard", "drafts", "finals", "montage", "work"):
        (cdir / sub).mkdir(parents=True, exist_ok=True)
    script_path = None
    if script_file:
        script_text = Path(script_file).read_text(encoding="utf-8")
    if script_text:
        dest = cdir / "script" / "script.md"
        dest.write_text(script_text, encoding="utf-8")
        script_path = rel(dest)
    budget = budget_usd if budget_usd is not None else load_models().get("budget", {}).get("default_clip_usd")
    with db.tx(conn):
        conn.execute(
            "INSERT INTO clips (slug, title, dir, stage, script_path, bpm, aspect_ratio, budget_usd, pitch, concept, "
            "brief_ready, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (slug, title, rel(cdir), "script", script_path, bpm, aspect, budget, pitch, concept,
             1 if script_text else 0, db.now(), db.now()),
        )
        for c in characters or []:
            set_casting(conn, slug, c)
        db.log_event(conn, slug, "clip", f"Clip créé : {title}")
    if song:
        add_clip_file(conn, slug, "song", song)
    if vocals:
        add_clip_file(conn, slug, "vocals", vocals)
    for f in dossier or []:
        add_clip_file(conn, slug, "dossier", f)
    for f in lyrics_files or []:
        add_clip_file(conn, slug, "lyrics", f)
    if lyrics_text and lyrics_text.strip():
        save_lyrics_text(conn, slug, lyrics_text)
    return db.get_clip(conn, slug)


def add_clip_file(conn: sqlite3.Connection, slug: str, kind: str, src: str | Path,
                  label: str | None = None) -> dict:
    """Range un fichier déposé par Michael dans le dossier du clip.

    song / vocals : le morceau et la voix isolée (un seul de chaque, remplacé).
    dossier : dossier de réalisation, direction artistique, storytelling, moodboard.
    lyrics : paroles. reference : images ou documents de référence.
    Les documents (pdf, docx, txt, md) sont aussi convertis en texte pour les agents.
    """
    if kind not in db.CLIP_FILE_KINDS:
        raise ProductionError(f"Type de fichier inconnu : {kind}")
    clip = db.get_clip(conn, slug)
    src = Path(src)
    cdir = studio() / clip["dir"]
    name = label or src.name
    if kind in ("song", "vocals"):
        dest = cdir / "song" / f"{'master' if kind == 'song' else 'vocals'}{src.suffix.lower()}"
        for old in (cdir / "song").glob(("master" if kind == "song" else "vocals") + ".*"):
            old.unlink()
    else:
        folder = cdir / ("script" if kind == "lyrics" else "dossier")
        folder.mkdir(parents=True, exist_ok=True)
        dest = _free_name(folder / _safe_name(src.name))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    text_path = media.extract_text(dest)
    with db.tx(conn):
        if kind in ("song", "vocals"):
            conn.execute("DELETE FROM clip_files WHERE clip_slug=? AND kind=?", (slug, kind))
            col = "song_path" if kind == "song" else "vocals_path"
            conn.execute(f"UPDATE clips SET {col}=?, updated_at=? WHERE slug=?", (rel(dest), db.now(), slug))
            if kind == "song":
                try:
                    conn.execute("UPDATE clips SET duration_s=? WHERE slug=?", (media.duration(dest), slug))
                except media.MediaError:
                    pass
        cur = conn.execute(
            "INSERT INTO clip_files (clip_slug, kind, label, path, text_path, created_at) VALUES (?,?,?,?,?,?)",
            (slug, kind, name, rel(dest), rel(text_path) if text_path else None, db.now()),
        )
        conn.execute("UPDATE clips SET updated_at=? WHERE slug=?", (db.now(), slug))
        db.log_event(conn, slug, "dossier", f"Fichier ajouté ({FILE_KIND_LABEL.get(kind, kind)}) : {name}")
    return db.row(conn.execute("SELECT * FROM clip_files WHERE id=?", (cur.lastrowid,)).fetchone())


FILE_KIND_LABEL = {"song": "morceau", "vocals": "voix isolée", "dossier": "dossier de réalisation",
                   "lyrics": "paroles", "reference": "référence"}


def _safe_name(name: str) -> str:
    stem, suffix = Path(name).stem, Path(name).suffix.lower()
    return f"{slugify(stem)[:60]}{suffix}"


def _free_name(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 1000):
        cand = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not cand.exists():
            return cand
    raise ProductionError("Trop de fichiers du même nom")


def remove_clip_file(conn: sqlite3.Connection, file_id: int) -> None:
    f = db.row(conn.execute("SELECT * FROM clip_files WHERE id=?", (file_id,)).fetchone())
    if f is None:
        raise ProductionError("Fichier inconnu")
    if f["kind"] == "song":
        raise ProductionError("Le morceau se remplace, il ne se supprime pas")
    with db.tx(conn):
        conn.execute("DELETE FROM clip_files WHERE id=?", (file_id,))
        if f["kind"] == "vocals":
            conn.execute("UPDATE clips SET vocals_path=NULL WHERE slug=?", (f["clip_slug"],))
        db.log_event(conn, f["clip_slug"], "dossier", f"Fichier retiré : {f['label']}")
    # Le fichier reste sur le disque dans un sous-dossier « retires » : rien n'est perdu.
    src = absp(f["path"])
    if src and src.is_file():
        bin_dir = src.parent / "retires"
        bin_dir.mkdir(exist_ok=True)
        src.rename(_free_name(bin_dir / src.name))


def save_lyrics_text(conn: sqlite3.Connection, slug: str, text: str) -> None:
    """Paroles collées dans la régie : enregistrées dans script/paroles.md."""
    clip = db.get_clip(conn, slug)
    dest = studio() / clip["dir"] / "script" / "paroles.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text.strip() + "\n", encoding="utf-8")
    with db.tx(conn):
        conn.execute("DELETE FROM clip_files WHERE clip_slug=? AND kind='lyrics' AND path=?", (slug, rel(dest)))
        if text.strip():
            conn.execute(
                "INSERT INTO clip_files (clip_slug, kind, label, path, text_path, created_at) VALUES (?,?,?,?,?,?)",
                (slug, "lyrics", "Paroles (saisies dans la régie)", rel(dest), rel(dest), db.now()),
            )
        conn.execute("UPDATE clips SET updated_at=? WHERE slug=?", (db.now(), slug))
        db.log_event(conn, slug, "dossier", "Paroles mises à jour")


def update_brief(conn: sqlite3.Connection, slug: str, *, title: str | None = None, pitch: str | None = None,
                 concept: str | None = None, aspect: str | None = None, budget_usd: float | None = None) -> dict:
    """Michael modifie le titre, le pitch, le concept ou les réglages du clip."""
    db.get_clip(conn, slug)
    sets, vals = [], []
    for col, val in (("title", title), ("pitch", pitch), ("concept", concept), ("aspect_ratio", aspect),
                     ("budget_usd", budget_usd)):
        if val is not None:
            sets.append(f"{col}=?")
            vals.append(val.strip() if isinstance(val, str) else val)
    if aspect is not None and aspect not in ("16:9", "9:16", "1:1", "4:5"):
        raise ProductionError("Format inconnu")
    if sets:
        conn.execute(f"UPDATE clips SET {', '.join(sets)}, updated_at=? WHERE slug=?", (*vals, db.now(), slug))
    return db.get_clip(conn, slug)


def submit_brief(conn: sqlite3.Connection, slug: str) -> None:
    """Michael envoie son dossier au script doctor, qui prépare le découpage."""
    clip = db.get_clip(conn, slug)
    if clip["stage"] != "script":
        raise ProductionError("Le découpage est déjà fait")
    if not clip.get("song_path"):
        raise ProductionError("Ajoute d'abord le morceau")
    has_shots = conn.execute("SELECT 1 FROM shots WHERE clip_slug=?", (slug,)).fetchone()
    has_docs = conn.execute(
        "SELECT 1 FROM clip_files WHERE clip_slug=? AND kind IN ('dossier','lyrics')", (slug,)).fetchone()
    if not (has_shots or has_docs or clip.get("script_path")):
        raise ProductionError("Saisis ton découpage ou dépose ton dossier de réalisation avant d'envoyer")
    with db.tx(conn):
        conn.execute("UPDATE clips SET brief_ready=1, updated_at=? WHERE slug=?", (db.now(), slug))
        db.log_event(conn, slug, "script", "Dossier envoyé au script doctor")


def clip_files(conn: sqlite3.Connection, slug: str) -> list[dict]:
    return db.rows(conn.execute("SELECT * FROM clip_files WHERE clip_slug=? ORDER BY kind, id", (slug,)).fetchall())


def set_casting(conn: sqlite3.Connection, clip_slug: str, character_slug: str,
                version: int | None = None, look: str | None = None) -> None:
    ch = conn.execute("SELECT * FROM characters WHERE slug=?", (character_slug,)).fetchone()
    if ch is None:
        raise ProductionError(f"Personnage inconnu : {character_slug}")
    version = version or ch["canon_version"]
    if not version:
        raise ProductionError(f"{character_slug} n'a pas de version canon validée")
    v = character_version(conn, character_slug, version)
    if v["status"] != "validated":
        raise ProductionError(f"{character_slug} v{version} n'est pas validée : seule une version validée peut être castée")
    conn.execute(
        "INSERT INTO castings (clip_slug, character_slug, version, look_slug) VALUES (?,?,?,?) "
        "ON CONFLICT(clip_slug, character_slug) DO UPDATE SET version=excluded.version, look_slug=excluded.look_slug",
        (clip_slug, character_slug, version, look),
    )


def set_stage(conn: sqlite3.Connection, slug: str, stage: str) -> None:
    if stage not in db.CLIP_STAGES:
        raise ProductionError(f"Étape invalide : {stage}")
    conn.execute("UPDATE clips SET stage=?, updated_at=? WHERE slug=?", (stage, db.now(), slug))
    db.log_event(conn, slug, "stage", f"Étape : {stage}")


SHOT_FIELDS = {"num", "section", "t_start", "t_end", "description", "framing", "motion", "camera",
               "characters", "singing", "notes", "id", "block"}
BLOCK_FIELDS = {"name", "intention", "shots", "num", "id"}


def _flatten_decoupage(data: Any) -> list[tuple[dict, list[dict]]]:
    """Accepte {"blocks": [{name, intention, shots: [...]}]}, {"shots": [...]} ou une liste de plans.

    Sans blocs, les plans sont regroupés par « section » (une section = un bloc).
    """
    if isinstance(data, dict) and "blocks" in data:
        out = []
        for i, b in enumerate(data["blocks"], 1):
            unknown = set(b) - BLOCK_FIELDS
            if unknown:
                raise ProductionError(f"Bloc {i} : champs inconnus {sorted(unknown)}")
            if not str(b.get("name") or "").strip():
                raise ProductionError(f"Bloc {i} : il faut un nom (intro, couplet 1, refrain…)")
            out.append(({"name": b["name"].strip(), "intention": b.get("intention")}, list(b.get("shots") or [])))
        return out
    shots = data["shots"] if isinstance(data, dict) else data
    groups: list[tuple[dict, list[dict]]] = []
    for sh in sorted(shots, key=lambda x: float(x.get("t_start", 0))):
        name = (sh.get("section") or "Séquence").strip()
        if not groups or groups[-1][0]["name"] != name:
            groups.append(({"name": name, "intention": None}, []))
        groups[-1][1].append(sh)
    return groups


def import_shots(conn: sqlite3.Connection, slug: str, shots: Any) -> int:
    """Remplace le découpage d'un clip (tant qu'il n'est pas validé). Retourne le nombre de plans."""
    clip = db.get_clip(conn, slug)
    if clip["stage"] not in ("script", "decoupage_review"):
        raise ProductionError("Le découpage est déjà validé : modifie les plans un par un avec `riot shot set`")
    cast = {c["character_slug"] for c in db.casting_for_clip(conn, slug)}
    blocks = _flatten_decoupage(shots)
    n = 0
    for bi, (block, items) in enumerate(blocks, 1):
        for s in items:
            n += 1
            where = f"Bloc « {block['name']} », plan {n}"
            unknown = set(s) - SHOT_FIELDS
            if unknown:
                raise ProductionError(f"{where} : champs inconnus {sorted(unknown)}")
            for req in ("t_start", "t_end", "description"):
                if s.get(req) in (None, ""):
                    raise ProductionError(f"{where} : il manque {'le début' if req == 't_start' else 'la fin' if req == 't_end' else 'la description'}")
            if float(s["t_end"]) <= float(s["t_start"]):
                raise ProductionError(f"{where} : la fin doit être après le début")
            if s.get("framing") and s["framing"] not in db.FRAMINGS:
                raise ProductionError(f"{where} : cadrage '{s['framing']}' invalide ({', '.join(db.FRAMINGS)})")
            if s.get("motion") and s["motion"] not in db.MOTIONS:
                raise ProductionError(f"{where} : mouvement '{s['motion']}' invalide ({', '.join(db.MOTIONS)})")
            missing = set(s.get("characters") or []) - cast
            if missing:
                raise ProductionError(f"{where} : personnages non castés dans ce clip : {sorted(missing)}")
    with db.tx(conn):
        conn.execute("DELETE FROM shots WHERE clip_slug=?", (slug,))
        conn.execute("DELETE FROM blocks WHERE clip_slug=?", (slug,))
        num = 0
        for bi, (block, items) in enumerate(blocks, 1):
            cur = conn.execute("INSERT INTO blocks (clip_slug, num, name, intention) VALUES (?,?,?,?)",
                               (slug, bi, block["name"], block.get("intention")))
            bid = cur.lastrowid
            for s in sorted(items, key=lambda x: float(x["t_start"])):
                num += 1
                conn.execute(
                    "INSERT INTO shots (clip_slug, num, block_id, section, t_start, t_end, description, framing, motion, "
                    "camera, characters, singing, notes, status, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (slug, num, bid, block["name"], float(s["t_start"]), float(s["t_end"]), s["description"].strip(),
                     s.get("framing") or None, s.get("motion") or None, s.get("camera") or None,
                     json.dumps(s.get("characters") or []), 1 if s.get("singing") else 0, s.get("notes"),
                     "image_todo", db.now()),
                )
        conn.execute("UPDATE clips SET updated_at=? WHERE slug=?", (db.now(), slug))
        db.log_event(conn, slug, "decoupage", f"Découpage enregistré : {len(blocks)} blocs, {num} plans")
    return num


def decoupage(conn: sqlite3.Connection, slug: str) -> list[dict]:
    """Le découpage sous forme de blocs contenant leurs plans."""
    blocks = db.rows(conn.execute("SELECT * FROM blocks WHERE clip_slug=? ORDER BY num", (slug,)).fetchall())
    shots = db.rows(conn.execute("SELECT * FROM shots WHERE clip_slug=? ORDER BY num", (slug,)).fetchall())
    by_block: dict[int | None, list] = {}
    for sh in shots:
        by_block.setdefault(sh.get("block_id"), []).append(sh)
    for b in blocks:
        b["shots"] = by_block.pop(b["id"], [])
        if b["shots"]:
            b["t_start"], b["t_end"] = b["shots"][0]["t_start"], b["shots"][-1]["t_end"]
    if by_block:  # plans d'un ancien découpage sans bloc
        orphans = [sh for v in by_block.values() for sh in v]
        blocks.append({"id": None, "num": len(blocks) + 1, "name": "Sans bloc", "intention": None, "shots": orphans,
                       "t_start": orphans[0]["t_start"], "t_end": orphans[-1]["t_end"]})
    return blocks


SETTABLE = {"section", "description", "framing", "motion", "camera", "characters", "singing", "tier",
            "model_key", "route_reason", "seed", "image_prompt", "video_prompt", "negative_prompt", "notes", "t_start", "t_end"}


def update_shot(conn: sqlite3.Connection, shot_id: int, **fields: Any) -> dict:
    sets, values = [], []
    for k, v in fields.items():
        if v is None:
            continue
        if k not in SETTABLE:
            raise ProductionError(f"Champ non modifiable : {k}")
        if k == "framing" and v not in db.FRAMINGS:
            raise ProductionError(f"Cadrage invalide : {v}")
        if k == "motion" and v not in db.MOTIONS:
            raise ProductionError(f"Mouvement invalide : {v}")
        if k == "tier" and v not in routing.tier_order():
            raise ProductionError(f"Palier invalide : {v}")
        if k == "model_key":
            routing.model(v)
        if k == "characters" and not isinstance(v, str):
            v = json.dumps(v)
        if k == "singing":
            v = 1 if v in (True, 1, "1", "true", "oui", "yes") else 0
        sets.append(f"{k}=?")
        values.append(v)
    if sets:
        conn.execute(f"UPDATE shots SET {', '.join(sets)}, updated_at=? WHERE id=?", (*values, db.now(), shot_id))
    return db.get_shot(conn, shot_id)


def _check_budget(conn: sqlite3.Connection, slug: str, extra: float, force: bool,
                  model_cfg: dict | None = None) -> None:
    clip = db.get_clip(conn, slug)
    budget = clip.get("budget_usd")
    if not budget or force:
        return
    if model_cfg and credits.funding_for(conn, model_cfg.get("provider", "fal"), extra) == "credits":
        return   # payé par des crédits : le budget en argent n'est pas touché
    spent = db.clip_cost(conn, slug)
    if spent + extra > budget:
        raise BudgetError(
            f"Budget du clip dépassé : {spent:.2f} $ dépensés + {extra:.2f} $ estimés > {budget:.2f} $. "
            "Demande à Michael d'augmenter le budget (riot clip budget) ou relance avec --force."
        )


def _insert_job(conn: sqlite3.Connection, table: str, target_id: int, endpoint: str,
                sub: dict, out: Path) -> int:
    cur = conn.execute(
        "INSERT INTO jobs (target_table, target_id, endpoint, provider, request_id, status_url, response_url, "
        "output_path, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (table, target_id, endpoint, sub.get("provider", "fal"), sub["request_id"], sub["status_url"],
         sub["response_url"], rel(out), "queued", db.now(), db.now()),
    )
    return cur.lastrowid


def _create_asset(conn: sqlite3.Connection, shot: dict, kind: str, out_dir: str, ext: str,
                  prompt: str | None, model_key: str, seed: int | None, params: dict, cost: float,
                  endpoint: str, sub: dict) -> dict:
    version = db.next_asset_version(conn, shot["id"], kind)
    funding = "cash" if is_demo(shot["clip_slug"]) else \
        credits.funding_for(conn, routing.model(model_key).get("provider", "fal"), cost)
    suffix = {"lipsync": "-lipsync", "image_hd": "-hd"}.get(kind, "")
    out = studio() / "clips" / shot["clip_slug"] / out_dir / f"plan-{shot['num']:03d}{suffix}-v{version}{ext}"
    with db.tx(conn):
        conn.execute(
            "UPDATE assets SET status='superseded' WHERE shot_id=? AND kind=? AND status IN ('ready','failed')",
            (shot["id"], kind),
        )
        cur = conn.execute(
            "INSERT INTO assets (shot_id, kind, version, path, prompt, model_key, seed, params, cost_usd, funding, "
            "status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (shot["id"], kind, version, rel(out), prompt, model_key, seed,
             json.dumps({k: v for k, v in params.items() if not str(v).startswith("data:")}),
             cost, funding, "generating", db.now()),
        )
        _insert_job(conn, "assets", cur.lastrowid, endpoint, sub, out)
    return {"asset_id": cur.lastrowid, "version": version, "path": rel(out), "cost_usd": cost,
            "request_id": sub["request_id"]}


def launch_image(conn: sqlite3.Connection, shot_id: int, force: bool = False, approved: bool = False) -> dict:
    shot = db.get_shot(conn, shot_id)
    if not shot.get("image_prompt"):
        raise ProductionError("Le plan n'a pas encore de prompt image (riot shot set --image-prompt)")
    clip = db.get_clip(conn, shot["clip_slug"])
    cfg = load_models()
    key = routing.pick_model("storyboard")
    mcfg = routing.model(key)
    casting = {c["character_slug"]: c for c in db.casting_for_clip(conn, clip["slug"])}
    refs: list[Path] = []
    per_char = max(2, int(mcfg.get("max_refs", 6)) // max(1, len(shot["characters"]) or 1))
    for c in shot["characters"]:
        if c in casting:
            refs += character_refs(conn, c, casting[c]["version"], casting[c]["look_slug"], limit=per_char)
    image_urls = [fal.to_data_uri(p) for p in refs]
    cost = routing.estimate_cost(mcfg, mode="draft")
    _check_budget(conn, clip["slug"], cost, force, mcfg)
    payload = routing.build_payload(mcfg, prompt=shot["image_prompt"], image_urls=image_urls,
                                    aspect_ratio=clip["aspect_ratio"], mode="draft")
    if _needs_approval(mcfg.get("provider", "fal"), cost, is_demo(clip["slug"]), approved):
        return _ask_spend(conn, "image", {"shot_id": shot_id, "force": force},
                          _hash(shot_id, shot["image_prompt"], key), f"Plan {shot['num']} : visuel draft",
                          cost, mcfg, key, detail=shot["image_prompt"], clip_slug=clip["slug"], shot_id=shot_id)
    sub = providers.submit(mcfg, payload, kind="image", label=f"plan {shot['num']} image",
                     force_mock=is_demo(clip["slug"]))
    res = _create_asset(conn, shot, "image", "storyboard", ".png", shot["image_prompt"], key, None,
                        payload, cost, mcfg["endpoint"], sub)
    db.set_shot_status(conn, shot_id, "image_gen")
    res["refs"] = [rel(p) for p in refs]
    return res


def launch_image_hd(conn: sqlite3.Connection, shot_id: int, force: bool = False,
                    model_key: str | None = None, approved: bool = False) -> dict:
    """Agrandit l'image de travail validée par Michael (automatique, fidèle à l'original)."""
    shot = db.get_shot(conn, shot_id)
    image = db.row(conn.execute(
        "SELECT * FROM assets WHERE shot_id=? AND kind='image' AND status='validated' ORDER BY version DESC LIMIT 1",
        (shot_id,),
    ).fetchone())
    if image is None:
        raise ProductionError("Aucune image validée par Michael pour ce plan")
    clip = db.get_clip(conn, shot["clip_slug"])
    if not model_key:
        tries = conn.execute("SELECT COUNT(*) FROM assets WHERE shot_id=? AND kind='image_hd' AND status='rejected'",
                             (shot_id,)).fetchone()[0]
        model_key = routing.pick_model("upscale_fallback" if tries else "upscale")
    mcfg = routing.model(model_key)
    cost = routing.estimate_cost(mcfg, mode="final")
    _check_budget(conn, clip["slug"], cost, force, mcfg)
    ref = image["remote_url"] if image["remote_url"] and not str(image["remote_url"]).startswith("mock://") \
        else fal.to_data_uri(absp(image["path"]))
    payload = routing.build_payload(mcfg, image_urls=[ref], mode="final")
    if _needs_approval(mcfg.get("provider", "fal"), cost, is_demo(clip["slug"]), approved):
        return _ask_spend(conn, "image_hd", {"shot_id": shot_id, "force": force, "model_key": model_key},
                          _hash(shot_id, image["id"], model_key), f"Plan {shot['num']} : visuel HD",
                          cost, mcfg, model_key, detail="Agrandissement du visuel validé",
                          clip_slug=clip["slug"], shot_id=shot_id)
    sub = providers.submit(mcfg, payload, kind="image", label=f"plan {shot['num']} HD",
                     force_mock=is_demo(clip["slug"]))
    params = {**payload, "from_image": image["id"]}
    res = _create_asset(conn, shot, "image_hd", "storyboard", ".png", None, model_key, None,
                        params, cost, mcfg["endpoint"], sub)
    db.set_shot_status(conn, shot_id, "hd_gen")
    return res


def keyframe_for_video(conn: sqlite3.Connection, shot_id: int) -> dict | None:
    """L'image de départ de la vidéo : la HD si elle est retenue, sinon l'image validée."""
    hd = db.row(conn.execute(
        "SELECT * FROM assets WHERE shot_id=? AND kind='image_hd' AND status IN ('validated','ready') "
        "ORDER BY version DESC LIMIT 1", (shot_id,)).fetchone())
    if hd:
        return hd
    return db.row(conn.execute(
        "SELECT * FROM assets WHERE shot_id=? AND kind='image' AND status='validated' ORDER BY version DESC LIMIT 1",
        (shot_id,)).fetchone())


def submit_video_plan(conn: sqlite3.Connection, shot_id: int) -> dict:
    """L'orchestrateur présente à Michael le plan vidéo : modèle, prompt, coût. Rien n'est encore dépensé."""
    shot = db.get_shot(conn, shot_id)
    if shot["status"] not in ("prompt_todo", "video_review"):
        raise ProductionError(f"Le plan {shot['num']} n'est pas à l'étape du prompt vidéo ({shot['status']})")
    if not shot.get("model_key"):
        raise ProductionError("Le plan n'a pas de modèle : lance d'abord `riot route <id> --apply`")
    if not shot.get("video_prompt"):
        raise ProductionError("Le plan n'a pas de prompt vidéo (riot shot set --video-prompt)")
    est = routing.route_shot(shot, model_key=shot["model_key"])
    db.set_shot_status(conn, shot_id, "video_review")
    db.log_event(conn, shot["clip_slug"], "videoplan",
                 f"Plan {shot['num']} : plan vidéo prêt ({est['model_label']}, ~{est['cost_total_usd']:.2f} $)")
    return est


def choose_model(conn: sqlite3.Connection, shot_id: int, model_key: str) -> dict:
    """Michael change le modèle vidéo d'un plan avant de valider."""
    shot = db.get_shot(conn, shot_id)
    if shot["status"] != "video_review":
        raise ProductionError("On ne change le modèle qu'au moment de valider le plan vidéo")
    cfg = routing.model(model_key)
    if cfg.get("kind") != "video":
        raise ProductionError(f"{model_key} n'est pas un modèle vidéo")
    if not routing.provider_usable(cfg.get("provider", "fal")):
        raise ProductionError(f"Le fournisseur {cfg.get('provider')} n'est pas branché")
    est = routing.route_shot(shot, model_key=model_key)
    conn.execute("UPDATE shots SET model_key=?, tier=?, route_reason=?, updated_at=? WHERE id=?",
                 (model_key, est["tier"], "Choisi par Michael", db.now(), shot_id))
    db.log_event(conn, shot["clip_slug"], "videoplan", f"Plan {shot['num']} : modèle changé pour {est['model_label']}")
    return est


def edit_video_prompt(conn: sqlite3.Connection, shot_id: int, prompt: str) -> None:
    shot = db.get_shot(conn, shot_id)
    if shot["status"] != "video_review":
        raise ProductionError("Le prompt se modifie au moment de valider le plan vidéo")
    if not prompt.strip():
        raise ProductionError("Le prompt est vide")
    conn.execute("UPDATE shots SET video_prompt=?, updated_at=? WHERE id=?", (prompt.strip(), db.now(), shot_id))
    db.log_event(conn, shot["clip_slug"], "videoplan", f"Plan {shot['num']} : prompt vidéo modifié par Michael")


def launch_draft(conn: sqlite3.Connection, shot_id: int, force: bool = False) -> dict:
    shot = db.get_shot(conn, shot_id)
    if not shot.get("video_prompt"):
        raise ProductionError("Le plan n'a pas de prompt vidéo (riot shot set --video-prompt)")
    if not shot.get("model_key"):
        raise ProductionError("Le plan n'a pas de modèle : lance d'abord `riot route <id> --apply`")
    image = keyframe_for_video(conn, shot_id)
    if image is None:
        raise ProductionError("Aucune image validée par Michael pour ce plan")
    clip = db.get_clip(conn, shot["clip_slug"])
    mcfg = routing.model(shot["model_key"])
    if not is_demo(clip["slug"]) and not routing.provider_usable(mcfg.get("provider", "fal")):
        raise ProductionError(f"Le fournisseur {mcfg.get('provider')} n'est pas branché")
    duration = routing.choose_duration(mcfg, routing.shot_seconds(shot))
    seed = shot.get("seed") or random.randint(1, 2**31 - 1)
    cost = routing.estimate_cost(mcfg, duration, "draft")
    _check_budget(conn, clip["slug"], cost, force, mcfg)
    image_ref = image["remote_url"] if image["remote_url"] and not str(image["remote_url"]).startswith("mock://") \
        else fal.to_data_uri(absp(image["path"]))
    payload = routing.build_payload(
        mcfg, prompt=shot["video_prompt"], image_urls=[image_ref], duration=duration, seed=seed,
        negative_prompt=shot.get("negative_prompt"), aspect_ratio=clip["aspect_ratio"], mode="draft",
    )
    sub = providers.submit(mcfg, payload, kind="video", label=f"plan {shot['num']} draft",
                     seconds=duration, force_mock=is_demo(clip["slug"]))
    res = _create_asset(conn, shot, "draft", "drafts", ".mp4", shot["video_prompt"], shot["model_key"], seed,
                        payload, cost, mcfg["endpoint"], sub)
    conn.execute("UPDATE shots SET seed=?, updated_at=? WHERE id=?", (seed, db.now(), shot_id))
    db.set_shot_status(conn, shot_id, "draft_gen")
    return res


def launch_final(conn: sqlite3.Connection, shot_id: int, force: bool = False) -> dict:
    """Rendu final du draft validé : upscale (identique au draft) ou re-rendu même seed."""
    shot = db.get_shot(conn, shot_id)
    draft = db.row(conn.execute(
        "SELECT * FROM assets WHERE shot_id=? AND kind='draft' AND status='validated' ORDER BY version DESC LIMIT 1",
        (shot_id,),
    ).fetchone())
    if draft is None:
        raise ProductionError("Aucun draft validé pour ce plan")
    clip = db.get_clip(conn, shot["clip_slug"])
    vcfg = routing.model(draft["model_key"])
    final_mode = vcfg.get("final_mode", "upscale")
    duration = routing.choose_duration(vcfg, routing.shot_seconds(shot))
    if final_mode == "keep":
        return _keep_draft_as_final(conn, shot, draft)
    if final_mode == "upscale":
        key = load_models()["upscale"]
        mcfg = routing.model(key)
        video_ref = draft["remote_url"] or fal.to_data_uri(absp(draft["path"]))
        payload = routing.build_payload(mcfg, video_url=video_ref, mode="final")
        prompt, seed = draft["prompt"], draft["seed"]
    else:
        key, mcfg = draft["model_key"], vcfg
        image = keyframe_for_video(conn, shot_id)
        image_ref = image["remote_url"] or fal.to_data_uri(absp(image["path"]))
        payload = routing.build_payload(
            mcfg, prompt=draft["prompt"], image_urls=[image_ref], duration=duration, seed=draft["seed"],
            negative_prompt=shot.get("negative_prompt"), aspect_ratio=clip["aspect_ratio"], mode="final",
        )
        prompt, seed = draft["prompt"], draft["seed"]
    cost = routing.estimate_cost(mcfg, duration, "final")
    _check_budget(conn, clip["slug"], cost, force, mcfg)
    sub = providers.submit(mcfg, payload, kind="video", label=f"plan {shot['num']} final",
                     seconds=duration, force_mock=is_demo(clip["slug"]))
    res = _create_asset(conn, shot, "final", "finals", ".mp4", prompt, key, seed, payload, cost,
                        mcfg["endpoint"], sub)
    db.set_shot_status(conn, shot_id, "final_gen")
    res["final_mode"] = final_mode
    return res


def _keep_draft_as_final(conn: sqlite3.Connection, shot: dict, draft: dict) -> dict:
    """Modèle sans basse résolution : le draft validé est déjà le final."""
    version = db.next_asset_version(conn, shot["id"], "final")
    src = absp(draft["path"])
    out = studio() / "clips" / shot["clip_slug"] / "finals" / f"plan-{shot['num']:03d}-v{version}{src.suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, out)
    next_status = "lipsync_todo" if shot["singing"] else "final_review"
    with db.tx(conn):
        cur = conn.execute(
            "INSERT INTO assets (shot_id, kind, version, path, remote_url, prompt, model_key, seed, params, "
            "cost_usd, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (shot["id"], "final", version, rel(out), draft["remote_url"], draft["prompt"], draft["model_key"],
             draft["seed"], json.dumps({"final_mode": "keep", "from_draft": draft["id"]}), 0.0, "ready", db.now()),
        )
        db.set_shot_status(conn, shot["id"], next_status)
    return {"asset_id": cur.lastrowid, "version": version, "path": rel(out), "cost_usd": 0.0,
            "final_mode": "keep", "status": next_status}


def launch_lipsync(conn: sqlite3.Connection, shot_id: int, force: bool = False) -> dict:
    shot = db.get_shot(conn, shot_id)
    clip = db.get_clip(conn, shot["clip_slug"])
    final = db.row(conn.execute(
        "SELECT * FROM assets WHERE shot_id=? AND kind='final' AND status IN ('ready','validated') "
        "ORDER BY version DESC LIMIT 1",
        (shot_id,),
    ).fetchone())
    if final is None:
        raise ProductionError("Pas de rendu final pour ce plan")
    voice = clip.get("vocals_path") or clip.get("song_path")
    if not voice:
        raise ProductionError("Ni piste voix ni morceau pour ce clip")
    slice_path = studio() / clip["dir"] / "work" / f"voix-plan-{shot['num']:03d}.mp3"
    media.cut_audio(absp(voice), float(shot["t_start"]), float(shot["t_end"]), slice_path)
    key = routing.lipsync_model_key(routing.shot_seconds(shot))
    mcfg = routing.model(key)
    video_ref = final["remote_url"] or fal.to_data_uri(absp(final["path"]))
    payload = routing.build_payload(mcfg, video_url=video_ref, audio_url=fal.to_data_uri(slice_path), mode="final")
    cost = routing.estimate_cost(mcfg, routing.shot_seconds(shot), "final")
    _check_budget(conn, clip["slug"], cost, force, mcfg)
    sub = providers.submit(mcfg, payload, kind="video", label=f"plan {shot['num']} lipsync",
                     seconds=routing.shot_seconds(shot), force_mock=is_demo(clip["slug"]))
    res = _create_asset(conn, shot, "lipsync", "finals", ".mp4", None, key, final["seed"], payload, cost,
                        mcfg["endpoint"], sub)
    db.set_shot_status(conn, shot_id, "lipsync_gen")
    return res


# --- Fin de génération -------------------------------------------------------

KIND_LABEL = {"image": "image de travail", "image_hd": "image HD", "draft": "brouillon vidéo",
              "final": "rendu final", "lipsync": "lip-sync"}

def on_job_done(conn: sqlite3.Connection, job: dict, result: dict) -> None:
    """Le worker a récupéré le résultat d'un job : on télécharge et on fait avancer le plan."""
    table = job["target_table"]
    if table == "character_assets":
        asset = db.row(conn.execute("SELECT * FROM character_assets WHERE id=?", (job["target_id"],)).fetchone())
        mcfg = routing.model(asset["model_key"])
        url = routing.extract_output(result, mcfg["output"])
        dest = absp(job["output_path"])
        dest = dest.with_suffix(_ext_from_url(url, dest.suffix))
        providers.download(url, dest, job.get("provider") or "fal")
        with db.tx(conn):
            conn.execute("UPDATE character_assets SET status='proposed', path=?, remote_url=? WHERE id=?",
                         (rel(dest), url, asset["id"]))
            conn.execute("UPDATE jobs SET status='done', updated_at=? WHERE id=?", (db.now(), job["id"]))
        return

    asset = db.row(conn.execute("SELECT * FROM assets WHERE id=?", (job["target_id"],)).fetchone())
    mcfg = routing.model(asset["model_key"])
    url = routing.extract_output(result, mcfg["output"])
    dest = absp(job["output_path"])
    dest = dest.with_suffix(_ext_from_url(url, dest.suffix))
    providers.download(url, dest, job.get("provider") or "fal")
    if asset["kind"] in ("draft", "final"):
        # la musique vient de Suno : aucune piste son ne doit rester dans les plans
        from .providers._http import strip_audio
        strip_audio(dest)
    seed = result.get("seed") if isinstance(result, dict) else None
    shot = db.get_shot(conn, asset["shot_id"])
    qc = load_models().get("qc", {})
    next_status = {
        "image": "image_qc" if qc.get("images", True) else "image_review",
        "image_hd": "hd_qc" if qc.get("images_hd", True) else "prompt_todo",
        "draft": "draft_qc" if qc.get("drafts", False) else "draft_review",
        "final": "lipsync_todo" if shot["singing"] else "final_review",
        "lipsync": "final_review",
    }[asset["kind"]]
    with db.tx(conn):
        conn.execute(
            "UPDATE assets SET status='ready', path=?, remote_url=?, seed=COALESCE(seed, ?) WHERE id=?",
            (rel(dest), url, seed, asset["id"]),
        )
        conn.execute("UPDATE jobs SET status='done', updated_at=? WHERE id=?", (db.now(), job["id"]))
        db.set_shot_status(conn, shot["id"], next_status)
        db.log_event(conn, shot["clip_slug"], "asset",
                     f"Plan {shot['num']} : {KIND_LABEL.get(asset['kind'], asset['kind'])} v{asset['version']} prêt")


def on_job_failed(conn: sqlite3.Connection, job: dict, error: str) -> None:
    with db.tx(conn):
        conn.execute("UPDATE jobs SET status='failed', last_error=?, updated_at=? WHERE id=?",
                     (error[:2000], db.now(), job["id"]))
        if job["target_table"] == "character_assets":
            conn.execute("UPDATE character_assets SET status='failed', error=? WHERE id=?",
                         (error[:2000], job["target_id"]))
            return
        conn.execute("UPDATE assets SET status='failed', error=?, cost_usd=0 WHERE id=?",
                     (error[:2000], job["target_id"]))
        asset = db.row(conn.execute("SELECT * FROM assets WHERE id=?", (job["target_id"],)).fetchone())
        shot = db.get_shot(conn, asset["shot_id"])
        conn.execute("UPDATE shots SET status='failed', notes=?, updated_at=? WHERE id=?",
                     (f"Échec {asset['kind']} v{asset['version']} : {error[:400]}", db.now(), shot["id"]))
        db.log_event(conn, shot["clip_slug"], "error", f"Plan {shot['num']} : échec {asset['kind']} — {error[:200]}")


# --- Contrôle qualité (agent) ------------------------------------------------

def qc_result(conn: sqlite3.Connection, shot_id: int, passed: bool, note: str = "") -> str:
    shot = db.get_shot(conn, shot_id)
    if shot["status"] not in ("image_qc", "hd_qc", "draft_qc"):
        raise ProductionError(f"Le plan {shot['num']} n'est pas en contrôle ({shot['status']})")
    kind = {"image_qc": "image", "hd_qc": "image_hd", "draft_qc": "draft"}[shot["status"]]
    retries_cfg = load_models().get("qc", {}).get("max_auto_retries", 2)
    if isinstance(retries_cfg, dict):
        retries_cfg = retries_cfg.get({"image": "images", "image_hd": "images_hd", "draft": "drafts"}[kind], 1)
    max_retries = int(retries_cfg)
    pass_status = {"image": "image_review", "image_hd": "prompt_todo", "draft": "draft_review"}[kind]
    retry_status = {"image": "image_todo", "image_hd": "hd_todo", "draft": "draft_todo"}[kind]
    giveup_status = {"image": "image_review", "image_hd": "hd_review", "draft": "draft_review"}[kind]
    asset = db.latest_asset(conn, shot_id, kind)
    if passed:
        status = pass_status
        conn.execute("UPDATE shots SET qc_retries=0, updated_at=? WHERE id=?", (db.now(), shot_id))
        if kind == "image_hd" and asset:
            conn.execute("UPDATE assets SET status='validated' WHERE id=?", (asset["id"],))
    elif shot["qc_retries"] < max_retries:
        status = retry_status
        conn.execute("UPDATE shots SET qc_retries=qc_retries+1, notes=?, updated_at=? WHERE id=?",
                     (f"Contrôle refusé : {note}", db.now(), shot_id))
        if asset:
            conn.execute("UPDATE assets SET status='rejected', error=? WHERE id=?", (f"QC : {note}", asset["id"]))
    else:
        # trop d'essais : Michael tranche avec la remarque de l'agent
        status = giveup_status
        conn.execute("UPDATE shots SET qc_retries=0, notes=?, updated_at=? WHERE id=?",
                     (f"À vérifier (contrôle auto non concluant) : {note}", db.now(), shot_id))
        if kind == "image_hd" and asset and asset["status"] == "rejected":
            conn.execute("UPDATE assets SET status='ready' WHERE id=?", (asset["id"],))
    db.set_shot_status(conn, shot_id, status)
    db.log_event(conn, shot["clip_slug"], "qc",
                 f"Plan {shot['num']} : contrôle {KIND_LABEL[kind]} {'OK' if passed else 'refusé'} {note}".strip())
    return status


def qc_frames(conn: sqlite3.Connection, shot_id: int) -> list[str]:
    """Extrait des images du dernier draft pour que l'agent puisse le regarder."""
    asset = db.latest_asset(conn, shot_id, "draft")
    if asset is None or not asset["path"]:
        raise ProductionError("Pas de draft à contrôler")
    out = absp(asset["path"]).parent / f".frames-{Path(asset['path']).stem}"
    return [str(p) for p in media.extract_frames(absp(asset["path"]), out, 3)]


# --- Validations de Michael --------------------------------------------------

def review_decoupage(conn: sqlite3.Connection, slug: str, decision: str, comment: str = "") -> None:
    clip = db.get_clip(conn, slug)
    if clip["stage"] != "decoupage_review":
        raise ProductionError("Le découpage n'est pas en attente de validation")
    with db.tx(conn):
        conn.execute(
            "INSERT INTO reviews (clip_slug, gate, decision, comment, handled, created_at) VALUES (?,?,?,?,?,?)",
            (slug, "decoupage", decision, comment, 1 if decision == "approve" else 0, db.now()),
        )
        if decision == "approve":
            set_stage(conn, slug, "production")
            conn.execute("UPDATE shots SET status='image_todo', updated_at=? WHERE clip_slug=?", (db.now(), slug))


def review_shot(conn: sqlite3.Connection, shot_id: int, decision: str, comment: str = "",
                asset_id: int | None = None) -> str:
    """Décision de Michael sur un plan en attente.

    Portes : images (image de travail), hd (écart signalé sur la HD), videoplan
    (prompt + modèle + coût), drafts, finals. Décisions : approve, change, et pour
    la porte hd, use_work_image (garder l'image de travail comme départ de la vidéo).
    """
    shot = db.get_shot(conn, shot_id)
    gate = db.REVIEW_STATUSES.get(shot["status"])
    if gate is None:
        raise ProductionError(f"Le plan {shot['num']} n'attend pas de validation ({shot['status']})")
    if decision not in ("approve", "change", "use_work_image"):
        raise ProductionError("Décision : approve, change ou use_work_image")
    if decision == "use_work_image" and gate != "hd":
        raise ProductionError("use_work_image ne vaut que pour la HD")
    if decision == "change" and not comment.strip():
        raise ProductionError("Explique la modification souhaitée")
    kind = {"images": "image", "hd": "image_hd", "videoplan": None, "drafts": "draft", "finals": None}[gate]
    if asset_id:
        asset = db.row(conn.execute("SELECT * FROM assets WHERE id=? AND shot_id=?", (asset_id, shot_id)).fetchone())
    elif kind:
        asset = db.latest_asset(conn, shot_id, kind)
    elif gate == "finals":
        asset = db.latest_asset(conn, shot_id, "lipsync") if shot["singing"] else None
        asset = asset or db.latest_asset(conn, shot_id, "final")
    else:
        asset = None
    with db.tx(conn):
        conn.execute(
            "INSERT INTO reviews (clip_slug, shot_id, asset_id, gate, decision, comment, handled, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (shot["clip_slug"], shot_id, asset["id"] if asset else None, gate,
             "change" if decision == "change" else "approve", comment, 0 if decision == "change" else 1, db.now()),
        )
        if decision == "use_work_image":
            if asset:
                conn.execute("UPDATE assets SET status='rejected' WHERE id=?", (asset["id"],))
            new_status = "prompt_todo"
        elif decision == "approve":
            if asset:
                conn.execute("UPDATE assets SET status='validated' WHERE id=?", (asset["id"],))
                conn.execute(
                    "UPDATE assets SET status='superseded' WHERE shot_id=? AND kind=? AND id!=? AND status='ready'",
                    (shot_id, asset["kind"], asset["id"]),
                )
            new_status = {"images": "hd_todo", "hd": "prompt_todo", "videoplan": "draft_todo",
                          "drafts": "final_todo", "finals": "done"}[gate]
            if gate == "images":
                # une nouvelle image validée rend caduques les HD précédentes
                conn.execute("UPDATE assets SET status='superseded' WHERE shot_id=? AND kind='image_hd' "
                             "AND status IN ('ready','validated')", (shot_id,))
            if gate == "finals":
                for k in ("final", "lipsync"):
                    other = db.latest_asset(conn, shot_id, k)
                    if other and other["status"] == "ready":
                        conn.execute("UPDATE assets SET status='validated' WHERE id=?", (other["id"],))
        else:
            if asset:
                conn.execute("UPDATE assets SET status='rejected' WHERE id=?", (asset["id"],))
            new_status = "change_requested"
        db.set_shot_status(conn, shot_id, new_status)
        _maybe_finish_clip(conn, shot["clip_slug"])
    return new_status


def approve_all(conn: sqlite3.Connection, slug: str, gate: str, block_id: int | None = None) -> int:
    status = {v: k for k, v in db.REVIEW_STATUSES.items()}.get(gate)
    if not status:
        raise ProductionError(f"Porte inconnue : {gate}")
    q, params = "SELECT id FROM shots WHERE clip_slug=? AND status=?", [slug, status]
    if block_id:
        q += " AND block_id=?"
        params.append(block_id)
    ids = [r["id"] for r in conn.execute(q + " ORDER BY num", params).fetchall()]
    for sid in ids:
        review_shot(conn, sid, "approve")
    return len(ids)


ROUTES = {
    "storyboard": "image_todo",   # l'image ne va pas (compo, décor, tenue, visage)
    "hd": "hd_todo",              # la HD a perdu quelque chose : on refait l'agrandissement
    "prompteur": "prompt_todo",   # mouvement, caméra, action à réécrire
    "routeur": "prompt_todo",     # rendu insuffisant : on monte d'un palier
    "finition": "final_todo",     # refaire le rendu final / lip-sync
    "script": "image_todo",       # le plan lui-même change (description, durée)
}


def handle_review(conn: sqlite3.Connection, review_id: int, route: str, note: str = "") -> dict:
    """L'orchestrateur a trié un retour de Michael : on renvoie le plan à la bonne étape."""
    if route not in ROUTES:
        raise ProductionError(f"Route inconnue : {route} ({', '.join(ROUTES)})")
    rv = db.row(conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone())
    if rv is None or rv["handled"]:
        raise ProductionError("Retour inconnu ou déjà traité")
    with db.tx(conn):
        if rv["gate"] == "decoupage":
            conn.execute("UPDATE reviews SET handled=1, route=?, handled_note=? WHERE id=?", (route, note, review_id))
            return {"review": review_id, "route": route}
        shot = db.get_shot(conn, rv["shot_id"])
        status = ROUTES[route]
        if route == "routeur":
            conn.execute("UPDATE shots SET tier=?, model_key=NULL WHERE id=?",
                         (routing.upgrade_tier(shot.get("tier")), shot["id"]))
        if route in ("storyboard", "script"):
            conn.execute("UPDATE shots SET seed=NULL WHERE id=?", (shot["id"],))
        conn.execute(
            "UPDATE shots SET notes=?, qc_retries=0, updated_at=? WHERE id=?",
            (f"Retour de Michael : {rv['comment']}" + (f" | Tri : {note}" if note else ""), db.now(), shot["id"]),
        )
        db.set_shot_status(conn, shot["id"], status)
        conn.execute("UPDATE reviews SET handled=1, route=?, handled_note=? WHERE id=?", (route, note, review_id))
        db.log_event(conn, shot["clip_slug"], "retour", f"Plan {shot['num']} renvoyé vers {route}")
    return {"review": review_id, "shot": shot["num"], "route": route, "status": status}


def _maybe_finish_clip(conn: sqlite3.Connection, slug: str) -> None:
    left = conn.execute("SELECT COUNT(*) FROM shots WHERE clip_slug=? AND status!='done'", (slug,)).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM shots WHERE clip_slug=?", (slug,)).fetchone()[0]
    if total and not left:
        set_stage(conn, slug, "done")


def retry_failed(conn: sqlite3.Connection, shot_id: int) -> str:
    """Remet un plan en échec à l'étape qui a échoué."""
    shot = db.get_shot(conn, shot_id)
    if shot["status"] != "failed":
        raise ProductionError("Le plan n'est pas en échec")
    last = db.row(conn.execute(
        "SELECT * FROM assets WHERE shot_id=? AND status='failed' ORDER BY id DESC LIMIT 1", (shot_id,)
    ).fetchone())
    status = {"image": "image_todo", "image_hd": "hd_todo", "draft": "draft_todo", "final": "final_todo",
              "lipsync": "lipsync_todo"}.get(last["kind"] if last else "image", "image_todo")
    if status == "draft_todo" and not (shot.get("model_key") and shot.get("video_prompt")):
        status = "prompt_todo"
    db.set_shot_status(conn, shot_id, status)
    return status


# --- Carnet de rodage des modèles -----------------------------------------------

def rodage(conn: sqlite3.Connection, model_key: str | None = None) -> list[dict]:
    """Ce que l'historique dit de chaque modèle vidéo : validé du premier coup ou refait,
    sur quels types de plans, avec les commentaires de Michael. Le routeur le lit."""
    q = ("SELECT a.id, a.model_key, a.version, a.status, a.cost_usd, s.framing, s.motion, s.num, s.clip_slug, "
         "s.description FROM assets a JOIN shots s ON s.id=a.shot_id WHERE a.kind='draft' AND a.status!='generating'")
    params: list = []
    if model_key:
        q += " AND a.model_key=?"
        params.append(model_key)
    stats: dict[str, dict] = {}
    for a in db.rows(conn.execute(q, params).fetchall()):
        m = stats.setdefault(a["model_key"], {"model": a["model_key"], "drafts": 0, "valides": 0, "refaits": 0,
                                              "echecs": 0, "cout_usd": 0.0, "par_mouvement": {}, "retours": []})
        m["drafts"] += 1
        m["cout_usd"] = round(m["cout_usd"] + (a["cost_usd"] or 0), 2)
        mv = m["par_mouvement"].setdefault(a["motion"] or "?", {"valides": 0, "refaits": 0})
        rv = conn.execute("SELECT decision, comment FROM reviews WHERE asset_id=? AND gate='drafts' "
                          "ORDER BY id DESC LIMIT 1", (a["id"],)).fetchone()
        if a["status"] == "failed":
            m["echecs"] += 1
        elif rv and rv["decision"] == "approve" or a["status"] == "validated":
            m["valides"] += 1
            mv["valides"] += 1
        elif rv and rv["decision"] == "change":
            m["refaits"] += 1
            mv["refaits"] += 1
            m["retours"].append(f"{a['clip_slug']} plan {a['num']} ({a['framing'] or '?'}, {a['motion'] or '?'}) : "
                                f"{rv['comment']}")
    out = list(stats.values())
    for m in out:
        jugés = m["valides"] + m["refaits"]
        m["taux_premier_coup"] = round(m["valides"] / jugés, 2) if jugés else None
    return sorted(out, key=lambda m: -m["drafts"])


# --- Vues --------------------------------------------------------------------

def shot_view(conn: sqlite3.Connection, shot: dict) -> dict:
    assets = db.rows(conn.execute(
        "SELECT * FROM assets WHERE shot_id=? ORDER BY kind, version", (shot["id"],)
    ).fetchall())
    s = dict(shot)
    s["assets"] = assets
    s["reviews"] = db.rows(conn.execute(
        "SELECT * FROM reviews WHERE shot_id=? ORDER BY id DESC LIMIT 10", (shot["id"],)
    ).fetchall())
    s["cost_usd"] = round(sum(a["cost_usd"] or 0 for a in assets), 3)
    clip_aspect = conn.execute("SELECT aspect_ratio FROM clips WHERE slug=?", (shot["clip_slug"],)).fetchone()
    shot = {**shot, "aspect_ratio": clip_aspect[0] if clip_aspect else None}
    if shot.get("model_key"):
        try:
            s["estimate"] = routing.route_shot(shot, model_key=shot["model_key"])
        except routing.RoutingError:
            s["estimate"] = None
    if shot["status"] == "video_review":
        s["model_options"] = routing.model_options(shot)
    return s


def clip_snapshot(conn: sqlite3.Connection, slug: str, compact: bool = False) -> dict:
    clip = db.get_clip(conn, slug)
    shots = db.rows(conn.execute("SELECT * FROM shots WHERE clip_slug=? ORDER BY num", (slug,)).fetchall())
    clip["casting"] = db.casting_for_clip(conn, slug)
    clip["cost_usd"] = round(db.clip_cost(conn, slug), 3)
    clip["credits_used_usd"] = round(db.clip_cost(conn, slug, "credits"), 3)
    counts: dict[str, int] = {}
    for s in shots:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    clip["status_counts"] = counts
    clip["pending_reviews"] = db.rows(conn.execute(
        "SELECT * FROM reviews WHERE clip_slug=? AND handled=0 AND decision='change' ORDER BY id", (slug,)
    ).fetchall())
    if compact:
        clip["shots"] = shots
    else:
        clip["shots"] = [shot_view(conn, s) for s in shots]
    script = absp(clip.get("script_path"))
    clip["script"] = script.read_text(encoding="utf-8") if script and script.is_file() else ""
    clip["blocks"] = [{k: v for k, v in b.items() if k != "shots"} | {"shot_ids": [x["id"] for x in b["shots"]]}
                      for b in decoupage(conn, slug)]
    clip["files"] = clip_files(conn, slug)
    clip["needs_agent"] = needs_agent(conn, slug)["reasons"]
    return clip


def needs_agent(conn: sqlite3.Connection, slug: str) -> dict:
    """Ce qui demande un agent Claude sur ce clip (utilisé par le worker)."""
    clip = db.get_clip(conn, slug)
    reasons: list[str] = []
    n_shots = conn.execute("SELECT COUNT(*) FROM shots WHERE clip_slug=?", (slug,)).fetchone()[0]
    if is_demo(slug):
        return {"clip": slug, "reasons": [], "fingerprint": "demo", "retry_on_backoff": False}
    if clip["stage"] == "script" and clip.get("brief_ready"):
        reasons.append("script_doctor: découpage à compléter" if n_shots else "script_doctor: découpage à extraire du dossier")
    pending_dec = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE clip_slug=? AND gate='decoupage' AND handled=0", (slug,)
    ).fetchone()[0]
    if pending_dec:
        reasons.append("script_doctor: retours sur le découpage")
    if clip["stage"] == "production" and n_shots:
        for status in db.AGENT_STATUSES:
            n = conn.execute("SELECT COUNT(*) FROM shots WHERE clip_slug=? AND status=? AND id NOT IN "
                             "(SELECT shot_id FROM spend_requests WHERE shot_id IS NOT NULL "
                             "AND status IN ('pending','approved'))", (slug, status)).fetchone()[0]
            if n:
                reasons.append(f"{status}: {n} plan(s)")
    brief_sig = None
    if clip["stage"] == "script":
        files = conn.execute("SELECT id FROM clip_files WHERE clip_slug=? ORDER BY id", (slug,)).fetchall()
        script = absp(clip.get("script_path"))
        st = script.stat() if script and script.is_file() else None
        brief_sig = [[r[0] for r in files], clip.get("pitch"), clip.get("concept"),
                     [st.st_mtime_ns, st.st_size] if st else None]
    fp = hashlib.sha1(json.dumps([reasons, _shot_fingerprint(conn, slug), brief_sig]).encode()).hexdigest()[:16]
    # À l'étape script, si l'agent n'a pas pu avancer (timecodes manquants), on
    # attend que Michael modifie son dossier au lieu de réessayer régulièrement.
    return {"clip": slug, "reasons": reasons, "fingerprint": fp, "retry_on_backoff": clip["stage"] != "script"}


def update_script(conn: sqlite3.Connection, slug: str, text: str) -> None:
    """Michael complète ou corrige son script (timecodes par plan) avant le découpage."""
    clip = db.get_clip(conn, slug)
    if clip["stage"] != "script":
        raise ProductionError("Le découpage est déjà fait : commente-le plutôt dans la régie")
    if not text.strip():
        raise ProductionError("Le script est vide")
    dest = studio() / clip["dir"] / "script" / "script.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    conn.execute("UPDATE clips SET script_path=?, updated_at=? WHERE slug=?", (rel(dest), db.now(), slug))
    db.log_event(conn, slug, "script", "Script mis à jour par Michael")


def _shot_fingerprint(conn: sqlite3.Connection, slug: str) -> list:
    marks = ",".join("?" * len(db.AGENT_STATUSES))
    return [tuple(r) for r in conn.execute(
        f"SELECT num, status, updated_at FROM shots WHERE clip_slug=? AND status IN ({marks}) ORDER BY num",
        (slug, *db.AGENT_STATUSES),
    ).fetchall()]


def assemble_clip(conn: sqlite3.Connection, slug: str) -> Path:
    """Montage du clip sur le morceau avec la meilleure version disponible de chaque plan."""
    clip = db.get_clip(conn, slug)
    shots = db.rows(conn.execute("SELECT * FROM shots WHERE clip_slug=? ORDER BY num", (slug,)).fetchall())
    segments = []
    for s in shots:
        best = None
        for kind in ("lipsync", "final", "draft", "image_hd", "image"):
            a = conn.execute(
                "SELECT * FROM assets WHERE shot_id=? AND kind=? AND status IN ('validated','ready') "
                "ORDER BY (status='validated') DESC, version DESC LIMIT 1",
                (s["id"], kind),
            ).fetchone()
            if a and absp(a["path"]) and absp(a["path"]).is_file():
                best = absp(a["path"])
                break
        segments.append({"path": best, "seconds": routing.shot_seconds(s)})
    out = studio() / clip["dir"] / "montage" / f"montage-{db.now().replace(':', '').replace('-', '')}.mp4"
    song_offset = float(shots[0]["t_start"]) if shots else 0.0
    media.assemble(segments, absp(clip.get("song_path")), out, clip["aspect_ratio"], song_offset)
    db.log_event(conn, slug, "montage", f"Montage généré : {out.name}")
    return out


def review_digest(conn: sqlite3.Connection, slug: str) -> str | None:
    """Texte de notification quand des plans attendent Michael."""
    clip = db.get_clip(conn, slug)
    parts = []
    if clip["stage"] == "decoupage_review":
        n = conn.execute("SELECT COUNT(*) FROM shots WHERE clip_slug=?", (slug,)).fetchone()[0]
        parts.append(f"découpage en {n} plans")
    labels = {"image_review": "image(s)", "hd_review": "image(s) HD à vérifier",
              "video_review": "plan(s) vidéo (prompt, modèle, coût)", "draft_review": "brouillon(s) vidéo",
              "final_review": "final(s)"}
    for status, label in labels.items():
        n = conn.execute("SELECT COUNT(*) FROM shots WHERE clip_slug=? AND status=?", (slug, status)).fetchone()[0]
        if n:
            parts.append(f"{n} {label}")
    if not parts:
        return None
    link = notify.regie_link(f"#/clip/{slug}")
    return f"🎬 <b>{clip['title']}</b> : à valider — {', '.join(parts)}.\n{link}"
