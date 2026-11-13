"""Tout en simulation, dans un studio temporaire : aucune dépense, aucun fichier du dépôt touché."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def studio(tmp_path, monkeypatch):
    root = tmp_path / "studio"
    root.mkdir()
    monkeypatch.setenv("RIOT_STUDIO_ROOT", str(root))
    monkeypatch.setenv("RIOT_DB_V3", str(root / "riot-v3.db"))
    monkeypatch.delenv("RIOT_ACTOR", raising=False)
    return root


@pytest.fixture
def conn(studio):
    from riotmachine import db
    c = db.open_db()
    yield c
    c.close()


@pytest.fixture
def clip(conn):
    """Un clip de 2 blocs et 4 plans, écrit par Michael."""
    from riotmachine import decoupage, store
    with store.revision(conn, store.MICHAEL, "création") as rev:
        cid = rev.create("clips", {"slug": "test", "title": "Clip de test", "brief": "Le brief de Michael"})
        decoupage.import_decoupage(rev, cid, {"blocks": [
            {"name": "Intro", "intention": "Ouvrir sur la rue", "shots": [
                {"t_start": 0, "t_end": 3, "words": "Elle sort"},
                {"t_start": 3, "t_end": 5.5, "words": "Elle ferme à clé"}]},
            {"name": "Couplet", "intention": "La marche", "shots": [
                {"t_start": 5.5, "t_end": 9.5, "words": "Descend vers le vélo"},
                {"t_start": 9.5, "t_end": 12, "words": "Essuie la selle"}]}]})
    return cid


@pytest.fixture(scope="session")
def v1_db(tmp_path_factory) -> Path:
    """Une base v1 (schéma 8) fabriquée par le code de legacy/ : démo + clip de 12 blocs et 64 plans."""
    work = tmp_path_factory.mktemp("v1")
    studio = work / "studio"
    studio.mkdir()
    shutil.copytree(REPO / "studio" / "characters", studio / "characters")
    env = {**os.environ, "RIOT_STUDIO_ROOT": str(studio), "RIOT_DB": str(studio / "riot.db"),
           "RIOT_FAL_MOCK": "1", "RIOT_AGENTS_ENABLED": "0", "PYTHONPATH": str(REPO / "legacy"),
           "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}
    for k in [k for k in env if k.endswith("_API_KEY") or k in ("FAL_KEY", "VERTEX_PROJECT")]:
        env[k] = ""
    r = subprocess.run([sys.executable, str(REPO / "tests" / "fixtures" / "make_v8_db.py")], env=env,
                       cwd=work, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    return studio / "riot.db"
