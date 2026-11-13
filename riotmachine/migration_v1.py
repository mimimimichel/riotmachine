"""Migration de la base v1 (schéma 8) vers la base v3 (D15, D17).

La base v1 n'est jamais modifiée : elle est ouverte en lecture seule. Chaque
table est migrée au lot où elle naît ; une étape déjà faite ne se refait pas
(table `import_v1`), donc relancer la migration ne crée aucun doublon et
ajoute seulement ce qui manque. Les identifiants des blocs et des plans sont
conservés.

Mode essai (`essai=True`) : tout se fait sur des copies, dans un dossier
temporaire ; seul le rapport est écrit.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import db, migrate, store
from .errors import RiotError

AUTHOR = store.MIGRATION_V1
V1_SCHEMA = 8

# Tables v1 et lot où elles seront migrées (pour le rapport).
LATER = {
    "characters": "lot 2 (artistes)", "character_versions": "lot 2 (bible)", "character_assets": "lot 2 (pack)",
    "looks": "lot 2 (looks)", "look_images": "lot 2 (looks)", "groups_": "lot 2 (groupes)",
    "group_members": "lot 2 (groupes)", "castings": "lot 2 (épinglage)", "elements": "lot 2 (bibliothèque)",
    "element_images": "lot 2 (bibliothèque)", "shot_elements": "lot 2 (bibliothèque)",
    "assets": "lot 2 (prises ; anciens visuels archivés, D7)", "clip_files": "lot 2 (brief)",
    "spend_requests": "lot 3 (accords)", "jobs": "lot 5 (suivi des générations)",
    "shot_notes": "lot 6 (fil de production)", "agent_runs": "lot 5 (journal des agents)",
}
NOT_MIGRATED = {
    "changes": "historique v1 laissé dans l'ancienne base (D21)",
    "events": "journal v1 laissé dans l'ancienne base",
    "notifications": "propre à la v1",
    "schema_version": "propre à la v1",
}


def _open_v1(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise RiotError(f"Base v1 introuvable : {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != V1_SCHEMA:
        conn.close()
        raise RiotError(f"La base v1 est au schéma {version}, la migration attend le schéma {V1_SCHEMA}. "
                        "Ouvre-la une fois avec la v1 (`v1-final`) pour la mettre à jour, puis relance.")
    return conn


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _done(new: sqlite3.Connection, step: str, key: str) -> int | None:
    r = new.execute("SELECT object_id FROM import_v1 WHERE step=? AND legacy_key=?", (step, key)).fetchone()
    return r["object_id"] if r else None


def _mark(rev: store.Revision, step: str, key: str, table: str, oid: int) -> None:
    rev.create("import_v1", {"step": step, "legacy_key": key, "object_type": table, "object_id": oid})


def _clips(old, new, rev, out) -> None:
    for c in old.execute("SELECT * FROM clips ORDER BY created_at, slug"):
        if _done(new, "clips", c["slug"]) is not None:
            out["deja"] += 1
            continue
        brief = "\n\n".join(x.strip() for x in (c["pitch"], c["concept"]) if x and x.strip()) or None
        oid = rev.create("clips", {"slug": c["slug"], "title": c["title"], "brief": brief,
                                   "created_at": c["created_at"]})
        _mark(rev, "clips", c["slug"], "clips", oid)
        out["importes"] += 1


def _clip_ids(new) -> dict[str, int]:
    return {r["slug"]: r["id"] for r in new.execute("SELECT id, slug FROM clips")}


def _blocks(old, new, rev, out) -> None:
    clips = _clip_ids(new)
    has_brief = "brief" in _cols(old, "blocks")
    for b in old.execute("SELECT * FROM blocks ORDER BY id"):
        key = str(b["id"])
        if _done(new, "blocks", key) is not None:
            out["deja"] += 1
            continue
        if b["clip_slug"] not in clips:
            out["anomalies"].append(f"bloc {b['id']} : clip {b['clip_slug']} absent, bloc non importé")
            continue
        michael = (b["brief"] if has_brief else None) or b["intention"]
        prod = b["intention"] if b["intention"] and b["intention"] != michael else None
        oid = rev.create("blocks", {"id": b["id"], "clip_id": clips[b["clip_slug"]], "num": b["num"],
                                    "name": b["name"], "intention": michael, "production_notes": prod})
        _mark(rev, "blocks", key, "blocks", oid)
        out["importes"] += 1


def _shots(old, new, rev, out) -> None:
    clips = _clip_ids(new)
    blocks = {r["id"] for r in new.execute("SELECT id FROM blocks")}
    cols = _cols(old, "shots")
    for s in old.execute("SELECT * FROM shots ORDER BY id"):
        key = str(s["id"])
        if _done(new, "shots", key) is not None:
            out["deja"] += 1
            continue
        if s["clip_slug"] not in clips:
            out["anomalies"].append(f"plan {s['id']} : clip {s['clip_slug']} absent, plan non importé")
            continue
        if float(s["t_end"]) <= float(s["t_start"]):
            out["anomalies"].append(f"plan {s['id']} ({s['clip_slug']} n° {s['num']}) : fin {s['t_end']} avant "
                                    f"le début {s['t_start']}, plan non importé ; à corriger dans la v1")
            continue
        block = s["block_id"] if s["block_id"] in blocks else None
        if s["block_id"] is not None and block is None:
            out["anomalies"].append(f"plan {s['id']} : bloc {s['block_id']} absent, plan importé sans bloc")
        words = s["script"] if "script" in cols else s["description"]
        oid = rev.create("shots", {
            "id": s["id"], "clip_id": clips[s["clip_slug"]], "block_id": block, "num": s["num"],
            "t_start": float(s["t_start"]), "t_end": float(s["t_end"]), "words": words,
            "production_text": s["description"]})
        if "deleted_at" in cols and s["deleted_at"]:
            rev.delete("shots", oid)
        _mark(rev, "shots", key, "shots", oid)
        out["importes"] += 1


def _feedback(old, new, rev, out) -> None:
    clips = _clip_ids(new)
    shots = {r["id"] for r in new.execute("SELECT id FROM shots")}
    for r in old.execute("SELECT * FROM reviews WHERE comment IS NOT NULL AND trim(comment)!='' ORDER BY id"):
        key = str(r["id"])
        if _done(new, "feedback", key) is not None:
            out["deja"] += 1
            continue
        if r["shot_id"] is not None and r["shot_id"] in shots:
            otype, oid = "shots", r["shot_id"]
        elif r["clip_slug"] in clips:
            otype, oid = "clips", clips[r["clip_slug"]]
        else:
            out["anomalies"].append(f"retour {r['id']} : objet introuvable, non importé")
            continue
        fid = rev.create("feedback", {"object_type": otype, "object_id": oid, "text": r["comment"],
                                      "route": r["route"], "result": r["handled_note"],
                                      "created_at": r["created_at"]})
        _mark(rev, "feedback", key, "feedback", fid)
        out["importes"] += 1


# Étapes du lot 1. Chaque lot ajoute les siennes (D15).
STEPS: list[tuple[str, str, Callable[..., None]]] = [
    ("clips", "clips", _clips),
    ("blocks", "blocks", _blocks),
    ("shots", "shots", _shots),
    ("feedback", "reviews (avec commentaire)", _feedback),
]


def run(old_path: Path, new_path: Path, *, essai: bool = False) -> dict[str, Any]:
    """Migre `old_path` (v1) vers `new_path` (v3). En essai, tout se fait sur des copies."""
    old_path, new_path = Path(old_path), Path(new_path)
    work = None
    src, dst = old_path, new_path
    if essai:
        work = Path(tempfile.mkdtemp(prefix="riot-essai-"))
        src = work / "v1.db"
        probe = _open_v1(old_path)          # contrôle du schéma avant de copier
        target = sqlite3.connect(src)
        probe.backup(target)
        target.close()
        probe.close()
        dst = work / "v3.db"
        if new_path.is_file():
            shutil.copy2(new_path, dst)
    old = _open_v1(src)
    try:
        new = db.connect(dst)
        mig = migrate.migrate(new)
        saved = migrate.backup(new, "avant-import-v1") if not essai and _has_rows(new) else None
        steps = []
        for name, v1_table, fn in STEPS:
            out = {"etape": name, "table_v1": v1_table, "importes": 0, "deja": 0, "anomalies": []}
            with store.revision(new, AUTHOR, f"migration v1 : {name}") as rev:
                fn(old, new, rev, out)
            steps.append(out)
        v1_counts = {t: old.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                     for (t,) in old.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                             "AND name NOT LIKE 'sqlite_%' ORDER BY name")}
        checks = _checks(old, new)
        new.close()
    finally:
        old.close()
        if work:
            shutil.rmtree(work, ignore_errors=True)
    return {"source": str(old_path), "cible": str(new_path), "essai": essai, "schema": mig,
            "sauvegarde": str(saved) if saved else None, "etapes": steps, "tables_v1": v1_counts,
            "controles": checks}


def _has_rows(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM import_v1 LIMIT 1").fetchone() is not None


def _checks(old: sqlite3.Connection, new: sqlite3.Connection) -> list[tuple[str, bool, str]]:
    out = []
    n_old = old.execute("SELECT COUNT(*) FROM shots WHERE t_end > t_start").fetchone()[0]
    n_new = new.execute("SELECT COUNT(*) FROM shots").fetchone()[0]
    out.append(("Tous les plans valides sont présents", n_old == n_new, f"{n_new} / {n_old}"))
    ids_old = {r[0] for r in old.execute("SELECT id FROM shots WHERE t_end > t_start")}
    ids_new = {r[0] for r in new.execute("SELECT id FROM shots")}
    out.append(("Identifiants des plans conservés", ids_old == ids_new,
                "identiques" if ids_old == ids_new else f"{len(ids_old ^ ids_new)} différences"))
    b_old = {r[0] for r in old.execute("SELECT id FROM blocks")}
    b_new = {r[0] for r in new.execute("SELECT id FROM blocks")}
    out.append(("Identifiants des blocs conservés", b_old == b_new,
                "identiques" if b_old == b_new else f"{len(b_old ^ b_new)} différences"))
    cols = _cols(old, "shots")
    if "deleted_at" in cols:
        d_old = old.execute("SELECT COUNT(*) FROM shots WHERE deleted_at IS NOT NULL").fetchone()[0]
        d_new = new.execute("SELECT COUNT(*) FROM shots WHERE deleted_at IS NOT NULL").fetchone()[0]
        out.append(("Plans retirés toujours retirés (et restaurables)", d_old == d_new, f"{d_new} / {d_old}"))
    if "script" in cols:
        diff = 0
        for r in old.execute("SELECT id, script FROM shots"):
            got = new.execute("SELECT words FROM shots WHERE id=?", (r["id"],)).fetchone()
            if got is not None and got["words"] != r["script"]:
                diff += 1
        out.append(("Mots de Michael recopiés à l'identique", diff == 0, f"{diff} écart(s)"))
    fb_old = old.execute("SELECT COUNT(*) FROM reviews WHERE comment IS NOT NULL AND trim(comment)!=''").fetchone()[0]
    fb_new = new.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    out.append(("Retours de Michael présents", fb_old == fb_new, f"{fb_new} / {fb_old}"))
    return out


def report_markdown(res: dict[str, Any], stamp: str) -> str:
    lines = [f"# Migration v1 → v3 : {'essai à blanc' if res['essai'] else 'migration réelle'}", "",
             f"- Date : {stamp}",
             f"- Base v1 : `{res['source']}` (ouverte en lecture seule, jamais modifiée)",
             f"- Base v3 : `{res['cible']}`" + (" (essai : travail sur une copie, rien n'a été écrit)" if res["essai"] else ""),
             f"- Migrations de schéma appliquées : {res['schema']['applied'] or 'aucune (déjà à jour)'}"]
    if res["sauvegarde"]:
        lines.append(f"- Copie de la base v3 avant import : `{res['sauvegarde']}`")
    ok = all(c[1] for c in res["controles"]) and not any(s["anomalies"] for s in res["etapes"])
    lines += ["", f"**Résultat : {'tout est conforme' if ok else 'à regarder, voir plus bas'}.**", "",
              "## Étapes de ce lot", "", "| Étape | Table v1 | Importés | Déjà là | Anomalies |", "|---|---|---|---|---|"]
    for s in res["etapes"]:
        lines.append(f"| {s['etape']} | {s['table_v1']} | {s['importes']} | {s['deja']} | {len(s['anomalies'])} |")
    lines += ["", "## Contrôles", "", "| Contrôle | Résultat | Détail |", "|---|---|---|"]
    for name, good, detail in res["controles"]:
        lines.append(f"| {name} | {'oui' if good else '**non**'} | {detail} |")
    anomalies = [a for s in res["etapes"] for a in s["anomalies"]]
    if anomalies:
        lines += ["", "## Anomalies", ""] + [f"- {a}" for a in anomalies]
    done = {s["table_v1"].split(" ")[0] for s in res["etapes"]}
    lines += ["", "## Tables v1 et lot de migration", "", "| Table v1 | Lignes | Migration |", "|---|---|---|"]
    for t, n in res["tables_v1"].items():
        where = "faite (lot 1)" if t in done else LATER.get(t) or NOT_MIGRATED.get(t) or "à décider"
        lines.append(f"| {t} | {n} | {where} |")
    return "\n".join(lines) + "\n"
