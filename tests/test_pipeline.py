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
    """Parcours complet : dossier -> blocs -> visuel draft -> HD -> plan vidéo -> vidéo draft -> HD + lip-sync."""
    assert run("init") == 0
    conn = db.connect()
    jj = conn.execute("SELECT * FROM characters WHERE slug='jj'").fetchone()
    assert jj["canon_version"] == 1
    refs = production.character_refs(conn, "jj", 1)
    assert refs[0].name.startswith("canon")

    dossier = tmp_path / "Dossier de réalisation.md"
    dossier.write_text("# DA\nAube froide puis or.", encoding="utf-8")
    assert run("clip", "new", "Premier Clip", "--song", studio["song"], "--vocals", studio["song"],
               "--characters", "jj", "--budget", "50", "--pitch", "JJ seule à l'aube",
               "--dossier", dossier) == 0
    clip = db.get_clip(conn, "premier-clip")
    assert clip["pitch"] == "JJ seule à l'aube" and clip["duration_s"] > 19
    files = production.clip_files(conn, "premier-clip")
    assert {f["kind"] for f in files} == {"song", "vocals", "dossier"}
    doc = next(f for f in files if f["kind"] == "dossier")
    assert production.absp(doc["text_path"]).read_text(encoding="utf-8").startswith("# DA")
    # rien ne part chez le script doctor tant que Michael n'a pas envoyé son dossier
    assert production.needs_agent(conn, "premier-clip")["reasons"] == []
    production.submit_brief(conn, "premier-clip")
    assert production.needs_agent(conn, "premier-clip")["reasons"] == ["script_doctor: découpage à extraire du dossier"]

    dec = {"blocks": [
        {"name": "Couplet", "intention": "froid", "shots": [
            {"t_start": 0, "t_end": 4, "description": "JJ chante en gros plan", "framing": "CU", "motion": "low",
             "characters": ["jj"], "singing": True}]},
        {"name": "Refrain", "shots": [
            {"t_start": 4, "t_end": 9, "description": "JJ danse, plan large", "framing": "WS", "motion": "high",
             "characters": ["jj"]},
            {"t_start": 9, "t_end": 12, "description": "Micro sur pied", "framing": "ECU", "motion": "static",
             "characters": []}]},
    ]}
    f = tmp_path / "shots.json"
    f.write_text(json.dumps(dec), encoding="utf-8")
    assert run("shots", "import", "premier-clip", f) == 0
    blocks = production.decoupage(conn, "premier-clip")
    assert [b["name"] for b in blocks] == ["Couplet", "Refrain"] and [len(b["shots"]) for b in blocks] == [1, 2]
    production.set_stage(conn, "premier-clip", "decoupage_review")
    production.review_decoupage(conn, "premier-clip", "approve")
    ids = [r["id"] for r in conn.execute("SELECT id FROM shots ORDER BY num")]

    # visuels draft
    for sid in ids:
        assert run("shot", "set", sid, "--image-prompt", "photo of JJ, 85mm") == 0
        assert run("gen", "image", sid) == 0
    worker.tick(conn, wake=False)
    assert {r["status"] for r in conn.execute("SELECT status FROM shots")} == {"image_qc"}
    for sid in ids:
        assert run("qc", "pass", sid) == 0
    assert production.approve_all(conn, "premier-clip", "images", blocks[1]["id"]) == 2
    assert db.get_shot(conn, ids[0])["status"] == "image_review"
    production.approve_all(conn, "premier-clip", "images")

    # visuels HD : automatiques, puis contrôle de fidélité
    worker.tick(conn, wake=False)   # lance les HD
    worker.tick(conn, wake=False)   # récupère les HD
    assert {r["status"] for r in conn.execute("SELECT status FROM shots")} == {"hd_qc"}
    work = production.absp(db.latest_asset(conn, ids[0], "image")["path"])
    hd = production.absp(db.latest_asset(conn, ids[0], "image_hd")["path"])
    assert work.is_file() and hd.is_file() and work != hd
    assert run("qc", "pass", ids[0]) == 0
    assert run("qc", "pass", ids[2]) == 0
    # la HD du plan 2 est refusée deux fois : Michael tranche
    assert run("qc", "fail", ids[1], "--note", "boucles lissées") == 0
    assert db.get_shot(conn, ids[1])["status"] == "hd_todo"
    worker.tick(conn, wake=False)
    worker.tick(conn, wake=False)
    second = db.latest_asset(conn, ids[1], "image_hd")
    assert second["model_key"] == "seedvr-image"   # deuxième essai avec l'autre outil
    assert run("qc", "fail", ids[1], "--note", "toujours lissées") == 0
    assert db.get_shot(conn, ids[1])["status"] == "hd_review"
    assert production.review_shot(conn, ids[1], "use_work_image") == "prompt_todo"
    assert production.keyframe_for_video(conn, ids[1])["kind"] == "image"
    assert production.keyframe_for_video(conn, ids[0])["kind"] == "image_hd"

    # plan vidéo : routeur + prompteur, puis Michael valide (ou change de modèle) avant toute dépense
    with pytest.raises(production.ProductionError):
        production.submit_video_plan(conn, ids[0])
    for sid in ids:
        assert run("route", sid, "--apply") == 0
        assert run("shot", "set", sid, "--video-prompt", "she moves", "--negative-prompt", "blur") == 0
        assert run("shot", "submit", sid) == 0
    tiers = [r["tier"] for r in conn.execute("SELECT tier FROM shots ORDER BY num")]
    assert tiers == ["eco", "premium", "eco"]
    assert {r["status"] for r in conn.execute("SELECT status FROM shots")} == {"video_review"}
    spent = db.clip_cost(conn, "premier-clip")
    view = production.shot_view(conn, db.get_shot(conn, ids[1]))
    assert {o["key"] for o in view["model_options"]} >= {"wan-3", "kling-3-standard", "seedance-2"}
    production.choose_model(conn, ids[1], "kling-3-standard")
    assert db.get_shot(conn, ids[1])["route_reason"] == "Choisi par Michael"
    production.edit_video_prompt(conn, ids[1], "she spins on the beat")
    worker.tick(conn, wake=False)
    assert db.clip_cost(conn, "premier-clip") == spent   # rien n'est parti
    production.approve_all(conn, "premier-clip", "videoplan")

    # vidéos draft lancées par le worker
    worker.tick(conn, wake=False)
    worker.tick(conn, wake=False)
    for sid in ids:
        assert run("qc", "frames", sid) == 0
        assert run("qc", "pass", sid) == 0
    assert db.latest_asset(conn, ids[1], "draft")["prompt"] == "she spins on the beat"

    # retour de Michael sur la vidéo du plan 2 -> prompteur -> nouveau plan vidéo à valider
    assert production.review_shot(conn, ids[1], "change", "Le tour est trop lent") == "change_requested"
    rv = conn.execute("SELECT id FROM reviews WHERE handled=0").fetchone()["id"]
    assert run("review", "handle", rv, "--route", "prompteur") == 0
    assert run("shot", "submit", ids[1]) == 0
    production.review_shot(conn, ids[1], "approve")
    worker.tick(conn, wake=False)
    worker.tick(conn, wake=False)
    assert run("qc", "pass", ids[1]) == 0
    assert db.latest_asset(conn, ids[1], "draft")["version"] == 2

    production.approve_all(conn, "premier-clip", "drafts")
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


def test_unplugged_provider_refused(studio, tmp_path):
    run("init")
    conn = db.connect()
    assert [p["key"] for p in routing.providers() if p["usable"]] == ["fal"]
    production.create_clip(conn, "Fournisseurs", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "fournisseurs", [{"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    sid = conn.execute("SELECT id FROM shots").fetchone()["id"]
    conn.execute("UPDATE shots SET status='video_review', model_key='wan-3', video_prompt='x' WHERE id=?", (sid,))
    cfg = routing.models_cfg()
    cfg["models"]["veo-test"] = {"kind": "video", "provider": "google", "label": "Veo", "endpoint": "x",
                                 "output": "video.url", "price": {"per_second": 0.5}, "durations": [4, 8]}
    try:
        with pytest.raises(production.ProductionError):
            production.choose_model(conn, sid, "veo-test")
        opts = {o["key"]: o for o in routing.model_options(db.get_shot(conn, sid))}
        assert opts["veo-test"]["usable"] is False and opts["wan-3"]["usable"] is True
    finally:
        cfg["models"].pop("veo-test")


def test_migration_from_v1(studio, tmp_path):
    """Une base créée avec le premier schéma passe au schéma 2 sans perte."""
    import sqlite3
    path = studio["root"] / "riot.db"
    old = sqlite3.connect(path)
    old.executescript("""
    CREATE TABLE clips (slug TEXT PRIMARY KEY, title TEXT NOT NULL, dir TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'script',
      song_path TEXT, vocals_path TEXT, script_path TEXT, bpm REAL, duration_s REAL, aspect_ratio TEXT NOT NULL DEFAULT '16:9',
      budget_usd REAL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE shots (id INTEGER PRIMARY KEY, clip_slug TEXT NOT NULL REFERENCES clips(slug), num INTEGER NOT NULL,
      section TEXT, t_start REAL NOT NULL, t_end REAL NOT NULL, description TEXT NOT NULL, framing TEXT, motion TEXT,
      camera TEXT, characters TEXT NOT NULL DEFAULT '[]', singing INTEGER NOT NULL DEFAULT 0, tier TEXT, model_key TEXT,
      seed INTEGER, image_prompt TEXT, video_prompt TEXT, negative_prompt TEXT, status TEXT NOT NULL DEFAULT 'image_todo',
      qc_retries INTEGER NOT NULL DEFAULT 0, notes TEXT, updated_at TEXT NOT NULL, UNIQUE (clip_slug, num));
    CREATE TABLE assets (id INTEGER PRIMARY KEY, shot_id INTEGER NOT NULL REFERENCES shots(id),
      kind TEXT NOT NULL CHECK (kind IN ('image','draft','final','lipsync')), version INTEGER NOT NULL, path TEXT,
      remote_url TEXT, prompt TEXT, model_key TEXT, seed INTEGER, params TEXT, cost_usd REAL NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'generating', error TEXT, created_at TEXT NOT NULL);
    CREATE TABLE reviews (id INTEGER PRIMARY KEY, clip_slug TEXT NOT NULL, shot_id INTEGER, asset_id INTEGER,
      gate TEXT NOT NULL CHECK (gate IN ('decoupage','images','drafts','finals','casting')),
      decision TEXT NOT NULL CHECK (decision IN ('approve','change')), comment TEXT, route TEXT,
      handled INTEGER NOT NULL DEFAULT 0, handled_note TEXT, created_at TEXT NOT NULL);
    CREATE TABLE characters (slug TEXT PRIMARY KEY, name TEXT NOT NULL, notes TEXT, canon_version INTEGER, created_at TEXT NOT NULL);
    CREATE TABLE character_versions (id INTEGER PRIMARY KEY, character_slug TEXT NOT NULL REFERENCES characters(slug),
      version INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft', dir TEXT NOT NULL, notes TEXT, created_at TEXT NOT NULL);
    CREATE TABLE character_assets (id INTEGER PRIMARY KEY, version_id INTEGER NOT NULL, kind TEXT NOT NULL, label TEXT,
      path TEXT, remote_url TEXT, prompt TEXT, model_key TEXT, cost_usd REAL NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'proposed', error TEXT, created_at TEXT NOT NULL);
    INSERT INTO clips VALUES ('ancien','Ancien','clips/ancien','production',NULL,NULL,'clips/ancien/script/script.md',NULL,NULL,'16:9',80,'t','t');
    INSERT INTO shots (clip_slug,num,t_start,t_end,description,status,updated_at) VALUES ('ancien',1,0,4,'plan','draft_review','t');
    INSERT INTO assets (shot_id,kind,version,status,cost_usd,created_at) VALUES (1,'draft',1,'ready',0.5,'t');
    INSERT INTO reviews (clip_slug,gate,decision,created_at) VALUES ('ancien','images','approve','t');
    PRAGMA user_version=1;
    """)
    old.commit()
    old.close()
    conn = db.connect()
    db.init_db(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert db.get_clip(conn, "ancien")["brief_ready"] == 1
    assert db.clip_cost(conn, "ancien") == 0.5
    conn.execute("INSERT INTO assets (shot_id,kind,version,status,created_at) VALUES (1,'image_hd',1,'ready','t')")
    conn.execute("INSERT INTO reviews (clip_slug,gate,decision,created_at) VALUES ('ancien','videoplan','approve','t')")
    snap = production.clip_snapshot(conn, "ancien")
    assert snap["blocks"][0]["name"] == "Sans bloc"


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


def test_canon_hd_flow(studio, tmp_path):
    """Michael dépose le brouillon, la HD part seule, il compare, valide, écrit ses instructions, lance le pack."""
    import subprocess
    run("init")
    conn = db.connect()
    ch = production.new_character(conn, "Nova")
    assert ch["slug"] == "nova" and ch["versions"][0]["status"] == "draft"
    img = tmp_path / "brouillon.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=300x400",
                    "-frames:v", "1", str(img)], check=True)
    with pytest.raises(production.ProductionError):
        production.request_pack(conn, "nova", 1)
    production.upload_canon_draft(conn, "nova", 1, img)
    worker.tick(conn, wake=False)
    hd = conn.execute("SELECT * FROM character_assets WHERE kind='canon' AND parent_id IS NOT NULL").fetchone()
    assert hd["status"] == "proposed" and hd["model_key"] == "topaz-image-hf"
    production.review_canon_hd(conn, hd["id"], "redo", "les yeux ont changé")
    worker.tick(conn, wake=False)
    hd2 = conn.execute("SELECT * FROM character_assets WHERE kind='canon' AND status='proposed'").fetchone()
    assert hd2["model_key"] == "seedvr-image"
    production.review_canon_hd(conn, hd2["id"], "approve")
    v = production.character_version(conn, "nova", 1)
    assert production.absp(v["dir"]).joinpath("canon.png").is_file()
    with pytest.raises(production.ProductionError):
        production.request_pack(conn, "nova", 1)   # pas d'instructions
    production.set_instructions(conn, "nova", 1, "turnaround 5 angles\n3 expressions")
    production.request_pack(conn, "nova", 1)
    assert [n["slug"] for n in production.characters_needing_agent(conn)] == ["nova"]
    res = production.launch_character_asset(conn, "nova", 1, "turnaround", "face", "turnaround of Nova")
    assert res["refs"][0].endswith("canon.png")
    run("character", "pack-done", "nova", "--version", "1")
    assert production.characters_needing_agent(conn) == []
    production.validate_character_version(conn, "nova", 1)


def test_use_draft_as_canon(studio, tmp_path):
    import subprocess
    run("init")
    conn = db.connect()
    production.new_character(conn, "Kai")
    img = tmp_path / "k.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=300x400",
                    "-frames:v", "1", str(img)], check=True)
    production.upload_canon_draft(conn, "kai", 1, img)
    worker.tick(conn, wake=False)
    hd = conn.execute("SELECT * FROM character_assets WHERE kind='canon' AND status='proposed'").fetchone()
    production.review_canon_hd(conn, hd["id"], "use_draft")
    canon = conn.execute("SELECT * FROM character_assets WHERE kind='canon' AND status='kept'").fetchone()
    assert canon["path"].endswith("canon.jpg")
