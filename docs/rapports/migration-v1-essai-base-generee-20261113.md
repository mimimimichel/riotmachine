# Migration v1 → v3 : essai à blanc

- Date : 13/11/2026 12:53
- Base v1 : `base v1 générée par legacy/ (démo + clip de 12 blocs et 64 plans)` (ouverte en lecture seule, jamais modifiée)
- Base v3 : `studio/riot-v3.db` (essai : travail sur une copie, rien n'a été écrit)
- Migrations de schéma appliquées : [1]

**Résultat : tout est conforme.**

## Étapes de ce lot

| Étape | Table v1 | Importés | Déjà là | Anomalies |
|---|---|---|---|---|
| clips | clips | 2 | 0 | 0 |
| blocks | blocks | 18 | 0 | 0 |
| shots | shots | 88 | 0 | 0 |
| feedback | reviews (avec commentaire) | 2 | 0 | 0 |

## Contrôles

| Contrôle | Résultat | Détail |
|---|---|---|
| Tous les plans valides sont présents | oui | 88 / 88 |
| Identifiants des plans conservés | oui | identiques |
| Identifiants des blocs conservés | oui | identiques |
| Plans retirés toujours retirés (et restaurables) | oui | 1 / 1 |
| Mots de Michael recopiés à l'identique | oui | 0 écart(s) |
| Retours de Michael présents | oui | 2 / 2 |

## Tables v1 et lot de migration

| Table v1 | Lignes | Migration |
|---|---|---|
| agent_runs | 0 | lot 5 (journal des agents) |
| assets | 61 | lot 2 (prises ; anciens visuels archivés, D7) |
| blocks | 18 | faite (lot 1) |
| castings | 1 | lot 2 (épinglage) |
| changes | 375 | historique v1 laissé dans l'ancienne base (D21) |
| character_assets | 17 | lot 2 (pack) |
| character_versions | 3 | lot 2 (bible) |
| characters | 2 | lot 2 (artistes) |
| clip_files | 4 | lot 2 (brief) |
| clips | 2 | faite (lot 1) |
| element_images | 0 | lot 2 (bibliothèque) |
| elements | 0 | lot 2 (bibliothèque) |
| events | 134 | journal v1 laissé dans l'ancienne base |
| group_members | 0 | lot 2 (groupes) |
| groups_ | 0 | lot 2 (groupes) |
| jobs | 54 | lot 5 (suivi des générations) |
| look_images | 0 | lot 2 (looks) |
| looks | 2 | lot 2 (looks) |
| notifications | 0 | propre à la v1 |
| reviews | 60 | faite (lot 1) |
| schema_version | 5 | propre à la v1 |
| shot_elements | 0 | lot 2 (bibliothèque) |
| shot_notes | 3 | lot 6 (fil de production) |
| shots | 88 | faite (lot 1) |
| spend_requests | 0 | lot 3 (accords) |
