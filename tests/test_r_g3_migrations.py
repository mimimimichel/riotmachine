"""R-G3 : schéma versionné, migrations numérotées et rejouables, copie avant migration, aucune suppression."""

import re
import shutil
import sqlite3

import pytest

from riotmachine import db, migrate, migration_v1


def test_r_g3_migrations_deux_fois_sans_erreur(studio):
    conn = db.connect()
    first = migrate.migrate(conn)
    second = migrate.migrate(conn)
    assert first["applied"] == [m.num for m in migrate.available()]
    assert second == {"applied": [], "backup": None}
    nums = [r[0] for r in conn.execute("SELECT num FROM schema_migrations ORDER BY num")]
    assert nums == first["applied"]


def test_r_g3_sauvegarde_avant_migration(studio, tmp_path):
    conn = db.connect()
    migrate.migrate(conn)
    extra = tmp_path / "migs"
    shutil.copytree(migrate.MIGRATIONS_DIR, extra)
    (extra / "9999_essai.sql").write_text("CREATE TABLE essai (id INTEGER PRIMARY KEY);")
    res = migrate.migrate(conn, extra)
    assert res["applied"] == [9999]
    saved = res["backup"]
    assert saved and (studio / "backups").is_dir()
    copy = sqlite3.connect(saved)
    assert copy.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == len(migrate.available())


def test_r_g3_migration_en_echec_laisse_la_base_intacte(studio, tmp_path):
    conn = db.connect()
    migrate.migrate(conn)
    extra = tmp_path / "migs"
    shutil.copytree(migrate.MIGRATIONS_DIR, extra)
    (extra / "9999_casse.sql").write_text("CREATE TABLE a (id INTEGER); CREATE TABLE a (id INTEGER);")
    with pytest.raises(Exception, match="9999"):
        migrate.migrate(conn, extra)
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='a'").fetchone() is None
    assert 9999 not in migrate.applied(conn)


def test_r_g3_migration_modifiee_refusee(studio, tmp_path):
    conn = db.connect()
    extra = tmp_path / "migs"
    shutil.copytree(migrate.MIGRATIONS_DIR, extra)
    migrate.migrate(conn, extra)
    f = next(extra.glob("0001_*.sql"))
    f.write_text(f.read_text() + "\n-- retouche\n")
    with pytest.raises(Exception, match="modifiée"):
        migrate.migrate(conn, extra)


def test_r_g3_aucune_suppression_de_donnees():
    for m in migrate.available():
        assert not re.search(r"\b(DROP|DELETE|TRUNCATE)\b", m.sql, re.I), m.name


def test_r_g3_migration_v1_sur_copie_de_base_v8(v1_db, studio, tmp_path):
    """Base v8 générée par legacy/ : aucune ligne perdue, identifiants conservés, base v1 intacte."""
    before = v1_db.read_bytes()
    target = studio / "riot-v3.db"
    res = migration_v1.run(v1_db, target)
    assert v1_db.read_bytes() == before                     # la base v1 n'est jamais modifiée
    assert all(ok for _n, ok, _d in res["controles"]), res["controles"]
    steps = {s["etape"]: s for s in res["etapes"]}
    assert steps["shots"]["importes"] == 88 and steps["blocks"]["importes"] == 18
    assert steps["clips"]["importes"] == 2 and steps["feedback"]["importes"] >= 1
    new = db.connect(target)
    old = sqlite3.connect(v1_db)
    for sid, script, desc in old.execute("SELECT id, script, description FROM shots"):
        words, prod = new.execute("SELECT words, production_text FROM shots WHERE id=?", (sid,)).fetchone()
        assert (words, prod) == (script, desc)
    assert new.execute("SELECT COUNT(*) FROM shots WHERE deleted_at IS NOT NULL").fetchone()[0] == 1
    # relancer n'ajoute rien
    res2 = migration_v1.run(v1_db, target)
    assert all(s["importes"] == 0 for s in res2["etapes"])
    assert new.execute("SELECT COUNT(*) FROM shots").fetchone()[0] == 88


def test_r_g3_migration_v1_essai_a_blanc(v1_db, studio):
    target = studio / "riot-v3.db"
    res = migration_v1.run(v1_db, target, essai=True)
    assert not target.exists()                               # rien n'est écrit en essai
    assert all(ok for _n, ok, _d in res["controles"])
    text = migration_v1.report_markdown(res, "13/11/2026")
    assert "essai à blanc" in text and "tout est conforme" in text and "| assets |" in text


def test_r_g3_migration_v1_refuse_un_autre_schema(studio, tmp_path):
    bad = tmp_path / "v1.db"
    c = sqlite3.connect(bad)
    c.execute("PRAGMA user_version=5")
    c.close()
    with pytest.raises(Exception, match="schéma 5"):
        migration_v1.run(bad, studio / "riot-v3.db", essai=True)
