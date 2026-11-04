# Changelog

Une ligne par exigence livrée (`docs/REQUIREMENTS.md`), la plus récente en haut.
Format : date, identifiant, ce qui change pour Michael.

## Lot 1 : Fondations

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
