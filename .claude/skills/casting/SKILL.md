---
name: casting
description: Crée ou fait évoluer un personnage et son pack de référence photoréaliste (canon, angles, silhouette, expressions, lumières). À utiliser avec /casting <personnage>.
argument-hint: <slug-du-personnage>
---

Travail de casting sur **$ARGUMENTS**, avec Michael.

1. `riot character show $ARGUMENTS` (si le personnage n'existe pas :
   `riot character new $ARGUMENTS --name "<Nom>"` après lui avoir demandé le nom).
2. Repère où on en est :
   - **Pas de version brouillon** : lis le brief (`studio/characters/$ARGUMENTS/brief-v*.md`).
     Si des points sont « à trancher », pose-les à Michael **avant** toute
     génération, note ses réponses dans le brief, puis crée la version :
     `riot character version $ARGUMENTS`.
   - **Brouillon sans canon** : délègue à l'agent `directeur-casting` l'écriture de l'ADN et
     les 3 à 4 candidates canon. Puis dis à Michael d'aller choisir dans la régie
     (onglet Personnages) et de relancer `/casting $ARGUMENTS` ensuite.
   - **Brouillon avec canon** : délègue à l'agent `directeur-casting` la génération du reste
     du pack. Puis dis à Michael de trier les images dans la régie (garder /
     rejeter) et de valider la version quand le pack lui plaît.
3. Les images arrivent dans la régie en une à deux minutes (le worker les récupère).
