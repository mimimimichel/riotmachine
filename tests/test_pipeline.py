"""Clip complet en mode simulation : découpage -> images -> drafts -> finals -> lip-sync -> montage."""

import json

import pytest

from riotmachine import cli, db, production, routing, worker


def run(*args):
    return cli.main([str(a) for a in args])


def test_routing_rules(studio):
    assert routing.classify({"motion": "high", "framing": "MS"})[0] == "premium"
    assert routing.classify({"motion": "medium", "framing": "WS"})[0] == "premium"
    assert routing.classify({"motion": "medium", "framing": "MS"})[0] == "standard"
    assert routing.classify({"motion": "static", "framing": "CU"})[0] == "eco"
    assert routing.upgrade_tier("eco") == "standard"
    assert routing.upgrade_tier("premium") == "premium"
    kling = routing.model("kling-3-standard")
    payload = routing.build_payload(kling, prompt="p", image_urls=["u"], duration=5, negative_prompt="n")
    assert payload == {"generate_audio": False, "prompt": "p", "start_image_url": "u", "duration": "5",
                       "negative_prompt": "n"}
    wan = routing.model("wan-3")
    p = routing.build_payload(wan, prompt="p", image_urls=["u"], duration=4, seed=7, aspect_ratio="16:9")
    assert p["resolution"] == "480p" and p["duration"] == 4 and p["audio"] is False and p["seed"] == 7
    assert routing.choose_duration(kling, 3.4) == 4
    assert routing.estimate_cost(wan, 5, "draft") == 0.25
    assert routing.extract_output({"images": [{"url": "x"}]}, "images[0].url") == "x"


def test_full_clip(studio, tmp_path):
    assert run("init") == 0
    conn = db.connect()
    jj = conn.execute("SELECT * FROM characters WHERE slug='jj'").fetchone()
    assert jj["canon_version"] == 1
    refs = production.character_refs(conn, "jj", 1)
    assert refs[0].name.startswith("canon")

    script = tmp_path / "script.md"
    script.write_text("Couplet : JJ chante face caméra.\nRefrain : elle danse.", encoding="utf-8")
    assert run("clip", "new", "Premier Clip", "--song", studio["song"], "--vocals", studio["song"],
               "--script", script, "--characters", "jj", "--budget", "50") == 0
    assert production.needs_agent(conn, "premier-clip")["reasons"]

    shots = [
        {"t_start": 0, "t_end": 4, "description": "JJ chante en gros plan", "framing": "CU", "motion": "low",
         "characters": ["jj"], "singing": True, "section": "couplet"},
        {"t_start": 4, "t_end": 9, "description": "JJ danse, plan large", "framing": "WS", "motion": "high",
         "characters": ["jj"], "section": "refrain"},
        {"t_start": 9, "t_end": 12, "description": "Micro sur pied", "framing": "ECU", "motion": "static",
         "characters": [], "section": "refrain"},
    ]
    f = tmp_path / "shots.json"
    f.write_text(json.dumps({"shots": shots}), encoding="utf-8")
    assert run("shots", "import", "premier-clip", f) == 0
    production.set_stage(conn, "premier-clip", "decoupage_review")
    production.review_decoupage(conn, "premier-clip", "approve")
    ids = [r["id"] for r in conn.execute("SELECT id FROM shots ORDER BY num")]
    assert len(ids) == 3

    # storyboard
    for sid in ids:
        assert run("shot", "set", sid, "--image-prompt", "photo of JJ, 85mm") == 0
        assert run("gen", "image", sid) == 0
    worker.tick(conn, wake=False)
    assert {r["status"] for r in conn.execute("SELECT status FROM shots")} == {"image_qc"}
    for sid in ids:
        assert run("qc", "pass", sid) == 0
    production.approve_all(conn, "premier-clip", "images")

    # routage + prompts + drafts
    for sid in ids:
        assert run("route", sid, "--apply") == 0
        assert run("shot", "set", sid, "--video-prompt", "she moves", "--negative-prompt", "blur") == 0
        assert run("gen", "draft", sid) == 0
    tiers = [r["tier"] for r in conn.execute("SELECT tier FROM shots ORDER BY num")]
    assert tiers == ["eco", "premium", "eco"]
    worker.tick(conn, wake=False)
    for sid in ids:
        assert run("qc", "frames", sid) == 0
        assert run("qc", "pass", sid) == 0

    # retour de Michael sur le plan 2 -> routeur -> palier supérieur conservé
    assert production.review_shot(conn, ids[1], "change", "Les mains sont ratées") == "change_requested"
    rv = conn.execute("SELECT id FROM reviews WHERE handled=0").fetchone()["id"]
    assert run("review", "handle", rv, "--route", "prompteur") == 0
    assert db.get_shot(conn, ids[1])["status"] == "prompt_todo"
    assert run("gen", "draft", ids[1]) == 0
    worker.tick(conn, wake=False)
    assert run("qc", "pass", ids[1]) == 0
    assert db.latest_asset(conn, ids[1], "draft")["version"] == 2

    production.approve_all(conn, "premier-clip", "drafts")
    # finals automatiques, puis lip-sync automatique sur le plan chanté
    for _ in range(4):
        worker.tick(conn, wake=False)
    statuses = [r["status"] for r in conn.execute("SELECT status FROM shots ORDER BY num")]
    assert statuses == ["final_review"] * 3
    assert db.latest_asset(conn, ids[0], "lipsync") is not None
    production.approve_all(conn, "premier-clip", "finals")
    assert db.get_clip(conn, "premier-clip")["stage"] == "done"

    montage = production.assemble_clip(conn, "premier-clip")
    assert montage.is_file() and montage.stat().st_size > 1000
    assert db.clip_cost(conn, "premier-clip") > 0


def test_budget_blocks(studio, tmp_path):
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Petit budget", song=studio["song"], characters=["jj"], budget_usd=0.01)
    production.import_shots(conn, "petit-budget", [
        {"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    sid = conn.execute("SELECT id FROM shots").fetchone()["id"]
    production.update_shot(conn, sid, image_prompt="x")
    with pytest.raises(production.BudgetError):
        production.launch_image(conn, sid)


def test_casting_requires_validated_version(studio):
    run("init")
    conn = db.connect()
    production.new_character_version(conn, "jj")
    production.create_clip(conn, "Test casting", song=studio["song"])
    with pytest.raises(production.ProductionError):
        production.set_casting(conn, "test-casting", "jj", version=2)


def test_character_pack_flow(studio):
    run("init")
    conn = db.connect()
    v = production.new_character_version(conn, "jj")
    res = production.launch_character_asset(conn, "jj", v["version"], "canon", "candidate a", "portrait of JJ")
    assert res["refs"]
    worker.tick(conn, wake=False)
    a = conn.execute("SELECT * FROM character_assets WHERE id=?", (res["asset_id"],)).fetchone()
    assert a["status"] == "proposed"
    with pytest.raises(production.ProductionError):
        production.validate_character_version(conn, "jj", v["version"])
    res_b = production.launch_character_asset(conn, "jj", v["version"], "canon", "candidate b", "portrait 2")
    worker.tick(conn, wake=False)
    production.review_character_asset(conn, res["asset_id"], "canon")
    production.review_character_asset(conn, res_b["asset_id"], "canon")   # Michael change d'avis
    canons = conn.execute(
        "SELECT * FROM character_assets WHERE version_id=? AND kind='canon'", (v["id"],)).fetchall()
    assert len(canons) == 1 and canons[0]["id"] == res_b["asset_id"]
    assert production.absp(canons[0]["path"]).is_file()
    vdir = production.absp(v["dir"])
    assert len(list(vdir.glob("canon.*"))) == 1
    refs = production.character_refs(conn, "jj", v["version"])
    assert len(refs) == 1 and refs[0].stem == "canon"
    production.validate_character_version(conn, "jj", v["version"])
    assert conn.execute("SELECT canon_version FROM characters WHERE slug='jj'").fetchone()[0] == 2
