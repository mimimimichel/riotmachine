"""Un test par exigence livrée de docs/REQUIREMENTS.md, nommé par son identifiant.

`pytest -k r_` liste les exigences couvertes.
"""

from __future__ import annotations

import sqlite3

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
    production.update_shot(conn, sid, description="v2")
    db.set_actor("agent:script-doctor")
    production.update_shot(conn, sid, description="v3", framing="CU")
    production.update_shot(conn, sid, description="v3")   # rien ne change : rien n'est journalisé
    db.set_actor("machine")

    hist = db.history(conn, "shots", sid)
    desc = [(r["old"], r["new"], r["author"]) for r in reversed(hist) if r["field"] == "description"]
    assert desc == [("v1", "v2", "michael"), ("v2", "v3", "agent:script-doctor")]
    assert [(r["field"], r["old"], r["new"]) for r in hist if r["field"] == "framing"] == [("framing", None, "CU")]
    assert len(hist) == 3

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
