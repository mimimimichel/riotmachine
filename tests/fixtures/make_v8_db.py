"""Fabrique une base v1 (schéma 8) avec le code de legacy/, pour tester la migration.

Lancé dans un processus à part, avec PYTHONPATH=legacy : l'ancien paquet
`riotmachine` n'est jamais importé à côté du nouveau.

Contenu : le clip de démonstration de la v1, plus « nobody-saw-test » en
12 blocs et 64 plans, avec des retours de Michael, un plan retiré et un texte
de Michael différent de la version de production.

Usage : python make_v8_db.py <dossier studio>
Variables lues par la v1 : RIOT_STUDIO_ROOT, RIOT_DB (posées par l'appelant).
"""

from __future__ import annotations

import sys


def main() -> None:
    from riotmachine import db, demo, production

    db.set_actor("michael")   # comme la régie v1 : le découpage est le texte de Michael
    with db.session() as conn:
        production.sync_character_files(conn)
        demo.create(conn)
        blocks = []
        t = 0.0
        n = 0
        for b in range(12):
            shots = []
            for _ in range(6 if b < 4 else 5):          # 4 x 6 + 8 x 5 = 64 plans
                n += 1
                d = 2.5 + (n % 3) * 0.5
                shots.append({"t_start": round(t, 2), "t_end": round(t + d, 2),
                              "script": f"Plan {n} : JJ dans la rue, mots de Michael",
                              "description": f"Plan {n} : JJ dans la rue (version de production)"})
                t += d
            blocks.append({"name": f"Bloc {b + 1}", "brief": f"Intention de Michael, bloc {b + 1}",
                           "shots": shots})
        production.create_clip(conn, "Nobody Saw (test)", slug="nobody-saw-test",
                               pitch="JJ traverse sa ville au matin.", concept="Concept de test, en deux phrases.")
        production.import_shots(conn, "nobody-saw-test", {"blocks": blocks}, by="michael")
        production.set_stage(conn, "nobody-saw-test", "decoupage_review")
        production.review_decoupage(conn, "nobody-saw-test", "change", "Le bloc 3 est trop long, resserre-le.")
        shot_ids = [r[0] for r in conn.execute(
            "SELECT id FROM shots WHERE clip_slug='nobody-saw-test' ORDER BY num")]
        # une baseline qui diffère de la production, et un plan retiré (suppression logique v1)
        conn.execute("UPDATE shots SET description='Production réécrite par un agent' WHERE id=?", (shot_ids[1],))
        conn.execute("UPDATE shots SET deleted_at='2026-11-10T10:00:00Z' WHERE id=?", (shot_ids[-1],))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        print(f"v1 schéma {version} ; clips={conn.execute('SELECT COUNT(*) FROM clips').fetchone()[0]} "
              f"plans={conn.execute('SELECT COUNT(*) FROM shots').fetchone()[0]}")


if __name__ == "__main__":
    sys.exit(main())
