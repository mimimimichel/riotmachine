"""Le worker réveille Claude Code au bon moment, sans clé API, et sans boucle infinie."""

import os
import stat
import time

from riotmachine import cli, db, production, settings, worker


def test_wakes_claude_once(studio, monkeypatch, tmp_path):
    fake = tmp_path / "claude"
    record = tmp_path / "appel.txt"
    fake.write_text(f"#!/bin/sh\necho \"$@\" > {record}\necho \"cle=${{ANTHROPIC_API_KEY:-absente}}\" >> {record}\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("RIOT_CLAUDE_BIN", str(fake))
    monkeypatch.setenv("RIOT_AGENTS_ENABLED", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ne-doit-pas-passer")
    settings.reset_caches()

    cli.main(["init"])
    conn = db.connect()
    script = tmp_path / "s.md"
    script.write_text("un script", encoding="utf-8")
    production.create_clip(conn, "Réveil", song=studio["song"], script_file=script, characters=["jj"])

    assert worker.wake_agents(conn) == ["reveil"]
    for _ in range(50):
        if record.exists() and "cle=" in record.read_text():
            break
        time.sleep(0.1)
    worker._reap_agents(conn)
    content = record.read_text()
    assert "-p /prod reveil" in content
    assert "--permission-mode acceptEdits" in content
    assert "cle=absente" in content

    # même situation, l'agent n'a rien fait avancer : pas de nouveau réveil immédiat
    assert worker.wake_agents(conn) == []
    # la situation change (nouveau retour, nouveau plan…) : réveil
    conn.execute("UPDATE clips SET stage='decoupage_review' WHERE slug='reveil'")
    conn.execute("INSERT INTO reviews (clip_slug, gate, decision, comment, created_at) "
                 "VALUES ('reveil','decoupage','change','plus court',?)", (db.now(),))
    assert worker.wake_agents(conn) == ["reveil"]
    os.environ.pop("ANTHROPIC_API_KEY", None)
