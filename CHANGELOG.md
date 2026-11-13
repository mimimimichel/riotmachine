# Changelog

Une ligne par exigence livrée, la plus récente en haut. Format : date,
identifiant, ce qui change pour Michael. Référence : `docs/SPEC-v3.md` (3.1).

## v3 — Lot 1 : Fondations

- 2026-11-13 R-T10 : les agents n'ont plus aucun outil pour écrire un fichier. Leurs permissions (`config/agents-permissions.json`) leur interdisent la base, la configuration et `.env` : ils n'agissent que par la CLI `riot`.
- 2026-11-13 R-T6 : chaque action est une révision qui s'applique entièrement ou pas du tout, et qui s'annule d'un geste (refusé, avec le motif, si un champ a changé depuis). Tout appel extérieur a un délai et un nombre d'essais bornés ; une demande de génération n'est jamais renvoyée automatiquement.
- 2026-11-13 R-T5 : chaque génération a une clé unique. Elle est enregistrée avant l'envoi au fournisseur. Un double clic ne crée rien de plus. Un arrêt du worker ne la renvoie jamais : au redémarrage, elle est retrouvée chez le fournisseur ou passe « à vérifier », avec un message qui dit quoi faire.
- 2026-11-13 R-A6 : chaque génération et chaque fichier sont une nouvelle version, jamais écrasée (`<nom>-v001`, `-v002`…). Retirer un plan qui a des prises le met de côté, restaurable.
- 2026-11-13 R-A4 : toute modification passe par une seule fonction qui journalise objet, champ, avant, après, auteur, raison et date. `riot history plan <id>` liste l'historique. La CLI refuse l'auteur « michael » : tes écritures viendront de la régie.
- 2026-11-13 R-A3 : tes mots (mots d'un plan, intention d'un bloc, brief, retours) sont dans des champs que ni un agent ni le code ne peuvent écrire ; les agents écrivent la version de production à côté.
- 2026-11-13 R-A2 : réimporter un découpage garde l'identifiant, les retours et l'historique de chaque plan ; un plan absent est retiré, pas supprimé. (Critère sur les prises : lot 2.)
- 2026-11-13 R-A1 : un plan est une seule ligne ; le découpage et la page du plan lisent la même.
- 2026-11-13 R-G2 : crochet de pré-commit v3 (tests verts obligatoires, sans porte de sortie) ; chaque exigence de cette section a son test `test_r_<id>_`.
- 2026-11-13 R-G3 : migrations numérotées (`riotmachine/migrations/`), rejouables, copie de la base avant migration, aucune suppression. Migration de la base v1 vers `studio/riot-v3.db`, table par table, avec essai à blanc et rapport (`riot migrer-v1 --essai`) ; la base v1 n'est jamais modifiée.

## v1 (archive, exigences de `docs/archive/REQUIREMENTS.md`)


## Lot 1 : Fondations

- 2026-11-11 R-B8 (correctif) : après « Écarter » avec une raison, l'écran du plan ne se mettait pas à jour : la case de la raison restait ouverte et bloquait le rafraîchissement. Les boutons Valider et Refuser restaient affichés alors que l'écart était enregistré. Toute action lancée depuis le détail d'un plan redessine maintenant l'écran.
- 2026-11-11 Références : « Utiliser telle quelle » sur une image déposée (inspiration ou brouillon) d'un décor, objet ou figurant. L'image sert directement de référence aux plans, sans brouillon ni image HD à générer. La fiche passe à « Prêt », avec sa vignette.
- 2026-11-11 R-B5 : créer un objet, un décor, un figurant ou une tenue (onglet Références) mène directement à sa fiche, ouverte. Le bouton de retour ramène là où l'on était : au plan si on venait d'un plan, sinon au formulaire d'ajout.
- 2026-11-11 R-F7 : lancer une vidéo draft se fait d'un seul bouton « Lancer la vidéo draft · ~coût ». Avant : « Passer au lancement », « Confirmer ? », puis « Lancer ». Le prompt se relit et se corrige dès que le plan vidéo est prêt. Les boutons qui portent leur coût (générer les propositions, lancer le visuel HD) ne demandent plus « Confirmer ? ».
- 2026-11-07 Dépenses : la page repère un fournisseur gratuit dont la limite du jour est atteinte (échec « quota » depuis minuit UTC sans réussite après, `production.quota_out`), l'annonce en tête et sur chaque ligne touchée (« Lancer quand même » à la place de « Lancer »), et propose de passer la demande sur un autre modèle gratuit (`POST /api/spend/<id>/model`, gratuit seulement). Une demande gratuite s'affiche « gratuit » et non plus « payé en argent », avec le nom du modèle au lieu de sa clé.
- 2026-11-07 R-F7 (correctif) : la boîte « Échec » d'un visuel passe en tête de la carte et écrit la raison elle-même (avant : « la remarque au-dessus », loin au-dessus). Pour un quota gratuit épuisé, elle précise que tous les modèles du fournisseur sont touchés et nomme le modèle à prendre.
- 2026-11-07 R-F8 (correctif) : la croix d'une référence enregistre tout de suite. Avant, rien n'était enregistré, l'alerte « @ introuvable » restait et la référence revenait au rechargement. Dans un bloc validé, elle passe par le prompt détaillé du plan.
- 2026-11-07 R-B8 : « Écarter » une proposition (visuel, HD, vidéo) ouvre une case « ce qui ne va pas et ce que tu veux à la place ». La raison s'ajoute aux remarques du plan et, quand c'était la dernière proposition, part avec la relance chez l'agent de l'étape.
- 2026-11-07 R-F8 : un @ affiché dans un texte n'est plus un lien (toucher le texte n'emmène plus ailleurs). Les puces de références sous le texte s'ouvrent au toucher et ont une croix qui retire le @ (le nom reste écrit). Dans le détail d'un plan, les puces suivent la frappe du prompt détaillé.
- 2026-11-07 Découpage : un seul bouton par bloc, « Valider et lancer ce bloc », dans la tête du bloc (grisé avec le nombre de plans restant à valider). Le bouton du corps du bloc et l'encadré du bas, qui faisaient la même chose, sont retirés.
- 2026-11-06 R-F7 (correctif) : « Demander une modif au storyboardeur » reste dans la section Visuel quand toutes les propositions sont écartées ou que l'essai a échoué, avec les propositions écartées à revoir dans un repli.
- 2026-11-06 R-F7 (correctif) : « Valider la vidéo draft » plantait (« Cannot read properties of undefined (reading 'trim') ») car le prompt, affiché en lecture seule à cette étape, était lu comme un champ. La validation ne le lit plus que s'il est modifiable.
- 2026-11-06 R-F7 : le détail d'un plan devient un parcours guidé. La frise en tête (Visuel :
  draft, HD ; Vidéo : draft, HD, lip-sync) mène à chaque étape ; trois sections, Le plan, Visuel,
  Vidéo ; chaque étape est une carte (faite, en cours, à venir). Le prompt du visuel se relit avant
  le lancement ; les modèles se choisissent dans un sélecteur replié ; les boutons nomment la vidéo
  concernée. Refuser une vidéo draft propose d'abord de corriger le visuel. Le visuel HD contrôlé
  attend désormais toujours la validation de Michael.
- 2026-11-06 R-F6 : un bouton « À faire » en haut à droite de chaque page ouvre la liste par-dessus
  la page, avec une pastille du nombre de choses à faire ; au retour d'une action, la liste se rouvre.
- 2026-11-06 R-F5 : la liste « À faire » suit l'ordre des blocs. Tout ce qui reste sur un bloc
  passe avant la validation du découpage du bloc suivant ; chaque ligne nomme son bloc.
- 2026-11-06 correctif régie : dans le détail d'un plan, la page derrière ne défile plus quand le
  tiroir arrive en bas, et une marge en bas laisse la fin visible au-dessus du bouton « Retour ».
- 2026-11-06 R-B8 : chaque proposition d'un plan s'écarte (bouton « Écarter » sous chaque
  visuel proposé, « Écarter cette version » sous la HD et les vidéos). Plus aucune
  proposition : le visuel repart chez le storyboard, les autres étapes chez l'orchestrateur.
- 2026-11-06 correctif régie : « Enregistrer » dans le découpage ne remonte plus en haut de
  la page, le plan où l'on a cliqué reste à sa place ; une action dans le détail d'un plan
  ne fait plus remonter la page du dessous.
- 2026-11-06 R-B7 : une étape déjà validée se corrige. Dans le plan, sur le visuel draft,
  le visuel HD ou le plan vidéo : « Demander une modif de ce visuel ». Le plan repart de
  là chez le bon agent, ce qui avait été fait après est mis de côté, la chaîne se rejoue.
- 2026-11-06 R-F4 : chaque ligne « À faire maintenant » ouvre l'endroit exact (le plan à
  valider, le bloc du découpage, l'image de décor ou de personnage à trier, le groupe de
  dépenses), mis en évidence. Après l'action (plan refermé, dépenses décidées), la régie
  ramène à la liste ; un bouton « Retour à la liste À faire » reste affiché entre-temps.
- 2026-11-06 correctif régie : dans le détail d'un plan, les blocs se chevauchaient sur
  téléphone ; le panneau est une simple colonne, vérifié sur les 65 plans. Les tests
  ignorent le jeton d'accès de la régie.
- 2026-11-05 R-E5 : une tenue se supprime (page du personnage ou onglet Références,
  avec confirmation). Elle sort des castings et des plans ; ses photos sont gardées
  dans `looks/.supprimees/`.
- 2026-11-05 correctifs régie après test complet sur téléphone : la vidéo draft
  s'affiche dans le plan (le lecteur tombait à 2 pixels de haut) ; les cartes de
  référence d'un plan ouvrent la fiche, avec retour au plan ; une génération échouée
  sans fichier ne s'affiche plus en image cassée ; la page Crew ne plante plus
  (en-têtes d'agents mal formés) ; les vidéos Vertex ne gonflent plus l'API de 3 Mo
  par plan ; message clair quand le GPU gratuit de Hugging Face refuse.
- 2026-11-05 R-B5 (suite) : l'onglet Références a un sous-menu Tout / Décors /
  Figurants / Objets / Tenues, collé en haut de l'écran ; venir d'un plan ouvre la bonne famille.
- 2026-11-05 correctif régie : « Copier le prompt » (image, vidéo, plan vidéo à valider)
  copie le texte même en HTTP ; avant, le navigateur refusait et l'appui long prenait
  l'image voisine. Un bouton Copier s'ajoute au prompt vidéo du plan à valider.
- 2026-11-04 R-B5 (début, avancé du lot 3 à la demande de Michael) : dans un plan, un @ ou
  une puce de référence ouvre la fiche de la référence (décor, objet, figurant, tenue,
  personnage) ; un bouton flottant « Retour au plan N » ramène au plan en cours
  d'édition, rouvert à sa place.
- 2026-11-04 R-F1 : chaque statut de plan a un responsable unique (`STATUS_OWNER`),
  affiché sur chaque plan et dans la timeline (« En attente de : toi / le storyboard /
  le fournisseur… », avec la raison) ; `/api/shots/<id>` renvoie `owner`.
- 2026-11-04 R-A3 : le texte de Michael (`script` d'un plan, `brief` d'un bloc) est
  stocké à part et aucun agent ne peut l'écrire (import refusé, `riot shot set
  --script` interdit). La version de production garde ses mots tels quels ; quand
  il change son texte après transformation, la production reste, se marque « à
  mettre à jour » et le script-doctor est rappelé. Le Découpage édite son texte et
  montre la version de production dessous.
- 2026-11-04 R-A2 : un plan et un bloc gardent leur id à travers toutes les éditions
  du découpage (blocs appariés par id, champ omis conservé). Un plan retiré qui a
  des images ou des vidéos est gardé avec elles, hors timeline, restaurable
  (« Plans retirés » en bas du Découpage, `riot shot restore`) ; la régie demande
  confirmation en affichant le montant dépensé. Valider le découpage entier ne
  remet plus les plans avancés à zéro.
- 2026-11-04 R-A4 : chaque changement d'un clip, bloc, plan, personnage, version ou
  élément est journalisé (avant, après, auteur, raison). `riot history …`,
  `GET /api/shots/<id>/history`, pli « Historique des changements » dans le détail
  d'un plan. Toutes les écritures passent par `db.update`.
- 2026-11-04 R-G2 : hook `pre-commit` (pytest vert avant tout commit, installé par
  `deploy/install-hooks.sh`), tests nommés par exigence dans
  `tests/test_requirements.py`, test qui vérifie que chaque exigence du changelog a
  le sien.
- 2026-11-04 R-G3 : schéma versionné (table `schema_version`), migrations numérotées
  et rejouables, sauvegarde automatique de `studio/riot.db` dans `studio/backups/`
  avant toute migration, `riot db status`.

## Avant le lot 1

- 2026-11-03 : état figé par le tag `avant-lot-1` (choix du modèle à chaque
  génération, style photo, feuilles de tenue, propositions multiples).
