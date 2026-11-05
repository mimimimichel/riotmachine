# Changelog

Une ligne par exigence livrée (`docs/REQUIREMENTS.md`), la plus récente en haut.
Format : date, identifiant, ce qui change pour Michael.

## Lot 1 : Fondations

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
