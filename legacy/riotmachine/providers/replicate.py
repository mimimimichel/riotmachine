"""Replicate (api.replicate.com) : Seedance 2.5, Wan 2.6, Wan 2.7.

Fichiers purgés une heure après la prédiction : la machine télécharge tout de suite.
Image locale envoyée en data URI. Spécifications vérifiées le 23/10/2026.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from . import _http

BASE = "https://api.replicate.com/v1"
ENV = "REPLICATE_API_TOKEN"


def _headers() -> dict:
    return {"Authorization": f"Bearer {_http.key(ENV)}", "Content-Type": "application/json"}


def submit(model_cfg: dict, payload: dict) -> dict:
    inputs = {k: v for k, v in payload.items() if v is not None}
    with httpx.Client(timeout=120) as c:
        data = _http.check(c.post(f"{BASE}/models/{model_cfg['endpoint']}/predictions", headers=_headers(),
                                  json={"input": inputs}), "Replicate")
    pid = data.get("id")
    if not pid:
        raise _http.ProviderError(f"Réponse Replicate inattendue : {str(data)[:300]}")
    url = (data.get("urls") or {}).get("get") or f"{BASE}/predictions/{pid}"
    return {"request_id": pid, "status_url": url, "response_url": url}


def _get(url: str) -> dict:
    with httpx.Client(timeout=60) as c:
        return _http.check(c.get(url, headers=_headers()), "Replicate")


def status(job: dict) -> str:
    st = _get(job["status_url"]).get("status", "")
    return {"starting": "IN_QUEUE", "processing": "IN_PROGRESS", "succeeded": "COMPLETED"}.get(
        st, "FAILED" if st in ("failed", "canceled") else "IN_PROGRESS")


def result(job: dict) -> dict:
    d = _get(job["status_url"])
    if d.get("status") != "succeeded":
        raise _http.ProviderError(f"Replicate : {d.get('error') or d.get('status')}")
    out = d.get("output")
    return {"video": {"url": out[0] if isinstance(out, list) else out}}


def download(url: str, dest: Path) -> Path:
    return _http.strip_audio(_http.download(url, dest, {"Authorization": f"Bearer {_http.key(ENV)}"}))
