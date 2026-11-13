"""Interface commune des fournisseurs. Les connecteurs réels reviennent au lot 5.

Un fournisseur expose :
- `name` ;
- `finds_by_key` : il sait retrouver une génération par notre clé unique (D22) ;
- `submit(payload, key) -> request_id` ; lève `ProviderRefused` pour un refus net ;
- `find(key) -> request_id | None` (si `finds_by_key`) ;
- `status(request_id) -> Status`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..errors import RiotError


class ProviderRefused(RiotError):
    """Le fournisseur refuse la demande, sans la facturer."""


@dataclass
class Status:
    state: str                 # en_cours | recue | refusee | echec
    cost: float = 0.0          # coût réel facturé
    content: bytes | None = None
    ext: str = ".bin"
    error: str | None = None


class Provider(Protocol):
    name: str
    finds_by_key: bool

    def submit(self, payload: dict, key: str) -> str: ...
    def find(self, key: str) -> str | None: ...
    def status(self, request_id: str) -> Status: ...
