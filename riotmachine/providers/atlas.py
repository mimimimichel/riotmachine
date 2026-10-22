"""Atlas Cloud (api.atlascloud.ai), revendeur : Seedance 2.5, Wan 2.6, Kling 3.

Corps plat avec `model`. Prix réel calculé à la fin (au token pour Seedance).
Médias conservés 14 jours. Spécifications vérifiées le 23/10/2026.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from . import _http

BASE = "https://api.atlascloud.ai/api/v1"
ENV = "ATLASCLOUD_API_KEY"


def _headers() -> dict:
    return {"Authorization": f"Bearer {_http.key(ENV)}", "Content-Type": "application/json"}


def submit(model_cfg: dict, payload: dict) -> dict:
    body = {"model": model_cfg["endpoint"], **{k: v for k, v in payload.items() if v is not None}}
    if isinstance(body.get("image"), str) and body["image"].startswith("data:"):
        body["image"] = body["image"].split(",", 1)[1]   # base64 accepté directement
    with httpx.Client(timeout=120) as c:
        data = _http.check(c.post(f"{BASE}/model/generateVideo", headers=_headers(), json=body), "Atlas Cloud")
    pid = (data.get("data") or {}).get("id")
    if not pid:
        raise _http.ProviderError(f"Réponse Atlas Cloud inattendue : {str(data)[:300]}")
    url = f"{BASE}/model/prediction/{pid}"
    return {"request_id": pid, "status_url": url, "response_url": url}


def _get(url: str) -> dict:
    with httpx.Client(timeout=60) as c:
        return _http.check(c.get(url, headers=_headers()), "Atlas Cloud").get("data") or {}


def status(job: dict) -> str:
    st = _get(job["status_url"]).get("status", "")
    if st in ("completed", "succeeded"):
        return "COMPLETED"
    if st == "failed":
        return "FAILED"
    return "IN_PROGRESS"


def result(job: dict) -> dict:
    d = _get(job["status_url"])
    if d.get("status") not in ("completed", "succeeded"):
        raise _http.ProviderError(f"Atlas Cloud : {d.get('error') or d.get('status')}")
    return {"video": {"url": (d.get("outputs") or [""])[0]}}


def download(url: str, dest: Path) -> Path:
    return _http.strip_audio(_http.download(url, dest))
