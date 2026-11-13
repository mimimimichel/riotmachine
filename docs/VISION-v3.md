# Riot Machine — Vision

Version 3.0 — 12 novembre 2026. Remplace les versions précédentes.

Ce document donne le sens et la logique d'ensemble. `SPEC-v3.md` dit quoi
construire, `PRODUCTION-PLANS-v3.md` détaille la fabrication des plans. En cas de
doute sur une décision de conception, c'est ce document qui tranche.

## 1. Ce qu'est Riot Machine

Riot Machine est un **label d'artistes IA** et le studio qui produit leurs
clips. Un label développe des artistes dans la durée : une identité, un
univers, une suite de sorties qui se répondent. Ce n'est pas un générateur de
vidéos indépendantes les unes des autres.

- Le label est indépendant : rock, électro, pop, esprit rebelle.
- **JJ** est la première artiste. D'autres artistes et des groupes suivront.
- Michael est le fondateur, le scénariste et le réalisateur. Il écrit, il a les
  idées, il choisit, il valide. Tout le travail technique est fait par des
  agents et par du code.
- La musique et les paroles existent avant le clip (générées par ailleurs).

Le studio réussit quand un clip sort, puis un autre, et qu'on reconnaît
l'artiste de l'un à l'autre.

## 2. Ce qui nous distingue

Les outils du marché (Freebeat, LTX Studio, Higgsfield, Flow, Neural Frames)
pensent « un morceau, une vidéo ». Ils font bien certaines choses, et on les
reprend : analyse du morceau, éléments réutilisables, langage de caméra,
prolongement d'une prise, retouche d'une prise. Ce qu'aucun ne fait :

1. **L'artiste d'abord.** Une bible d'artiste (identité, univers, façon de
   bouger et de chanter) qui dure et que tous les clips respectent.
2. **Une bibliothèque de label.** Décors, objets, figurants, looks, plans de
   coupe : ce qui a été créé une fois peut resservir, quand Michael le décide.
3. **Un réalisateur aux commandes.** Découpage sur la musique, plan par plan,
   avec ses mots conservés, et des corrections au bon niveau.
4. **Le coût sous contrôle.** Le modèle le moins cher qui tient le besoin, les
   crédits gratuits d'abord, jamais de dépense sans accord.
5. **Indépendant des modèles.** Les modèles changent tous les mois ; le studio
   les traite comme des fournisseurs interchangeables décrits dans un catalogue.

## 3. La trajectoire

| Phase | But | Moyens | On passe à la suite quand |
|---|---|---|---|
| **0. Rodage** (en cours) | Sortir le **clip zéro** : un bloc du premier morceau de JJ, 8 à 10 plans | Crédits offerts (Google Cloud, Veo), tout en brouillon | Le clip zéro est monté, pour moins de 10 $ de crédits consommés, et la liste des irritants est écrite |
| **1. Viabilité** | Un premier clip complet de JJ, publiable | Crédits offerts d'abord | Coût ≤ 50 € (cible 20 €), temps de Michael raisonnable, qualité qu'il assume de publier |
| **2. Qualité** | 3 ou 4 clips de JJ, avec leurs déclinaisons | Modèles payants là où ils apportent quelque chose | JJ a une présence et un public |
| **3. Label** | D'autres artistes, des groupes | Bibliothèque et bibles partagées | — |
| **4. Ouverture** (option) | Proposer l'outil ou le service à d'autres | À décider selon ce que la phase 2 aura montré | — |

Veo n'est qu'un moyen de la phase 0. Rien dans la conception ne doit dépendre
d'un modèle en particulier.

Tant que le clip zéro n'est pas sorti, on ne construit que ce qui y mène. Le
modèle de données, lui, est posé dès maintenant pour le label entier, afin de
ne pas le refaire.

## 4. Les objets, du label au plan

```
Label
 ├─ Bibliothèque      décors, objets, figurants, looks, plans de coupe
 ├─ Portefeuille      réserves de crédits (offerts, achetés)
 ├─ Catalogue         modèles, capacités, prix
 └─ Artiste           (ou groupe d'artistes)
     ├─ Bible         identité (versions, canon, ADN, pack) + univers
     └─ Clip          un morceau, un brief, une note d'intention
         ├─ Bloc      partie du morceau
         ├─ Séquence  même lieu, même moment, même tenue
         │   └─ Plan  les mots de Michael, un début, une fin
         ├─ Prise     une vidéo générée, pour un ou plusieurs plans
         ├─ Montage   déduit du découpage
         └─ Déclinaisons  vertical, teasers, boucle, vidéo paroles
```

Règles de fond :
- **L'identité suit l'artiste** dans tous ses clips. Tout le reste (décors,
  objets, tenues, palette) ne se réutilise que si Michael le choisit pour ce
  clip. Le brief du clip prime sur la bible.
- **Un clip épingle** les versions qu'il utilise. Faire évoluer JJ ne change
  pas un clip en cours.
- **Le plan est l'unité de regard**, la prise l'unité de fabrication.

## 5. Le parcours d'un clip

1. **Brief** : Michael dépose le morceau, son concept, ses références, et
   choisit dans la bibliothèque ce qu'il reprend.
2. **Analyse du morceau** : temps, sections, énergie, paroles calées.
3. **Note d'intention** : une page, validée par Michael, lue par tous les agents.
4. **Découpage** : séquences et plans, proposés par le script-doctor ou écrits
   par Michael, validés par bloc. Animatique en cartons sur la musique.
5. **Préparation** : image maîtresse de chaque séquence ; le planificateur
   propose les prises, l'offre et le coût.
6. **Plan de tournage** : Michael accorde la dépense.
7. **Tournage**, puis **dérushage** plan par plan : garder, refaire, prolonger,
   retoucher, changer d'offre.
8. **Montage** automatique, **déclinaisons**, export.

À chaque étape, Michael voit ce qui a été fait et par qui, et peut corriger à
l'endroit précis sans refaire le reste.

## 6. Qui fait quoi

| Qui | Rôle |
|---|---|
| **Michael** | Idées, brief, mots des plans, choix des références, validations, accords de dépense, garder ou refuser |
| **Assistant de régie** | L'interlocuteur unique : Michael lui parle, il route vers le bon acteur et rend compte |
| **script-doctor** | Mise en scène : séquences, plans, timecodes, propositions quand le découpage doit changer |
| **décorateur, directeur de casting** | Bibliothèque, images maîtresses, packs d'artistes |
| **prompteur** | L'action et la caméra de chaque plan |
| **contrôleur** | Signale les écarts à la bible et à l'image maîtresse |
| **veilleur** | Tient le catalogue des modèles à jour |
| **Le code** (planificateur, worker, montage) | Tout ce qui se calcule : choix de l'offre, regroupement en prises, coûts, timecodes, suivi des générations, montage |

Un agent ne décide jamais à la place de Michael sur le plan créatif, ne dépense
jamais sans accord, et ne note pas son propre travail.

## 7. Principes de conception

1. **Le label avant le clip.** Toute donnée se range au bon étage (label,
   artiste, clip) pour pouvoir resservir.
2. **La baseline de Michael est intouchable.** Ses mots sont conservés à part ;
   les agents écrivent à côté.
3. **Tout est tracé et corrigeable au bon niveau.** Chaque étape laisse une
   ligne lisible avec une entrée « Corriger ».
4. **Le découpage est de la mise en scène.** La machine mesure les impacts, le
   script-doctor propose, Michael choisit. Rien ne se décale tout seul.
5. **Ce qui se calcule est du code**, déterministe et testé. Les agents ne
   servent qu'à ce qui demande du jugement.
6. **Indépendance des modèles.** Tout passe par le catalogue. Une fonction
   demandée que l'offre choisie ne sait pas faire déclenche un avertissement et
   la recommandation d'une offre qui la couvre.
7. **Rien n'est dépensé sans accord**, sur un montant affiché. Le gratuit
   d'abord, puis les crédits détenus, puis le paiement direct.
8. **Sobre et rapide.** Aucun agent ne tourne sur une minuterie. Un agent n'est
   appelé que sur un événement qui le demande, avec le contexte minimal. La
   régie répond vite, sur téléphone.
9. **Robuste.** Une panne, une coupure ou un redémarrage ne perd rien et ne
   paie rien deux fois.
10. **Le document d'abord.** Rien ne se code qui ne soit dans la spec. Une
    exigence livrée, c'est un test, du code et une ligne de changelog.

## 8. Ce que Riot Machine n'est pas

- Pas un générateur en un clic : pas de mode « tout automatique ».
- Pas un logiciel de montage manuel : le montage se déduit du découpage, et
  s'exporte vers un logiciel de montage pour les finitions à la main.
- Pas un outil multi-utilisateurs, pour l'instant : un utilisateur, un PC Linux
  à la maison, accès distant par Tailscale, agents sur l'abonnement Claude.
- Pas un atelier de modèles : aucun code propre à un modèle hors du catalogue.

## 9. Vocabulaire

| Terme | Sens |
|---|---|
| **Bible d'artiste** | Identité (versions, canon, ADN, pack) et univers (palette, lumière, lieux, objets, gestuelle, interdits) |
| **Bibliothèque** | Les éléments du label réutilisables, versionnés |
| **Brief** | Ce que Michael donne pour un clip : concept, références, choix de réutilisation |
| **Note d'intention** | La page qui fixe concept, arc, palette et références du clip |
| **Baseline** | Les mots de Michael, jamais modifiés par un agent |
| **Séquence** | Unité de mise en scène : même lieu, même moment, même tenue |
| **Plan** | Unité de montage, à ses timecodes |
| **Prise** | Une vidéo générée ; elle couvre un ou plusieurs plans |
| **Fenêtre** | La portion d'une prise utilisée par un plan |
| **Profil** | Le type de besoin d'une séquence (décor, action, jeu, chant…) |
| **Offre** | Un modèle chez un fournisseur, à un prix |
| **Réserve** | Des crédits offerts ou achetés chez un fournisseur |
| **Point fixe** | Un timecode qui ne bouge pas sans décision explicite |
| **Plan A, plan B** | Performance ou récit ; plan de coupe réutilisable |
| **Déclinaison** | Une sortie dérivée du clip : vertical, teaser, boucle, vidéo paroles |
| **Clip zéro** | Le premier bloc tourné de bout en bout, jalon de la phase 0 |
