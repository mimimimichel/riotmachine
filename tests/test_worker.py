"""Les agents Claude ne partent que sur accord (R-T1), avec coût mesuré et plafonds (R-T4)."""

import json
import os
import stat
import time

from riotmachine import agents, cli, db, production, settings, worker

RESULT = {"type": "result", "subtype": "success", "total_cost_usd": 0.42, "num_turns": 7,
          "usage": {"input_tokens": 1000, "cache_read_input_tokens": 500, "output_tokens": 300}}


def _fake_claude(tmp_path, monkeypatch, backoff="600"):
    fake = tmp_path / "claude"
    record = tmp_path / "appel.txt"
    fake.write_text(f"#!/bin/sh\necho \"$@\" > {record}\necho \"cle=${{ANTHROPIC_API_KEY:-absente}}\" >> {record}\n"
                    f"echo '{json.dumps(RESULT)}'\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("RIOT_CLAUDE_BIN", str(fake))
    monkeypatch.setenv("RIOT_AGENTS_ENABLED", "1")
    monkeypatch.setenv("RIOT_AGENT_BACKOFF", backoff)
    settings.reset_caches()
    return record


def _wait_done(conn):
    for _ in range(50):
        agents.reap(conn)
        if not agents._running:
            return
        time.sleep(0.1)


def _clip(conn, studio, tmp_path, title="Réveil"):
    script = tmp_path / "s.md"
    script.write_text("un script", encoding="utf-8")
    production.create_clip(conn, title, song=studio["song"], script_file=script, characters=["jj"])


def test_r_t1_agent_waits_for_michael(studio, monkeypatch, tmp_path):
    record = _fake_claude(tmp_path, monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ne-doit-pas-passer")
    cli.main(["init"])
    conn = db.connect()
    _clip(conn, studio, tmp_path)

    # le worker dépose une demande, il ne lance rien
    assert worker.wake_agents(conn) == []
    assert not record.exists()
    req = agents.pending(conn)
    assert len(req) == 1 and req[0]["status"] == "pending" and req[0]["command"] == "/prod reveil"
    assert req[0]["reasons"]
    # dix tours de plus : toujours une seule demande, aucun lancement
    for _ in range(10):
        assert worker.wake_agents(conn) == []
    assert len(agents.pending(conn)) == 1

    db.set_actor("michael")
    agents.decide(conn, req[0]["id"], True)
    db.set_actor("worker")
    assert worker.wake_agents(conn) == ["reveil"]
    _wait_done(conn)
    content = record.read_text()
    assert "-p /prod reveil" in content and "--max-budget-usd 1.00" in content
    assert "--output-format json" in content and "agents-permissions.json" in content
    assert "cle=absente" in content
    run = conn.execute("SELECT * FROM agent_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert run["cost_usd"] == 0.42 and run["turns"] == 7 and run["tokens_in"] == 1500 and run["tokens_out"] == 300
    assert run["requested_by"] == "michael"

    # même situation après le passage : pas de nouvelle demande
    assert worker.wake_agents(conn) == []
    assert agents.pending(conn) == []
    # la situation change : nouvelle demande, estimée sur le passage mesuré
    conn.execute("UPDATE clips SET stage='decoupage_review' WHERE slug='reveil'")
    conn.execute("INSERT INTO reviews (clip_slug, gate, decision, comment, created_at) "
                 "VALUES ('reveil','decoupage','change','plus court',?)", (db.now(),))
    worker.wake_agents(conn)
    (r2,) = agents.pending(conn)
    assert r2["status"] == "pending" and r2["est_usd"] == 0.42
    os.environ.pop("ANTHROPIC_API_KEY", None)


def test_r_t1_refused_and_withdrawn(studio, monkeypatch, tmp_path):
    _fake_claude(tmp_path, monkeypatch)
    cli.main(["init"])
    conn = db.connect()
    _clip(conn, studio, tmp_path)
    worker.wake_agents(conn)
    (r,) = agents.pending(conn)
    agents.decide(conn, r["id"], False)
    assert worker.wake_agents(conn) == []
    assert conn.execute("SELECT status FROM agent_queue WHERE id=?", (r["id"],)).fetchone()[0] == "refused"
    # le besoin disparaît : une demande en attente devient sans objet
    conn.execute("UPDATE clips SET stage='done' WHERE slug='reveil'")
    conn.execute("INSERT INTO agent_queue (key, command, reasons, fingerprint, status, created_at, updated_at) "
                 "VALUES ('reveil','/prod reveil','[]','x','pending',?,?)", (db.now(), db.now()))
    conn.execute("UPDATE clips SET stage='script' WHERE slug='reveil'")
    monkeypatch.setattr(production, "needs_agent", lambda c, s: {"reasons": [], "fingerprint": "z"})
    worker.wake_agents(conn)
    assert agents.pending(conn) == []


def test_r_t4_auto_mode_under_day_cap(studio, monkeypatch, tmp_path):
    record = _fake_claude(tmp_path, monkeypatch)
    cli.main(["init"])
    conn = db.connect()
    agents.put(conn, "agent_mode", "auto")
    agents.put(conn, "claude_day_cap_usd", 0.5)
    agents.put(conn, "claude_run_cap_usd", 0.4)
    _clip(conn, studio, tmp_path)
    assert worker.wake_agents(conn) == ["reveil"]
    _wait_done(conn)
    assert "--max-budget-usd 0.40" in record.read_text()
    assert agents.spent_today(conn) == 0.42
    # plafond du jour atteint : la demande suivante attend Michael
    conn.execute("UPDATE clips SET stage='decoupage_review' WHERE slug='reveil'")
    conn.execute("INSERT INTO reviews (clip_slug, gate, decision, comment, created_at) "
                 "VALUES ('reveil','decoupage','change','plus court',?)", (db.now(),))
    assert worker.wake_agents(conn) == []
    (r,) = agents.pending(conn)
    assert r["status"] == "pending"


def test_r_t1_idle_means_no_agent(studio, monkeypatch, tmp_path):
    """Sans clip à traiter : aucun lancement, aucune demande."""
    record = _fake_claude(tmp_path, monkeypatch)
    cli.main(["init"])
    conn = db.connect()
    for _ in range(20):
        assert worker.wake_agents(conn) == []
    assert agents.pending(conn) == [] and not record.exists()


def test_waits_for_michael_script(studio, monkeypatch, tmp_path):
    """Timecodes manquants : pas de nouvelle demande tant que Michael ne modifie pas son script."""
    _fake_claude(tmp_path, monkeypatch, backoff="0")
    cli.main(["init"])
    conn = db.connect()
    production.create_clip(conn, "Sans temps", song=studio["song"], script_text="Une idée, pas de timecodes",
                           characters=["jj"])
    worker.wake_agents(conn)
    (r,) = agents.pending(conn)
    agents.decide(conn, r["id"], True)
    assert worker.wake_agents(conn) == ["sans-temps"]
    _wait_done(conn)
    time.sleep(1.1)
    assert worker.wake_agents(conn) == []          # même avec un délai d'attente nul
    assert agents.pending(conn) == []
    production.update_script(conn, "sans-temps", "Plan 1 — 0:00.0 → 0:04.0 — JJ chante")
    worker.wake_agents(conn)
    assert len(agents.pending(conn)) == 1


def test_r_t4_settings_validated(studio):
    cli.main(["init"])
    conn = db.connect()
    import pytest
    with pytest.raises(ValueError):
        agents.put(conn, "agent_mode", "toujours")
    with pytest.raises(ValueError):
        agents.put(conn, "claude_day_cap_usd", -1)
    agents.put(conn, "claude_day_cap_usd", 5)
    assert agents.config(conn)["day_cap_usd"] == 5.0
