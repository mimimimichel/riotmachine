"""Aiguillage des générations vers les fournisseurs.

Chaque modèle de config/models.yaml déclare son fournisseur (`provider`). Ce
module envoie la requête au bon adaptateur, puis le worker suit la génération
avec `status` et `result`, et la production récupère le fichier avec `download`.

Un adaptateur expose :
    submit(model_cfg, payload) -> {"request_id", "status_url", "response_url"}
    status(job) -> "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED"
    result(job) -> dict (réponse brute du fournisseur, lue avec `output` du modèle)
    download(url, dest) -> Path

En simulation (pas de clé fal, ou clip de démo), tout passe par le simulateur de
fal : aucune requête payante, des images et vidéos factices.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import fal
from ..settings import get_settings


from ._http import ProviderError  # noqa: E402,F401


def _adapters() -> dict[str, Any]:
    from . import atlas, evolink, gemini, kling, minimax, replicate, runway, vertex
    return {"fal": fal_adapter, "kling": kling, "vertex": vertex, "gemini": gemini, "runway": runway,
            "minimax": minimax, "atlas": atlas, "replicate": replicate, "evolink": evolink}


def simulated(provider: str = "fal") -> bool:
    """Fournisseur simulé : pas de clé dans .env (ou RIOT_FAL_MOCK=1 pour tout simuler)."""
    from .. import routing
    return routing._forced_simulation() or not routing.provider_has_key(provider)


def submit(model_cfg: dict, payload: dict, *, kind: str, label: str = "", seconds: float | None = None,
           force_mock: bool = False) -> dict[str, str]:
    provider = model_cfg.get("provider", "fal")
    if force_mock or simulated(provider):
        sub = fal.submit(model_cfg.get("endpoint", ""), payload, kind=kind, label=label, seconds=seconds,
                         force_mock=True)
    else:
        adapter = _adapters().get(provider)
        if adapter is None:
            raise ProviderError(f"Fournisseur inconnu : {provider}")
        sub = adapter.submit(model_cfg, payload)
    return {**sub, "provider": provider}


def _adapter_for(job: dict):
    if str(job.get("status_url", "")).startswith("mock://"):
        return fal_adapter
    return _adapters()[job.get("provider") or "fal"]


def status(job: dict) -> str:
    return _adapter_for(job).status(job)


def result(job: dict) -> dict[str, Any]:
    return _adapter_for(job).result(job)


def download(url: str, dest: Path, provider: str = "fal") -> Path:
    if url.startswith("mock://") or provider == "fal":
        return fal.download(url, dest)
    return _adapters()[provider].download(url, dest)


class fal_adapter:  # noqa: N801 - espace de noms, comme les modules des autres fournisseurs
    """fal.ai : file d'attente queue.fal.run (voir riotmachine/fal.py)."""

    @staticmethod
    def submit(model_cfg: dict, payload: dict) -> dict[str, str]:
        return fal.submit(model_cfg["endpoint"], payload)

    @staticmethod
    def status(job: dict) -> str:
        return fal.status(job["status_url"])

    @staticmethod
    def result(job: dict) -> dict[str, Any]:
        return fal.result(job["response_url"])

    @staticmethod
    def download(url: str, dest: Path) -> Path:
        return fal.download(url, dest)
