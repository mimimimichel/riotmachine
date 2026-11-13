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
    production.set_visual_hd(conn, "premier-clip", True)   # ce parcours teste aussi le visuel HD (facultatif)
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
    # R-F7 : une HD contrôlée attend la validation de Michael
    assert db.get_shot(conn, ids[0])["status"] == "hd_review"
    assert production.review_shot(conn, ids[0], "approve") == "prompt_todo"
    assert production.review_shot(conn, ids[2], "approve") == "prompt_todo"
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
    # en simulation, tout fournisseur branché dans le code est utilisable ; un fournisseur inconnu, jamais
    assert {p["key"] for p in routing.providers() if p["usable"]} == routing.IMPLEMENTED_PROVIDERS
    production.create_clip(conn, "Fournisseurs", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "fournisseurs", [{"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    sid = conn.execute("SELECT id FROM shots").fetchone()["id"]
    conn.execute("UPDATE shots SET status='video_review', model_key='wan-3', video_prompt='x' WHERE id=?", (sid,))
    cfg = routing.models_cfg()
    cfg["providers"]["luma"] = {"label": "Luma", "env": ["LUMA_KEY"]}
    cfg["models"]["veo-test"] = {"kind": "video", "provider": "luma", "label": "Ray", "endpoint": "x",
                                 "output": "video.url", "price": {"per_second": 0.5}, "durations": [4, 8]}
    try:
        with pytest.raises(production.ProductionError):
            production.choose_model(conn, sid, "veo-test")
        opts = {o["key"]: o for o in routing.model_options(db.get_shot(conn, sid))}
        assert opts["veo-test"]["usable"] is False and opts["wan-3"]["usable"] is True
    finally:
        cfg["models"].pop("veo-test")
        cfg["providers"].pop("luma")


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
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    assert db.get_clip(conn, "ancien")["brief_ready"] == 1
    assert db.clip_cost(conn, "ancien") == 0.5
    conn.execute("INSERT INTO assets (shot_id,kind,version,status,created_at) VALUES (1,'image_hd',1,'ready','t')")
    conn.execute("INSERT INTO reviews (clip_slug,gate,decision,created_at) VALUES ('ancien','videoplan','approve','t')")
    snap = production.clip_snapshot(conn, "ancien")
    assert snap["blocks"][0]["name"] == "Sans bloc"


def test_budget_blocks(studio, tmp_path, monkeypatch):
    monkeypatch.setattr(production.credits, "funding_for", lambda *a: "cash")   # pas de crédits gratuits
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Petit budget", song=studio["song"], characters=["jj"], budget_usd=0.01)
    production.import_shots(conn, "petit-budget", [
        {"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    conn.execute("UPDATE blocks SET validated=1 WHERE clip_slug=?", ("petit-budget",))   # bloc validé : en production
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
    assert hd["status"] == "proposed" and hd["model_key"] == "nano-banana-pro"   # jamais Google pour une image
    production.review_canon_hd(conn, hd["id"], "redo", "les yeux ont changé")
    worker.tick(conn, wake=False)
    hd2 = conn.execute("SELECT * FROM character_assets WHERE kind='canon' AND status='proposed'").fetchone()
    assert hd2["model_key"] == "nano-banana-pro"
    assert conn.execute("SELECT status FROM character_assets WHERE id=?", (hd["id"],)).fetchone()[0] == "rejected"
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
    canon = conn.execute("SELECT * FROM character_assets WHERE kind='canon' AND status='kept' AND path LIKE 'characters/kai/%'").fetchone()
    assert canon["path"].endswith("canon.jpg")


def test_spend_needs_approval(studio, monkeypatch):
    """Hors simulation, une génération d'image attend l'accord de Michael, puis le worker la lance."""
    from riotmachine import providers as prov
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Accord", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "accord", [{"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    conn.execute("UPDATE blocks SET validated=1 WHERE clip_slug=?", ("accord",))   # bloc validé : en production
    sid = conn.execute("SELECT id FROM shots").fetchone()["id"]
    production.update_shot(conn, sid, image_prompt="x")
    monkeypatch.setattr(prov, "simulated", lambda provider="fal": False)
    monkeypatch.setattr(routing, "provider_has_key", lambda key: True)   # fal branché pour ce test
    real_submit = prov.submit
    calls = []
    monkeypatch.setattr(prov, "submit", lambda *a, **k: calls.append(1) or real_submit(*a, **{**k, "force_mock": True}))
    res = production.launch_image(conn, sid, model="nano-banana-2")      # modèle payant choisi par Michael
    assert res["status"] == "pending" and res["est_usd"] > 0 and not calls
    assert production.launch_image(conn, sid, model="nano-banana-2")["spend_request"] == res["spend_request"]   # pas de doublon
    assert production.needs_agent(conn, "accord")["reasons"] == [] or "image_todo" not in str(
        production.needs_agent(conn, "accord")["reasons"])
    production.decide_spend(conn, [res["spend_request"]], "approve")
    assert production.run_approved_spend(conn) == 1 and calls
    assert db.get_shot(conn, sid)["status"] == "image_gen"


def test_elements_flow(studio, tmp_path):
    """Décors : fiche, image de Michael, lien aux plans ; le visuel attend une référence gardée."""
    import subprocess
    from riotmachine import elements
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Decors", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "decors", [{"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]},
                                             {"t_start": 4, "t_end": 8, "description": "y", "characters": []}])
    conn.execute("UPDATE blocks SET validated=1 WHERE clip_slug=?", ("decors",))   # bloc validé : en production
    ids = [r["id"] for r in conn.execute("SELECT id FROM shots ORDER BY num")]
    e = elements.create(conn, "decors", "decor", "Jardin de JJ", "Terrasse en dalles", ["vide au retour"])
    elements.link(conn, ids, e["id"], "vide au retour")
    production.update_shot(conn, ids[0], image_prompt="x")
    assert elements.missing_refs(conn, ids[0]) == ["Jardin de JJ"]   # pas bloquant : le visuel partirait sans
    img = tmp_path / "j.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=green:s=320x240",
                    "-frames:v", "1", str(img)], check=True)
    elements.add_image(conn, e["id"], img)               # image de départ : sert de référence en attendant la HD
    assert elements.missing_refs(conn, ids[0]) == []
    ce = elements.clip_elements(conn, "decors")[0]
    assert ce["step"] == "hd_todo" and "reference image" in ce["prompt_text"] and ce["prompt_status"] == "requested"
    assert any("image(s) de départ à regarder" in r for r in production.needs_agent(conn, "decors")["reasons"])
    elements.describe(conn, e["id"], "Photorealistic high-definition photograph of a green garden.", "Jardin vert")
    ce = elements.clip_elements(conn, "decors")[0]
    assert ce["prompt_by"] == "agent" and ce["prompt_text"].startswith("Photorealistic") and ce["prompt_status"] == "none"
    elements.set_prompt(conn, e["id"], "Mon prompt à moi")
    res = elements.launch_image(conn, e["id"], "vide au retour", approved=True)
    job = conn.execute("SELECT * FROM jobs WHERE target_table='element_images' AND target_id=?",
                       (res["image_id"],)).fetchone()
    assert job is not None
    worker.tick(conn, wake=False)
    gen = conn.execute("SELECT status, prompt FROM element_images WHERE id=?", (res["image_id"],)).fetchone()
    assert gen["status"] == "proposed" and gen["prompt"].startswith("Mon prompt à moi")
    elements.pick(conn, res["image_id"], "keep")
    refs, text = elements.shot_context(conn, ids[0])
    assert refs and "Jardin de JJ" in text and "vide au retour" in text and "@jardin-de-jj" in text
    production.launch_image(conn, ids[0])               # simulation : part directement
    assert len(elements.clip_elements(conn, "decors")[0]["shots"]) == 2
    # une image HD déposée telle quelle sert directement de référence
    e2 = elements.create(conn, "decors", "objet", "Vélo", "Vélo rouge")
    elements.add_image(conn, e2["id"], img, role="hd")
    assert elements.clip_elements(conn, "decors")[1]["step"] == "done"
    # @slug dans un plan relie l'élément
    production.update_shot(conn, ids[1], description="Le @velo contre le mur")
    assert [x["slug"] for x in elements.for_shot(conn, ids[1])] == ["jardin-de-jj", "velo"]


def test_element_free_drafts(studio, tmp_path, monkeypatch):
    """Inspirations + texte -> brouillons gratuits ; le brouillon gardé devient l'image de départ."""
    import shutil
    import subprocess
    from riotmachine import elements
    from riotmachine.providers import cloudflare
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Salon", song=studio["song"], characters=["jj"])
    e = elements.create(conn, "salon", "decor", "Salon", "")
    img = tmp_path / "i.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x240",
                    "-frames:v", "1", str(img)], check=True)
    elements.add_image(conn, e["id"], img, role="inspi")
    elements.add_image(conn, e["id"], img, role="inspi")
    assert elements.clip_elements(conn, "salon")[0]["step"] == "start"     # une inspiration n'est pas une image de départ
    seen = {}

    def fake(prompt, images, dest, **kw):
        seen["prompt"], seen["n"] = prompt, len(images)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(img, dest)
        return dest
    monkeypatch.setattr(elements, "draft_backends", lambda: [("cloudflare", "klein-9b", "test")])
    monkeypatch.setattr(routing, "provider_has_key", lambda key: True)
    monkeypatch.setattr(cloudflare, "generate", fake)
    r = elements.launch_drafts(conn, e["id"], "le canapé vert de la 2e image", 2, background=False,
                               backend="cloudflare:klein-9b")
    assert len(r["images"]) == 2 and r["cost_usd"] == 0
    assert seen["n"] == 2 and "canapé vert" in seen["prompt"]
    ce = elements.clip_elements(conn, "salon")[0]
    assert ce["step"] == "draft_choose" and ce["brief"] == "le canapé vert de la 2e image"
    elements.pick(conn, r["images"][0], "keep")
    ce = elements.clip_elements(conn, "salon")[0]
    assert ce["step"] == "hd_todo" and ce["prompt_status"] == "requested" and len(ce["draft_paths"]) == 1


def test_no_google_credits_for_images(studio):
    """Règle de Michael : les crédits Google Cloud sont réservés à la vidéo."""
    from riotmachine import providers
    from riotmachine.providers._http import ProviderError
    for role in ("storyboard", "casting", "canon_hd", "upscale", "upscale_fallback"):
        for key in routing.models_cfg()["image"][role]:
            assert routing.model(key).get("provider") != "vertex", (role, key)
    monkeypatch_env = providers.simulated
    providers.simulated = lambda p="fal": False
    try:
        with pytest.raises(ProviderError):
            providers.submit({"provider": "vertex", "label": "x"}, {}, kind="image")
    finally:
        providers.simulated = monkeypatch_env


def test_provider_keys_admin(studio, tmp_path, monkeypatch):
    """Régie : ajouter, changer, retirer une clé, désactiver un fournisseur ; la clé n'est jamais renvoyée."""
    import os
    from riotmachine import provider_keys
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_CHAT_ID=42\n")
    monkeypatch.setattr(provider_keys, "ENV_FILE", env)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    provider_keys.set_key("cloudflare", "CLOUDFLARE_API_TOKEN", "abcdefgh12345678")
    assert "CLOUDFLARE_API_TOKEN=abcdefgh12345678" in env.read_text() and "TELEGRAM_CHAT_ID=42" in env.read_text()
    assert oct(env.stat().st_mode)[-3:] == "600"
    assert provider_keys.masked("CLOUDFLARE_API_TOKEN") == "••••5678"
    with pytest.raises(provider_keys.KeyError_):
        provider_keys.set_key("cloudflare", "TELEGRAM_CHAT_ID", "x")      # seulement les clés du fournisseur
    provider_keys.set_key("cloudflare", "CLOUDFLARE_API_TOKEN", "zzzzzzzz99990000")
    assert env.read_text().count("CLOUDFLARE_API_TOKEN=") == 1
    provider_keys.set_enabled("cloudflare", False)
    assert not next(p for p in routing.providers() if p["key"] == "cloudflare")["enabled"]
    provider_keys.set_enabled("cloudflare", True)
    provider_keys.remove_key("cloudflare", "CLOUDFLARE_API_TOKEN")
    assert "CLOUDFLARE_API_TOKEN" not in env.read_text() and not os.environ.get("CLOUDFLARE_API_TOKEN")
    assert "RIOT_DISABLED_PROVIDERS" not in env.read_text()


def test_character_pack_and_mention(studio, tmp_path):
    """Michael dépose ses images dans le pack (telles quelles) ; @slug d'un personnage le caste et l'ajoute au plan."""
    import subprocess
    run("init")
    conn = db.connect()
    production.new_character(conn, "Rex")
    img = tmp_path / "sheet.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=orange:s=320x240",
                    "-frames:v", "1", str(img)], check=True)
    production.add_pack_images(conn, "rex", 1, "sheet", [img])
    production.add_pack_images(conn, "rex", 1, "canon", [img])
    refs = production.character_refs(conn, "rex", 1)
    canon = conn.execute("SELECT a.path FROM character_assets a JOIN character_versions v ON v.id=a.version_id "
                         "WHERE v.character_slug='rex' AND a.kind='canon' AND a.status='kept'").fetchall()
    assert len(canon) == 1 and str(refs[0]).endswith(canon[0]["path"].split("/")[-1])   # une seule canon, en tête
    assert conn.execute("SELECT COUNT(*) FROM character_assets a JOIN character_versions v ON v.id=a.version_id "
                        "WHERE v.character_slug='rex' AND a.status='kept'").fetchone()[0] == 2   # pas de doublon
    production.create_clip(conn, "Chien", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "chien", [{"t_start": 0, "t_end": 4, "description": "@rex aboie", "characters": []}])
    sh = conn.execute("SELECT * FROM shots WHERE clip_slug='chien'").fetchone()
    assert "rex" in json.loads(sh["characters"])
    assert any(c["character_slug"] == "rex" for c in db.casting_for_clip(conn, "chien"))
    assert any(c["slug"] == "rex" for c in production.clip_snapshot(conn, "chien")["characters_all"])


def test_validate_block_by_block(studio):
    """Un bloc validé part en production sans attendre les autres, et ne se modifie plus."""
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Blocs", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "blocs", {"blocks": [
        {"name": "Intro", "shots": [{"t_start": 0, "t_end": 4, "description": "a", "characters": []}]},
        {"name": "Couplet", "shots": [{"t_start": 4, "t_end": 8, "description": "b", "characters": []}]}]})
    production.set_stage(conn, "blocs", "decoupage_review")
    b1, b2 = [r["id"] for r in conn.execute("SELECT id FROM blocks WHERE clip_slug='blocs' ORDER BY num")]
    s1, s2 = [r["id"] for r in conn.execute("SELECT id FROM shots WHERE clip_slug='blocs' ORDER BY num")]
    with pytest.raises(production.ProductionError):
        production.validate_block(conn, b1)                 # le plan n'est pas encore validé
    production.set_cut_ok(conn, s1, True)
    assert production.validate_block(conn, b1)["clip_in_production"] is False
    assert any("références du bloc 1" in r for r in production.needs_agent(conn, "blocs")["reasons"])
    production.shot_ref(conn, s1, "jj")                       # le scripte relie sans toucher au texte
    assert "jj" in db.get_shot(conn, s1)["characters"]
    production.block_refs_checked(conn, "blocs", 1)
    assert not any("références du bloc" in r for r in production.needs_agent(conn, "blocs")["reasons"])
    snap = production.clip_snapshot(conn, "blocs", compact=True)
    assert [s["en_production"] for s in snap["shots"]] == [True, False]
    assert db.get_clip(conn, "blocs")["stage"] == "decoupage_review"
    with pytest.raises(production.ProductionError):     # un bloc validé ne disparaît pas du découpage
        production.import_shots(conn, "blocs", {"blocks": [
            {"name": "Couplet", "shots": [{"id": s2, "t_start": 4, "t_end": 8, "description": "b2", "characters": []}]}]})
    production.import_shots(conn, "blocs", {"blocks": [
        {"name": "Intro", "shots": [{"id": s1, "t_start": 0, "t_end": 4, "description": "changé", "characters": []}]},
        {"name": "Couplet", "shots": [{"id": s2, "t_start": 4, "t_end": 8, "description": "b2", "characters": []}]}]})
    assert db.get_shot(conn, s1)["description"] == "a"     # le plan du bloc validé n'a pas bougé
    production.set_cut_ok(conn, s2, True)
    assert production.validate_block(conn, b2)["clip_in_production"] is True
    assert db.get_clip(conn, "blocs")["stage"] == "production"


def test_looks_reusable_and_wearer(studio):
    """Une tenue se cite partout ; changer son porteur réécrit les plans qui la citent."""
    run("init")
    conn = db.connect()
    production.new_character(conn, "Max")
    production.create_clip(conn, "Un", song=studio["song"], characters=["jj"])
    production.create_look(conn, "jj", "Tailleur test", "blazer bleu", clip_slug="un")
    with pytest.raises(production.ProductionError):
        production.create_look(conn, "jj", "tailleur test")                 # pas de doublon pour un même porteur
    production.create_clip(conn, "Deux", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "deux", [{"t_start": 0, "t_end": 4, "description": "elle entre en @jj-tailleur-test", "characters": []}])
    sh = conn.execute("SELECT * FROM shots WHERE clip_slug='deux'").fetchone()
    assert json.loads(sh["looks"]) == {"jj": "tailleur-test"} and "jj" in json.loads(sh["characters"])
    assert [l["slug"] for l in production.clip_looks(conn, "deux")] == ["jj-tailleur-test"]   # reprise sans rien rattacher
    assert production.move_look(conn, "jj", "tailleur-test", "max") == "max-tailleur-test"
    sh = conn.execute("SELECT * FROM shots WHERE clip_slug='deux'").fetchone()
    assert "@max-tailleur-test" in sh["description"] and json.loads(sh["looks"]) == {"max": "tailleur-test"}


def test_canon_pair_flow(studio, tmp_path, monkeypatch):
    """La canon en deux images : la tête d'abord, puis le corps à partir d'elle, choisis par Michael."""
    import shutil
    import subprocess
    from riotmachine import elements
    run("init")
    conn = db.connect()
    production.new_character(conn, "Rox")
    img = tmp_path / "r.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=tan:s=320x240",
                    "-frames:v", "1", str(img)], check=True)
    production.request_canon(conn, "rox", 1, "regard doux")
    assert any(n["what"] == "canon demandée" for n in production.characters_needing_agent(conn))
    monkeypatch.setattr(elements, "draft_backends", lambda: [("cloudflare", "klein-9b", "test")])
    monkeypatch.setattr(elements, "_draft_one", lambda b, p, refs, out, w, h: (out.parent.mkdir(parents=True, exist_ok=True), shutil.copy(img, out)))
    monkeypatch.setattr(production.routing, "provider_usable", lambda key: key == "cloudflare")
    monkeypatch.setattr(production.providers, "simulated", lambda provider="fal": False)
    import threading
    monkeypatch.setattr(threading, "Thread", lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    pend = production.launch_character_asset(conn, "rox", 1, "canon", "tete", "portrait")
    assert pend["status"] == "pending" and pend["est_usd"] == 0                # même gratuit : accord de Michael d'abord
    r = production.launch_character_asset(conn, "rox", 1, "canon", "tete", "portrait", approved=True)
    production.canon_waiting(conn, "rox", 1)
    a = conn.execute("SELECT * FROM character_assets WHERE id=?", (r["asset_id"],)).fetchone()
    assert a["status"] == "proposed" and a["cost_usd"] == 0
    production.make_canon(conn, a["id"], "canon")
    assert production.character_version(conn, "rox", 1)["canon_status"] == "requested"   # le corps est demandé
    r2 = production.launch_character_asset(conn, "rox", 1, "canon_body", "en-pied", "full body", approved=True)
    production.make_canon(conn, r2["asset_id"], "canon_body")
    assert production.character_version(conn, "rox", 1)["canon_status"] == "done"
    kinds = [x[0] for x in conn.execute("SELECT kind FROM character_assets a JOIN character_versions v ON v.id=a.version_id "
                                        "WHERE v.character_slug='rox' AND a.status='kept' ORDER BY a.id")]
    assert kinds == ["canon", "canon_body"]


def test_image_proposals_count(studio, monkeypatch):
    """Michael choisit le nombre de propositions : le coût est multiplié, le plan attend toutes les propositions."""
    from riotmachine import providers as prov
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Nombre", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "nombre", [{"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    conn.execute("UPDATE blocks SET validated=1 WHERE clip_slug=?", ("nombre",))
    sid = conn.execute("SELECT id FROM shots").fetchone()["id"]
    production.update_shot(conn, sid, image_prompt="x")
    monkeypatch.setattr(prov, "simulated", lambda provider="fal": False)
    monkeypatch.setattr(routing, "provider_has_key", lambda key: True)
    real_submit = prov.submit
    calls = []
    monkeypatch.setattr(prov, "submit", lambda *a, **k: calls.append(1) or real_submit(*a, **{**k, "force_mock": True}))
    one = production.launch_image(conn, sid, model="nano-banana-2")    # payant : une seule par défaut
    two = production.launch_image(conn, sid, count=2, model="nano-banana-2")
    assert one["spend_request"] != two["spend_request"]
    assert abs(two["est_usd"] - 2 * one["est_usd"]) < 1e-6
    assert production.launch_image(conn, sid, count=9, model="nano-banana-2")["est_usd"] <= 4 * one["est_usd"] + 1e-6
    production.decide_spend(conn, [two["spend_request"]], "approve")
    production.run_approved_spend(conn)
    assert len(calls) == 2
    gen = conn.execute("SELECT COUNT(*) n FROM assets WHERE shot_id=? AND kind='image' AND status='generating'", (sid,)).fetchone()["n"]
    assert gen == 2 and db.get_shot(conn, sid)["status"] == "image_gen"
    info = production.image_launch_info(db.get_shot(conn, sid))
    assert info["counts"]["payant"] == 1 and info["counts"]["gratuit"] == 3
    jobs = [dict(r) for r in conn.execute("SELECT * FROM jobs WHERE target_table='assets' ORDER BY id")]
    production.on_job_done(conn, jobs[0], {"images": [{"url": "mock://image?label=a"}]})
    assert db.get_shot(conn, sid)["status"] == "image_gen"          # la deuxième proposition est encore en route
    production.on_job_done(conn, jobs[1], {"images": [{"url": "mock://image?label=b"}]})
    ready = conn.execute("SELECT COUNT(*) n FROM assets WHERE shot_id=? AND kind='image' AND status='ready'", (sid,)).fetchone()["n"]
    assert ready == 2 and db.get_shot(conn, sid)["status"] in ("image_qc", "image_review")


def test_change_request_any_step(studio):
    """Michael demande une modif à n'importe quelle étape du visuel : pas d'erreur, l'orchestrateur la reçoit."""
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Modif", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "modif", [{"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    conn.execute("UPDATE blocks SET validated=1 WHERE clip_slug=?", ("modif",))
    sid = conn.execute("SELECT id FROM shots").fetchone()["id"]
    for st in ("image_todo", "image_qc", "image_gen", "prompt_todo"):
        db.set_shot_status(conn, sid, st)
        assert production.review_shot(conn, sid, "change", "réveil sans texte") == "change_requested"
    assert len(production.clip_snapshot(conn, "modif")["pending_reviews"]) == 4


def test_look_reference_sheet(studio, tmp_path, monkeypatch):
    """Tenue : Michael dépose la photo portée, la machine crée la feuille, il la garde, elle part en tête."""
    import shutil as sh
    import subprocess
    from riotmachine import elements, look_sheets
    run("init")
    conn = db.connect()
    production.create_look(conn, "jj", "Essai feuille", "blazer bleu marine")
    photo = tmp_path / "portee.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64", "-frames:v", "1",
                    str(photo)], check=True)
    with pytest.raises(look_sheets.LookError):
        look_sheets.launch_sheet(conn, "jj", "essai-feuille", background=False)      # pas encore de photo
    production.add_look_image(conn, "jj", "essai-feuille", photo)
    monkeypatch.setattr(elements, "draft_backends", lambda: [("huggingface", "kontext-dev", "Kontext"),
                                                             ("cloudflare", "klein-9b", "FLUX.2 klein 9B")])
    seen = {}
    def fake(b, text, inputs, out, w, h):
        assert b[1] != "kontext-dev"                                         # une seule image : écarté
        seen["inputs"], seen["text"] = inputs, text
        out.parent.mkdir(parents=True, exist_ok=True); sh.copy(photo, out)
    monkeypatch.setattr(elements, "_draft_one", fake)
    monkeypatch.setattr(routing, "provider_has_key", lambda key: True)
    res = look_sheets.launch_sheet(conn, "jj", "essai-feuille", count=2, background=False, model="cloudflare:klein-9b")
    assert res["count"] == 2 and "BACK VIEW" in seen["text"] and "blazer bleu marine" in seen["text"]
    assert "IDENTITY" in seen["text"] and "canon" in str(seen["inputs"][0])   # le visage vient de la canon, en image 1
    assert any(p.name == "portee.png" for p in seen["inputs"])
    assert any("feuille-" in p.name and "-face" in p.name for p in seen["inputs"])   # la vue de face guide les autres
    lk = [x for x in production.studio_looks(conn) if x["slug"] == "jj-essai-feuille"][0]
    assert len(lk["sheet_props"]) == 2 and lk["sheet"] is None
    look_sheets.decide(conn, lk["sheet_props"][0]["id"], "keep")
    refs = look_sheets.refs(conn, "jj", "essai-feuille")
    assert "feuilles" in str(refs[0]) and refs[1].name == "portee.png"
    cr = production.character_refs(conn, "jj", 1, "essai-feuille")
    assert "feuilles" in str(cr[1])                                         # canon d'abord, puis la feuille


def test_photo_style_in_prompts(studio):
    """Le style photo du clip part à la fin de chaque prompt d'image ; vide, c'est le style par défaut."""
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Style", song=studio["song"], characters=["jj"])
    clip = db.get_clip(conn, "style")
    assert "no visible pores" in production.with_style("a garden", clip)
    production.set_style(conn, "style", "Moody night look, neon reflections.")
    out = production.with_style("a garden", db.get_clip(conn, "style"))
    assert out.endswith("PHOTO STYLE: Moody night look, neon reflections.")
    assert production.with_style(out, db.get_clip(conn, "style")) == out     # jamais ajouté deux fois


def test_chosen_model_only_and_clear_error(studio, monkeypatch):
    """Le modèle choisi par Michael est le seul essayé ; s'il échoue, l'erreur le nomme et dit quoi faire."""
    from riotmachine import image_models
    from riotmachine.providers import cloudflare, hfspace
    from riotmachine.providers._http import ProviderError
    run("init")
    conn = db.connect()
    production.create_clip(conn, "Choix", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "choix", [{"t_start": 0, "t_end": 4, "description": "x", "characters": ["jj"]}])
    conn.execute("UPDATE blocks SET validated=1 WHERE clip_slug=?", ("choix",))
    sid = conn.execute("SELECT id FROM shots").fetchone()["id"]
    production.update_shot(conn, sid, image_prompt="x")
    monkeypatch.setattr(routing, "provider_has_key", lambda key: True)
    from riotmachine import providers as prov
    monkeypatch.setattr(prov, "simulated", lambda provider="fal": False)
    def quota(*a, **k):
        raise ProviderError("quota gratuit du jour épuisé")
    hf_calls = []
    monkeypatch.setattr(cloudflare, "generate", quota)
    monkeypatch.setattr(hfspace, "generate", lambda *a, **k: hf_calls.append(1))
    o = image_models.options("visuel")
    assert o["default"] == "cloudflare:klein-9b" and o["models"][0]["why"]
    production.launch_image(conn, sid, approved=True, count=2, model="cloudflare:klein-9b")
    shot = db.get_shot(conn, sid)
    assert shot["status"] == "failed" and not hf_calls                       # aucun repli silencieux
    errs = [r["error"] for r in conn.execute("SELECT error FROM assets WHERE shot_id=? AND status='failed'", (sid,))]
    assert len(errs) == 2 and all("FLUX.2 klein 9B" in e and "quota" in e and "autre modèle" in e for e in errs)
    with pytest.raises(production.ProductionError):
        production.launch_image(conn, sid, approved=True, model="modele-inconnu")
