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
