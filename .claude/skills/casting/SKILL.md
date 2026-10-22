---
name: casting
description: Crée ou fait évoluer un personnage et son pack de référence photoréaliste (canon, angles, silhouette, expressions, lumières). Lancé par le worker quand Michael demande un pack dans la régie, ou à la main avec /casting <personnage>.
argument-hint: <slug-du-personnage>
---

Travail de casting sur **$ARGUMENTS**.

Le parcours se fait dans la régie (onglet Personnages) :
1. Michael dépose le brouillon de la canon ; la canon HD est générée
   automatiquement (agrandissement fidèle) ; il la compare au brouillon et la valide.
2. Michael écrit ses **instructions** pour le pack et clique « Lancer le pack ».
3. Toi : tu fais générer le pack, puis Michael trie et valide la version.

## Ce que tu fais

1. `riot character show $ARGUMENTS` : repère la version brouillon dont
   `pack_status` vaut `requested`. Lis ses `instructions` (aussi dans
   `studio/characters/$ARGUMENTS/v<N>/instructions.md`), les images déjà gardées
   ou rejetées et leurs `comment` (les raisons des rejets de Michael).
2. Délègue à l'agent `directeur-casting` (outil Agent) : ADN de la version si
   absent, puis une commande `riot character gen` par image demandée dans les
   instructions, en passant la canon validée en référence. Il ne refait pas une
   image déjà gardée ; il tient compte des commentaires des images rejetées.
3. Termine par `riot character pack-done $ARGUMENTS --version <N>`, même si une
   partie des images a échoué (dis-le dans ton résumé).
4. Si les instructions sont ambiguës sur un trait d'identité, ne tranche pas :
   génère ce qui est clair, puis `riot notify` la question à Michael.

À la main (`/casting <slug>` dans Claude Code), sans pack demandé : fais le point
avec Michael sur l'étape où en est le personnage et dis-lui quoi faire dans la régie.
