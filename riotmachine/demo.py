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

PITCH = "JJ seule dans un entrepôt vide au petit matin. La lumière froide se réchauffe à mesure qu'elle reprend confiance."

CONCEPT = """Un plan-séquence mental : JJ arrive dans un entrepôt abandonné où elle répétait avec son ancien groupe.
Couplets dans la lumière froide de l'aube, refrains dans un or chaud qui envahit tout l'espace.
Palette : bleu acier puis ambre. Caméra lente sur les couplets, libre et tournante sur les refrains.
Fin : le micro seul dans la lumière, elle est partie."""

LYRICS = """[Couplet 1]
Le matin rentre par les vitres cassées
J'ai gardé ta voix dans le béton

[Pré-refrain]
Et je marche vers la lumière

[Refrain]
Riot, riot, tout brûle en dedans
Riot, riot, je danse contre le vent
"""

# (bloc, intention, [(durée, description, cadrage, mouvement, caméra, chanté)])
BLOCKS = [
    ("Intro", "Arrivée dans l'entrepôt, aube bleue", [
        (3.0, "Porte métallique qui s'entrouvre, poussière dans le contre-jour", "WS", "low", "static", False),
        (3.0, "Silhouette de JJ dans l'encadrement", "MWS", "low", "slow push-in", False),
        (2.5, "Ses baskets sur le sol mouillé", "CU", "low", "tracking", False),
        (3.5, "Plan large de l'entrepôt vide, JJ minuscule au centre", "EWS", "static", "static", False),
    ]),
    ("Couplet 1", "Elle chante pour elle-même, lumière froide", [
        (4.0, "JJ chante face caméra, gros plan, lumière froide de fenêtre", "CU", "low", "slow push-in", True),
        (4.0, "Profil de JJ, elle ferme les yeux sur la fin de phrase", "MCU", "low", "static", True),
        (3.0, "Sa main glisse sur un vieux pied de micro", "CU", "low", "static", False),
        (4.0, "JJ chante en marchant le long des vitres", "MS", "medium", "tracking", True),
        (3.0, "Reflet de JJ dans une vitre brisée", "MCU", "low", "static", False),
        (4.0, "JJ chante, regard caméra, la lumière commence à chauffer", "CU", "low", "slow push-in", True),
    ]),
    ("Pré-refrain", "La lumière monte, elle avance", [
        (3.0, "JJ marche vers la grande verrière, de dos", "MS", "medium", "tracking", False),
        (3.0, "Ses boucles traversées par un rayon de soleil", "ECU", "low", "static", False),
        (3.0, "Elle se retourne de trois quarts, sourire léger", "MCU", "medium", "handheld", True),
    ]),
    ("Refrain 1", "Explosion d'or, elle danse", [
        (4.0, "JJ danse au centre de l'entrepôt, plan large, poussière dans la lumière", "WS", "high", "orbit", False),
        (3.0, "Gros plan visage, elle chante le refrain à pleine voix", "CU", "medium", "handheld", True),
        (3.0, "Ses mains et ses boucles qui volent", "CU", "high", "handheld", False),
        (4.0, "Tour sur elle-même sur le temps fort, caméra basse", "MWS", "high", "low angle orbit", False),
        (3.0, "Elle chante, bras levés, contre-jour doré", "MS", "medium", "slow push-in", True),
    ]),
    ("Couplet 2", "Retour au calme, souvenir du groupe", [
        (4.0, "Photos du groupe scotchées sur un pilier", "CU", "static", "static", False),
        (4.0, "JJ chante assise sur une caisse, lumière ambrée", "MS", "low", "static", True),
        (3.0, "Ses doigts tapent le rythme sur la caisse", "ECU", "low", "static", False),
        (4.0, "JJ chante, plan rapproché, larme retenue", "CU", "low", "slow push-in", True),
    ]),
    ("Outro", "Elle part, la lumière reste", [
        (4.0, "JJ s'éloigne vers la porte, plan large", "WS", "medium", "static", False),
        (4.0, "Le micro seul dans la lumière dorée", "ECU", "static", "static", False),
    ]),
]


def _decoupage() -> dict:
    t = 0.0
    blocks = []
    for name, intention, shots in BLOCKS:
        items = []
        for dur, desc, framing, motion, camera, singing in shots:
            items.append({"t_start": round(t, 1), "t_end": round(t + dur, 1), "description": desc, "framing": framing,
                          "motion": motion, "camera": camera, "characters": [] if "micro seul" in desc or "Photos" in desc
                          or "Porte" in desc else ["jj"], "singing": singing})
            t += dur
        blocks.append({"name": name, "intention": intention, "shots": items})
    return {"blocks": blocks}


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
        for table in ("shots", "blocks", "clip_files", "castings", "reviews", "events"):
            conn.execute(f"DELETE FROM {table} WHERE clip_slug=?", (SLUG,))
        conn.execute("DELETE FROM agent_runs WHERE clip_slug=?", (SLUG,))
        conn.execute("DELETE FROM clips WHERE slug=?", (SLUG,))
    shutil.rmtree(production.studio() / "clips" / SLUG, ignore_errors=True)


def create(conn: sqlite3.Connection) -> str:
    reset(conn)
    production.sync_character_files(conn)
    dec = _decoupage()
    total = dec["blocks"][-1]["shots"][-1]["t_end"]
    tmp = Path(tempfile.mkdtemp())
    song = tmp / "demo.mp3"
    # un faux morceau avec du relief, pour que la forme d'onde ressemble à quelque chose
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=110:duration={total},volume='0.15+0.6*abs(sin(t*1.7))*(0.5+0.5*sin(t/9))':eval=frame",
                    str(song)], check=True)
    dossier = tmp / "dossier-de-realisation.md"
    dossier.write_text("# Dossier de réalisation (démo)\n\n" + CONCEPT, encoding="utf-8")
    production.create_clip(conn, "Premier clip (démo)", slug=SLUG, song=song, vocals=song,
                           characters=["jj"], budget_usd=80, pitch=PITCH, concept=CONCEPT,
                           lyrics_text=LYRICS, dossier=[dossier])
    shutil.rmtree(tmp, ignore_errors=True)
    notes = production.studio() / "clips" / SLUG / "script" / "notes.md"
    notes.write_text("Relecture (démo) : le refrain dansé en plan large est le plus cher ; "
                     "les gros plans de mains sont risqués en IA, à surveiller.", encoding="utf-8")
    production.import_shots(conn, SLUG, dec)
    production.set_stage(conn, SLUG, "decoupage_review")
    production.review_decoupage(conn, SLUG, "approve")
    ids = [r["id"] for r in conn.execute("SELECT id FROM shots WHERE clip_slug=? ORDER BY num", (SLUG,))]
    n = len(ids)

    # Visuels draft pour tous les plans sauf l'outro (encore en cours de storyboard)
    for sid in ids[:-2]:
        production.update_shot(conn, sid, image_prompt="Use the reference images for JJ's exact face… (démo)")
        production.launch_image(conn, sid)
    _drain(conn)
    for sid in ids[:-2]:
        production.qc_result(conn, sid, True, "démo")

    # Visuels validés sur l'intro, le couplet 1, le pré-refrain et le refrain 1 -> HD
    validated = ids[:18]
    for sid in validated:
        production.review_shot(conn, sid, "approve")
    _drain(conn)
    for sid in validated:
        shot = db.get_shot(conn, sid)
        if shot["status"] == "hd_qc":
            production.qc_result(conn, sid, sid != ids[12], "démo" if sid != ids[12] else
                                 "La HD a lissé les boucles : texture moins serrée que sur le visuel validé")
    # le plan 13 a eu deux refus : il remonte à Michael
    for _ in range(3):
        _drain(conn)
        shot = db.get_shot(conn, ids[12])
        if shot["status"] == "hd_qc":
            production.qc_result(conn, ids[12], False, "La HD a lissé les boucles : texture moins serrée que sur le visuel validé")

    # Plans vidéo (routeur + prompteur) pour les plans dont la HD est prête
    for sid in validated:
        shot = db.get_shot(conn, sid)
        if shot["status"] != "prompt_todo":
            continue
        route = production.routing.route_shot(shot)
        production.update_shot(conn, sid, tier=route["tier"], model_key=route["model_key"], route_reason=route["why"],
                               video_prompt="She sings softly as the camera slowly pushes in… (démo)",
                               negative_prompt="blur, morphing face")
        production.submit_video_plan(conn, sid)
    # Michael a validé les plans vidéo de l'intro et du couplet 1
    for sid in ids[:10]:
        production.review_shot(conn, sid, "approve")
    _drain(conn)
    for sid in ids[:10]:
        if db.get_shot(conn, sid)["status"] == "draft_qc":
            production.qc_result(conn, sid, True, "démo")
    # vidéos draft validées sur l'intro et le début du couplet 1 -> vidéo HD + lip-sync
    for sid in ids[:7]:
        production.review_shot(conn, sid, "approve")
    _drain(conn)
    for sid in ids[:4]:
        production.review_shot(conn, sid, "approve")
    production.review_shot(conn, ids[8], "change",
                           "Le reflet est trop net, je veux qu'on devine à peine son visage dans la vitre.")
    production.review_shot(conn, ids[16], "approve")  # plan vidéo validé
    _drain(conn)
    del n
    return SLUG
