"""Google Cloud Vertex AI (Gemini Enterprise Agent Platform) : Veo 3.1, image vers vidéo.

C'est la voie qui consomme les crédits Google Cloud (essai de 300 $). L'API
Gemini d'AI Studio, elle, n'est pas payable par ces crédits.

Authentification, au choix (.env) :
  - VERTEX_API_KEY : clé API liée à un compte de service (la plus simple) ;
  - GOOGLE_APPLICATION_CREDENTIALS : chemin du JSON d'un compte de service
    (rôle « Vertex AI User »), ou le fichier de connexion du compte Google de
    Michael (gcloud auth application-default login), échangé contre un jeton OAuth.
Plus VERTEX_PROJECT (identifiant du projet). Région : us-central1 (seule ouverte à Veo).

Soumission : :predictLongRunning ; suivi : :fetchPredictOperation ; la vidéo revient
en base64 dans la réponse (pas de bucket nécessaire). Spécifications vérifiées le 22/10/2026.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

from . import _http

REGION = "us-central1"
_token: dict = {}


def _project() -> str:
    return _http.key("VERTEX_PROJECT")


def _auth() -> tuple[dict, dict]:
    """(headers, query params) selon la méthode configurée."""
    api_key = os.environ.get("VERTEX_API_KEY", "").strip()
    if api_key:
        return {"Content-Type": "application/json"}, {"key": api_key}
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not creds_path:
        raise _http.ProviderError("Vertex AI : ni VERTEX_API_KEY ni GOOGLE_APPLICATION_CREDENTIALS dans .env")
    if not _token or _token["exp"] < time.time() + 120:
        # Compte de service (JSON) ou compte Google de Michael (gcloud auth application-default login).
        import google.auth
        from google.auth.transport.requests import Request
        creds, _ = google.auth.load_credentials_from_file(
            creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"], quota_project_id=_project())
        creds.refresh(Request())
        headers: dict = {}
        creds.apply(headers)
        _token.update(headers=headers, exp=time.time() + 3300)
    return {**_token["headers"], "Content-Type": "application/json"}, {}


def _model_url(model_id: str, verb: str) -> str:
    return (f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{_project()}/locations/{REGION}"
            f"/publishers/google/models/{model_id}:{verb}")


def submit(model_cfg: dict, payload: dict) -> dict:
    if model_cfg.get("kind") == "image":
        return _submit_image(model_cfg, payload)
    mime, b64 = _http.image_parts(payload.get("image") or "")
    params = {"aspectRatio": payload.get("aspect_ratio") or "16:9", "durationSeconds": int(payload.get("duration") or 8),
              "resolution": payload.get("resolution") or "720p", "generateAudio": False, "sampleCount": 1,
              "resizeMode": "crop", "personGeneration": "allow_adult"}
    if payload.get("negative_prompt"):
        params["negativePrompt"] = payload["negative_prompt"]
    if payload.get("seed") is not None:
        params["seed"] = int(payload["seed"]) % 4294967295
    body = {"instances": [{"prompt": payload.get("prompt") or "",
                           "image": {"bytesBase64Encoded": b64, "mimeType": mime}}],
            "parameters": params}
    headers, query = _auth()
    with httpx.Client(timeout=120) as c:
        data = _http.check(c.post(_model_url(model_cfg["endpoint"], "predictLongRunning"), headers=headers,
                                  params=query, json=body), "Vertex AI")
    op = data.get("name")
    if not op:
        raise _http.ProviderError(f"Réponse Vertex inattendue : {str(data)[:300]}")
    return {"request_id": op.rsplit("/", 1)[-1], "status_url": op, "response_url": model_cfg["endpoint"]}


# --- Images : Nano Banana (Gemini Image) sur Vertex, payées par les crédits Google ---
# L'appel est synchrone : l'image est rangée dans studio/work/vertex/ et le suivi
# (status/result) la relit. Point d'accès global (les modèles image n'y sont qu'en global).

def _image_store() -> Path:
    from ..settings import get_settings
    d = Path(get_settings().studio_root) / "work" / "vertex"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _submit_image(model_cfg: dict, payload: dict) -> dict:
    import base64
    import uuid
    parts = []
    for uri in payload.get("images") or []:
        mime, b64 = _http.image_parts(uri)
        parts.append({"inlineData": {"mimeType": mime, "data": b64}})
    parts.append({"text": payload.get("prompt") or model_cfg.get("fixed_prompt") or ""})
    img_cfg = {"aspectRatio": payload.get("aspect_ratio") or "1:1"}
    if payload.get("resolution"):
        img_cfg["imageSize"] = payload["resolution"]
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": img_cfg}}
    url = (f"https://aiplatform.googleapis.com/v1/projects/{_project()}/locations/global"
           f"/publishers/google/models/{model_cfg['endpoint']}:generateContent")
    headers, query = _auth()
    with httpx.Client(timeout=300) as c:
        data = _http.check(c.post(url, headers=headers, params=query, json=body), "Vertex AI (image)")
    rid = uuid.uuid4().hex[:12]
    path = _image_store() / f"{rid}.json"
    for cand in data.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                (_image_store() / f"{rid}.png").write_bytes(base64.b64decode(inline["data"]))
                path.write_text('{"ok": true}')
                return {"request_id": rid, "status_url": f"vertex-image://{rid}", "response_url": f"vertex-image://{rid}"}
    reason = ((data.get("candidates") or [{}])[0].get("finishReason") or
              (data.get("promptFeedback") or {}).get("blockReason") or "aucune image")
    path.write_text(json_dumps({"error": f"Nano Banana n'a rendu aucune image ({reason})"}))
    return {"request_id": rid, "status_url": f"vertex-image://{rid}", "response_url": f"vertex-image://{rid}"}


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _image_job(job: dict) -> dict | None:
    url = str(job.get("status_url", ""))
    if not url.startswith("vertex-image://"):
        return None
    import json
    rid = url.split("://", 1)[1]
    meta = _image_store() / f"{rid}.json"
    return {"rid": rid, **(json.loads(meta.read_text()) if meta.exists() else {"error": "image perdue"})}


def _operation(job: dict) -> dict:
    headers, query = _auth()
    with httpx.Client(timeout=300) as c:
        return _http.check(c.post(_model_url(job["response_url"], "fetchPredictOperation"), headers=headers,
                                  params=query, json={"operationName": job["status_url"]}), "Vertex AI")


def status(job: dict) -> str:
    img = _image_job(job)
    if img is not None:
        return "FAILED" if img.get("error") else "COMPLETED"
    op = _operation(job)
    if not op.get("done"):
        return "IN_PROGRESS"
    return "FAILED" if op.get("error") else "COMPLETED"


def result(job: dict) -> dict:
    img = _image_job(job)
    if img is not None:
        if img.get("error"):
            raise _http.ProviderError(img["error"])
        return {"images": [{"url": f"vertex-image://{img['rid']}"}]}
    op = _operation(job)
    if op.get("error"):
        raise _http.ProviderError(f"Vertex AI : {op['error'].get('message', op['error'])}")
    resp = op.get("response") or {}
    videos = resp.get("videos") or []
    if not videos:
        filtered = resp.get("raiMediaFilteredCount")
        why = "; ".join(resp.get("raiMediaFilteredReasons") or [])
        raise _http.ProviderError(f"Veo n'a rendu aucune vidéo{' (refusée par la modération' + (' : ' + why if why else '') + ')' if filtered else ''}")
    v = videos[0]
    if v.get("bytesBase64Encoded"):
        return {"video": {"url": f"data:{v.get('mimeType', 'video/mp4')};base64,{v['bytesBase64Encoded']}"}}
    raise _http.ProviderError("Veo a rendu la vidéo dans un bucket : mode non pris en charge")


def download(url: str, dest: Path) -> Path:
    if url.startswith("vertex-image://"):
        import shutil
        src = _image_store() / f"{url.split('://', 1)[1]}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), dest)
        return dest
    return _http.strip_audio(_http.download(url, dest))
