# Test des trois modes de Veo 3.1 sur Vertex (11/11/2026)

Brief : `BRIEF-TEST-VEO.md`. Plan et prompts : `plan.json`. Script : `scripts/test_veo_modes.py`.
Budget validé : 4,80 $ (6,40 $ au pire). **Dépensé : 4,80 $.** P4 a été reporté au 12/11 à cause d'une panne de Cloudflare, puis fait ce jour-là sur Cloudflare, sans autre fournisseur.
Les observations portent sur trois images extraites par vidéo (`planche.jpg`) et
doivent être confirmées en regardant les vidéos.

## 1. Les générations

| Plan | Mode | Modèle | Références envoyées | Résultat | Coût | Génération |
|---|---|---|---|---|---|---|
| P1 (plan 5) | références | Fast 720p 8 s | visage `details/ancienne-canon-7.png`, porte-documents | vidéo reçue | 0,64 $ | 56 s |
| P2 (plan 2) | références | Fast 720p 8 s | visage `ancienne-canon-7.png`, porte-documents | vidéo reçue | 0,64 $ | 62 s |
| P3 (gros plan tiré du plan 4) | références | Fast 720p 8 s | visage `ancienne-canon-7.png` | vidéo reçue | 0,64 $ | 34 s |
| P4 (plan 4) | première + dernière image | Fast 720p 8 s | `P4/premiere.png` et `P4/derniere.png`, faites le 12/11 sur FLUX.2 klein 9B (Cloudflare, gratuit) avec `ancienne-canon-7.png`, le porte-documents et le portail | vidéo reçue le 12/11, aucun refus | 0,64 $ | 66 s |
| P5 (plan 5, témoin) | image vers vidéo | Fast 720p 8 s | visuel actuel `plan-005-v10.png` | vidéo reçue | 0,64 $ | 55 s |
| P1b (= P1) | références | Standard 720p 8 s | comme P1 | 1er essai bloqué en sortie (15236754, non facturé) ; relancé une fois avec l'accord de Michael : vidéo reçue | 1,60 $ | 50 s |

### Les refus, dans l'ordre

Un refus ne coûte rien : Google l'écrit dans sa réponse.

1. Premier passage, avec P1, P2 et P1b en `canon.png` + tenue + sac, et P3 en `canon.png` + tenue : les quatre refusées, « input image violates Vertex AI's usage guidelines », code 15236754.
2. P3 avec `canon/tshirt-blanc-rousseur.png` + tenue : refusée à l'entrée, même code.
3. P3 avec `tshirt-blanc-rousseur.png` seule : l'entrée passe, mais la vidéo est filtrée en sortie (« 1 videos were filtered out… », 15236754).
4. P3 avec `details/ancienne-canon-7.png` seule : acceptée.
5. P1 et P2 avec `ancienne-canon-7.png` + porte-documents : acceptées. P1b, avec les mêmes images en Standard : filtrée en sortie. Je ne l'ai pas relancée d'office. Michael a accordé une relance, qui est passée.

**Ce que j'en conclus.** La photo de la tenue black tailor (`looks/black-tailor/11008-2.png`) est refusée dès l'entrée, et je l'ai retirée de P1 et P2. Les deux photos `canon` de la v2 donnent une vidéo bloquée en sortie, car le filtre « personnalité connue » vise ce visage-là. `ancienne-canon-7.png` passe, mais le filtre de sortie n'est pas déterministe : P1 est passée en Fast et P1b, avec les mêmes images, a été bloquée en Standard.

**P4.** FLUX.2 klein 9B sur Cloudflare a répondu « Internal server error » (code 3043) trois fois de suite, que ce soit avec `canon.png` ou avec `ancienne-canon-7.png`. Ce n'est pas le quota du jour. Le 12/11 à 10 h 17, Cloudflare a répondu du premier coup et les deux images sont faites. Veo a accepté la vidéo sans refus, ni à l'entrée ni en sortie.

## 2. Observations par vidéo

- **P1, références, plan 5.** JJ est vue de dos presque tout le plan : la ressemblance ne se juge pas. Le porte-documents est le bon (cuir camel, rabat), le tailleur noir est juste, aucun objet parasite. Elle tourne la tête vers la rue, pas vers la haie comme le dit le prompt. Le début et la fin sont conformes : elle s'éloigne et continue.
- **P2, références, plan 2.** C'est la vidéo la plus fidèle au plan : porte vitrée gris-bleu, trois marches en pierre, vélo vert d'eau, tailleur noir à décolleté en V, bon sac. Le visage est petit dans le cadre. Au milieu, elle semble tenir le guidon du vélo plutôt que d'essuyer la selle : à vérifier sur la vidéo. Le plan finit comme prévu, quand elle traverse la cour vers la droite.
- **P3, références, gros plan.** Le visage est proche de JJ : boucles brun cuivré sans reflet blond, yeux clairs, peau dorée. Les taches de rousseur restent à vérifier en plein écran. La veste est croisée à deux boutons, alors que le prompt et la tenue disent un bouton. Les mains sur la grille sont propres sur les images extraites. Le plan finit comme le prompt le dit, quand elle relève la tête vers la rue.
- **P4, première + dernière image, plan 4** (`planche-p4.jpg`). Le début colle exactement à la première image : JJ devant le portail, main sur la serrure, porte-documents camel à l'épaule, tailleur noir juste, visage proche de JJ (boucles cuivrées, peau dorée), aucun cadenas. La clé se voit dans sa main gauche vers 2 s ; la rotation de la clé et les deux tractions sur le portail ne se lisent pas sur les images extraites, à vérifier sur la vidéo. Le défaut vient des deux images d'entrée : klein n'a pas tenu « same framing », et la dernière image est plus large, avec la rue en profondeur et JJ qui s'éloigne, le bras tendu vers le portail. Pour relier les deux cadrages, Veo improvise : vers 4 s, JJ quitte le portail et part sur le trottoir, la caméra recule alors que le prompt la veut fixe, puis vers 6,5 s un fondu enchaîné bascule sur le cadrage de la dernière image, où elle revient tendre la main vers le portail. La fin est donc exacte image par image, mais l'action du milieu n'a pas de sens.
- **P5, témoin, image vers vidéo.** Le visage reste fidèle à l'image de départ, mais le sac est faux (un cabas, hérité du visuel) et un chemisier blanc apparaît, hérité du prompt. La fin est conforme : elle se retourne et repart.

## 3. Comparaison P1 références Fast / P1b Standard / P5 témoin

**P1 Fast contre P1b Standard** (`planche-p1-p1b.jpg`), mêmes images, même prompt :
- **Standard joue mieux l'action.** JJ se retourne vraiment vers la haie et la caméra, son visage passe de trois quarts et reste ressemblant : boucles cuivrées, peau dorée. En Fast, elle reste de dos et tourne à peine la tête.
- **En Standard, le sac se porte à la main** et non à l'épaule comme le dit le prompt. En Fast, il est bien à l'épaule. Dans les deux, le sac et la tenue sont justes.
- **Coût :** 1,60 $ en Standard contre 0,64 $ en Fast. Le filtre de sortie a bloqué le premier essai Standard, sans frais.

**P1 contre P5 :**
- **Le mode références règle le sac et la tenue.** P1 a le porte-documents et le tailleur noir. P5 garde le cabas et ajoute un chemisier blanc, deux erreurs venues de la chaîne.
- **Le témoin tient mieux le visage**, puisqu'il part d'une image où on le voit. P1 ne montre JJ que de dos : le mode références ne garantit pas le cadrage.

## 4. Réponses aux trois questions

1. **Fast accepte-t-il les références ?** Oui. `veo-3.1-fast-generate-001` a accepté `referenceImages` sans erreur « not supported ».
2. **JJ tient-elle en mode références ?** Oui en gros plan (P3), à condition d'utiliser une photo que le filtre laisse passer. Les deux photos `canon` de la v2 sont bloquées. Il faut donc une planche de vues de JJ v2 (face, trois quarts, profil) testée chez Google, comme pour la v1 le 29/10.
3. **Le mode deux images règle-t-il P4 ?** En partie. Veo respecte la première et la dernière image à la lettre, sans cadenas et avec le bon sac, ce que le mode image vers vidéo n'assurait pas. Mais il ne corrige pas deux images incohérentes entre elles : quand le cadrage change de l'une à l'autre, il fait bouger la caméra, invente un trajet et finit par un fondu. Le mode est donc utile pour un plan d'action, à une condition : les deux images doivent avoir le même cadrage et le même décor, et seule la pose doit changer. Il faut les faire valider ensemble par Michael avant la vidéo, ou faire la dernière image en retouchant la première plutôt qu'en la générant à part.

## 5. Ce que la chaîne actuelle a produit

À reprendre ensuite. Rien n'est corrigé.

- Le visuel validé du **plan 4** (`plan-004-v14.png`) montre un **cadenas** sur le portail, et JJ y porte un **cabas** au lieu du porte-documents.
- Le visuel validé du **plan 5** (`plan-005-v10.png`) montre aussi le **cabas**.
- Le prompt vidéo actuel du **plan 5** décrit « **navy blazer, white blouse** », ce qui n'est pas la tenue black tailor. La vidéo témoin P5 montre ce chemisier blanc.
- **Telegram ne délivre plus les notifications depuis le 7/11** (`riot notify` répond « envoye: false »). La notification de fin de ce test n'est pas partie.

## 6. Décision de Michael sur la photo de la tenue (11/11)

`looks/black-tailor/11008-2.png` est très probablement la photo d'une vraie personne trouvée en ligne : déposée à la main, sans génération, et refusée par Google dès l'entrée. Elle ne doit plus servir de référence nulle part.

La régie a maintenant un statut « Inspiration seulement » pour les photos de tenue. La photo est rangée dans `inspiration/`, sert encore à créer une feuille de tenue, mais ne part jamais en référence. Le bouton « Remettre en référence » annule.

La photo de JJ a été passée dans ce statut par l'application. La tenue black tailor n'envoie donc plus aucune image en référence : elle est décrite par le texte seulement, jusqu'à une photo générée de JJ dans la tenue (pack v2). Le code n'est pas commité, à la demande de Michael.

## 7. Leçons à ajouter à PROCESS.md (« Ce qu'on a appris »), sans le modifier maintenant

- 11/11/2026 : Veo (Vertex) bloque les deux photos canon de JJ v2 (`canon.png`, `canon/tshirt-blanc-rousseur.png`). L'une est refusée à l'entrée avec la photo de la tenue, l'autre seule donne une vidéo filtrée en sortie, code 15236754 « personnalité connue ». `details/ancienne-canon-7.png` passe, en Fast comme en Standard. Une référence pour Veo se teste une fois avant d'entrer dans le pack.
- 11/11/2026 : un refus de Veo en sortie (« videos were filtered out ») n'est pas facturé et semble aléatoire. P1 passe en Fast, P1b est bloquée en Standard avec les mêmes images et le même prompt, puis passe à la relance. Une seule relance, sur accord de Michael, est raisonnable.

## 8. Recommandations, sans les appliquer

- **Dans `config/models.yaml`**, ajouter à `veo-31-fast-vertex` et `veo-31-vertex` un mode « références » : `referenceImages` de type asset, au plus 3, durée fixée à 8 s, sans image de départ ni dernière image. Lite ne le prend pas.
- **Dans la chaîne**, offrir les deux modes par plan :
  - le mode références quand la tenue et les objets comptent plus que le cadrage exact ;
  - l'image de départ quand la composition est décisive.

  Le routeur proposerait l'un ou l'autre, et Michael choisirait.
- **Des références « propres pour Google »** par personnage et par tenue, chacune testée une fois et marquée acceptée ou refusée. La photo de tenue trouvée en ligne est refusée : il faut une photo générée de JJ dans la tenue.
- **Le mode première + dernière image** pour les plans d'action, avec deux images au même cadrage, validées ensemble. La dernière image se fait de préférence en retouchant la première (même décor, même caméra, seule la pose change).
- **Le filtre de sortie est aléatoire.** Une vidéo bloquée est gratuite, et une relance unique sur accord de Michael est raisonnable.
- **Prompts.** 150 à 200 mots qui décrivent tout le plan ont donné des vidéos fidèles à l'action (P2, P3). Une phrase sur l'identité ne suffit pas à forcer un plan de face : il faut l'écrire (« she turns to face the camera »).
