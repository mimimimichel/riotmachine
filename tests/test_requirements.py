"""Un test par exigence livrée de docs/REQUIREMENTS.md, nommé par son identifiant.

`pytest -k r_` liste les exigences couvertes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from riotmachine import db


# --- G. Qualité logicielle ---------------------------------------------------

def test_r_g3_migrations_idempotentes(studio):
    """R-G3 : base au schéma courant, migrations rejouées deux fois sans erreur, sauvegarde présente."""
    backups = studio["root"] / "backups"
    with db.session() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
        applied = [r["version"] for r in conn.execute("SELECT version FROM schema_version ORDER BY version")]
        assert applied[-1] == db.SCHEMA_VERSION
        assert all(v in applied for v in range(db.BASELINE_VERSION, db.SCHEMA_VERSION + 1))
        conn.execute("INSERT INTO clips (slug, title, dir, created_at, updated_at) VALUES ('x','X','clips/x','t','t')")
    # une base neuve n'a rien à sauvegarder
    assert not list(backups.glob("*.db")) if backups.exists() else True

    # on fait passer la base pour une base d'avant les migrations numérotées : tout se rejoue
    raw = sqlite3.connect(studio["root"] / "riot.db")
    raw.execute(f"PRAGMA user_version={db.BASELINE_VERSION}")
    raw.commit()
    raw.close()
    with db.session() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
        assert conn.execute("SELECT count(*) FROM clips").fetchone()[0] == 1
        rows = db.rows(conn.execute("SELECT * FROM schema_version WHERE version>?", (db.BASELINE_VERSION,)).fetchall())
        assert rows and all(r["backup_path"] for r in rows)
    saved = list(backups.glob(f"riot-*-v{db.BASELINE_VERSION}.db"))
    assert len(saved) == 1
    copy = sqlite3.connect(saved[0])
    assert copy.execute("SELECT count(*) FROM clips").fetchone()[0] == 1   # la sauvegarde est une base lisible
    copy.close()

    # deuxième passage au schéma courant : rien ne bouge, pas de nouvelle sauvegarde
    with db.session() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    assert len(list(backups.glob("*.db"))) == 1

    # l'état est lisible pour Michael
    status = db.schema_status(conn=db.connect())
    assert status["version"] == db.SCHEMA_VERSION
    assert status["sauvegardes"] and status["migrations"]


def test_r_g2_hook_et_tests_nommes():
    """R-G2 : hook pre-commit installé, et chaque exigence du CHANGELOG a son test `test_r_<id>_`."""
    import re
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    hook = repo / "deploy" / "hooks" / "pre-commit"
    assert hook.is_file() and hook.stat().st_mode & 0o111, "deploy/hooks/pre-commit manquant ou non exécutable"
    assert "pytest" in hook.read_text()
    installed = repo / ".git" / "hooks" / "pre-commit"
    if (repo / ".git").exists():
        assert installed.exists(), "hook non installé : bash deploy/install-hooks.sh"
        assert installed.resolve() == hook.resolve()
    delivered = set(re.findall(r"\bR-([A-G]\d+)\b", (repo / "CHANGELOG.md").read_text()))
    tests = "\n".join(p.read_text() for p in (repo / "tests").glob("test_*.py"))
    missing = sorted(i for i in delivered if not re.search(rf"def test_r_{i.lower()}_", tests))
    assert not missing, f"exigences livrées sans test nommé : {missing}"


# --- A. Données ----------------------------------------------------------------

def test_r_a4_historique(studio):
    """R-A4 : trois modifications successives donnent trois lignes avant/après avec leur auteur ;
    `riot history`, l'API et l'absence d'UPDATE direct hors db.py."""
    import re
    from pathlib import Path
    from fastapi.testclient import TestClient
    from riotmachine import cli, production
    from riotmachine.regie.app import app

    assert cli.main(["init"]) == 0
    assert cli.main(["clip", "new", "Histo", "--song", str(studio["song"]), "--characters", "jj"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.import_shots(conn, "histo", {"blocks": [{"name": "B", "shots": [
        {"t_start": 0, "t_end": 4, "description": "v1", "characters": ["jj"]}]}]}, by="michael")
    sid = conn.execute("SELECT id FROM shots").fetchone()[0]
    db.set_actor("michael")
    production.update_shot(conn, sid, script="v2")   # son texte ; la production le suit (pas encore transformée)
    db.set_actor("agent:script-doctor")
    production.update_shot(conn, sid, description="v2 complété", framing="CU")
    production.update_shot(conn, sid, description="v2 complété")   # rien ne change : rien n'est journalisé
    db.set_actor("machine")

    hist = db.history(conn, "shots", sid)
    desc = [(r["old"], r["new"], r["author"]) for r in reversed(hist) if r["field"] == "description"]
    assert desc == [("v1", "v2", "michael"), ("v2", "v2 complété", "agent:script-doctor")]
    assert [(r["old"], r["new"], r["author"]) for r in hist if r["field"] == "script"] == [("v1", "v2", "michael")]
    assert [(r["field"], r["old"], r["new"]) for r in hist if r["field"] == "framing"] == [("framing", None, "CU")]
    assert len(hist) == 4

    # la CLI et la régie exposent le même historique, dans l'ordre
    assert cli.main(["history", "shot", str(sid)]) == 0
    client = TestClient(app)
    api = client.get(f"/api/shots/{sid}/history").json()
    assert [r["field"] for r in api] == [r["field"] for r in hist]
    assert client.get(f"/api/shots/{sid}").json()["id"] == sid

    # aucun UPDATE direct sur les tables suivies hors db.py
    pkg = Path(production.__file__).parent
    direct = {}
    for p in pkg.rglob("*.py"):
        if p.name == "db.py":
            continue
        hits = re.findall(r"UPDATE\s+(clips|blocks|shots|characters|character_versions|elements)\s+SET", p.read_text())
        if hits:
            direct[p.name] = hits
    assert not direct, f"UPDATE directs à passer par db.update : {direct}"


def test_r_a2_identifiants_stables(studio, monkeypatch):
    """R-A2 : une image sur le plan 3, la description du plan 2 modifiée et le découpage réimporté :
    le plan 3 garde son id, son image et son statut. Blocs appariés par id, champ omis conservé,
    suppression logique d'un plan qui a des assets, restauration."""
    from riotmachine import cli, production, routing
    from riotmachine import providers as prov

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Stable", song=studio["song"], characters=["jj"])
    slug = "stable"
    dec = {"blocks": [
        {"name": "Couplet", "shots": [
            {"t_start": 0, "t_end": 4, "description": "plan un", "framing": "CU", "characters": ["jj"]},
            {"t_start": 4, "t_end": 8, "description": "plan deux", "characters": ["jj"]}]},
        {"name": "Refrain", "shots": [
            {"t_start": 8, "t_end": 12, "description": "plan trois", "characters": ["jj"]}]},
    ]}
    production.import_shots(conn, slug, dec, by="michael")
    blocks = production.decoupage(conn, slug)
    ids = {sh["num"]: sh["id"] for b in blocks for sh in b["shots"]}
    bids = {b["name"]: b["id"] for b in blocks}
    assert sorted(ids) == [1, 2, 3]

    # le refrain part en production : une image est générée sur le plan 3
    production.set_cut_ok(conn, ids[3], True)
    production.validate_block(conn, bids["Refrain"])
    production.block_refs_checked(conn, slug, 2, "")
    production.update_shot(conn, ids[3], image_prompt="x")
    monkeypatch.setattr(prov, "simulated", lambda provider="fal": False)
    monkeypatch.setattr(routing, "provider_has_key", lambda key: True)
    real_submit = prov.submit
    monkeypatch.setattr(prov, "submit", lambda *a, **k: real_submit(*a, **{**k, "force_mock": True}))
    production.launch_image(conn, ids[3], approved=True, model="nano-banana-2", count=1)
    shot3 = db.get_shot(conn, ids[3])
    assert shot3["status"] == "image_gen"
    asset = db.latest_asset(conn, ids[3], "image")
    assert asset

    # Michael modifie la description du plan 2 et réenregistre, sans renvoyer le cadrage du plan 1
    dec2 = {"blocks": [
        {"id": bids["Couplet"], "name": "Couplet", "shots": [
            {"id": ids[1], "t_start": 0, "t_end": 4, "description": "plan un", "characters": ["jj"]},
            {"id": ids[2], "t_start": 4, "t_end": 8, "description": "plan deux, revu", "characters": ["jj"]}]},
        {"id": bids["Refrain"], "name": "Refrain", "shots": [
            {"id": ids[3], "t_start": 8, "t_end": 12, "description": "plan trois", "characters": ["jj"]}]},
    ]}
    production.import_shots(conn, slug, dec2, by="michael")
    after = {sh["num"]: sh for b in production.decoupage(conn, slug) for sh in b["shots"]}
    assert after[3]["id"] == ids[3] and after[3]["status"] == "image_gen"
    assert db.latest_asset(conn, ids[3], "image")["id"] == asset["id"]
    assert after[2]["id"] == ids[2] and after[2]["description"] == "plan deux, revu"
    assert after[1]["id"] == ids[1] and after[1]["framing"] == "CU"   # champ omis : conservé
    assert {b["name"]: b["id"] for b in production.decoupage(conn, slug)} == bids

    # les blocs se réordonnent par id sans changer d'id ni de plan
    dec3 = {"blocks": [dec2["blocks"][1], dec2["blocks"][0]]}
    production.import_shots(conn, slug, dec3, by="michael")
    blocks3 = production.decoupage(conn, slug)
    assert [b["id"] for b in blocks3] == [bids["Refrain"], bids["Couplet"]]
    assert [sh["id"] for b in blocks3 for sh in b["shots"]] == [ids[3], ids[1], ids[2]]
    production.import_shots(conn, slug, dec2, by="michael")   # retour à l'ordre initial

    # un plan retiré qui a des assets est supprimé logiquement : image et historique conservés, restaurable
    conn.execute("INSERT INTO assets (shot_id, kind, version, path, status, cost_usd, created_at) VALUES (?,?,?,?,?,?,?)",
                 (ids[2], "image", 1, "x.png", "ready", 0.5, db.now()))
    dec4 = {"blocks": [
        {"id": bids["Couplet"], "name": "Couplet", "shots": [dec2["blocks"][0]["shots"][0]]},
        dec2["blocks"][1]]}
    production.import_shots(conn, slug, dec4, by="michael")
    gone = db.get_shot(conn, ids[2])
    assert gone["deleted_at"] and db.latest_asset(conn, ids[2], "image")["cost_usd"] == 0.5
    assert [sh["id"] for b in production.decoupage(conn, slug) for sh in b["shots"]] == [ids[1], ids[3]]
    snap = production.clip_snapshot(conn, slug)
    assert [s["id"] for s in snap["shots"]] == [ids[1], ids[3]]
    assert [s["id"] for s in snap["deleted_shots"]] == [ids[2]] and snap["deleted_shots"][0]["cost_usd"] == 0.5
    assert any(c["field"] == "deleted_at" for c in db.history(conn, "shots", ids[2]))
    production.restore_shot(conn, ids[2])
    back = {sh["num"]: sh for b in production.decoupage(conn, slug) for sh in b["shots"]}
    assert [back[n]["id"] for n in (1, 2, 3)] == [ids[1], ids[2], ids[3]]
    assert db.get_shot(conn, ids[2])["deleted_at"] is None

    # un plan sans asset est supprimé réellement
    dec5 = {"blocks": [
        {"id": bids["Couplet"], "name": "Couplet", "shots": [dec2["blocks"][0]["shots"][1]]},
        dec2["blocks"][1]]}
    production.import_shots(conn, slug, dec5, by="michael")
    assert conn.execute("SELECT 1 FROM shots WHERE id=?", (ids[1],)).fetchone() is None

    # valider le découpage entier ne remet pas à zéro un plan déjà avancé
    production.set_cut_ok(conn, ids[2], True)
    production.set_stage(conn, slug, "decoupage_review")
    production.review_decoupage(conn, slug, "approve")
    assert db.get_shot(conn, ids[3])["status"] == "image_gen"


def test_r_a3_baseline_michael(studio):
    """R-A3 : le texte de Michael (`script`, `brief`) n'est jamais écrit par un agent ; la production
    (`description`, `intention`) le suit jusqu'à la première transformation, puis reste et se marque
    « à mettre à jour » quand Michael change son texte ; l'agent complète sans reformuler."""
    from riotmachine import cli, production

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Base", song=studio["song"], characters=["jj"])
    slug = "base"
    production.import_shots(conn, slug, {"blocks": [{"name": "B", "brief": "mon intention", "shots": [
        {"t_start": 0, "t_end": 4, "script": "JJ marche sous la pluie", "characters": ["jj"]}]}]}, by="michael")
    sh = conn.execute("SELECT * FROM shots").fetchone()
    b = conn.execute("SELECT * FROM blocks").fetchone()
    assert sh["script"] == sh["description"] == "JJ marche sous la pluie"
    assert b["brief"] == b["intention"] == "mon intention"
    sid, bid = sh["id"], b["id"]

    # le script-doctor complète : les mots de Michael, puis ses compléments
    agent = {"blocks": [{"id": bid, "name": "B", "intention": "mon intention, lumière froide", "shots": [
        {"id": sid, "t_start": 0, "t_end": 4, "description": "JJ marche sous la pluie, parapluie rouge, plan large",
         "framing": "WS", "characters": ["jj"]}]}]}
    production.import_shots(conn, slug, agent)
    sh = db.get_shot(conn, sid)
    assert sh["script"] == "JJ marche sous la pluie"
    assert sh["description"] == "JJ marche sous la pluie, parapluie rouge, plan large" and sh["prod_outdated"] == 0
    b = db.row(conn.execute("SELECT * FROM blocks WHERE id=?", (bid,)).fetchone())
    assert b["brief"] == "mon intention" and b["intention"] == "mon intention, lumière froide"

    # il ne reformule pas, il n'écrit ni le script ni le brief
    bad = json.loads(json.dumps(agent))
    bad["blocks"][0]["shots"][0]["description"] = "Une femme marche dehors"
    with pytest.raises(production.ProductionError, match="mots de Michael"):
        production.import_shots(conn, slug, bad)
    bad = json.loads(json.dumps(agent))
    bad["blocks"][0]["shots"][0]["script"] = "autre"
    with pytest.raises(production.ProductionError, match="script"):
        production.import_shots(conn, slug, bad)
    bad = json.loads(json.dumps(agent))
    bad["blocks"][0]["brief"] = "autre"
    with pytest.raises(production.ProductionError, match="brief"):
        production.import_shots(conn, slug, bad)
    assert db.get_shot(conn, sid)["script"] == "JJ marche sous la pluie"

    # Michael change son texte : la production reste, marquée à mettre à jour, le script-doctor est rappelé
    mine = {"blocks": [{"id": bid, "name": "B", "brief": "mon intention", "shots": [
        {"id": sid, "t_start": 0, "t_end": 4, "script": "JJ court sous la pluie", "characters": ["jj"]}]}]}
    production.import_shots(conn, slug, mine, by="michael")
    sh = db.get_shot(conn, sid)
    assert sh["script"] == "JJ court sous la pluie"
    assert sh["description"] == "JJ marche sous la pluie, parapluie rouge, plan large" and sh["prod_outdated"] == 1
    assert any("production à mettre à jour" in r for r in production.needs_agent(conn, slug)["reasons"])
    # le script-doctor remet la production à jour, à partir des nouveaux mots
    with pytest.raises(production.ProductionError, match="mots de Michael"):
        production.update_shot(conn, sid, description="JJ marche sous la pluie, parapluie rouge")
    production.update_shot(conn, sid, description="JJ court sous la pluie, parapluie rouge, plan large")
    assert db.get_shot(conn, sid)["prod_outdated"] == 0
    assert not any("production à mettre à jour" in r for r in production.needs_agent(conn, slug)["reasons"])

    # un agent ne peut pas écrire le script par la CLI ; la régie (Michael) le peut
    db.set_actor("agent:script-doctor")
    with pytest.raises(production.ProductionError, match="Michael"):
        production.update_shot(conn, sid, script="x")
    db.set_actor("michael")
    production.update_shot(conn, sid, script="JJ court sous la pluie, essoufflée")
    db.set_actor("machine")
    sh = db.get_shot(conn, sid)
    assert sh["script"] == "JJ court sous la pluie, essoufflée" and sh["prod_outdated"] == 1
    settings = json.loads((Path(production.__file__).parent.parent / ".claude" / "settings.json").read_text())
    assert any("--script" in d for d in settings["permissions"]["deny"])


# --- F. Clarté --------------------------------------------------------------------

def test_r_f1_responsable_par_statut(studio):
    """R-F1 : chaque statut a un responsable unique ; `/api/shots/<id>` renvoie `owner` ;
    les surcharges (bloc non validé, dépense en attente, références à vérifier) désignent le bon."""
    from fastapi.testclient import TestClient
    from riotmachine import cli, production
    from riotmachine.regie.app import app

    assert set(db.STATUS_OWNER) == set(db.SHOT_STATUSES), "un statut sans responsable"
    assert set(db.STATUS_OWNER.values()) <= set(db.OWNER_LABEL), "un responsable sans libellé"

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Qui", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "qui", {"blocks": [{"name": "B", "shots": [
        {"t_start": 0, "t_end": 4, "script": "a", "characters": ["jj"]},
        {"t_start": 4, "t_end": 8, "script": "b", "characters": ["jj"]}]}]}, by="michael")
    ids = [r["id"] for r in conn.execute("SELECT id FROM shots ORDER BY num")]
    client = TestClient(app)
    one = client.get(f"/api/shots/{ids[0]}").json()
    assert one["owner"]["who"] == "michael" and "bloc" in one["owner"]["why"]   # le bloc n'est pas validé : à lui

    for sid in ids:
        production.set_cut_ok(conn, sid, True)
    bid = conn.execute("SELECT id FROM blocks").fetchone()[0]
    production.validate_block(conn, bid)
    assert production.shot_view(conn, db.get_shot(conn, ids[0]))["owner"]["who"] == "agent:script-doctor"
    production.block_refs_checked(conn, "qui", 1, "")
    assert production.shot_view(conn, db.get_shot(conn, ids[0]))["owner"]["who"] == "agent:storyboard"

    db.set_shot_status(conn, ids[1], "video_review")
    v = production.shot_view(conn, db.get_shot(conn, ids[1]))["owner"]
    assert v["who"] == "michael" and v["label"].startswith("En attente de : ")
    db.set_shot_status(conn, ids[1], "prompt_todo")
    assert production.shot_view(conn, db.get_shot(conn, ids[1]))["owner"]["who"] == "agent:routeur"
    production.update_shot(conn, ids[1], model_key="wan-3")
    assert production.shot_view(conn, db.get_shot(conn, ids[1]))["owner"]["who"] == "agent:prompteur"
    db.set_shot_status(conn, ids[1], "draft_gen")
    assert production.shot_view(conn, db.get_shot(conn, ids[1]))["owner"]["who"] == "fournisseur"
    db.update(conn, "shots", ids[1], {"status": "failed", "failed_step": "lipsync"})
    assert production.shot_view(conn, db.get_shot(conn, ids[1]))["owner"]["who"] == "agent:finition"


# --- B. Découpage et plans ------------------------------------------------------

def test_r_b5_navigation_vers_reference(studio):
    """R-B5 (début) : un plan expose ses références avec leur slug, la régie en fait des liens vers la
    fiche de la référence (route .../decors/ref/<slug>) avec un bouton de retour au plan.
    Le critère complet (block, script, description, script_notes, reviews, references, history) arrive au lot 3."""
    from fastapi.testclient import TestClient
    from riotmachine import cli, elements, production
    from riotmachine.regie.app import app

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Nav", song=studio["song"], characters=["jj"])
    elements.create(conn, "nav", "decor", "Jardin de JJ", description="le jardin")
    production.import_shots(conn, "nav", {"blocks": [{"name": "B", "shots": [
        {"t_start": 0, "t_end": 4, "script": "@jj dans le @jardin-de-jj", "characters": ["jj"]}]}]}, by="michael")
    sid = conn.execute("SELECT id FROM shots").fetchone()[0]
    shot = TestClient(app).get(f"/api/shots/{sid}").json()
    assert [e["slug"] for e in shot["elements"]] == ["jardin-de-jj"]
    assert shot["script"] == "@jj dans le @jardin-de-jj"

    js = (Path(production.__file__).parent / "regie" / "static" / "app.js").read_text()
    assert 'sub === "ref"' in js and "goToRef" in js and "backbtn" in js
    assert 'id="look-${esc(lk.slug)}"' in js and "focusRefTarget" in js


def test_r_e5_supprimer_une_tenue(studio):
    """R-E5 : une tenue supprimée sort des castings et des plans ; ses fichiers sont gardés à part."""
    from fastapi.testclient import TestClient
    from riotmachine import cli, production
    from riotmachine.regie.app import app

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Tenue", song=studio["song"], characters=["jj"])
    if not conn.execute("SELECT 1 FROM looks WHERE character_slug='jj' AND slug='bureau'").fetchone():
        production.create_look(conn, "jj", "bureau", "tailleur gris", clip_slug="tenue")
    lk = db.row(conn.execute("SELECT * FROM looks WHERE character_slug='jj' AND slug='bureau'").fetchone())
    conn.execute("UPDATE castings SET look_slug='bureau' WHERE clip_slug='tenue' AND character_slug='jj'")
    production.import_shots(conn, "tenue", {"blocks": [{"name": "B", "shots": [
        {"t_start": 0, "t_end": 4, "script": "@jj-bureau entre", "characters": ["jj"]}]}]}, by="michael")
    sid = conn.execute("SELECT id FROM shots").fetchone()[0]
    db.update(conn, "shots", sid, {"looks": json.dumps({"jj": "bureau"})}, by="michael")
    old_dir = production.absp(lk["dir"])
    assert old_dir.is_dir()

    r = TestClient(app).delete("/api/characters/jj/looks/bureau")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["worn"] == [1] and body["cited"] == [1]
    assert conn.execute("SELECT count(*) FROM looks WHERE slug='bureau'").fetchone()[0] == 0
    assert conn.execute("SELECT looks FROM shots WHERE id=?", (sid,)).fetchone()[0] is None
    assert conn.execute("SELECT look_slug FROM castings WHERE clip_slug='tenue'").fetchone()[0] is None
    assert any(h["field"] == "looks" and "supprimée" in (h["reason"] or "") for h in db.history(conn, "shots", sid))
    assert not old_dir.exists() and (old_dir.parent / ".supprimees").is_dir()
    assert TestClient(app).delete("/api/characters/jj/looks/bureau").status_code >= 400


def test_r_f4_a_faire_mene_au_bon_endroit(studio):
    """R-F4 : chaque ligne « À faire » porte un lien précis (un plan, le bloc à valider, le groupe de
    dépenses) ; la régie mémorise d'où l'on vient et y ramène."""
    from fastapi.testclient import TestClient
    from riotmachine import cli, production
    from riotmachine.regie.app import app

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Todo", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "todo", {"blocks": [
        {"name": "A", "shots": [{"t_start": 0, "t_end": 4, "script": "un", "characters": ["jj"]},
                                {"t_start": 4, "t_end": 8, "script": "deux", "characters": ["jj"]}]},
        {"name": "B", "shots": [{"t_start": 8, "t_end": 12, "script": "trois", "characters": ["jj"]}]}]}, by="michael")
    ids = [r[0] for r in conn.execute("SELECT id FROM shots WHERE clip_slug='todo' ORDER BY num")]
    conn.execute("UPDATE shots SET status='draft_review' WHERE id=?", (ids[1],))
    conn.execute("UPDATE clips SET stage='decoupage_review' WHERE slug='todo'")
    conn.execute("INSERT INTO spend_requests (action, args, dedupe, label, clip_slug, shot_id, est_usd, status, created_at) "
                 "VALUES ('image', '{}', 'x', 'Plan 1', 'todo', ?, 0, 'pending', '2026-11-06T00:00:00Z')", (ids[0],))
    conn.commit()
    todo = TestClient(app).get("/api/overview").json()["todo"]
    hrefs = [t["href"] for t in todo]
    assert "#/depenses/clip:todo" in hrefs
    assert "#/clip/todo/decoupage/avalider" in hrefs
    assert f"#/clip/todo/plans/p/{ids[1]}" in hrefs
    assert any("plan 2, vidéo draft" in t["label"] for t in todo)
    assert any("bloc 1 à valider" in t["label"] for t in todo)

    js = (Path(production.__file__).parent / "regie" / "static" / "app.js").read_text()
    assert "data-todo" in js and "function goBack" in js and "function closeShot" in js
    assert 'sub === "avalider"' in js and "focusToSort" in js and "showSpend(arg)" in js


def test_r_f5_a_faire_suit_les_blocs(studio):
    """R-F5 : on finit le bloc 1 avant de valider le découpage du bloc 2."""
    from fastapi.testclient import TestClient
    from riotmachine import cli, production
    from riotmachine.regie.app import app

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Ordre", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "ordre", {"blocks": [
        {"name": "A", "shots": [{"t_start": 0, "t_end": 4, "script": "un", "characters": ["jj"]}]},
        {"name": "B", "shots": [{"t_start": 4, "t_end": 8, "script": "deux", "characters": ["jj"]}]}]}, by="michael")
    sid = conn.execute("SELECT id FROM shots WHERE clip_slug='ordre' AND num=1").fetchone()[0]
    conn.execute("UPDATE blocks SET validated=1 WHERE clip_slug='ordre' AND num=1")
    conn.execute("UPDATE shots SET status='image_review' WHERE id=?", (sid,))
    conn.execute("UPDATE clips SET stage='decoupage_review' WHERE slug='ordre'")
    conn.commit()
    todo = TestClient(app).get("/api/overview").json()["todo"]
    labels = [t["label"] for t in todo]
    plan = next(i for i, l in enumerate(labels) if "plan 1, visuel" in l)
    cut = next(i for i, l in enumerate(labels) if "bloc 2 à valider" in l)
    assert plan < cut
    assert "bloc 1" in labels[plan]


def test_r_f6_a_faire_sur_toutes_les_pages():
    """R-F6 : bouton « À faire » avec pastille dans la barre du haut, liste rouverte au retour."""
    from riotmachine import production
    static = Path(production.__file__).parent / "regie" / "static"
    html = (static / "index.html").read_text()
    js = (static / "app.js").read_text()
    assert 'id="todobtn"' in html and 'id="todo-n"' in html and 'id="todopop"' in html
    assert "function updateTodoBtn" in js and "state.todoPopReturn" in js and "afterRoute()" in js


def test_r_f7_detail_du_plan_en_parcours(studio):
    """R-F7 : la HD contrôlée attend Michael ; le détail suit Visuel puis Vidéo, guidé par la frise."""
    from riotmachine import cli, production
    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Parcours", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "parcours", {"blocks": [{"name": "A", "shots": [
        {"t_start": 0, "t_end": 4, "script": "un", "characters": ["jj"]}]}]}, by="michael")
    sid = conn.execute("SELECT id FROM shots WHERE clip_slug='parcours'").fetchone()[0]
    conn.execute("INSERT INTO assets (shot_id, kind, version, status, created_at) VALUES (?, 'image_hd', 1, 'ready', ?)",
                 (sid, db.now()))
    db.set_shot_status(conn, sid, "hd_qc")
    conn.commit()
    assert production.qc_result(conn, sid, True, "fidèle") == "hd_review"
    assert production.review_shot(conn, sid, "approve") == "prompt_todo"

    js = (Path(production.__file__).parent / "regie" / "static" / "app.js").read_text()
    for name in ("function renderGuide", "function renderVisuel", "function renderVideo", "function goStep",
                 "function videoModelPicker", "function refuseBox", 'data-fixvisual', 'data-sendrefuse'):
        assert name in js, name
    assert '"Le plan"' in js and '"Visuel"' in js and '"Vidéo"' in js
    assert "Lancer la vidéo draft" in js and "Valider le visuel HD" in js
    # à la revue de la vidéo, le prompt est en lecture seule (<pre>) : la validation ne le lit pas comme un champ
    assert 'vp.tagName === "TEXTAREA"' in js
    # le retour au storyboardeur reste possible quand toutes les propositions sont écartées
    assert "function askStoryboard" in js and js.count("askStoryboard(shot)") >= 2
    # un seul bouton pour valider un bloc au découpage, dans sa tête
    assert js.count("data-validateblock=") == 1 and "blockready" not in js


def test_r_b7_corriger_une_etape_validee(studio):
    """R-B7 : depuis la vidéo draft, Michael fait refaire le visuel ; le plan repart chez le storyboard."""
    from fastapi.testclient import TestClient
    from riotmachine import cli, production
    from riotmachine.regie.app import app

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Redo", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "redo", {"blocks": [{"name": "A", "shots": [
        {"t_start": 0, "t_end": 4, "script": "un réveil", "characters": ["jj"]}]}]}, by="michael")
    sid = conn.execute("SELECT id FROM shots WHERE clip_slug='redo'").fetchone()[0]
    for kind, st in (("image", "validated"), ("image_hd", "validated"), ("draft", "ready")):
        conn.execute("INSERT INTO assets (shot_id, kind, version, status, created_at) VALUES (?,?,1,?,?)",
                     (sid, kind, st, db.now()))
    conn.execute("UPDATE shots SET status='draft_review' WHERE id=?", (sid,))
    conn.commit()
    client = TestClient(app)
    assert client.post(f"/api/shots/{sid}/redo", json={"step": "image", "comment": ""}).status_code >= 400
    r = client.post(f"/api/shots/{sid}/redo", json={"step": "image", "comment": "le réveil doit être de face"})
    assert r.status_code == 200, r.text
    assert db.get_shot(conn, sid)["status"] == "image_todo"
    st = dict(conn.execute("SELECT kind, status FROM assets WHERE shot_id=?", (sid,)).fetchall())
    assert st == {"image": "rejected", "image_hd": "superseded", "draft": "superseded"}
    rv = conn.execute("SELECT route, handled, comment FROM reviews WHERE shot_id=? ORDER BY id DESC", (sid,)).fetchone()
    assert rv["route"] == "storyboard" and rv["handled"] == 1 and "de face" in rv["comment"]
    conn.execute("UPDATE shots SET status='image_gen' WHERE id=?", (sid,))
    conn.commit()
    assert client.post(f"/api/shots/{sid}/redo", json={"step": "image", "comment": "x"}).status_code >= 400

    js = (Path(production.__file__).parent / "regie" / "static" / "app.js").read_text()
    assert "function redoBox" in js and "/redo`" in js


def test_r_b8_ecarter_une_proposition(studio):
    """R-B8 : Michael écarte une proposition ; la dernière écartée fait repartir l'étape."""
    from fastapi.testclient import TestClient
    from riotmachine import cli, production
    from riotmachine.regie.app import app

    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Ecart", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "ecart", {"blocks": [{"name": "A", "shots": [
        {"t_start": 0, "t_end": 4, "script": "un", "characters": ["jj"]},
        {"t_start": 4, "t_end": 8, "script": "deux", "characters": ["jj"]}]}]}, by="michael")
    s1, s2 = [r[0] for r in conn.execute("SELECT id FROM shots WHERE clip_slug='ecart' ORDER BY num")]
    add = lambda sid, kind, v, st: conn.execute(
        "INSERT INTO assets (shot_id, kind, version, status, created_at) VALUES (?,?,?,?,?)",
        (sid, kind, v, st, db.now())).lastrowid
    i1, i2 = add(s1, "image", 1, "ready"), add(s1, "image", 2, "ready")
    ok = add(s1, "image", 3, "validated")
    d1 = add(s2, "draft", 1, "ready")
    conn.execute("UPDATE shots SET status='image_review' WHERE id=?", (s1,))
    conn.execute("UPDATE shots SET status='draft_review' WHERE id=?", (s2,))
    conn.commit()
    c = TestClient(app)
    r = c.post(f"/api/assets/{i1}/discard", json={"note": "trop sombre"}).json()
    assert r["left"] == 1 and db.get_shot(conn, s1)["status"] == "image_review"
    a = conn.execute("SELECT status, error FROM assets WHERE id=?", (i1,)).fetchone()
    assert a["status"] == "rejected" and a["error"].startswith("Écartée par Michael")
    assert c.post(f"/api/assets/{i2}/discard", json={}).json()["status"] == "image_todo"
    assert c.post(f"/api/assets/{ok}/discard", json={}).status_code >= 400
    assert c.post(f"/api/assets/{d1}/discard", json={}).json()["status"] == "change_requested"
    assert conn.execute("SELECT COUNT(*) FROM reviews WHERE shot_id=? AND handled=0", (s2,)).fetchone()[0] == 1

    js = (Path(production.__file__).parent / "regie" / "static" / "app.js").read_text()
    assert "data-discard" in js and "function byMichael" in js


def test_r_f8_mention_sans_quitter_le_texte():
    """R-F8 : un @ dans le texte n'ouvre rien ; la puce ouvre la référence, sa croix la retire."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "riotmachine/regie/static/app.js").read_text()
    i = js.index("function mentionHtml(")
    body = js[i:js.index("\n}", i)]
    assert "data-go" not in body
    assert 'class="refchip k-${e.kind}" data-go=' in js
    assert js.count("data-unref=") >= 1 and "function unmention" in js
    assert "data-refsdt=" in js
    # la croix enregistre tout de suite (bloc validé : par le prompt détaillé du plan), sans tenir compte de la casse
    i = js.index("function unmention(")
    assert '"gi"' in js[i:i + 300]
    j = js.index('closest("button[data-unref]")')
    assert "/detail`" in js[j:j + 3000] and "decoupage-edit" in js[j:j + 3000]


def test_r_b8_ecarter_demande_pourquoi():
    """R-B8 : « Écarter » demande ce qui ne va pas ; la raison part avec l'écart (note du plan)."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "riotmachine/regie/static/app.js").read_text()
    assert "data-dodiscard" in js and "discardbox" in js
    i = js.index("if (d.dodiscard)")
    assert "{ json: { note } }" in js[i:i + 400]


def test_r_f7_echec_dit_pourquoi():
    """R-F7 : la boîte « Échec » écrit la raison elle-même et, pour un quota épuisé, nomme un modèle d'un autre fournisseur."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "riotmachine/regie/static/app.js").read_text()
    i = js.index("function failBox(")
    assert "La remarque au-dessus" not in js
    assert 'author === "machine"' in js[i:i + 600] and "function quotaHint" in js
    assert 'h = failBox(shot, "image") + h;' in js


def test_r_f7_quota_epuise_et_changement_de_modele(studio, monkeypatch):
    """Dépenses : un quota gratuit épuisé aujourd'hui est repéré, et une demande en attente passe sur un autre modèle gratuit."""
    from datetime import datetime, timezone
    from riotmachine import cli, production, routing
    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Quota", song=studio["song"], characters=["jj"])
    production.import_shots(conn, "quota", {"blocks": [{"name": "A", "shots": [
        {"t_start": 0, "t_end": 4, "script": "un", "characters": ["jj"]}]}]}, by="michael")
    sid = conn.execute("SELECT id FROM shots WHERE clip_slug='quota'").fetchone()[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("INSERT INTO assets (shot_id, kind, version, path, status, model_key, error, created_at) "
                 "VALUES (?, 'image', 1, NULL, 'failed', 'cloudflare:klein-9b', 'FLUX.2 klein 9B (Cloudflare) : quota gratuit du jour épuisé', ?)",
                 (sid, now))
    conn.execute("INSERT INTO spend_requests (action, args, dedupe, label, clip_slug, shot_id, model_key, provider, est_usd, funding, status, created_at) "
                 "VALUES ('image', ?, 'q', 'Plan 1 : visuel draft (FLUX.2 klein 9B (Cloudflare), gratuit)', 'quota', ?, "
                 "'cloudflare:klein-9b', 'gratuit', 0, 'cash', 'pending', ?)",
                 (json.dumps({"shot_id": sid, "count": 3, "model": "cloudflare:klein-9b"}), sid, now))
    conn.commit()
    assert "cloudflare" in production.quota_out(conn)
    rid = conn.execute("SELECT id FROM spend_requests WHERE dedupe='q'").fetchone()[0]
    assert production.spend_requests(conn)[0]["free"] is True
    monkeypatch.setattr(routing, "provider_usable", lambda p: True)
    production.change_spend_model(conn, rid, "huggingface:flux2-dev")
    r = conn.execute("SELECT args, model_key, label FROM spend_requests WHERE id=?", (rid,)).fetchone()
    assert json.loads(r[0])["model"] == "huggingface:flux2-dev" and r[1] == "huggingface:flux2-dev"
    assert "Hugging Face" in r[2] and "Cloudflare" not in r[2]
    with pytest.raises(production.ProductionError):
        production.change_spend_model(conn, rid, "nano-banana-pro")


def test_r_f7_lancer_la_video_en_un_toucher():
    """R-F7 : la vidéo draft se lance d'un seul bouton (coût écrit dessus), sans « Passer au lancement » ni « Confirmer ? »."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "riotmachine/regie/static/app.js").read_text()
    assert "Passer au lancement de la vidéo draft" not in js
    assert "data-launchdraft" in js
    i = js.index("if (d.launchdraft)")
    assert "/run`" in js[i:i + 900] and 'decision: "approve"' in js[i:i + 900]
    assert 'needsConfirm(t, "regen"' not in js and 'needsConfirm(t, "run"' not in js


def test_r_b5_nouvel_objet_ouvre_sa_fiche():
    """R-B5 : créer un objet ou une tenue mène à sa fiche, avec le retour vers l'endroit d'où l'on venait."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "riotmachine/regie/static/app.js").read_text()
    assert "function openNewRef(" in js
    assert js.count("openNewRef(clip,") >= 2


def test_r_e_objet_image_telle_quelle(studio):
    """Un objet dont l'image déposée est déjà la bonne la garde telle quelle comme référence (pas de HD à générer)."""
    import subprocess
    from riotmachine import cli, elements, production
    assert cli.main(["init"]) == 0
    conn = db.connect()
    db.init_db(conn)
    production.create_clip(conn, "Sac", song=studio["song"], characters=["jj"])
    e = elements.create(conn, "sac", "objet", "Sac porte-documents", "")
    img = studio["tmp"] / "sac.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=brown:s=64x64", "-frames:v", "1", str(img)], check=True)
    ins = elements.add_image(conn, e["id"], img, role="inspi")
    elements.pick(conn, ins["id"], "use")
    el = [x for x in elements.clip_elements(conn, "sac") if x["id"] == e["id"]][0]
    assert el["step"] == "done"
    assert any(i["role"] == "hd" and i["status"] == "kept" for i in el["images"])
