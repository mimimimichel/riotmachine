"""Petits outils communs aux adaptateurs : clés, images, téléchargement."""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
from pathlib import Path

import httpx


class ProviderError(Exception):
    pass


def key(env: str) -> str:
    value = os.environ.get(env, "").strip()
    if not value:
        raise ProviderError(f"{env} manquant dans .env")
    return value


def image_parts(ref: str) -> tuple[str, str]:
    """(type MIME, base64 brut) d'une image donnée en data URI ou en URL https."""
    m = re.match(r"data:([^;]+);base64,(.*)$", ref, re.S)
    if m:
        return m.group(1), m.group(2)
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        r = c.get(ref)
    if r.status_code >= 400:
        raise ProviderError(f"Image de départ illisible ({r.status_code}) : {ref[:120]}")
    mime = r.headers.get("content-type", "image/png").split(";")[0]
    return mime, base64.b64encode(r.content).decode()


def check(r: httpx.Response, who: str) -> dict:
    if r.status_code >= 400:
        raise ProviderError(f"{who} a refusé la requête ({r.status_code}) : {r.text[:600]}")
    try:
        return r.json()
    except ValueError as exc:
        raise ProviderError(f"Réponse illisible de {who} : {r.text[:300]}") from exc


def download(url: str, dest: Path, headers: dict | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if url.startswith("data:"):
        tmp.write_bytes(base64.b64decode(url.split(",", 1)[1]))
    else:
        with httpx.Client(timeout=300, follow_redirects=True) as c, c.stream("GET", url, headers=headers or {}) as r:
            if r.status_code >= 400:
                raise ProviderError(f"Téléchargement impossible ({r.status_code}) : {url[:160]}")
            with tmp.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
    tmp.replace(dest)
    return dest


def strip_audio(path: Path) -> Path:
    """Retire la piste son d'une vidéo (la musique vient de Suno)."""
    if path.suffix.lower() not in (".mp4", ".mov", ".webm") or not shutil.which("ffmpeg"):
        return path
    out = path.with_name(path.stem + ".noaudio" + path.suffix)
    proc = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-an", "-c:v", "copy", str(out)],
                          capture_output=True)
    if proc.returncode == 0:
        out.replace(path)
    return path
