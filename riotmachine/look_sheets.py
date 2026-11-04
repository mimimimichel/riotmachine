"""Tenues : photos de Michael et feuille de référence générée par la Riot Machine.

1. Michael dépose une ou plusieurs photos de la tenue portée par le personnage.
2. Il lance la feuille de référence (son clic vaut accord ; gratuit, il choisit le nombre).
   La machine part de ses photos et de la canon du personnage, avec un prompt fixe :
   trois vues en pied (face, trois-quarts, dos) et une rangée de détails.
3. Il garde la meilleure proposition. La feuille gardée part en tête des références de la
   tenue, devant ses photos, pour chaque visuel où le personnage la porte.
"""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from . import db
from .production import IMAGE_EXT, absp, rel

# Une feuille = trois vues générées séparément, puis assemblées par la machine.
# Les modèles gratuits ne savent pas composer une planche en une image : vue par vue, ils suivent.
VIEWS = [
    ("face", "FRONT VIEW, the person faces the camera"),
    ("trois-quarts", "THREE-QUARTER VIEW, the body turned 45 degrees to the side, the face still visible"),
    ("dos", "BACK VIEW, the person stands with the back to the camera, the back of the head and the back of "
            "every garment visible"),
]
VIEW_PROMPT = (
    "Character turnaround photo, one single view: {view}.\n"
    "IDENTITY: reference image 1 is the person. Keep exactly the face, facial features, skin tone, hair "
    "(colour, texture, length, volume) and body shape from image 1. Do not change the face.\n"
    "OUTFIT: the other reference images show the outfit, worn. Reproduce every garment exactly: cut, colour, "
    "fabric, fit, length, neckline, buttons, pockets, trousers, shoes, jewellery. The full outfit is worn and "
    "visible in this view, nothing removed, nothing added.\n"
    "FRAMING: vertical full-body shot, the whole person from the top of the head to the soles of the shoes, "
    "centered, with empty background space above the head and below the feet; the person fills about 80 percent "
    "of the image height. Camera at waist height, straight on, 50mm lens, no tilt, no crop, no close-up.\n"
    "POSE: standing straight, feet slightly apart, arms relaxed and slightly away from the body, neutral expression.\n"
    "SET: plain light grey seamless studio background, soft even lighting, no props.\n"
    "STYLE: realistic photograph. One single person in the image. No text, no labels, no collage, no split screen."
)
VIEW_SIZE = (576, 1024)   # vertical ; les Spaces Hugging Face refusent un côté au-delà de 1024



class LookError(Exception):
    pass


def _look(conn: sqlite3.Connection, character_slug: str, look: str) -> dict:
    lk = db.row(conn.execute("SELECT * FROM looks WHERE character_slug=? AND slug=?", (character_slug, look)).fetchone())
    if lk is None:
        raise LookError(f"Tenue inconnue : @{character_slug}-{look}")
    return lk


def sync_photos(conn: sqlite3.Connection, lk: dict) -> None:
    """Les images déposées directement dans le dossier de la tenue comptent comme photos de Michael."""
    ldir = absp(lk["dir"])
    if not ldir or not ldir.is_dir():
        return
    known = {r["path"] for r in conn.execute("SELECT path FROM look_images WHERE look_id=?", (lk["id"],)).fetchall()}
    for p in sorted(ldir.glob("*")):
        if p.suffix.lower() in IMAGE_EXT and rel(p) not in known:
            conn.execute("INSERT INTO look_images (look_id, role, status, path, created_at) VALUES (?,?,?,?,?)",
                         (lk["id"], "photo", "kept", rel(p), db.now()))
    conn.commit()


def images(conn: sqlite3.Connection, lk: dict) -> dict:
    """Photos, feuille gardée et propositions de feuille d'une tenue."""
    sync_photos(conn, lk)
    rows = db.rows(conn.execute("SELECT * FROM look_images WHERE look_id=? AND status!='rejected' ORDER BY id",
                                (lk["id"],)).fetchall())
    photos = [r for r in rows if r["role"] == "photo" and r["status"] == "kept"]
    sheet = next((r for r in reversed(rows) if r["role"] == "sheet" and r["status"] == "kept"), None)
    props = [r for r in rows if r["role"] == "sheet" and r["status"] in ("generating", "proposed", "failed")]
    return {"photos": photos, "sheet": sheet, "sheet_props": props,
            "generating": any(r["status"] == "generating" for r in props)}


def refs(conn: sqlite3.Connection, character_slug: str, look: str) -> list[Path]:
    """Références d'une tenue pour un visuel : la feuille gardée d'abord, puis les photos."""
    lk = conn.execute("SELECT * FROM looks WHERE character_slug=? AND slug=?", (character_slug, look)).fetchone()
    if lk is None:
        return []
    im = images(conn, dict(lk))
    paths = ([im["sheet"]["path"]] if im["sheet"] else []) + [p["path"] for p in im["photos"]]
    return [absp(p) for p in paths if absp(p) and absp(p).is_file()]


def add_photo(conn: sqlite3.Connection, lk: dict, dest: Path) -> int:
    cur = conn.execute("INSERT INTO look_images (look_id, role, status, path, created_at) VALUES (?,?,?,?,?)",
                       (lk["id"], "photo", "kept", rel(dest), db.now()))
    conn.commit()
    return cur.lastrowid


def _person_ref(conn: sqlite3.Connection, character_slug: str) -> Path | None:
    """La tête canon du personnage (version castée la plus récente, sinon la dernière version)."""
    from . import production
    row = conn.execute("SELECT canon_version FROM characters WHERE slug=?", (character_slug,)).fetchone()
    version = row["canon_version"] if row and row["canon_version"] else None
    if version is None:
        v = conn.execute("SELECT MAX(version) v FROM character_versions WHERE character_slug=?",
                         (character_slug,)).fetchone()
        version = v["v"] if v else None
    if version is None:
        return None
    try:
        r = production.character_refs(conn, character_slug, version, limit=1)
    except Exception:  # noqa: BLE001 - personnage sans pack : la feuille part des photos seules
        return None
    return r[0] if r else None


def sheet_prompt(conn: sqlite3.Connection, lk: dict, view: str = VIEWS[0][1]) -> str:
    from . import production
    text = VIEW_PROMPT.format(view=view)
    if lk.get("description"):
        text += f"\nOUTFIT DETAILS: {lk['description']}"
    row = conn.execute("SELECT canon_version FROM characters WHERE slug=?", (lk["character_slug"],)).fetchone()
    if row and row["canon_version"]:
        resume = production.resume_text(conn, lk["character_slug"], row["canon_version"])
        if resume:
            text += f"\nPERSON DETAILS: {resume}"
    return text


def launch_sheet(conn: sqlite3.Connection, character_slug: str, look: str, count: int | None = None,
                 background: bool | None = None, model: str | None = None) -> dict:
    """Propositions de feuille de référence, gratuites. Le clic de Michael vaut accord."""
    from . import elements, production
    lk = _look(conn, character_slug, look)
    im = images(conn, lk)
    if not im["photos"]:
        raise LookError("Dépose d'abord au moins une photo de la tenue portée")
    if im["generating"]:
        raise LookError("Des propositions sont déjà en cours pour cette tenue")
    from . import image_models
    model = model or image_models.default("feuille_tenue")
    if not model:
        raise LookError("Aucun modèle d'image branché (page Fournisseurs)")
    try:
        m = image_models.check(model)
    except image_models.ModelError as exc:
        raise LookError(str(exc)) from exc
    if not m["free"]:
        raise LookError(f"{m['label']} : les feuilles de tenue passent pour l'instant par un modèle gratuit")
    n = max(1, min(3, int(count or 1)))   # chaque feuille coûte trois images du quota gratuit
    person = _person_ref(conn, character_slug)
    photos = [absp(p["path"]) for p in im["photos"]][-3:]
    inputs = ([person] if person else []) + photos
    prompt = "\n\n".join(f"[{name}] " + sheet_prompt(conn, lk, view) for name, view in VIEWS)
    ids = []
    with db.tx(conn):
        conn.execute("UPDATE look_images SET status='rejected' WHERE look_id=? AND role='sheet' "
                     "AND status IN ('proposed','failed')", (lk["id"],))
        for _ in range(n):
            cur = conn.execute("INSERT INTO look_images (look_id, role, status, prompt, model_key, created_at) "
                               "VALUES (?,?,?,?,?,?)", (lk["id"], "sheet", "generating", prompt, model, db.now()))
            ids.append(cur.lastrowid)
        db.log_event(conn, lk["clip_slug"], "casting",
                     f"Tenue @{character_slug}-{look} : {n} feuille(s) de référence lancée(s), {n * len(VIEWS)} image(s)")
    args = (lk["id"], ids, inputs, model)
    bg = production.BACKGROUND if background is None else background
    if bg:
        import threading
        threading.Thread(target=_run_sheets, args=args, daemon=True).start()
    else:
        _run_sheets(*args)
    return {"look": f"{character_slug}-{look}", "images": ids, "count": n, "cost_usd": 0}


def _run_sheets(look_id: int, ids: list[int], inputs: list[Path], model: str = "cloudflare:klein-9b") -> None:
    """Chaque feuille : une image par vue sur le modèle choisi (et lui seul), puis la feuille assemblée."""
    from . import image_models
    conn = db.connect()
    lk = db.row(conn.execute("SELECT * FROM looks WHERE id=?", (look_id,)).fetchone())
    out_dir = absp(lk["dir"]) / "feuilles"
    out_dir.mkdir(parents=True, exist_ok=True)
    nrefs = image_models.get(model)["refs"]
    w, h = VIEW_SIZE
    error = None
    for image_id in ids:
        views = []
        for name, view in VIEWS:
            if error:
                break
            out = out_dir / f"feuille-{image_id}-{name}.png"
            # image 1 = la personne ; puis la vue de face déjà faite (même tenue, même éclairage) ; puis les photos
            refs = (inputs[:1] + views[:1] + inputs[1:])[:min(4, nrefs)]
            try:
                image_models.run_free(model, sheet_prompt(conn, lk, view), refs, out, w, h)
            except image_models.ModelError as exc:
                error = f"Vue {name} : {exc}"
                break
            views.append(out)
        if len(views) == len(VIEWS):
            sheet = out_dir / f"feuille-{image_id}.png"
            try:
                _compose(views, sheet)
                conn.execute("UPDATE look_images SET status='proposed', path=? WHERE id=?", (rel(sheet), image_id))
            except (OSError, subprocess.CalledProcessError) as exc:
                conn.execute("UPDATE look_images SET status='failed', error=? WHERE id=?",
                             (f"Assemblage de la feuille impossible : {exc}"[:700], image_id))
        else:
            conn.execute("UPDATE look_images SET status='failed', error=? WHERE id=?",
                         ((error or "vue manquante")[:700], image_id))
        conn.commit()


def sheet_backends() -> list:
    """Modèles gratuits qui lisent plusieurs images (la canon et la tenue). Kontext n'en lit qu'une : écarté."""
    from . import elements
    return [b for b in elements.draft_backends() if b[1] != "kontext-dev"]


def _compose(views: list[Path], dest: Path) -> None:
    """Les vues côte à côte, même hauteur, fond gris clair : la feuille de référence."""
    n = len(views)
    inputs = sum((["-i", str(v)] for v in views), [])
    scaled = ";".join(f"[{i}]scale=-2:1280,pad=iw+40:1280:20:0:color=0xd9d9d9[v{i}]" for i in range(n))
    stack = "".join(f"[v{i}]" for i in range(n)) + f"hstack=inputs={n}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", f"{scaled};{stack}",
                    "-frames:v", "1", str(dest)], check=True, capture_output=True)


def decide(conn: sqlite3.Connection, image_id: int, decision: str) -> dict:
    """Michael garde une feuille (elle remplace la précédente) ou écarte une image (feuille ou photo)."""
    r = db.row(conn.execute("SELECT * FROM look_images WHERE id=?", (image_id,)).fetchone())
    if r is None:
        raise LookError("Image de tenue inconnue")
    if decision not in ("keep", "reject"):
        raise LookError("Décision : keep ou reject")
    with db.tx(conn):
        if decision == "keep":
            if r["role"] != "sheet" or r["status"] != "proposed":
                raise LookError("Seule une proposition de feuille se garde")
            conn.execute("UPDATE look_images SET status='rejected' WHERE look_id=? AND role='sheet' AND status='kept'",
                         (r["look_id"],))
            conn.execute("UPDATE look_images SET status='kept' WHERE id=?", (image_id,))
        else:
            conn.execute("UPDATE look_images SET status='rejected' WHERE id=?", (image_id,))
            if r["role"] == "photo" and r["path"]:
                # la photo sort du dossier de la tenue : elle ne repart plus comme référence
                src = absp(r["path"])
                if src and src.is_file():
                    trash = src.parent / "retirees"
                    trash.mkdir(exist_ok=True)
                    dest = trash / src.name
                    src.rename(dest)
                    conn.execute("UPDATE look_images SET path=? WHERE id=?", (rel(dest), image_id))
    return {"id": image_id, "decision": decision}


def view(conn: sqlite3.Connection, lk: dict) -> dict:
    """Pour la régie : photos, feuille gardée, propositions (avec leurs ids pour les boutons)."""
    from . import production
    im = images(conn, lk)
    c = production.variants_cfg()
    slim = lambda r: {k: r[k] for k in ("id", "role", "status", "path", "model_key", "error")}  # noqa: E731
    return {"photos": [slim(r) for r in im["photos"]], "sheet": slim(im["sheet"]) if im["sheet"] else None,
            "sheet_props": [slim(r) for r in im["sheet_props"]], "sheet_generating": im["generating"],
            "sheet_count": {"default": 1, "max": 3}, "views": [v[0] for v in VIEWS],
            "person_ref": rel(_person_ref(conn, lk["character_slug"])) if _person_ref(conn, lk["character_slug"]) else None}
