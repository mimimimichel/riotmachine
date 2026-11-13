"""R-A1 à R-A4, R-A6 : objet unique, identifiants stables, baseline, historique, versions."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from riotmachine import decoupage, files, generations, store, views
from riotmachine.errors import Refused, RiotError

REPO = Path(__file__).resolve().parent.parent


def _shot_ids(conn, cid):
    return [r[0] for r in conn.execute("SELECT id FROM shots WHERE clip_id=? AND deleted_at IS NULL ORDER BY num", (cid,))]


# --- R-A1 ------------------------------------------------------------------------

def test_r_a1_un_plan_une_seule_ligne_pour_toutes_les_vues(conn, clip):
    sid = _shot_ids(conn, clip)[0]
    with store.revision(conn, "agent:script-doctor", "précision") as rev:
        rev.update("shots", sid, {"production_text": "JJ sort, sac camel à l'épaule"})
    in_decoupage = views.decoupage(conn, clip)[0]["shots"][0]
    on_page = views.shot_page(conn, sid)["shot"]
    assert in_decoupage["production_text"] == on_page["production_text"] == "JJ sort, sac camel à l'épaule"
    assert conn.execute("SELECT COUNT(*) FROM shots WHERE id=?", (sid,)).fetchone()[0] == 1


# --- R-A2 ------------------------------------------------------------------------

def test_r_a2_reimport_garde_identifiants_retours_et_historique(conn, clip):
    ids = _shot_ids(conn, clip)
    blocks = [b["id"] for b in views.decoupage(conn, clip)]
    with store.revision(conn, store.MICHAEL, "retour") as rev:
        fid = rev.create("feedback", {"object_type": "shots", "object_id": ids[0], "text": "Plus serré"})
    h_before = len(store.history(conn, "shots", ids[0]))
    # Michael raccourcit le plan 4, retire le plan 3, ajoute un plan ; les autres ne bougent pas
    data = {"blocks": [
        {"id": blocks[0], "shots": [{"id": ids[0]}, {"id": ids[1]}]},
        {"id": blocks[1], "shots": [{"id": ids[3], "t_end": 11.5}, {"t_start": 11.5, "t_end": 13, "words": "Elle part"}]}]}
    with store.revision(conn, store.MICHAEL, "découpage modifié") as rev:
        counts = decoupage.import_decoupage(rev, clip, data)
    assert counts["plans_retires"] == 1 and counts["plans_crees"] == 1
    after = _shot_ids(conn, clip)
    assert after[:2] == ids[:2] and after[2] == ids[3]          # mêmes identifiants
    page = views.shot_page(conn, ids[0])
    assert [f["id"] for f in page["feedback"]] == [fid]          # le retour suit le plan
    assert len(page["history"]) == h_before                     # plan non touché : historique intact
    gone = conn.execute("SELECT deleted_at FROM shots WHERE id=?", (ids[2],)).fetchone()[0]
    assert gone is not None                                      # retiré, pas supprimé
    with store.revision(conn, store.MICHAEL, "restauration") as rev:
        assert rev.restore("shots", ids[2])
    assert conn.execute("SELECT deleted_at FROM shots WHERE id=?", (ids[2],)).fetchone()[0] is None


# --- R-A3 ------------------------------------------------------------------------

@pytest.mark.parametrize("table,field", [("shots", "words"), ("blocks", "intention"), ("clips", "brief"),
                                         ("feedback", "text")])
def test_r_a3_un_agent_ne_peut_pas_ecrire_la_baseline(conn, clip, table, field):
    oid = {"shots": _shot_ids(conn, clip)[0], "blocks": views.decoupage(conn, clip)[0]["id"], "clips": clip}.get(table)
    if table == "feedback":
        with store.revision(conn, store.MICHAEL) as rev:
            oid = rev.create("feedback", {"object_type": "clips", "object_id": clip, "text": "Garde le chien"})
    before = conn.execute(f"SELECT {field} FROM {table} WHERE id=?", (oid,)).fetchone()[0]
    for author in ("agent:script-doctor", "code:worker"):
        with pytest.raises(Refused, match="texte de Michael"):
            with store.revision(conn, author) as rev:
                rev.update(table, oid, {field: "reformulé par la machine"})
    assert conn.execute(f"SELECT {field} FROM {table} WHERE id=?", (oid,)).fetchone()[0] == before


def test_r_a3_l_agent_ecrit_a_cote_et_la_baseline_reste_identique(conn, clip):
    sid = _shot_ids(conn, clip)[1]
    words = conn.execute("SELECT words FROM shots WHERE id=?", (sid,)).fetchone()[0]
    data = {"blocks": [{"id": b["id"], "shots": [{"id": s["id"]} for s in b["shots"]]} for b in views.decoupage(conn, clip)]}
    data["blocks"][0]["shots"][1]["production_text"] = "Elle tourne la clé deux fois, gros plan sur la serrure"
    with store.revision(conn, "agent:script-doctor", "complète") as rev:
        decoupage.import_decoupage(rev, clip, data)
    assert conn.execute("SELECT words FROM shots WHERE id=?", (sid,)).fetchone()[0] == words
    data["blocks"][0]["shots"][1]["words"] = "Elle verrouille"
    with pytest.raises(Refused):
        with store.revision(conn, "agent:script-doctor") as rev:
            decoupage.import_decoupage(rev, clip, data)
    with pytest.raises(Refused):                                  # un plan neuf ne peut pas porter de mots
        with store.revision(conn, "agent:script-doctor") as rev:
            rev.create("shots", {"clip_id": clip, "num": 9, "t_start": 20, "t_end": 22, "words": "inventés"})


# --- R-A4 ------------------------------------------------------------------------

def test_r_a4_trois_modifications_trois_lignes_exactes(conn, clip):
    sid = _shot_ids(conn, clip)[2]
    n0 = len(store.history(conn, "shots", sid))
    with store.revision(conn, store.MICHAEL, "plus long") as rev:
        rev.update("shots", sid, {"t_end": 10.0})
    with store.revision(conn, "agent:prompteur", "précision") as rev:
        rev.update("shots", sid, {"production_text": "Elle descend les trois marches"})
    with store.revision(conn, store.MICHAEL, "mots") as rev:
        rev.update("shots", sid, {"words": "Descend vers le vélo vert"})
    lines = store.history(conn, "shots", sid)[n0:]
    assert [(h["field"], h["before"], h["after"], h["author"], h["reason"]) for h in lines] == [
        ("t_end", 9.5, 10.0, "michael", "plus long"),
        ("production_text", None, "Elle descend les trois marches", "agent:prompteur", "précision"),
        ("words", "Descend vers le vélo", "Descend vers le vélo vert", "michael", "mots")]
    assert all(h["created_at"] for h in lines)


def _riot(args, studio, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k != "RIOT_ACTOR"}
    env.update({"RIOT_STUDIO_ROOT": str(studio), "RIOT_DB_V3": str(studio / "riot-v3.db"),
                "PYTHONPATH": str(REPO), **(extra_env or {})})
    return subprocess.run([sys.executable, "-m", "riotmachine.cli", *args], env=env, capture_output=True, text=True)


def test_r_a4_riot_history_liste_les_lignes(conn, clip, studio):
    sid = _shot_ids(conn, clip)[0]
    r = _riot(["--auteur", "agent:prompteur", "ecrire", "plan", str(sid), "production_text=Elle sort vite",
               "--raison", "rythme"], studio)
    assert r.returncode == 0, r.stderr
    r = _riot(["history", "plan", str(sid)], studio)
    assert r.returncode == 0, r.stderr
    assert "agent:prompteur" in r.stdout and "Elle sort vite" in r.stdout and "rythme" in r.stdout


def test_r_a4_michael_refuse_depuis_la_cli(conn, clip, studio):
    sid = _shot_ids(conn, clip)[0]
    r = _riot(["ecrire", "plan", str(sid), "words=Usurpé"], studio, {"RIOT_ACTOR": "michael"})
    assert r.returncode == 2 and "régie" in r.stderr
    r = _riot(["--auteur", "michael", "ecrire", "plan", str(sid), "words=Usurpé"], studio)
    assert r.returncode == 2 and "régie" in r.stderr
    assert conn.execute("SELECT words FROM shots WHERE id=?", (sid,)).fetchone()[0] == "Elle sort"
    with pytest.raises(Refused):
        store.author_from_cli("Michael")


def test_r_a4_aucune_ecriture_hors_de_la_fonction_unique():
    import re
    allowed = {"store.py", "migrate.py"}
    pattern = re.compile(r"\b(INSERT\s+(OR\s+\w+\s+)?INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|REPLACE\s+INTO)\b", re.I)
    offenders = [f"{p.name}" for p in (REPO / "riotmachine").rglob("*.py")
                 if p.name not in allowed and pattern.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"écritures SQL hors de store : {offenders}"


# --- R-A6 ------------------------------------------------------------------------

def test_r_a6_deux_generations_deux_versions_en_base_et_sur_disque(conn, clip, studio):
    from riotmachine.providers.simulation import SimulatedProvider
    sid = _shot_ids(conn, clip)[0]
    sim = SimulatedProvider()
    for n in (1, 2):
        with store.revision(conn, "code:planificateur") as rev:
            gid = generations.request(rev, f"plan:{sid}:essai:{n}", object_type="shots", object_id=sid,
                                      provider="simulation", kind="prise", payload={"n": n}, est_cost=0.64)
        assert generations.send(conn, gid, sim) == "envoyee"
    while generations.poll(conn, {"simulation": sim}) == 0:
        pass
    rows = conn.execute("SELECT path FROM generations WHERE object_id=? ORDER BY id", (sid,)).fetchall()
    paths = [Path(r[0]) for r in rows]
    assert len(paths) == 2 and paths[0] != paths[1] and all(p.is_file() for p in paths)
    assert [p.name for p in paths] == ["prise-v001.mp4", "prise-v002.mp4"]


def test_r_a6_un_fichier_existant_n_est_jamais_ecrase(tmp_path):
    a = files.save_version(b"un", tmp_path, "image", ".png")
    b = files.save_version(b"deux", tmp_path, "image", ".png")
    assert a.read_bytes() == b"un" and b.read_bytes() == b"deux"
    assert not list(tmp_path.glob(".*.part"))


def test_r_a6_suppression_logique_et_restaurable_d_un_plan_qui_a_des_prises(conn, clip):
    sid = _shot_ids(conn, clip)[0]
    with store.revision(conn, "code:planificateur") as rev:
        generations.request(rev, "k1", object_type="shots", object_id=sid, provider="simulation", kind="prise",
                            payload={}, est_cost=0.64)
    with store.revision(conn, store.MICHAEL, "retire") as rev:
        rev.delete("shots", sid)
    assert conn.execute("SELECT COUNT(*) FROM shots WHERE id=?", (sid,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM generations WHERE object_id=?", (sid,)).fetchone()[0] == 1
    with store.revision(conn, store.MICHAEL, "remet") as rev:
        rev.restore("shots", sid)
    assert views.shot_page(conn, sid)["shot"]["deleted_at"] is None
    with pytest.raises(RiotError):
        with store.revision(conn, store.MICHAEL) as rev:
            rev.update("shots", 999, {"t_end": 1})
