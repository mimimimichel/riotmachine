"""Client minimal pour la file d'attente fal.ai (queue.fal.run).

Flux : on soumet une requête, fal renvoie request_id + status_url + response_url,
le worker interroge le statut toutes les RIOT_POLL_SECONDS, puis télécharge le
résultat. Pas de webhook : le PC n'a pas besoin d'être joignable depuis internet.

Mode simulation (RIOT_FAL_MOCK=1, actif par défaut sans FAL_KEY) : aucune
requête payante, les images et vidéos sont fabriquées localement avec ffmpeg.
Pratique pour tester toute la chaîne gratuitement.
"""

from __future__ import annotations

import base64
import mimetypes
import subprocess
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from .settings import get_settings

QUEUE_BASE = "https://queue.fal.run"
MAX_DATA_URI_BYTES = 15 * 1024 * 1024


class FalError(Exception):
    pass


def _headers() -> dict[str, str]:
    key = get_settings().fal_key
    if not key:
        raise FalError("FAL_KEY manquant dans .env (ou activer RIOT_FAL_MOCK=1)")
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def is_mock() -> bool:
    return get_settings().fal_mock


def to_data_uri(path: str | Path) -> str:
    """Encode un fichier local pour l'envoyer à fal sans hébergement intermédiaire."""
    p = Path(path)
    data = p.read_bytes()
    if len(data) > MAX_DATA_URI_BYTES:
        raise FalError(f"Fichier trop lourd pour un envoi direct ({len(data) // 1_000_000} Mo) : {p.name}")
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def submit(endpoint: str, payload: dict[str, Any], kind: str = "video", label: str = "",
           seconds: float | None = None, force_mock: bool = False) -> dict[str, str]:
    """Soumet une requête. kind/label/seconds ne servent qu'au mode simulation."""
    if is_mock() or force_mock:
        rid = f"mock-{uuid.uuid4().hex[:12]}"
        q = f"kind={kind}&label={label[:40].replace('&', ' ')}&dur={int(round(seconds or 5))}"
        return {
            "request_id": rid,
            "status_url": f"mock://status/{rid}",
            "response_url": f"mock://result/{rid}?{q}",
        }
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{QUEUE_BASE}/{endpoint}", headers=_headers(), json=payload)
    if r.status_code >= 400:
        raise FalError(f"fal a refusé la requête ({r.status_code}) : {r.text[:500]}")
    data = r.json()
    rid = data.get("request_id")
    if not rid:
        raise FalError(f"Réponse fal inattendue : {data}")
    return {
        "request_id": rid,
        "status_url": data.get("status_url") or f"{QUEUE_BASE}/{endpoint}/requests/{rid}/status",
        "response_url": data.get("response_url") or f"{QUEUE_BASE}/{endpoint}/requests/{rid}",
    }


def status(status_url: str) -> str:
    """Retourne IN_QUEUE, IN_PROGRESS, COMPLETED ou FAILED."""
    if status_url.startswith("mock://"):
        return "COMPLETED"
    with httpx.Client(timeout=30) as client:
        r = client.get(status_url, headers=_headers())
    if r.status_code >= 400:
        raise FalError(f"Statut fal illisible ({r.status_code}) : {r.text[:300]}")
    data = r.json()
    st = str(data.get("status", "")).upper()
    if data.get("error"):
        return "FAILED"
    return st or "IN_PROGRESS"


def result(response_url: str) -> dict[str, Any]:
    if response_url.startswith("mock://"):
        q = parse_qs(urlparse(response_url).query)
        kind = q.get("kind", ["video"])[0]
        label = q.get("label", [""])[0]
        dur = q.get("dur", ["5"])[0]
        url = f"mock://{kind}?label={label}&dur={dur}"
        if kind == "image":
            return {"images": [{"url": url}], "image": {"url": url}, "seed": 42}
        return {"video": {"url": url}, "seed": 42}
    with httpx.Client(timeout=60) as client:
        r = client.get(response_url, headers=_headers())
    if r.status_code >= 400:
        raise FalError(f"Échec de génération ({r.status_code}) : {r.text[:800]}")
    return r.json()


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("mock://"):
        return _mock_render(url, dest)
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        with client.stream("GET", url) as r:
            if r.status_code >= 400:
                raise FalError(f"Téléchargement impossible ({r.status_code}) : {url}")
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
            tmp.replace(dest)
    return dest


def _mock_render(url: str, dest: Path) -> Path:
    """Fabrique une image ou une vidéo factice pour les tests (ffmpeg)."""
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    label = (q.get("label", ["mock"])[0] or "mock").replace(":", " ").replace("'", " ")
    kind = parsed.netloc or "video"
    text = f"drawtext=text='{label}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2"
    if kind == "image":
        # une teinte par plan (la HD garde celle de son visuel) pour que la démo se lise
        import hashlib
        base = label.replace(" HD", "").replace(" image", "")
        palette = ["0x3b2a5c", "0x5c2a4f", "0x2a4a5c", "0x5c4a2a", "0x2a5c45", "0x4a2a5c", "0x5c3a2a", "0x2a3a5c"]
        color = palette[int(hashlib.md5(base.encode()).hexdigest(), 16) % len(palette)]
        size = "1920x1080" if label.endswith("HD") else "1280x720"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
            "-i", f"gradients=s={size}:c0={color}:c1=0x0a0911:x0=0:y0=0:x1=1280:y1=720:d=1",
            "-frames:v", "1", "-vf", text, str(dest),
        ]
    else:
        dur = q.get("dur", ["5"])[0]
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
            "-i", f"testsrc2=s=854x480:d={dur}:r=24", "-vf", text,
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(dest),
        ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # ffmpeg sans drawtext (police absente) : on refait sans texte
        cmd = [c for c in cmd if c not in ("-vf", text)]
        subprocess.run(cmd, check=True, capture_output=True)
    return dest
