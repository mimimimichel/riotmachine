# Riot Machine — Vision

Version 1.0 — 4 novembre 2026. Ce document et `REQUIREMENTS.md` sont la référence
du produit. Le code, les consignes des agents et la régie les appliquent. Quand
le besoin change, on modifie d'abord ces documents, puis le code.

## 1. Finalité

Riot Machine est le studio qui produit les clips des artistes IA de Michael, à
commencer par JJ. Michael est le créatif : il écrit, il a les idées, il choisit,
il valide. Tout le reste, la production technique, est fait par des agents et par
le worker, sans qu'il ait à s'en occuper.

Le studio réussit quand un clip sort. Pas quand une fonction de plus existe.

## 2. Le constat de départ (octobre 2026)

Deux semaines de construction, zéro clip produit, 300 $ de crédits Vertex
intacts. Les causes, constatées dans le code et à l'usage :

- La machine demande une action par plan à chaque étape. Sur 60 plans, c'est
  300 à 400 interactions. Le goulot, c'est Michael, et la machine le sollicite
  plan par plan au lieu de bloc par bloc.
- Découpage et plans sont les mêmes données, mais présentées comme deux mondes :
  champs différents, capacités différentes, aucune navigation de l'un à l'autre.
- Les mots de Michael sont écrasés par les agents (le script doctor réécrit la
  seule colonne `description`). Il n'y a pas de baseline.
- Chaque sauvegarde du découpage supprime et recrée tous les plans :
  identifiants, statuts et notes perdus.
- Après validation, le découpage est figé : on ne peut ni couper, ni fusionner,
  ni insérer un plan, et un changement de durée n'invalide rien.
- Aucun moyen de travailler « en brouillon » : chaque plan passe par toutes les
  étapes (HD, contrôle, upscale, lip-sync) même quand on rode la machine.
- Les évolutions se sont faites par petits bouts dans Claude Code, sans document
  de référence, d'où des régressions.

## 3. Ce que la machine optimise, dans l'ordre

1. **Le débit.** Un clip doit pouvoir sortir en quelques jours, pas en
   quelques semaines. Michael intervient par lot (un bloc à la fois), sur une
   grille, et la machine enchaîne seule entre deux interventions.
2. **La cohérence des personnages.** Chaque génération part de la canon, de
   l'ADN et du look castés. L'identité est contrôlée avant que Michael ne voie
   le résultat.
3. **Le coût.** Un mode brouillon permet de faire un clip entier pour quelques
   dollars ; les étapes chères ne se font que sur ce qui est validé, et seulement
   en mode final.
4. **Le contrôle là où il compte.** Michael valide le découpage, les visuels et
   les finals. Le reste est automatique, avec des seuils qu'il règle.

Quand deux objectifs se contredisent, l'ordre ci-dessus tranche.

## 4. Principes

- **Un objet, plusieurs vues.** Un plan est une seule chose en base. L'onglet
  Découpage en est la vue « écriture », l'onglet Plans la vue « production », le
  détail la vue complète. On passe de l'une à l'autre en un clic, sans perdre
  de contexte.
- **La baseline de Michael est intouchable.** Ce que Michael écrit (script d'un
  plan, intention d'un bloc, instructions de casting, retours) est stocké à part
  et jamais modifié par un agent. Les agents produisent des versions de
  production à côté. Michael voit toujours les deux.
- **Tout est tracé.** Chaque changement sur un plan, un bloc, un clip ou un
  personnage est journalisé : qui, quand, avant, après, pourquoi. L'historique
  se lit par plan et par clip.
- **Identifiants stables.** Un plan garde son identifiant toute sa vie, quelles
  que soient les éditions du découpage. Ses notes, ses images, ses retours le
  suivent.
- **Des modes, pas un seul chemin.** Brouillon, standard, final. Chaque étape
  peut être sautée explicitement. Passer du brouillon au final ne refait que ce
  qui manque.
- **Par lot.** L'unité de travail de Michael est le bloc. Accord de dépense par
  bloc, validation en grille, notification par lot.
- **Un responsable par état.** À tout moment, la régie dit pour chaque plan qui
  est attendu : Michael, tel agent, le worker ou le fournisseur.
- **Le changement a des conséquences connues.** Modifier un plan validé est
  permis ; la machine dit ce que ça invalide et ne refait que ça.
- **Le document d'abord.** Une fonctionnalité qui n'est pas dans
  `REQUIREMENTS.md` ne se code pas. Une exigence livrée, c'est du code, un test
  et une ligne de changelog.

## 5. Ce que Riot Machine n'est pas

- Pas un générateur de clip en un clic : Michael réalise, plan par plan, avec ses
  timecodes.
- Pas une application multi-utilisateurs ni un produit commercial, pour
  l'instant. Un seul utilisateur, un PC Linux à la maison, Tailscale, Telegram.
- Pas un atelier de modèles : les fournisseurs se déclarent dans
  `config/models.yaml`, on n'écrit pas de code par modèle hors de cette
  configuration.

## 6. Qui fait quoi

| Qui | Fait | Ne fait pas |
|---|---|---|
| **Michael** | Concept, script, timecodes, choix de la canon, validation du découpage, tri des visuels en grille, validation des finals, accords de dépense par lot, réglage des seuils | Écrire des prompts, choisir un modèle, surveiller une génération |
| **Orchestrateur** (Claude Code, `CLAUDE.md`) | Fait avancer les plans, distribue aux agents, trie les retours, résume | Valider, dépenser hors accord, modifier la baseline |
| **script-doctor** | Complète le découpage (cadrage, mouvement, caméra, chanté) dans la version de production, écrit ses remarques | Toucher aux timecodes, réécrire la baseline |
| **storyboard** | Prompt image et lancement du visuel, en embarquant canon, ADN, look, décor | Juger son propre résultat |
| **controleur** | Identité, anatomie, artefacts, fidélité HD ; score et verdict stockés | Juger les choix artistiques |
| **routeur** / **prompteur** | Modèle le moins cher qui tient le palier ; prompt vidéo adapté | Dépasser le plafond du mode ou du lot |
| **decorateur** / **directeur-casting** | Fiches et références des décors ; packs des personnages | Choisir la canon, valider une version |
| **finition** | Dépannage HD et lip-sync | — |
| **Worker** | Suit les générations, enchaîne les étapes automatiques, réveille l'orchestrateur, notifie par lot | Décider |

## 7. Vocabulaire ajouté

| Terme | Sens |
|---|---|
| **Baseline** | Le texte de Michael pour un plan, un bloc ou un personnage, tel qu'il l'a écrit. Jamais modifié par un agent. |
| **Version de production** | La version complétée par les agents, à partir de la baseline. |
| **Mode** | Brouillon, standard ou final. Fixé au clip, surchargeable par bloc et par plan. Détermine les étapes faites, sautées, et la qualité demandée. |
| **Lot** | Un ensemble de plans traités ensemble : en général les plans d'un bloc à une étape donnée. Unité de l'accord de dépense, de la validation en grille et de la notification. |
| **Révision** | Une modification journalisée d'un plan validé, avec ses conséquences (ce qui est conservé, ce qui est à refaire). |

## 8. Le jalon : clip zéro

Avant toute autre évolution, un clip zéro sort de la machine :

- un bloc du premier morceau de JJ (le refrain), 8 à 10 plans, 25 à 35 s ;
- en mode brouillon, de bout en bout jusqu'au montage ;
- moins de 10 $ de génération, sur les crédits Vertex ou fal ;
- avec, à la fin, la liste des irritants rencontrés, qui alimente
  `REQUIREMENTS.md`.

Tant que le clip zéro n'est pas livré, aucune fonctionnalité hors des exigences
P0 ne se développe.
