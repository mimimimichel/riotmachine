"""La CLI `riot` de la v3. Les agents n'agissent que par elle (R-T10).

Une commande qui écrit signe avec `--auteur agent:<nom>` ou `code:<module>`
(ou RIOT_ACTOR). « michael » est refusé : Michael écrit depuis la régie (D10).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import db, migrate, migration_v1, settings, store
from .errors import RiotError

OBJECTS = {"clip": "clips", "bloc": "blocks", "plan": "shots", "retour": "feedback", "generation": "generations"}


def _table(name: str) -> str:
    t = OBJECTS.get(name, name)
    if t not in store.FIELDS:
        raise RiotError(f"Objet inconnu : {name} (attendu : {', '.join(OBJECTS)})")
    return t


def _value(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


def cmd_migrer(a) -> None:
    conn = db.connect()
    res = migrate.migrate(conn)
    print(f"Base v3 : {settings.db_path()}")
    print(f"Migrations appliquées : {res['applied'] or 'aucune, la base est à jour'}")
    if res["backup"]:
        print(f"Copie faite avant migration : {res['backup']}")


def cmd_history(a) -> None:
    conn = db.open_db()
    table = _table(a.objet)
    lines = store.history(conn, table, a.id)
    if not lines:
        print(f"Aucun historique pour {a.objet} {a.id}.")
        return
    for h in lines:
        what = "créé" if h["field"] == "@cree" else f"{h['field']} : {h['before']!r} → {h['after']!r}"
        print(f"{h['created_at'][:19].replace('T', ' ')}  r{h['revision_id']}  {h['author']}  {what}"
              + (f"  ({h['reason']})" if h["reason"] else ""))


def cmd_ecrire(a) -> None:
    author = store.author_from_cli(a.auteur)
    values = {}
    for item in a.champs:
        if "=" not in item:
            raise RiotError(f"« {item} » : écris champ=valeur")
        k, v = item.split("=", 1)
        values[k.strip()] = _value(v)
    conn = db.open_db()
    with store.revision(conn, author, a.raison) as rev:
        changed = rev.update(_table(a.objet), a.id, values)
    print("Rien à changer." if not changed else f"Modifié : {', '.join(changed)} (révision {rev.id}).")


def cmd_migrer_v1(a) -> None:
    src = Path(a.depuis).expanduser()
    dst = Path(a.vers).expanduser() if a.vers else settings.db_path()
    res = migration_v1.run(src, dst, essai=a.essai)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = migration_v1.report_markdown(res, stamp)
    out = Path(a.rapport) if a.rapport else (
        settings.REPO_ROOT / "docs" / "rapports"
        / f"migration-v1-{'essai' if a.essai else 'reelle'}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    ok = all(c[1] for c in res["controles"])
    print(f"{'Essai' if a.essai else 'Migration'} terminé{'' if a.essai else 'e'} : "
          f"{'tout est conforme' if ok else 'des contrôles échouent'}. Rapport : {out}")
    if not ok:
        sys.exit(1)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="riot", description="Riot Machine v3")
    p.add_argument("--auteur", help="agent:<nom> ou code:<module> (jamais michael)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("migrer", help="Met la base v3 à jour (migrations numérotées, copie avant)")
    sp.set_defaults(func=cmd_migrer)
    sp = sub.add_parser("history", aliases=["historique"], help="Historique d'un objet")
    sp.add_argument("objet")
    sp.add_argument("id", type=int)
    sp.set_defaults(func=cmd_history)
    sp = sub.add_parser("ecrire", help="Modifie des champs d'un objet (droits vérifiés, historique écrit)")
    sp.add_argument("objet")
    sp.add_argument("id", type=int)
    sp.add_argument("champs", nargs="+", help="champ=valeur")
    sp.add_argument("--raison")
    sp.set_defaults(func=cmd_ecrire)
    sp = sub.add_parser("migrer-v1", help="Migre la base v1 vers la base v3 (avec --essai : à blanc)")
    sp.add_argument("--depuis", required=True, help="base v1 (riot.db), jamais modifiée")
    sp.add_argument("--vers", help="base v3 (défaut : studio/riot-v3.db)")
    sp.add_argument("--essai", action="store_true", help="tout sur des copies ; seul le rapport est écrit")
    sp.add_argument("--rapport", help="chemin du rapport (défaut : docs/rapports/)")
    sp.set_defaults(func=cmd_migrer_v1)
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except RiotError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
