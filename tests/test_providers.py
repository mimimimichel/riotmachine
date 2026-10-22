"""Adaptateurs des fournisseurs : format exact des requêtes et lecture des réponses,
avec un faux serveur HTTP (aucune requête réelle, aucune dépense)."""

import base64
import json

import httpx
import pytest

from riotmachine import providers, routing
from riotmachine.providers import gemini, kling, runway, vertex

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode()
MP4 = base64.b64encode(b"fake mp4").decode()


@pytest.fixture
def fake_http(monkeypatch):
    """Remplace httpx.Client par un client branché sur un faux serveur. Retourne la liste des requêtes."""
    calls = []
    routes = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append({"method": request.method, "url": str(request.url), "headers": dict(request.headers), "json": body})
        for (method, needle), resp in routes.items():
            if request.method == method and needle in str(request.url):
                return httpx.Response(200, json=resp(body) if callable(resp) else resp)
        return httpx.Response(404, json={"error": "route inconnue"})

    real = httpx.Client

    def client(*a, **kw):
        kw.pop("follow_redirects", None)
        return real(transport=httpx.MockTransport(handler), follow_redirects=True, timeout=5)

    monkeypatch.setattr(httpx, "Client", client)
    return calls, routes


def test_runway(fake_http, monkeypatch):
    calls, routes = fake_http
    monkeypatch.setenv("RUNWAYML_API_SECRET", "rw")
    routes[("POST", "/v1/image_to_video")] = {"id": "t1"}
    routes[("GET", "/v1/tasks/t1")] = {"status": "SUCCEEDED", "output": ["https://out/v.mp4"], "cost": {"credits": 60}}
    cfg = routing.model("veo-31-fast-runway")
    payload = routing.build_payload(cfg, prompt="p", image_urls=[PNG], duration=6, seed=3, negative_prompt="blur",
                                    aspect_ratio="16:9")
    sub = runway.submit(cfg, payload)
    sent = calls[0]
    assert sent["headers"]["x-runway-version"] == "2024-11-06" and sent["headers"]["authorization"] == "Bearer rw"
    assert sent["json"] == {"model": "veo3.1_fast", "audio": False, "promptText": "p", "promptImage": PNG,
                            "duration": 6, "seed": 3, "negativePrompt": "blur", "ratio": "1920:1080"}
    job = {**sub, "provider": "runway"}
    assert runway.status(job) == "COMPLETED"
    assert runway.result(job)["video"]["url"] == "https://out/v.mp4"
    # Grok Lite : pas de ratio du clip, un ratio « auto » fixe
    g = routing.model("grok-lite-runway")
    runway.submit(g, routing.build_payload(g, prompt="p", image_urls=[PNG], duration=4, aspect_ratio="16:9"))
    assert calls[-1]["json"]["ratio"] == "auto_720p"


def test_kling(fake_http, monkeypatch):
    calls, routes = fake_http
    monkeypatch.setenv("KLING_API_KEY", "kl")
    routes[("POST", "/image-to-video/kling-2.6")] = {"data": {"id": "k1", "status": "submitted"}}
    routes[("GET", "/tasks?task_ids=k1")] = {"data": [{"status": "succeeded",
                                                      "outputs": [{"type": "video", "url": "https://k/v.mp4"}]}]}
    cfg = routing.model("kling-26-direct")
    payload = routing.build_payload(cfg, prompt="she turns", image_urls=[PNG], duration=5, negative_prompt="blur",
                                    mode="draft")
    sub = kling.submit(cfg, payload)
    body = calls[0]["json"]
    assert calls[0]["url"] == "https://api-singapore.klingai.com/image-to-video/kling-2.6"
    assert body["contents"][0] == {"type": "prompt", "text": "she turns\nAvoid: blur."}
    assert body["contents"][1]["url"] == PNG.split(",", 1)[1]          # base64 brut
    assert body["settings"] == {"audio": "off", "resolution": "1080p", "duration": 5}
    assert kling.status(sub) == "COMPLETED" and kling.result(sub)["video"]["url"] == "https://k/v.mp4"


def test_vertex(fake_http, monkeypatch):
    calls, routes = fake_http
    monkeypatch.setenv("VERTEX_PROJECT", "mon-projet")
    monkeypatch.setenv("VERTEX_API_KEY", "vx")
    op = "projects/mon-projet/locations/us-central1/publishers/google/models/veo-3.1-fast-generate-001/operations/op1"
    routes[("POST", ":predictLongRunning")] = {"name": op}
    routes[("POST", ":fetchPredictOperation")] = {"done": True, "response": {
        "videos": [{"bytesBase64Encoded": MP4, "mimeType": "video/mp4"}]}}
    cfg = routing.model("veo-31-fast-vertex")
    payload = routing.build_payload(cfg, prompt="p", image_urls=[PNG], duration=6, seed=9, negative_prompt="blur",
                                    aspect_ratio="9:16", mode="final")
    sub = vertex.submit(cfg, payload)
    sent = calls[0]
    assert "us-central1-aiplatform.googleapis.com/v1/projects/mon-projet/locations/us-central1/publishers/google/models/veo-3.1-fast-generate-001:predictLongRunning" in sent["url"]
    assert "key=vx" in sent["url"]
    params = sent["json"]["parameters"]
    assert params["generateAudio"] is False and params["aspectRatio"] == "9:16" and params["durationSeconds"] == 6
    assert params["resolution"] == "1080p" and params["negativePrompt"] == "blur"
    assert sent["json"]["instances"][0]["image"] == {"bytesBase64Encoded": PNG.split(",", 1)[1], "mimeType": "image/png"}
    assert calls and vertex.status(sub) == "COMPLETED"
    assert calls[-1]["json"] == {"operationName": op}
    url = vertex.result(sub)["video"]["url"]
    assert url.startswith("data:video/mp4;base64,")


def test_gemini(fake_http, monkeypatch):
    calls, routes = fake_http
    monkeypatch.setenv("GEMINI_API_KEY", "gm")
    routes[("POST", "/v1beta/interactions")] = {"id": "i1", "status": "queued"}
    routes[("GET", "/v1beta/interactions/i1")] = {"id": "i1", "status": "completed", "steps": [
        {"type": "model_output", "content": [{"type": "video", "data": MP4, "mime_type": "video/mp4"}]}]}
    cfg = routing.model("omni-flash-gemini")
    sub = gemini.submit(cfg, routing.build_payload(cfg, prompt="p", image_urls=[PNG], duration=6, aspect_ratio="16:9",
                                                   mode="final"))
    body = calls[0]["json"]
    assert calls[0]["headers"]["x-goog-api-key"] == "gm"
    assert body["response_format"]["duration"] == "6s" and body["response_format"]["resolution"] == "1080p"
    assert body["background"] is True and body["input"][0]["type"] == "image"
    assert gemini.status(sub) == "COMPLETED"
    assert gemini.result(sub)["video"]["url"].startswith("data:video/mp4;base64,")


def test_provider_errors_are_readable(fake_http, monkeypatch):
    calls, routes = fake_http
    monkeypatch.setenv("RUNWAYML_API_SECRET", "rw")
    routes[("GET", "/v1/tasks/t2")] = {"status": "FAILED", "failure": "Contenu refusé", "failureCode": "SAFETY"}
    job = {"status_url": "https://api.dev.runwayml.com/v1/tasks/t2", "provider": "runway"}
    assert runway.status(job) == "FAILED"
    with pytest.raises(providers.ProviderError, match="Contenu refusé"):
        runway.result(job)
    monkeypatch.delenv("KLING_API_KEY", raising=False)
    with pytest.raises(providers.ProviderError, match="KLING_API_KEY"):
        kling.submit(routing.model("kling-26-direct"), {"prompt": "x", "image": PNG})


def test_cheapest_respects_format_duration_and_credits(studio, monkeypatch):
    from riotmachine import cli, db, settings
    cli.main(["init"])
    shot = {"motion": "low", "framing": "CU", "t_start": 0, "t_end": 4, "aspect_ratio": "16:9"}
    key, _ = routing.cheapest_for("eco", shot)
    assert not routing.model(key).get("to_test")
    # format carré : jamais Veo ni Omni
    square = {**shot, "aspect_ratio": "1:1"}
    for m in routing.model_options(square):
        if m["aspects"] and "1:1" not in m["aspects"]:
            assert not m["fits"]
    # plan de 12 s : jamais un modèle limité à 8 s
    long = {**shot, "t_end": 12}
    assert not routing.fits_shot(routing.model("veo-31-fast-vertex"), long, "eco")
    # crédits Google Cloud ouverts : Veo passe devant, à coût effectif nul
    cfg = routing.models_cfg()
    cfg["providers"]["vertex"]["credits"] = {"label": "crédits Google Cloud", "usd": 300, "start": "", "expires": ""}
    try:
        key, _ = routing.cheapest_for("standard", {**shot, "motion": "medium"})
        assert routing.model(key)["provider"] == "vertex"
        why = routing.route_shot({**shot, "motion": "medium"})["why"]
        assert "crédits Google Cloud" in why
    finally:
        cfg["providers"]["vertex"]["credits"]["usd"] = 0
