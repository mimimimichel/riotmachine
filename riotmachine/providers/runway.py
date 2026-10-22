"""Runway API (api.dev.runwayml.com), image vers vidéo.

Runway revend aussi Veo 3.1, Kling 3, Seedance, Wan, Hailuo et Grok Imagine :
un modèle = une valeur de `model` dans `defaults`. Spécifications vérifiées le 22/10/2026.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from . import _http

BASE = "https://api.dev.runwayml.com"
VERSION = "2024-11-06"
ENV = "RUNWAYML_API_SECRET"
MAX_DATA_URI = 5 * 1024 * 1024   # 5 Mo après encodage


def _headers() -> dict:
    return {"Authorization": f"Bearer {_http.key(ENV)}", "X-Runway-Version": VERSION,
            "Content-Type": "application/json"}


def submit(model_cfg: dict, payload: dict) -> dict:
    body = dict(payload)
    ratio = body.get("ratio")
    ratios = model_cfg.get("ratios") or {}
    if ratio in ratios:
        body["ratio"] = ratios[ratio]
    elif ratios and ratio not in ratios.values():
        body.pop("ratio", None)   # format non proposé par ce modèle : Runway suit l'image
    image = body.get("promptImage")
    if isinstance(image, str) and image.startswith("data:") and len(image) > MAX_DATA_URI:
        raise _http.ProviderError("Image de départ trop lourde pour Runway (5 Mo encodés max)")
    with httpx.Client(timeout=60) as c:
        data = _http.check(c.post(f"{BASE}/v1/image_to_video", headers=_headers(), json=body), "Runway")
    tid = data.get("id")
    if not tid:
        raise _http.ProviderError(f"Réponse Runway inattendue : {data}")
    url = f"{BASE}/v1/tasks/{tid}"
    return {"request_id": tid, "status_url": url, "response_url": url}


def _task(job: dict) -> dict:
    with httpx.Client(timeout=30) as c:
        return _http.check(c.get(job["status_url"], headers=_headers()), "Runway")


def status(job: dict) -> str:
    st = _task(job).get("status", "")
    return {"PENDING": "IN_QUEUE", "THROTTLED": "IN_QUEUE", "RUNNING": "IN_PROGRESS",
            "SUCCEEDED": "COMPLETED"}.get(st, "FAILED" if st in ("FAILED", "CANCELLED") else "IN_PROGRESS")


def result(job: dict) -> dict:
    t = _task(job)
    if t.get("status") != "SUCCEEDED":
        raise _http.ProviderError(f"Runway : {t.get('failure') or t.get('status')} ({t.get('failureCode', '')})")
    return {"video": {"url": (t.get("output") or [""])[0]}, "cost_credits": (t.get("cost") or {}).get("credits")}


def download(url: str, dest: Path) -> Path:
    return _http.strip_audio(_http.download(url, dest))
