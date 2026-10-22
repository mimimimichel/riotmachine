"""Clip de démonstration, entièrement simulé (aucune dépense, aucun agent).

`riot demo` crée « demo-premier-clip » avec des plans à toutes les étapes, pour
découvrir la régie. Supprime-le avec `riot demo --reset`.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from . import db, production, worker

SLUG = "demo-premier-clip"

SCRIPT = """# Premier clip (démo)

Intention : JJ seule dans un entrepôt vide au petit matin, lumière froide qui se
réchauffe sur le refrain.

Plan 1 — 0:00.0 → 0:04.0 — JJ chante face caméra, gros plan, lumière froide de fenêtre
Plan 2 — 0:04.0 → 0:08.0 — Profil de JJ, elle ferme les yeux sur la fin de phrase
Plan 3 — 0:08.0 → 0:14.0 — Elle marche vers la grande verrière
Plan 4 — 0:14.0 → 0:20.0 — Refrain : elle danse, plan large, la caméra tourne autour d'elle
Plan 5 — 0:20.0 → 0:24.0 — Ses mains et ses boucles qui volent
Plan 6 — 0:24.0 → 0:28.0 — Le micro seul dans la lumière dorée
"""

SHOTS = [
    {"t_start": 0, "t_end": 4, "section": "couplet 1", "description": "JJ chante face caméra, gros plan, lumière froide de fenêtre",
     "framing": "CU", "motion": "low", "camera": "slow push-in", "characters": ["jj"], "singing": True},
    {"t_start": 4, "t_end": 8, "section": "couplet 1", "description": "Profil de JJ, elle ferme les yeux sur la fin de phrase",
     "framing": "MCU", "motion": "low", "camera": "static", "characters": ["jj"], "singing": True},
    {"t_start": 8, "t_end": 14, "section": "pré-refrain", "description": "JJ marche vers la grande verrière, de dos puis de trois quarts",
     "framing": "MS", "motion": "medium", "camera": "tracking shot", "characters": ["jj"]},
    {"t_start": 14, "t_end": 20, "section": "refrain", "description": "JJ danse au centre de l'entrepôt, plan large, poussière dans la lumière",
     "framing": "WS", "motion": "high", "camera": "orbit", "characters": ["jj"]},
    {"t_start": 20, "t_end": 24, "section": "refrain", "description": "Plan serré sur ses mains et ses boucles qui volent",
     "framing": "CU", "motion": "medium", "camera": "handheld", "characters": ["jj"]},
    {"t_start": 24, "t_end": 28, "section": "outro", "description": "Micro sur pied seul dans la lumière dorée",
     "framing": "ECU", "motion": "static", "camera": "static", "characters": []},
]


def _drain(conn: sqlite3.Connection) -> None:
    for _ in range(6):
        worker.poll_jobs(conn)
        worker.run_automatic_steps(conn)


def reset(conn: sqlite3.Connection) -> None:
    ids = [r["id"] for r in conn.execute("SELECT id FROM shots WHERE clip_slug=?", (SLUG,))]
    with db.tx(conn):
        for sid in ids:
            asset_ids = [r["id"] for r in conn.execute("SELECT id FROM assets WHERE shot_id=?", (sid,))]
            for aid in asset_ids:
                conn.execute("DELETE FROM jobs WHERE target_table='assets' AND target_id=?", (aid,))
            conn.execute("DELETE FROM assets WHERE shot_id=?", (sid,))
        for table in ("shots", "castings", "reviews", "events"):
            conn.execute(f"DELETE FROM {table} WHERE clip_slug=?", (SLUG,))
        conn.execute("DELETE FROM agent_runs WHERE clip_slug=?", (SLUG,))
        conn.execute("DELETE FROM clips WHERE slug=?", (SLUG,))
    shutil.rmtree(production.studio() / "clips" / SLUG, ignore_errors=True)


def create(conn: sqlite3.Connection) -> str:
    reset(conn)
    production.sync_character_files(conn)
    tmp = Path(tempfile.mkdtemp())
    song = tmp / "demo.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=220:duration=28,volume=0.2", str(song)], check=True)
    production.create_clip(conn, "Premier clip (démo)", slug=SLUG, song=song, vocals=song,
                           script_text=SCRIPT, bpm=96, characters=["jj"], budget_usd=80)
    shutil.rmtree(tmp, ignore_errors=True)
    notes = production.studio() / "clips" / SLUG / "script" / "notes.md"
    notes.write_text("Relecture (démo) : le refrain en plan large dansé est le plan le plus cher ; "
                     "le gros plan mains (plan 5) est risqué en IA, à surveiller.", encoding="utf-8")
    production.import_shots(conn, SLUG, SHOTS)
    production.set_stage(conn, SLUG, "decoupage_review")
    production.review_decoupage(conn, SLUG, "approve")
    ids = [r["id"] for r in conn.execute("SELECT id FROM shots WHERE clip_slug=? ORDER BY num", (SLUG,))]

    for sid in ids:
        production.update_shot(conn, sid, image_prompt="Use the reference images for JJ's exact face… (démo)")
        production.launch_image(conn, sid)
    _drain(conn)
    for sid in ids:
        production.qc_result(conn, sid, True, "démo")
    for sid in ids[:4]:
        production.review_shot(conn, sid, "approve")
        shot = db.get_shot(conn, sid)
        route = production.routing.route_shot(shot)
        production.update_shot(conn, sid, tier=route["tier"], model_key=route["model_key"],
                               video_prompt="She sings softly, slow push-in… (démo)", negative_prompt="blur")
        production.launch_draft(conn, sid)
    _drain(conn)
    for sid in ids[:4]:
        production.qc_result(conn, sid, True, "démo")
    for sid in ids[:2]:
        production.review_shot(conn, sid, "approve")
    _drain(conn)
    production.review_shot(conn, ids[3], "change", "La danse est trop sage : je veux un vrai tour sur elle-même sur le temps fort.")
    return SLUG
