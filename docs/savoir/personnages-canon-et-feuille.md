# Personnages : canon, feuille, expressions, langue des prompts

Comment faire l'image de référence et la feuille de personnage qui donnent la reproduction la plus fiable en vidéo, quand faire des expressions, et en quelle langue prompter. Recherche du 1er novembre 2026.

Pour Riot Machine. Arrêtée au 1er novembre 2026.

## Comment lire ce document

Chaque recommandation porte une étiquette de source :

- **[OFFICIEL]** : documentation de l'éditeur du modèle (Google, ByteDance/BytePlus, Kuaishou/Kling, Black Forest Labs, Runway, Higgsfield).
- **[CRÉATEUR]** : créateur reconnu qui publie sa méthode et ses prompts (Dan Kieft, Tao Prompts, AI Video School).
- **[AVIS]** : blog, revendeur, fil Reddit. Indice seulement.
- **[SYNTHÈSE]** : ma déduction à partir des sources. Pas testée.

Les prompts cités sont recopiés mot pour mot. Une seule retouche : les tirets cadratins des originaux sont remplacés par un tiret simple « - ». Les coupes sont signalées par `[...]`.

Accès aux sources :

- Dan Kieft : la description YouTube, la transcription automatique complète et la page de prompts (dankieft.com/aimusicvideo redirige vers suno-seedance-music-video.vercel.app) sont accessibles.
- Tao Prompts : la description (avec le prompt de la planche) et la transcription automatique complète sont accessibles.
- Andy Lo : la vidéo `PeelSIEewUY` traite d'automatisation n8n (« How I Used $0 to Create 1000+ Videos on Autopilot », mars 2025). Elle ne parle pas de personnages. Je n'en tire rien. Je n'ai pas trouvé d'autre vidéo d'Andy Lo sur la cohérence.
- Guide officiel Seedance 2.0 et 2.5 (BytePlus) : accessible après rendu JavaScript. C'est la source la plus précise de toute la recherche.
- Aide Runway « Creating with Gen-4 References » : refusée (403). J'ai utilisé l'article Runway « How to use character references in AI ».

---

## 1. La canon : le portrait de référence

### Ce que disent les sources

**[OFFICIEL] Seedance 2.0 (BytePlus, mis à jour le 28/09/2026).** C'est la consigne la plus nette. Elle vient de la FAQ « Inaccurate face reference ». Cause de la dérive d'identité : une image unique qui mélange visage, corps, tenue et détails, ou un visage trop petit dans l'image. Remède, cité mot pour mot :

> Prepare a close-up face image: In addition to the original full-body photo, prepare an extra close-up face image containing only the character's head (headshot, retaining only the face; no expression is best; minimize interfering elements such as shoulders, neck, and background).

> For character references, using a headshot + full-body photo is sufficient.

**[OFFICIEL] Runway, article « How to use character references in AI » (Julia Martins, 19/12/2025).**

- « High resolution - at least 1024px on the shortest side »
- « Sharp focus on the face with clear details »
- « Even lighting that shows features without harsh shadows »
- « Simple or neutral background that doesn't compete for attention »
- « Front-facing or 3/4 angle captures features most effectively »
- À éviter : angles extrêmes, mains, cheveux ou objets devant le visage, autre personne dans le cadre, filtres lourds, photo sous-exposée.
- « a single high-quality reference image works well for most projects. »

**[OFFICIEL] Kling, Element Library :** « We recommend uploading a front-facing image for higher consistency. » La photo de face est l'image principale de l'élément.

**[OFFICIEL] Kling, blog Subject Binding (26/06/2026) :** « Even lighting and clear facial geometry are essential for the best results. »

**[OFFICIEL] Higgsfield, aide Seedance :** « Upload a sharp, front-facing, well-lit reference image and add a short prompt describing the action and camera move. »

**[OFFICIEL] Veo (API Gemini et Vertex) :** jusqu'à trois images d'une seule personne, d'un seul personnage ou d'un seul produit (« asset »). Vertex précise que `veo-3.1-generate-001` ne rend que des vidéos de 8 s avec des images de sujet. Guide de prompt Gemini API : « Enhance the facial details: Specify facial details as a focus of the photo like using the word portrait in the prompt. »

**[CRÉATEUR] Dan Kieft (vidéo du 05/10/2026, Suno v6 et Seedance 2.5 sur Higgsfield).** Sa méthode tient en trois étapes : « First, we're going to be creating the face. Second, we're going to be creating the outfits. And then third, we're going to be creating the character sheets. » Le visage se fait seul, sans tenue ni décor. Son « Universal Prompt Director » est une consigne à coller dans ChatGPT ou Claude. Le LLM écrit ensuite le prompt de visage. Les règles de la « face lock » :

```text
FACE LOCK SETUP (new character, identity-only stage - no outfit styling, no environment):
- Backdrop: mid-gray seamless studio (locked default; pure white only if explicitly requested) - even neutral mid-gray, no seam line, no gradient, no falloff to black/white
- Wardrobe: plain black camisole (women) / plain black ribbed tank (men) - nothing else, no styling
- Lighting: one broad diffused source from camera-left or camera-right, slightly above; soft triangle of light on the shadow cheek; gentle wrap on the face; no hard shadow edges, no rim light, no hair light, no kicker
- Skin: matte and velvety, zero shine on forehead/nose bridge/cheekbones/temples/chin, no oily T-zone, low-contrast milky look; warmth preserved and natural - never pale, washed-out, or cool-shifted
- Camera: 50mm prime, wide aperture, natural round bokeh, even sharpness, soft natural film grain
- Close every prompt with: "Photographed not generated."

CHARACTER DESCRIPTION RULES:
- Describe: bone structure, eye shape/color, brow shape, nose, lip shape, skin tone/finish, hair (color nuance, length, texture, style), body build/proportions/posture, default expression, identity markers (piercings, scars, beauty marks, tattoos)
- No teeth-showing smile unless explicitly requested - default is neutral, subtle, closed-lip
```

Source : https://suno-seedance-music-video.vercel.app/ (section « Universal Prompt Director »). Le même bloc donne aussi des règles de sortie : pas de nom réel, pas de marque, pas de bloc négatif, pas de format d'image dans le texte (« chest-up portrait » plutôt que « 3:4 »).

Analyse du prompt :

- Il isole l'identité : fond gris neutre, débardeur noir uni, aucun décor. La tenue arrive à l'étape suivante.
- La lumière du visage a un léger modelé (triangle de lumière sur la joue). La planche, à l'étape 3, repasse en lumière totalement plate (voir section 2). La canon sert à juger le visage. La planche sert à transmettre l'information.
- La bouche est fermée et l'expression neutre. Il ne veut pas de sourire avec les dents.
- Le grain de film et la mention « Photographed not generated » visent le réalisme de la peau. Ils ne servent pas la cohérence.

**[CRÉATEUR] Tao Prompts (06/07/2026) :** « When I generate the character reference image, I like to create it in 4K resolution so I can get the highest quality AI characters possible. »

**[CRÉATEUR] Dan Kieft, sur le choix du modèle d'image :** « what image model should I use? Well, the answer to that is it doesn't really matter. The only thing that matters is your taste. » Il génère le même prompt sur trois modèles et garde le meilleur.

### Recommandations pour Riot Machine

1. **Deux images de vérité, pas une.** [OFFICIEL Seedance, CRÉATEUR Kieft] La canon est un **gros plan de tête** : visage seul, face caméra, regard objectif, bouche fermée, expression neutre. Une **pleine pied de face** dans la tenue de référence l'accompagne. Les deux partent ensemble dans chaque génération.
2. **Cadrage.** [OFFICIEL Seedance, Runway] Pour Seedance, la tête seule (« retaining only the face »). Chez Kieft, le cadrage va du sommet du crâne aux clavicules. Je retiens : du haut du crâne aux clavicules, le visage remplit le cadre, sans mains. [SYNTHÈSE]
3. **Fond.** [CRÉATEUR Kieft, OFFICIEL Runway] Gris moyen uni, sans dégradé ni vignettage. Le blanc est acceptable : Google l'utilise pour le chien de son exemple.
4. **Lumière.** [OFFICIEL Runway et Kling, CRÉATEUR Kieft] Douce, régulière, sans ombre dure, sans contre-jour, sans gélatine colorée. Pas d'ambiance : l'ambiance appartient au plan, pas à la canon.
5. **Expression.** [OFFICIEL Seedance : « no expression is best »] Neutre, bouche fermée.
6. **Vêtements.** [CRÉATEUR Kieft] Sur la tête seule : un haut neutre (débardeur noir uni) ou l'encolure de la tenue de référence. La tenue complète se montre dans la pleine pied. Pas de logo, pas d'accessoire tenu à la main.
7. **Cheveux.** [OFFICIEL Runway] Rien devant le visage. La coiffure de la canon devient la coiffure de référence. Une autre coiffure demande une nouvelle version du personnage.
8. **Résolution.** [OFFICIEL Runway : au moins 1024 px sur le petit côté ; Seedance 2.5 accepte jusqu'à 4K ; CRÉATEUR Tao : 4K] Produire la canon en 2K ou 4K et la garder ainsi. Le système envoie à chaque modèle la taille qu'il accepte. Rappel du PROCESS (22/10/2026) : jamais d'agrandissement avec retouche du visage.
9. **À éviter.** [OFFICIEL Runway, Seedance] Lunettes de soleil, chapeau, mains près du visage, maquillage extrême qui masque les traits, filtres, image mixte (visage, tenue et détails dans une seule image), visage trop petit.
10. **Ressemblance avec une célébrité.** [OFFICIEL Seedance] La FAQ cite la dérive qui rend le personnage semblable à une célébrité, avec un blocage à la modération. Riot l'a vécu : Vertex a refusé la canon v1 de JJ le 29/10/2026 (« personnalité connue »). [SYNTHÈSE] Donner à la canon des traits propres : grain de beauté, sourcils, forme du nez. Éviter le visage générique de « pop star parfaite ». Garder plusieurs vues validées de la même version pour remplacer une image refusée.
11. **Seedance en direct chez BytePlus : visages réels refusés.** [OFFICIEL BytePlus, guide « Create portrait videos », 08/10/2026] Seedance 2.0 et 2.5 n'acceptent pas les références contenant de vrais visages humains. La plateforme fait seulement confiance à ses propres sorties : vidéos Seedance, dernière image d'une vidéo Seedance et images Seedream 5.0. Il faut le même compte, des fichiers originaux non retouchés et moins de 30 jours. Une canon photoréaliste faite avec Nano Banana peut donc être bloquée chez BytePlus. Je n'ai pas vérifié la règle chez fal.ai ou Higgsfield. Dan Kieft envoie bien des visages photoréalistes à Seedance 2.5 par Higgsfield.

### Prompt type de canon

Il n'existe pas de prompt de canon publié en entier par ces créateurs. Kieft publie la consigne pour le LLM, pas le prompt final. Voici une proposition **[SYNTHÈSE]** qui applique ses règles et la consigne Seedance. Elle n'est pas testée :

```text
Tight chest-up studio portrait of [identity block from adn.md], framed from just above the crown down to the collarbones, face filling the frame, squared to camera, head level, eyes directly to camera, neutral expression, lips closed and relaxed. Plain black camisole. Hair kept off the face. Even, neutral mid-gray seamless backdrop with no gradient. One broad diffused soft light slightly above camera, gentle wrap, no hard shadows, no rim light. Matte natural skin with fine real texture. 50mm prime, sharp focus on the eyes. Photographed not generated.
```

---

## 2. La feuille de personnage (turnaround)

### Deux écoles opposées

**École « planche unique » [CRÉATEUR].** Les trois créateurs produisent une planche avec toutes les vues dans une seule image.

Dan Kieft, planche en trois panneaux, prompt à donner à un LLM avec deux images (le gros plan du visage et la pleine pied en tenue). Il insiste : « Don't just use the full body image. » Extraits du gabarit, mot pour mot :

```text
A three-panel character reference sheet composed as one horizontal frame, divided into three equal vertical panels side by side, thin clean separation between panels, the same figure and the same outfit rendered identically across all three. No text, no labels, no numbering anywhere in the image.

Identity: [Write a detailed description of the specific character from the identity references. [...]]

Wardrobe: [Describe the exact outfit in detailed flowing prose, progressing from the upper body through the lower body to footwear. [...]]

LEFT PANEL - full body front view, headless. The full figure stands squared to camera from the shoulders down to [the actual footwear, or feet if barefoot], arms relaxed at the sides, hands open and loose, weight even across both feet. There is no head and no hair - no hair falls across the chest or shoulders. The neck rises a short way from the shoulders and terminates in a clean, flat, sharply defined horizontal edge at the base of the throat, exactly like a headless dress-form mannequin [...]

CENTER PANEL - full body rear, head attached. The complete figure from above the crown down to [the actual footwear, or feet if barefoot], seen directly from behind, standing squared away from camera, weight even, arms relaxed at the sides. [...]

RIGHT PANEL - tight chest-up face lock. Framed from just above the crown down to the collarbones with the face filling the panel, squared to camera, head level, eyes directly to camera, neutral model face-card expression, lips closed and relaxed. [...]

The background is a single flat 18% neutral gray field - one uniform value at every pixel corner to corner, identical directly beside the subject and in the far corners, with no seam line, no gradient, no hotspot, no vignette, and no falloff to lighter or darker anywhere in the frame. [...]

Relight from scratch overriding any reference lighting, applied uniformly across all three panels: completely flat shadowless illumination - one enormous soft frontal source at camera position wrapping the subject evenly [...] Extremely low contrast, even, milky, catalogue-flat. Form is described by bone structure, hair strands, and fabric folds alone, not by light and shadow.

[...] Even sharpness edge to edge across the entire frame in every panel. No depth-of-field falloff, no bokeh, no background blur [...] Photographed on a 50mm prime, soft natural film grain. Photographed not generated.
```

Source : https://suno-seedance-music-video.vercel.app/ (section « Character sheet prompt »).

Analyse :

- **Un seul visage par planche.** Le corps de face est sans tête et le dos est vu de derrière. Le seul visage visible est le gros plan. Kieft n'explique pas ce choix dans la vidéo. [SYNTHÈSE] Il évite probablement que le modèle vidéo lise deux visages, donc deux personnages. Le guide Seedance décrit précisément ce défaut (voir plus bas).
- **Lumière totalement plate**, fond gris 18 % uniforme, aucune ombre portée, netteté partout. La planche transporte de l'information, pas une ambiance.
- **Aucun texte ni étiquette** dans l'image.
- **Le visage occupe tout un panneau.** Cela répond au défaut « face ratio is too small » du guide Seedance.

Il l'utilise ensuite comme une seule référence `@image1` dans Seedance 2.5, avec cette liaison explicite, mot pour mot :

```text
[REFERENCE BINDING]
@image1 = the sole character and wardrobe reference for the man. Use the close-up for his exact facial identity and the front and back views for his outfit and body proportions. These are views of the same man, not separate characters. Do not reproduce the reference sheet layout.
```

Et plus loin dans le même prompt :

```text
@image1 defines him in all eight stages. Face, skin tone, locs, hairline, facial hair, tattoo, earrings, chain and outfit must be identical from the first frame to the last - do not re-interpret his features between cuts.
```

Source : même page, section « The prompt I got back ».

Tao Prompts, planche en quatre colonnes (description de la vidéo du 06/07/2026), mot pour mot :

```text
Create a professional character reference sheet of of a young balkan woman with long, pin-straight dark hair and a middle part. Thick natural eyebrows, sharp black winged eyeliner. Wearing a sleek black western-inspired outfit featuring a fitted tank top, a fringe mini skirt with a studded belt, layered silver jewelry. Plain empty landscape in the background. Soft diffused lighting.
Arrange into four vertical columns, each representing one viewing angle. Each column contains a full-body view on top and a matching close-up portrait directly beneath it.
Columns (left → right):
Column 1: front view (full body above, front portrait below)
Column 2: left profile (fullbody character facing left) with portrait facing left below
Column 3: right profile (fullbody character facing right) with portrait facing right below
Column 4: back view, with matching portrait below.
Maintain even spacing and framing around the character portraits. Clean silhouette, consistent alignment, and clean panel separation.
Cinematic photo, muted colors, shot on 35mm film. No Text. Thin borders.
```

Source : description de https://www.youtube.com/watch?v=M7p7HrJjcdA. Il génère la planche avec GPT Image 2 sur OpenArt, en 4K. Il la donne ensuite à Seedance 2.0 avec l'image du plan : « I've also tagged the character reference shot of her to make sure the AI knows what she looks like from all the different camera angles. » Analyse : huit visages sur une planche, fond « paysage » et non neutre. C'est l'inverse des consignes Seedance 2.0 et de Kieft. Il en tire pourtant un clip montrable. Le résultat dépend donc du modèle et du nombre de personnages.

AI Video School (Mike, vidéo du 23/01/2026, 276 000 vues), planche 4 + 3, mot pour mot :

```text
Create a professional character reference sheet based strictly on the uploaded reference image. Use a clean, neutral plain background and present the sheet as a technical model turnaround while matching the exact visual style of the reference (same realism level, rendering approach, texture, color treatment, and overall aesthetic). Arrange the composition into two horizontal rows. Top row: four full-body standing views placed side-by-side in this order: front view, left profile view (facing left), right profile view (facing right), back view. Bottom row: three highly detailed close-up portraits aligned beneath the full-body row in this order: front portrait, left profile portrait (facing left), right profile portrait (facing right). Maintain perfect identity consistency across every panel. Keep the subject in a relaxed A-pose and with consistent scale and alignment between views, accurate anatomy, and clear silhouette; ensure even spacing and clean panel separation, with uniform framing and consistent head height across the full-body lineup and consistent facial scale across the portraits. Lighting should be consistent across all panels (same direction, intensity, and softness), with natural, controlled shadows that preserve detail without dramatic mood shifts. Output a crisp, print-ready reference sheet look, sharp details.
```

Et pour changer de tenue sans casser la planche :

```text
Keep the same character sheet layout. Keep their physical characteristics and expression the same. Change the outfit to [outfit description or reference to image].
```

Source : description de https://www.youtube.com/watch?v=f4HcdR3cd4M (Nano Banana dans Google Flow, puis Veo et Kling).

**École « images séparées » [OFFICIEL].** Les éditeurs vidéo demandent des images distinctes.

- **Seedance 2.0 (BytePlus).** Le guide déconseille la planche, mot pour mot : « Using multi-view character images is not recommended. Multi-view assets contain different angles of the same character, and the model may easily identify them as multiple different subjects, which instead worsens the ID drift issue. » Dans la FAQ « Duplicated characters », il ajoute : « For character reference images, prioritize independent single-person photos. Three-view or multi-view assets are not recommended. »
- **Seedance 2.5 (BytePlus, 16/10/2026).** Le guide change de position : « Seedance 2.0 does not recommend using multi-view images as subject references, while Seedance 2.5 supports them. » Il met une limite : « For 1-5 subjects, both single-view and multi-view inputs are supported. For more than 5 subjects, single-view inputs are generally more stable. If multiple viewpoints are needed, it is recommended to split them into separate images from different views, rather than using one image that contains multiple viewpoints. »
- **Kling (Element Library).** Un élément contient 1 image principale et 1 à 3 images supplémentaires, soit 4 au plus. « The main reference image serves as the primary source for the element. » Les images supplémentaires montrent d'autres angles ou des détails. Le blog Subject Binding liste : « Up to 4 Images (Front, Side, Back, Detail) ». Une vidéo de 3 à 8 s d'un seul personnage peut aussi créer l'élément.
- **Veo 3.1.** Jusqu'à 3 images « asset » d'un seul sujet. Rien n'est dit sur les planches.
- **Nano Banana (doc Gemini API), section « Character consistency: 360 view ».** La méthode officielle est itérative, une vue par génération : « You can generate 360-degree views of a character by iteratively prompting for different angles. For best results, include previously generated images in subsequent prompts to maintain consistency. »

```text
Template
A studio portrait of [person] against [background], [looking forward/in profile looking right/etc.]

Prompt
A studio portrait of this man against white, in profile looking right
```

Source : https://ai.google.dev/gemini-api/docs/image-generation

**[AVIS] Reddit (r/VEO3, mai 2026).** Un utilisateur rapporte que « sometimes when I use the sheets it'll generate two characters where there should be one ». Il est passé à l'élément lié de Kling 3 avec quatre images séparées. C'est un témoignage isolé, mais il confirme le défaut que décrit le guide Seedance 2.0.

### Recommandation : fabriquer en planche, ranger en images séparées

1. **Générer les vues dans une même passe.** [CRÉATEUR, SYNTHÈSE] La planche unique aide le modèle d'image à garder les mêmes proportions et la même tenue d'une vue à l'autre. On la génère en Nano Banana à partir de la canon et de la pleine pied, comme le fait Kieft.
2. **Puis découper ou régénérer chaque vue en image propre.** [AVIS, SYNTHÈSE] Un guide signale que recadrer un panneau fait perdre de la résolution. Mieux vaut régénérer chaque vue en pleine résolution avec la planche en référence. La méthode 360 de Google (une vue par génération, avec les vues déjà faites en référence) donne directement des images séparées.
3. **Le pack type par personnage :**
   - canon (tête, face) ;
   - pleine pied de face (tenue de référence) ;
   - trois-quarts, en buste et en pied ;
   - profil ;
   - dos (coiffure et dos de la tenue) ;
   - la planche elle-même, gardée pour Seedance 2.5 et les modèles qui la gèrent bien.
4. **Fond et lumière.** Gris neutre uniforme, lumière plate, aucune ombre portée [CRÉATEUR Kieft]. Pose neutre : bras le long du corps ou A-pose [CRÉATEUR AI Video School].
5. **Étiquetage.** Aucun texte dans l'image : Kieft, Tao (« No Text ») et Seedance 2.5 pour les storyboards (« Avoid adding text directly on the storyboard »). On étiquette par le nom de fichier et dans le prompt.
6. **Pas d'accessoire tenu à la main dans la planche.** [AVIS] Les objets tenus dérivent d'un angle à l'autre. Un objet clé reçoit sa propre fiche, comme dans l'onglet Décors.

### Quelle référence envoyer à quel modèle

| Modèle | Références à envoyer | Ordre et liaison | Source |
|---|---|---|---|
| Nano Banana 2 / Pro (image du plan) | canon + pleine pied + vue proche de l'angle du plan + décor | Donner un rôle à chaque image : « Use Image A for the character's pose, Image B for the art style, and Image C for the background environment. » Jusqu'à 4 personnages (NB 2 / 3.1 Flash) ou 5 (NB Pro). | OFFICIEL Google (blog « 7 tips » et doc API) |
| FLUX.2 (image du plan) | canon + pleine pied + décor | « When using multiple input images, clearly describe the role of each: subject from image 1, style from image 2, background from image 3. » 8 références au plus à 1 MP de sortie, 7 à 2 MP. Le texte compte plus en début de prompt. Pas de prompt négatif. | OFFICIEL BFL |
| Veo 3.1 (Vertex), référence vers vidéo | 3 images « asset » au plus : canon + pleine pied + décor. Ou canon + pleine pied + trois-quarts si le décor vient du prompt. | Pas de règle d'ordre publiée. Nommer les rôles dans le prompt (« Using the provided images for the detective, the woman, and the office setting »). Sortie de 8 s. | OFFICIEL Google |
| Veo 3.1, image vers vidéo | l'image du plan (première image) | « Veo uses the input image as the initial frame. » La première image porte toute l'identité. | OFFICIEL Google |
| Kling 3.0 / Omni | Élément : image principale = canon de face ; supplémentaires = trois-quarts, profil, dos | Appel par `[@Nom]`. L'image principale passe en premier. | OFFICIEL Kling |
| Seedance 2.0 | canon (tête) + pleine pied, pas de planche | « Place important assets first ». Lier chaque personnage à son image. 4 à 5 références en tout. | OFFICIEL BytePlus |
| Seedance 2.5 | canon + pleine pied, ou la planche (1 à 5 sujets) | Même liaison. Ajouter « Do not reproduce the reference sheet layout ». | OFFICIEL BytePlus, CRÉATEUR Kieft |

Le guide Seedance 2.0 recommande ce dosage : « Recommended configuration (4-5 assets in total): 1-2 character images (facial close-up / full body) + 1 scene image + 1 camera movement video + 1 audio clip. » Il prévient : « It is not recommended to use the full asset limit. »

**[CRÉATEUR] AI Video School**, dans sa vidéo : envoyer la planche en ingrédient même quand une première image existe déjà. Même pratique chez Tao Prompts : image du plan et planche ensemble dans Seedance 2.0.

### Prompts types de liaison (officiels)

Seedance 2.0, liaison d'un sujet (BytePlus, mot pour mot) :

```text
Define the woman wearing a red dress and a straw hat in Image 1 as Subject 1
```

```text
<Subject 1> facial features reference image 1 (headshot), makeup and styling reference image 2 (full-body photo).
```

Seedance 2.0, contrainte contre les jumeaux (à la fin du prompt, mot pour mot) :

```text
Throughout the video, characters with completely identical appearance, clothing, and accessories are prohibited. Do not generate duplicate avatars or a twin effect. Keep only a single corresponding character in the same frame, and do not reproduce repeated copies of characters.
```

Le guide ajoute : « Currently, it is not possible to directly avoid the twin problem 100%. »

Seedance 2.0, gabarit de référence multi-angle (mot pour mot) :

```text
Refer to/Extract/Combine/Use the [Subject] from [Image N] to generate [Scene Description], maintaining consistent [Subject] features.
```

Veo 3.1, ingrédients (Google Cloud, « The ultimate prompting guide for Veo 3.1 », 15/10/2025, mot pour mot) :

```text
Using the provided images for the detective, the woman, and the office setting, create a medium shot of the detective behind his desk. He looks up at the woman and says in a weary voice, "Of all the offices in this town, you had to walk into mine."
```

Kling, élément (Element Library, mot pour mot) :

```text
[@Shirt Boy] walks down the hillside and sits by the pole in [@Image].
```

**[CRÉATEUR] Tao Prompts, sur l'angle de caméra :** même avec la planche, il faut décrire l'angle dans le prompt. « Even though all of this information is already included in the reference image, you still need to give the AI video a description of how the shot looks. » Sans cela, le modèle choisit son propre angle.

---

## 3. Les portraits d'expression

### Ce que disent les sources

- Aucune doc officielle ne demande de feuille d'expressions pour l'image vers vidéo.
- **[OFFICIEL Seedance 2.0]** La référence de visage doit être neutre : « no expression is best ».
- **[OFFICIEL Seedance 2.5]** Les mots d'émotion forts créent des artefacts : « Replace intense emotional language such as "fanatical" or "extremely shocked" with more neutral wording such as "amazed" to reduce the probability of glowing eyes. »
- **[OFFICIEL Google, Nano Banana]** L'expression se change par une retouche : « Keep everything the same, but change the character's expression to be more serious. » Google prévient : « While usually reliable, character consistency across edits may vary. »
- **[OFFICIEL Kling]** Un élément peut se créer depuis une vidéo de 3 à 8 s. Le blog dit qu'elle capte « motion and facial dynamics ».
- **[OFFICIEL Veo]** En image vers vidéo, l'image est la première image du plan.
- **[CRÉATEUR Kieft, Tao]** Aucun des deux ne fait de feuille d'expressions. L'émotion vient du jeu généré par le modèle vidéo. Tao ajoute une phrase d'action au prompt (« She gestures with her hands ») et met les paroles du segment dans le prompt pour la synchro labiale.
- **[AVIS]** Je n'ai trouvé aucun test qui compare un plan avec ou sans feuille d'expressions.

### Recommandations

1. **Ne jamais utiliser un portrait d'expression comme référence d'identité.** [OFFICIEL Seedance] La référence d'identité reste la canon neutre. Une expression forte en référence risque d'imprimer cette émotion sur tout le plan. [SYNTHÈSE]
2. **Usage utile n°1 : la première image d'un plan.** [OFFICIEL Veo, SYNTHÈSE] Quand un plan commence sur une émotion précise (un cri, un rire, des larmes), on génère l'image de départ avec cette expression. Le modèle vidéo part de là. C'est un visuel de plan fait sur mesure, pas un élément du pack.
3. **Usage utile n°2 : tester la canon.** [SYNTHÈSE] Trois ou quatre expressions générées depuis la canon montrent si l'identité tient quand le visage bouge. Si JJ ne se reconnaît plus en riant, la canon est fragile. Le dossier `expressions` du pack peut garder ce rôle de contrôle.
4. **Usage utile n°3 : un trait de jeu propre au personnage.** [SYNTHÈSE] Un sourire asymétrique ou le jeu bouche ouverte d'Alister. Une image le montre mieux qu'un texte quand le modèle le rate.
5. **Inutile :**
   - en plan de chant avec synchro labiale, quand le modèle génère le jeu à partir de l'audio et des paroles (méthode Tao) ;
   - comme référence supplémentaire ajoutée « au cas où » : chaque image en plus dilue les priorités (Seedance : « It is not recommended to use the full asset limit ») ;
   - en série complète de huit émotions générée d'avance pour chaque personnage. Le coût est réel et l'usage incertain. [SYNTHÈSE]

---

## 4. Prompter en anglais ou en français

### Ce que disent les docs

| Modèle | Position officielle | Source |
|---|---|---|
| Veo 3.1 | « English (EN) is fully supported, but other languages have not been evaluated, so they may work but results can vary. » | OFFICIEL doc Veo, API Gemini |
| Nano Banana (2, 2.1, Pro) | « For best performance, use the following languages: EN, ar-EG, de-DE, es-MX, fr-FR, [...] zh-CN. » Le français est dans la liste. | OFFICIEL doc Gemini API |
| FLUX.2 | « FLUX.2 understands multiple languages. Prompt in your native language for more culturally authentic results. » Un exemple en français : « Un marché alimentaire dans la campagne normande ». | OFFICIEL BFL |
| Kling 3.0 | La langue du texte du prompt n'est pas précisée. Dialogue généré : « Chinese, English, Japanese, Korean, and Spanish. » « If dialogue is entered in a language other than those listed above, the model will translate it into English. » Le français parlé est donc traduit en anglais. | OFFICIEL guide Kling 3.0 |
| Seedance 2.0 | « mixing Chinese and English should be avoided ». Un dialogue dans une autre langue doit être marqué : « says in Japanese {こんにちは} ». Les exemples sont en anglais ou en chinois. | OFFICIEL BytePlus |
| Seedance 2.5 | « native generation in more than 10 languages ». La liste n'est pas donnée dans le guide. | OFFICIEL BytePlus |
| Seedream | Non vérifié dans cette recherche. | |

**Tests publiés :** je n'ai trouvé aucun test sérieux qui compare le même prompt en français et en anglais sur ces modèles. Les comparatifs publiés travaillent tous en anglais. [AVIS]

**Pratique des créateurs :** Kieft, Tao et AI Video School écrivent tous en anglais. Kieft dicte son intention en langage naturel à un LLM (« use this voice dictation mode ») et le LLM écrit le prompt structuré.

### Recommandation pour Riot Machine

1. **Michael écrit en français.** L'intention, l'ADN, les commentaires et les retours restent en français. Il ne doit jamais écrire un prompt anglais lui-même.
2. **Le prompt envoyé aux modèles est en anglais.** La raison principale est Veo, dont seul l'anglais est évalué. L'anglais est aussi la seule langue commune à tous les modèles du studio. Un pipeline unique en anglais évite qu'un modèle comprenne moins bien qu'un autre. [OFFICIEL Veo, SYNTHÈSE]
3. **Le bloc d'identité est figé en anglais et recopié tel quel.** C'est déjà le cas avec `adn.md`. FLUX.2 le demande (« Repeat these details in every panel prompt »), Kieft aussi (« do not re-interpret his features »). Le bloc ne se traduit pas à chaque plan. Il se recopie mot pour mot. Une traduction automatique à chaque appel ferait varier les mots, donc l'identité. [SYNTHÈSE]
4. **Les paroles restent dans leur langue d'origine.** Elles s'écrivent entre guillemets (Veo) ou entre `{}` (Seedance) avec la langue indiquée. Riot génère sans son et la musique vient de Suno, donc seule la synchro labiale est concernée. Attention : Kling 3.0 traduit en anglais un dialogue généré en français.
5. **Exception possible : FLUX.2 et Nano Banana** pour un décor français (un bistrot, une rue de village). La doc FLUX.2 dit que la langue locale rend mieux les lieux locaux. À tester sur un cas avant d'en faire une règle.

---

## 5. Un animal récurrent : Alister

### Ce que disent les sources

- **[OFFICIEL Kling]** L'Element Library détecte le type de sujet, dont « Animals » (« Realistic animals, anime-style animals, CG-rendered animals »). On peut régler la voix sur « No Voice ».
- **[OFFICIEL BytePlus]** La modération des visages vise les visages humains réels : « Trust takes effect only when face moderation is triggered. For scenarios without faces, model outputs do not have trust-related issues ». Seedance 2.5 accepte les animaux comme sujets de référence.
- **[OFFICIEL Google, forum développeurs, Katie Nguyen, 30/10/2025]** C'est un cas réel avec un chien (Remy), Nano Banana puis Veo. La méthode :
  - partir d'une vraie photo du chien (« I used my original image of Remy ») ;
  - générer le sujet seul, sur fond blanc : « Subject: Remy in a specific costume and pose, against a neutral background. » ;
  - générer le décor sans le chien : « Scene: The background setting, generated without the dog, to guide the environment. » ;
  - envoyer les deux à Veo en `reference_type="asset"`.

  Prompt de référence publié, mot pour mot :

```text
Generate a photorealistic image of this dog sitting down against a white background wearing a bumble bee costume.
```

  Prompts Veo publiés, mot pour mot :

```text
A close-up cinematic zoom-in on the dog at a table in the coffee shop as it slowly lifts a white mug to its face and takes a sip. Distant chatter and coffee sounds are audible.
```

```text
The dog runs into the gym, hops on the treadmill and jumps up to press start. The dog then begins a comically fast jog while looking at the camera and panting.
```

  Source : https://discuss.google.dev/t/a-spooky-day-in-the-life-veo-reference-images-nano-banana-and-the-art-of-canine-costumes/281607

- **[AVIS]** Les blogs sur les animaux concordent sans tester :
  - partir de photos réelles ;
  - écrire un bloc d'identité fixe : race, couleurs, marques, yeux, oreilles, queue ;
  - nommer les marques précises pour éviter la dérive vers un chien générique de la race ;
  - faire une planche de vues ;
  - ne changer qu'une variable à la fois.

### Recommandations

1. **La canon d'Alister est une tête de face, plus une pleine pied de profil.** [SYNTHÈSE à partir de Seedance et Kling] Chez un chien, le profil montre la silhouette, la longueur du poil et la queue enroulée sur le dos, mieux que la face. Fond gris ou blanc neutre, lumière douce, chien debout ou assis calmement.
2. **Bouche.** [SYNTHÈSE] Fermée ou entrouverte, au repos. Le jeu « dents et grognement » de l'ADN se garde pour les premières images de plans précis. Il ne va pas dans la référence d'identité.
3. **Vues du pack :**
   - tête de face ;
   - trois-quarts ;
   - profil debout ;
   - dos (queue enroulée vue de derrière) ;
   - un gros plan de détail sur la crinière crème et le contraste avec le dos doré.

   Dans Kling : image principale = tête de face, supplémentaires = profil, trois-quarts, dos. [OFFICIEL Kling pour la structure]
4. **Si Alister s'inspire d'un vrai chien, utiliser ses vraies photos comme source.** C'est la méthode de l'exemple Google. Il n'y a pas de blocage visage chez Seedance pour un animal. [OFFICIEL Google, BytePlus]
5. **Bloc d'identité.** L'`adn.md` d'Alister est déjà bien fait : couleurs par zone, crinière, yeux, oreilles droites, queue enroulée, mention « Never change his coat color ». [SYNTHÈSE] Pour le prompt vidéo, en extraire une version courte de deux à trois traits stables. Seedance le demande pour lier un sujet : « Use 2-3 clear and stable static features ». Exemple : « the large golden-cream Eurasier with a pale cream mane and a thick tail curled over his back ».
6. **Plans avec JJ et Alister ensemble.** [OFFICIEL Seedance] Définir chaque sujet par une étiquette stable et la répéter à chaque mention : « Define [...] in Image 1 as JJ, and define [...] in Image 3 as Alister ». Ajouter la contrainte contre les jumeaux. Décrire l'échelle (le chien arrive à la hanche de JJ) : le guide Seedance 2.5 cite les erreurs de taille et de proportion entre personnages.
7. **Le poil en mouvement est le point faible attendu.** [SYNTHÈSE, non sourcé] Les poils longs perdent du volume ou changent de couleur sous une lumière forte. Contrôler chaque plan sur ce point. Préférer des plans courts. Pour Veo, envoyer la référence du chien et celle du décor séparément, comme dans l'exemple Google.

---

## Sources

### Officielles

| URL | Ce qu'elle apporte |
|---|---|
| https://docs.byteplus.com/en/docs/ModelArk/seedance-2-0-prompt-guide | Guide Seedance 2.0 (28/09/2026). Tête + pleine pied, planche multi-vues déconseillée, jumeaux, liaison des sujets, ordre des références, 4 à 5 références, règle de langue. Page en JavaScript, lue après rendu. |
| https://docs.byteplus.com/en/docs/ModelArk/seedance-2-5-prompt-guide | Guide Seedance 2.5 (16/10/2026). Multi-vues accepté pour 1 à 5 sujets, 50 références dont 30 images, plus de 10 langues, yeux brillants, contraintes d'échelle. |
| https://docs.byteplus.com/en/docs/ModelArk/seedance-portrait-asset-guide | Seedance refuse les vrais visages humains. Seules les sorties Seedance et Seedream 5.0 du même compte, de moins de 30 jours, sont acceptées. |
| https://ai.google.dev/gemini-api/docs/image-generation | Nano Banana : 14 références, 4 personnages (NB 2.1 / 3.1 Flash) ou 5 (NB Pro), méthode 360 itérative, bonnes pratiques, liste des langues avec fr-FR. |
| https://blog.google/products/gemini/prompting-tips-nano-banana-pro/ | Donner un rôle à chaque image de référence. Limite : « character consistency across edits may vary ». |
| https://ai.google.dev/gemini-api/docs/veo | Veo 3.1 : 3 images de référence d'un seul sujet, image vers vidéo, première et dernière image. Seul l'anglais est évalué. Modèles preview fermés le 22/10/2026. |
| https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/use-reference-images-to-guide-video-generation | Vertex : 1 à 3 images de sujet, `referenceType: asset`, 8 s imposés avec `veo-3.1-generate-001`. Mise à jour du 30/10/2026. |
| https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1 | Formule de prompt Veo, flux « ingredients to video » avec prompts publiés, horodatage. |
| https://blog.google/innovation-and-ai/technology/ai/veo-3-1-ingredients-to-video/ | Annonce des ingrédients (13/01/2026). Conseil de créer les ingrédients avec Nano Banana Pro. |
| https://discuss.google.dev/t/a-spooky-day-in-the-life-veo-reference-images-nano-banana-and-the-art-of-canine-costumes/281607 | Cas réel d'un chien. Sujet sur fond neutre, décor sans le chien, prompts publiés. Article d'une employée Google sur le forum officiel. |
| https://docs.bfl.ai/guides/prompting_guide_flux2 | FLUX.2 : multilingue, ordre des mots, rôles des images, 8 références à 1 MP, répétition du bloc de personnage, pas de prompt négatif. |
| https://docs.bfl.ai/guides/usecases_editing_character_consistency | FLUX.2 : cohérence par références multiples, exemples d'édition. |
| https://kling.ai/quickstart/klingai-element-library-3-user-guide | Éléments Kling : 1 image principale de face et jusqu'à 3 supplémentaires, type « Animals », syntaxe `[@Nom]`. |
| https://kling.ai/quickstart/klingai-video-3-model-user-guide | Kling 3.0 : 5 langues de dialogue, le reste traduit en anglais, multi-plans. |
| https://kling.ai/blog/kling-3-subject-binding-character-consistency | Kling (26/06/2026) : 4 images (face, profil, dos, détail), lumière régulière. |
| https://runway.com/resources/ai-character-references-tips | Runway (19/12/2025) : critères techniques d'une bonne référence (1024 px, lumière, fond, angles, obstacles). |
| https://higgsfield.ai/creator-hub/help-center/ai-models/how-do-i-use-seedance | Higgsfield : référence de face nette, éléments réutilisables entre générations. |

### Créateurs reconnus

| URL | Ce qu'elle apporte |
|---|---|
| https://www.youtube.com/watch?v=BKDrtzJktO0 | Dan Kieft (05/10/2026). Méthode visage, puis tenue, puis planche. Planche générée à partir de deux images. Choix du modèle d'image au goût. Transcription automatique lue en entier. |
| https://suno-seedance-music-video.vercel.app/ (via dankieft.com/aimusicvideo) | Tous les prompts de Kieft : Prompt Director de visage, gabarit de planche en 3 panneaux, liaison `@image1` dans Seedance 2.5. |
| https://www.youtube.com/watch?v=M7p7HrJjcdA | Tao Prompts (06/07/2026). Planche en 4 colonnes en 4K, planche et image du plan envoyées ensemble à Seedance 2.0, angle à écrire dans le prompt, paroles dans le prompt. Transcription lue en entier. |
| https://www.youtube.com/watch?v=f4HcdR3cd4M | AI Video School (23/01/2026). Prompts de planche 4 + 3 et de changement de tenue dans Nano Banana. |
| https://aivideoschool.xyz/ai-video-school/how-to-create-consistent-characters-with-reference-sheets/ | Article d'accompagnement de la vidéo précédente. Mêmes prompts. |

### Avis, indices seulement

| URL | Ce qu'elle apporte |
|---|---|
| https://reddit.sentinel-team.org/posts/1t5gybx/snapshots/2026-05-16T01%3A23%3A47.097555Z | Miroir d'un fil r/VEO3. Les planches font parfois apparaître deux personnages. Passage à quatre images séparées dans Kling 3. |
| https://www.youtube.com/watch?v=PeelSIEewUY | Andy Lo : vidéo hors sujet (automatisation n8n). Rien d'utilisable. |
| magicshot.ai, lovart.ai, toyboxai.io (blogs d'animaux) | Conseils concordants mais non testés sur les marques et le bloc d'identité d'un animal. |
| eachlabs.ai, segmind.com, vercel.com (pages Kling v3) | Langues de Kling selon des revendeurs, contradictoires entre elles. |

---

## Ce qui reste incertain

1. **Planche ou images séparées pour Veo 3.1 et Kling 3.0.** Aucune doc ne tranche pour une planche unique. Seedance a tranché, dans un sens pour la 2.0 et dans l'autre pour la 2.5. Les créateurs obtiennent de bons résultats avec des planches. Un test court sur JJ réglerait la question : même plan, planche contre trois images séparées, en 4 s et 720p.
2. **Ordre des références dans Veo et Nano Banana.** Ce n'est documenté nulle part. Seedance dit seulement : « Place important assets first ». L'idée que la première image pèse le plus chez Veo vient d'un blog non vérifié.
3. **Le corps sans tête de Kieft.** Il ne l'explique pas. Mon explication (un seul visage pour éviter les jumeaux) reste une hypothèse.
4. **Le français dans les prompts.** Aucun test publié. Veo n'évalue que l'anglais. La recommandation « anglais pour les modèles » repose sur ce point et sur la prudence, pas sur une mesure.
5. **La règle des vrais visages Seedance chez les revendeurs** (fal.ai, Higgsfield). Elle est documentée chez BytePlus seulement. Une canon photoréaliste faite par Nano Banana pourrait être refusée selon le fournisseur.
6. **Les portraits d'expression.** Aucune source ne mesure leur effet en image vers vidéo. Les usages proposés en section 3 sont des déductions.
7. **Le poil long d'Alister en mouvement.** Aucune source ne traite ce cas. C'est le risque principal à surveiller sur le chien.
8. **La langue de Seedream.** Non vérifiée.
9. **Gemini Omni Flash.** Google oriente désormais vers ce modèle (`gemini-omni-1.1-flash`) en remplacement de Veo 3.1 preview sur l'API Gemini. Je n'ai pas étudié sa gestion des références.
10. **Les dates des vidéos YouTube** viennent des métadonnées de la page. Les transcriptions sont automatiques : les noms de modèles y sont parfois déformés (« Cense 2.5 », « Hicksfield »).
