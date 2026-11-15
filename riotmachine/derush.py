"""Dérushage plan par plan (PRODUCTION-PLANS-v3 §13 D-E, R-H13) et état v3 d'un plan (§12).

Michael juge chaque plan dans sa prise : garder, refaire avec un motif, régler la
fenêtre (début dans la prise, vitesse 0,9 à 1,1). Rien ici ne dépense : refaire
remet le plan dans le prochain plan de tournage, qui affiche son coût.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import db, tournage

SPEED_MIN, SPEED_MAX = 0.9, 1.1

# Motifs de « Refaire » et suite proposée (§13 E)
MOTIVES: dict[str, dict[str, str]] = {
    "visage": {"label": "Visage", "next": "Change la référence de visage dans le plan de tournage ; si ça ne suffit pas, "
               "passe sur une offre mieux notée en jeu."},
    "tenue": {"label": "Tenue ou objet faux", "next": "Vérifie la tenue du plan et les références envoyées ; ajoute la "
              "référence de l'objet."},
    "parasite": {"label": "Objet parasite", "next": "Retire le mot qui l'appelle dans l'action (mots pièges signalés) ; "
                 "il passe aussi dans « à éviter »."},
    "action": {"label": "Action, jeu", "next": "Réécris l'action du plan dans le plan de tournage (ou demande au "
               "prompteur), puis retourne-le."},
    "debut_fin": {"label": "Début ou fin du plan", "next": "Précise le début et la fin dans l'action ; le mode première "
                  "et dernière image viendra après le clip zéro."},
    "mains": {"label": "Mains, déformation", "next": "Relance telle quelle ; si ça recommence, passe sur l'offre au-dessus."},
    "raccord": {"label": "Raccord avec les voisins", "next": "Regroupe le plan avec son voisin dans une même prise "
                "(même axe), ou rapproche leurs actions."},
    "rythme": {"label": "Rythme, durée", "next": "Règle la fenêtre et la vitesse ici, sans rien dépenser ; sinon "
               "retouche le découpage."},
    "autre": {"label": "Autre", "next": "Ta remarque reste sur le plan ; corrige l'action ou les références avant de retourner."},
}

STATE_LABEL = {"a_preparer": "à préparer", "pret": "prêt", "en_tournage": "en tournage", "a_derusher": "à dérusher",
               "garde": "gardé", "a_refaire": "à refaire", "bloque": "bloqué"}


def _pairs(conn: sqlite3.Connection, shot_id: int) -> list[dict]:
    return db.rows(conn.execute(
        "SELECT ts.*, t.status AS take_status, t.path, t.offer_key, t.duration_s, t.form, t.error, t.cost_usd, "
        "t.est_usd, t.created_at AS take_created, t.mode, t.resolution FROM take_shots ts JOIN takes t ON t.id=ts.take_id "
        "WHERE ts.shot_id=? ORDER BY t.id DESC", (shot_id,)).fetchall())


def shot_state(conn: sqlite3.Connection, shot: dict, pairs: list[dict] | None = None) -> str:
    pairs = _pairs(conn, shot["id"]) if pairs is None else pairs
    if any(p["kept"] for p in pairs):
        return "garde"
    if any(p["take_status"] in ("queued", "submitting", "running") for p in pairs):
        return "en_tournage"
    if any(p["take_status"] == "done" and not p["verdict"] for p in pairs):
        return "a_derusher"
    if pairs and pairs[0]["take_status"] in ("blocked", "failed", "check"):
        return "bloque"
    if pairs and all(p["verdict"] == "redo" or p["take_status"] != "done" for p in pairs):
        return "a_refaire"
    return "pret" if shot.get("shootable") else "a_preparer"


def needs_take(conn: sqlite3.Connection, shot: dict) -> bool:
    """Le plan entre dans le prochain plan de tournage : jamais tourné, ou à refaire, ou bloqué."""
    return shot_state(conn, shot) in ("pret", "a_refaire", "bloque")


def view(conn: sqlite3.Connection, seq_id: int) -> dict[str, Any]:
    seq = tournage.seq_row(conn, seq_id)
    shots = [s for s in tournage.seq_shots(conn, seq_id) if s["shootable"]]
    clip = db.get_clip(conn, seq["clip_slug"])
    out = []
    for s in shots:
        pairs = _pairs(conn, s["id"])
        st = shot_state(conn, s, pairs)
        d = round(float(s["t_end"]) - float(s["t_start"]), 3)
        out.append({"id": s["id"], "num": s["num"], "t_start": s["t_start"], "t_end": s["t_end"], "duration": d,
                    "words": s.get("script") or s["description"], "state": st, "state_label": STATE_LABEL[st],
                    "takes": [{"take_id": p["take_id"], "status": p["take_status"], "path": p["path"],
                               "t_in": p["t_in"], "t_out": p["t_out"], "speed": p["speed"], "kept": bool(p["kept"]),
                               "verdict": p["verdict"], "motive": p["motive"], "note": p["note"],
                               "take_duration": p["duration_s"], "form": p["form"], "offer": p["offer_key"],
                               "cost_usd": p["cost_usd"] if p["cost_usd"] is not None else p["est_usd"],
                               "error": p["error"]} for p in pairs]})
    return {"sequence": seq, "shots": out, "song_path": clip.get("song_path"),
            "motives": [{"key": k, **v} for k, v in MOTIVES.items()]}


def _pair(conn: sqlite3.Connection, take_id: int, shot_id: int) -> dict:
    p = db.row(conn.execute("SELECT ts.*, t.duration_s, t.status AS take_status FROM take_shots ts JOIN takes t "
                            "ON t.id=ts.take_id WHERE ts.take_id=? AND ts.shot_id=?", (take_id, shot_id)).fetchone())
    if not p:
        raise tournage.TournageError("Ce plan n'est pas dans cette prise.")
    return p


def _log(conn: sqlite3.Connection, shot_id: int, field: str, old: Any, new: Any, reason: str) -> None:
    conn.execute("INSERT INTO changes (table_name, row_id, field, old, new, author, reason, created_at) "
                 "VALUES ('take_shots', ?, ?, ?, ?, ?, ?, ?)",
                 (str(shot_id), field, None if old is None else str(old), None if new is None else str(new),
                  db.actor(), reason, db.now()))


def set_window(conn: sqlite3.Connection, take_id: int, shot_id: int, t_in: float, speed: float = 1.0) -> dict:
    """Déplace la fenêtre du plan dans sa prise, ajuste la vitesse (gratuit, §14)."""
    p = _pair(conn, take_id, shot_id)
    speed = round(float(speed), 3)
    if not SPEED_MIN - 1e-6 <= speed <= SPEED_MAX + 1e-6:
        raise tournage.TournageError("La vitesse reste entre 0,9 et 1,1.")
    s = db.get_shot(conn, shot_id)
    need = (float(s["t_end"]) - float(s["t_start"])) * speed
    t_in = max(0.0, round(float(t_in), 2))
    if t_in + need > float(p["duration_s"]) + 0.01:
        raise tournage.TournageError(f"La fenêtre dépasse la fin de la prise ({p['duration_s']:.1f} s) : "
                                     f"recule le début ou accélère.")
    with db.tx(conn):
        conn.execute("UPDATE take_shots SET t_in=?, t_out=?, speed=? WHERE take_id=? AND shot_id=?",
                     (t_in, round(t_in + need, 2), speed, take_id, shot_id))
        _log(conn, shot_id, f"fenetre:{take_id}", f"{p['t_in']}@{p['speed']}", f"{t_in}@{speed}", "fenêtre réglée")
    return {"t_in": t_in, "t_out": round(t_in + need, 2), "speed": speed}


def keep(conn: sqlite3.Connection, take_id: int, shot_id: int) -> dict:
    p = _pair(conn, take_id, shot_id)
    if p["take_status"] != "done":
        raise tournage.TournageError("Cette prise n'est pas encore rentrée.")
    with db.tx(conn):
        conn.execute("UPDATE take_shots SET kept=0 WHERE shot_id=? AND take_id!=?", (shot_id, take_id))
        conn.execute("UPDATE take_shots SET kept=1, verdict='keep', decided_at=? WHERE take_id=? AND shot_id=?",
                     (db.now(), take_id, shot_id))
        _log(conn, shot_id, "garde", None, take_id, "plan gardé")
    return {"ok": True}


def redo(conn: sqlite3.Connection, take_id: int, shot_id: int, motive: str, note: str = "") -> dict:
    if motive not in MOTIVES:
        raise tournage.TournageError("Motif inconnu")
    _pair(conn, take_id, shot_id)
    with db.tx(conn):
        conn.execute("UPDATE take_shots SET kept=0, verdict='redo', motive=?, note=?, decided_at=? "
                     "WHERE take_id=? AND shot_id=?", (motive, (note or "").strip() or None, db.now(), take_id, shot_id))
        _log(conn, shot_id, "refaire", None, f"{motive}: {note}", "plan à refaire")
        if (note or "").strip():
            db.add_note(conn, shot_id, "michael", f"Dérushage, {MOTIVES[motive]['label']} : {note.strip()}")
    return {"ok": True, "next": MOTIVES[motive]["next"]}


def kept_segments(conn: sqlite3.Connection, slug: str, block_nums: list[int] | None = None) -> list[dict]:
    """Les plans du clip (blocs validés, ou ceux demandés) dans l'ordre du morceau, avec leur prise gardée."""
    q = ("SELECT s.id, s.num, s.t_start, s.t_end, s.description, s.script, b.num AS block_num FROM shots s "
         "LEFT JOIN blocks b ON b.id=s.block_id WHERE s.clip_slug=? AND s.deleted_at IS NULL")
    params: list[Any] = [slug]
    if block_nums:
        q += f" AND b.num IN ({','.join('?' * len(block_nums))})"
        params += block_nums
    else:
        q += " AND b.validated=1"
    out = []
    for s in db.rows(conn.execute(q + " ORDER BY s.t_start", params).fetchall()):
        k = conn.execute("SELECT ts.*, t.path FROM take_shots ts JOIN takes t ON t.id=ts.take_id WHERE ts.shot_id=? "
                         "AND ts.kept=1 AND t.status='done'", (s["id"],)).fetchone()
        out.append({**s, "take_path": k["path"] if k else None, "t_in": k["t_in"] if k else None,
                    "speed": k["speed"] if k else 1.0, "take_id": k["take_id"] if k else None})
    return out
