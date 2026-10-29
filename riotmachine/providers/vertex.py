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


def _operation(job: dict) -> dict:
    headers, query = _auth()
    with httpx.Client(timeout=300) as c:
        return _http.check(c.post(_model_url(job["response_url"], "fetchPredictOperation"), headers=headers,
                                  params=query, json={"operationName": job["status_url"]}), "Vertex AI")


def status(job: dict) -> str:
    op = _operation(job)
    if not op.get("done"):
        return "IN_PROGRESS"
    return "FAILED" if op.get("error") else "COMPLETED"


def result(job: dict) -> dict:
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
    return _http.strip_audio(_http.download(url, dest))
