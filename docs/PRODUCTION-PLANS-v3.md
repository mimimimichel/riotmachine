# Riot Machine — Production des plans

Version 3.1 — 13 novembre 2026. Fait partie de `SPEC-v3.md` (v3.1), à lire après
`VISION-v3.md`. Remplace dans `PROCESS.md` l'ancienne chaîne visuel draft → HD →
plan vidéo → draft → HD.

## 1. Constats

Usage sur le bloc 1 et test Veo du 11/11
(`studio/tests/veo-modes-2026-11-11/RAPPORT.md`) :

- La vidéo ne recevait que le visuel du plan, jamais les références : toute
  erreur du visuel (cadenas, mauvais sac) passait dans la vidéo.
- Le visuel, image « représentative », servait de première image : la vidéo
  démarrait au milieu de l'action.
- Le prompteur réécrivait la tenue de mémoire (« navy blazer, white blouse »).
- Sept passages par plan, pour un rendu en dessous du niveau.
- Les modèles actuels génèrent directement à partir de références, et
  plusieurs plans dans une même génération. Veo 3.1 Fast l'a confirmé pour les
  références ; Standard joue mieux la consigne.
- Le filtre de Google refuse certaines références et parfois une vidéo en
  sortie, sans frais, de façon en partie aléatoire.
- Chaque modèle a ses limites (durée d'une génération, nombre de plans, nombre
  de références, prix). Elles changent tous les mois.

## 2. Le besoin

> Je décris mes séquences et mes plans. La machine me dit comment elle les
> tournerait, avec quel modèle et pour combien. Je valide la dépense, elle
> tourne, je dérushe plan par plan. Je vois tout ce qui a été fait, par qui,
> et je peux corriger au bon endroit sans refaire le reste. Je ne paie jamais
> plus que nécessaire, et jamais sans avoir dit oui.

## 3. Principes

1. **Indépendant du modèle.** Aucune règle propre à un modèle dans le code.
   Tout passe par le catalogue (§6). Veo n'est qu'une ligne du catalogue,
   utilisée pour le rodage parce que ses crédits sont offerts.
2. **Le découpage est de la mise en scène.** Il ne dépend pas du modèle. Seul
   le regroupement des plans en prises en dépend.
3. **Ce qui se calcule est du code.** Choix du modèle, regroupement, durées,
   coûts, contrôle des timecodes : déterministe, testé, instantané. Les agents
   font ce qui demande du jugement (mise en scène, écriture, contrôle visuel).
4. **Rien n'est dépensé sans l'accord de Michael**, sur un montant affiché.
   Seule exception : une relance non facturée par le fournisseur.
5. **Le moins cher qui tient le besoin**, payé d'abord par le gratuit, puis par
   les crédits déjà détenus, puis en direct.
6. **Tout est visible et corrigeable au bon niveau.** Chaque étape, même
   automatique, laisse une trace lisible avec une entrée « Corriger ».
7. **Le plan reste l'unité de regard.** On tourne par prise, on juge et on
   corrige par plan.

## 4. Les objets

```
Clip
 ├─ Bloc        partie du morceau (intro, couplet, refrain) ; unité de validation du découpage
 ├─ Séquence    unité de mise en scène : même lieu, même moment, même tenue, mêmes figurants
 │   └─ Plan    unité de montage : mots de Michael, début, fin ; appartient à un bloc et à une séquence
 └─ Prise       une vidéo générée ; couvre un ou plusieurs plans d'une même séquence
     └─ Fenêtre la portion de la prise utilisée par un plan
```

| Objet | Précisions |
|---|---|
| **Séquence** | Porte un **profil** (§7), une **fiche** (lieu, heure, météo, lumière, palette, figurants) et une **image maîtresse** validée par Michael. Ses plans peuvent ne pas se suivre dans le morceau (une performance entrecoupée d'autres plans). Une séquence peut couvrir plusieurs blocs : seuls les plans des blocs validés se tournent ; une prise ne regroupe que des plans de blocs validés. |
| **Plan** | Garde ses timecodes quoi qu'il arrive aux prises. Attributs : `personnages`, `jeu` (aucun, présent, porteur), `chanté`, `dansé`, `composition` (libre, stricte), `mouvement`, `axe` (étiquette libre : deux plans de même axe peuvent sortir d'une même prise continue), `rôle` (A : performance ou récit ; B : plan de coupe, versable à la banque de l'artiste), **caméra** en champs (`cadrage`, `focale`, `angle`, `hauteur`, `mouvement de caméra`, `vitesse`), **jeu** par personnage (`émotion`, intention, en quelques mots). |
| **Prise** | Mode, offre (modèle + fournisseur), durée, prompt assemblé, références envoyées, coût, réserve débitée, statut, motif de refus. Deux formes quand elle couvre plusieurs plans : **continue** (un axe, une action, découpée en fenêtres) ou **multi-plans** (coupes demandées dans le prompt). |
| **Fenêtre** | Début et fin dans la prise, vitesse (1,0 par défaut, 0,9 à 1,1 au plus). Une prise gardée pour un plan = une fenêtre gardée. |
| **Offre** | Un modèle chez un fournisseur, avec son prix. On compare des offres, pas des modèles. |
| **Réserve** | Des crédits gratuits, offerts ou achetés chez un fournisseur : solde, expiration. |
| **Lot** | Les prises soumises ensemble à l'accord de Michael, avec leur total. |

Schéma : tables `sequences`, `takes`, `take_shots` (prise, plan, fenêtre,
vitesse, gardée), `reserves`, `steps` (fil de production, §12) ; colonnes
ajoutées à `shots` (`sequence_id`, attributs ci-dessus). Les tables `assets`
vidéo existantes sont migrées en prises. Les anciens visuels de plan sont
archivés et rattachés à leur plan : consultables, jamais envoyés à un modèle,
sauf si Michael en choisit un comme image maîtresse.

## 5. Les rôles

| Qui | Nature | Fait | Ne fait pas |
|---|---|---|---|
| **Michael** | — | Écrit ou corrige séquences et plans, valide le découpage, l'image maîtresse, chaque dépense, garde ou refuse chaque plan | Choisir un agent, écrire un prompt |
| **script-doctor** | agent | Propose séquences, plans et timecodes calés sur l'analyse du morceau ; remplit attributs, profil, fiche de séquence ; propose comment résoudre tout changement d'un découpage validé (§14.1) | Connaître les modèles ; appliquer un changement sans l'accord de Michael |
| **décorateur** | agent | Fiches de décor, objets, figurants ; propose l'image maîtresse | La valider |
| **planificateur** | **code** | Choisit l'offre, regroupe les plans en prises, calcule durées et coûts, contrôle les timecodes, place les fenêtres | Juger |
| **prompteur** | agent | Écrit Action et Caméra/lumière ; la machine assemble et met au format du modèle | Écrire identité, tenue, objets, décor |
| **contrôleur** | agent | Compare chaque prise à la canon et à l'image maîtresse ; signale les écarts | Bloquer : il signale, Michael décide |
| **orchestrateur** | agent | Route les corrections de Michael vers le bon acteur ; résume | Dépenser, valider |
| **veilleur** | agent, périodique | Vérifie le catalogue (prix, durées, nouveaux modèles), propose les mises à jour | Les appliquer sans accord |
| **worker** | code | Lance ce qui est accordé, suit les générations, relance le non-facturé | Décider |

Changement par rapport à `PROCESS.md` : le script-doctor peut désormais
proposer les timecodes. Une fois le découpage validé, seule une décision de
Michael les change.

## 6. Le catalogue des modèles

`config/models.yaml` est la seule source des capacités et des prix des modèles
de vidéo, d'image et de lip-sync (champ `kind: video | image | lipsync`). Chaque
entrée porte `verified_at` et `source` ; une entrée non vérifiée depuis plus de
45 jours est signalée dans la régie.

```yaml
models:
  veo-3.1-fast:
    capabilities:
      modes:
        references:   {durations: [8], max_refs: {image: 3}}
        first_last:   {durations: [4, 6, 8]}
        image_start:  {durations: [4, 6, 8]}
        text:         {durations: [4, 6, 8]}
      exclusive: [[references, first_last], [references, image_start]]
      multi_shot:  {max_shots: 3, cuts: approximate, syntax: timestamps}
      resolutions: [720p, 1080p]
      audio_optional: true
      extend: true              # prolonger une prise
      continue_from_frame: true # démarrer sur la dernière image d'une prise
      edit_object: false        # ajouter ou retirer un objet dans une prise
      upscale_same_video: false
    profiles: {decor: ok, action: ok, jeu: weak, chant_serre: weak, chant_danse_large: no,
               multi_personnages: weak, composition_stricte: ok}
    prompt_dialect: veo
    offers:
      - provider: vertex
        price_per_s: {720p: 0.08, 1080p: 0.10}     # sans audio
        reserve: google-cloud-trial
        refusals_billed: false
    verified_at: 2026-11-11
    source: test veo-modes-2026-11-11
```

Valeurs initiales à saisir. Seul Veo est vérifié par un test ; les autres
viennent de pages de fournisseurs lues le 11/11 et portent `verified: false`
jusqu'à leur premier essai.

| Modèle | Durée d'une prise | Plans par prise | Références | Prix indicatif (720p ou proche) |
|---|---|---|---|---|
| Veo 3.1 Lite | 4, 6, 8 s | — | aucune | 0,05 $/s (ouverture sur Vertex à vérifier) |
| Veo 3.1 Fast | 4, 6, 8 s (8 en références) | 2 à 3, coupes approximatives | 3 images | 0,08 $/s |
| Veo 3.1 Standard | idem | idem | 3 images | 0,20 $/s |
| Kling 3.0 | 3 à 15 s | 2 à 6, durée fixée par plan | 4 images | 0,08 à 0,17 $/s selon l'offre |
| Seedance 2.0 | 4 à 15 s | jusqu'à 4 | 9 images, 3 vidéos, 3 audios | 0,30 $/s |
| Seedance 2.5 | 4 à 30 s | plusieurs | 30 images, 10 vidéos, 10 audios | 0,47 $/s |
| MiniMax H3 | 4 à 15 s | à vérifier | 9 images, 3 vidéos, 3 audios | 0,08 $/s officiel ; 0,03 $/s chez un hébergeur (poids ouverts) |

**Compatibilité.** Toute fonction demandée (mode, nombre de références, plans
par prise, durée, prolonger, plan suivant, retouche d'objet, audio en
référence) est vérifiée contre l'offre choisie. Si l'offre ne la couvre pas,
la régie affiche un avertissement sur place et recommande l'offre la moins
chère qui la couvre, avec l'écart de coût et les conséquences (R-H28).

Les notes `ok / weak / no` par profil sont des déclarations de départ. Le
**carnet de rodage** (taux de plans gardés par offre et par profil) les corrige :
sous 40 % de plans gardés sur au moins 5 essais, une offre passe à `weak` pour
ce profil et la régie le dit.

## 7. Les profils

Michael et le script-doctor manipulent des profils, pas des modèles.

| Profil | Quand | Capacités exigées |
|---|---|---|
| `decor` | aucun personnage | — |
| `action` | personnage, jeu aucun ou présent | références de personnage |
| `jeu` | le visage ou l'action porte le plan | références ; `jeu: ok` |
| `chant_serre` | chanté, cadrage serré | références ; lip-sync possible ensuite |
| `chant_danse_large` | chanté et dansé, plan large | références ; mouvement fort ; audio en référence souhaité |
| `multi_personnages` | deux personnages ou plus identifiables | assez de références pour chacun |
| `composition_stricte` (P1) | départ et arrivée imposés | mode première + dernière image ; les deux images sont générées avec les références du personnage. Jusqu'au clip zéro, un tel plan part en mode références. |

Le profil d'une séquence est le plus exigeant de ses plans, sauf si le
planificateur sépare les plans exigeants dans leur propre prise (§8).

## 8. Le planificateur

Fonction pure : `(séquence, plans, catalogue, réserves, qualité du clip) →
prises proposées`. Mêmes entrées, même sortie. Aucun appel à un modèle.

1. **Offres candidates** : celles dont les capacités couvrent le profil et dont
   le fournisseur est branché. Une offre `weak` reste candidate mais marquée.
2. **Classement** : d'abord par source de paiement (gratuit, réserve détenue,
   paiement direct), puis par coût total de la séquence, puis par taux du
   carnet de rodage. Une offre `weak` moins chère qu'une offre `ok` n'est pas
   retenue par défaut : elle est listée en alternative avec son avertissement.
3. **Regroupement** des plans de la séquence en prises, pour l'offre retenue :
   - plans de même `axe` → une prise **continue** si la somme des fenêtres
     tient dans la durée maximale ;
   - plans qui se suivent dans le morceau → une prise **multi-plans** si
     l'offre le permet, dans la limite de `max_shots` et de la durée maximale
     moins une marge (0,5 s par coupe si `cuts: approximate`, aucune si les
     durées par plan sont fixées par l'API) ;
   - un plan `jeu: porteur` ou `chant_serre` est seul dans sa prise ;
   - (P1) un plan `composition: stricte` est seul, en mode première + dernière image ;
     jusqu'au clip zéro, il part en mode références.
4. **Durée de prise** : la plus petite durée permise par l'offre et le mode qui
   couvre les plans regroupés.
5. **Alertes**, avec proposition : plan plus long que le maximum de l'offre
   (couper au temps fort le plus proche, enchaîner deux prises, ou offre qui
   tient la durée) ; secondes payées non utilisées au-delà de 40 %.
6. **Résolution** selon la qualité du clip (`brouillon` : la plus basse de
   l'offre ; `final` : 1080p ou la plus haute). Si l'offre a
   `upscale_same_video`, le brouillon peut être agrandi au lieu d'être refait.
7. **Contrôle des timecodes** à chaque écriture : bornes du morceau ; trou et
   chevauchement signalés « à résoudre » (§14.1), jamais corrigés d'office.

Après tournage, le code détecte les coupes réelles d'une prise multi-plans,
place les fenêtres, et signale tout écart supérieur à 0,3 s avec deux issues :
ajuster la vitesse (dans 0,9 à 1,1) ou refaire.

## 9. Le prompt

Assemblé par la machine, mis au format du modèle par un **dialecte**
(`prompt_dialect` : horodatage pour Veo, plans séparés pour Kling, etc.).

| Bloc | Source | Écrit par |
|---|---|---|
| Identité | ADN de la version castée | référentiel |
| Tenue | look du clip | référentiel |
| Style de l'artiste | bible d'artiste, pour ce que le clip a choisi d'en reprendre (palette, lumière, gestuelle) | référentiel |
| Objets | fiches des objets liés aux plans | référentiel |
| Décor, ambiance | fiche de séquence | référentiel |
| Action, par plan | début → déroulé → fin, au présent ; dit quand le visage est visible si `jeu` ≠ aucun | prompteur |
| Caméra, par plan | champs caméra du plan, traduits par le dialecte | machine |
| Jeu, par personnage | champ émotion et intention | machine |
| Lumière, par plan | ce que la fiche de séquence ne dit pas | prompteur |
| À éviter | négatif du modèle + mots pièges | machine |

Contrôle des **mots pièges** sur les blocs écrits par un agent (`lock`,
`shoot`, `fire`, `crash`, `strike`, `cast`…), liste en configuration, enrichie
par les motifs « objet parasite » du dérushage. Un agent ne peut pas écrire un
bloc du référentiel.

## 10. Références et cohérence

**Références**
- Statut par fournisseur pour chaque image : `acceptée`, `refusée`, `non
  testée`, mis à jour à chaque appel.
- Sélection automatique dans la limite de l'offre, par priorité : visage,
  image maîtresse de la séquence, vue en pied (plan large), objet principal,
  autres. Seuls les éléments que Michael a choisis pour le clip sont
  candidats (`SPEC-v3.md` R-L3). Jamais une image « inspiration seulement ».
- Refus à l'entrée : référence acceptée suivante du même type ; aucune → prise
  `bloquée` avec le message et l'action possible.
- Refus en sortie non facturé : deux relances automatiques, puis `bloquée`.

**Cohérence d'un plan à l'autre**, de la plus forte à la plus faible :
1. même prise (continue ou multi-plans) ;
2. image maîtresse de la séquence en référence de toutes ses prises ;
3. fiche de séquence injectée mot pour mot dans tous les prompts ;
4. enchaînement : dernière image d'une prise comme première de la suivante,
   pour une action continue (quand le mode le permet) ;
5. étalonnage commun par séquence au montage ;
6. contrôleur : compare chaque prise à l'image maîtresse et signale les écarts.

Mélange de modèles dans une même séquence : autorisé, mais signalé.

## 11. Les dépenses

- Toute génération payante, **crédits offerts compris**, attend un accord sur un montant affiché :
  tournage, reprise, changement de modèle, image maîtresse, lip-sync.
  L'accord vaut jusqu'à ce montant ; au-delà, nouvel accord.
- L'exigence R-D2 (validation automatique sous un seuil) est supprimée.
- **Portefeuille** : liste des réserves (fournisseur, solde, expiration,
  origine : offert ou acheté). Chaque ligne de coût indique la réserve débitée.
  Une réserve qui expire dans moins de 15 jours est signalée.
- Le coût réel remplace l'estimation à la réception ; un refus non facturé
  coûte 0.

## 12. Le parcours et sa lisibilité

```
1 Découpage      script-doctor propose ─▶ [Michael valide, par bloc]
2 Préparation    décorateur : image maîtresse ─▶ [Michael valide, avec son coût]
                 planificateur : prises, offre, coût      prompteur : action, caméra
3 Plan de tournage ─▶ [Michael accorde la dépense, tout ou une sélection]
4 Tournage       worker (relances non facturées automatiques)      contrôleur
5 Dérushage ─▶ [Michael, plan par plan : garder, refaire, corriger]
6 Lip-sync des plans chantés gardés (P1, hors clip zéro) ─▶ [accord] ─▶ montage (jouable à tout moment)
```

États d'un plan : `à préparer`, `prêt`, `en tournage`, `à dérusher`, `gardé`,
`à refaire`, `bloqué`. Un plan `bloqué` dit pourquoi et quoi faire.

**Fil de production.** Chaque étape, humaine ou automatique, écrit une ligne
(`steps`) rattachée à la séquence, à la prise ou au plan : qui, quand, ce qui a
été décidé ou produit, pourquoi, coût, lien vers le détail. Chaque ligne a une
action « Corriger » qui ouvre un champ adressé à l'acteur de l'étape.

## 13. Les écrans

Téléphone d'abord, une main. Une décision par écran. Un défaut proposé pour
tout. Le coût avant l'action. Les mots de Michael toujours à côté de ce que la
machine en a fait.

**A. Découpage.** Les blocs, et dans chacun les séquences et leurs plans.
Chaque séquence porte une pastille indicative calculée en direct :
`action · Veo Fast · 2 prises · 1,28 $ · crédits Google`. Un plan hors limites
est signalé sur place avec sa correction. Toucher un plan ouvre sa page.

**B. Plan de tournage** (d'un bloc ou d'une séquence).

```
┌──────────────────────────────────────┐
│ ‹ JJ sort de chez elle     4 plans   │
│ action · image maîtresse ✓           │
├──────────────────────────────────────┤
│ PRISE A · multi-plans · 6 s payées 8 │
│  1 « Elle sort »              3,0 s  │
│  2 « Elle ferme à clé »       2,5 s  │
│ Veo Fast · visage, maîtresse, sac    │
│ 0,64 $ · crédits Google              │
├──────────────────────────────────────┤
│ PRISE B · multi-plans · 6,5 s        │
│  3 « Descend vers le vélo »   4,0 s  │
│  4 « Essuie la selle »        2,5 s  │
│ 0,64 $ · crédits Google              │
├──────────────────────────────────────┤
│ Autres offres pour la séquence       │
│  Kling 3.0 · 1 prise · 1,10 $ direct │
├──────────────────────────────────────┤
│ Total 1,28 $ · Google reste 289,10 $ │
│ [   Accorder et tourner — 1,28 $    ]│
└──────────────────────────────────────┘
```

Toucher une prise : prompt par blocs, références, raison du choix,
alternatives chiffrées, « sortir ce plan », « regrouper avec… ». Toucher
« Autres offres » change l'offre de toute la séquence et recalcule.

**C. Séquence.** Fiche, image maîtresse, fil de production, prises et leur état.

**D. Page du plan.** Mots de Michael, version de production, attributs ;
toutes ses prises côte à côte (fenêtre, offre, coût, verdict du contrôleur) ;
son fil ; « voir dans le découpage ».

**E. Dérushage.** Un plan à la fois, en boucle sur la musique à son timecode ;
« dans la séquence » le joue entre ses voisins. Bande de la prise avec la
fenêtre, déplaçable. Actions : **Garder**, **Refaire**, **Changer d'offre**,
et selon les capacités de l'offre : **Prolonger** (allonge la prise à partir de
ses dernières images), **Plan suivant** (nouvelle prise qui démarre sur la
dernière image de celle-ci), **Retoucher** (ajouter ou retirer un objet dans la
prise gardée). Une action que l'offre ne couvre pas reste visible, avec
l'avertissement et l'offre recommandée.
Refaire propose des motifs :

| Motif | Suite proposée |
|---|---|
| Visage | autre référence de visage ; puis offre mieux notée en `jeu` |
| Tenue ou objet faux | vérifie les blocs injectés, ajoute la référence de l'objet |
| Objet parasite | retouche de la prise si l'offre le permet ; sinon reprise ; ajout au négatif et aux mots pièges |
| Action, jeu | bloc Action renvoyé au prompteur avec le commentaire |
| Début ou fin du plan | mode première + dernière image |
| Mains, déformation | relance ; puis offre au-dessus |
| Raccord avec les voisins | même prise que le voisin, ou enchaînement |
| Rythme, durée | fenêtre, vitesse, ou retouche du découpage |

Chaque suite affiche ce qu'elle garde, ce qu'elle refait, son coût, et attend
l'accord. Le texte libre seul est routé par l'orchestrateur.

**F. Portefeuille.** Réserves, soldes, expirations, dépenses par clip.

## 14. Corriger au bon niveau

Le retour se fait toujours sur l'objet concerné ; Michael ne choisit jamais
l'acteur.

| Niveau | Demande | Gardé | Refait |
|---|---|---|---|
| Plan dans une prise | déplacer la fenêtre, ajuster la vitesse | tout | rien (gratuit) |
| Plan dans une prise | « refaire seul » | les fenêtres des autres plans | une prise pour ce plan |
| Plan dans une prise | « retoucher » : ajouter ou retirer un objet (si `edit_object`) | la prise | une version retouchée, au prix affiché |
| Prise | prolonger, plan suivant (si l'offre le permet) | la prise | la suite |
| Prise | refaire avec un motif | découpage, références | la prise |
| Prise | changer d'offre | contenu du prompt, références | regroupement, format, prise |
| Regroupement | sortir un plan, regrouper | les prises non touchées | les prises concernées |
| Séquence | profil, fiche, image maîtresse, offre | découpage | les prises marquées « à refaire » |
| Découpage | modifier, retirer, abandonner un plan | tout, tant que rien n'est choisi | selon la proposition du script-doctor retenue (§14.1) |

Une ancienne prise n'est jamais supprimée : elle reste comparable et gardable.

### 14.1 Modifier un découpage validé

Un changement de découpage est une question de mise en scène, pas de calcul.
La machine ne décale ni n'étire jamais rien d'elle-même. Elle mesure l'impact ;
le **script-doctor** propose comment le résoudre ; Michael choisit.

**Chaque plan se modifie indépendamment.** Raccourcir, rallonger, déplacer ou
retirer un plan ne touche pas ses voisins. Cela peut laisser un trou ou créer
un chevauchement : c'est un état permis, visible, marqué « à résoudre ». Tant
qu'il n'est pas résolu, la zone ne se tourne pas, et le montage y affiche un
carton.

**Ce qui déclenche une proposition**
- Michael modifie ou retire un plan.
- Michael abandonne un plan au dérushage (motif « Impossible à tourner » :
  « la clé dans la serrure, Veo n'y arrive pas »).
- (P1, R-H27) La machine détecte une anomalie : trou, chevauchement, plan plus long que le
  maximum de son offre, plan chanté décalé de sa parole, coupe qui a quitté son
  temps, prise qui ne couvre plus son plan.
- Michael demande « propose autre chose » sur un plan ou une séquence.

**Étape 1 : la machine mesure (code).** Elle établit la fiche d'impact :
- la zone à résoudre (de quand à quand, combien de secondes) ;
- ce qui l'entoure : séquence et bloc de chaque voisin, paroles et temps
  forts dans la zone ;
- les **points fixes** à ne pas déplacer : limites de bloc et de séquence,
  début d'un plan chanté, plan marqué « calé » par Michael ;
- la matière déjà payée : secondes non utilisées dans les prises voisines,
  prises gardées, anciennes prises ;
- les limites de l'offre de la séquence (durée d'une prise, plans par prise).

**Étape 2 : le script-doctor propose (agent).** À partir de la fiche, du
découpage complet, du dossier de réalisation et des retours de Michael, il
écrit deux ou trois propositions de mise en scène, en phrases, chacune avec le
nouveau découpage de la zone. Règles :
- ne déplacer aucun point fixe, sauf proposition qui le dit explicitement ;
- rester dans la séquence quand c'est possible ; ne jamais faire commencer plus
  tôt un plan d'une autre séquence ;
- préférer ce qui réutilise la matière existante ;
- dire pourquoi, en une phrase ;
- tenir compte de la raison de l'abandon (ne pas reproposer l'action qui ne
  se tourne pas).

Exemples :
> « Je prolonge le plan 1 par un zoom arrière sur la maison. Le plan 3, qui
> ouvre le refrain, ne bouge pas. La prise A a 1,5 s non utilisées. »
>
> « Je remplace les plans 2 et 3 par un plan-séquence : JJ marche vers le
> portail en chantant, en une prise. »

**Étape 3 : la machine chiffre (code).** Pour chaque proposition, le
planificateur calcule : timecodes avant et après, prises conservées, prises à
refaire avec leur coût et la réserve débitée, lip-sync à refaire, coupes hors
temps. Une proposition qui viole un invariant ou un point fixe sans le dire
est rejetée avant d'être montrée.

**Étape 4 : Michael choisit.**

```
┌──────────────────────────────────────┐
│ ‹ À résoudre · 0:11.5 → 0:14.0       │
│ Plan 2 « ferme à clé » abandonné     │
│ ▁▂▅▇▅▂▁▂▅▇▅▂▁▂▅▇▅▂   ▶ écouter la zone│
│ ├── 1 ──┤░░ trou 2,5 s ░░├─ 3 refrain│
├──────────────────────────────────────┤
│ ◉ Prolonger le plan 1 : zoom arrière │
│   sur la maison. Le refrain ne bouge │
│   pas.              gratuit (prise A)│
│ ○ Plan-séquence 2+3 : JJ marche vers │
│   le portail en chantant.            │
│                 1 prise · 0,64 $     │
│ ○ Plan de coupe : le chien à la      │
│   fenêtre.            1 prise · 0,64 $│
├──────────────────────────────────────┤
│ [ Choisir ] [ Autre idée… ] [ Laisser]│
└──────────────────────────────────────┘
```

- Chaque proposition se déplie : découpage de la zone avant et après, sur la
  forme d'onde, avec le son ; impact détaillé.
- **Autre idée…** : Michael écrit la sienne, ou commente une proposition ; le
  script-doctor repropose.
- **Laisser** : la zone reste « à résoudre ».
- Le choix s'applique en une révision, journalisée, annulable d'un geste. Les
  mots de Michael pour les plans retirés sont conservés dans l'historique.
- Toute dépense qui en découle passe par l'accord habituel.

**Le son sur les écrans de découpage.** Partout où un timecode se lit ou se
modifie : forme d'onde autour des plans, temps, sections, paroles, lecture en
boucle de la zone, image des prises quand elles existent. Les repères aident à
placer une coupe (aimantation aux temps, désactivable) ; ils ne déplacent rien
d'autre que ce que Michael touche.

Seuls ajustements sans proposition, parce qu'ils ne changent pas le découpage :
déplacer la fenêtre d'un plan dans sa prise, ajuster sa vitesse (0,9 à 1,1).

**Changer de modèle après un premier rendu** produit une autre vidéo. Sont
conservés : découpage, timecodes, contenu du prompt, références, image
maîtresse, retours. Sont recalculés : regroupement, format du prompt, choix
des références. La régie recommande de changer l'offre de la séquence entière
et avertit d'un mélange.

## 15. Exigences

Priorité P0 = nécessaire au clip zéro. Chaque exigence a au moins un test
nommé `test_r_hNN_…`.

| Id | Pr. | Énoncé | Critère d'acceptation |
|---|---|---|---|
| R-H1 | P0 | Objets séquence, prise, fenêtre (§4) ; migration des vidéos existantes en prises. | Deux plans sur une prise, fenêtres disjointes : le montage est correct. |
| R-H2 | P0 | Attributs de plan et profil de séquence, modifiables par Michael, journalisés. | Modifier `jeu` recalcule profil et proposition. |
| R-H3 | P0 | Catalogue (§6) : capacités par mode, offres, prix, réserve, `verified_at`. Aucune règle de modèle dans le code. | Ajouter un modèle fictif au YAML le rend proposable sans toucher au Python. |
| R-H4 | P0 | Planificateur déterministe (§8) : offres candidates, classement, regroupement, durées, alertes. | Un test par règle du §8 ; même entrée, même sortie ; séquence de 12 s : 2 prises avec une offre à 8 s, 1 prise avec une offre à 15 s. |
| R-H5 | P0 | Ordre de paiement gratuit → réserve → direct ; offre `weak` jamais choisie par défaut. | Tests de classement avec et sans réserve. |
| R-H6 | P0 | Prompt assemblé par blocs, dialecte par modèle, blocs du référentiel non éditables par un agent, contrôle des mots pièges. | Le prompt contient le texte du look ; « she locks the gate » est signalé ; sortie Veo en horodatage. |
| R-H7 | P0 | Références : statut par fournisseur, sélection par priorité dans la limite de l'offre, jamais d'image inspiration, repli sur refus à l'entrée. | Image `refusée` jamais envoyée ; prise `bloquée` avec message si aucun visage accepté. |
| R-H8 | P0 | Accord obligatoire avant toute génération payante, par lot, jusqu'au montant affiché ; relance automatique seulement si non facturée (2 au plus). R-D2 supprimée. | Aucune génération payante sans ligne d'accord ; dépassement refusé. |
| R-H9 | P0 | Réserves et portefeuille ; coût réel et réserve débitée sur chaque prise. | Solde décrémenté du coût réel ; refus non facturé = 0. |
| R-H10 | P0 | États du plan (§12) et migration des anciens statuts. | `STATUS_OWNER` couvre les sept états. |
| R-H11 | P0 | Fil de production : une ligne par étape, avec action « Corriger ». | Une séquence tournée en simulation a au moins les lignes script-doctor, planificateur, références, prompteur, tournage, contrôle. |
| R-H12 | P0 | Écran Plan de tournage (§13 B) : prises, offre, références, coût, réserve, autres offres, accord total ou partiel. | `POST /api/shoot` crée le lot ; rien ne part avant. |
| R-H13 | P0 | Page du plan et dérushage (§13 D, E) : prises côte à côte, fenêtre réglable, garder, refaire avec motif, changer d'offre. | Un test par motif : la suite proposée est celle de la table. |
| R-H14 | P0 | Détection des coupes d'une prise multi-plans, placement des fenêtres, signalement au-delà de 0,3 s. | Vidéo de test à coupe connue : fenêtres placées à ± 2 images. |
| R-H15 | P0 | Image maîtresse et fiche de séquence, validées par Michael, envoyées à toutes les prises de la séquence. | Référence et texte présents dans chaque prise. |
| R-H16 | P1 | Corrections par niveau (§14) : sortir un plan, regrouper, refaire seul, retouche de passage si l'offre le permet. | Un test par ligne de la table du §14. |
| R-H17 | P1 | Changement d'offre d'une séquence après rendu : recalcul, anciennes prises conservées, avertissement de mélange. | Test : avertissement présent, anciennes prises gardables. |
| R-H18 | P1 | Découpage proposé par le script-doctor à partir de `riot analyse` (séquences, plans, timecodes sur les temps) ; pastilles indicatives en direct dans l'écran Découpage. | La pastille change quand un plan change de durée. |
| R-H19 | P1 | Carnet de rodage : taux de plans gardés par offre et profil ; déclassement en `weak` selon la règle du §6. | 1 gardé sur 5 → `weak` pour ce profil. |
| R-H20 | P1 | Mode première + dernière image ; enchaînement entre prises. | Prompts image « first frame » / « last frame » avec les références. |
| R-H21 | P1 | Étalonnage commun par séquence au montage. | Les plans d'une séquence reçoivent le même filtre. |
| R-H22 | P1 | Contrôleur : écarts à la canon et à l'image maîtresse affichés au dérushage. | Verdict et note stockés sur la prise. |
| R-H25 | P0 | Modification d'un plan indépendante de ses voisins (§14.1) ; trou et chevauchement permis comme état « à résoudre », visibles, bloquant le tournage de la zone ; abandon d'un plan depuis le dérushage. | Retirer un plan ne change aucun timecode voisin ; la zone est marquée ; le tournage de la zone est refusé avec le message. |
| R-H26 | P0 | Résolution par proposition (§14.1), réduite pour le clip zéro. Déclencheur : Michael abandonne ou modifie un plan. Fiche d'impact calculée par le code, 2 ou 3 propositions de mise en scène écrites par le script-doctor, chiffrées par le planificateur, rejet des propositions qui violent un invariant ou un point fixe non annoncé, choix ou contre-proposition de Michael, application en une révision annulable. La détection continue d'anomalies relève de R-H27 (P1). | Plan abandonné avant un plan d'une autre séquence : aucune proposition ne déplace ce dernier ; chaque proposition porte coût et impact ; annuler restaure l'état exact. |
| R-H27 | P1 | Son sur les écrans de découpage (§14.1) : forme d'onde, temps, sections, paroles, lecture en boucle, aimantation désactivable. Points fixes (limites de bloc et de séquence, plans chantés, plans « calés »). Détection continue des anomalies. | Un test par anomalie ; un point fixe n'est jamais déplacé sans proposition explicite acceptée. |
| R-H28 | P0 | Vérification de compatibilité (§6) : avertissement sur place et recommandation de l'offre la moins chère qui couvre la fonction demandée. | Demander une retouche d'objet sur une offre sans `edit_object` affiche l'avertissement et une offre compatible chiffrée ; rien ne part. |
| R-H29 | P1 | Prolonger et Plan suivant depuis une prise gardée, proposés aussi par le script-doctor dans ses résolutions. | Prise prolongée liée à sa prise d'origine ; fenêtre étendue. |
| R-H30 | P1 | Retouche d'une prise gardée (ajout ou retrait d'un objet), comme nouvelle version de la prise. | L'ancienne version reste gardable ; coût et réserve affichés avant. |
| R-H31 | P0 | Champs caméra et champ de jeu par personnage sur le plan, rôle A ou B ; traduits dans le prompt par le dialecte. | Deux dialectes donnent deux formulations du même réglage de focale. |
| R-H23 | P2 | Veilleur du catalogue ; signalement des entrées de plus de 45 jours. | Entrée ancienne signalée dans la régie. |
| R-H24 | P2 | Brouillon agrandi quand l'offre a `upscale_same_video`. | — |

Les exigences des autres familles (label, données, préparation, montage,
régie, performance) sont dans `SPEC-v3.md`.

## 16. Livraison

L'ordre des lots est celui de `SPEC-v3.md` §8.

**Préalables hors code**
- Pack v2 de JJ accepté par Veo (visage trois quarts, profil, en pied par tenue).
- Essais de rodage à mener avec un brief de test et un budget, hors
  développement : prolonger, plan suivant et retouche d'objet par l'API de
  Veo, en plus de ceux-ci. À ajouter au test en cours (`veo-modes-2026-11-11`) :
  P4 (première + dernière image) ; une prise multi-plans 3 s + 4 s avec
  références ; une prise continue découpée en trois fenêtres ; un appel Veo
  Lite sur Vertex. Budget : 3 $.
