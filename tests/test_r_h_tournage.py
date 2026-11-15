"""Tournage par séquence en simulation : séquences, plan de tournage, accord, prises (R-H1, R-H7, R-H8, R-H12, R-T5)."""

import json

import pytest

from riotmachine import catalogue as cat
from riotmachine import cli, db, prises, production, settings, tournage


@pytest.fixture
def clip(studio, monkeypatch):
    cli.main(["init"])
    conn = db.connect()
    production.sync_character_files(conn)
    production.create_clip(conn, "Essai v3", song=studio["song"], characters=["jj"], script_text="essai")
    dec = {"blocks": [
        {"name": "Le matin", "shots": [
            {"t_start": 0, "t_end": 3, "description": "JJ sort de la maison", "characters": ["jj"]},
            {"t_start": 3, "t_end": 6.5, "description": "JJ ferme le portail", "characters": ["jj"],
             "detail": "JJ closes the gate and snaps the padlock"},
            {"t_start": 6.5, "t_end": 9, "description": "La rue vide"}]},
        {"name": "Le bureau", "shots": [
            {"t_start": 9, "t_end": 12, "description": "JJ au bureau", "characters": ["jj"]}]}]}
    production.import_shots(conn, "essai-v3", dec)
    b1 = conn.execute("SELECT id FROM blocks WHERE clip_slug='essai-v3' AND num=1").fetchone()[0]
    for (sid,) in conn.execute("SELECT id FROM shots WHERE block_id=?", (b1,)).fetchall():
        production.set_cut_ok(conn, sid, True)
    production.validate_block(conn, b1)
    # Veo branché en simulation, avec une enveloppe de crédits
    monkeypatch.setattr("riotmachine.routing.providers", lambda: [{"key": "vertex", "usable": True}])
    cat.reset()
    yield conn
    cat.reset()


def _seq(conn):
    d = tournage.clip_sequences(conn, "essai-v3")
    return d, d["sequences"][0]["id"]


def test_r_h1_default_sequences_per_block_and_d5_validated_only(clip):
    d, sid = _seq(clip)
    assert [s["name"] for s in d["sequences"]] == ["Le matin", "Le bureau"]
    assert d["sequences"][1]["badge"] == "aucun plan d'un bloc validé"
    v = tournage.sequence_view(clip, sid)
    assert v["plan"]["offer"] and v["plan"]["takes"]
    assert all(w["shot_id"] for t in v["plan"]["takes"] for w in t["shots"])


def test_r_h6_prompt_blocks_and_traps(clip):
    _, sid = _seq(clip)
    v = tournage.sequence_view(clip, sid)
    texts = [t["prompt"]["text"] for t in v["plan"]["takes"]]
    assert any("JJ" in x for x in texts)                       # identité injectée depuis le référentiel
    assert any("padlock" in t["prompt"]["traps"] for t in v["plan"]["takes"])   # mot piège signalé
    shot = next(s for s in v["shots"] if s["num"] == 2)
    assert "padlock" in shot["traps"]


def test_r_h2_michael_splits_sequence_and_plan_recomputes(clip):
    _, sid = _seq(clip)
    before = tournage.sequence_view(clip, sid)["plan"]
    rue = clip.execute("SELECT id FROM shots WHERE clip_slug='essai-v3' AND num=3").fetchone()[0]
    db.set_actor("michael")
    new = tournage.create_sequence(clip, "essai-v3", "La rue", [rue])
    after = tournage.sequence_view(clip, sid)["plan"]
    assert sum(len(t["shots"]) for t in after["takes"]) == sum(len(t["shots"]) for t in before["takes"]) - 1
    assert tournage.sequence_view(clip, new["id"])["profile"] == "decor"
    hist = clip.execute("SELECT author FROM changes WHERE table_name='shots' AND row_id=? AND field='sequence_id' "
                        "ORDER BY id DESC", (str(rue),)).fetchone()
    assert hist["author"] == "michael"


def test_d35_option_impacts_listed_before_change(clip):
    _, sid = _seq(clip)
    v = tournage.sequence_view(clip, sid)
    imp = v["option_impacts"]
    assert imp["resolution"] and all(x["impact"][0].startswith("Coût") for x in imp["resolution"].values())
    assert all("impact" in a for a in v["alternatives"])


def test_r_h7_refused_reference_never_sent(clip):
    _, sid = _seq(clip)
    v = tournage.sequence_view(clip, sid)
    first = v["refs"][0]["path"]
    tournage.set_ref_status(clip, first, "vertex", "refused_in")
    v = tournage.sequence_view(clip, sid)
    assert all(r["path"] != first for t in v["plan"]["takes"] for r in t.get("refs", []))
    assert not any(r["selected"] for r in v["refs"] if r["path"] == first)


def test_r_h8_shoot_only_on_accord_and_within_amount(clip):
    _, sid = _seq(clip)
    v = tournage.sequence_view(clip, sid)
    total = v["plan"]["total_usd"]
    assert clip.execute("SELECT COUNT(*) FROM takes").fetchone()[0] == 0     # rien ne part avant l'accord
    with pytest.raises(prises.ShootError, match="coût a changé"):
        prises.shoot(clip, sid, total - 0.5)
    r = prises.shoot(clip, sid, total)
    assert r["takes"] == len(v["plan"]["takes"]) and r["total_usd"] == total
    lot = clip.execute("SELECT * FROM shoot_lots").fetchone()
    assert lot["decided_by"] == "michael" and lot["total_usd"] == total
    # double clic : refusé tant que les prises sont en cours (R-T5)
    with pytest.raises(prises.ShootError, match="déjà en cours"):
        prises.shoot(clip, sid, total)


def test_r_h9_takes_run_in_simulation_and_reserve_decreases(clip):
    _, sid = _seq(clip)
    before = cat.reserves(clip)["vertex"]["remaining"]
    total = tournage.sequence_view(clip, sid)["plan"]["total_usd"]
    prises.shoot(clip, sid, total)
    assert round(before - cat.reserves(clip)["vertex"]["remaining"], 2) == total   # engagé dès l'accord
    for _ in range(5):
        prises.tick(clip)
    rows = clip.execute("SELECT * FROM takes").fetchall()
    assert all(r["status"] == "done" and r["path"] for r in rows)
    assert all((production.studio() / r["path"]).is_file() for r in rows)
    assert round(sum(r["cost_usd"] for r in rows), 2) == total
    assert all(r["funding"] == "reserve:vertex" for r in rows)
    sent = json.loads(rows[0]["refs"])
    if sent:
        assert tournage.ref_status(clip, sent[0], "vertex") == "accepted"


def test_refusal_not_billed_retried_then_blocked(clip, monkeypatch):
    _, sid = _seq(clip)
    prises.shoot(clip, sid, tournage.sequence_view(clip, sid)["plan"]["total_usd"])
    from riotmachine import providers
    monkeypatch.setattr(providers, "result", lambda job: (_ for _ in ()).throw(
        providers.ProviderError("Veo n'a rendu aucune vidéo (refusée par la modération : 15236754)")))
    for _ in range(8):
        prises.tick(clip)
    rows = clip.execute("SELECT * FROM takes").fetchall()
    assert all(r["status"] == "blocked" and r["cost_usd"] == 0 and r["retries"] == 2 for r in rows)


def test_r_t5_interrupted_submit_never_resent(clip):
    _, sid = _seq(clip)
    prises.shoot(clip, sid, tournage.sequence_view(clip, sid)["plan"]["total_usd"])
    clip.execute("UPDATE takes SET status='submitting'")
    prises.mark_interrupted(clip)
    prises.tick(clip)
    assert {r[0] for r in clip.execute("SELECT status FROM takes")} == {"check"}


def test_regie_shoot_route(clip):
    from fastapi.testclient import TestClient
    from riotmachine.regie.app import app
    client = TestClient(app)
    seqs = client.get("/api/clips/essai-v3/sequences").json()["sequences"]
    v = client.get(f"/api/sequences/{seqs[0]['id']}").json()
    r = client.post(f"/api/sequences/{seqs[0]['id']}/shoot", json={"accepted_usd": v["plan"]["total_usd"]})
    assert r.status_code == 200 and r.json()["takes"] >= 1
    r = client.post(f"/api/sequences/{seqs[1]['id']}/shoot", json={"accepted_usd": 99})
    assert r.status_code == 400


def _shot_all(clip):
    _, sid = _seq(clip)
    prises.shoot(clip, sid, tournage.sequence_view(clip, sid)["plan"]["total_usd"])
    for _ in range(5):
        prises.tick(clip)
    return sid


def test_r_h13_derush_keep_redo_window(clip):
    from riotmachine import derush
    sid = _shot_all(clip)
    v = derush.view(clip, sid)
    assert all(s["state"] == "a_derusher" for s in v["shots"])
    s1, s2 = v["shots"][0], v["shots"][1]
    t1 = s1["takes"][0]["take_id"]
    db.set_actor("michael")
    derush.keep(clip, t1, s1["id"])
    r = derush.redo(clip, s2["takes"][0]["take_id"], s2["id"], "parasite", "un cadenas apparaît")
    assert "mots pièges" in r["next"]
    with pytest.raises(tournage.TournageError, match="0,9 et 1,1"):
        derush.set_window(clip, t1, s1["id"], 0.2, 1.3)
    w = derush.set_window(clip, t1, s1["id"], 0.5, 1.1)
    assert w["t_out"] == round(0.5 + 3 * 1.1, 2)
    v = derush.view(clip, sid)
    assert [x["state"] for x in v["shots"]][:2] == ["garde", "a_refaire"]
    # le plan de tournage suivant ne porte que les plans à refaire (et ceux encore à dérusher n'y sont pas)
    plan = tournage.sequence_view(clip, sid)["plan"]
    planned = {w["shot_id"] for t in plan["takes"] for w in t["shots"]}
    assert planned == {s2["id"]}


def test_r_m1_montage_cartons_and_cache(clip):
    from riotmachine import derush, media, montage
    sid = _shot_all(clip)
    v = derush.view(clip, sid)
    db.set_actor("michael")
    derush.keep(clip, v["shots"][0]["takes"][0]["take_id"], v["shots"][0]["id"])
    info = montage.build(clip, "essai-v3")
    assert info["kept"] == 1 and info["shots"] == 3 and info["reencoded"] == 3
    assert abs(media.duration(production.studio() / info["path"]) - 9.0) < 0.3
    # une fenêtre modifiée : seul ce plan est réencodé
    derush.set_window(clip, v["shots"][0]["takes"][0]["take_id"], v["shots"][0]["id"], 0.4, 1.0)
    info = montage.build(clip, "essai-v3")
    assert info["reencoded"] == 1
    assert montage.build(clip, "essai-v3")["reencoded"] == 0
