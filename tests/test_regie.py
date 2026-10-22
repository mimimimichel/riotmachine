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
    assert by_num[1]["status"] == "final_review"
    assert by_num[4]["status"] == "change_requested"

    # un retour sans commentaire est refusé
    r = client.post(f"/api/shots/{by_num[5]['id']}/review", json={"decision": "change", "comment": " "})
    assert r.status_code == 400
    r = client.post(f"/api/shots/{by_num[5]['id']}/review", json={"decision": "change", "comment": "Plus de lumière"})
    assert r.json()["status"] == "change_requested"
    r = client.post(f"/api/clips/{demo.SLUG}/approve-all/finals")
    assert r.json()["approved"] == 2

    # fichiers : les médias oui, la base non
    assert client.get("/media/characters/jj/v1/canon.jpg").status_code == 200
    assert client.get("/media/riot.db").status_code == 404
    assert client.get("/media/../.env").status_code == 404

    # nouveau clip depuis le formulaire
    with open(studio["song"], "rb") as fh:
        r = client.post("/api/clips", data={"title": "Depuis la régie", "script": "Un refrain.", "characters": "jj"},
                        files={"song": ("morceau.mp3", fh, "audio/mpeg")})
    assert r.status_code == 200, r.text
    assert client.get("/api/clips/depuis-la-regie").json()["stage"] == "script"

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
