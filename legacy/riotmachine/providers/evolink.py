"""EvoLink (api.evolink.ai), revendeur : Kling 3.0.

L'image de départ doit être une URL publique (la base64 n'est pas documentée) :
les visuels HD hébergés par fal conviennent. Spécifications vérifiées le 23/10/2026.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from . import _http

BASE = "https://api.evolink.ai/v1"
ENV = "EVOLINK_API_KEY"


def _headers() -> dict:
    return {"Authorization": f"Bearer {_http.key(ENV)}", "Content-Type": "application/json"}


def submit(model_cfg: dict, payload: dict) -> dict:
    image = payload.get("image_start") or ""
    if not image.startswith("http"):
        raise _http.ProviderError("EvoLink demande une URL publique pour l'image de départ")
    body = {"model": model_cfg["endpoint"], **{k: v for k, v in payload.items() if v is not None}}
    with httpx.Client(timeout=120) as c:
        data = _http.check(c.post(f"{BASE}/videos/generations", headers=_headers(), json=body), "EvoLink")
    tid = data.get("id") or data.get("task_id") or (data.get("data") or {}).get("id")
    if not tid:
        raise _http.ProviderError(f"Réponse EvoLink inattendue : {str(data)[:300]}")
    url = f"{BASE}/tasks/{tid}"
    return {"request_id": tid, "status_url": url, "response_url": url}


def _get(url: str) -> dict:
    with httpx.Client(timeout=60) as c:
        d = _http.check(c.get(url, headers=_headers()), "EvoLink")
    return d.get("data") or d


def status(job: dict) -> str:
    st = _get(job["status_url"]).get("status", "")
    return {"pending": "IN_QUEUE", "processing": "IN_PROGRESS", "completed": "COMPLETED"}.get(
        st, "FAILED" if st == "failed" else "IN_PROGRESS")


def result(job: dict) -> dict:
    d = _get(job["status_url"])
    if d.get("status") != "completed":
        raise _http.ProviderError(f"EvoLink : {d.get('error') or d.get('status')}")
    return {"video": {"url": (d.get("results") or [""])[0]}}


def download(url: str, dest: Path) -> Path:
    return _http.strip_audio(_http.download(url, dest))
