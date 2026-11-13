"""Importer un découpage sans jamais supprimer ni recréer (R-A2).

Format : {"blocks": [{"id"?, "name", "intention"?, "production_notes"?,
          "shots": [{"id"?, "t_start", "t_end", "words"?, "production_text"?}]}]}

- un bloc ou un plan qui porte un `id` est mis à jour sur place ; un champ
  absent est conservé ;
- sans `id`, il est créé ;
- un bloc ou un plan du clip absent du découpage est retiré logiquement :
  il garde son identifiant, ses retours, ses générations et son historique,
  et se restaure.
Les droits d'écriture sont ceux de `store` : un agent ne peut pas écrire les
mots de Michael (R-A3).
"""

from __future__ import annotations

from typing import Any

from .errors import RiotError
from .store import Revision

_BLOCK_KEYS = {"id", "name", "intention", "production_notes", "shots"}
_SHOT_KEYS = {"id", "t_start", "t_end", "words", "production_text"}


def _validate(rev: Revision, clip: int, data: Any) -> list[dict]:
    if not isinstance(data, dict) or not isinstance(data.get("blocks"), list):
        raise RiotError("Découpage illisible : attendu {\"blocks\": [...]}.")
    own_blocks = {r[0] for r in rev.conn.execute("SELECT id FROM blocks WHERE clip_id=?", (clip,))}
    own_shots = {r[0] for r in rev.conn.execute("SELECT id FROM shots WHERE clip_id=?", (clip,))}
    n = 0
    for bi, b in enumerate(data["blocks"], 1):
        where = f"Bloc {bi} « {b.get('name', '?')} »"
        if set(b) - _BLOCK_KEYS:
            raise RiotError(f"{where} : champs inconnus {sorted(set(b) - _BLOCK_KEYS)}")
        if b.get("id") is not None and b["id"] not in own_blocks:
            raise RiotError(f"{where} : le bloc {b['id']} n'appartient pas à ce clip")
        if b.get("id") is None and not b.get("name"):
            raise RiotError(f"{where} : un nouveau bloc a besoin d'un nom")
        for s in b.get("shots") or []:
            n += 1
            w = f"{where}, plan {n}"
            if set(s) - _SHOT_KEYS:
                raise RiotError(f"{w} : champs inconnus {sorted(set(s) - _SHOT_KEYS)}")
            if s.get("id") is not None and s["id"] not in own_shots:
                raise RiotError(f"{w} : le plan {s['id']} n'appartient pas à ce clip")
            if s.get("id") is None and (s.get("t_start") is None or s.get("t_end") is None):
                raise RiotError(f"{w} : un nouveau plan a besoin d'un début et d'une fin")
            if s.get("t_start") is not None and s.get("t_end") is not None and float(s["t_end"]) <= float(s["t_start"]):
                raise RiotError(f"{w} : la fin ({s['t_end']}) doit être après le début ({s['t_start']})")
    return data["blocks"]


def import_decoupage(rev: Revision, clip: int, data: Any) -> dict[str, int]:
    blocks = _validate(rev, clip, data)
    seen_blocks, seen_shots = set(), set()
    placed: list[tuple[float, int]] = []
    counts = {"blocs_crees": 0, "plans_crees": 0, "plans_modifies": 0, "plans_retires": 0, "blocs_retires": 0}
    for num, b in enumerate(blocks, 1):
        fields = {k: b[k] for k in ("name", "intention", "production_notes") if k in b}
        if b.get("id") is not None:
            bid = b["id"]
            rev.update("blocks", bid, {**fields, "num": num})
            rev.restore("blocks", bid)
        else:
            bid = rev.create("blocks", {"clip_id": clip, "num": num, **fields})
            counts["blocs_crees"] += 1
        seen_blocks.add(bid)
        for s in b.get("shots") or []:
            fields = {k: s[k] for k in ("t_start", "t_end", "words", "production_text") if k in s}
            if s.get("id") is not None:
                sid = s["id"]
                if rev.update("shots", sid, {**fields, "block_id": bid}):
                    counts["plans_modifies"] += 1
                rev.restore("shots", sid)
            else:
                sid = rev.create("shots", {"clip_id": clip, "block_id": bid, "num": 0, **fields})
                counts["plans_crees"] += 1
            seen_shots.add(sid)
            t0 = rev.get("shots", sid)["t_start"]
            placed.append((float(t0), sid))
    for num, (_t, sid) in enumerate(sorted(placed), 1):
        rev.update("shots", sid, {"num": num})
    for (sid,) in rev.conn.execute("SELECT id FROM shots WHERE clip_id=? AND deleted_at IS NULL", (clip,)).fetchall():
        if sid not in seen_shots and rev.delete("shots", sid):
            counts["plans_retires"] += 1
    for (bid,) in rev.conn.execute("SELECT id FROM blocks WHERE clip_id=? AND deleted_at IS NULL", (clip,)).fetchall():
        if bid not in seen_blocks and rev.delete("blocks", bid):
            counts["blocs_retires"] += 1
    return counts
