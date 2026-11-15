"""Routes de la régie pour le tournage v3 : séquences, plan de tournage, prises, dérushage, montage."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db, prises, production, tournage

router = APIRouter()


def _conn():
    conn = db.connect()
    db.init_db(conn)
    db.set_actor("michael")
    return conn


def _err(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


ERRORS = (prises.ShootError, tournage.TournageError, production.ProductionError, LookupError, ValueError)


@router.get("/api/clips/{slug}/sequences")
def clip_sequences(slug: str) -> dict[str, Any]:
    return tournage.clip_sequences(_conn(), slug)


@router.get("/api/sequences/{seq_id}")
def sequence(seq_id: int) -> dict[str, Any]:
    try:
        return tournage.sequence_view(_conn(), seq_id)
    except ERRORS as exc:
        raise _err(exc)


class NewSequence(BaseModel):
    name: str
    shot_ids: list[int] = []


@router.post("/api/clips/{slug}/sequences")
def new_sequence(slug: str, body: NewSequence) -> dict[str, Any]:
    try:
        return tournage.create_sequence(_conn(), slug, body.name, body.shot_ids)
    except ERRORS as exc:
        raise _err(exc)


class SeqUpdate(BaseModel):
    name: str | None = None
    fiche: str | None = None
    profile: str | None = None
    offer_key: str | None = None
    clear_offer: bool = False
    options: dict | None = None


@router.post("/api/sequences/{seq_id}")
def update_sequence(seq_id: int, body: SeqUpdate) -> dict[str, Any]:
    fields = {k: v for k, v in body.model_dump().items() if v is not None and k != "clear_offer"}
    if body.clear_offer:
        fields["offer_key"] = None
    try:
        return tournage.update_sequence(_conn(), seq_id, **fields)
    except ERRORS as exc:
        raise _err(exc)


class MoveShots(BaseModel):
    shot_ids: list[int]


@router.post("/api/sequences/{seq_id}/shots")
def move_shots(seq_id: int, body: MoveShots) -> dict[str, Any]:
    try:
        return tournage.move_shots(_conn(), body.shot_ids, seq_id)
    except ERRORS as exc:
        raise _err(exc)


class ShotAttrs(BaseModel):
    jeu: str | None = None
    axe: str | None = None
    composition: str | None = None
    action_en: str | None = None
    look: dict | None = None          # {"character": "jj", "look": "black-tailor"} ; look vide = aucune


@router.post("/api/shots/{shot_id}/attrs")
def shot_attrs(shot_id: int, body: ShotAttrs) -> dict[str, Any]:
    conn = _conn()
    fields = {k: v for k, v in body.model_dump().items() if v is not None and k != "look"}
    try:
        with db.tx(conn):
            if body.look:
                from .. import elements
                elements.set_shot_look(conn, shot_id, body.look["character"], body.look.get("look") or None)
                db.update(conn, "shots", shot_id, {"looks_manual": 1}, reason="tenue posée à la main")
            if fields:
                tournage.set_shot_attrs(conn, shot_id, **fields)
    except ERRORS as exc:
        raise _err(exc)
    return {"ok": True}


class Quality(BaseModel):
    quality: str


@router.post("/api/clips/{slug}/quality")
def clip_quality(slug: str, body: Quality) -> dict[str, Any]:
    try:
        tournage.set_quality(_conn(), slug, body.quality)
    except ERRORS as exc:
        raise _err(exc)
    return {"ok": True}


class Shoot(BaseModel):
    accepted_usd: float
    take_ns: list[int] | None = None


@router.post("/api/sequences/{seq_id}/shoot")
def shoot(seq_id: int, body: Shoot) -> dict[str, Any]:
    """Michael accorde la dépense affichée (R-H8, R-H12) : rien ne part avant, rien au-delà."""
    try:
        return prises.shoot(_conn(), seq_id, body.accepted_usd, body.take_ns, by="michael")
    except ERRORS as exc:
        raise _err(exc)


@router.post("/api/takes/{take_id}/relaunch")
def relaunch(take_id: int) -> dict[str, Any]:
    try:
        return prises.relaunch(_conn(), take_id)
    except ERRORS as exc:
        raise _err(exc)


# --- dérushage et montage -----------------------------------------------------------------

@router.get("/api/sequences/{seq_id}/derush")
def derush_view(seq_id: int) -> dict[str, Any]:
    from .. import derush
    try:
        return derush.view(_conn(), seq_id)
    except ERRORS as exc:
        raise _err(exc)


class Verdict(BaseModel):
    action: str                 # keep | redo | window
    motive: str | None = None
    note: str = ""
    t_in: float | None = None
    speed: float = 1.0


@router.post("/api/takes/{take_id}/shots/{shot_id}")
def take_shot(take_id: int, shot_id: int, body: Verdict) -> dict[str, Any]:
    from .. import derush
    conn = _conn()
    from .. import montage
    try:
        if body.action == "keep":
            out = derush.keep(conn, take_id, shot_id)
        elif body.action == "redo":
            out = derush.redo(conn, take_id, shot_id, body.motive or "autre", body.note)
        elif body.action == "window":
            out = derush.set_window(conn, take_id, shot_id, body.t_in or 0.0, body.speed)
        else:
            out = None
    except ERRORS as exc:
        raise _err(exc)
    if out is not None:
        slug = conn.execute("SELECT clip_slug FROM takes WHERE id=?", (take_id,)).fetchone()[0]
        montage.start(slug)        # le montage suit chaque décision, en tâche de fond (R-M1)
        return out
    raise _err(ValueError("Action inconnue"))


@router.post("/api/clips/{slug}/montage")
def montage_start(slug: str) -> dict[str, Any]:
    from .. import montage
    return montage.start(slug)


@router.get("/api/clips/{slug}/montage")
def montage_status(slug: str) -> dict[str, Any]:
    from .. import montage
    return montage.status(slug)
