# Changelog

Une ligne par exigence livrée (`docs/REQUIREMENTS.md`), la plus récente en haut.
Format : date, identifiant, ce qui change pour Michael.

## Lot 1 : Fondations

- 2026-11-04 R-F1 : chaque statut de plan a un responsable unique (`STATUS_OWNER`),
  affiché sur chaque plan et dans la timeline (« En attente de : toi / le storyboard /
  le fournisseur… », avec la raison) ; `/api/shots/<id>` renvoie `owner`.
- 2026-11-04 R-A3 : le texte de Michael (`script` d'un plan, `brief` d'un bloc) est
  stocké à part et aucun agent ne peut l'écrire (import refusé, `riot shot set
  --script` interdit). La version de production garde ses mots tels quels ; quand
  il change son texte après transformation, la production reste, se marque « à
  mettre à jour » et le script-doctor est rappelé. Le Découpage édite son texte et
  montre la version de production dessous.
- 2026-11-04 R-A2 : un plan et un bloc gardent leur id à travers toutes les éditions
  du découpage (blocs appariés par id, champ omis conservé). Un plan retiré qui a
  des images ou des vidéos est gardé avec elles, hors timeline, restaurable
  (« Plans retirés » en bas du Découpage, `riot shot restore`) ; la régie demande
  confirmation en affichant le montant dépensé. Valider le découpage entier ne
  remet plus les plans avancés à zéro.
- 2026-11-04 R-A4 : chaque changement d'un clip, bloc, plan, personnage, version ou
  élément est journalisé (avant, après, auteur, raison). `riot history …`,
  `GET /api/shots/<id>/history`, pli « Historique des changements » dans le détail
  d'un plan. Toutes les écritures passent par `db.update`.
- 2026-11-04 R-G2 : hook `pre-commit` (pytest vert avant tout commit, installé par
  `deploy/install-hooks.sh`), tests nommés par exigence dans
  `tests/test_requirements.py`, test qui vérifie que chaque exigence du changelog a
  le sien.
- 2026-11-04 R-G3 : schéma versionné (table `schema_version`), migrations numérotées
  et rejouables, sauvegarde automatique de `studio/riot.db` dans `studio/backups/`
  avant toute migration, `riot db status`.

## Avant le lot 1

- 2026-11-03 : état figé par le tag `avant-lot-1` (choix du modèle à chaque
  génération, style photo, feuilles de tenue, propositions multiples).
