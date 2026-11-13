"""Revue du 30/10 : découpage enregistré sur place, historique des remarques,
relance à la bonne étape, fin de la simulation, durée vs modèle, scénariste."""

import pytest

from riotmachine import cli, db, production, routing, scenario
from riotmachine.providers import ProviderError, submit


def _clip(studio):
    assert cli.main(["init"]) == 0
    assert cli.main(["clip", "new", "Test", "--song", str(studio["song"]), "--characters", "jj"]) == 0
    conn = db.connect()
    production.import_shots(conn, "test", {"blocks": [{"name": "Intro", "look": "cold window light", "shots": [
        {"t_start": 0, "t_end": 2, "description": "Plan court", "detail": "A short shot"},
        {"t_start": 2, "t_end": 12, "description": "Plan long"}]}]})
    return conn


def test_decoupage_garde_les_ids_et_le_texte_de_michael(studio):
    conn = _clip(studio)
    shots = conn.execute("SELECT * FROM shots WHERE clip_slug='test' ORDER BY num").fetchall()
    a, b = shots[0]["id"], shots[1]["id"]
    from riotmachine import elements
    el = elements.create(conn, "test", "decor", "Maison")
    elements.link(conn, [a], el["id"])
    # Michael réécrit le prompt détaillé et coupe le plan 1 en deux
    production.import_shots(conn, "test", {"blocks": [{"name": "Intro", "shots": [
        {"id": a, "t_start": 0, "t_end": 1, "description": "Plan court", "detail": "Mon texte"},
        {"split_from": a, "t_start": 1, "t_end": 2, "description": "Moitié", "detail": "Mon texte"},
        {"id": b, "t_start": 2, "t_end": 12, "description": "Plan long"}]}]}, by="michael")
    s1 = db.get_shot(conn, a)
    assert s1["detail"] == "Mon texte" and s1["detail_edited"] == 1 and s1["num"] == 1
    new = conn.execute("SELECT id FROM shots WHERE clip_slug='test' AND num=2").fetchone()["id"]
    assert conn.execute("SELECT COUNT(*) FROM shot_elements WHERE shot_id=?", (new,)).fetchone()[0] == 1
    # un agent ne réécrit pas le texte de Michael
    production.import_shots(conn, "test", {"blocks": [{"name": "Intro", "shots": [
        {"id": a, "t_start": 0, "t_end": 2, "description": "Plan court", "detail": "Autre"},
        {"id": b, "t_start": 2, "t_end": 12, "description": "Plan long"}]}]})
    assert db.get_shot(conn, a)["detail"] == "Mon texte"
    with pytest.raises(production.ProductionError):
        production.update_shot(conn, a, detail="Réécrit")
    assert conn.execute("SELECT look FROM blocks WHERE clip_slug='test'").fetchone()["look"] == "cold window light"


def test_duree_et_modele(studio):
    conn = _clip(studio)
    snap = production.clip_snapshot(conn, "test")
    fits = [s["fit"]["level"] for s in snap["shots"]]
    assert fits == ["warn", "bad"]           # Veo : 2 s fait payer 4 s ; 10 s dépasse 8 s
    assert snap["incomplete"] == [1, 2]


def test_historique_et_relance(studio):
    conn = _clip(studio)
    sid = conn.execute("SELECT id FROM shots WHERE clip_slug='test' AND num=1").fetchone()["id"]
    db.add_note(conn, sid, "michael", "Plus de lumière")
    conn.execute("UPDATE shots SET status='failed', failed_step='draft', video_prompt='x', model_key='veo-31-fast-vertex' "
                 "WHERE id=?", (sid,))
    db.add_note(conn, sid, "machine", "Échec vidéo draft")
    notes = db.shot_notes(conn, sid)
    assert [n["author"] for n in notes] == ["machine", "michael"]
    assert production.retry_failed(conn, sid) == "draft_todo"


def test_pas_de_faux_fichier(studio, monkeypatch):
    monkeypatch.delenv("RIOT_FAL_MOCK")
    from riotmachine import settings
    settings.reset_caches()
    with pytest.raises(ProviderError, match="pas branché"):
        submit(routing.model("seedance-2"), {}, kind="video")


def test_scenariste(studio):
    conn = _clip(studio)
    scenario.submit_brainstorm(conn, "test", "Une longue conversation de brainstorm sur le clip, avec des idées. " * 2)
    assert any(r.startswith("scenariste") for r in production.needs_agent(conn, "test")["reasons"])
    scenario.propose(conn, "test", {"resume": "r", "parts": [
        {"key": "pitch", "kind": "pitch", "text": "Nouveau pitch"},
        {"key": "plans", "kind": "plans", "text": "- un plan"}]})
    scenario.decide(conn, "test", "pitch", "accept")
    assert db.get_clip(conn, "test")["pitch"] == "Nouveau pitch"
    scenario.decide(conn, "test", "plans", "accept")
    assert db.get_clip(conn, "test")["scenario_status"] == "none"
    assert any(f["label"].startswith("Scénariste") for f in production.clip_files(conn, "test"))
