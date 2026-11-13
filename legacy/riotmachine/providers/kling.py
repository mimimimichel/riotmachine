"""Kling AI, API officielle (api-singapore.klingai.com), nouvelle API à clé.

POST /image-to-video/{modèle} puis GET /tasks?task_ids=... Pas de negative prompt
ni de ratio en image vers vidéo : la sortie suit le ratio de l'image de départ, et
les négations passent dans le prompt. Spécifications vérifiées le 22/10/2026.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from . import _http

BASE = "https://api-singapore.klingai.com"
ENV = "KLING_API_KEY"


def _headers() -> dict:
    return {"Authorization": f"Bearer {_http.key(ENV)}", "Content-Type": "application/json"}


def submit(model_cfg: dict, payload: dict) -> dict:
    prompt = payload.get("prompt") or ""
    if payload.get("negative_prompt"):
        prompt = f"{prompt}\nAvoid: {payload['negative_prompt']}."
    image = payload.get("image") or ""
    if image.startswith("data:"):
        image = image.split(",", 1)[1]   # Kling attend le base64 brut, sans préfixe
    settings = dict(model_cfg.get("settings") or {})
    for k in ("resolution", "duration"):
        if payload.get(k) is not None:
            settings[k] = int(payload[k]) if k == "duration" else payload[k]
    body = {"contents": [{"type": "prompt", "text": prompt[:2500]}, {"type": "first_frame", "url": image}],
            "settings": settings, "options": {"watermark_info": {"enabled": False}}}
    with httpx.Client(timeout=60) as c:
        data = _http.check(c.post(f"{BASE}/image-to-video/{model_cfg['endpoint']}", headers=_headers(),
                                  json=body), "Kling")
    tid = (data.get("data") or {}).get("id")
    if not tid:
        raise _http.ProviderError(f"Réponse Kling inattendue : {str(data)[:300]}")
    url = f"{BASE}/tasks?task_ids={tid}"
    return {"request_id": tid, "status_url": url, "response_url": url}


def _task(job: dict) -> dict:
    with httpx.Client(timeout=30) as c:
        data = _http.check(c.get(job["status_url"], headers=_headers()), "Kling")
    items = data.get("data") or []
    return items[0] if items else {}


def status(job: dict) -> str:
    st = _task(job).get("status", "")
    return {"submitted": "IN_QUEUE", "processing": "IN_PROGRESS", "succeeded": "COMPLETED",
            "failed": "FAILED"}.get(st, "IN_PROGRESS")


def result(job: dict) -> dict:
    t = _task(job)
    if t.get("status") != "succeeded":
        raise _http.ProviderError(f"Kling : {t.get('message') or t.get('status')}")
    videos = [o for o in (t.get("outputs") or []) if o.get("type") == "video"]
    if not videos:
        raise _http.ProviderError("Kling : aucune vidéo dans la réponse")
    return {"video": {"url": videos[0]["url"]}}


def download(url: str, dest: Path) -> Path:
    return _http.strip_audio(_http.download(url, dest))
