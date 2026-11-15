"""Les prises : accord, départ chez le fournisseur, suivi, refus non facturés (R-H8, R-H9, R-T5).

Cycle d'une prise :
    queued      accordée par Michael, pas encore envoyée
    submitting  envoi en cours (si le worker s'arrête ici, la prise passe « check » au redémarrage :
                elle n'est jamais renvoyée d'office, D22)
    running     chez le fournisseur
    done        vidéo reçue, à dérusher
    blocked     refusée (référence refusée, vidéo filtrée deux fois…) : le message dit quoi faire
    failed      erreur facturée ou inattendue
    check       à vérifier par Michael (envoi interrompu)
"""

from __future__ import annotations

import base64
import json
import mimetypes
import sqlite3
from pathlib import Path
from typing import Any

from . import catalogue as cat
from . import db, notify, production, providers, routing, tournage
from .settings import load_models

MAX_FREE_RETRIES = 2      # relances automatiques d'un refus non facturé (PRODUCTION-PLANS-v3 §10)


class ShootError(Exception):
    pass


def _data_uri(rel: str) -> str:
    p = production.absp(rel)
    if not p or not p.is_file():
        raise ShootError(f"Image introuvable : {rel}")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def shoot(conn: sqlite3.Connection, seq_id: int, accepted_usd: float, take_ns: list[int] | None = None,
          by: str = "michael") -> dict:
    """Michael accorde la dépense affichée : un lot, une prise par groupe de plans. Rien ne part au-delà
    du montant accordé (R-H8). Un double clic ne crée pas deux fois les mêmes prises (R-T5)."""
    view = tournage.sequence_view(conn, seq_id)
    plan = view["plan"]
    if not plan or not plan["takes"]:
        if any(x.get("state") == "en_tournage" for x in view["shots"]):
            raise ShootError("Ces plans sont déjà en cours de tournage : attends leur retour.")
        raise ShootError("Aucune prise à tourner dans cette séquence.")
    if plan["blocking"]:
        raise ShootError("Des points bloquants restent à régler (en rouge sur la page de la séquence).")
    takes = [t for t in plan["takes"] if not take_ns or t["n"] in take_ns]
    total = round(sum(t["est_usd"] for t in takes), 2)
    if total > float(accepted_usd) + 0.005:
        raise ShootError(f"Le coût a changé : {total:.2f} $ au lieu de {accepted_usd:.2f} $. Recharge la page et relis.")
    seq = view["sequence"]
    o = cat.offer(plan["offer"])
    with db.tx(conn):
        busy = []
        for t in takes:
            key = _content_key(seq_id, plan, t)
            if conn.execute("SELECT 1 FROM takes WHERE idem_key LIKE ? AND status IN ('queued','submitting','running')",
                            (key + "%",)).fetchone():
                busy.append(t["n"])
        if busy:
            raise ShootError("Ces prises sont déjà en cours de tournage : " + ", ".join(chr(64 + n) for n in busy) + ".")
        cur = conn.execute("INSERT INTO shoot_lots (clip_slug, sequence_id, total_usd, status, decided_by, created_at) "
                           "VALUES (?,?,?,?,?,?)", (seq["clip_slug"], seq_id, total, "approved", by, db.now()))
        lot = cur.lastrowid
        created = []
        reserves = cat.reserves(conn)
        for t in takes:
            key = _content_key(seq_id, plan, t)
            n_same = conn.execute("SELECT COUNT(*) FROM takes WHERE idem_key LIKE ?", (key + "%",)).fetchone()[0]
            funding, _ = cat.funding_for(o, t["est_usd"], reserves)
            refs = [r["path"] for r in (t.get("refs") or [])]
            cur = conn.execute(
                "INSERT INTO takes (clip_slug, sequence_id, lot_id, offer_key, mode, form, duration_s, resolution, prompt, "
                "refs, est_usd, funding, status, idem_key, provider, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (seq["clip_slug"], seq_id, lot, o["key"], t["mode"], t["form"], t["duration_s"], t["resolution"],
                 json.dumps({"text": t["prompt"]["text"], "negative": t["prompt"]["negative"]}, ensure_ascii=False),
                 json.dumps(refs), t["est_usd"], funding, "queued", f"{key}-{n_same + 1}", o["provider"], db.now(), db.now()))
            tid = cur.lastrowid
            for i, w in enumerate(t["shots"]):
                conn.execute("INSERT INTO take_shots (take_id, shot_id, ord, t_in, t_out) VALUES (?,?,?,?,?)",
                             (tid, w["shot_id"], i, w["t_in"], w["t_out"]))
            created.append(tid)
        db.log_event(conn, seq["clip_slug"], "shoot",
                     f"Séquence {seq['num']} « {seq['name']} » : {len(created)} prise(s) accordée(s), {total:.2f} $ ({o['label']})")
    return {"lot": lot, "takes": len(created), "take_ids": created, "total_usd": total}


def _content_key(seq_id: int, plan: dict, t: dict) -> str:
    return tournage.idem_key(seq_id, plan["offer"], t["mode"], t["resolution"], t["duration_s"],
                             [(w["shot_id"], w["t_in"], w["t_out"]) for w in t["shots"]],
                             t["prompt"]["text"], [r["path"] for r in (t.get("refs") or [])])


# --- worker -----------------------------------------------------------------------------

def _model_cfg(offer_key: str) -> dict:
    return {**load_models()["models"][offer_key], "key": offer_key}


def submit_queued(conn: sqlite3.Connection) -> int:
    n = 0
    for t in db.rows(conn.execute("SELECT * FROM takes WHERE status='queued' ORDER BY id").fetchall()):
        conn.execute("UPDATE takes SET status='submitting', attempts=attempts+1, updated_at=? WHERE id=? AND status='queued'",
                     (db.now(), t["id"]))
        p = json.loads(t["prompt"])
        refs = json.loads(t["refs"] or "[]")
        payload: dict[str, Any] = {"prompt": p["text"], "negative_prompt": p.get("negative"),
                                   "duration": int(t["duration_s"]), "resolution": t["resolution"],
                                   "aspect_ratio": _aspect(conn, t["clip_slug"])}
        try:
            if t["mode"] == "references":
                payload["references"] = [_data_uri(r) for r in refs]
            sub = providers.submit(_model_cfg(t["offer_key"]), payload, kind="video",
                                   label=f"prise {t['id']}", seconds=t["duration_s"])
        except (providers.ProviderError, ShootError) as exc:
            _refused_or_failed(conn, t, str(exc), at_input=True)
            continue
        conn.execute("UPDATE takes SET status='running', provider=?, request_id=?, status_url=?, response_url=?, "
                     "updated_at=? WHERE id=?", (sub["provider"], sub.get("request_id"), sub.get("status_url"),
                                                 sub.get("response_url"), db.now(), t["id"]))
        n += 1
    return n


def _aspect(conn: sqlite3.Connection, slug: str) -> str:
    r = conn.execute("SELECT aspect_ratio FROM clips WHERE slug=?", (slug,)).fetchone()
    return r["aspect_ratio"] if r else "16:9"


def _is_refusal(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in ("modération", "usage guidelines", "filtered", "15236754", "responsible ai", "rai"))


def _refused_or_failed(conn: sqlite3.Connection, t: dict, msg: str, at_input: bool = False) -> None:
    o = cat.offer(t["offer_key"])
    refusal = _is_refusal(msg)
    if refusal and not o["refusals_billed"]:
        refs = json.loads(t["refs"] or "[]")
        if at_input or "input image" in msg.lower():
            # refus à l'entrée : une des références ne passe pas. On ne sait pas laquelle : Michael tranche.
            conn.execute("UPDATE takes SET status='blocked', cost_usd=0, error=?, updated_at=? WHERE id=?",
                         (f"{o['provider_label']} refuse une des images de référence ({len(refs)} envoyées). "
                          "Rien n'est facturé. Dans le plan de tournage, décoche une référence ou remplace-la, puis relance.",
                          db.now(), t["id"]))
            _notify(conn, t, "refusée à l'entrée (une référence ne passe pas), rien n'est facturé")
            return
        if t["retries"] < MAX_FREE_RETRIES:
            # vidéo filtrée en sortie, non facturée : relance automatique, au plus deux fois
            conn.execute("UPDATE takes SET status='queued', retries=retries+1, request_id=NULL, status_url=NULL, "
                         "response_url=NULL, error=?, updated_at=? WHERE id=?", (msg[:500], db.now(), t["id"]))
            return
        conn.execute("UPDATE takes SET status='blocked', cost_usd=0, error=?, updated_at=? WHERE id=?",
                     (f"Vidéo filtrée par {o['provider_label']} trois fois de suite, sans frais. Change une référence "
                      "ou le texte de l'action, puis relance.", db.now(), t["id"]))
        _notify(conn, t, "filtrée trois fois, sans frais : à revoir")
        return
    conn.execute("UPDATE takes SET status='failed', error=?, updated_at=? WHERE id=?", (msg[:1000], db.now(), t["id"]))
    _notify(conn, t, f"en échec : {msg[:160]}")


def _notify(conn: sqlite3.Connection, t: dict, what: str) -> None:
    notify.send_once(conn, f"take:{t['id']}:{t['status']}:{t['retries']}",
                     f"🎬 Prise {t['id']} ({t['clip_slug']}) {what}.\n"
                     + notify.regie_link(f"#/clip/{t['clip_slug']}/tournage/d/{t['sequence_id']}"))


def poll_running(conn: sqlite3.Connection) -> int:
    """Suit les prises chez le fournisseur. Sans prise en cours, aucune requête sortante (R-T2)."""
    done = 0
    for t in db.rows(conn.execute("SELECT * FROM takes WHERE status='running' ORDER BY id").fetchall()):
        job = {"provider": t["provider"], "request_id": t["request_id"], "status_url": t["status_url"],
               "response_url": t["response_url"]}
        try:
            st = providers.status(job)
            if st in ("IN_QUEUE", "IN_PROGRESS"):
                continue
            try:
                res = providers.result(job)
            except providers.ProviderError as exc:
                _refused_or_failed(conn, t, str(exc))
                done += 1
                continue
            url = routing.extract_output(res, _model_cfg(t["offer_key"]).get("output", "video.url"))
            dest = production.studio() / "clips" / t["clip_slug"] / "prises" / f"prise-{t['id']:04d}.mp4"
            providers.download(url, dest, t["provider"])
            conn.execute("UPDATE takes SET status='done', path=?, cost_usd=est_usd, error=NULL, updated_at=? WHERE id=?",
                         (production.rel(dest), db.now(), t["id"]))
            _after_done(conn, t)
            done += 1
        except Exception as exc:   # réseau : on réessaie au tour suivant
            conn.execute("UPDATE takes SET error=?, updated_at=? WHERE id=?", (f"suivi : {exc}"[:500], db.now(), t["id"]))
    return done


def _after_done(conn: sqlite3.Connection, t: dict) -> None:
    """Références acceptées ; notification groupée quand toutes les prises du lot sont rentrées (R-D5)."""
    for r in json.loads(t["refs"] or "[]"):
        tournage.set_ref_status(conn, r, t["provider"], "accepted", f"prise {t['id']}")
    left = conn.execute("SELECT COUNT(*) FROM takes WHERE lot_id=? AND status IN ('queued','submitting','running')",
                        (t["lot_id"],)).fetchone()[0]
    if not left:
        n = conn.execute("SELECT COUNT(*) FROM takes WHERE lot_id=? AND status='done'", (t["lot_id"],)).fetchone()[0]
        conn.execute("UPDATE shoot_lots SET status='done' WHERE id=?", (t["lot_id"],))
        notify.send_once(conn, f"lot-done:{t['lot_id']}",
                         f"🎬 {n} prise(s) prête(s) à dérusher ({t['clip_slug']}).\n"
                         + notify.regie_link(f"#/clip/{t['clip_slug']}/tournage/d/{t['sequence_id']}"))


def mark_interrupted(conn: sqlite3.Connection) -> None:
    """Au démarrage du worker : un envoi interrompu n'est jamais renvoyé d'office (R-T5, D22)."""
    conn.execute("UPDATE takes SET status='check', error=?, updated_at=? WHERE status='submitting'",
                 ("Envoi interrompu (redémarrage) : la prise est peut-être partie. Vérifie avant de relancer.", db.now()))


def relaunch(conn: sqlite3.Connection, take_id: int) -> dict:
    """Michael relance une prise bloquée ou à vérifier, au même prix déjà accordé (même contenu)."""
    t = db.row(conn.execute("SELECT * FROM takes WHERE id=?", (take_id,)).fetchone())
    if not t or t["status"] not in ("blocked", "check", "failed"):
        raise ShootError("Cette prise n'est pas à relancer.")
    conn.execute("UPDATE takes SET status='queued', retries=0, error=NULL, updated_at=? WHERE id=?", (db.now(), take_id))
    return {"ok": True}


def tick(conn: sqlite3.Connection) -> dict:
    return {"takes_sent": submit_queued(conn), "takes_back": poll_running(conn)}


def spent(conn: sqlite3.Connection, slug: str | None = None) -> dict:
    q = "SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(CASE WHEN status IN ('queued','submitting','running') THEN est_usd END),0) FROM takes"
    r = conn.execute(q + (" WHERE clip_slug=?" if slug else ""), ((slug,) if slug else ())).fetchone()
    return {"spent_usd": round(r[0], 2), "engaged_usd": round(r[1], 2)}
