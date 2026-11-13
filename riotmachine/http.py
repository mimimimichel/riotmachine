"""Appels extérieurs : délai et nombre d'essais toujours bornés (R-T6).

Seules les requêtes sans effet (GET, HEAD) sont réessayées par défaut. Une
requête qui peut créer quelque chose chez le fournisseur (POST d'une
génération) n'est jamais réessayée ici : c'est `generations` qui tranche (R-T5).
"""

from __future__ import annotations

import time
from typing import Callable
from urllib.parse import urlparse

import httpx

from .errors import RiotError

TIMEOUT_S = 30.0
MAX_ATTEMPTS = 3
_SAFE = {"GET", "HEAD"}


def call(method: str, url: str, *, timeout: float = TIMEOUT_S, attempts: int | None = None,
         retry_unsafe: bool = False, transport: httpx.BaseTransport | None = None,
         sleep: Callable[[float], None] = time.sleep, **kwargs) -> httpx.Response:
    method = method.upper()
    if attempts is None:
        attempts = MAX_ATTEMPTS if (method in _SAFE or retry_unsafe) else 1
    attempts = max(1, min(int(attempts), MAX_ATTEMPTS))
    host = urlparse(url).netloc or url
    last: Exception | None = None
    for i in range(attempts):
        try:
            with httpx.Client(timeout=timeout, transport=transport) as c:
                r = c.request(method, url, **kwargs)
            if r.status_code >= 500 and i < attempts - 1:
                last = RiotError(f"{host} a répondu {r.status_code}")
                sleep(2 ** i)
                continue
            return r
        except httpx.TransportError as exc:      # délai dépassé, connexion coupée
            last = exc
            if i < attempts - 1:
                sleep(2 ** i)
    raise RiotError(f"{host} ne répond pas ({last}) après {attempts} essai{'s' if attempts > 1 else ''} "
                    f"de {timeout:.0f} s au plus. Réessaie plus tard.")
