# Riot Machine — Exigences

Version 1.1 — 4 novembre 2026. Complète `VISION.md`.

Chaque exigence a un identifiant (`R-xx`), une priorité et un critère
d'acceptation testable. Les commits et les tests référencent l'identifiant.

| Priorité | Sens |
|---|---|
| **P0** | Nécessaire au clip zéro. Se livre en premier, dans l'ordre du plan de livraison. |
| **P1** | Nécessaire au premier clip complet (60 plans, mode final). |
| **P2** | Confort, après le premier clip. |

Format d'une exigence : énoncé, raison, critère d'acceptation. Quand une
exigence modifie le schéma de la base, elle le dit.

---

## A. Données : un objet, une baseline, un historique

### R-A1 [P0] Un plan est un objet unique
**Énoncé.** Le découpage et la production lisent et écrivent les mêmes lignes
(`blocks`, `shots`). Aucune vue ne tient de copie.
**Raison.** Aujourd'hui c'est déjà le cas en base, mais pas à l'écran : les
deux onglets montrent des champs différents.
**Critère.** Un champ modifié dans l'onglet Découpage apparaît dans le détail du
plan sans rechargement de la base, et réciproquement.

### R-A2 [P0] Identifiants stables
**Énoncé.** L'édition du découpage (régie ou `riot shots import`) met à jour les
plans existants et n'en supprime que ceux que Michael a retirés. Un plan garde
son `id`, son statut, ses notes, ses images, ses retours et son historique à
travers toutes les éditions.
**Raison.** `import_shots` met à jour par `id` depuis fin octobre, mais les
blocs sont appariés par position (l'`id` de bloc envoyé est ignoré), un champ
omis du découpage est effacé, et la validation du découpage entier remet tous
les plans du clip à `image_todo`, même ceux déjà avancés.
**Schéma.** Chaque plan du découpage porte son `id` quand il existe ; un plan
sans `id` est nouveau. Les blocs de même. Un plan retiré du découpage qui a
déjà des assets n'est pas supprimé : il reçoit `shots.deleted_at` (suppression
logique). Il sort de la timeline, des invariants et du montage ; ses assets et
son historique restent ; il est restaurable. Un plan sans asset est supprimé
réellement. En régie, retirer un plan qui a des assets demande confirmation en
affichant le montant dépensé.
**Critère.** Test : importer un découpage, générer une image sur le plan 3,
modifier la description du plan 2 et réimporter ; le plan 3 a le même `id`, son
image et son statut. Retirer le plan 3 du découpage le marque `deleted_at` et
garde son image ; le restaurer le remet dans la timeline.

### R-A3 [P0] Baseline de Michael
**Énoncé.** Pour chaque champ créatif, le texte de Michael est stocké dans une
colonne dédiée que les agents n'ont pas le droit d'écrire :
`shots.script` (ses mots pour le plan), `blocks.brief` (son intention),
`character_versions.instructions` (déjà), `reviews.comment` (déjà). Les agents
écrivent dans `shots.description`, `blocks.intention`, etc.
**Raison.** Le script doctor réécrit `description`, seule colonne existante ;
les mots de Michael disparaissent.
**Schéma.** Ajout de `shots.script`, `blocks.brief`, `shots.prod_outdated`.
Migration : copier `description` dans `script` et `intention` dans `brief`
pour les lignes existantes.
**Règle.** `description` suit `script` tant qu'aucun agent ne l'a transformée.
Après transformation, une modification de `script` laisse `description` en
place, pose le marqueur `prod_outdated` (« production à mettre à jour »,
visible en régie) et renvoie le plan au script-doctor. Le script-doctor
complète, il ne reformule pas : `description` = les mots de Michael + ses
compléments.
**Critère.** Test : après passage du script-doctor, `shots.script` est
identique au texte saisi ; un import d'agent qui envoie `script` ou `brief`
est refusé. La CLI refuse `riot shot set --script` depuis un agent
(permission `.claude/settings.json`) ; la régie l'autorise.

### R-A4 [P0] Historique des changements
**Énoncé.** Toute modification d'un champ de `clips`, `blocks`, `shots`,
`characters`, `character_versions`, `elements` est journalisée dans une table
`changes` : objet, champ, valeur avant, valeur après, auteur (`michael`,
`agent:<nom>`, `worker`), raison (libre), horodatage.
**Raison.** Michael veut voir ce qu'il a demandé et ce qui a été transformé,
sans perte en ligne.
**Schéma.** Table `changes`. Les écritures passent par une fonction unique
(`db.update(...)`) qui journalise ; pas d'`UPDATE` direct ailleurs (un test
lit le code source et le vérifie). Auteur : `michael` depuis la régie,
`worker` depuis le worker ; depuis la CLI, l'agent est déduit de la commande
(`shots import` → script-doctor, `gen image` → storyboard, `qc` → controleur,
`route` → routeur, `shot set --video-prompt` → prompteur, sinon
`agent:orchestrateur`), ou forcé par la variable `RIOT_ACTOR`.
**Critère.** `riot history shot <id>` et l'onglet « Historique » du détail d'un
plan listent les changements dans l'ordre. Test : trois modifications
successives donnent trois lignes avec avant/après corrects.

### R-A5 [P1] Retours conservés tels quels
**Énoncé.** Un retour de Michael (`reviews`) garde son texte, sa route, la note
de l'orchestrateur et le résultat (quel asset a été produit en réponse). Il
n'est plus recopié dans `shots.notes` ; le détail du plan affiche la liste des
retours et leur traitement.
**Critère.** Test : un retour traité est lié à l'asset produit ensuite ;
`shots.notes` ne contient plus de « Retour de Michael : ».

### R-A6 [P1] Versions d'assets jamais écrasées
**Énoncé.** Refaire un visuel ou une vidéo crée une nouvelle version de
l'asset ; l'ancienne reste consultable et comparable (déjà en partie le cas via
`assets.version`, à garantir pour tous les types, HD comprise).
**Critère.** Test : deux générations d'image sur le même plan donnent
`version` 1 et 2, toutes deux en base et sur disque.

---

## B. Découpage et plans : cycle de vie, navigation, changements

### R-B1 [P0] Validation par bloc
**Énoncé.** Le découpage se valide bloc par bloc. Un bloc validé entre en
production ; les autres restent éditables. Le statut de clip
`decoupage_review` devient un statut de bloc (`blocks.status` :
`draft`, `review`, `validated`).
**Raison.** Le clip zéro est un seul bloc ; et sur un clip complet, Michael
peut lancer le refrain pendant qu'il écrit le couplet 2.
**Schéma.** `blocks.status`, `blocks.validated_at`.
**Critère.** Test : clip à 2 blocs, bloc 1 validé → ses plans sont en
`image_todo`, ceux du bloc 2 restent sans statut de production et éditables.

### R-B2 [P1] Opérations de révision d'un bloc validé
**Énoncé.** Sur un bloc validé, cinq opérations sont possibles, par Michael dans
la régie et par les agents en CLI : `riot shot retime <id> --start --end`,
`riot shot split <id> --at <t>`, `riot shot merge <id> <id2>`,
`riot shot insert --after <id> --end <t> --script "…"`,
`riot shot delete <id>`. Chacune est une révision journalisée (R-A4) et
applique la table d'impact (R-B4). Les plans sont renumérotés sans changer d'`id`.
**Raison.** Aujourd'hui, après validation, on ne peut ni couper ni fusionner ni
insérer ; un agent à qui l'on demande de modifier une partie du clip ne peut
pas le faire proprement.
**Critère.** Test pour chaque opération : invariants (R-B3) respectés après
coup, `id` des plans non touchés inchangés, historique écrit.

### R-B3 [P0] Invariants temporels
**Énoncé.** À chaque écriture de plan : pas de trou ni de chevauchement dans un
bloc, `0 ≤ t_start < t_end ≤ durée du morceau`, durée d'un plan ≤ durée
maximale du modèle choisi s'il y en a un. Une violation est refusée avec un
message en français qui nomme le plan et le problème. Au montage, une vidéo
plus longue que son plan est rognée ; plus courte, le plan est signalé
(`assemble` liste les écarts).
**Critère.** Tests : chevauchement refusé, trou refusé, plan au-delà du
morceau refusé ; montage avec une vidéo de 5 s sur un plan de 4,5 s réussit ;
avec une vidéo de 4 s sur un plan de 5 s, l'écart est listé.

### R-B4 [P1] Table d'impact d'une révision
**Énoncé.** Une modification d'un plan validé n'invalide que ce qu'elle rend
faux. La table fait foi ; la machine remet le plan à l'étape indiquée et
conserve les assets encore valables.

| Changement | Conservé | À refaire | Nouveau statut |
|---|---|---|---|
| `script` / `description` | rien (anciennes versions gardées, R-A6) | visuel, vidéo | `image_todo` |
| timecodes, écart ≤ 0,5 s | tout | rien (rognage au montage) | inchangé |
| timecodes, écart > 0,5 s | visuel, HD | vidéo, lip-sync | `prompt_todo` si vidéo existait, sinon inchangé |
| `framing` / `motion` / `camera` | visuel si `framing` inchangé | prompt vidéo, vidéo | `prompt_todo` |
| `characters` / look / décor | rien | tout | `image_todo` |
| `singing` | visuel, vidéo | lip-sync | `lipsync_todo` ou `done` |

**Critère.** Un test par ligne de la table.

### R-B5 [P0] Navigation et contexte complet
**Énoncé.** Depuis un plan de l'onglet Découpage, un clic ouvre son détail de
production ; depuis le détail, un clic revient au plan dans le découpage. Le
détail d'un plan affiche : bloc et son brief, `script` (baseline),
`description` (production), remarques du script-doctor pour ce plan, retours,
références de personnage et de décor qui seront envoyées, historique.
**Raison.** Michael retourne sans cesse dans le découpage pour retrouver une
information absente du détail.
**Critère.** Revue manuelle sur le clip démo ; test de la régie : la réponse de
`/api/shots/<id>` contient `block`, `script`, `description`, `script_notes`,
`reviews`, `references`, `history`.

### R-B6 [P1] Remarques du script-doctor par plan
**Énoncé.** Le script-doctor écrit ses remarques par plan (`shots.agent_notes`)
et par bloc, en plus de `script/notes.md`.
**Critère.** Test : après passage simulé, chaque plan complété a une
`agent_notes` non vide quand l'agent en a une.

---

## C. Modes de production et sauts d'étapes

### R-C1 [P0] Trois modes
**Énoncé.** Un clip a un mode par défaut, surchargeable par bloc et par plan :

| Mode | Visuel | Contrôle image | HD | Vidéo | Contrôle vidéo | Upscale | Lip-sync | Validation vidéo par Michael |
|---|---|---|---|---|---|---|---|---|
| `brouillon` | 1 image, résolution basse, modèle le moins cher | non | sauté | palier eco, plus basse résolution, durée plancher | non | sauté | sauté | automatique sous seuil (R-D2) |
| `standard` | selon routage | oui | oui | selon routage | oui | oui | plans chantés | oui |
| `final` | selon routage | oui | oui | selon routage, palier ≥ standard | oui | oui | plans chantés | oui |

Le mode d'un nouveau clip est `brouillon`.
**Raison.** Roder la machine et faire une V0 ne doit pas coûter 100 $.
**Schéma.** `clips.mode`, `blocks.mode` (nullable), `shots.mode` (nullable).
`config/models.yaml` déclare pour chaque mode les étapes actives et la
résolution demandée.
**Critère.** Test : un clip simulé de 10 plans en `brouillon` passe de
`image_todo` à `done` sans jamais passer par `hd_*`, `lipsync_*` ni
`*_qc`, et son coût estimé est inférieur au plafond du mode (R-C4).

### R-C2 [P0] Sauter une étape
**Énoncé.** Michael peut sauter n'importe quelle étape d'un plan ou d'un bloc
(HD, contrôle, upscale, lip-sync, validation vidéo) depuis la régie ou
`riot shot skip <id> <étape> --why`. L'étape passe en `skipped` avec la raison,
le plan continue. Un plan qui a sauté une étape le signale dans la régie.
**Critère.** Test : `skip hd` sur un plan en `hd_todo` le fait passer à
`prompt_todo` et journalise.

### R-C3 [P1] Promotion de mode
**Énoncé.** Passer un plan, un bloc ou un clip de `brouillon` à `standard` ou
`final` ne refait que les étapes manquantes ou sautées, en réutilisant ce qui
est validé (un visuel validé en brouillon reste la base de la HD).
**Critère.** Test : plan `done` en brouillon, promu en `final` → statut
`hd_todo`, visuel conservé, vidéo brouillon conservée comme référence.

### R-C4 [P0] Plafond et estimation par mode
**Énoncé.** Avant tout lancement de lot, la régie affiche le coût estimé du lot
et le cumul du clip ; chaque mode a un plafond par plan dans
`config/models.yaml` (brouillon : 0,30 $ par plan tout compris, valeur
initiale). Un lot qui dépasserait le plafond ou le budget du clip ne part pas.
**Critère.** Test : clip en brouillon de 60 plans, estimation ≤ 18 $ ; un lot
à 0,50 $ par plan en brouillon est refusé.

---

## D. Travail par lot et automatisation

### R-D1 [P0] Accord de dépense par lot
**Énoncé.** L'accord de dépense se donne pour un lot (les plans d'un bloc à une
étape : « 12 visuels du refrain, ~1,00 $ »), pas par image. Les générations
du lot partent sans autre accord jusqu'au montant accordé. Les demandes
`pending` unitaires actuelles sont regroupées en lots dans la régie.
**Raison.** Depuis le 29/10, chaque image attend un accord : la machine ne
dépense plus rien.
**Schéma.** Table `batches` (clip, bloc, étape, plans, montant accordé, montant
dépensé, statut).
**Critère.** Test : accorder un lot de 5 images → les 5 générations partent ;
la 6e, hors lot, reste `pending`.

### R-D2 [P1] Auto-validation sous seuil
**Énoncé.** Par mode, des règles d'auto-validation configurables : en
`brouillon`, le plan vidéo est accepté sans Michael si palier `eco` et coût ≤
seuil ; le contrôleur peut valider seul un visuel dont le score d'identité
dépasse un seuil. Les seuils sont dans `config/models.yaml` et modifiables
dans la régie.
**Critère.** Test : en brouillon, un plan en `video_review` sous seuil passe
en `draft_todo` sans décision ; au-dessus, il attend.

### R-D3 [P0] Validation en grille
**Énoncé.** Les visuels (et les vidéos draft) d'un lot se valident sur une seule
page : vignettes, pour chaque plan « garder / refaire / commenter », et
« tout garder ». Une seule requête enregistre toutes les décisions.
**Critère.** Test de la régie : `POST /api/batches/<id>/decide` avec 8
décisions met à jour les 8 plans en une transaction.

### R-D4 [P0] Enchaînement automatique
**Énoncé.** La validation d'un bloc (R-B1) crée le lot de visuels du bloc et
le soumet à l'accord (R-D1) ; l'accord lance les générations ; chaque étape
automatique s'enchaîne sans passage manuel de `/prod`. Le worker réveille
l'orchestrateur dès qu'un plan attend un agent, au plus 60 s après.
**Critère.** Test du worker en simulation : bloc validé + lot accordé → tous
les plans atteignent `image_review` sans autre appel.

### R-D5 [P1] Notifications par lot
**Énoncé.** Un message Telegram par lot prêt (« Refrain : 12 visuels à trier »),
avec le lien vers la grille. Jamais un message par plan.
**Critère.** Test : 12 plans passant en `image_review` dans la même minute
produisent une seule notification.

### R-D6 [P2] File d'attente visible
**Énoncé.** La régie montre ce qui tourne chez les fournisseurs, depuis quand,
et ce qui est en file.

---

## E. Cohérence des personnages et des décors

### R-E1 [P0] Références embarquées et tracées
**Énoncé.** Toute génération d'image ou de vidéo d'un plan embarque la canon de
la version castée, l'ADN (Toujours / Jamais) dans le prompt, le look du clip
et la référence du décor. `riot shot show` liste exactement les références qui
partiront ; le log de génération (`assets.params`) les conserve. Avec
plusieurs personnages, chacun garde au moins sa canon (aujourd'hui la canon du
second peut être tronquée).
**Critère.** Test : `assets.params` d'une image générée contient les chemins de
la canon et du décor, et le prompt contient la section Toujours de l'ADN ; avec
deux personnages castés, les deux canons sont dans les références envoyées.

### R-E2 [P1] Contrôle d'identité mesuré
**Énoncé.** Le contrôleur compare chaque visuel et chaque vidéo à la canon et
produit un score (0–100) et un verdict, stockés sur l'asset. Deux refus
d'identité sur le même plan font remonter à Michael une suggestion : changer
de référence (autre vue du pack) ou de modèle.
**Critère.** Test : deux `qc fail` identité → notification avec suggestion ;
`assets.qc_score` renseigné.

### R-E3 [P0] Clip épinglé à une version et un look
**Énoncé.** (Existant, à garantir par test.) Un clip épingle la version et le
look de chaque personnage ; valider une nouvelle version de JJ ne change pas
les références d'un clip en cours.
**Critère.** Test : créer et valider v3 pendant qu'un clip est casté en v2 ;
`riot shot show` du clip donne toujours la canon v2.

### R-E4 [P1] Mémoire de ce qui marche
**Énoncé.** Les essais réussis (modèle, référence utilisée, prompt) se rangent
par version de personnage (existant : `essais/`). Le routeur et le prompteur
les consultent : `riot character show` et `riot rodage` les exposent par
personnage.
**Critère.** Test : un essai enregistré apparaît dans `riot rodage --character jj`.

### R-E5 [P1] Supprimer une tenue
**Énoncé.** Michael supprime une tenue depuis la page du personnage ou l'onglet
Références, après confirmation. Elle sort des castings et des plans qui la
portaient (changement journalisé). Le texte des plans n'est pas réécrit : la
régie dit dans quels plans le @ reste écrit. Les photos et feuilles ne sont pas
détruites, elles partent dans `looks/.supprimees/`.
**Critère.** Test : supprimer `@jj-bureau` portée par un plan et castée → la
tenue disparaît, le plan ne la porte plus (ligne dans `changes`), le casting
n'a plus de look, le dossier est dans `.supprimees/`.

---

## F. Clarté : qui fait quoi, où en est-on

### R-F1 [P0] Un responsable par état
**Énoncé.** Chaque statut de plan a un responsable unique (Michael, un agent
nommé, le worker, le fournisseur). La régie l'affiche sur chaque plan
(« En attente de : storyboard ») et dans la timeline.
**Critère.** Table `STATUS_OWNER` dans `db.py`, couvrant tous les statuts
(test : aucun statut sans responsable) ; `/api/shots/<id>` renvoie `owner`.

### R-F2 [P1] Tableau de bord du clip
**Énoncé.** En tête du clip : par bloc, nombre de plans par état, ce qui attend
Michael, ce qui tourne, coût engagé et estimé jusqu'au bout, mode.
**Critère.** `/api/clips/<slug>/dashboard` renvoie ces chiffres ; test sur le
clip démo.

### R-F3 [P2] Journal lisible
**Énoncé.** `riot events` et l'onglet Journal présentent les événements en
français, groupés par lot, filtrables par plan.

---

## G. Qualité logicielle et méthode

### R-G1 [P0] Le document fait foi
**Énoncé.** Toute fonctionnalité correspond à une exigence de ce document.
Les messages de commit citent les identifiants (`R-A2, R-A3`). Une exigence
nouvelle s'écrit ici avant de se coder.

### R-G2 [P0] Tests et non-régression
**Énoncé.** Chaque exigence P0 et P1 a au moins un test automatique nommé par
son identifiant (`test_r_a2_identifiants_stables`). Deux scénarios de bout en
bout en simulation servent de non-régression : un clip en `brouillon`, un clip
en `final` avec révisions. `pytest` doit être vert avant tout commit (hook
`pre-commit`). Un test cassé par une évolution se corrige dans le même commit.
Les deux scénarios de bout en bout dépendent des modes (lot 2) et des
révisions (lot 4) : ils se livrent avec ces lots.
**Critère.** Hook en place ; `pytest -k r_` liste une entrée par exigence P0/P1 livrée.

### R-G3 [P0] Migrations de schéma
**Énoncé.** Le schéma est versionné (table `schema_version` et
`PRAGMA user_version`), les migrations sont numérotées et idempotentes, une
sauvegarde de `riot.db` est faite dans `studio/backups/` avant chaque
migration. Aucune migration ne supprime de données de Michael. `riot db status`
montre la version, les migrations appliquées et les sauvegardes.
**Critère.** Test : base au schéma courant → migrations appliquées deux fois
sans erreur ; sauvegarde présente.

### R-G4 [P0] Gel fonctionnel
**Énoncé.** Jusqu'à la livraison du clip zéro, seules les exigences P0 se
développent, dans l'ordre du plan de livraison. Toute autre idée s'ajoute ici
en P1 ou P2.

### R-G5 [P0] Méthode de travail dans Claude Code
**Énoncé.** Claude Code travaille lot par lot (voir plan de livraison), en mode
plan avant chaque lot : il lit `VISION.md` et ce document, propose le plan du
lot, attend l'accord, puis livre exigence par exigence (test d'abord, code,
changelog, mise à jour de `PROCESS.md` et des consignes d'agents si le process
change). Un lot se termine par `pytest` vert et un résumé de ce qui a changé
pour Michael.

---

## Plan de livraison

| Lot | Exigences | Ce que Michael obtient |
|---|---|---|
| **1. Fondations** | R-G3, R-G2 (hook + squelette), R-A2, R-A3, R-A4, R-F1 | Plus de perte de données ; sa baseline conservée ; historique ; « en attente de » |
| **2. Modes et lots** | R-C1, R-C2, R-C4, R-D1, R-D4 | Un clip en brouillon pour quelques dollars, qui avance seul entre deux accords |
| **3. Régie du clip zéro** | R-B1, R-B3, R-B5, R-D3, R-E1, R-E3 | Validation par bloc, grille de tri, détail complet, références garanties |
| → **Clip zéro** | — | Le refrain de JJ, 8 à 10 plans, < 10 $ ; liste des irritants |
| **4. Révisions** | R-B2, R-B4, R-B6, R-A5, R-A6 | Modifier un bloc validé sans rien casser |
| **5. Automatisation** | R-D2, R-D5, R-C3, R-E2, R-E4, R-F2 | Moins d'interventions, promotion brouillon → final |
| **6. Confort** | R-D6, R-F3 | — |

## Changelog du document

- 1.2 (05/11/2026) : R-E5, suppression d'une tenue, à la demande de Michael.
- 1.1 (04/11/2026) : après audit du code et décisions de Michael pour le lot 1.
  R-A2 : raison mise à jour (l'import met déjà à jour par `id`), suppression
  logique `deleted_at`. R-A3 : règle script / description et marqueur
  `prod_outdated`. R-A4 : auteur des changements. R-E1 : canons tronquées à
  plusieurs personnages. R-G2 : scénarios de bout en bout livrés avec les lots
  2 et 4. R-G3 : `studio/backups/` et `riot db status`.
- 1.0 (04/11/2026) : première version, issue de l'analyse du code au 30/10 et
  des constats de Michael.
