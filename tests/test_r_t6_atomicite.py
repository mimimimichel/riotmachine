"""R-T6 : tout ou rien, révisions annulables, appels extérieurs bornés."""

import httpx
import pytest

from riotmachine import decoupage, http, store, views
from riotmachine.errors import RiotError


def _snapshot(conn):
    return [tuple(r) for r in conn.execute("SELECT id, num, t_start, t_end, words, production_text, deleted_at "
                                           "FROM shots ORDER BY id")]


def test_r_t6_une_erreur_en_cours_laisse_la_base_dans_l_etat_d_avant(conn, clip):
    before = _snapshot(conn)
    n_changes = conn.execute("SELECT COUNT(*) FROM changes").fetchone()[0]
    n_revs = conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
    with pytest.raises(RiotError):
        with store.revision(conn, store.MICHAEL, "découpage") as rev:
            rev.update("shots", 1, {"t_end": 4.0})
            rev.delete("shots", 2)
            rev.update("shots", 999, {"t_end": 1.0})            # erreur au milieu
    assert _snapshot(conn) == before
    assert conn.execute("SELECT COUNT(*) FROM changes").fetchone()[0] == n_changes
    assert conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == n_revs


def test_r_t6_annuler_une_revision_restaure_l_etat_exact(conn, clip):
    before = _snapshot(conn)
    blocks = views.decoupage(conn, clip)
    data = {"blocks": [{"id": blocks[0]["id"], "shots": [{"id": blocks[0]["shots"][0]["id"], "t_end": 2.5}]},
                       {"id": blocks[1]["id"], "shots": [{"id": s["id"]} for s in blocks[1]["shots"]]
                        + [{"t_start": 12, "t_end": 14, "words": "Nouveau plan"}]}]}
    with store.revision(conn, store.MICHAEL, "révision du découpage") as rev:
        decoupage.import_decoupage(rev, clip, data)
    rid = rev.id
    assert _snapshot(conn) != before
    store.undo(conn, rid, store.MICHAEL)
    after = _snapshot(conn)
    created = [r for r in after if r[0] not in {b[0] for b in before}]
    assert [r for r in after if r[0] in {b[0] for b in before}] == before   # état exact
    assert created and all(r[6] is not None for r in created)                # le plan créé est retiré
    with pytest.raises(RiotError, match="déjà annulée"):
        store.undo(conn, rid, store.MICHAEL)


def test_r_t6_annulation_refusee_si_le_champ_a_change_depuis(conn, clip):
    with store.revision(conn, store.MICHAEL, "a") as rev:
        rev.update("shots", 1, {"t_end": 2.0})
    first = rev.id
    with store.revision(conn, store.MICHAEL, "b") as rev:
        rev.update("shots", 1, {"t_end": 2.5})
    with pytest.raises(RiotError, match="a changé"):
        store.undo(conn, first, store.MICHAEL)


def test_r_t6_appels_exterieurs_bornes():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectTimeout("délai", request=request)
    t = httpx.MockTransport(handler)
    with pytest.raises(RiotError, match="ne répond pas"):
        http.call("GET", "https://exemple.test/x", transport=t, sleep=lambda s: None)
    assert calls["n"] == http.MAX_ATTEMPTS
    calls["n"] = 0
    with pytest.raises(RiotError):
        http.call("POST", "https://exemple.test/generer", transport=t, sleep=lambda s: None)
    assert calls["n"] == 1                                   # une génération n'est jamais renvoyée ici
    calls["n"] = 0
    with pytest.raises(RiotError):
        http.call("GET", "https://exemple.test/x", attempts=50, transport=t, sleep=lambda s: None)
    assert calls["n"] == http.MAX_ATTEMPTS                    # plafond infranchissable


def test_r_t6_reponse_5xx_puis_succes():
    seq = iter([503, 200])
    t = httpx.MockTransport(lambda req: httpx.Response(next(seq), json={}))
    assert http.call("GET", "https://exemple.test/x", transport=t, sleep=lambda s: None).status_code == 200
