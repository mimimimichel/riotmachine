---
name: etat
description: Point rapide sur le studio — clips en cours, ce qui attend Michael, générations en cours, coûts. À utiliser avec /etat ou /etat <clip>.
argument-hint: "[slug-du-clip]"
---

Fais le point pour Michael.

- Sans argument : `riot status --json`, puis pour chaque clip actif une ligne :
  étape, nombre de plans à valider de son côté, travail en cours côté agents, coût.
- Avec un clip ($ARGUMENTS) : `riot status $ARGUMENTS` et `riot events --clip $ARGUMENTS --limit 10`,
  puis résume : où en est le clip, ce qu'il doit valider, les derniers incidents.

Rappelle-lui l'adresse de la régie si des validations l'attendent. Pas de longue
liste : 10 lignes maximum.
