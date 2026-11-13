"""R-T5 : clé unique par génération ; une coupure, un redémarrage ou un double clic ne relance rien."""

import pytest

from riotmachine import db, generations, store
from riotmachine.providers.simulation import SimulatedProvider


class Coupure(BaseException):
    """Le processus du worker meurt (kill) : rien après ce point ne s'exécute."""


def _request(conn, key="lot:1:prise:1", provider="simulation"):
    with store.revision(conn, "code:planificateur", "accord de Michael") as rev:
        return generations.request(rev, key, object_type="shots", object_id=1, provider=provider,
                                   kind="prise", payload={"prompt": "JJ sort"}, est_cost=0.64)


def _poll_until_done(conn, providers):
    for _ in range(5):
        if generations.poll(conn, providers):
            return
    raise AssertionError("génération jamais terminée")


def test_r_t5_worker_tue_pendant_l_envoi_une_seule_facture_et_resultat_recupere(studio):
    conn = db.open_db()
    sim = SimulatedProvider()

    def kill():
        raise Coupure()
    sim.after_submit = kill                    # la demande arrive chez le fournisseur, puis le worker meurt
    gid = _request(conn)
    with pytest.raises(Coupure):
        generations.send(conn, gid, sim)
    conn.close()

    sim.after_submit = None                    # redémarrage du worker
    conn = db.open_db()
    assert generations.get(conn, gid)["status"] == "envoi"
    assert generations.resume(conn, {"simulation": sim}) == []
    assert generations.send(conn, gid, sim) == "envoyee"      # déjà partie : rien n'est renvoyé
    _poll_until_done(conn, {"simulation": sim})
    g = generations.get(conn, gid)
    assert sim.submissions == 1 and sim.billed == 0.64
    assert g["status"] == "recue" and g["real_cost"] == 0.64 and g["path"]


def test_r_t5_worker_tue_pendant_le_suivi(studio):
    conn = db.open_db()
    sim = SimulatedProvider()
    gid = _request(conn)
    generations.send(conn, gid, sim)
    conn.close()
    conn = db.open_db()                          # redémarrage : la génération est suivie, pas relancée
    generations.resume(conn, {"simulation": sim})
    _poll_until_done(conn, {"simulation": sim})
    assert sim.submissions == 1 and generations.get(conn, gid)["status"] == "recue"


def test_r_t5_fournisseur_sans_recherche_par_cle_passe_a_verifier(studio):
    conn = db.open_db()
    sim = SimulatedProvider(name="aveugle", finds_by_key=False)

    def kill():
        raise Coupure()
    sim.after_submit = kill
    gid = _request(conn, provider="aveugle")
    with pytest.raises(Coupure):
        generations.send(conn, gid, sim)
    sim.after_submit = None
    msgs = generations.resume(conn, {"aveugle": sim})
    g = generations.get(conn, gid)
    assert g["status"] == "a_verifier" and len(msgs) == 1 and "n'a pas été relancée" in msgs[0]
    assert generations.send(conn, gid, sim) == "a_verifier"   # jamais relancée d'office
    assert sim.submissions == 1


def test_r_t5_double_clic_une_seule_generation(studio):
    conn = db.open_db()
    sim = SimulatedProvider()
    a = _request(conn)
    b = _request(conn)
    assert a == b
    assert conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0] == 1
    generations.send(conn, a, sim)
    generations.send(conn, b, sim)
    assert sim.submissions == 1


def test_r_t5_refus_non_facture_coute_zero(studio):
    conn = db.open_db()
    sim = SimulatedProvider(refuse=True)
    gid = _request(conn)
    assert generations.send(conn, gid, sim) == "refusee"
    g = generations.get(conn, gid)
    assert g["real_cost"] == 0 and "refusée" in g["error"] and sim.billed == 0


def test_r_t5_reponse_perdue_ne_relance_pas(studio):
    """Un délai dépassé pendant l'envoi : la demande est peut-être partie, elle n'est pas renvoyée."""
    conn = db.open_db()
    sim = SimulatedProvider()

    def timeout():
        raise TimeoutError("délai dépassé")
    sim.after_submit = timeout
    gid = _request(conn)
    assert generations.send(conn, gid, sim) == "envoi"
    sim.after_submit = None
    assert generations.send(conn, gid, sim) == "envoi"
    generations.resume(conn, {"simulation": sim})
    _poll_until_done(conn, {"simulation": sim})
    assert sim.submissions == 1 and generations.get(conn, gid)["status"] == "recue"
