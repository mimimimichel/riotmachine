"""Configuration : variables d'environnement (.env) + config/models.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Charge un fichier .env simple (CLE=valeur) sans écraser l'environnement."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "oui", "on"}


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    studio_root: Path
    db_path: Path
    models_path: Path
    fal_key: str | None
    fal_mock: bool
    telegram_token: str | None
    telegram_chat_id: str | None
    regie_url: str
    regie_host: str
    regie_port: int
    regie_token: str | None
    poll_seconds: int
    claude_bin: str
    claude_model: str | None
    agent_timeout_s: int
    agent_backoff_s: int
    agents_enabled: bool

    @property
    def characters_dir(self) -> Path:
        return self.studio_root / "characters"

    @property
    def clips_dir(self) -> Path:
        return self.studio_root / "clips"

    @property
    def groups_dir(self) -> Path:
        return self.studio_root / "groups"

    @property
    def logs_dir(self) -> Path:
        return self.studio_root / "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv(REPO_ROOT / ".env")
    studio_root = Path(os.environ.get("RIOT_STUDIO_ROOT", REPO_ROOT / "studio")).expanduser().resolve()
    return Settings(
        repo_root=REPO_ROOT,
        studio_root=studio_root,
        db_path=Path(os.environ.get("RIOT_DB", studio_root / "riot.db")).expanduser(),
        models_path=Path(os.environ.get("RIOT_MODELS", REPO_ROOT / "config" / "models.yaml")),
        fal_key=os.environ.get("FAL_KEY") or None,
        fal_mock=_env_bool("RIOT_FAL_MOCK", default=not os.environ.get("FAL_KEY")),
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID") or None,
        regie_url=os.environ.get("RIOT_REGIE_URL", "http://localhost:8420").rstrip("/"),
        regie_host=os.environ.get("RIOT_REGIE_HOST", "0.0.0.0"),
        regie_port=int(os.environ.get("RIOT_REGIE_PORT", "8420")),
        regie_token=os.environ.get("RIOT_REGIE_TOKEN") or None,
        poll_seconds=int(os.environ.get("RIOT_POLL_SECONDS", "30")),
        claude_bin=os.environ.get("RIOT_CLAUDE_BIN", "claude"),
        claude_model=os.environ.get("RIOT_CLAUDE_MODEL") or None,
        agent_timeout_s=int(os.environ.get("RIOT_AGENT_TIMEOUT", "2400")),
        agent_backoff_s=int(os.environ.get("RIOT_AGENT_BACKOFF", "600")),
        agents_enabled=_env_bool("RIOT_AGENTS_ENABLED", default=True),
    )


@lru_cache(maxsize=1)
def load_models() -> dict:
    """Charge config/models.yaml (table de routage, endpoints, prix)."""
    path = get_settings().models_path
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def reset_caches() -> None:
    """Utilisé par les tests."""
    get_settings.cache_clear()
    load_models.cache_clear()
