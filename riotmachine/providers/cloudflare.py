"""Cloudflare Workers AI : brouillons d'images gratuits (FLUX.2 klein).

Le plan gratuit de Cloudflare donne 10 000 « neurones » par jour, renouvelés
chaque jour, sans carte bancaire : environ 90 images 1024 px par jour avec
FLUX.2 [klein] 4B. Sur ce plan, rien ne peut être facturé : au-delà de
l'enveloppe du jour, l'appel est refusé jusqu'au lendemain.

L'appel est synchrone (quelques secondes) : pas de file d'attente.
Jusqu'à 4 images de référence, chacune réduite sous 512 x 512 avant l'envoi.
Spécifications vérifiées le 30/10/2026 (changelog Cloudflare du 15/01/2026).
"""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path

import httpx

from . import _http

ENV_ACCOUNT = "CLOUDFLARE_ACCOUNT_ID"
ENV_TOKEN = "CLOUDFLARE_API_TOKEN"
MODELS = {"klein-4b": "@cf/black-forest-labs/flux-2-klein-4b",
          "klein-9b": "@cf/black-forest-labs/flux-2-klein-9b"}


def _small(src: Path, tmp: Path, i: int) -> Path:
    """Réduit une image sous 512 x 512 (exigence du modèle), en JPEG."""
    out = tmp / f"ref{i}.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf",
                    "scale='min(504,iw)':'min(504,ih)':force_original_aspect_ratio=decrease",
                    "-q:v", "3", str(out)], check=True, capture_output=True)
    return out


def generate(prompt: str, images: list[Path], dest: Path, *, width: int = 1024, height: int = 768,
             seed: int | None = None, model: str = "klein-4b") -> Path:
    """Génère une image et l'écrit dans `dest`. Lève ProviderError en cas de refus."""
    account, token = _http.key(ENV_ACCOUNT), _http.key(ENV_TOKEN)
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODELS[model]}"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        files = []
        for i, p in enumerate(images[:4]):
            small = _small(Path(p), tmp, i)
            files.append((f"input_image_{i}", (small.name, small.read_bytes(), "image/jpeg")))
        data = {"prompt": prompt, "width": str(width), "height": str(height)}
        if seed is not None:
            data["seed"] = str(seed)
        with httpx.Client(timeout=180) as c:
            r = c.post(url, headers={"Authorization": f"Bearer {token}"}, data=data, files=files or None)
    if r.status_code >= 400:
        msg = r.text[:300]
        if r.status_code == 429 or "neuron" in msg.lower() or "limit" in msg.lower():
            raise _http.ProviderError("Enveloppe gratuite Cloudflare du jour épuisée : réessaie demain.")
        raise _http.ProviderError(f"Cloudflare a refusé ({r.status_code}) : {msg}")
    body = r.json()
    b64 = ((body.get("result") or {}).get("image")) or body.get("image")
    if not b64:
        raise _http.ProviderError(f"Réponse Cloudflare sans image : {str(body)[:200]}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(b64))
    return dest
