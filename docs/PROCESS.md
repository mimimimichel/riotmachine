# Le process de production d'un clip

Ce document est la référence. Le code, les consignes des agents (`CLAUDE.md`,
`.claude/agents/`) et la régie l'appliquent. Quand le process change, on modifie
d'abord ce document, puis le reste.

Dernière mise à jour : 22 octobre 2026.

## 1. Les rôles

| Qui | Rôle |
|---|---|
| **Michael** | Scénariste et réalisateur. Il écrit le concept, fixe le découpage et les timecodes, valide à chaque porte. Lui seul valide. |
| **Orchestrateur** | Chef de production (Claude Code, `CLAUDE.md`). Il fait avancer les plans, distribue le travail aux agents, trie les retours de Michael. |
| **script-doctor** | Lit le dossier, complète le découpage (cadrage, mouvement, caméra, plan chanté). Ne crée ni ne déplace aucun plan. |
| **storyboard** | Écrit le prompt et lance le visuel draft de chaque plan. |
| **controleur** | Contrôle indépendant avant Michael : identité, anatomie, artefacts, fidélité de la HD. Ne juge pas les choix artistiques. |
| **routeur** | Choisit le fournisseur et le modèle vidéo de chaque plan, le moins cher qui fera le travail, avec sa raison. |
| **prompteur** | Écrit le prompt vidéo adapté au modèle choisi. |
| **finition** | Dépanne la vidéo HD et le lip-sync. |
| **directeur-casting** | Génère le pack de référence d'un personnage d'après les instructions de Michael. |
| **Worker** | Programme qui tourne en continu. Il suit les générations, lance les étapes automatiques, envoie les notifications et réveille les agents. Il ne prend aucune décision. |

## 2. Vocabulaire

| Terme | Sens |
|---|---|
| **Clip** | Un morceau mis en images. Il vit dans le Studio. |
| **Bloc** | Une partie du morceau : intro, couplet 1, refrain… Il regroupe plusieurs plans. |
| **Plan** | Un plan du clip, avec un début et une fin fixés par Michael. |
| **Visuel draft** | L'image de travail d'un plan, en 1K. Elle sert à valider le cadrage, la pose, la lumière. |
| **Visuel HD** | Le visuel draft validé, agrandi sans être redessiné. C'est l'image de départ de la vidéo. |
| **Plan vidéo** | Le fournisseur, le modèle, le prompt vidéo et le coût estimé d'un plan, présentés à Michael avant toute dépense vidéo. |
| **Vidéo draft** | La première vidéo du plan, en basse résolution quand le modèle le permet. |
| **Vidéo HD** | La vidéo draft validée, agrandie (ou déjà en qualité finale selon le modèle). |
| **Lip-sync** | La bouche recalée sur la voix, pour les plans chantés. |
| **Canon** | L'image de vérité d'un personnage. Référence n°1 de toutes les générations. |
| **Pack** | Les images de référence d'un personnage : angles, silhouette, expressions, lumières, détails. |
| **Version** | Un état figé d'un personnage (canon + pack + ADN). Un clip utilise une version validée. |

## 3. Les étapes d'un clip

```
1 Concept ─▶ 2 Découpage ─▶ 3 Visuel draft ─▶ 4 Visuel HD ─▶ 5 Plan vidéo ─▶ 6 Vidéo draft ─▶ 7 Vidéo HD + lip-sync ─▶ 8 Montage
   Michael     Michael          storyboard        auto            routeur          auto               auto                  auto
               script-doctor    controleur        controleur      prompteur        controleur
   ─────────  [valide]          [valide]          [si écart]      [valide]         [valide]           [valide]
```

Après le découpage, chaque plan avance à son rythme, plan par plan. Un plan peut
être en vidéo pendant qu'un autre est encore en visuel draft.

### Étape 1 : Concept

- **Entrée** : le morceau (export Suno), la voix isolée (stem « vocals », pour le
  lip-sync), le pitch, le concept, le dossier de réalisation (direction
  artistique, storytelling, plans, références, infos clés ; PDF, Word, texte ou
  images), les paroles, le casting, le format de l'image, le budget de génération.
- **Où** : régie → Studio → Nouveau clip, puis onglet **Dossier**.
- **Sortie** : le dossier du clip (`studio/clips/<clip>/`). Chaque document reçoit
  une version texte que les agents lisent.

### Étape 2 : Découpage

- **Michael** saisit ses blocs et leurs plans avec les timecodes (onglet
  **Découpage**), ou les met dans son dossier. Les timecodes viennent de lui,
  en écoutant le morceau. Aucun agent ne les invente.
- **Michael** clique « Envoyer au script doctor » (onglet Dossier).
- **script-doctor** lit tout le dossier, reprend les blocs et plans tels quels,
  complète chaque plan (cadrage, mouvement, caméra, personnages, plan chanté,
  intention du bloc) et écrit ses remarques dans `script/notes.md`.
- **Porte : Michael valide le découpage**, le corrige directement, ou demande des
  changements. Une fois validé, le découpage ne se modifie plus que plan par plan.

### Étape 3 : Visuel draft

- **storyboard** écrit le prompt (en anglais) à partir du plan, de l'intention du
  bloc, du dossier et de la canon des personnages, puis lance la génération.
- **controleur** vérifie identité, anatomie, artefacts et respect du plan. En cas
  de refus, le storyboard recommence (2 essais automatiques), puis le plan passe
  quand même à Michael avec la remarque.
- **Porte : Michael valide le visuel** ou écrit ce qu'il veut changer.

### Étape 4 : Visuel HD

- **Automatique** : le visuel validé est agrandi par un outil fidèle (Topaz haute
  fidélité, retouche des visages coupée, 0,08 $ ; second essai avec SeedVR).
- **controleur** compare la HD au visuel validé : visage, regard, peau, cheveux,
  tenue, décor doivent être identiques.
- **Porte, seulement en cas d'écart** : Michael compare au curseur et choisit
  « Valider la HD », « Partir du visuel draft » ou « Demander une modif ».

### Étape 5 : Plan vidéo

- **routeur** choisit le fournisseur et le modèle (voir section 5) et donne sa
  raison en une phrase.
- **prompteur** écrit le prompt vidéo en suivant le guide du modèle choisi.
- **Porte : Michael valide le plan vidéo.** Il voit l'image de départ, le modèle,
  la raison, le coût estimé (vidéo draft, vidéo HD, lip-sync) et le prompt. Il peut
  changer de modèle ou retoucher le prompt. **Rien n'est dépensé avant.**

### Étape 6 : Vidéo draft

- **Automatique** : le worker lance la vidéo dès la validation du plan vidéo.
- **controleur** regarde trois images extraites (anatomie, visage qui se
  déforme, artefacts). Un essai automatique en cas de refus.
- **Porte : Michael valide la vidéo draft** (« Lire dans le morceau » la joue
  calée sur la musique).

### Étape 7 : Vidéo HD et lip-sync

- **Automatique** : agrandissement de la vidéo draft validée (donc identique à ce
  qui a été validé), ou rendu final direct pour les modèles sans basse résolution.
  Puis lip-sync sur la voix isolée pour les plans chantés.
- **Porte : Michael valide le final.**

### Étape 8 : Montage

- « Monter le clip » assemble la meilleure version disponible de chaque plan sur
  le morceau, à tout moment. Dès les visuels, cela donne une animatique.

## 4. Les retours de Michael

Michael écrit simplement ce qu'il veut. L'orchestrateur choisit la route :

| Route | Quand | Le plan repart en |
|---|---|---|
| `storyboard` | Le visuel ne va pas : composition, décor, tenue, visage, lumière | Visuel draft |
| `hd` | Seule la HD a perdu ou changé quelque chose | Visuel HD |
| `prompteur` | Le mouvement, l'action ou la caméra ne vont pas | Plan vidéo (revalidé par Michael) |
| `routeur` | Rendu technique insuffisant (mains, morphing, flou), ou modèle contesté | Plan vidéo, palier supérieur (revalidé) |
| `finition` | Seule la vidéo HD ou le lip-sync pose problème | Vidéo HD |
| `script` | Le plan lui-même change (idée, durée) | Visuel draft |

Le commentaire de Michael est recopié dans les notes du plan. Tous les agents le
lisent en priorité.

## 5. Le choix du fournisseur et du modèle

**Règle : le modèle le moins cher qui est adapté au besoin du plan.**

1. Le besoin vient du plan : mouvement (fixe, faible, moyen, fort), cadrage,
   nombre de personnages. Les règles de `config/models.yaml` en déduisent un
   palier : `eco` (plans calmes, gros plans, objets), `standard` (marche, gestes,
   cheveux et tissus en mouvement), `premium` (danse, chorégraphie, plans larges
   animés, plusieurs personnages).
2. Chaque modèle déclare les paliers qu'il sait tenir. Parmi les modèles des
   fournisseurs branchés qui tiennent le palier, on prend le moins cher pour la
   durée du plan.
3. Le routeur peut s'écarter de cette règle s'il a une raison (retour de Michael
   sur un plan semblable, défaut connu d'un modèle). Il l'écrit.
4. Michael voit tous les modèles avec leur coût pour ce plan et peut en choisir
   un autre avant de valider.

Les offres des revendeurs et des modèles non éprouvés sont marquées « à
tester » : jamais choisies automatiquement, mais proposées à Michael dans le plan
vidéo. On retire la marque une fois la qualité vérifiée.

**Période de rodage.** Les prix et les forces des modèles bougent vite. Pendant
le rodage, on regarde au cas par cas. Le carnet de rodage (`riot rodage`) tire de
l'historique, pour chaque modèle : combien de vidéos draft validées du premier
coup, combien refaites, pour quels types de plans, avec les commentaires de
Michael. Le routeur le consulte avant de choisir. Les leçons durables sont
reportées dans la section 8 de ce document et dans `config/models.yaml`
(paliers tenus, guide de prompt).

Les fournisseurs, leurs clés et leurs modèles sont décrits dans
[FOURNISSEURS.md](FOURNISSEURS.md).

## 6. Le budget

- Chaque clip a un budget de génération (80 $ par défaut), modifiable dans
  l'onglet Dossier.
- Avant chaque génération, la machine vérifie que le coût estimé ne fait pas
  dépasser le budget. Sinon elle s'arrête et prévient Michael.
- Une alerte part à 80 % du budget.
- Les validations du plan vidéo affichent le coût avant toute dépense vidéo.

## 7. Les personnages

1. **Brouillon de la canon** : Michael dépose l'image qu'il a faite.
2. **Canon HD** : générée automatiquement par agrandissement fidèle. Michael la
   compare au brouillon au curseur. Il la valide, la fait refaire (avec l'autre
   outil), ou garde le brouillon tel quel.
3. **Instructions et pack** : Michael écrit ce qu'il veut (angles, plans en
   pied, expressions, lumières, tenues, détails) et lance le pack. Le
   directeur-casting génère les images à partir de la canon validée.
4. **Tri et validation** : Michael garde ou rejette chaque image (avec un
   commentaire si besoin), relance le pack si nécessaire, puis valide la version.

Une version validée est figée : les clips qui l'utilisent en dépendent. Pour
faire évoluer un personnage, on crée une nouvelle version.

## 8. Ce qu'on a appris

Section à enrichir au fil des clips : une ligne par leçon, avec sa date.

- 22/10/2026 : l'agrandissement d'image avec retouche des visages change
  l'identité du personnage. On le désactive toujours.
- 22/10/2026 : les vidéos sont générées sans son, la musique vient de Suno. Ça
  évite de payer 50 à 100 % de plus. Quand un modèle impose le son, la piste est
  retirée après téléchargement.
- 22/10/2026 : pour un même modèle, le prix va souvent du simple au double selon
  le fournisseur. On compare des offres (modèle + fournisseur), pas des modèles.
- 22/10/2026 : Google a fermé Veo 3.1 sur l'API Gemini. Veo passe par Vertex AI,
  seule voie payable par les crédits de l'essai Google Cloud.
- 23/10/2026 : Kling 3 Standard chez fal.ai sort en 720p. Une sortie en dessous de
  1080p doit être agrandie : son coût entre dans la comparaison.
- 23/10/2026 : le lip-sync Kling (0,014 $/s) remplace Sync Lipsync (0,08 $/s) sur
  les plans de 2 à 10 s.
- 29/10/2026 : Veo (Vertex) refuse la canon v1 de JJ (code 15236754, « personnalité
  connue »), même réduite dans un plan large. Les trois vues de sa planche
  turnaround (face, trois quarts, profil) passent, et l'identité tient. Le
  filtre vise une image précise, pas JJ : une image refusée se remplace par une
  autre de la même version. Un refus à l'entrée ne produit rien.
- 29/10/2026 : un test de fournisseur se fait au plus court et en plus basse
  résolution (2 s, ~420p), ou au plancher du modèle (Veo : 4 s, 720p).

## 9. Où vivent les choses

| Quoi | Où |
|---|---|
| Ce process | `docs/PROCESS.md` |
| Fournisseurs et modèles | `docs/FOURNISSEURS.md`, `config/models.yaml` |
| Règles de l'orchestrateur | `CLAUDE.md` |
| Consignes de chaque agent | `.claude/agents/*.md` |
| Passages automatiques | `.claude/skills/prod/` (clips), `.claude/skills/casting/` (personnages) |
| Dossier d'un clip | `studio/clips/<clip>/` : `song/`, `dossier/`, `script/`, `storyboard/`, `drafts/`, `finals/`, `montage/` |
| Personnages | `studio/characters/<slug>/v<N>/` |
| Base (statuts, validations, coûts) | `studio/riot.db` |
| Journaux des agents | `studio/logs/` |
