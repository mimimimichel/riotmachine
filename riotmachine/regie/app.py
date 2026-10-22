"""La régie : application web locale où Michael regarde, valide et commente.

Lancement : `riot regie` (port 8420 par défaut). Accès depuis le téléphone via
Tailscale. Si RIOT_REGIE_TOKEN est défini, la première visite doit se faire avec
?token=<valeur> (un cookie prend le relais ensuite).
"""

from __future__ import annotations

import secrets
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import db, production
from ..settings import get_settings

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Riot Machine — régie", docs_url=None, redoc_url=None)


@app.middleware("http")
async def token_guard(request: Request, call_next):
    token = get_settings().regie_token
    if token:
        given = (request.query_params.get("token") or request.cookies.get("riot_token")
                 or request.headers.get("authorization", "").removeprefix("Bearer "))
        if not given or not secrets.compare_digest(given, token):
            return JSONResponse({"detail": "Accès refusé : ouvre la régie avec ?token=…"}, status_code=401)
        if request.query_params.get("token"):
            resp = RedirectResponse(url=str(request.url.remove_query_params("token")))
            resp.set_cookie("riot_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365)
            return resp
    return await call_next(request)


def _conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


def _error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- lecture -------------------------------------------------------------------------

@app.get("/api/overview")
def overview() -> dict[str, Any]:
    conn = _conn()
    clips = db.rows(conn.execute("SELECT * FROM clips ORDER BY updated_at DESC").fetchall())
    for c in clips:
        c["cost_usd"] = round(db.clip_cost(conn, c["slug"]), 2)
        counts = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) n FROM shots WHERE clip_slug=? GROUP BY status", (c["slug"],))}
        c["status_counts"] = counts
        c["shots"] = sum(counts.values())
        c["to_review"] = sum(counts.get(s, 0) for s in db.REVIEW_STATUSES) + (
            1 if c["stage"] == "decoupage_review" else 0)
    characters = db.rows(conn.execute("SELECT * FROM characters ORDER BY slug").fetchall())
    for ch in characters:
        canon = conn.execute(
            "SELECT ca.path FROM character_assets ca JOIN character_versions cv ON cv.id=ca.version_id "
            "WHERE cv.character_slug=? AND cv.version=? AND ca.kind='canon' AND ca.status='kept' "
            "ORDER BY ca.id DESC LIMIT 1", (ch["slug"], ch["canon_version"] or 0)).fetchone()
        ch["canon_path"] = canon["path"] if canon else None
        ch["to_review"] = conn.execute(
            "SELECT COUNT(*) FROM character_assets ca JOIN character_versions cv ON cv.id=ca.version_id "
            "WHERE cv.character_slug=? AND ca.status='proposed'", (ch["slug"],)).fetchone()[0]
    jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
    s = get_settings()
    return {"clips": clips, "characters": characters, "jobs_running": jobs,
            "fal_mode": "simulation" if s.fal_mock else "réel"}


@app.get("/api/clips/{slug}")
def clip(slug: str) -> dict[str, Any]:
    conn = _conn()
    try:
        snap = production.clip_snapshot(conn, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    notes = production.absp(f"{snap['dir']}/script/notes.md")
    snap["script_notes"] = notes.read_text(encoding="utf-8") if notes and notes.is_file() else ""
    montage_dir = production.absp(f"{snap['dir']}/montage")
    montages = sorted(montage_dir.glob("montage-*.mp4")) if montage_dir and montage_dir.is_dir() else []
    snap["montages"] = [production.rel(p) for p in montages[-5:]][::-1]
    snap["events"] = db.rows(conn.execute(
        "SELECT * FROM events WHERE clip_slug=? ORDER BY id DESC LIMIT 15", (slug,)).fetchall())
    return snap


@app.get("/api/characters/{slug}")
def character(slug: str) -> dict[str, Any]:
    try:
        return production.character_snapshot(_conn(), slug)
    except production.ProductionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --- décisions de Michael ---------------------------------------------------------------

class Decision(BaseModel):
    decision: str
    comment: str = ""
    asset_id: int | None = None


@app.post("/api/clips/{slug}/decoupage")
def decide_decoupage(slug: str, body: Decision) -> dict[str, Any]:
    try:
        production.review_decoupage(_conn(), slug, body.decision, body.comment)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/shots/{shot_id}/review")
def decide_shot(shot_id: int, body: Decision) -> dict[str, Any]:
    try:
        status = production.review_shot(_conn(), shot_id, body.decision, body.comment, body.asset_id)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True, "status": status}


@app.post("/api/clips/{slug}/approve-all/{gate}")
def decide_all(slug: str, gate: str) -> dict[str, Any]:
    try:
        n = production.approve_all(_conn(), slug, gate)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True, "approved": n}


class ScriptText(BaseModel):
    text: str


@app.post("/api/clips/{slug}/script")
def save_script(slug: str, body: ScriptText) -> dict[str, Any]:
    try:
        production.update_script(_conn(), slug, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


class Budget(BaseModel):
    budget_usd: float


@app.post("/api/clips/{slug}/budget")
def set_budget(slug: str, body: Budget) -> dict[str, Any]:
    conn = _conn()
    conn.execute("UPDATE clips SET budget_usd=?, updated_at=? WHERE slug=?", (body.budget_usd, db.now(), slug))
    return {"ok": True}


@app.post("/api/shots/{shot_id}/retry")
def retry(shot_id: int) -> dict[str, Any]:
    try:
        return {"ok": True, "status": production.retry_failed(_conn(), shot_id)}
    except production.ProductionError as exc:
        raise _error(exc)


_assembling: set[str] = set()


@app.post("/api/clips/{slug}/assemble")
def assemble(slug: str) -> dict[str, Any]:
    if slug in _assembling:
        return {"ok": True, "running": True}
    _assembling.add(slug)

    def work() -> None:
        try:
            production.assemble_clip(_conn(), slug)
        except Exception as exc:  # visible dans le journal du clip
            db.log_event(_conn(), slug, "error", f"Montage impossible : {exc}")
        finally:
            _assembling.discard(slug)

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "running": True}


@app.post("/api/clips")
async def new_clip(
    title: str = Form(...),
    script: str = Form(""),
    characters: str = Form("jj"),
    aspect: str = Form("16:9"),
    budget: float | None = Form(None),
    bpm: float | None = Form(None),
    song: UploadFile = File(...),
    vocals: UploadFile | None = File(None),
) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="riot-upload-"))
    try:
        song_path = tmp / Path(song.filename or "morceau.mp3").name
        with song_path.open("wb") as fh:
            shutil.copyfileobj(song.file, fh)
        vocals_path = None
        if vocals is not None and vocals.filename:
            vocals_path = tmp / f"voix-{Path(vocals.filename).name}"
            with vocals_path.open("wb") as fh:
                shutil.copyfileobj(vocals.file, fh)
        chars = [c.strip() for c in characters.split(",") if c.strip()]
        clip = production.create_clip(
            _conn(), title, song=song_path, vocals=vocals_path, script_text=script or None,
            bpm=bpm, aspect=aspect, budget_usd=budget, characters=chars,
        )
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": True, "slug": clip["slug"]}


class AssetPick(BaseModel):
    decision: str


@app.post("/api/character-assets/{asset_id}")
def pick_character_asset(asset_id: int, body: AssetPick) -> dict[str, Any]:
    try:
        production.review_character_asset(_conn(), asset_id, body.decision)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/characters/{slug}/versions/{version}/validate")
def validate_version(slug: str, version: int) -> dict[str, Any]:
    try:
        production.validate_character_version(_conn(), slug, version)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


# --- fichiers -------------------------------------------------------------------------------

class StudioFiles(StaticFiles):
    """Sert studio/ (images, vidéos avec lecture partielle pour le défilement)."""

    def __init__(self) -> None:
        root = get_settings().studio_root
        root.mkdir(parents=True, exist_ok=True)
        super().__init__(directory=root, check_dir=True)

    async def get_response(self, path: str, scope):
        if path.endswith((".db", ".db-wal", ".db-shm")) or path.startswith("logs/"):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


app.mount("/media", StudioFiles(), name="media")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
