"""Générations : clé unique, jamais deux fois facturées (R-T5).

Cycle : prevue -> envoi -> envoyee -> recue | refusee | echec, ou a_verifier.

1. `request` crée la génération sous sa clé unique. Rappelée avec la même clé
   (double clic, reprise), elle rend la génération existante.
2. `send` enregistre et valide « envoi » AVANT d'appeler le fournisseur. Une
   génération qui n'est plus « prévue » n'est jamais renvoyée.
3. Au redémarrage, `resume` traite les générations restées « envoi » (le
   processus s'est arrêté pendant l'appel) : le fournisseur la retrouve par sa
   clé s'il le sait, sinon elle passe « à vérifier » et n'est jamais relancée
   d'office (D22).
4. `poll` récupère les résultats ; le coût réel remplace l'estimation, un
   refus non facturé coûte 0.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Mapping

from . import files, settings, store
from .errors import RiotError
from .providers import Provider, ProviderRefused

WORKER = "code:worker"


def get(conn: sqlite3.Connection, gen_id: int) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM generations WHERE id=?", (gen_id,)).fetchone()
    if r is None:
        raise RiotError(f"Génération {gen_id} introuvable.")
    return r


def request(rev: store.Revision, key: str, *, object_type: str, object_id: int, provider: str, kind: str,
            payload: dict, est_cost: float) -> int:
    existing = rev.conn.execute("SELECT id FROM generations WHERE idem_key=?", (key,)).fetchone()
    if existing:
        return existing["id"]
    return rev.create("generations", {
        "idem_key": key, "object_type": object_type, "object_id": object_id, "provider": provider,
        "kind": kind, "payload": json.dumps(payload, ensure_ascii=False, sort_keys=True), "est_cost": est_cost,
        "status": "prevue"})


def send(conn: sqlite3.Connection, gen_id: int, provider: Provider) -> str:
    """Envoie une génération prévue. Rend son statut. Ne renvoie jamais une génération déjà partie."""
    g = get(conn, gen_id)
    if g["status"] != "prevue":
        return g["status"]
    with store.revision(conn, WORKER, "envoi au fournisseur") as rev:
        rev.update("generations", gen_id, {"status": "envoi", "attempts": g["attempts"] + 1})
    try:
        rid = provider.submit(json.loads(g["payload"]), g["idem_key"])
    except ProviderRefused as exc:
        with store.revision(conn, WORKER, "refus du fournisseur") as rev:
            rev.update("generations", gen_id, {"status": "refusee", "error": str(exc), "real_cost": 0.0})
        return "refusee"
    except Exception:
        # Réponse perdue (coupure, délai dépassé) : la demande est peut-être partie.
        # Elle reste « envoi » ; `resume` tranche sans jamais la renvoyer à l'aveugle.
        return "envoi"
    with store.revision(conn, WORKER, "reçue par le fournisseur") as rev:
        rev.update("generations", gen_id, {"status": "envoyee", "request_id": rid})
    return "envoyee"


def resume(conn: sqlite3.Connection, providers: Mapping[str, Provider]) -> list[str]:
    """Au démarrage du worker. Rend les messages pour Michael (générations à vérifier)."""
    messages = []
    for g in conn.execute("SELECT * FROM generations WHERE status='envoi' ORDER BY id").fetchall():
        p = providers.get(g["provider"])
        rid = p.find(g["idem_key"]) if p is not None and p.finds_by_key else None
        with store.revision(conn, WORKER, "reprise après redémarrage") as rev:
            if rid:
                rev.update("generations", g["id"], {"status": "envoyee", "request_id": rid})
            elif p is not None and p.finds_by_key:
                # le fournisseur confirme ne l'avoir jamais reçue : rien n'est parti
                rev.update("generations", g["id"], {"status": "prevue"})
            else:
                msg = (f"Génération {g['id']} ({g['kind']}, {g['provider']}) : le worker s'est arrêté pendant "
                       f"l'envoi et ce fournisseur ne permet pas de la retrouver. Elle n'a pas été relancée. "
                       f"Regarde sur la console du fournisseur si elle y est (clé {g['idem_key']}).")
                rev.update("generations", g["id"], {"status": "a_verifier", "error": msg})
                messages.append(msg)
    return messages


def poll(conn: sqlite3.Connection, providers: Mapping[str, Provider], out_dir: Path | None = None) -> int:
    """Interroge les générations envoyées. Rend le nombre terminées."""
    out_dir = out_dir or settings.generated_dir()
    done = 0
    for g in conn.execute("SELECT * FROM generations WHERE status='envoyee' ORDER BY id").fetchall():
        st = providers[g["provider"]].status(g["request_id"])
        if st.state == "en_cours":
            continue
        values: dict = {"status": st.state if st.state in ("recue", "refusee", "echec") else "echec",
                        "real_cost": float(st.cost or 0.0)}
        if st.state == "recue" and st.content is not None:
            path = files.save_version(st.content, out_dir / g["object_type"] / str(g["object_id"]),
                                      g["kind"], st.ext)
            values["path"] = str(path)
        if st.error:
            values["error"] = st.error
        with store.revision(conn, WORKER, f"résultat : {values['status']}") as rev:
            rev.update("generations", g["id"], values)
        done += 1
    return done
