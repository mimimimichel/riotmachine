# Riot Machine

Label d'artistes IA et studio qui produit leurs clips. Version 3 en cours de
construction sur la branche `v3` ; la version 1 reste sur l'étiquette
`v1-final` et dans `legacy/`.

- Ce qu'est le projet : `docs/VISION-v3.md`
- Ce qu'on construit : `docs/SPEC-v3.md` et `docs/PRODUCTION-PLANS-v3.md`
- Les décisions prises : `docs/DECISIONS-v3.md`
- Ce qui est livré : `CHANGELOG.md`

## Sur le PC

`bash ~/riotmachine/scripts/sur-le-pc.sh` fait la sauvegarde datée de la base et
des clips, relève ce qui tourne, installe une copie de travail v3 à côté de la
v1 sans la toucher, lance les tests et un essai à blanc de la migration, puis
écrit son rapport dans `docs/rapports/`. Il se relance sans danger.

## Développement

```
python3 -m venv .venv-v3 && .venv-v3/bin/pip install -e '.[dev]'
bash deploy/install-hooks.sh
.venv-v3/bin/python -m pytest
```
