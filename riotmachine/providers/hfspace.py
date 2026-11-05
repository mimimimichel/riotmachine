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
    # Spaces officiels testés en gratuit le 31/10/2026 (Qwen Image Edit 2511 réserve 360 s de GPU par
    # appel : refusé hors compte PRO, retiré).
    "flux2-dev": "black-forest-labs/FLUX.2-dev",          # plusieurs images en entrée, ~40 s
    "kontext-dev": "black-forest-labs/FLUX.1-Kontext-Dev",  # une image en entrée, ~30 s
}
QUOTA_WORDS = ("quota", "exceeded", "gpu time", "too many requests", "rate limit", "gpu duration")


def generate(space: str, prompt: str, images: list[Path], dest: Path, *, width: int = 1024, height: int = 768,
             seed: int | None = None) -> Path:
    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:   # dépendance absente
        raise _http.ProviderError("gradio_client n'est pas installé") from exc
    token = os.environ.get("HF_TOKEN", "").strip() or None
    width, height = _fit(width, height)
    try:
        client = Client(SPACES[space], token=token, verbose=False)
        if space == "kontext-dev":
            if not images:
                raise _http.ProviderError("FLUX.1 Kontext a besoin d'une image")
            # une seule image : la plus récente de Michael
            res = client.predict(handle_file(str(images[-1])), prompt, seed or 0, seed is None, 2.5, 20,
                                 api_name="/infer")
        else:
            gallery = [{"image": handle_file(str(p)), "caption": None} for p in images[:3]]
            # 20 étapes : au-delà, la réservation de GPU dépasse ce que le gratuit accepte
            res = client.predict(prompt, gallery, seed or 0, seed is None, width, height, 20, 4.0, False,
                                 api_name="/infer")
    except _http.ProviderError:
        raise
    except Exception as exc:   # le client gradio lève des types variés
        msg = str(exc)
        # Un Space ZeroGPU qui refuse le GPU (quota du jour, file saturée) renvoie un AppError
        # dont le message est seulement « RuntimeError » : ce n'est pas une panne du Space.
        if any(w in msg.lower() for w in QUOTA_WORDS) or type(exc).__name__ == "RuntimeError" \
                or msg.strip() in ("RuntimeError", "None", ""):
            raise _http.ProviderError("GPU gratuit refusé (quota du jour épuisé ou file saturée), "
                                      "réessaie plus tard ou prends un autre modèle") from exc
        raise _http.ProviderError(f"indisponible pour l'instant ({type(exc).__name__}: {msg[:120]})") from exc
    path = _first_image(res)
    if not path:
        raise _http.ProviderError(f"Hugging Face ({space}) : réponse sans image")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, dest)
    return dest


def _fit(width: int, height: int, limit: int = 1024) -> tuple[int, int]:
    """Les Spaces FLUX refusent un côté au-delà de 1024 px : on réduit en gardant le format (multiples de 16)."""
    k = min(1.0, limit / max(width, height))
    return int(width * k) // 16 * 16, int(height * k) // 16 * 16


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
