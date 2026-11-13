"""La fonction d'écriture unique (R-A1 à R-A4, R-A6, R-T6).

Toute modification de données passe par une révision :

    with store.revision(conn, author, "raison") as rev:
        rev.update("shots", 12, {"t_end": 14.5})

Une révision s'applique entièrement ou pas du tout (une erreur annule tout), et
chaque champ modifié laisse une ligne d'historique : objet, champ, avant, après,
auteur, raison, date. Rien n'est jamais supprimé : `delete` pose `deleted_at`,
`restore` l'enlève. Une révision s'annule d'un geste (`undo`).

Auteurs (D19) : `michael`, `agent:<nom>`, `code:<module>`. Michael peut écrire
tous les champs. Les champs de baseline n'acceptent que Michael, et l'import de
la base v1, qui recopie ses propres mots sans les changer (D26).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from .db import now
from .errors import Refused, RiotError

MICHAEL = "michael"
MIGRATION_V1 = "code:migration-v1"
_AUTHOR = re.compile(r"^(michael|agent:[a-z0-9][a-z0-9-]*|code:[a-z0-9][a-z0-9_.-]*)$")

A, C = "agent", "code"
BASELINE: frozenset[str] = frozenset()   # Michael seul (et la recopie de ses mots à la migration)

# Pour chaque table : champ -> sortes d'auteurs autorisées en plus de Michael.
FIELDS: dict[str, dict[str, frozenset[str]]] = {
    "clips": {"slug": frozenset({C}), "title": frozenset({C}), "brief": BASELINE},
    "blocks": {"clip_id": frozenset({C}), "num": frozenset({A, C}), "name": frozenset({A, C}),
               "intention": BASELINE, "production_notes": frozenset({A, C})},
    "shots": {"clip_id": frozenset({C}), "block_id": frozenset({A, C}), "num": frozenset({A, C}),
              "t_start": frozenset({A, C}), "t_end": frozenset({A, C}),
              "words": BASELINE, "production_text": frozenset({A, C})},
    "feedback": {"object_type": frozenset({C}), "object_id": frozenset({C}), "text": BASELINE,
                 "route": frozenset({A, C}), "result": frozenset({A, C})},
    "generations": {f: frozenset({C}) for f in (
        "idem_key", "object_type", "object_id", "provider", "kind", "payload", "est_cost", "real_cost",
        "status", "request_id", "attempts", "error", "path")},
    "import_v1": {f: frozenset({C}) for f in ("step", "legacy_key", "object_type", "object_id")},
}
# Champs que le code peut fixer à la création (dates d'origine lors d'un import).
_CREATE_ONLY = {"id", "created_at"}
_NAMES = {"clips": "clip", "blocks": "bloc", "shots": "plan", "feedback": "retour",
          "generations": "génération", "import_v1": "import v1"}


def check_author(author: str) -> str:
    if not isinstance(author, str) or not _AUTHOR.match(author):
        raise Refused(f"Auteur invalide : {author!r}. Attendu : michael, agent:<nom> ou code:<module>.")
    return author


def author_from_cli(value: str | None) -> str:
    """Auteur d'une commande `riot` : jamais « michael » (D10), ni en option, ni par RIOT_ACTOR."""
    chosen = value or os.environ.get("RIOT_ACTOR") or "code:cli"
    if chosen.strip().lower() == MICHAEL:
        raise Refused("« michael » ne peut écrire que depuis la régie, où il est authentifié. "
                      "Depuis la CLI, signe agent:<nom> ou code:<module>.")
    return check_author(chosen.strip())


def _kind(author: str) -> str:
    return author.split(":", 1)[0]


def may_write(author: str, table: str, field: str) -> bool:
    if author == MICHAEL:
        return True
    allowed = FIELDS[table][field]
    if allowed is BASELINE:
        return author == MIGRATION_V1
    return _kind(author) in allowed


def _enc(v: Any) -> str | None:
    return None if v is None else json.dumps(v, ensure_ascii=False)


def _dec(v: str | None) -> Any:
    return None if v is None else json.loads(v)


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return float(a) == float(b)
    return a == b


class Revision:
    """Une révision ouverte. Ses écritures sont journalisées et validées ensemble."""

    def __init__(self, conn: sqlite3.Connection, author: str, reason: str | None, undoes: int | None = None):
        self.conn, self.author, self.reason, self._undoes = conn, author, reason, undoes
        self.id: int | None = None

    # -- interne --------------------------------------------------------------
    def _rev_id(self) -> int:
        if self.id is None:
            cur = self.conn.execute(
                "INSERT INTO revisions (author, reason, created_at, undoes) VALUES (?,?,?,?)",
                (self.author, self.reason, now(), self._undoes))
            self.id = cur.lastrowid
        return self.id

    def _log(self, table: str, oid: int, field: str, before: Any, after: Any) -> None:
        self.conn.execute(
            "INSERT INTO changes (revision_id, object_type, object_id, field, before, after, author, reason, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (self._rev_id(), table, oid, field, _enc(before), _enc(after), self.author, self.reason, now()))

    def _check(self, table: str, fields: dict[str, Any], creating: bool = False) -> None:
        if table not in FIELDS:
            raise RiotError(f"Table inconnue pour l'écriture : {table}")
        for f in fields:
            if creating and f in _CREATE_ONLY:
                if _kind(self.author) != C and self.author != MICHAEL:
                    raise Refused(f"{f} ne se fixe pas à la main")
                continue
            if f not in FIELDS[table]:
                raise RiotError(f"{_NAMES[table]} : champ inconnu « {f} »")
            if not may_write(self.author, table, f):
                if FIELDS[table][f] is BASELINE:
                    raise Refused(f"« {f} » ({_NAMES[table]}) est le texte de Michael : {self.author} ne peut pas "
                                  "l'écrire. Écris la version de production à côté.")
                raise Refused(f"{self.author} ne peut pas écrire « {f} » ({_NAMES[table]}).")

    def get(self, table: str, oid: int) -> sqlite3.Row:
        r = self.conn.execute(f"SELECT * FROM {table} WHERE id=?", (oid,)).fetchone()
        if r is None:
            raise RiotError(f"{_NAMES.get(table, table).capitalize()} {oid} introuvable.")
        return r

    # -- écritures --------------------------------------------------------------
    def create(self, table: str, values: dict[str, Any]) -> int:
        self._check(table, values, creating=True)
        stamp = now()
        row = {"created_at": stamp, **values, "updated_at": stamp}
        cols = ", ".join(row)
        cur = self.conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(row))})",
                                tuple(row.values()))
        oid = int(cur.lastrowid if "id" not in values else values["id"])
        self._log(table, oid, "@cree", None, None)
        for f, v in values.items():
            if f not in _CREATE_ONLY and v is not None:
                self._log(table, oid, f, None, v)
        return oid

    def update(self, table: str, oid: int, values: dict[str, Any]) -> dict[str, Any]:
        self._check(table, values)
        cur = self.get(table, oid)
        changed = {f: v for f, v in values.items() if not _same(cur[f], v)}
        if not changed:
            return {}
        sets = ", ".join(f"{f}=?" for f in changed)
        self.conn.execute(f"UPDATE {table} SET {sets}, updated_at=? WHERE id=?",
                          (*changed.values(), now(), oid))
        for f, v in changed.items():
            self._log(table, oid, f, cur[f], v)
        return changed

    def _set_deleted(self, table: str, oid: int, value: str | None) -> bool:
        cur = self.get(table, oid)
        if cur["deleted_at"] == value or (value is not None and cur["deleted_at"] is not None):
            return False
        self.conn.execute(f"UPDATE {table} SET deleted_at=?, updated_at=? WHERE id=?", (value, now(), oid))
        self._log(table, oid, "deleted_at", cur["deleted_at"], value)
        return True

    def delete(self, table: str, oid: int) -> bool:
        """Suppression logique : la ligne reste, restaurable (R-A6)."""
        self._check(table, {})
        return self._set_deleted(table, oid, now())

    def restore(self, table: str, oid: int) -> bool:
        self._check(table, {})
        return self._set_deleted(table, oid, None)


@contextmanager
def revision(conn: sqlite3.Connection, author: str, reason: str | None = None,
             _undoes: int | None = None) -> Iterator[Revision]:
    """Ouvre une révision atomique : tout ou rien (R-T6)."""
    check_author(author)
    if conn.in_transaction:
        raise RiotError("Une révision est déjà ouverte sur cette connexion.")
    conn.execute("BEGIN IMMEDIATE")
    rev = Revision(conn, author, reason, _undoes)
    try:
        yield rev
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def undo(conn: sqlite3.Connection, revision_id: int, author: str, reason: str | None = None) -> int | None:
    """Annule une révision entière, dans une nouvelle révision. Refuse si un champ a changé depuis."""
    r = conn.execute("SELECT * FROM revisions WHERE id=?", (revision_id,)).fetchone()
    if r is None:
        raise RiotError(f"Révision {revision_id} introuvable.")
    if r["undone_by"] is not None:
        raise RiotError(f"La révision {revision_id} est déjà annulée (par la révision {r['undone_by']}).")
    lines = conn.execute("SELECT * FROM changes WHERE revision_id=? ORDER BY id DESC", (revision_id,)).fetchall()
    created = {(ch["object_type"], ch["object_id"]) for ch in lines if ch["field"] == "@cree"}
    with revision(conn, author, reason or f"annule la révision {revision_id}", _undoes=revision_id) as rev:
        for ch in lines:
            table, oid, field = ch["object_type"], ch["object_id"], ch["field"]
            if (table, oid) in created:
                if field == "@cree":   # un objet créé par la révision : suppression logique
                    rev._set_deleted(table, oid, now())
                continue
            cur = rev.get(table, oid)
            if not _same(cur[field], _dec(ch["after"])):
                raise RiotError(f"Annulation impossible : « {field} » ({_NAMES.get(table, table)} {oid}) a changé "
                                f"depuis la révision {revision_id}. Annule d'abord les révisions suivantes.")
            if field == "deleted_at":
                rev._set_deleted(table, oid, _dec(ch["before"]))
            else:
                rev._check(table, {field: None})
                rev.conn.execute(f"UPDATE {table} SET {field}=?, updated_at=? WHERE id=?",
                                 (_dec(ch["before"]), now(), oid))
                rev._log(table, oid, field, _dec(ch["after"]), _dec(ch["before"]))
        new_id = rev._rev_id()
        conn.execute("UPDATE revisions SET undone_by=? WHERE id=?", (new_id, revision_id))
    return new_id


def history(conn: sqlite3.Connection, object_type: str, object_id: int) -> list[dict[str, Any]]:
    """Les lignes d'historique d'un objet, de la plus ancienne à la plus récente (R-A4)."""
    return [{**dict(r), "before": _dec(r["before"]), "after": _dec(r["after"])} for r in conn.execute(
        "SELECT * FROM changes WHERE object_type=? AND object_id=? ORDER BY id", (object_type, object_id))]
