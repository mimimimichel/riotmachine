"""La régie : application web locale où Michael regarde, valide et commente.

Lancement : `riot regie` (port 8420 par défaut). Accès depuis le téléphone via
Tailscale. Si RIOT_REGIE_TOKEN est défini, la première visite doit se faire avec
?token=<valeur> (un cookie prend le relais ensuite).
"""

from __future__ import annotations

import json
import secrets
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import db, media, production, providers, routing
from ..settings import get_settings

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Riot Machine — régie", docs_url=None, redoc_url=None)


@app.middleware("http")
async def token_guard(request: Request, call_next):
    token = get_settings().regie_token
    public = request.url.path in ("/manifest.webmanifest", "/sw.js") or request.url.path.startswith("/static/icons/")
    if token and not public:
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
        ch["hd_to_review"] = conn.execute(
            "SELECT COUNT(*) FROM character_assets ca JOIN character_versions cv ON cv.id=ca.version_id "
            "WHERE cv.character_slug=? AND ca.kind='canon' AND ca.parent_id IS NOT NULL AND ca.status='proposed'",
            (ch["slug"],)).fetchone()[0]
    for c in clips:
        poster = conn.execute(
            "SELECT a.path FROM assets a JOIN shots s ON s.id=a.shot_id WHERE s.clip_slug=? "
            "AND a.kind IN ('image_hd','image') AND a.status IN ('validated','ready') AND a.path IS NOT NULL "
            "ORDER BY (a.status='validated') DESC, s.num LIMIT 1", (c["slug"],)).fetchone()
        c["poster"] = poster["path"] if poster else None
        c["to_review"] += 0
    jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
    agents = conn.execute("SELECT clip_slug FROM agent_runs WHERE ended_at IS NULL").fetchall()
    return {"clips": clips, "characters": characters, "jobs_running": jobs,
            "agents_running": [r["clip_slug"] for r in agents],
            "providers": routing.providers(), "spend": _spend_summary(conn), "todo": _todo(conn, clips, characters)}


def _todo(conn, clips: list[dict], characters: list[dict]) -> list[dict[str, Any]]:
    """Ce qui attend une validation, tous clips confondus, du plus urgent au moins urgent."""
    out: list[dict[str, Any]] = []
    sp = _spend_summary(conn)
    if sp["pending"]:
        out.append({"label": f"{sp['pending']} dépense{'s' if sp['pending'] > 1 else ''} en attente de validation "
                             f"(~{sp['usd']:.2f} $)", "href": "#/depenses"})
    gate_label = {"image_review": "visuel", "hd_review": "visuel HD", "video_review": "plan vidéo",
                  "draft_review": "vidéo draft", "final_review": "final"}
    for c in clips:
        base = f"#/clip/{c['slug']}"
        if c["stage"] == "decoupage_review":
            out.append({"label": f"{c['title']} : découpage en attente de validation", "href": base + "/decoupage"})
        if c.get("scenario_status") == "proposed":
            out.append({"label": f"{c['title']} : propositions du scénariste à relire", "href": base + "/dossier"})
        for st, lab in gate_label.items():
            n = c["status_counts"].get(st, 0)
            if n:
                out.append({"label": f"{c['title']} : {n} {lab}{'s' if n > 1 else ''} en attente de validation",
                            "href": base + "/plans"})
        n_prop = conn.execute("SELECT COUNT(*) FROM element_images i JOIN elements e ON e.id=i.element_id "
                              "WHERE e.clip_slug=? AND i.status='proposed'", (c["slug"],)).fetchone()[0]
        if n_prop:
            out.append({"label": f"{c['title']} : {n_prop} image{'s' if n_prop > 1 else ''} de décor à garder ou écarter",
                        "href": base + "/decors"})
    for ch in characters:
        if ch.get("to_review"):
            out.append({"label": f"{ch['name']} : {ch['to_review']} image{'s' if ch['to_review'] > 1 else ''} "
                                 "en attente de validation", "href": f"#/personnages/{ch['slug']}"})
    return out


def _spend_summary(conn) -> dict[str, Any]:
    r = conn.execute("SELECT COUNT(*), COALESCE(SUM(est_usd),0) FROM spend_requests WHERE status='pending'").fetchone()
    return {"pending": r[0], "usd": round(r[1], 2)}


@app.get("/api/spend")
def spend_list() -> dict[str, Any]:
    """Dépenses en attente de l'accord de Michael, et les dernières décidées."""
    from .. import credits
    conn = _conn()
    recent = conn.execute("SELECT * FROM spend_requests WHERE status!='pending' ORDER BY id DESC LIMIT 30").fetchall()
    return {"pending": production.spend_requests(conn, "pending"), "recent": [dict(r) for r in recent],
            "credits": credits.status(conn), "summary": _spend_summary(conn)}


class SpendDecision(BaseModel):
    ids: list[int]
    decision: str
    note: str = ""


@app.post("/api/spend/decide")
def spend_decide(body: SpendDecision) -> dict[str, Any]:
    try:
        n = production.decide_spend(_conn(), body.ids, body.decision, body.note)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True, "decided": n}


@app.get("/api/providers")
def providers() -> dict[str, Any]:
    """Page Fournisseurs : état, crédits, offres comparées sur un plan type de 6 s, carnet de rodage."""
    from .. import credits
    conn = _conn()
    sample = {"t_start": 0, "t_end": 6, "motion": "medium", "framing": "MS", "characters": []}
    models = []
    for m in routing.video_models():
        est = routing.route_shot(sample, model_key=m["key"])
        cfg = routing.model(m["key"])
        models.append({**m, "per_second_usd": round(est["cost_total_usd"] / 6, 3), "final_mode": cfg.get("final_mode"),
                       "duration_range": f"{min(cfg.get('durations', [5]))}-{max(cfg.get('durations', [5]))} s"})
    models.sort(key=lambda m: m["per_second_usd"])
    return {"providers": routing.providers(), "credits": credits.status(conn), "video_models": models,
            "rodage": production.rodage(conn), "lipsync": routing.models_cfg().get("lipsync"),
            "image_upscale": routing.models_cfg()["image"].get("upscale")}


class ProviderKey(BaseModel):
    name: str
    value: str


@app.post("/api/providers/{key}/key")
def provider_set_key(key: str, body: ProviderKey) -> dict[str, Any]:
    """Ajoute ou change une clé d'API. Elle est écrite dans .env, jamais renvoyée."""
    from .. import provider_keys
    try:
        provider_keys.set_key(key, body.name, body.value)
    except provider_keys.KeyError_ as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "masked": provider_keys.masked(body.name)}


@app.delete("/api/providers/{key}/key/{name}")
def provider_remove_key(key: str, name: str) -> dict[str, Any]:
    from .. import provider_keys
    try:
        provider_keys.remove_key(key, name)
    except provider_keys.KeyError_ as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


class ProviderEnabled(BaseModel):
    enabled: bool


@app.post("/api/providers/{key}/enabled")
def provider_enable(key: str, body: ProviderEnabled) -> dict[str, Any]:
    from .. import provider_keys
    try:
        provider_keys.set_enabled(key, body.enabled)
    except provider_keys.KeyError_ as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


DOCS = Path(__file__).resolve().parents[2] / "docs"


@app.get("/api/crew")
def crew() -> dict[str, Any]:
    """L'équipe (config/crew.yaml + consignes de chaque agent) et la bibliothèque (docs/savoir/)."""
    import yaml
    from ..settings import REPO_ROOT
    cfg = yaml.safe_load((REPO_ROOT / "config" / "crew.yaml").read_text(encoding="utf-8")) or {}
    out = []
    for a in cfg.get("crew", []):
        meta = {}
        f = REPO_ROOT / ".claude" / "agents" / f"{a.get('fichier')}.md" if a.get("fichier") else None
        if f and f.is_file():
            head = f.read_text(encoding="utf-8").split("---")[1]
            meta = yaml.safe_load(head) or {}
        out.append({**a, "modele": meta.get("model", "celui de la session"), "outils": meta.get("tools", ""),
                    "consignes": f".claude/agents/{a['fichier']}.md" if a.get("fichier") else "CLAUDE.md"})
    lib = []
    for p in sorted((DOCS / "savoir").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("# ")), p.stem)
        intro = next((l.strip() for l in text.splitlines()[1:] if l.strip() and not l.startswith("#")), "")
        lib.append({"name": p.name, "title": title, "intro": intro[:240],
                    "readers": [a["titre"] for a in cfg.get("crew", []) if p.name in (a.get("lit") or [])]})
    return {"crew": out, "library": lib, "departements": cfg.get("departements", [])}


@app.get("/api/savoir/{name}")
def savoir(name: str) -> dict[str, Any]:
    p = (DOCS / "savoir" / name).resolve()
    if p.parent != (DOCS / "savoir").resolve() or not p.is_file():
        raise HTTPException(404, "Document inconnu")
    return {"name": name, "text": p.read_text(encoding="utf-8")}


@app.get("/api/clips/{slug}/waveform")
def waveform(slug: str) -> dict[str, Any]:
    conn = _conn()
    try:
        clip = db.get_clip(conn, slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    song = production.absp(clip.get("song_path"))
    if not song or not song.is_file():
        return {"peaks": [], "duration": None}
    cache = song.with_name(song.stem + ".peaks.json")
    if cache.is_file() and cache.stat().st_mtime >= song.stat().st_mtime:
        return json.loads(cache.read_text())
    try:
        data = {"peaks": media.waveform(song), "duration": clip.get("duration_s") or media.duration(song)}
    except media.MediaError:
        return {"peaks": [], "duration": clip.get("duration_s")}
    cache.write_text(json.dumps(data))
    return data


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
        "SELECT * FROM events WHERE clip_slug=? ORDER BY id DESC LIMIT 30", (slug,)).fetchall())
    snap["agent_running"] = bool(conn.execute(
        "SELECT 1 FROM agent_runs WHERE clip_slug=? AND ended_at IS NULL", (slug,)).fetchone())
    snap["providers"] = routing.providers()
    ana = production.absp(f"{snap['dir']}/work/analyse.json")
    try:
        lines = json.loads(ana.read_text(encoding="utf-8")).get("lines", []) if ana and ana.is_file() else []
    except (OSError, ValueError):
        lines = []
    snap["lyrics_lines"] = [{"start": l["start"], "end": l["end"], "text": l["text"]} for l in lines]
    snap["characters_available"] = db.rows(conn.execute(
        "SELECT slug, name, canon_version FROM characters WHERE canon_version IS NOT NULL ORDER BY slug").fetchall())
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
def decide_all(slug: str, gate: str, block: int | None = None) -> dict[str, Any]:
    try:
        n = production.approve_all(_conn(), slug, gate, block)
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


def _save_uploads(tmp: Path, files: list[UploadFile] | None, prefix: str = "") -> list[Path]:
    out = []
    for f in files or []:
        if f is None or not f.filename:
            continue
        dest = tmp / f"{prefix}{len(out)}-{Path(f.filename).name}"
        with dest.open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        # on garde le nom d'origine pour le rangement
        named = tmp / prefix / Path(f.filename).name
        named.parent.mkdir(parents=True, exist_ok=True)
        dest.rename(named)
        out.append(named)
    return out


@app.post("/api/clips")
async def new_clip(
    title: str = Form(...),
    pitch: str = Form(""),
    concept: str = Form(""),
    lyrics_text: str = Form(""),
    characters: str = Form(""),
    aspect: str = Form("16:9"),
    budget: float | None = Form(None),
    song: UploadFile = File(...),
    vocals: UploadFile | None = File(None),
    dossier: list[UploadFile] | None = File(None),
    lyrics: list[UploadFile] | None = File(None),
) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="riot-upload-"))
    try:
        song_path = _save_uploads(tmp, [song], "song")[0]
        vocals_paths = _save_uploads(tmp, [vocals] if vocals else [], "vocals")
        chars = [c.strip() for c in characters.split(",") if c.strip()]
        clip = production.create_clip(
            _conn(), title, song=song_path, vocals=vocals_paths[0] if vocals_paths else None,
            aspect=aspect, budget_usd=budget, characters=chars, pitch=pitch or None, concept=concept or None,
            lyrics_text=lyrics_text or None, dossier=_save_uploads(tmp, dossier, "dossier"),
            lyrics_files=_save_uploads(tmp, lyrics, "lyrics"),
        )
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": True, "slug": clip["slug"]}


@app.post("/api/clips/{slug}/files")
async def add_files(slug: str, kind: str = Form(...), files: list[UploadFile] = File(...)) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="riot-upload-"))
    try:
        conn = _conn()
        added = [production.add_clip_file(conn, slug, kind, p) for p in _save_uploads(tmp, files, "f")]
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": True, "files": added}


class SourceText(BaseModel):
    label: str = ""
    text: str


@app.post("/api/clips/{slug}/sources")
def add_source(slug: str, body: SourceText) -> dict[str, Any]:
    """Conversation, transcription ou notes collées pour le script doctor (aucune limite de taille)."""
    try:
        f = production.add_source_text(_conn(), slug, body.label, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True, "file": f}


class VisualHd(BaseModel):
    on: bool


@app.post("/api/clips/{slug}/visual-hd")
def visual_hd(slug: str, body: VisualHd) -> dict[str, Any]:
    try:
        production.set_visual_hd(_conn(), slug, body.on)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/da")
def save_da(slug: str, body: ScriptText) -> dict[str, Any]:
    try:
        production.set_da(_conn(), slug, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/da/apply")
def apply_da(slug: str) -> dict[str, Any]:
    try:
        return {"ok": True, "where": production.apply_da(_conn(), slug)}
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)


class MemoireText(BaseModel):
    text: str


@app.post("/api/clips/{slug}/memoire")
def edit_memoire(slug: str, body: MemoireText) -> dict[str, Any]:
    try:
        production.save_memoire(_conn(), slug, body.text, by="michael")
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/memoire/request")
def ask_memoire(slug: str) -> dict[str, Any]:
    try:
        production.request_memoire(_conn(), slug)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.delete("/api/files/{file_id}")
def remove_file(file_id: int) -> dict[str, Any]:
    try:
        production.remove_clip_file(_conn(), file_id)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


class Brief(BaseModel):
    title: str | None = None
    pitch: str | None = None
    concept: str | None = None
    aspect: str | None = None
    budget_usd: float | None = None


@app.post("/api/clips/{slug}/brief")
def save_brief(slug: str, body: Brief) -> dict[str, Any]:
    try:
        production.update_brief(_conn(), slug, title=body.title, pitch=body.pitch, concept=body.concept,
                                 aspect=body.aspect, budget_usd=body.budget_usd)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/lyrics")
def save_lyrics(slug: str, body: ScriptText) -> dict[str, Any]:
    try:
        production.save_lyrics_text(_conn(), slug, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


class DecoupageEdit(BaseModel):
    blocks: list[dict[str, Any]]


@app.post("/api/clips/{slug}/decoupage-edit")
def edit_decoupage(slug: str, body: DecoupageEdit) -> dict[str, Any]:
    try:
        n = production.import_shots(_conn(), slug, {"blocks": body.blocks}, by="michael")
    except (production.ProductionError, LookupError, ValueError, TypeError) as exc:
        raise _error(exc)
    return {"ok": True, "shots": n}


@app.post("/api/blocks/{block_id}/validate")
def block_validate(block_id: int) -> dict[str, Any]:
    try:
        return production.validate_block(_conn(), block_id)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)


class CutOk(BaseModel):
    ok: bool = True


@app.post("/api/shots/{shot_id}/cut-ok")
def shot_cut_ok(shot_id: int, body: CutOk) -> dict[str, Any]:
    try:
        production.set_cut_ok(_conn(), shot_id, body.ok)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/shots/{shot_id}/refs-ok")
def shot_refs_ok(shot_id: int, body: CutOk) -> dict[str, Any]:
    """Michael confirme qu'un plan n'a pas besoin de référence @ : plus aucun signalement."""
    conn = _conn()
    db.get_shot(conn, shot_id)
    conn.execute("UPDATE shots SET refs_ok=? WHERE id=?", (1 if body.ok else 0, shot_id))
    return {"ok": True}


class ShotChange(BaseModel):
    comment: str


@app.post("/api/shots/{shot_id}/cut-change")
def shot_cut_change(shot_id: int, body: ShotChange) -> dict[str, Any]:
    try:
        production.request_shot_change(_conn(), shot_id, body.comment)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/submit-brief")
def submit_brief(slug: str) -> dict[str, Any]:
    try:
        production.submit_brief(_conn(), slug)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


class ModelChoice(BaseModel):
    model_key: str


@app.post("/api/shots/{shot_id}/model")
def choose_model(shot_id: int, body: ModelChoice) -> dict[str, Any]:
    try:
        est = production.choose_model(_conn(), shot_id, body.model_key)
    except (production.ProductionError, LookupError, routing.RoutingError) as exc:
        raise _error(exc)
    return {"ok": True, "estimate": est}


@app.post("/api/shots/{shot_id}/detail")
def shot_detail(shot_id: int, body: ScriptText) -> dict[str, Any]:
    try:
        production.set_detail(_conn(), shot_id, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


class BlockLook(BaseModel):
    text: str


@app.post("/api/clips/{slug}/blocks/{num}/look")
def block_look(slug: str, num: int, body: BlockLook) -> dict[str, Any]:
    try:
        production.set_block_look(_conn(), slug, num, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/complete")
def complete_decoupage(slug: str) -> dict[str, Any]:
    """Michael demande au script doctor de compléter les plans incomplets."""
    try:
        production.request_completion(_conn(), slug)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


# --- scénariste ------------------------------------------------------------------------

@app.post("/api/clips/{slug}/brainstorm")
def brainstorm(slug: str, body: ScriptText) -> dict[str, Any]:
    from .. import scenario
    try:
        path = scenario.submit_brainstorm(_conn(), slug, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True, "path": path}


@app.get("/api/clips/{slug}/scenario")
def scenario_get(slug: str) -> dict[str, Any]:
    from .. import scenario
    try:
        return scenario.state(_conn(), slug)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class ScenarioPick(BaseModel):
    key: str
    decision: str          # accept | reject
    text: str | None = None


@app.post("/api/clips/{slug}/scenario")
def scenario_pick(slug: str, body: ScenarioPick) -> dict[str, Any]:
    from .. import scenario
    try:
        return scenario.decide(_conn(), slug, body.key, body.decision, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)


class LipsyncChoice(BaseModel):
    model_key: str | None = None


@app.post("/api/shots/{shot_id}/lipsync")
def choose_lipsync(shot_id: int, body: LipsyncChoice) -> dict[str, Any]:
    try:
        production.choose_lipsync(_conn(), shot_id, body.model_key)
    except (production.ProductionError, LookupError, routing.RoutingError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/shots/{shot_id}/video-prompt")
def video_prompt(shot_id: int, body: ScriptText) -> dict[str, Any]:
    try:
        production.edit_video_prompt(_conn(), shot_id, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


# --- personnages ----------------------------------------------------------------------

class NewCharacter(BaseModel):
    name: str


@app.post("/api/characters")
def create_character(body: NewCharacter) -> dict[str, Any]:
    try:
        ch = production.new_character(_conn(), body.name)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True, "slug": ch["slug"]}


@app.post("/api/characters/{slug}/versions")
def new_version(slug: str) -> dict[str, Any]:
    try:
        v = production.new_character_version(_conn(), slug)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True, "version": v["version"]}


@app.post("/api/characters/{slug}/versions/{version}/canon-draft")
async def canon_draft(slug: str, version: int, file: UploadFile = File(...)) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="riot-upload-"))
    try:
        path = _save_uploads(tmp, [file], "canon")[0]
        production.upload_canon_draft(_conn(), slug, version, path)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": True}


@app.post("/api/characters/{slug}/versions/{version}/pack-images")
async def pack_upload(slug: str, version: int, kind: str = Form(...),
                      files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Michael dépose ses propres images dans le pack de référence (gardées telles quelles)."""
    tmp = Path(tempfile.mkdtemp(prefix="riot-upload-"))
    try:
        added = production.add_pack_images(_conn(), slug, version, kind, _save_uploads(tmp, files, "pack"))
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": True, "added": len(added)}


@app.post("/api/characters/{slug}/versions/{version}/canon-hd")
def canon_hd_now(slug: str, version: int) -> dict[str, Any]:
    try:
        return production.canon_hd_from_canon(_conn(), slug, version)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    except Exception as exc:   # fournisseur non branché, refus du fournisseur
        raise HTTPException(400, str(exc))


class CanonRole(BaseModel):
    role: str = "canon"


@app.post("/api/characters/{slug}/versions/{version}/canon-request")
def canon_request(slug: str, version: int, body: ScriptText) -> dict[str, Any]:
    try:
        production.request_canon(_conn(), slug, version, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/character-assets/{asset_id}/make-canon")
def asset_make_canon(asset_id: int, body: CanonRole | None = None) -> dict[str, Any]:
    try:
        production.make_canon(_conn(), asset_id, (body.role if body else "canon"))
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


class AssetKind(BaseModel):
    kind: str


@app.post("/api/character-assets/{asset_id}/kind")
def asset_kind(asset_id: int, body: AssetKind) -> dict[str, Any]:
    try:
        production.set_asset_kind(_conn(), asset_id, body.kind)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


class DraftTo(BaseModel):
    asset_id: int
    kind: str


@app.post("/api/characters/{slug}/versions/{version}/draft-to")
def draft_to(slug: str, version: int, body: DraftTo) -> dict[str, Any]:
    try:
        return production.draft_to_pack(_conn(), slug, version, body.asset_id, body.kind)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)


class ShotCharacter(BaseModel):
    slug: str
    remove: bool = False


@app.post("/api/shots/{shot_id}/characters")
def shot_character(shot_id: int, body: ShotCharacter) -> dict[str, Any]:
    """Un personnage du studio joue dans le plan (casté dans le clip si besoin), ou en sort."""
    from .. import elements
    conn = _conn()
    try:
        with db.tx(conn):
            if body.remove:
                elements.remove_character(conn, shot_id, body.slug)
            else:
                elements.add_character(conn, shot_id, body.slug)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


# --- Décors, objets et figurants ---------------------------------------------------
class ElementIn(BaseModel):
    kind: str = "decor"
    name: str = ""
    description: str | None = None
    states: list[str] | None = None


class ElementBrief(BaseModel):
    text: str = ""


@app.post("/api/elements/{element_id}/brief")
def element_brief(element_id: int, body: ElementBrief) -> dict[str, Any]:
    from .. import elements
    try:
        return elements.set_brief(_conn(), element_id, body.text)
    except production.ProductionError as exc:
        raise _error(exc)


class ElementDrafts(BaseModel):
    brief: str = ""
    n: int = 2
    backend: str = ""   # vide : le meilleur modèle gratuit disponible


@app.post("/api/elements/{element_id}/drafts")
def element_drafts(element_id: int, body: ElementDrafts) -> dict[str, Any]:
    """Brouillons gratuits (Cloudflare) d'après les images d'inspiration et le texte de Michael."""
    from .. import elements
    try:
        return elements.launch_drafts(_conn(), element_id, body.brief, body.n, backend=body.backend or None)
    except production.ProductionError as exc:
        raise _error(exc)


class ElementGen(BaseModel):
    state: str | None = None
    notes: str = ""
    prompt: str | None = None   # prompt de l'image HD tel que Michael le voit (enregistré avant le lancement)


class ElementPrompt(BaseModel):
    text: str = ""


class ShotElementIn(BaseModel):
    element_id: int
    state: str | None = None
    remove: bool = False


@app.get("/api/clips/{slug}/elements")
def clip_elements(slug: str) -> dict[str, Any]:
    from .. import elements
    conn = _conn()
    clip = db.get_clip(conn, slug)
    spend = [r for r in production.spend_requests(conn, "pending") if r["action"] == "element_image"
             and r["clip_slug"] == slug]
    shots = [{"id": r["id"], "num": r["num"], "description": r["description"]} for r in
             conn.execute("SELECT id, num, description FROM shots WHERE clip_slug=? ORDER BY num", (slug,))]
    key, mcfg, cost = elements.hd_model()
    return {"elements": elements.clip_elements(conn, slug), "decors_status": clip.get("decors_status"),
            "spend": spend, "shots": shots, "hd_cost": round(cost, 3), "hd_model": mcfg.get("label", key),
            "hd_usable": routing.provider_usable(mcfg.get("provider", "fal")) and mcfg.get("provider") != "vertex",
            "hd_provider": (routing.models_cfg().get("providers") or {}).get(mcfg.get("provider", "fal"), {}).get("label"),
            "looks": production.clip_looks(conn, slug),
            "other_looks": [lk for lk in production.studio_looks(conn)
                            if lk["slug"] not in {x["slug"] for x in production.clip_looks(conn, slug)}],
            "characters": [{"slug": c["slug"], "name": c["name"]} for c in production.studio_characters(conn)],
            "cast": [{"slug": c["character_slug"], "name": c["name"]} for c in db.casting_for_clip(conn, slug)],
            "drafts_usable": bool(elements.draft_backends()),
            "draft_models": [{"key": f"{b[0]}:{b[1]}", "label": b[2]} for b in elements.draft_backends()]}


@app.post("/api/clips/{slug}/elements")
def new_element(slug: str, body: ElementIn) -> dict[str, Any]:
    from .. import elements
    try:
        return elements.create(_conn(), slug, body.kind, body.name, body.description or "", body.states)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)


@app.post("/api/elements/{element_id}")
def edit_element(element_id: int, body: ElementIn) -> dict[str, Any]:
    from .. import elements
    try:
        return elements.update(_conn(), element_id, name=body.name or None, description=body.description,
                               states=body.states)
    except production.ProductionError as exc:
        raise _error(exc)


@app.post("/api/elements/{element_id}/describe")
def describe_element(element_id: int) -> dict[str, Any]:
    from .. import elements
    try:
        return elements.request_describe(_conn(), element_id)
    except production.ProductionError as exc:
        raise _error(exc)


@app.delete("/api/elements/{element_id}")
def remove_element(element_id: int) -> dict[str, Any]:
    from .. import elements
    try:
        elements.delete(_conn(), element_id)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/elements/{element_id}/images")
async def element_images(element_id: int, files: list[UploadFile] = File(...), state: str = Form(""),
                         role: str = Form("draft")) -> dict[str, Any]:
    from .. import elements
    tmp = Path(tempfile.mkdtemp(prefix="riot-upload-"))
    try:
        conn = _conn()
        return {"ok": True, "images": [elements.add_image(conn, element_id, p, state or None, role=role)
                                       for p in _save_uploads(tmp, files, "element")]}
    except production.ProductionError as exc:
        raise _error(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.post("/api/elements/{element_id}/generate")
def element_generate(element_id: int, body: ElementGen) -> dict[str, Any]:
    from .. import elements
    conn = _conn()
    try:
        if body.prompt is not None:
            elements.set_prompt(conn, element_id, body.prompt)
        e = elements._element(conn, element_id)
        prompt = None
        if body.notes.strip():
            has_draft = bool(elements._draft_for_state(conn, element_id, body.state)
                             or elements._draft_for_state(conn, element_id, None))
            prompt = elements.generation_prompt(e, body.state, body.notes.strip(), from_draft=has_draft)
        # Michael clique sur un bouton qui affiche le coût : c'est son accord
        return elements.launch_image(conn, element_id, body.state, prompt, approved=True)
    except (production.ProductionError, providers.ProviderError) as exc:
        raise _error(exc)


@app.post("/api/elements/{element_id}/prompt")
def element_prompt(element_id: int, body: ElementPrompt) -> dict[str, Any]:
    from .. import elements
    try:
        elements.set_prompt(_conn(), element_id, body.text)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/elements/generate-ready")
def elements_generate_ready(slug: str) -> dict[str, Any]:
    from .. import elements
    try:
        return elements.launch_ready(_conn(), slug)
    except (production.ProductionError, providers.ProviderError) as exc:
        raise _error(exc)


@app.post("/api/element-images/{image_id}")
def element_pick(image_id: int, body: Decision) -> dict[str, Any]:
    from .. import elements
    try:
        elements.pick(_conn(), image_id, body.decision)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/clips/{slug}/decors/request")
def decors_request(slug: str) -> dict[str, Any]:
    from .. import elements
    elements.request(_conn(), slug)
    return {"ok": True}


@app.post("/api/shots/{shot_id}/elements")
def shot_element(shot_id: int, body: ShotElementIn) -> dict[str, Any]:
    from .. import elements
    conn = _conn()
    try:
        if body.remove:
            elements.unlink(conn, shot_id, body.element_id)
        else:
            elements.link(conn, [shot_id], body.element_id, body.state, manual=True)   # ajouté à la main : gardé
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True, "elements": elements.for_shot(conn, shot_id)}


@app.post("/api/characters/{slug}/versions/{version}/resume")
def save_resume(slug: str, version: int, body: ScriptText) -> dict[str, Any]:
    try:
        production.save_resume(_conn(), slug, version, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/characters/{slug}/versions/{version}/adn")
def save_adn(slug: str, version: int, body: ScriptText) -> dict[str, Any]:
    try:
        production.save_adn(_conn(), slug, version, body.text)
    except (production.ProductionError, LookupError) as exc:
        raise _error(exc)
    return {"ok": True}


class LookIn(BaseModel):
    name: str
    description: str = ""
    clip_slug: str | None = None


@app.post("/api/characters/{slug}/looks")
def new_look(slug: str, body: LookIn) -> dict[str, Any]:
    try:
        return production.create_look(_conn(), slug, body.name, body.description, clip_slug=body.clip_slug)
    except production.ProductionError as exc:
        raise _error(exc)


class LookEdit(BaseModel):
    description: str | None = None
    wearer: str | None = None   # nouveau porteur : la référence @ et les plans suivent


@app.post("/api/characters/{slug}/looks/{look}")
def edit_look(slug: str, look: str, body: LookEdit) -> dict[str, Any]:
    try:
        conn = _conn()
        if body.description is not None:
            production.update_look(conn, slug, look, body.description)
        key = production.move_look(conn, slug, look, body.wearer) if body.wearer else None
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True, "key": key}


@app.post("/api/characters/{slug}/looks/{look}/images")
async def look_images(slug: str, look: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="riot-upload-"))
    try:
        paths = _save_uploads(tmp, files, "tenue")
        return {"ok": True, "paths": [production.add_look_image(_conn(), slug, look, p) for p in paths]}
    except production.ProductionError as exc:
        raise _error(exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.post("/api/characters/{slug}/versions/{version}/instructions")
def instructions(slug: str, version: int, body: ScriptText) -> dict[str, Any]:
    try:
        production.set_instructions(_conn(), slug, version, body.text)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


@app.post("/api/characters/{slug}/versions/{version}/pack")
def pack(slug: str, version: int) -> dict[str, Any]:
    try:
        production.request_pack(_conn(), slug, version)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


class CanonDecision(BaseModel):
    decision: str
    comment: str = ""


@app.post("/api/character-assets/{asset_id}/canon-hd")
def canon_hd(asset_id: int, body: CanonDecision) -> dict[str, Any]:
    try:
        production.review_canon_hd(_conn(), asset_id, body.decision, body.comment)
    except production.ProductionError as exc:
        raise _error(exc)
    return {"ok": True}


class AssetPick(BaseModel):
    decision: str
    comment: str = ""


@app.post("/api/character-assets/{asset_id}")
def pick_character_asset(asset_id: int, body: AssetPick) -> dict[str, Any]:
    try:
        conn = _conn()
        if body.comment:
            production.comment_character_asset(conn, asset_id, body.comment)
        production.review_character_asset(conn, asset_id, body.decision)
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


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker() -> FileResponse:
    """À la racine : le service worker couvre toute la régie (installation en application)."""
    return FileResponse(STATIC / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/")
def index() -> HTMLResponse:
    """La page charge app.js et app.css avec leur date de modification : la tablette
    ne garde jamais une ancienne version en cache après une mise à jour."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for name in ("app.js", "app.css"):
        v = int((STATIC / name).stat().st_mtime)
        html = html.replace(f"/static/{name}", f"/static/{name}?v={v}")
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
