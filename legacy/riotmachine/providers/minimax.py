"""MiniMax, API officielle (api.minimax.io).

Deux API : V2 pour H3 / H3-Max (`content` avec image first_frame, `ratio` adaptatif),
V1 pour Hailuo 2.3 / 2.3-Fast (`first_frame_image`, puis récupération du fichier).
Pas de negative prompt (passé dans le prompt). H3 produit toujours du son : retiré
après téléchargement. Spécifications vérifiées le 23/10/2026.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from . import _http

BASE = "https://api.minimax.io"
ENV = "MINIMAX_API_KEY"


def _headers() -> dict:
    return {"Authorization": f"Bearer {_http.key(ENV)}", "Content-Type": "application/json"}


def _prompt(payload: dict) -> str:
    p = payload.get("prompt") or ""
    return f"{p} Avoid: {payload['negative_prompt']}." if payload.get("negative_prompt") else p


def submit(model_cfg: dict, payload: dict) -> dict:
    model = model_cfg["endpoint"]
    image = payload.get("image") or ""
    if model_cfg.get("api") == "v1":
        body = {"model": model, "first_frame_image": image, "prompt": _prompt(payload), "prompt_optimizer": False,
                "duration": int(payload.get("duration") or 6), "resolution": payload.get("resolution") or "768P"}
        url, path = f"{BASE}/v1/video_generation", "v1"
    else:
        body = {"model": model, "content": [{"type": "text", "text": _prompt(payload)},
                                            {"type": "image_url", "image_url": {"url": image}, "role": "first_frame"}],
                "resolution": payload.get("resolution") or "768P", "duration": int(payload.get("duration") or 6),
                "ratio": "adaptive"}
        url, path = f"{BASE}/v2/video_generation", "v2"
    with httpx.Client(timeout=120) as c:
        data = _http.check(c.post(url, headers=_headers(), json=body), "MiniMax")
    base = data.get("base_resp") or {}
    if base.get("status_code"):
        raise _http.ProviderError(f"MiniMax : {base.get('status_msg')} (code {base.get('status_code')})")
    tid = data.get("task_id")
    if not tid:
        raise _http.ProviderError(f"Réponse MiniMax inattendue : {str(data)[:300]}")
    status_url = (f"{BASE}/v1/query/video_generation?task_id={tid}" if path == "v1"
                  else f"{BASE}/v2/query/video_generation/{tid}")
    return {"request_id": tid, "status_url": status_url, "response_url": status_url}


def _get(url: str) -> dict:
    with httpx.Client(timeout=60) as c:
        return _http.check(c.get(url, headers=_headers()), "MiniMax")


def status(job: dict) -> str:
    d = _get(job["status_url"])
    st = (d.get("task") or {}).get("status") or d.get("status") or ""
    st = st.lower()
    if st in ("queued", "preparing", "queueing"):
        return "IN_QUEUE"
    if st in ("succeeded", "success"):
        return "COMPLETED"
    if st in ("failed", "fail", "cancelled"):
        return "FAILED"
    return "IN_PROGRESS"


def result(job: dict) -> dict:
    d = _get(job["status_url"])
    task = d.get("task")
    if task is not None:   # API V2
        if task.get("status") != "succeeded":
            raise _http.ProviderError(f"MiniMax : {(task.get('error') or {}).get('message') or task.get('status')}")
        return {"video": {"url": (task.get("content") or {}).get("url")}}
    if d.get("status") != "Success":   # API V1
        raise _http.ProviderError(f"MiniMax : {d.get('status')} {(d.get('base_resp') or {}).get('status_msg', '')}")
    f = _get(f"{BASE}/v1/files/retrieve?file_id={d['file_id']}")
    return {"video": {"url": (f.get("file") or {}).get("download_url")}}


def download(url: str, dest: Path) -> Path:
    return _http.strip_audio(_http.download(url, dest))
