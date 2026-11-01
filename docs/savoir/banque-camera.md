# Banque de plans et de mouvements de caméra

La référence du prompteur et du storyboardeur : grosseurs, angles, mouvements, optiques, avec la formulation qui marche dans chaque modèle et l'effet produit. Recherche du 1er novembre 2026.

Recherche pour le prompteur de Riot Machine. Date : 1er novembre 2026.
Modèles visés : Veo 3.1 aujourd'hui, puis Kling 3, Seedance 2, Wan, Hailuo, Runway.

## Légende

- `[S12]` renvoie à la source n° 12 de la section « Sources ».
- Les formulations entre guillemets et en anglais sont copiées mot pour mot depuis la source citée.
- **[déduit]** signale une règle ou un usage que je propose sans source directe. Il vient du vocabulaire du cinéma ou du recoupement de plusieurs sources.
- **[tiers]** signale un blog d'éditeur ou de plateforme, non officiel et souvent commercial. À tester avant d'en faire une règle.
- Les usages « en clip » (couplet, refrain, etc.) sont sourcés quand une source les donne (surtout Luma [S19], Atlabs [S22], la recette Higgsfield [S7]). Sinon ils sont marqués [déduit].

---

## 1. Règles générales

### 1.1 Un seul mouvement principal par plan

- Kling recommande un mouvement principal par plan. Empiler push, pan, tilt, rotate et zoom rend l'image instable [S3].
- Seedance exécute proprement une instruction de caméra, mais pas deux. Deux mouvements empilés donnent « jitter, drift, or mid-clip direction changes » [S18].
- Hailuo : un ou deux mouvements restent lisibles. Au-delà, le mouvement intermédiaire tremble [S13]. Replicate fixe la limite du modèle Director à 3 mouvements combinés [S14].
- Runway : « Use one primary camera movement per prompt » [S11].
- Pour enchaîner deux mouvements, on coupe en deux plans. Seedance accepte « cut to » [S18]. Veo accepte des segments horodatés [S2]. Kling 3 accepte jusqu'à six plans dans une génération [S5].

### 1.2 Toujours un mot de vitesse

- Sans mot de vitesse, le modèle produit un mouvement « moyen » [S12].
- Mots qui marchent : slow, gradual, steady, subtle, gentle, rapid, fast, sudden, dramatic, continuous [S12]. Kling ajoute « smooth », « steady », « no sudden motion » [S3].
- Runway donne une durée dans le mot : « slow dolly push-in over 4 seconds » [S10].
- Le blog Kling associe une vitesse à une durée de plan : « Ultra-slow motion » (2 à 3 s), « slow and deliberate » (5 à 8 s), « moderate pace » (3 à 5 s), « quick snap » (1 à 2 s) [S4].

### 1.3 Donner une cible et un point d'arrivée

- Un pan sans cible dérive. Écrire « pan left to reveal… » [S10].
- Seedance : décrire l'état final. Exemple fort : « slow push-in from a 45° angle, ending in a medium close-up » [S18].
- Kling : ajouter une proposition de but, du type « to emphasize » ou « to reveal » [S3].
- Kling 3 : décrire où le mouvement s'arrête, sinon il boucle ou déforme (guide tiers cité dans la recherche, [tiers]).

### 1.4 Séparer la caméra et le sujet

- Dire lequel des deux reste immobile. Sinon le modèle anime les deux [S12].
- Phrases de verrouillage : « The camera holds completely still. » et « No subject motion. » [S12].
- Un push-in sur un sujet immobile réussit mieux qu'un push-in sur un sujet rapide [S3].
- Sur Veo 3.1, sujet et caméra en mouvement en même temps donnent des résultats imprévisibles [S21].
- Ne pas combiner un push-in avec plusieurs changements du sujet (se tourne, marche, change d'expression) [S3].

### 1.5 En image vers vidéo, décrire le mouvement, pas la scène

- L'image fixe déjà le sujet, le décor et la lumière. Le prompt décrit ce qui change [S12] [S5] [S16].
- Structure Runway image vers vidéo : « The camera [motion description] as the subject [action]. [Additional descriptions] » [S9].
- Formule Wan image vers vidéo : « Prompt = Motion + Camera movement » [S16].
- Redécrire la scène donne une boucle presque fixe [S12].
- Ne demander que le mouvement que l'image permet. Un portrait buste ne peut pas se lever et partir [S12].
- Vérifier les indices de mouvement dans l'image source (flou de bougé, poussière, pose en plein geste). Ils peuvent contredire le prompt [S9].
- Une image source floue sur les mains ou le visage empire en vidéo [S9].

### 1.6 Ordre des mots dans le prompt

Les sources ne s'accordent pas. Voici ce que dit chaque éditeur.

| Modèle | Ordre recommandé | Source |
|---|---|---|
| Veo 3.1 | « [Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance] » : la caméra en premier | [S2] |
| Runway (texte vers vidéo) | « [Camera] shot of [a subject/object] [action] in [environment]. [Supporting component descriptions] » | [S9] |
| Runway (image vers vidéo) | « The camera [motion description] as the subject [action]. » | [S9] |
| Seedance 2.0 | Formule officielle citée : « subject + motion + environment + camera + aesthetics + audio » | [S18] |
| Kling | Sujet, mouvement du sujet, scène, langage caméra, lumière, ambiance | [S4] [S3] |
| Wan | « Entity + Scene + Motion + Aesthetic control + Stylization » ; la caméra est dans « Aesthetic control » | [S16] |
| Hailuo | La commande entre crochets se place là où l'action a lieu dans la phrase, pas en tête parmi les mots de style | [S13] |

- Atlabs affirme que les modèles pèsent plus les premiers mots et met la caméra en tête [S22] [tiers]. Aucune source officielle ne le confirme.
- **Règle proposée [déduit]** : pour Veo et Runway, la caméra en tête. Pour Kling et Seedance, le sujet d'abord puis une ligne caméra explicite (« Camera: … »). Pour Hailuo, la commande entre crochets au moment de l'action.

### 1.7 Pas de négation dans le prompt

- Veo : ne pas écrire « no » ou « don't ». Décrire ce qu'on veut. Exemple Google : « a desolate landscape with no buildings or roads » plutôt que « no man-made structures » [S2]. Le guide Vertex met les éléments à exclure dans le champ prompt négatif, sous forme de liste : « wall, frame » [S1].
- Runway : « use positive phrasing » [S9]. Une source tierce note que « No camera movement » peut produire l'inverse sur Gen-4 ([tiers], cité dans la recherche Runway).
- Wan accepte un champ negative_prompt séparé, par exemple « warping, camera shake, text » ([tiers], cité dans la recherche Wan).

### 1.8 Demander une caméra fixe

| Modèle | Formulation sourcée | Source |
|---|---|---|
| Veo | « static shot of a serene landscape » ; « The camera is static. » ; « The camera remains static as the flower slowly and gracefully unfurls » | [S1] |
| Runway | « The locked-off camera remains perfectly still » ; « Minimal subject motion only » | [S9] |
| Runway | « The camera is entirely motionless for the duration of the scene, with movement only occurring from the subject. » | [S10] |
| Runway (Gen-4.5, via Runware) | « The camera holds completely still. » | [S12] |
| Hailuo | `[Static shot]` | [S13] |
| Wan | « fixed camera » ; « fixed camera position » | [S16] |
| Wan (test) | « Static locked-off camera » a tenu 5 s sans dérive ni coupe | [S17] |
| Luma (clip) | « Locked three-quarter view » ; « Hold an extreme wide locked shot through the first half » | [S19] |
| Tous (conseil Dreamina) | « A locked-off medium shot holds the same framing throughout. » | [S24] |

Conseils associés :
- Donner au plan une source de mouvement qui n'est pas la caméra : vapeur, cheveux, foule [S24].
- Dire que le sujet reste en place : « The cup stays still. » [S24].
- Répéter « static » plusieurs fois n'aide pas. Si la dérive persiste, changer de mode ou passer par une référence [S24].
- Les plans larges et les plans d'ensemble dérivent le plus. Stabiliser au montage si besoin [S10].
- Seedance 1.0 avait une option « caméra fixe » dans l'API. Une source tierce conseille de la décocher quand on demande un mouvement [S31] [tiers]. À vérifier sur Seedance 2.

### 1.9 Éviter la caméra qui dérive

- Ancrer le mouvement sur un sujet nommé. Sans ancre, le modèle dérive [S22].
- Un tracking dérive si la relation caméra-sujet n'est pas claire [S23]. Exemple Runway : « camera trucks left, matching the rider's speed » [S10].
- Sur Veo 3.1, un dolly de plus de 3 s fait glisser le sujet hors du centre. Solution : couper en deux plans et raccorder au montage [S21].
- Orbite : ajouter « consistent speed » et « subject stays centered and in focus » [S22].
- Ne pas diriger deux fois : si un réglage caméra (preset, curseur) existe, ne pas décrire un autre mouvement dans le texte [S10]. Higgsfield cite la caméra écrite en texte au lieu des paramètres comme cause de déformation [S8].
- Kling a un mouvement par défaut fort. Baisser l'intensité ou passer sur Seedance pour ce plan [S25] [tiers].

### 1.10 Éviter les coupes non voulues

- Runway : allonger la durée, puis ajouter « Continuous, seamless shot » [S9].
- Seedance : « one continuous take, no cuts » [S18].
- Wan coupe tout seul si le prompt ne donne aucune direction caméra. Un test a obtenu cinq plans en 5 s. Ajouter « medium close-up, slight low angle, slow push in » a donné une prise continue [S17].
- Google (Gemini Omni Flash) conseille aussi de demander un plan continu unique [S30].

### 1.11 Durée et amplitude

- Veo 3.1 produit des clips de 4, 6 ou 8 s [S2].
- Seedance : une source tierce résume la règle à « un sujet, une action, un mouvement de caméra, une humeur » pour un clip de 4 s ([tiers], article Luma sur Seedance, page devenue introuvable).
- Trois lieux dans 5 s donnent un « smeared morphing ». Au-delà de 8 s, utiliser une timeline seconde par seconde [S18].
- Wan : la page Alibaba, telle que l'outil d'extraction l'a lue, conseille de garder les orbites sous 45° [S16]. À vérifier sur la page.
- Veo 3.1 : « 360 orbit » devient le plus souvent un pan partiel [S21].
- **Règle proposée [déduit]** : sur 4 s, un quart d'orbite, un push-in court ou un tilt simple. Garder l'orbite complète, le crane ample et le FPV pour 6 à 8 s, ou pour un preset dédié.

### 1.12 Protéger les visages

- Les mouvements rapides déforment les visages en cours de plan, par exemple `[Shake]` [S13].
- Les rotations rapides, les changements de sens brusques et les trajectoires multi-directions sont durs à garder cohérents [S8].
- Les vues de face donnent des visages plus propres que les angles extrêmes. Formulations : « eye-level camera angle », « slight three-quarter view », « Direct eye-level frontal view » [S15].
- Le flou de bougé fait perdre les repères du visage. Ralentir le mouvement ou raccourcir le plan [S15].
- En gros plan, un mouvement lent et un cadrage de profil limitent la déformation. Exemple Luma : « Tight profile close-up, gentle handheld movement » [S19].
- Ne changer qu'une variable à la fois entre deux plans (décor, angle ou lumière). Garder le décor et ne changer que l'angle stabilise le personnage [S8].
- Grand angle en gros plan : risque de déformation du visage ([tiers], cité dans la recherche sur les visages).

### 1.13 Dolly ou zoom : le dire

- Le zoom grossit l'image sans parallaxe. Le dolly déplace la caméra et crée la parallaxe [S1] [S13].
- Veo 3.1 confond les deux dans environ 20 % des essais. Ajouter « camera physically moves forward, not zoom, true dolly motion » a fait passer le taux de réussite d'environ 80 % à 95 % [S21] [tiers].
- Kapwing propose : « Camera physically moves forward through the scene. No lens zoom. » [S23].
- Sur Veo, « zoom » produit souvent un zoom numérique [S21].

### 1.14 Chiffrer les angles

- Sur Veo 3.1, un angle chiffré marche mieux qu'un angle vague [S21] :
  - contre-plongée : « camera positioned 15cm above ground level, looking up at 45 degrees » ;
  - dutch angle : « camera tilted 15 degrees counterclockwise on its roll axis » (compris dans 65 % des essais).
- Sur Veo, « aerial » marche mieux que « drone shot » [S21].

### 1.15 Format vertical 9:16

- En 9:16, privilégier push-in, tilt et orbite. Éviter les grands travellings latéraux [S22] [tiers].

### 1.16 Mots vagues à bannir

- « cinematic camera movement », « make it cinematic », « dynamic camera, epic movement, orbiting and zooming », « dynamic cinematic camera » [S3] [S18] [S10].
- Runway : un objectif nommé (« 35mm lens ») fait quelque chose de concret, « cinematic » non [S10].

### 1.17 Contradictions à éviter

- « static camera with fast push-in and orbit movement » [S3].
- « Fixed shot » avec « orbit the subject » : jitter ou compromis [S18].
- Push-in avec « the camera stays still » [S13].
- « static handheld dolly zoom » [S22].
- Mélanger la grammaire entre crochets de Hailuo et la même instruction en langage naturel [S13].
- Redire le même mouvement de plusieurs façons : le modèle fait la moyenne [S13].

### 1.18 Ce que disent les comparatifs entre modèles

- Curious Refuge, Kling 3.0 contre Veo 3.1, cinq tests caméra : Kling gagne pan, tracking, POV et handheld. Veo réussit mieux le mouvement du crane up, mais l'image reste inutilisable [S20].
- Atlabs : Seedance 2.0 excelle en tracking complexe et en orbite. Veo 3.1 brille en caméra à l'épaule réaliste et en dialogue [S22] [tiers].
- Seedance suit les directions caméra avec précision. Kling fait des mouvements plus amples et moins précis [S25] [tiers].
- Seedance réagit beaucoup aux mots d'angle et de cadrage, Kling très peu. Kling réagit aux mots de vitesse, qui perturbent Seedance [S26] [tiers].
- Contradiction : PicassoIA trouve le handheld de Veo 3.1 « le plus naturel » [S21], Curious Refuge trouve que Veo 3.1 rate le handheld [S20]. À tester.

---

## 2. Grosseurs de plan

| Nom français | Terme du prompt | Formulation sourcée | Effet, émotion | Usage en clip | Pièges |
|---|---|---|---|---|---|
| Plan de grand ensemble | extreme wide shot | « Hold an extreme wide locked shot through the first half » [S19] | Isolement, échelle ; sujet à peine visible [S10] | Intro, pont, fin [déduit] | Dérive facilement en plan fixe [S10] |
| Plan d'ensemble | wide shot, establishing shot | « wide shot of a lone cabin in a snowy landscape » [S1] | Situe le sujet dans son décor [S1] | Ouverture, changement de lieu [S10] | Dérive en plan fixe [S10] |
| Plan moyen (en pied) | full shot, full body shot | « full shot of a dancer performing » [S1] | Action, mouvement, mode [S10] | Danse, tenue de l'artiste [déduit] | Mains et pieds à surveiller [déduit] |
| Plan américain | medium full shot (« Medium-full shot » [S10]) | « Medium-full shot » [S10] | Corps et attitude [déduit] | Marche, pose, performance [déduit] | |
| Plan taille | medium shot | « medium shot of two people conversing » [S1] | Langage du corps et expression ; « The workhorse shot » [S10] | Couplet, plan chanté [déduit] | |
| Plan rapproché poitrine | medium close-up | « medium close-up, slight low angle, slow push in » (test Wan) [S17] | Visage lisible avec les épaules [déduit] | Plan chanté principal [déduit] | |
| Gros plan | close-up | « close-up of a character's determined eyes » [S1] | Émotion, réaction [S1] [S10] | Refrain, ligne forte du texte [déduit] | Mouvement rapide = visage déformé [S13] |
| Très gros plan | extreme close-up | « extreme close-up of a drop of water landing on a leaf » [S1] | Texture, tension, détail [S10] | Insert : yeux, lèvres, bijoux [déduit] | |
| Insert, macro | macro close-up, macro lens | « locked-off camera » avec « macro close-up » (gabarit produit Wan) [S17] | Détail [S10] | Insert : micro, main, instrument [déduit] | |
| Plan à deux | two-shot | Terme listé par Google [S2] et Alibaba [S16] | Relation entre deux personnes [déduit] | Duo, featuring [déduit] | Identités qui se mélangent aux points de contact [S8] |

Exemples de cadrages pour un clip chanté, tirés de la description de la vidéo Tao Prompts [S27] (liste « Camera Angles for Burst Mode ») :
- « Medium front shot, she sings directly into camera. »
- « Close-up as she performs. »
- « Tight close-up on her eyes looking through the crystal glass. »
- « Profile close-up with crystal reflections across her face. »
- « Three-quarter full-body shot inside the crystal cage. »
- « Tight close-up as she closes her eyes during an emotional lyric. »
- « Low-angle medium shot emphasizing the towering crystal cage. »
- « Wide shot centered on the cage with crystal statues dancing around her. »
- « Over-the-shoulder shot looking toward the crystal statues. »
- « Tight close-up as she sings with a subtle head tilt. »

Observation : Tao Prompts décrit chaque plan par un cadrage et une action. Il ne met pas de mouvement de caméra dans ces 20 plans. Je n'ai pas pu lire la transcription de la vidéo.

---

## 3. Angles

| Nom français | Terme du prompt | Formulation sourcée | Effet, émotion | Usage en clip | Modèles et pièges |
|---|---|---|---|---|---|
| Hauteur d'yeux | eye-level shot | « eye-level shot of a woman sipping tea » [S1] | Neutre, naturel [S1] [S4] | Plan chanté face caméra [déduit] | L'angle le plus sûr pour les visages [S15] |
| Contre-plongée | low-angle shot | « low-angle tracking shot of a superhero landing » [S1] ; « low-angle shot. Camera positioned below the subject's eyeline, pointing upward toward them. » [S23] | Puissance, domination [S4] [S10] | Rap, hip-hop : « Low-angle camera tracks backward from knee height. » [S19] | Veo : chiffrer la hauteur et l'angle [S21] |
| Contre-plongée totale | worm's-eye view | « worm's-eye view of towering skyscrapers » [S1] | Échelle, enfermement, malaise [S10] | Plan de décor, intro [déduit] | |
| Plongée | high-angle shot | « high-angle shot of a child lost in a crowd » [S1] ; « High angle looking down at a serene pond. » [S9] | Vulnérabilité, isolement [S4] [S10] | Couplet triste, solitude [déduit] | |
| Plongée totale | bird's-eye view, top-down shot, overhead | « A bird's-eye view of a vast, intricate maze made of high green hedges. » [S1] ; « Bird's eye view looking straight down » [S21] | Motif, chorégraphie, géographie [S10] | Danse : preset « Overhead » dans la recette clip Higgsfield [S7] | Veo le réussit bien [S21] |
| Plan débullé | dutch angle, canted angle | « dutch angle shot of a character running down a hallway » [S1] ; « camera tilted 15 degrees counterclockwise on its roll axis » [S21] | Malaise, désorientation [S10] | Pont, tension, clip sombre ; recettes horreur et SF Higgsfield [S7] | « Use sparingly » [S10] ; amplitude imprévisible sans chiffre [S21] |
| Plan subjectif | POV shot | « POV shot as someone rides a rollercoaster » [S1] | Immersion [S10] | Plan du point de vue du public ou de l'artiste [déduit] | Veo 3.1 a raté le POV (personne ajoutée, rendu de tracking) ; Kling 3.0 meilleur [S20] |
| Amorce épaule | over-the-shoulder shot | « over-the-shoulder shot during a tense negotiation » [S1] | Point de vue, confrontation [S10] | Duo, regard vers la foule [S27] | |
| Profil | profile shot | « Tight profile close-up, gentle handheld movement » [S19] | Visage stable en gros plan [S19] | Couplet intime [S19] | |
| Trois-quarts | three-quarter view | « slight three-quarter view » [S15] ; « Locked three-quarter view » [S19] | Plus vivant que la face, visage propre [S15] | Plan chanté [déduit] | |
| Plan aérien | aerial shot | « Sweeping aerial drone shot flying over a tropical island chain » [S1] | Grandeur, géographie [déduit] | Intro, transition de lieu [déduit] | Sur Veo, « aerial » bat « drone shot » [S21] |

---

## 4. Mouvements de caméra (fiches)

### 4.1 Plan fixe
- **Terme** : static shot, locked-off shot, fixed camera.
- **Prompt** : voir le tableau 1.8.
- **Effet** : stabilité, lisibilité. Runway : « Creates tension and symmetry; lets action carry the scene » [S10].
- **Clip** : plan chanté avec lip sync [déduit], plan de danse où le corps fait tout le mouvement [déduit], plan symétrique.
- **Modèles** : tous le gèrent. Une liste communautaire en fait le choix par défaut pour la vidéo IA [S33] [tiers].
- **Pièges** : dérive sur les plans larges [S10]. Donner un mouvement à la scène pour éviter l'image figée [S24].

### 4.2 Travelling avant
- **Terme** : dolly in, push in, push-in.
- **Prompt** :
  - « Slow continuous push-in toward the Mustang. » [S12]
  - « The camera slowly pushes in as the person scales the giant soda. » [S9]
  - « Slow push-in toward a luxury skincare bottle on a marble table » [S3]
  - « slow dolly push-in over 4 seconds » [S10]
  - Atlabs : « Slow dolly in toward the subject's face », avec « background gently compressing, shallow depth of field » et « tension building with each second, cinematic 35mm look » [S22]
  - Anti-zoom pour Veo : « camera physically moves forward, not zoom, true dolly motion » [S21]
- **Effet** : attire l'attention, intimité, tension qui monte [S3] [S10] [S22].
- **Clip** : Atlabs le cite pour les clips musicaux et les révélations [S22]. Recette Higgsfield : « Dolly In/Out on beat » [S7]. Montée vers le refrain, ligne émotionnelle [déduit].
- **Modèles** : le mouvement le plus fiable selon plusieurs guides. Veo : 80 % de vrai dolly, 95 % avec la phrase anti-zoom [S21].
- **Pièges** : glisse vers le zoom [S21]. Sujet qui sort du centre au-delà de 3 s sur Veo [S21]. Éviter si le sujet change trois fois d'action [S3].

### 4.3 Travelling arrière
- **Terme** : dolly out, pull back, pull out, pull-back reveal.
- **Prompt** :
  - « dolly out from the character to emphasize their isolation » [S1]
  - « Camera slowly pulls back from a close-up of a designer ring to reveal a full jewelry display » [S3]
  - « Camera pulls back slowly from a close-up of a child's hands » … « to reveal an entire glowing carnival stretching to the horizon » [S22]
  - Clip : « Slowly pull back from an eye close-up to a waist-up shot. » [S19]
  - Hailuo : `[Pull out]` [S13]
- **Effet** : révélation, échelle, contexte, isolement, fin [S1] [S10] [S22].
- **Clip** : refrain chez Luma, y compris « pull rapidly backward into a wide skyline reveal » [S19]. Ouverture et fin chez Atlabs [S22].
- **Pièges** : le plan doit avoir un sujet de départ clair et un décor à révéler [S3].

### 4.4 Travelling latéral
- **Terme** : truck left / truck right, dolly left / dolly right, lateral dolly.
- **Prompt** :
  - « truck right, following a character as they walk along a busy sidewalk » [S1]
  - « Slow lateral dolly from left to right. » [S12]
  - « camera trucks left, matching the rider's speed » [S10]
  - Hailuo : `[Truck left]`, `[Truck right]` [S13]
  - Couplet chez Luma : « Very slow lateral camera slide, shallow depth of field » [S19]
- **Effet** : accompagne, parcourt l'espace [S10].
- **Clip** : couplet calme [S19], marche de l'artiste [déduit].
- **Pièges** : ne pas confondre avec le pan (le pan pivote sur place, le truck glisse) [S24]. À éviter en 9:16 pour les grands latéraux [S22].

### 4.5 Travelling d'accompagnement
- **Terme** : tracking shot, follow shot, follow-cam.
- **Prompt** :
  - « Side tracking shot following the character as they walk through a neon-lit street at night » avec « camera locked to their pace » [S22]
  - « Track the subject left to right as they walk along the sidewalk » [S21]
  - « Smooth subtle tracking shot following her gracefully from left to right. » [S3]
  - Rap : « Low-angle camera tracks backward from knee height. » [S19]
  - Wan : « follow-cam perspective » [S16]
  - Hailuo : `[Tracking shot]` [S13]
- **Effet** : élan narratif, le spectateur marche avec le sujet [S22] [S16].
- **Clip** : marche, poursuite, lyric video [S22].
- **Modèles** : Kling 3.0 a battu Veo 3.1 de peu sur « low-angle tracking shot of a man running through a jungle » [S20]. Seedance fort sur les trackings complexes [S22] [tiers].
- **Pièges** : perd le sujet dans les virages et les foules sur Veo [S21]. Qualité en baisse si on ajoute un crane pendant que le sujet bouge [S21]. Un détail d'approche peut transformer le tracking en push-in [S24].

### 4.6 Panoramique horizontal
- **Terme** : pan left / pan right.
- **Prompt** :
  - « slow pan left across a city skyline at dusk » [S1]
  - « Slow horizontal pan from left to right along the coastline. » [S12]
  - « Smooth pan from left to right across a modern desk setup » [S3]
  - Hailuo : `[Pan left]`, `[Pan right]` [S13]
- **Effet** : parcourt un espace, suit une action, révèle [S3] [S10].
- **Clip** : révélation d'un décor ou d'un groupe [déduit].
- **Modèles** : Kling 3.0 a mieux réussi un pan de révélation que Veo 3.1, qui a déformé le personnage [S20].
- **Pièges** : donner une cible [S10]. Ne pas panoter contre un sujet rapide [S3]. Pan et tilt simultanés sont plus durs [S4].

### 4.7 Panoramique vertical
- **Terme** : tilt up / tilt down.
- **Prompt** :
  - « tilt down from the character's shocked face to the revealing letter in their hands » [S1]
  - « Camera tilts up from a pair of running shoes to the athlete's face » [S3]
  - « Slow vertical tilt upward. » [S12]
  - « gentle tilt down from sky to ground » [S4]
  - Exemple cité par le compte Gemini : « slow vertical tilt down, cinematic shot » (rapporté par une recherche, compte X de Google)
- **Effet** : montre la hauteur, va d'un détail à un autre sur l'axe vertical [S3] [S10].
- **Clip** : présentation de l'artiste des pieds au visage [déduit, sur le modèle de [S3]]. Bon en 9:16 [S22].
- **Pièges** : il faut une structure verticale claire dans l'image [S3].

### 4.8 Panoramique filé
- **Terme** : whip pan.
- **Prompt** :
  - « whip pan from one arguing character to another » [S1]
  - « Rapid whip pan from the drummer to the lead singer mid-performance » avec « motion blur streaking across the frame, landing sharply in focus on the singer » [S22]
  - Runway : « Whip pan to painting of a fox. Whip pan back to the woman with a curious expression. » [S9]
  - Preset Higgsfield « Whip Pan » [S6]
- **Effet** : énergie, transition sèche [S22].
- **Clip** : drop, changement de scène, passage d'un musicien à l'autre [S22].
- **Pièges** : mouvement rapide, risque d'artefacts élevé [S33] [tiers]. Combiner whip pan et macro zoom embrouille le modèle (blog tiers cité dans la recherche). [déduit] Le flou masque la transition : on peut couper au milieu du flou au montage.

### 4.9 Élévation verticale
- **Terme** : pedestal up / pedestal down.
- **Prompt** : « pedestal up to reveal the full height of an ancient, towering tree » [S1]. Hailuo : `[Pedestal up]`, `[Pedestal down]` [S13].
- **Effet** : révèle ce qu'il y a derrière un obstacle, sans changer d'angle [S10].
- **Pièges** : ce n'est pas un crane, la caméra monte droite [S10].

### 4.10 Grue
- **Terme** : crane up / crane down, crane shot, jib up / jib down.
- **Prompt** :
  - « crane shot revealing a vast medieval battlefield » [S1]
  - Google : « Crane shot starting low on a lone hiker and ascending high above, revealing they are standing on the edge of a colossal, mist-filled canyon at sunrise » [S2]
  - « slow crane up from ground level to reveal the full skyline » [S21]
  - « Camera cranes up and away from the subject standing on a rooftop at golden hour », révélant « the full city skyline below, triumphant and cinematic » [S22]
  - Presets Higgsfield : « Crane Up », « Crane Down », « Crane Over The Head », « Jib up », « Jib down » [S6]
- **Effet** : triomphe, ampleur, révélation [S22] [S23].
- **Clip** : dernier refrain, fin, plan d'installation [S22].
- **Modèles** : Veo 3.1 tient bien le crane [S21] et l'exécute mieux que Kling 3.0 dans le test Curious Refuge [S20].
- **Pièges** : mouvement ample. Sur 4 s, viser une montée courte [déduit].

### 4.11 Arc et orbite
- **Terme** : arc shot (portion de cercle), orbit, 360 orbit, circle around.
- **Prompt** :
  - « arc shot around a couple embracing in the rain » [S1]
  - « Slow continuous orbit around the Mustang. » [S12]
  - « slow clockwise orbit » [S10]
  - « Smooth 180 degree orbit around the subject at chest height », « consistent speed », « subject stays centered and in focus » [S22]
  - Wan : « The camera slowly circles from behind him to the front. » [S16]
  - Veo, première et dernière image : « The camera performs a smooth 180-degree arc shot, starting with the front-facing view of the singer and circling around her to seamlessly end on the POV shot from behind her on stage. » [S2]
  - Clip : « Slow circular orbit during the first half of the chorus » ; « When the strings swell, slowly orbit one quarter around the person » ; « the camera swings into a faster orbit » [S19]
  - Runway : « The camera executes an aggressive, sweeping horizontal arc around the subject » [S9]
  - Hailuo, combinaison « Left circling » : `[truck left, pan right, tracking shot]` [S13]
  - Presets Higgsfield : « Arc Left », « Arc Right », « 360 Orbit », « Lazy Susan » [S6]
- **Effet** : héroïsation, « gravity and importance; a moment crowned » [S23].
- **Clip** : refrain et montée [S19], danse et présentation de personnage [S22], recette clip Higgsfield [S7].
- **Modèles** : Seedance 2.0 fort [S22] [S25] [tiers]. Veo 3.1 transforme souvent « 360 orbit » en pan partiel [S21].
- **Pièges** : une orbite oblige le modèle à inventer les faces cachées du sujet. Risque de déformation du visage (recherche sur les visages, [tiers]). Arc court sur 4 s [déduit]. Wan : sous 45° [S16]. Préciser le sens et la vitesse [S10].

### 4.12 Caméra à l'épaule
- **Terme** : handheld, shaky cam, natural camera shake.
- **Prompt** :
  - « handheld camera shot during a chaotic marketplace chase » [S1]
  - « Handheld documentary film style. Natural camera shake. » [S9]
  - « handheld documentary camera with subtle natural shake » [S10]
  - « Handheld camera following behind the subject through a crowded market » avec « subtle natural shake, documentary realism » [S22]
  - Couplet : « Handheld camera moves between the musician and band silhouettes » [S19]
  - Hailuo : `[Shake]` [S13]
- **Effet** : réalisme, urgence, matière brute [S10] [S22].
- **Clip** : couplet, ambiance live ou backstage [S19] [déduit].
- **Modèles** : PicassoIA le juge le mouvement le plus naturel sur Veo 3.1 [S21]. Curious Refuge trouve au contraire que Veo 3.1 rate le prompt et que Kling 3.0 s'en sort mieux [S20]. Atlabs place Veo 3.1 en tête [S22]. À tester.
- **Pièges** : un tremblement fort déforme les visages [S13]. Rester sur « subtle » ou « gentle » en gros plan [S19].

### 4.13 Steadicam et gimbal
- **Terme** : steadicam, gimbal, smooth gliding.
- **Prompt** : « steady Steadicam movement » [S4]. Runway liste « smooth gliding » comme qualité de mouvement [S11].
- **Effet** : Steadicam suit à pied, plus doux que l'épaule. Gimbal : le plus lisse, pour les trajectoires complexes [S10].
- **Clip** : longue marche de l'artiste, plan-séquence [déduit].

### 4.14 Drone et FPV
- **Terme** : aerial shot, drone shot, drone ascending, FPV drone, FPV racing style.
- **Prompt** :
  - « Fast FPV drone shot diving off a cliff edge and skimming low over the ocean surface toward a lighthouse », « aggressive speed, slight motion blur, high energy » [S22]
  - « Drone ascending from single red poppy. » [S11]
  - « slow forward drone flight rising above the rooftops » [S10]
  - Wan : « fast fly-through » [S16]
  - Preset Higgsfield « FPV Drone » [S6]
- **Effet** : adrénaline [S22].
- **Clip** : EDM, drop, transition entre deux lieux [S22]. Recettes action et SF Higgsfield [S7].
- **Pièges** : mouvement rapide, risque d'artefacts [S33] [tiers]. Mieux sur 6 à 8 s [déduit].

### 4.15 Zoom optique
- **Terme** : zoom in / zoom out.
- **Prompt** : « A slow, dramatic zoom in on a mysterious, ancient compass lying on a dusty map. » [S1]. Hailuo : `[Zoom in]`, `[Zoom out]` [S13].
- **Effet** : grossit sans parallaxe, fond aplati [S13].
- **Clip** : effet clip années 70, rapproché sur un détail [déduit].
- **Pièges** : ne pas l'utiliser quand on veut de la profondeur [S10].

### 4.16 Zoom brutal
- **Terme** : crash zoom, rapid zoom in / out, snap zoom.
- **Prompt** : Runway le définit comme « a rapid, aggressive zoom » et l'enchaîne après un arc, avec la mise au point qui finit sur les yeux du sujet [S9]. Presets Higgsfield « Crash Zoom In », « Crash Zoom Out », « Rapid Zoom In », « Rapid Zoom Out », « YoYo Zoom » [S6]. Les presets « Rapid Zoom » sont rattachés à Hailuo d'après les dossiers d'images [S6].
- **Effet** : choc, révélation brutale, accent comique [S10].
- **Clip** : temps fort, drop, mot-clé du refrain [déduit]. Recette clip Higgsfield : « Crash Zoom In » [S7].
- **Pièges** : aucun test publié trouvé. [déduit] Préférer le preset quand il existe.

### 4.17 Travelling compensé (effet Vertigo)
- **Terme** : dolly zoom, vertigo effect, Hitchcock zoom.
- **Prompt** :
  - « vertigo effect (dolly zoom) on a character standing at the edge of a cliff » [S1]
  - « 5-second dolly zoom » [S4]
  - Prompt bank Higgsfield, cité par la recherche : « The camera physically dollies forward from [6] meters to [2.5] meters while the lens simultaneously zooms out from [18] to [84] degrees field of view. »
  - Presets Higgsfield « Dolly Zoom In », « Dolly Zoom Out » [S6]
- **Effet** : vertige, choc intérieur, moment émotionnel [S1] [déduit].
- **Clip** : prise de conscience dans le texte, pont [déduit].
- **Modèles** : Seedance le liste parmi ses mouvements [S18]. Sur Veo 3.1, « Vertigo effect » donne des résultats inconstants [S21].
- **Pièges** : mouvement double par nature. Passer par un preset ou un prompt chiffré [déduit].

### 4.18 Snorricam
- **Terme** : SnorriCam.
- **Prompt** : terme listé par Runway [S11]. Preset Higgsfield « Snorricam » [S6].
- **Effet** : caméra fixée sur l'acteur, le décor tangue ; stress, émotion forte (fiche tierce Higgsfield, [tiers]).
- **Clip** : perte de contrôle, ivresse, panique [déduit].

### 4.19 Traversée d'objet
- **Terme** : fly-through, through object, flying cam transition.
- **Prompt** : Wan « fast fly-through » [S16]. Presets Higgsfield « Through Object In », « Through Object Out » (par exemple à travers un judas de porte) et « Flying Cam Transition » (passage d'une ville poussiéreuse à un salon par une arche) [S6].
- **Clip** : transition entre deux décors [déduit].

### 4.20 Autres presets Higgsfield utiles en clip
Noms exacts relevés sur la page officielle [S6] : « Head Tracking », « Hero Cam », « Eyes In », « Mouth In », « Glam », « Robo Arm », « Wiggle », « Incline », « Double Dolly », « Super Dolly In », « Super Dolly Out », « Car Chasing », « Car Grip », « Road Rush », « Buckle Up », « BTS », « Eating Zoom », « Low Shutter », « Fisheye », « 3D Rotation ». Descriptions données : « Hero Cam », gros plan qui passe de la silhouette à la pleine lumière ; « BTS », plan de coulisses d'un tournage [S6]. Les autres n'ont pas de description sur la page.

---

## 5. Optiques et mise au point

| Nom français | Terme du prompt | Formulation sourcée | Effet | Usage en clip | Pièges |
|---|---|---|---|---|---|
| Grand angle | wide-angle lens | « wide-angle lens shot of a grand cathedral interior, emphasizing its soaring arches » [S1] | Champ large, espace [S1] | Décor, plan de groupe [déduit] | Déforme les visages en gros plan ([tiers]) |
| Téléobjectif | telephoto lens, long-focus lens | « telephoto lens shot capturing a distant eagle in flight against a mountain range » [S1] | Compresse la perspective [S1] | Artiste isolé dans la foule [déduit] | |
| Fisheye | fisheye lens | « fisheye lens view from inside a car, capturing the driver and the entire curved dashboard » [S1] | Distorsion en barillet [S1] | Rap, skate, esthétique années 90 [déduit] ; preset « Fisheye » [S6] | |
| Macro | macro lens | Terme listé par Google [S2] | Détail [S10] | Insert [déduit] | |
| Focale chiffrée | 35mm lens | Runway cite « 35mm lens » et « 35mm film look » comme termes concrets [S10] | Rendu réaliste [S10] | Toute la vidéo, pour la cohérence [déduit] | 50 mm et 85 mm : aucune source vidéo trouvée. 85 mm pour un portrait est un usage photo [déduit] |
| Faible profondeur de champ | shallow depth of field, bokeh | « Close-up with very shallow depth of field, a young woman's face, looking out a bus window… » [S2] | Isole le sujet [S1] [S10] | Plan chanté, couplet intime [S19] [déduit] | |
| Grande profondeur de champ | deep focus, deep depth of field | « landscape scene with deep depth of field » [S1] | Tout est net [S10] | Plan de groupe, décor chargé [S10] | |
| Flou artistique | soft focus | Terme listé par Google [S2] | Souvenir, rêve, romance [S10] | Pont, flash-back [déduit] | |
| Bascule de point | rack focus | « rack focus from the coffee cup in the foreground to the woman's face in the background » [S21] ; « rack focus slowly shifts to reveal a person sitting alone in the background » [S10] | Déplace l'attention sans bouger la caméra [S10] | Révélation douce, passage micro vers visage [déduit] ; preset « Focus Change » [S6] | Veo : réussi dans l'unique test publié [S21] |
| Reflet d'objectif | lens flare | « cinematic lens flare as the sun dips below the horizon behind a silhouetted couple » [S1] | Chaleur, contre-jour [déduit] | Fin de clip, coucher de soleil [déduit] | |
| Anamorphique | anamorphic lens | Sources tierces : nommer « horizontal » et « blue » pour le flare, « oval » ou « elliptical » pour le bokeh, cadre 2.39:1, source lumineuse ponctuelle dans le champ ([tiers], pages Hailuo knowledge et Melies citées par la recherche) | Look cinéma large [tiers] | Clip esthétique ; style « Anamorphic » de la recette clip Higgsfield [S7] | Trop de termes techniques empilés créent des artefacts ([tiers]) |
| Tilt-shift | tilt-shift lens | Terme listé par Alibaba [S16] | Effet maquette [déduit] | Plan de ville, transition [déduit] | |

---

## 6. Vitesse et temps

| Nom français | Terme du prompt | Formulation sourcée | Effet | Usage en clip | Pièges |
|---|---|---|---|---|---|
| Ralenti | slow motion, super slow motion | Runway : « slow motion » (environ 50 %), « super slow motion » (environ 10 %) [S11] | Émotion étirée [déduit] | Refrain, danse, cheveux, eau [déduit] | [déduit] Le ralenti casse la synchro labiale. À éviter sur un plan chanté |
| Accéléré | timelapse | « Time-lapse of flower blooming. » [S11] ; « The camera remains static as the flower slowly and gracefully unfurls » [S1] | Temps qui passe | Transition jour vers nuit : preset « Timelapse Landscape » [S6] | Caméra fixe obligatoire [S1] |
| Personnage immobile, foule accélérée | timelapse human | Runway : « Handheld camera: The man stands still as the crowd moves around him. » [S9] ; preset « Timelapse Human » [S6] | Solitude au milieu du monde [déduit] | Couplet mélancolique [déduit] | |
| Hyperlapse | hyperlapse, hyperspeed | Preset « Hyperlapse » [S6] ; Runway liste « hyperspeed » [S11] | Énergie, voyage | Transition, drop [déduit] | |
| Rampe de vitesse | speed ramping | Terme listé par Runway [S11] | Accent sur un geste [déduit] | Drop, geste de danse [déduit] | Aucun test publié trouvé. [déduit] Plus sûr au montage qu'au prompt |
| Bullet time | bullet time | Preset Higgsfield « Bullet Time », dont une variante Wan 2.5 [S6] ; recette action [S7] | Moment figé, caméra qui tourne | Temps fort du refrain [déduit] | Aucun test publié trouvé. Passer par le preset [déduit] |
| Obturation lente | low shutter | Preset Higgsfield « Low Shutter » [S6] | Traînées de mouvement [déduit] | Danse, club [déduit] | |
| Flou de mouvement | motion blur trails | Runway liste « motion blur trails » [S11] | Vitesse [déduit] | Danse [déduit] | Le flou fait perdre les repères du visage [S15] |

---

## 7. Syntaxes propres à chaque modèle

### Veo 3.1 (Google)
- Formule : « [Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance] » [S2].
- Plans horodatés dans une génération [S2] :
  « [00:00-00:02] Medium shot from behind a young female explorer… »
  « [00:02-00:04] Reverse shot of the explorer's freckled face… »
  « [00:04-00:06] Tracking shot following the explorer… »
  « [00:06-00:08] Wide, high-angle crane shot, revealing the lone explorer… »
- Première et dernière image : on fournit deux images et on décrit la transition. Exemple : l'arc de 180° autour de la chanteuse (fiche 4.11) [S2].
- Durées : 4, 6 ou 8 s [S2].
- Note : Google a arrêté les modèles Veo 3.1 Preview de l'API Gemini le 22 octobre 2026 [S30]. La config de Riot Machine (`config/models.yaml`) appelle les versions GA en « -001 » (veo-3.1-generate-001, veo-3.1-fast-generate-001, veo-3.1-lite-generate-001). Elle n'est donc pas touchée.

### Kling 3.0
- Jusqu'à six plans par sortie, chacun avec cadrage, sujet et mouvement [S5].
- Exemple de syntaxe : « Master Prompt: » puis « Multi shot Prompt 1: » avec « (Duration: 5 seconds) » [S5]. La page ne dit pas que la syntaxe est obligatoire.
- Exemple Kling de séquence en quatre plans : plan large fixe, push-in, tilt down, pull-back [S3].
- Kling 3.0 Omni règle par plan la durée, la grosseur, la perspective et le mouvement [S3].

### Seedance 2.0
- Formule citée : « subject + motion + environment + camera + aesthetics + audio » [S18].
- Prompt de 60 à 100 mots, l'essentiel en tête [S18].
- Référence vidéo pour copier un mouvement : « @video1 = camera movement only » ; « follow all camera movements from @video1 » [S18].
- Deuxième mouvement : « cut to » [S18]. Plan long : « Seconds 6-10: camera pushes in as the barista sets down the saucer » [S18].
- Le guide officiel ByteDance (BytePlus ModelArk, « Dreamina Seedance 2.0 series prompt guide ») existe, mais la page ne se lit qu'avec JavaScript. Je n'ai pas pu la lire.

### Hailuo / MiniMax
- Commandes entre crochets [S13] : `[Push in]`, `[Pull out]`, `[Zoom in]`, `[Zoom out]`, `[Pan left]`, `[Pan right]`, `[Tilt up]`, `[Tilt down]`, `[Truck left]`, `[Truck right]`, `[Pedestal up]`, `[Pedestal down]`, `[Tracking shot]`, `[Shake]`, `[Static shot]`.
- Virgule dans un crochet = mouvements simultanés : `[Truck left, Pan right]`. Crochets séparés = mouvements successifs : « A man picks up a book [Pedestal up], then begins reading it [Static shot]. » [S13].
- Combinaisons nommées par Hailuo [S13] : « Upward reveal » `[push in, pedestal up]` ; « Walking shot » `[truck left, tracking shot]` ; « Scenic pass » `[truck left, pedestal up]` ; « Stage shot » `[pan right, zoom in]` ; « Downward tilt » `[pedestal down, tilt up]` ; « Left circling » `[truck left, pan right, tracking shot]`.
- Grammaire issue du modèle Director. Hailuo 2.3 la comprend aussi. Le langage naturel marche sur les modèles récents [S13]. Maximum 3 mouvements combinés [S14].

### Wan (Alibaba)
- Formules officielles [S16] : « Prompt = Entity + Scene + Motion » ; image vers vidéo « Prompt = Motion + Camera movement » ; multi-plans « Prompt = Overall description + Shot number + Timestamp + Shot content ».
- Mouvements nommés : « camera pushes in », « camera pulls out », « camera moves left », « camera tilts up », « orbiting camera movement », « fixed camera », « follow-cam perspective », « drone shot », « fast fly-through », « compound camera movement » [S16].
- Le réécrivain automatique (prompt_extend) n'ajoute pas d'intention caméra [S17].

### Runway (Gen-4, Gen-4.5)
- Structures texte et image vers vidéo : voir 1.6 [S9].
- Plan en boucle : « The camera must start and end on the exact same frame to create a perfect loop. » [S9].
- Contradiction entre deux pages Runway : la page « AI video prompting guide » dit d'éviter « then » et « next » [S11]. L'Academy conseille « X occurs, then Y occurs » pour séquencer [S9].
- La page officielle « Camera Terms, Prompts, & Examples » de Gen-4.5 renvoie une erreur 403. Je ne l'ai pas lue.

### Luma (Ray)
- « Camera Motion Concepts » : mouvements appris sur quelques exemples, combinables en langage naturel [changelog Luma, cité par la recherche]. Je n'ai pas obtenu la liste des noms. La page d'aide sur les plans fixes renvoie une erreur 404.

### Higgsfield
- Liste complète des presets relevée sur la page officielle [S6] : General, Eyes In, Bullet Time, Aerial Pullback, Arc Left, Arc Right, BTS, Buckle Up, Car Chasing, Car Grip, Crane Down, Crane Over The Head, Crane Up, Crash Zoom In, Crash Zoom Out, Dolly In, Dolly Left, Dolly Out, Dolly Right, Dolly Zoom In, Dolly Zoom Out, Double Dolly, Dutch Angle, Eating Zoom, Fisheye, Flying Cam Transition, Focus Change, FPV Drone, Glam, Handheld, Head Tracking, Hero Cam, Hyperlapse, Incline, Jib down, Jib up, Lazy Susan, Low Shutter, Mouth In, Object POV, Overhead, Pan Left, Pan Right, Rapid Zoom In, Rapid Zoom Out, Road Rush, Robo Arm, Snorricam, Static, Super Dolly In, Super Dolly Out, Through Object In, Through Object Out, Tilt Down, Tilt up, Timelapse Glam, Timelapse Human, Timelapse Landscape, Whip Pan, Wiggle, YoYo Zoom, 360 Orbit, Zoom In, Zoom Out, 3D Rotation.
- Rattachement aux modèles, déduit des dossiers d'images de la page [S6] : Wan 2.5 (Eyes In, Pan, Dolly, Car Grip, Handheld, Mouth In, Through Object, Bullet Time, Static) ; Kling (Aerial Pullback, Flying Cam Transition) ; Hailuo (Timelapse, Rapid Zoom, Hero Cam, Jib, Eating Zoom, BTS, Road Rush, Through Object). Les autres ne disent pas leur modèle.

---

## 8. Combinaisons utiles en clip

### 8.1 Par partie du morceau

| Partie | Mouvement conseillé | Formulation sourcée | Source |
|---|---|---|---|
| Intro | Plan d'installation, pull-back ou crane | « Camera pulls back slowly… to reveal… » ; recette Higgsfield « Establish space » | [S22] [S7] |
| Couplet | Mouvement intime et régulier | « Very slow lateral camera slide, shallow depth of field » ; « Handheld camera moves between the musician and band silhouettes » ; « Camera travels straight forward without rotation. » | [S19] |
| Pré-refrain | Push-in lent qui monte la tension | « Slow dolly in toward the subject's face » | [S22] ; placement [déduit] |
| Refrain | Orbite ou pull-back | « Slow circular orbit during the first half of the chorus » ; « pull rapidly backward into a wide skyline reveal » ; « Slowly pull back from an eye close-up to a waist-up shot. » | [S19] |
| Drop, crescendo | Le plus gros mouvement au sommet | « the camera swings into a faster orbit » ; « When the strings swell, slowly orbit one quarter around the person » ; whip pan, FPV | [S19] [S22] |
| Pont | Révélation lente ou changement tardif | « Wide rear three-quarter shot slowly circles toward profile » | [S19] |
| Dernier refrain, fin | Crane up | « Camera cranes up and away from the subject standing on a rooftop at golden hour » | [S22] |
| Danse | Orbite 360, dolly sur le temps, plongée totale, crash zoom | « 360 Orbit, Dolly In/Out on beat, Overhead, Crash Zoom In » | [S7] [tiers] |
| Plan chanté | Plan fixe ou push-in très lent, face ou trois-quarts | « Medium front shot, she sings directly into camera. » | [S27] ; mouvement [déduit] |
| Insert | Très gros plan ou macro, caméra fixe ou rack focus | « locked-off camera » + « macro close-up » | [S17] |
| Transition | Whip pan, traversée d'objet, arc entre première et dernière image | « Rapid whip pan from the drummer to the lead singer » ; arc 180° Veo | [S22] [S2] |

La recette Higgsfield conseille Hailuo 2.3 et Kling 2.6 pour la danse et le clip, avec le style « Cinematic » ou « Anamorphic » [S7] [tiers].

### 8.2 Combinaisons qui marchent

| Combinaison | Formulation | Effet | Source |
|---|---|---|---|
| Push-in + faible profondeur de champ en gros plan | « Slow dolly in toward the subject's face », « background gently compressing, shallow depth of field » | Tension intime | [S22] |
| Rapproché poitrine + légère contre-plongée + push-in | « medium close-up, slight low angle, slow push in » | Plan chanté qui gagne en force | [S17] |
| Contre-plongée + tracking arrière | « Low-angle camera tracks backward from knee height. » | Rap, assurance | [S19] |
| Profil serré + épaule douce | « Tight profile close-up, gentle handheld movement » | Couplet intime, visage stable | [S19] |
| Push-in + pedestal up | `[push in, pedestal up]` (« Upward reveal ») | Révélation montante | [S13] |
| Truck + pan inverse | `[Truck left, Pan right]` | Tourne autour du sujet | [S13] |
| Pan + zoom | `[pan right, zoom in]` (« Stage shot ») | Plan de scène | [S13] |
| Arc + crash zoom sur les yeux | Exemple Runway image vers vidéo | Temps fort | [S9] |
| Arc 180° entre deux images | Exemple Veo première et dernière image | Passage de la face à la vue de dos sur scène | [S2] |
| Rack focus premier plan vers visage | « rack focus from the coffee cup in the foreground to the woman's face in the background » | Révélation douce | [S21] |
| Fixe + foule accélérée | « Handheld camera: The man stands still as the crowd moves around him. » | Solitude | [S9] |
| Tracking + crash zoom | Blog tiers lié à Higgsfield cité par la recherche : « layer tracking with crash zoom to escalate » | Escalade | [tiers] |

### 8.3 Combinaisons à éviter

| Combinaison | Pourquoi | Source |
|---|---|---|
| Fixe + orbite | Jitter, dérive, compromis | [S18] |
| Fixe + push-in rapide + orbite | Contradiction | [S3] |
| Pan + tilt en même temps | Plus dur à exécuter | [S4] |
| Orbite + zoom + crane | Le modèle en choisit un ou les mélange en dérive | [S10] |
| Crane pendant que le sujet bouge (Veo) | Baisse de qualité | [S21] |
| Push-in + sujet qui tourne, marche et change d'expression | Instabilité | [S3] |
| `[Shake]` ou mouvement rapide en gros plan | Visage déformé | [S13] |
| Whip pan + macro zoom | Embrouille le modèle | [tiers] |
| Handheld + fixe + dolly zoom | Contradiction | [S22] |
| Réglage caméra + autre mouvement écrit dans le texte | Double direction, artefacts | [S10] |

---

## 9. Choisir selon l'effet recherché

| Effet voulu | Plans et mouvements | Source |
|---|---|---|
| Puissance | Contre-plongée, contre-plongée totale, crane up, Hero Cam | [S4] [S10] [S22] [S6] |
| Intimité | Push-in lent, gros plan, faible profondeur de champ, profil serré | [S3] [S10] [S19] |
| Tension | Push-in lent, plan fixe symétrique, dutch angle, contre-plongée totale | [S22] [S10] |
| Révélation | Pull-back, crane up, tilt, pan « to reveal », rack focus, pedestal up | [S1] [S3] [S10] |
| Énergie | Whip pan, crash zoom, FPV, orbite rapide, handheld | [S22] [S19] [S10] |
| Isolement | Dolly out, plongée, plan de grand ensemble, espace vide | [S1] [S10] |
| Vertige, malaise | Dolly zoom, dutch angle, Snorricam | [S1] [S10] [tiers] |
| Immersion | POV, FPV, tracking | [S10] [S22] |
| Héroïsation | Orbite, arc, contre-plongée | [S23] [S22] |
| Rêve, souvenir | Soft focus, ralenti | [S10] ; ralenti [déduit] |
| Réalisme brut | Handheld, focale 35 mm | [S10] [S22] |

---

## 10. Ce que je n'ai pas pu vérifier

- **Tao Prompts** : j'ai lu la description et les chapitres de la vidéo M7p7HrJjcdA (« How to Make a Professional Music Video with AI (Full Guide) », 6 juillet 2026) et de « The ONLY 7 Prompts You Need to Create Any AI Video ». La transcription était inaccessible. Son guide sur la caméra dans Kling est payant (Gumroad, 10 $).
- **Dan Kieft, Andy Lo, Theoretically Media** : aucun contenu exploitable trouvé. Pour Dan Kieft, seul un résumé tiers liste ses thèmes (statique, pan, tilt, zoom, dolly, truck, pedestal, slider, tracking, handheld, drone, crane, tilt-shift, zoom infini, timelapse).
- **Curious Refuge** : seul le comparatif Kling contre Veo est public. Le cours est payant.
- **Pages officielles non lues** : Runway « Camera Terms, Prompts, & Examples » (403), guide Seedance 2.0 de BytePlus (JavaScript), guide caméra Luma (404).
- **Taux de réussite chiffrés** : ils viennent de PicassoIA [S21], un blog d'éditeur. Ce ne sont pas des mesures indépendantes.
- **Ralenti, rampe de vitesse, bullet time** : aucun test publié par modèle.

---

## 11. Sources

| N° | URL | Ce qu'elle apporte |
|---|---|---|
| S1 | https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide | Guide officiel Vertex AI pour Veo : définitions et exemples mot pour mot des grosseurs, angles, mouvements, optiques ; caméra fixe ; prompt négatif |
| S2 | https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1 | Guide officiel Google Veo 3.1 : formule, vocabulaire, crane, timestamps, première et dernière image (arc 180° autour d'une chanteuse), durées 4/6/8 s |
| S3 | https://kling.ai/blog/kling-ai-camera-control-video-guide | Blog officiel Kling (Kling 3.0 et Omni) : push, pull, pan, tilt, track, orbit ; pièges ; un mouvement par plan |
| S4 | https://kling.ai/blog/ai-camera-control-movement-prompts-guide | Blog officiel Kling : angles et émotions, vitesses et durées, pan et tilt combinés plus durs |
| S5 | https://blog.fal.ai/kling-3-0-prompting-guide/ | Guide fal.ai Kling 3.0 : multi-plans jusqu'à six, syntaxe, image vers vidéo |
| S6 | https://higgsfield.ai/camera-controls | Page officielle Higgsfield : liste complète des noms de presets, quelques descriptions, modèles déduits des images |
| S7 | https://raw.githubusercontent.com/OSideMedia/higgsfield-ai-prompt-skill/main/skills/higgsfield-recipes/SKILL.md | Fiche tierce : recettes Higgsfield par genre, dont clip et danse [tiers] |
| S8 | https://higgsfield.ai/blog/how-to-avoid-distortions-ai-videos | Blog Higgsfield : causes caméra des déformations, une variable à la fois |
| S9 | https://academy.runwayml.com/prompt-guide | Runway Academy : structures de prompt, caméra fixe, plan continu, boucle, exemples mot pour mot |
| S10 | https://runway.com/resources/ai-camera-prompts | Runway : glossaire caméra complet avec effets, plan fixe, steadicam et gimbal, rack focus, pièges |
| S11 | https://runway.com/resources/ai-video-prompting-guide | Runway : formule, termes de vitesse (slow motion 50 %, super slow motion 10 %, speed ramping), FPV, SnorriCam |
| S12 | https://runware.ai/docs/models/runway-gen-4-5/guides/directing-motion.md | Runware sur Gen-4.5 : termes fiables, mots de vitesse, séparer caméra et sujet, image vers vidéo |
| S13 | https://hailuoai.video/pages/blog/camera-movement-prompt-cheatsheet | Hailuo : commandes entre crochets, règles de combinaison, combinaisons nommées, pièges sur les visages |
| S14 | https://replicate.com/minimax/video-01-director | Replicate, MiniMax Director : crochets, maximum trois mouvements, liste |
| S15 | https://hailuoai.video/pages/blog/fix-distorted-faces-ai-video | Hailuo : angles et lumière qui protègent les visages |
| S16 | https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt | Guide officiel Alibaba pour Wan : vocabulaire, formules, caméra fixe, multi-plans |
| S17 | https://blog.segmind.com/wan-3-prompt-guide-alibabas-official-formulas-tested/ | Segmind : tests des formules Wan, coupes inventées sans direction caméra, plan fixe tenu 5 s |
| S18 | https://www.heyuan110.com/posts/ai/2026-07-11-seedance-2-prompt-guide/ | Seedance 2.0 : un mouvement par clip, état final, référence @video, modes d'échec |
| S19 | https://lumalabs.ai/news/ai-music-video-prompts | Luma : mouvements par partie du morceau (couplet, refrain, drop, pont), visages en gros plan |
| S20 | https://curiousrefuge.com/blog/kling-vs-veo | Curious Refuge : cinq tests caméra Kling 3.0 contre Veo 3.1 avec les prompts |
| S21 | https://blog.picassoia.com/veo-3-1-cinematic-camera-control-put-to-the-test | PicassoIA : taux de réussite par mouvement sur Veo 3.1, phrase anti-zoom, angles chiffrés [tiers] |
| S22 | https://www.atlabs.ai/blog/ultimate-prompt-guide-best-camera-movement-prompts-for-ai-videos-2026 | Atlabs : 8 mouvements avec prompt, émotion, usage clip ; 9:16 ; modèles forts [tiers] |
| S23 | https://www.kapwing.com/resources/the-complete-ai-camera-prompt-guide-77-shots-and-movements/ | Kapwing : effets de l'orbite et du tracking, formulation anti-zoom, contre-plongée décrite [tiers] |
| S24 | https://dreamina.capcut.com/ai-video/text-to-video-camera-prompts-fix-unwanted-motion | Dreamina : caméra fixe, dérive, causes d'échec [tiers] |
| S25 | https://sagnikbhattacharya.com/blog/seedance-vs-kling | Seedance contre Kling : précision et amplitude des mouvements [tiers] |
| S26 | https://blog.segmind.com/kling-vs-seedance-ai-video-comparison/ | Segmind : Seedance réagit aux mots d'angle, Kling aux mots de vitesse [tiers] |
| S27 | https://www.youtube.com/watch?v=M7p7HrJjcdA | Tao Prompts, description de la vidéo : 20 cadrages de clip chanté mot pour mot |
| S28 | https://www.youtube.com/watch?v=zzBmvzR-URg | Tao Prompts, « The ONLY 7 Prompts » : chapitres (cinematic, timestamp, cutscene, anchor, negative) |
| S29 | https://www.cinemaparlant.com/fichesactivites/ft_lexiquefrancaisanglais.pdf | Lexique cinéma français-anglais : échelle des plans, mouvements, plongée, contre-plongée |
| S30 | https://ai.google.dev/gemini-api/docs/video | Google : arrêt de Veo 3.1 Preview le 22 octobre 2026 sur l'API Gemini ; Gemini Omni Flash conseillé |
| S31 | https://docs.byteplus.com/docs/ModelArk/1587797 | BytePlus Seedance 1.0 : mouvements reconnus (extrait de recherche seulement) |
| S32 | https://lumalabs.ai/changelog/camera-motion-concepts-launch | Luma : lancement des Camera Motion Concepts (via résultat de recherche) |
| S33 | https://cdn.jsdelivr.net/npm/ai-creator-toolkit@1.4.0/skills/director/knowledge/camera-movements.md | Fichier communautaire : vitesse lente plus stable, combinaisons risquées, notes par modèle parfois datées [tiers] |
