# Riot Machine — Spécification

Version 3.0 — 12 novembre 2026. Remplace `REQUIREMENTS.md` (v1.x). À lire après
`VISION-v3.md`. Le détail de la fabrication des plans est dans
`PRODUCTION-PLANS-v3.md` (exigences R-H), qui fait partie de cette spécification.

## 0. Conventions

- Chaque exigence a un identifiant, une priorité et un critère testable. Les
  tests s'appellent `test_r_<id>_…`, les commits citent les identifiants.
- **P0** : nécessaire au clip zéro. **P1** : nécessaire au premier clip
  complet. **P2** : ensuite.
- Les identifiants des versions précédentes sont conservés quand l'exigence
  survit. Ceux qui disparaissent sont listés au §9.
- Tout texte destiné à Michael (régie, messages, erreurs) est en français, dit
  ce qui se passe et ce qu'il peut faire.

## 1. Le label et les artistes (R-L)

Objets : voir `VISION-v3.md` §4.

| Id | Pr. | Énoncé | Critère |
|---|---|---|---|
| R-L1 | P0 | Modèle de données à trois étages : label, artiste (ou groupe), clip. Chaque élément (décor, objet, figurant, look, plan de coupe, réserve) appartient à un étage. L'existant (`characters`, `elements`, `clips`) est migré dans ce modèle. | Un décor créé au niveau du label est visible depuis deux clips de deux artistes. |
| R-L2 | P0 | **Bible d'artiste** : identité (versions, canon, ADN Toujours / Jamais, pack, statut des images par fournisseur) et univers (palette, lumière, lieux, objets fétiches, gestuelle, façon de chanter, interdits). Versionnée ; un clip épingle la version qu'il utilise (reprend R-E3). | Valider une v3 de l'artiste ne change pas les références d'un clip épinglé en v2. |
| R-L3 | P0 | **Réutilisation au choix.** À la création d'un clip, seule l'identité de l'artiste est héritée. Michael choisit explicitement, dans la bibliothèque et la bible, ce que le clip reprend (décors, objets, looks, palette, plans de coupe). Le brief du clip prime sur la bible. | Un clip neuf n'envoie aucune référence de décor ou d'objet tant que Michael n'en a pas choisi. |
| R-L4 | P0 | **Brief de clip** : morceau, concept, références, choix de réutilisation, qualité (`brouillon` ou `final`), budget. Texte de Michael conservé en baseline. | Le brief est lisible depuis chaque écran du clip. |
| R-L5 | P1 | **Bibliothèque du label** : éléments versionnés, avec statut « référence » ou « inspiration seulement », statut par fournisseur, et la liste des clips qui les utilisent. Un élément créé dans un clip peut être versé à la bibliothèque. | Verser un décor d'un clip à la bibliothèque le rend sélectionnable ailleurs. |
| R-L6 | P1 | **Banque de plans B** par artiste : une prise gardée marquée « plan de coupe » devient réutilisable dans un autre clip, sans coût. | Une prise de la banque se place sur un plan d'un autre clip, coût 0. |
| R-L7 | P1 | **Déclinaisons** d'un clip : version verticale, teasers, boucle courte, vidéo paroles. Les plans portent une zone sûre pour le recadrage vertical ; le contrôleur signale un sujet hors zone. | Export vertical d'un clip sans sujet coupé sur les plans marqués conformes. |
| R-L8 | P2 | Tableau de bord du label : artistes, clips, coûts par artiste et par clip, réserves. | — |

## 2. Données : baseline, historique, stabilité (R-A)

| Id | Pr. | Énoncé | Critère |
|---|---|---|---|
| R-A1 | P0 | Un plan est un objet unique ; toutes les vues lisent et écrivent les mêmes lignes. | Un champ modifié dans une vue apparaît dans les autres. |
| R-A2 | P0 | Identifiants stables : aucune édition ne supprime et recrée. Un plan garde identifiant, prises, retours et historique. | Réimporter un découpage modifié conserve l'identifiant et les prises des plans non touchés. |
| R-A3 | P0 | Baseline de Michael dans des champs que les agents ne peuvent pas écrire : mots d'un plan, intention d'un bloc, brief, note d'intention, instructions de casting, retours. Les agents écrivent une version de production à côté ; ils complètent, ils ne reformulent pas. | Après passage d'un agent, la baseline est identique ; l'écriture par un agent est refusée. |
| R-A4 | P0 | Historique : toute modification passe par une fonction d'écriture unique qui journalise objet, champ, avant, après, auteur, raison, date. | Trois modifications donnent trois lignes exactes ; `riot history` les liste. |
| R-A5 | P1 | Un retour de Michael garde son texte, sa route et son résultat (ce qui a été produit en réponse). | Un retour traité est lié à la prise produite ensuite. |
| R-A6 | P0 | Rien de généré n'est écrasé ni supprimé : chaque prise et chaque image est une version. La suppression d'un plan qui a des prises est logique et restaurable. | Deux générations donnent deux versions présentes en base et sur disque. |

## 3. Préparation du clip (R-P)

| Id | Pr. | Énoncé | Critère |
|---|---|---|---|
| R-P1 | P0 | **Analyse du morceau**, une fois par morceau, en local, mise en cache : tempo, temps, sections, énergie par section, paroles calées dans le temps. | L'analyse d'un morceau déjà analysé ne recalcule rien. |
| R-P2 | P1 | Analyse enrichie : pistes séparées (voix, batterie, basse, autres), paroles calées au mot, repérage des passages chantés. En local, en tâche de fond, sans bloquer la régie. | Les passages chantés sont proposés comme plans chantés et points fixes. |
| R-P3 | P0 | **Note d'intention** : une page (concept, arc, palette, références), écrite par Michael ou choisie parmi des propositions du script-doctor, validée par lui, fournie à tous les agents du clip. | Aucun agent du clip ne tourne sans la note validée (hors rédaction de la note). |
| R-B1 | P0 | Le découpage se valide **par bloc**. Un bloc validé peut entrer en préparation pendant que les autres s'écrivent. | Bloc 1 validé : ses plans passent « à préparer », ceux du bloc 2 restent éditables. |
| R-B5 | P0 | Du découpage à la production en un geste, dans les deux sens. La page d'un plan montre bloc, séquence, brief, mots de Michael, version de production, remarques des agents, retours, références, historique. | La réponse de l'API d'un plan contient tous ces éléments. |
| R-B6 | P1 | Le script-doctor écrit ses remarques par plan et par séquence. | — |
| R-P4 | P0 | **Animatique en cartons** : le découpage joué sur le morceau, chaque plan affichant ses mots pendant sa durée, avec les prises gardées quand elles existent. Calculée par du code, gratuite, immédiate. | Disponible dès qu'un bloc a des plans, sans appel à un modèle ni à un agent. |
| R-P5 | P1 | Images dans l'animatique, en option et sur accord. Elles ne sont jamais envoyées à la vidéo, sauf choix explicite comme image maîtresse ou image de départ. | — |

Le découpage proposé par le script-doctor, les points fixes et la modification
d'un découpage validé sont spécifiés dans `PRODUCTION-PLANS-v3.md` (§14.1, R-H18,
R-H25 à R-H27).

## 4. Fabrication des plans (R-H)

Voir `PRODUCTION-PLANS-v3.md` : objets séquence, prise et fenêtre ; rôles ;
catalogue des modèles ; profils ; planificateur ; prompt assemblé ; références
et cohérence ; dépenses et portefeuille ; fil de production ; écrans ;
corrections par niveau ; modification du découpage ; exigences R-H1 à R-H31.

## 5. Montage et sorties (R-M)

Le montage se déduit du découpage. Riot Machine n'est pas un logiciel de
montage manuel.

| Id | Pr. | Énoncé | Critère |
|---|---|---|---|
| R-M1 | P0 | Montage automatique d'un bloc ou du clip sur le morceau : coupes aux timecodes, fenêtres et vitesses des prises gardées, carton pour un plan sans prise ou une zone « à résoudre ». Jouable à tout moment ; ne recalcule que ce qui a changé. | Modifier une fenêtre ne ré-encode que le plan concerné. |
| R-H21 | P1 | Étalonnage commun par séquence. | Les plans d'une séquence reçoivent le même traitement. |
| R-M2 | P1 | Transitions simples (coupe franche par défaut, fondu), titres, générique. | — |
| R-M3 | P1 | Exports : format du clip, déclinaisons (R-L7), fichier maître. | — |
| R-M4 | P2 | Export du projet vers un logiciel de montage (prises nommées et liste de montage importable). | — |
| R-M5 | P2 | Effets légers pilotés par le son (à partir des pistes séparées). | — |

## 6. Régie et assistant (R-R)

| Id | Pr. | Énoncé | Critère |
|---|---|---|---|
| R-R1 | P0 | Régie pensée pour le téléphone, une main : une décision par écran, un défaut proposé pour tout, le coût avant l'action. Écrans : label, artiste, clip (découpage, plan de tournage, séquence, plan, dérushage, montage), portefeuille. | Revue manuelle sur téléphone avec le clip de démonstration. |
| R-R2 | P0 | Chaque état dit **qui est attendu** (Michael, tel agent, le code, le fournisseur) et, s'il est bloqué, pourquoi et quoi faire. | Aucun état sans responsable. |
| R-F2 | P1 | Tableau de bord du clip : par bloc, plans par état, ce qui attend Michael, ce qui tourne, coût engagé et estimé. | — |
| R-D5 | P1 | Notifications regroupées : un message par lot prêt, jamais un par plan. Le canal (Telegram) est vérifié au démarrage ; une panne du canal est signalée dans la régie. | 12 plans prêts dans la même minute : un message. |
| R-R3 | P1 | **Assistant de régie** : un champ de conversation dans la régie et par Telegram. Michael écrit ou dicte une demande ; l'assistant la classe (question d'état, correction d'un plan, d'une prise, d'une séquence, du découpage, demande de dépense) et la transmet au bon acteur, avec l'objet concerné. Les questions d'état sont servies par du code, sans agent. Toute action qui dépense ou qui modifie le découpage revient à Michael pour accord. | « Où en est le refrain ? » répond sans appel à un agent ; « refais le plan 4 plus serré » crée une demande sur le plan 4 avec son coût. |
| R-D6, R-F3 | P2 | File d'attente visible ; journal lisible, groupé, filtrable. | — |

## 7. Performance, sobriété, robustesse (R-T)

| Id | Pr. | Énoncé | Critère |
|---|---|---|---|
| R-T1 | P0 | **Aucun agent sur minuterie.** Un agent n'est lancé que par un événement qui le demande (un état qui l'attend, une demande de Michael). Les événements proches sont regroupés en un seul passage. Au repos, zéro appel à Claude. | Sur 24 h sans activité : aucun lancement d'agent. Dix plans prêts en 5 s : un seul passage. |
| R-T2 | P0 | **Suivi des générations sobre** : le worker n'interroge un fournisseur que s'il a des générations en cours, avec un intervalle croissant, ou par notification quand le fournisseur le permet. Au repos, aucune requête. | Sans génération en cours : zéro requête sortante. |
| R-T3 | P0 | **Le code d'abord.** Ce que le code sait faire ne passe pas par un agent : choix de l'offre, regroupement, coûts, timecodes, états, montage, questions d'état. | Revue : aucun agent appelé pour une de ces tâches. |
| R-T4 | P0 | **Contexte minimal et budget.** Chaque agent reçoit la fiche de ce qu'il traite, pas le clip entier. Chaque agent déclare son modèle (le plus petit qui suffit) et un plafond de tours. Chaque passage est journalisé : agent, déclencheur, durée, tours, jetons quand ils sont connus. Un plafond quotidien configurable suspend les agents et prévient Michael. | `riot usage` donne la consommation par agent et par jour ; le plafond atteint suspend et notifie. |
| R-T5 | P0 | **Aucune double dépense.** Chaque génération porte une clé unique ; un redémarrage, une coupure ou un double clic ne relance pas une génération déjà partie. Le worker reprend les générations en cours au redémarrage. | Tuer le worker pendant une génération puis le relancer : une seule génération facturée, résultat récupéré. |
| R-T6 | P0 | **Opérations atomiques.** Toute action de Michael s'applique entièrement ou pas du tout, et les révisions du découpage sont annulables. Délais et nombre d'essais bornés sur tout appel extérieur. | Une erreur en cours d'application laisse la base dans l'état d'avant. |
| R-T7 | P0 | **Régie rapide** : réponse de l'API en moins de 300 ms sur un clip de 60 plans ; vignettes et aperçus basse définition générés une fois ; chargement à la demande ; mises à jour poussées par le serveur, sans rechargement ni interrogation en boucle. | Mesure automatisée sur le clip de démonstration de 60 plans. |
| R-T8 | P0 | **Calculs lourds en tâche de fond** (analyse du morceau, montage, aperçus), mis en cache, jamais recalculés sans changement, jamais dans une requête de la régie. | Deuxième demande du même montage : servie depuis le cache. |
| R-T9 | P1 | `riot doctor` : état des fournisseurs, des réserves, du canal de notification, du worker, de l'espace disque, des entrées du catalogue trop anciennes. | — |
| R-G3 | P0 | Schéma versionné, migrations numérotées et rejouables, sauvegarde de la base avant chaque migration, aucune suppression de données. | Migrations appliquées deux fois sans erreur ; sauvegarde présente. |
| R-G2 | P0 | Un test par exigence P0 et P1 ; deux scénarios complets en simulation (un bloc en brouillon ; un clip avec modification du découpage et changement d'offre) ; tests verts avant tout commit. | Crochet de pré-commit en place. |
| R-G1, R-G4 | P0 | La spec fait foi ; rien hors spec. Jusqu'au clip zéro, seules les exigences P0. | — |
| R-G5 | P0 | Méthode : un lot à la fois, plan du lot validé par Michael avant le code, test d'abord, résumé en fin de lot. Tout le développement en simulation, sans dépense. | — |

## 8. Livraison

| Lot | Exigences | Ce que Michael obtient |
|---|---|---|
| **0. État des lieux** | — | Ce qui se garde, ce qui se réécrit, sur une branche neuve ; rien n'est supprimé |
| **1. Fondations** | R-G3, R-G2, R-A1 à R-A4, R-A6, R-T5, R-T6 | Données sûres, baseline, historique, aucune double dépense |
| **2. Label et objets** | R-L1 à R-L4, R-H1, R-H2, R-H3, R-H10, R-R2 | Label, artiste, clip, séquences, prises, catalogue, états |
| **3. Calcul** | R-H4, R-H5, R-H8, R-H9, R-H28, R-T3 | Planificateur, accords de dépense, portefeuille, avertissements de compatibilité |
| **4. Préparation** | R-P1, R-P3, R-P4, R-B1, R-M1, R-T8 | Analyse, note d'intention, validation par bloc, animatique, montage |
| **5. Fabrication** | R-H6, R-H7, R-H14, R-H15, R-H31, R-T1, R-T2, R-T4 | Prompt assemblé, références, image maîtresse, agents sobres |
| **6. Régie** | R-R1, R-B5, R-H11, R-H12, R-H13, R-H25, R-H26, R-T7 | Plan de tournage, page du plan, dérushage, propositions du script-doctor |
| → **Clip zéro** | | Le bloc 1 de JJ, sur les crédits offerts |
| **7. Découpage au son** | R-H27, R-H18, R-P2, R-B6 | |
| **8. Souplesse** | R-H16, R-H17, R-H19, R-H20, R-H22, R-H29, R-H30, R-A5 | Prolonger, plan suivant, retouche, changement d'offre, rodage |
| **9. Label vivant** | R-L5, R-L6, R-L7, R-H21, R-M2, R-M3, R-R3, R-D5, R-F2, R-T9, R-P5 | Bibliothèque, plans B, déclinaisons, finition, assistant |
| **10. Ensuite** | R-L8, R-M4, R-M5, R-H23, R-H24, R-D6, R-F3 | |

## 9. Identifiants retirés

| Retiré | Remplacé par |
|---|---|
| R-B2, R-B3, R-B4 | R-H25, R-H26, R-H27 et `PRODUCTION-PLANS-v3.md` §8.7, §14 |
| R-C1, R-C2, R-C3, R-C4 | Qualité du clip (R-L4, `PRODUCTION-PLANS-v3.md` §8.6), R-H8, R-H9, R-H17, R-H24 |
| R-D1, R-D2, R-D3, R-D4 | R-H8 (R-D2 supprimée sans remplacement), R-H12, R-H13, R-T1 |
| R-E1, R-E2, R-E3, R-E4 | R-H7, R-H15, R-H22, R-L2, R-H19 |
| R-F1 | R-R2, R-H10 |

## 10. Changelog

- 3.0 (12/11/2026) : spécification unique. Ajout du label (R-L), de la
  préparation (R-P), du montage (R-M), de la régie et de l'assistant (R-R), de
  la performance et de la robustesse (R-T). Intègre les décisions des 11 et
  12/11 et les propositions retenues après l'étude des outils du marché.
