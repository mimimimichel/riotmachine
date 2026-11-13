# Riot Machine v3 — consignes pour Claude Code

Lis d'abord, dans cet ordre : `docs/VISION-v3.md`, `docs/SPEC-v3.md`,
`docs/PRODUCTION-PLANS-v3.md`, `docs/DECISIONS-v3.md`. Ils remplacent toute
consigne antérieure. L'ancien code (v1) est dans `legacy/` : une base de
référence, jamais importée, jamais une raison de reprendre un comportement.

## Règles

- Fais tout toi-même. Ne demande à Michael que les décisions créatives, les
  dépenses et les vrais choix de conception. Pour le reste, prends l'option la
  plus simple conforme à la spec et note-la dans `docs/DECISIONS-v3.md` (D11).
- Ce qui ne se fait que sur le PC passe par `scripts/sur-le-pc.sh`, tenu à jour
  à chaque lot (D12).
- Un lot à la fois, dans l'ordre de `SPEC-v3.md` §8. Par exigence : test
  `test_r_<id>_…` d'abord, puis code, puis une ligne de `CHANGELOG.md`. Tests
  verts avant chaque commit (crochet `deploy/hooks/pre-commit`, installé par
  `bash deploy/install-hooks.sh`), identifiants dans le message. Pousse `v3` à
  la fin de chaque lot.
- Aucune dépense : tout en simulation (`riotmachine/providers/simulation.py`).
- Aucune règle propre à un modèle dans le code : tout vient du catalogue.
- Toute écriture passe par `riotmachine/store.py` (révision, historique, droits).
- Aucun agent sur minuterie, aucune interrogation en boucle.
- Écritures atomiques, clé unique par génération, délais et essais bornés. Une
  erreur remonte en français, avec ce qu'on peut faire.
- La base v3 est `studio/riot-v3.db` ; `studio/riot.db` (v1) n'est jamais modifiée.

## Où sont les choses

- `riotmachine/` : le code v3. `migrations/` : schéma numéroté.
- `tests/` : un fichier par famille d'exigences ; `tests/fixtures/make_v8_db.py`
  fabrique une base v1 avec `legacy/` pour tester la migration.
- `config/agents-permissions.json` : ce que les agents ont le droit de faire (R-T10).
- `docs/rapports/` : rapports produits sur le PC et essais de migration.
