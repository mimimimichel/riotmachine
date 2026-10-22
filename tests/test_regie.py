"""La régie : lecture, décisions de Michael, création de clip, fichiers protégés."""

from fastapi.testclient import TestClient

from riotmachine import cli, db, demo


def test_regie_flow(studio):
    cli.main(["init"])
    conn = db.connect()
    demo.create(conn)
    from riotmachine.regie.app import app
    client = TestClient(app)

    ov = client.get("/api/overview").json()
    assert ov["clips"][0]["slug"] == demo.SLUG
    assert ov["characters"][0]["canon_path"].endswith("canon.jpg")

    clip = client.get(f"/api/clips/{demo.SLUG}").json()
    by_num = {s["num"]: s for s in clip["shots"]}
    assert [b["name"] for b in clip["blocks"]][:2] == ["Intro", "Couplet 1"]
    assert by_num[1]["status"] == "done"
    assert by_num[9]["status"] == "change_requested"
    assert by_num[13]["status"] == "hd_review"
    assert by_num[11]["status"] == "video_review" and by_num[11]["model_options"]
    assert {f["kind"] for f in clip["files"]} >= {"song", "dossier", "lyrics"}
    assert client.get(f"/api/clips/{demo.SLUG}/waveform").json()["peaks"]

    # un retour sans commentaire est refusé
    sid = by_num[19]["id"]
    r = client.post(f"/api/shots/{sid}/review", json={"decision": "change", "comment": " "})
    assert r.status_code == 400
    r = client.post(f"/api/shots/{sid}/review", json={"decision": "change", "comment": "Plus de lumière"})
    assert r.json()["status"] == "change_requested"
    r = client.post(f"/api/clips/{demo.SLUG}/approve-all/finals")
    assert r.json()["approved"] == 3
    # plan vidéo : changer de modèle puis valider
    sid = by_num[12]["id"]
    assert client.post(f"/api/shots/{sid}/model", json={"model_key": "kling-3-standard"}).status_code == 200
    assert client.post(f"/api/shots/{sid}/video-prompt", json={"text": "slow push in"}).status_code == 200
    assert client.post(f"/api/shots/{sid}/review", json={"decision": "approve"}).json()["status"] == "draft_todo"
    # HD : partir du visuel draft
    r = client.post(f"/api/shots/{by_num[13]['id']}/review", json={"decision": "use_work_image"})
    assert r.json()["status"] == "prompt_todo"

    # fichiers : les médias oui, la base non
    assert client.get("/media/characters/jj/v1/canon.jpg").status_code == 200
    assert client.get("/media/riot.db").status_code == 404
    assert client.get("/media/../.env").status_code == 404

    # nouveau clip depuis le formulaire
    with open(studio["song"], "rb") as fh:
        song = fh.read()
    r = client.post("/api/clips", data={"title": "Depuis la régie", "pitch": "Un pitch", "characters": "jj",
                                        "lyrics_text": "La la la"},
                    files=[("song", ("morceau.mp3", song, "audio/mpeg")),
                           ("dossier", ("DA.md", b"# DA", "text/markdown")),
                           ("dossier", ("plans.txt", b"Plan 1 0:00-0:04", "text/plain"))])
    assert r.status_code == 200, r.text
    c = client.get("/api/clips/depuis-la-regie").json()
    assert c["stage"] == "script" and c["pitch"] == "Un pitch" and not c["brief_ready"]
    assert sorted(f["kind"] for f in c["files"]) == ["dossier", "dossier", "lyrics", "song"]
    r = client.post("/api/clips/depuis-la-regie/decoupage-edit", json={"blocks": [
        {"name": "Intro", "shots": [{"t_start": 0, "t_end": 4, "description": "JJ", "characters": ["jj"]}]}]})
    assert r.json()["shots"] == 1
    assert client.post("/api/clips/depuis-la-regie/submit-brief").status_code == 200
    fid = c["files"][0]["id"]
    assert client.delete(f"/api/files/{fid}").status_code in (200, 400)

    # personnages : création, brouillon de canon
    assert client.post("/api/characters", json={"name": "Nova"}).json()["slug"] == "nova"
    png = studio["root"] / "characters" / "jj" / "v1" / "canon.jpg"
    r = client.post("/api/characters/nova/versions/1/canon-draft", files={"file": ("b.jpg", png.read_bytes(), "image/jpeg")})
    assert r.status_code == 200, r.text
    assert client.post("/api/characters/nova/versions/1/instructions", json={"text": "5 angles"}).status_code == 200
    assert client.post("/api/characters/nova/versions/1/pack").status_code == 400   # canon HD pas encore validée

    assert client.get("/").status_code == 200


def test_token_guard(studio, monkeypatch):
    monkeypatch.setenv("RIOT_REGIE_TOKEN", "secret")
    from riotmachine import settings
    settings.reset_caches()
    from riotmachine.regie.app import app
    client = TestClient(app)
    assert client.get("/api/overview").status_code == 401
    r = client.get("/?token=secret", follow_redirects=False)
    assert r.status_code == 307 and "riot_token" in r.headers["set-cookie"]
    assert client.get("/api/overview", headers={"Authorization": "Bearer secret"}).status_code == 200
