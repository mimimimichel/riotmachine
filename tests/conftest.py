import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def studio(tmp_path, monkeypatch):
    """Studio temporaire en mode simulation, avec JJ et un morceau factice."""
    root = tmp_path / "studio"
    # seulement la version 1 validée de JJ : les tests ne dépendent pas des versions en cours de Michael
    shutil.copytree(REPO / "studio" / "characters", root / "characters",
                    ignore=lambda d, names: [n for n in names if n.startswith("v") and n[1:].isdigit() and n != "v1"])
    monkeypatch.setenv("RIOT_STUDIO_ROOT", str(root))
    monkeypatch.setenv("RIOT_FAL_MOCK", "1")
    monkeypatch.setenv("RIOT_AGENTS_ENABLED", "0")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    from riotmachine import settings
    settings.reset_caches()
    song = tmp_path / "song.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
                    str(song)], check=True)
    yield {"root": root, "song": song, "tmp": tmp_path}
    settings.reset_caches()
