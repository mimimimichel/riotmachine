"""Fichiers produits : chaque version est un nouveau fichier, jamais écrasé (R-A6)."""

from __future__ import annotations

import os
from pathlib import Path


def save_version(content: bytes, dest_dir: Path, stem: str, ext: str) -> Path:
    """Écrit `content` dans `<stem>-vNNN<ext>`, au premier numéro libre.

    Le fichier est d'abord écrit à côté, puis lié sous son nom final : le lien
    échoue si le nom existe déjà, donc un fichier existant n'est jamais écrasé,
    et une coupure ne laisse jamais un fichier final à moitié écrit.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / f".{stem}.{os.getpid()}.part"
    tmp.write_bytes(content)
    try:
        n = 1
        while True:
            target = dest_dir / f"{stem}-v{n:03d}{ext}"
            try:
                os.link(tmp, target)
                return target
            except FileExistsError:
                n += 1
    finally:
        tmp.unlink(missing_ok=True)
