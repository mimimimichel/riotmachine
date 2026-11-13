"""Fournisseur simulé : tout le développement se fait avec lui, sans dépense.

Il tient un registre côté « serveur » (ce qu'un vrai fournisseur aurait reçu et
facturé), ce qui permet aux tests de vérifier qu'une génération n'est jamais
facturée deux fois.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ProviderRefused, Status


@dataclass
class SimulatedProvider:
    name: str = "simulation"
    finds_by_key: bool = True
    price: float = 0.64
    jobs: dict[str, dict] = field(default_factory=dict)       # request_id -> travail reçu
    by_key: dict[str, str] = field(default_factory=dict)      # clé -> request_id
    submissions: int = 0
    refuse: bool = False
    after_submit: object = None                               # appelé après réception (tests : « coupure »)

    @property
    def billed(self) -> float:
        return round(sum(j["billed"] for j in self.jobs.values()), 4)

    def submit(self, payload: dict, key: str) -> str:
        self.submissions += 1
        if self.refuse:
            raise ProviderRefused("Demande refusée par le fournisseur simulé (non facturée).")
        rid = f"sim-{len(self.jobs) + 1}"
        self.jobs[rid] = {"payload": payload, "key": key, "billed": self.price, "polls": 0}
        self.by_key[key] = rid
        if callable(self.after_submit):
            self.after_submit()
        return rid

    def find(self, key: str) -> str | None:
        return self.by_key.get(key)

    def status(self, request_id: str) -> Status:
        job = self.jobs[request_id]
        job["polls"] += 1
        if job["polls"] < 2:
            return Status("en_cours")
        return Status("recue", cost=job["billed"], content=f"SIMULATION {request_id}".encode(), ext=".mp4")
