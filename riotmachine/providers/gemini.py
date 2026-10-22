"""API Gemini (AI Studio) : Gemini Omni Flash, image vers vidéo.

Veo 3.1 n'y est plus disponible depuis le 22/10/2026. Omni génère toujours du son :
la piste est retirée après téléchargement. Pas de format 1:1, pas de negative prompt.
Cette API n'est pas payable par les crédits Google Cloud. Spécifications vérifiées le 22/10/2026.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from . import _http

BASE = "https://generativelanguage.googleapis.com/v1beta"
ENV = "GEMINI_API_KEY"


def _headers() -> dict:
    return {"x-goog-api-key": _http.key(ENV), "Content-Type": "application/json"}


def submit(model_cfg: dict, payload: dict) -> dict:
    mime, b64 = _http.image_parts(payload.get("image") or "")
    prompt = payload.get("prompt") or ""
    if payload.get("negative_prompt"):
        prompt = f"{prompt} Avoid: {payload['negative_prompt']}."
    body = {"model": model_cfg["endpoint"],
            "input": [{"type": "image", "data": b64, "mime_type": mime}, {"type": "text", "text": prompt}],
            "response_format": {"type": "video", "aspect_ratio": payload.get("aspect_ratio") or "16:9",
                                "resolution": payload.get("resolution") or "720p",
                                "duration": f"{int(payload.get('duration') or 6)}s", "delivery": "uri"},
            "generation_config": {"video_config": {"task": "image_to_video"}},
            "background": True}
    with httpx.Client(timeout=120) as c:
        data = _http.check(c.post(f"{BASE}/interactions", headers=_headers(), json=body), "Gemini")
    iid = data.get("id") or (data.get("name") or "").rsplit("/", 1)[-1]
    if not iid:
        raise _http.ProviderError(f"Réponse Gemini inattendue : {str(data)[:300]}")
    url = f"{BASE}/interactions/{iid}"
    return {"request_id": iid, "status_url": url, "response_url": url}


def _get(url: str) -> dict:
    with httpx.Client(timeout=60) as c:
        return _http.check(c.get(url, headers=_headers()), "Gemini")


def status(job: dict) -> str:
    st = _get(job["status_url"]).get("status", "")
    if st in ("queued",):
        return "IN_QUEUE"
    if st == "completed":
        return "COMPLETED"
    if st in ("failed", "cancelled", "incomplete"):
        return "FAILED"
    return "IN_PROGRESS"


def result(job: dict) -> dict:
    data = _get(job["status_url"])
    if data.get("status") != "completed":
        raise _http.ProviderError(f"Gemini : {data.get('status')} {str(data.get('error') or '')[:300]}")
    for step in data.get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for item in step.get("content") or []:
            if item.get("type") == "video":
                if item.get("data"):
                    return {"video": {"url": f"data:video/mp4;base64,{item['data']}"}}
                if item.get("uri"):
                    return {"video": {"url": item["uri"]}}
    raise _http.ProviderError("Gemini : aucune vidéo dans la réponse")


def download(url: str, dest: Path) -> Path:
    if url.startswith("data:"):
        return _http.strip_audio(_http.download(url, dest))
    # fichier : on attend qu'il soit prêt, puis on le télécharge
    file_id = url.split("files/")[-1].split(":")[0].split("?")[0]
    for _ in range(40):
        if _get(f"{BASE}/files/{file_id}").get("state") == "ACTIVE":
            break
        import time
        time.sleep(3)
    return _http.strip_audio(_http.download(f"{BASE}/files/{file_id}:download?alt=media", dest, _headers()))
