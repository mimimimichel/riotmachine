"""Hugging Face Spaces (ZeroGPU) : brouillons d'images gratuits.

Les Spaces officiels de Qwen et Black Forest Labs tournent sur les GPU gratuits
de Hugging Face. Quota de calcul par jour, renouvelé 24 h après le premier usage
(documentation vérifiée le 31/10/2026) : 2 min sans compte, 5 min avec un compte
gratuit (jeton HF_TOKEN, facultatif). Rien ne peut être facturé : quota épuisé,
l'appel est refusé.

Ces Spaces sont des pages publiques : leur interface peut changer. En cas
d'erreur, la chaîne de brouillons passe à l'option gratuite suivante.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import _http

SPACES = {
    # clé : (Space, nom de l'endpoint, construction des arguments)
    "qwen-edit-2511": "Qwen/Qwen-Image-Edit-2511",
    "flux2-dev": "black-forest-labs/FLUX.2-dev",
}
QUOTA_WORDS = ("quota", "exceeded", "gpu time", "zerogpu", "too many requests", "rate limit")


def generate(space: str, prompt: str, images: list[Path], dest: Path, *, width: int = 1024, height: int = 768,
             seed: int | None = None) -> Path:
    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:   # dépendance absente
        raise _http.ProviderError("gradio_client n'est pas installé") from exc
    token = os.environ.get("HF_TOKEN", "").strip() or None
    try:
        client = Client(SPACES[space], hf_token=token, verbose=False)
        gallery = [{"image": handle_file(str(p)), "caption": None} for p in images[:3]]
        if space == "qwen-edit-2511":
            res = client.predict(gallery, prompt, seed or 0, seed is None, 4.0, 40, height, width, False,
                                 api_name="/infer")
        else:
            res = client.predict(prompt, gallery, seed or 0, seed is None, width, height, 28, 4.0, False,
                                 api_name="/infer")
    except Exception as exc:   # le client gradio lève des types variés
        msg = str(exc)
        if any(w in msg.lower() for w in QUOTA_WORDS):
            raise _http.ProviderError(f"Quota gratuit Hugging Face du jour épuisé ({space})") from exc
        raise _http.ProviderError(f"Hugging Face ({space}) : {msg[:200]}") from exc
    path = _first_image(res)
    if not path:
        raise _http.ProviderError(f"Hugging Face ({space}) : réponse sans image")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, dest)
    return dest


def _first_image(res) -> str | None:
    """Les Spaces renvoient un chemin, une liste, une galerie ou un tuple (image, graine)."""
    if isinstance(res, str) and Path(res).is_file():
        return res
    if isinstance(res, dict):
        for k in ("image", "path", "value"):
            v = res.get(k)
            found = _first_image(v) if v is not None else None
            if found:
                return found
    if isinstance(res, (list, tuple)):
        for x in res:
            found = _first_image(x)
            if found:
                return found
    return None
