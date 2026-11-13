"""Chemins de la v3. La base v3 est distincte de la base v1 (D17)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def studio_root() -> Path:
    return Path(os.environ.get("RIOT_STUDIO_ROOT", REPO_ROOT / "studio")).expanduser().resolve()


def db_path() -> Path:
    return Path(os.environ.get("RIOT_DB_V3", studio_root() / "riot-v3.db")).expanduser()


def backups_dir() -> Path:
    return studio_root() / "backups"


def generated_dir() -> Path:
    """Fichiers produits par les générations, versionnés (R-A6)."""
    return studio_root() / "generations"
