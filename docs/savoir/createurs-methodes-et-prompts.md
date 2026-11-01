# Créateurs : méthodes et prompts

Ce que les créateurs suivis par Michael font et publient, avec leurs prompts mot pour mot. Recherche du 1er novembre 2026 ; transcriptions complètes dans docs/savoir/sources/.

## 1. Dan Kieft : « Suno v6 + Seedance 2.5 is NUTS at Making AI Music Videos »

### Fiche

- URL : https://www.youtube.com/watch?v=BKDrtzJktO0
- Chaîne : Dan Kieft, 318 000 abonnés.
- Publiée le 5 octobre 2026. Durée 23 min 36 s. 203 722 vues au 1er novembre.
- Description : lien affilié Higgsfield (dankieft.com/higgsfield), lien vers la page de prompts (dankieft.com/aimusicvideo), Instagram, mail pro. Sujet « inspiré par @noisygroup ».
- Pas de chapitres YouTube. La page de prompts découpe la méthode en 7 parties.
- Transcription : complète (sous-titres automatiques). Quelques noms sont déformés par la transcription : « Cense 2.5 » pour Seedance 2.5, « Jenjutsu » pour Genjutsu, « Nano Man Pro » pour Nano Banana Pro, « Cream 5.0 » probablement pour Seedream 5.0, « GPT 2.5 Sunburst » non identifié avec certitude.
- Page de prompts : dankieft.com/aimusicvideo redirige vers https://suno-seedance-music-video.vercel.app/. Elle est accessible et complète. Le fichier skill `.md` est téléchargeable sur Dropbox. Il cite un second fichier, `references/advanced-techniques.md`, qui n'est pas fourni.

### Ce que contient la vidéo

Trois outils : Suno pour la musique, Higgsfield pour toutes les images et vidéos, un LLM (Claude ou ChatGPT) pour écrire les prompts.

Sept étapes :

1. **Musique.** Il fait d'abord un beat instrumental (tech house), le télécharge, le recharge dans Suno comme référence audio, ajoute ses paroles et « remixe » le style en K-pop.
2. **Personnages, en trois temps : visage, tenue, planche.** Il pense d'abord à l'apparence, au maquillage et à la personnalité, « comme un acteur ». Un prompt système (« Universal Prompt Director ») dans le LLM produit le prompt du visage. Il génère le même prompt sur trois modèles d'image et garde celui qu'il préfère : « le modèle ne compte pas, seul le goût compte ». La tenue vient d'une image Pinterest décrite par le LLM. La planche de personnage part de **deux** images : le gros plan (détail du visage) et le plan en pied (détail de la tenue).
3. **Décors.** Deux voies. Décor simple : une ligne « Location » dans le prompt vidéo, Seedance invente le lieu. Décor riche : il génère d'abord une image du décor et la passe en référence. « Les images coûtent très peu, essayez plusieurs modèles. »
4. **Angles de caméra.** Contre-plongée, plongée, angle hollandais, ras du sol, vue zénithale, par-dessus l'épaule, profil. Il donne au LLM la planche, le fichier skill, l'audio et l'image, décrit l'angle, et le LLM écrit le prompt Seedance.
5. **Mouvements de caméra.** Zoom arrière, crash zoom, caméra à l'épaule, travelling, orbite. Il ajoute du tremblé en post-production. Il renvoie vers aicameramovements.com.
6. **Prompt en un coup.** Planche + skill + 30 s d'audio : un seul prompt donne un clip de 30 s pour les réseaux. Il le présente comme la voie rapide, pas la meilleure.
7. **Lip-sync.** L'audio de référence est un **MP4 à image noire**, pas un MP3. Si le personnage chante sur les chœurs ou les ad-libs, il exporte les stems de Suno, garde la voix voulue, la rend en MP4 noir et recolle les stems au montage.

### Le moment autour de 15 min 13 s

À 15 min 00 s, il passe dans l'onglet vidéo Seedance 2.5 de Higgsfield. Il charge la planche, le fichier audio et le prompt. Son conseil : « si vous n'êtes pas sûr de votre prompt, partez d'abord sur un réglage plus bas ; si ça ne va pas, corrigez, puis générez en version haute ». Il ajoute : vérifier que chaque référence est bien liée au prompt, et que la durée réglée correspond à la durée écrite dans le prompt. Le résultat est le plan en angle hollandais avec le double qui marche au fond.

Juste après (15 min 45 s à 17 min 30 s), il montre la technique des **15 angles en une génération** : une coupe par seconde, puis il fait des captures des angles réussis pour les réutiliser comme références.

### Ses outils et ce qu'ils coûtent

| Poste | Outil | Coût vérifié |
|---|---|---|
| Musique | Suno v6 | non vérifié ici |
| Images (visage, tenue, planche, décor) | Higgsfield : GPT Image, Seedream 5.0, Nano Banana Pro, Soul | crédits Higgsfield |
| Vidéo | Seedance 2.5 sur Higgsfield, essai de Cinema Studio 4.0 | voir ci-dessous |
| Remplacement de personnage | Higgsfield Genjutsu (garde le mouvement, change le personnage) | crédits Higgsfield |
| Prompts | Claude ou ChatGPT + son fichier skill | abonnement LLM |
| Montage | DaVinci Resolve ou Premiere | hors IA |

Prix de Seedance 2.5 relevés :
- **Higgsfield**, billet du 20 octobre 2026 : formule Plus à 49 $ par mois pour 1 000 crédits (39 $ en annuel). C'est la formule la moins chère qui donne Seedance 2.5. Un clip de 8 s coûte 24 crédits en 480p, 56 en 720p, 128 en 1080p. Au tarif Plus, cela fait environ 1,18 $, 2,74 $ et 6,27 $ par clip de 8 s.
- **API Segmind**, test du 7 août 2026 : 0,1065 $/s en 480p, 0,2389 $/s en 720p. La facture réelle colle au tarif à 0,7 % près. Un article Hackernoon du 22 octobre 2026, qui reprend Segmind, donne 0,5876 $/s en 1080p.
- **Studio** (`docs/FOURNISSEURS.md`) : Replicate à 0,23 $/s en 720p, Runway et Atlas Cloud à 0,30 $/s. Atlas Cloud signale que Replicate a quatre prix selon la résolution et selon qu'une vidéo est en entrée ou non. La méthode de Dan passe l'audio par une vidéo MP4 : le tarif « avec vidéo en entrée » pourrait s'appliquer. À vérifier.

Calcul indicatif (mon calcul, pas une donnée de Dan) pour un morceau de 3 min :
- tout en Seedance 2.5 720p par API : 180 s × 0,24 $ = 43 $ par passe. Avec un essai raté sur deux en moyenne, environ 65 $. En 1080p direct : 106 $ par passe.
- mixte : 40 % de plans chantés en Seedance 2.5 720p (72 s, environ 17 $ par passe, 26 $ avec les reprises) et le reste en Veo 3.1 Fast 1080p sans son sur les crédits Google (108 s × 0,10 $ = 11 $ par passe, 16 $ avec les reprises, payés par les 300 $).
- la technique des 15 angles : 15 s en 720p à 0,24 $/s = 3,58 $ pour 15 plans d'une seconde, soit 0,24 $ par plan. Chez Veo, un plan coûte au minimum 4 s : 0,40 $ en Fast 1080p.

### Mon avis

C'est la meilleure des cinq sources, de loin. La qualité vient de quatre choses, et aucune n'est un secret technique :
1. **Un travail de direction avant de générer.** Personnage pensé comme un acteur, décor pensé comme un plateau, liste d'angles choisie.
2. **Des prompts très structurés** : objectif, continuité, étapes horodatées avec état initial, action, état final, type de coupe, style, caméra, audio, exclusions. Son fichier skill impose cette structure.
3. **Seedance 2.5 en mode référence** (planche + décor + audio), pas en mode « image de départ ». Le lip-sync se fait dans la même génération que le jeu du corps. Le chant et le mouvement sont donc cohérents.
4. **Beaucoup de plans courts et de coupes au montage.** Il génère des variantes d'angle et garde les meilleures secondes.

Limites :
- Il est affilié à Higgsfield. Les liens de la description, de la page et la dernière ligne imposée par son skill (« Generate your video in Seedance 2.5 on Higgsfield », lien dankieft.com/skill) sont des liens affiliés.
- Il ne donne aucun coût. Il génère beaucoup (trois modèles par visage, plusieurs décors, variantes d'angles). La vidéo ne dit pas combien de générations ont été jetées.
- Le fichier `advanced-techniques.md` (édition, extension, premier et dernier image) n'est pas publié.

### Ressemblances et écarts avec le studio

| Point | Dan Kieft | Riot Machine aujourd'hui |
|---|---|---|
| Vidéo | Seedance 2.5, références multiples | Veo 3.1 image vers vidéo, une image de départ par plan |
| Son | lip-sync natif dans la génération, audio en MP4 noir | vidéo sans son, lip-sync séparé (Kling LipSync) |
| Plans courts | plusieurs coupes dans une prise (15 angles en 15 s) | un plan par prise, minimum 4 s facturé chez Veo |
| Personnage | planche 3 panneaux sur gris neutre 18 % | canon + pack + fiche ADN |
| Prompts | LLM + skill structuré par étapes | agents storyboard et prompteur |
| Stems | voix principale isolée de chaque personnage, ad-libs retirés | stem « vocals » global |

### Ce qu'on peut reprendre

1. **Sa structure de prompt** (GOAL, CONTINUITY, STAGE, VISUAL STYLE, CAMERA AND PERFORMANCE, AUDIO, EXCLUSIONS, MAINTAIN CONSISTENCY) dans le guide du prompteur. Elle vaut aussi pour Veo, sauf la partie références audio.
2. **Sa planche de personnage à trois panneaux** : corps de face sans tête, corps de dos avec tête, gros plan du visage, sur un gris plat sans ombre. Le corps sans tête évite que le modèle lise deux visages. C'est un bon modèle pour le pack de JJ.
3. **Son conseil contre les refus de ressemblance** (skill, section « Avoiding IP and likeness flags ») : ne pas montrer un visage hyperréaliste, de face et pleinement éclairé, quand le plan n'en a pas besoin. Cela rejoint le refus de la canon v1 de JJ par Veo le 29 octobre. C'est une piste, pas une garantie : le conseil vise Seedance.
4. **Le test du lip-sync par MP4 noir** sur Seedance 2.5. Dan et Tao Prompts le font tous les deux. Le studio a noté « à tester sur 2 s ». Le test se fait en 480p, au plus court permis par le fournisseur.
5. **Les stems par personnage** : une voix isolée par chanteur, sans ad-libs, pour chaque plan chanté.
6. **Les plans multiples par prise** pour les plans de moins de 4 s : 41 plans sur 65 dans Nobody Saw. Seedance 2.5 le fait, avec une coupe par seconde.
7. **Les 15 angles en une prise comme banque de références** : on garde les captures des angles réussis comme images de départ.

### Prompts publiés, mot pour mot

Source : https://suno-seedance-music-video.vercel.app/ (redirection de https://dankieft.com/aimusicvideo), lue le 1er novembre 2026.

**Outils listés sur la page :** Suno (« Make the beat here, add your lyrics, remix the style »), Higgsfield (« For every image and video. All the Seedance 2.5 stuff runs in here. »), Claude ou ChatGPT, et « Seedance 2.5 Prompt Builder. My skill file (.md). Drop it into your LLM and it follows my prompt structure. »

#### 01. Musique : le beat (Suno)

```
Tech house. 126 BPM, G minor, 4/4 time. A heavy, saturated kick drum drives the rhythm alongside a crisp, high-frequency closed hi-hat on the off-beats. A syncopated, percussive synth bassline plays a repetitive two-bar pattern, emphasizing the root note with short, staccato envelopes. A dark, resonant synth lead enters with a rhythmic, three-note motif that uses a band-pass filter sweep. Shaker loops provide additional high-end energy. A metallic, industrial-sounding percussion hit occurs on the second beat of every fourth bar. The arrangement features a minimalist build-up where a high-pass filter is applied to the drums, followed by a sudden drop where the sub-bass frequencies return in full.
```

#### 01. Musique : les paroles

```
[Intro]
(Ah-ah, ah-ah)
Voguing, voguing
Look at me, look at me now

[Verse 1]
Strut in the dark, spotlight on my face
Every single move, I'm setting the pace
Diamonds on my wrist, fire in my eyes
Runway is mine, watch me claim the prize

[Pre-Chorus]
Bass hit heavy, heart beat faster
Ain't no other, I'm the master
One, two, step, don't test me
Voguing hard, can't arrest me

[Chorus]
G-A-L-A mode, I'm unstoppable
Hyperpop heart, unmistakable
Catwalk queen, watch me dominate
Every single frame, I calculate

[Post-Chorus / Chant]
(Left, right, strike a pose)
(Left, right, watch it close)
Voguing, voguing, ah-ah

[Verse 2 - RAP]
Yeah, step in the room, I'm the one they whisper
Cold shoulder flex, watch the room get stiffer
Every angle sharp, every word a blade
Built this whole empire, watch it never fade
Runway's my battlefield, heels like weapons
Every single glance is a lesson, no exception
Vogue in the smoke, camera catch the shine
Y'all still catching up, I'm three steps in time

[Chorus]
G-A-L-A mode, I'm unstoppable
Hyperpop heart, unmistakable
Catwalk queen, watch me dominate
Every single frame, I calculate

[Bridge]
(Whispered/half-sung)
Slow it down... watch me now...
Every move calculated, take a bow
(Build back up)
Bass drop- now

[Final Chorus / Outro]
G-A-L-A mode, unstoppable
Hyperpop heart, unmistakable
(Ad-libs, vocal chops fade out)
Voguing... voguing... ah
```

#### 01. Musique : le remix de style

```
k pop girl group trap funk fusion hard 808 sub bass rolling trap hi hats Electronic, Hip Hop, House, R&B, Funk inspired groove warm funky bassline jazzy chord stabs filtered disco samples syncopated swing rhythm vocal chops pitched ad libs unison chant vocals smooth autotune lead runway voguing catwalk energy glossy colorful production groovy bounce confident female vocal harmonies danceable dark pop 128 136 bpm
```

#### 02. Personnage : Universal Prompt Director (visage)

Prompt système à coller dans le LLM, qui écrit ensuite le prompt image.

```
You are an image-prompt director for photoreal AI character face locks (for tools like Nano Banana / Banana Pro, GPT-image, Higgsfield-style generators).

CORE PHILOSOPHY:
Every output must read as a real photograph of a real human - never CGI, never plastic, never 3D-render, never "AI-generic" skin. Real pore texture, peach fuzz, hair flyaways, subsurface scattering, matte skin finish.

FLATTERING-REALISM CEILING (always on):
Full skin realism (pores, peach fuzz, subsurface scattering) but NEVER unflattering - no acne, no blemishes, no scarring, no enlarged pores, no harsh dermatology-photo detail. Texture is fine, soft, even, natural. Resolve any conflict toward "fine, even, flattering" - the face should always look good.

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

UNIVERSAL OUTPUT RULES:
1. No real names, no brand names - generic visual descriptors only
2. No @image tags or placeholder syntax - reference attachment happens in the tool's UI
3. No meta-commentary ("this is the shot," "the read is...") - pure visible description only
4. No negative prompt blocks
5. No aspect ratio specs in the prompt text (no "3:4," "16:9," etc.) - framing described in plain language only ("chest-up portrait," "full body")
6. Deliver the full prompt as ONE continuous block, ready to copy-paste
7. Before writing the full prompt, give a short bullet-point confirmation of what's about to be built (character traits, backdrop, framing) and wait for a go-ahead - unless it's a minor tweak to an already-approved prompt, in which case just deliver the revision directly

When the user gives you a character description (or asks you to invent one), lock the spec first, confirm it, then produce the face-lock prompt following the structure above.
```

#### 02. Personnage : prompt de la planche

Prompt système à coller dans le LLM avec deux images (gros plan et plan en pied).

```
You are a character-sheet prompt writer. Analyze the images I upload and write one complete text-to-image prompt matching the exact format, paragraph order, descriptive density, and photographic treatment of the template below.

Your deliverable is the written prompt only. Do not generate an image or call image-generation tools.

Analyze the references silently. Replace every bracketed instruction in the template with detailed descriptions of the actual character and outfit. No brackets or placeholders may remain in your output.

REFERENCE RULES
- Preserve the character's identity, facial proportions, apparent age, skin tone, eyes, hairstyle, makeup, facial hair, build, and visible defining features.
- Use ethnicity or nationality only if I specify it; otherwise describe visible appearance.
- If separate identity and outfit images are supplied, use each for its intended purpose. Do not copy the outfit model's identity.
- My written changes override the images.
- Describe the actual garments, materials, colors, construction, fit, layering, accessories, and footwear precisely.
- Do not carry over the example character's pink hair, blue eyes, Korean identity, feminine physique, couture clothing, or other details unless supported by my references or instructions.
- Keep asymmetrical features on the correct anatomical side across views.
- Infer only the simplest necessary continuation of details not visible in the references.
- Preserve image-reference tags if I supply them, incorporating them naturally into the Identity and Wardrobe paragraphs.
- Keep the exact three-panel arrangement: headless front body, rear body with head attached, frontal face close-up.
- Preserve all fixed background, lighting, shadow, color, skin-finish, and camera wording below. Do not summarize, shorten, soften, or replace these paragraphs.
- Adapt anatomical language only when the supplied character requires it.
- Output the finished prompt as plain paragraphs. No introduction, explanation, bullet points, code fence, or additional headings. Keep only "Identity:", "Wardrobe:", and the three panel labels shown in the template.

OUTPUT TEMPLATE

A three-panel character reference sheet composed as one horizontal frame, divided into three equal vertical panels side by side, thin clean separation between panels, the same figure and the same outfit rendered identically across all three. No text, no labels, no numbering anywhere in the image.

Identity: [Write a detailed description of the specific character from the identity references. Include apparent age, overall facial structure, cheekbones, jawline, eye color and shape, eyebrows, nose, lips, natural skin tone, makeup where present, hairstyle, hair color, length, hairline, facial hair where present, physique, and visible distinguishing features. Preserve tattoos, piercings, or other defining features when present rather than automatically excluding them. Use flowing descriptive sentences at the same level of detail as the supplied example. Keep the identity fully realistic and photographic.]

Wardrobe: [Describe the exact outfit in detailed flowing prose, progressing from the upper body through the lower body to footwear. Include each layer, its color, material, shape, volume, fit, neckline, collar, sleeves, seams, closures, draping, hems, and visible decorative details. Describe worn jewelry and accessories where present and permitted by my instructions. Explain how pieces overlap and where they sit on the body. Preserve the reference design without adding unrelated fashion elements.]

LEFT PANEL - full body front view, headless. The full figure stands squared to camera from the shoulders down to [the actual footwear, or feet if barefoot], arms relaxed at the sides, hands open and loose, weight even across both feet. There is no head and no hair - no hair falls across the chest or shoulders. The neck rises a short way from the shoulders and terminates in a clean, flat, sharply defined horizontal edge at the base of the throat, exactly like a headless dress-form mannequin - a crisp sculptural cut with a clean visible edge, not blurred, not faded, not dissolving, no wisps, no smoke, no ghosting, no transparency, no blood, no anatomy detail at the cut. Above that clean edge there is only empty field. The panel keeps full headroom so the figure sits at the same scale and position in the frame as a normal full-body portrait, [describe the actual full outfit silhouette and its key front-facing details] all clearly readable.

CENTER PANEL - full body rear, head attached. The complete figure from above the crown down to [the actual footwear, or feet if barefoot], seen directly from behind, standing squared away from camera, weight even, arms relaxed at the sides. [Describe the character's actual hair or head appearance from behind, followed by the outfit's back construction, silhouette, layers, seams, drape, accessories, and footwear. Match the front view's body scale, shoulder height, foot baseline, proportions, and garment lengths. Preserve the hairstyle's actual length and volume.]

RIGHT PANEL - tight chest-up face lock. Framed from just above the crown down to the collarbones with the face filling the panel, squared to camera, head level, eyes directly to camera, neutral model face-card expression, lips closed and relaxed. [Describe the actual neckline, collar, upper garment, and any relevant worn accessories entering the bottom of frame.] Every facial plane, the full eye construction, brow, nose, lip shape, and hairline read at maximum detail, [restate the character's specific eye appearance and relevant defining facial details] clearly visible.

Skin renders at its true natural skin tone, identical in value and hue across the face, arms, hands, back, and body in every panel, never darkened, never tanned, never pale or washed-out or cool-shifted.

The background is a single flat 18% neutral gray field - one uniform value at every pixel corner to corner, identical directly beside the subject and in the far corners, with no seam line, no gradient, no hotspot, no vignette, and no falloff to lighter or darker anywhere in the frame. It is a flat color field, not a photographed backdrop - no surface, no floor, no wall, no corner, no horizon, and no plane the figure stands on or in front of.

Relight from scratch overriding any reference lighting, applied uniformly across all three panels: completely flat shadowless illumination - one enormous soft frontal source at camera position wrapping the subject evenly, matched equal fill from camera-left and camera-right at identical intensity, matched fill from above and below, so both sides of the face read at exactly the same brightness. No key-and-fill ratio, no modelling, no shadow side, no cheek triangle, no nose shadow, no under-chin shadow, no rim light, no hair light, no kicker, no specular hotspot. Extremely low contrast, even, milky, catalogue-flat. Form is described by bone structure, hair strands, and fabric folds alone, not by light and shadow.

Absolutely zero shadow anywhere outside the subject in any panel. No cast shadow, no contact shadow, no floor shadow, no drop shadow, no ambient occlusion where the body meets the background, no soft darkening behind the shoulders or beneath the hem, no halo, no edge darkening, and no rim separating the figure from the field. Shading exists only on the subject and stops cleanly at the silhouette. Absolutely zero light bleed outside the subject - no spill, no glow, no bounce, no reflected color cast thrown from the skin or the wardrobe onto the background, and no brightening anywhere behind the figure.

Skin reads matte and velvety - zero shine on forehead, nose bridge, cheekbones, temples, and chin, no oily T-zone. Skin renders at its true natural skin tone and wardrobe at its true natural color, warmth preserved and natural against the neutral gray, never pale or washed-out or cool-shifted by the background. Real peach fuzz at the jaw and hairline, real soft fine even pore texture, subsurface scattering reading as semi-translucent biology, real hair rendered strand by strand with fine flyaways at the hairline, [insert a detailed sequence of material-realism descriptions specific to the actual outfit: the weave, tailoring, knit, leather grain, metal reflections, faceted sparkle, embroidery, gloss, or other surface properties that are genuinely present], never plastic, never waxy, never glass-skin, never harsh - fine flattering texture that keeps the face looking good, no acne, no blemishes, no rough pores.

Even sharpness edge to edge across the entire frame in every panel. No depth-of-field falloff, no bokeh, no background blur, no lens vignette, no lens distortion, no flare, no bloom, no chromatic aberration, no atmospheric haze, no air between the subject and the background. Photographed on a 50mm prime, soft natural film grain. Photographed not generated.
```

#### 03. Décor rouge (ligne « Location »)

```
Location: a bare cinematic set - a deep, saturated red backdrop gradating smoothly into black toward the edges and upper frame, no visible floor line or props, pure atmospheric color and shadow. A single hard spotlight moves erratically through the sequence, never settling into a full frontal reveal - always a graze, a rim edge, a sliver, or a sweep that clips only part of her.
```

#### 03. Décor blanc (ligne « Location »)

```
Location: a bright, minimal white studio - seamless white cyclorama floor and walls, soft even shadowless light, no visible props or set dressing, pure clean white space extending back into a soft white infinity behind the walking figure.
```

#### 03. Prompt complet avec le décor blanc (plan en angle hollandais)

```
[GOAL]
K-pop performance shot, extreme close-up foreground of Kai at a Dutch angle lip-syncing directly to camera, while the same version of her walks in the background of a bright white studio. Duration: 11s (full length of @Video 1's audio).

[CONTINUITY]
Character: Kai corresponds to @Image 1 for identity and wardrobe - sleek dark hair parted center and pulled back, sharp graphic black winged eyeliner, and the sculptural white couture look: a high-collar draped white gown with a red-veined membrane wing structure spanning the shoulders and back, a spiked white-and-red crown radiating from the hairline. Both the foreground and background figures are the exact same version of Kai - same identity, same hair, same wardrobe, same crown - appearing twice in the same frame as one continuous character, not two different people.
Location: a bright, minimal white studio - seamless white cyclorama floor and walls, soft even shadowless light, no visible props or set dressing, pure clean white space extending back into a soft white infinity behind the walking figure.
Audio: @Video 1 provides the audio track for this shot - use its music and vocal only. Do not use any visual content, subject, or setting from @Video 1.

[STAGE 1 | 0-11s | Foreground lip sync, background walk]
Initial state: the frame is held at a Dutch angle tilt. Kai's face fills roughly two-thirds of the foreground in extreme close-up, her features cropped tight and off-axis with the tilt, direct to camera, composed expression. Well behind her and offset to the opposite side of the frame, the same Kai appears small and distant, standing at the start of a diagonal walking path in the white studio.
Primary event: the foreground Kai lip-syncs directly to camera with sharp, confident playback energy, her expression shifting between lines - a smirk, a sharper stare - while the background Kai walks steadily across the white space along the diagonal, unaware of the foreground, her full silhouette crisp and small against the bright white studio, continuing to walk at a natural pace for the full duration of the shot.
End state: foreground Kai holds a final direct stare on the last line, still filling most of the tilted frame; background Kai now much further along her walking path, smaller and near the edge of frame.
Cut type: NO CUT, continuous locked Dutch-angle composition throughout.

[VISUAL STYLE]
Clean high-key editorial music-video look: soft even white studio light on the background figure, slightly harder directional key on the foreground face to separate her from the white space, cool-neutral color balance, fine film grain, subtle diffusion bloom on the whites, crisp contemporary grade - fashion-campaign polish with a deliberate off-kilter Dutch tilt.

[CAMERA AND PERFORMANCE]
Locked-off camera held at a fixed, pronounced Dutch angle tilt for the full shot - no cuts, no reframing. Two depth layers held simultaneously in one continuous composition: a large, tightly cropped foreground face and a small, distant full-body figure walking through the background, both the same character. The foreground face stays large and static in frame while the background figure's walk provides the only major motion, crossing the white space at a steady confident runway pace along a diagonal line for the full 11 seconds.

[AUDIO]
(Hyperpop-leaning dance-pop track plays throughout, driving playback energy - full 11s length of @Video 1.)
Dialogue language: American English. The foreground Kai lip-syncs with full playback energy, matched to the vocal in @Video 1's audio: {G-A-L-A mode, I'm unstoppable. Hyperpop heart, unmistakable. Catwalk queen, watch me dominate.}
The background Kai does not lip-sync - mouth neutral, focus is on her walk.
No on-screen subtitles.

[EXCLUSIONS]
No on-screen text, logos, or watermarks. No other characters - only the two instances of Kai in frame, foreground and background. No cuts - single locked Dutch-angle composition for the full 11s. No wardrobe or hair difference between the foreground and background Kai - identical in both.

[MAINTAIN CONSISTENCY]
One character, Kai, appearing twice in the same frame - foreground close-up and background walking figure - both matching @Image 1's identity and wardrobe exactly, same white studio location throughout, same locked Dutch-angle framing held for the entire shot.
```

#### 04. Ce qu'il a dit au LLM pour l'angle hollandais

```
Using the md file and strictly follow it's prompt structure, with the 2 references, @image1 as the character and @video1 as the lip sync audio

Create an extreme close up fixed Dutch angle of her in the foreground lip-syncing directly to camera. the initial state starts off at a dutch angle with her face filling the foreground in an extreme closeup.

While the same version of her walks in the far background of a bright white studio at the opposite side of the frame
```

#### 04. Les 15 angles en une prise (prompt Seedance)

```
Music video insert sequence, 15 hard-cut angles, featuring one female performer @Image 1 in a dark industrial motorcycle hangar @Image 2 lip syncing and dancing to the song @Video 1.

The camera cuts to a completely different angle every second, so there's 15 different and unique from each other camera angles, with her doing different things on each shot. Use cinematic angles that is shown in a hollywood movie
```

#### 05. Mouvements de caméra (consignes de la page)

```
Zoom out, crash zoom in, handheld, tracking shot, orbit
Not sure what's out there? This site shows every move with its prompt
Want to swap the character but keep the move? Use Higgsfield's character swap
```

#### 06. Prompt en un coup : ce qu'il a dit au LLM

```
use the skill file and follow the prompt structure using the stages structure to give me a 30 sec prompt for seedance 2.5.

I want to make a 30-second video based on the @audio1 I just sent you. use the guy @image1 as the character. I want something pretty simple, ultra cinematic.

I want a guy who's in a car, driving his car. We have some POV of the car, like an action rig. Then we have some side shots. Then he gets out of the car, medium shot, he moves forward. When he gets out of the car, he goes to a friend. The friend checks him. Then he looks at the camera, does his playback. Then cut, we have another shot where he's lying on his bed, it's a bit blurry. He does his playback. Cut.

He's outside, leaning against a wall. There are guys on the right doing something, he's focused. He does his playback.

So that's pretty much the idea I have. Really add shots to make it more aesthetic. It's something blurry. And I specify in the prompt that he does the lip sync throughout the video, so you don't need to specify which line he's going to say at each cut.
```

#### 06. Prompt en un coup : le prompt rendu par le LLM

```
[GOAL]
Music-video sequence, 30 seconds, single male performer. The man from @image1 lip-syncs continuously to the bound audio track across four locations - a daytime drive, a street arrival with a friend, a bed, an exterior wall. No plot, no resolution: pure performance, atmosphere and texture.

[REFERENCE BINDING]
@image1 = the sole character and wardrobe reference for the man. Use the close-up for his exact facial identity and the front and back views for his outfit and body proportions. These are views of the same man, not separate characters. Do not reproduce the reference sheet layout.
@video1 = the complete 30s music track. It is the ONLY audio source and plays uncut from 0s to 30s.
The man's mouth, jaw, breath and micro head movement must stay locked to the vocal performance in @video1 for the ENTIRE runtime - in every single stage, including inside the moving car, including when he is lying down, including when he is not facing camera. He is never silent. Never generate additional speech, narration or dialogue.

[SUBJECT PROFILE]
The man: exactly the man shown in @image1. Young adult, lean build, medium-brown skin, dark asymmetrical locs swept to one side with closely cropped sides, brown eyes, faint moustache and light facial stubble, small teardrop tattoo beneath his right eye, silver hoop earrings, and a silver chain with green oval accents.
Outfit, fixed and never changed: the exact muted grey-olive cropped zip jacket from @image1, with its oversized pale beige collar and pale ribbed cuffs and waistband, worn open over a white ribbed tank top; charcoal-grey wide-leg pleated trousers, black belt with a silver buckle, and grey-and-white low-top sneakers. Preserve the reference's garment shapes, fit, materials, colours and accessories. No logos, no graphics, no branding anywhere on the clothing.
@image1 defines him in all eight stages. Face, skin tone, locs, hairline, facial hair, tattoo, earrings, chain and outfit must be identical from the first frame to the last - do not re-interpret his features between cuts.

[CONTINUITY]
FRIEND B: second young man, Stage 5 only. Taller, heavier build, cropped hair, olive canvas jacket. Never lip-syncs, never looks at camera.
BACKGROUND PAIR: two figures, Stage 8 only, screen right, deep and out of focus. They never approach, never face camera.
THE CAR: one single vehicle across Stages 1–4 - a dark grey older sedan, worn fabric interior, no badges, no visible license plate. Same model, same colour, same interior every time it appears.
THE STREET: Stages 3, 4, 5, 6 and 8 all take place on the same stretch of street - same pale concrete wall, same damp asphalt, same low grey buildings. It must read as one continuous location.
THE BED: Stage 7 only, interior, unmade pale grey sheets, daylight from an unseen window.

[STAGE 1 | 0–2s | COLD OPEN]
Initial state: black frame.
Primary event: hard cut in on an extreme close-up insert - rain beads scattered across a windshield, a wiper blade sweeping through frame, the blown-out white sky glaring through the glass behind them. The man's face is only half-readable in the reflection, broken by water and light.
End state: frame dominated by out-of-focus water and white sky; the face has NOT yet been clearly revealed.
Cut type: HARD CUT in from black.

[STAGE 2 | 2–6s | ACTION RIG POV]
Initial state: interior of the car, overcast daylight, in motion.
Primary event: hood-mounted action rig, low, wide, rigidly locked to the car body - the man sits static and perfectly stable in frame while the grey city smears and rushes behind him through the windshield. Flat white sky reflected across the glass in a soft milky sheet. One hand hangs at the top of the wheel. He is already lip-syncing, jaw loose, chin low, barely moving his head.
End state: rig framing unchanged, wet road and grey buildings streaking behind the glass.
Cut type: NO CUT within the stage. The rig never detaches from the car.

[STAGE 3 | 6–10s | SIDE / LATERAL]
Initial state: same drive, continuous.
Primary event: cut to the exterior side. Door-mounted rig looking in through the open driver window at his profile, lit flat and shadowless by the overcast sky, the reflection of passing buildings sliding across the door panel. Then a lateral tracking shot from a parallel vehicle, medium wide, the car sliding through frame right to left over wet asphalt.
End state: the car slows and pulls to the curb, suspension dipping as it settles.
Cut type: HARD CUT between the two angles, on the beat. No dissolves.

[STAGE 4 | 10–14s | THE EXIT]
Initial state: car stationary at the curb, engine off.
Primary event: the driver door swings open. The man steps out into a MEDIUM SHOT and walks forward toward camera. The camera retreats ahead of him on a slow dolly-back, handheld weight, holding him at chest height as he closes distance. He keeps lip-syncing while he walks.
End state: he has cleared the car and is walking in open street, the car soft and out of focus behind him.
Cut type: HARD CUT on the beat at 10s.

[STAGE 5 | 14–17s | THE DAP]
Initial state: the man walking forward, FRIEND B waiting ahead against the wall.
Primary event: FRIEND B pushes off the wall and they meet - a quick dap: hand clasp pulling into a half-shoulder embrace, one beat of contact, then release. Shot from a low three-quarter angle behind FRIEND B's shoulder, his back and arm occluding the left third of frame in heavy foreground blur.
End state: the clasp releases; the man's face clears the foreground occlusion.
Cut type: CUT.

[STAGE 6 | 17–20s | FACE CAMERA]
Initial state: the man standing in the street, FRIEND B now out of frame.
Primary event: he turns his head and locks eyes directly into the lens. Locked-off medium close-up, very slow almost imperceptible push in. Full playback, direct address, no smile, jaw working, eyelids heavy. A soft out-of-focus foreground element - a parked car roof, a railing - crosses the bottom edge of frame and partially breaks the clean read of his face.
End state: he is still holding the lens as the stage ends.
Cut type: CUT.

[STAGE 7 | 20–25s | THE BED]
Initial state: new location, interior, daytime.
Primary event: the man lies on his back on an unmade bed, head turned toward the lens on the pillow, flat window daylight washing the sheets. Overhead high angle, camera very close, lens wide open - his eyes are in focus and the rest of the frame collapses into blur. He lip-syncs lying down, quieter, smaller movement, one arm behind his head.
End state: he holds the gaze upward, motionless apart from his mouth.
Cut type: HARD CUT into the stage. Deliberately the softest, dreamiest frame of the film.

[STAGE 8 | 25–30s | THE WALL]
Initial state: back outside, same street as Stages 3–6.
Primary event: the man leans back against the pale concrete wall, shoulder blades flat to it, one foot up against the surface. Screen right, deep in the background and heavily out of focus, two figures move and talk among themselves. He ignores them entirely - locked forward, focused, unbothered, still lip-syncing. Slow lateral dolly right to left, foreground poles and parked cars wiping through frame.
End state: the dolly settles; he is still against the wall, still performing, holding until the frame ends.
Cut type: HARD CUT in on the beat at 25s. The film ends on this shot - no fade to black, hard out on the last frame.

[VISUAL STYLE]
Ultra-cinematic, anamorphic, overcast daylight throughout. Shot as if on Kodak Vision3 250D, rated slightly over and printed flat. Single light source: a solid white overcast sky acting as one enormous softbox - completely shadowless, no sun, no direction, no hard edges anywhere. Desaturated cool palette of concrete grey, damp asphalt, pale sky, muted olive and black. Blacks are lifted and milky, never crushed. Contrast is low and the whole image sits slightly cool.
Softness is the signature of this film: shoot everything wide open with extremely shallow depth of field. Foreground objects, shoulders, poles, glass and fabric constantly drift through frame out of focus and occlude the man. Focus is human, not perfect - it lands slightly late, breathes, and occasionally misses before settling. Long shutter, so any movement leaves a smear of motion blur. Where the white sky enters frame it blooms and softly veils the lens.
Fine organic film grain, visible in the flat mid-tones. Restrained and premium, never flashy. No spectacle. Composition stays calm even when the track is at its loudest.
Preserve the man's identity and wardrobe from @image1. Keep supporting characters and locations original, with no visible branding.

[CAMERA AND PERFORMANCE]
Cut on the beat, always hard cuts, never dissolves or morphs.
The man's performance is contained, not theatrical: heavy eyelids, minimal blinking, jaw doing the work while the head stays relatively still, shoulders low and relaxed, weight always on one leg, hands mostly idle. Confidence read as stillness. He never smiles, never gestures wide, never mouths silently - his articulation is precise and locked to @video1.
Only the man ever addresses the lens. Every other person in frame stays in their own world.

[AUDIO]
(@video1 - the bound music track plays continuously and uncut across all eight stages. It is the only music.)
<Diegetic sound is minimal and sits far under the track: muffled engine hum in Stages 2–3, tyres on wet road, a door latch in Stage 4, distant traffic in Stages 6 and 8.>
{No dialogue. The man never speaks a spoken line - his mouth movement is lip-sync to @video1 only. FRIEND B and the background pair are silent.}
[No subtitles. No lyrics on screen. No text of any kind.]

[EXCLUSIONS]
No sunlight, no hard shadows, no blue sky, no golden hour, no lens flare from a sun source, no night, no neon, no streetlights.
No on-screen text, lyrics, titles, logos, brand marks, license plates or watermarks.
No second person ever looking into the lens. No crowd, no extras beyond the three named figures.
No slow-motion ramping, no speed ramps, no dissolves, no whip-pan transitions, no light-leak wipes, no colour-shift transitions.
No drone or aerial shots. No fisheye. No saturated colour.
No smiling to camera, no phone screens, no visible weapons, no smoke or vape.
No wardrobe change, no location that contradicts the four established ones.

[MAINTAIN CONSISTENCY]
One performer, one friend, two background figures - headcount never changes. The man matches @image1 and the [SUBJECT PROFILE] exactly in all eight stages: same face, skin tone, locs, hairline, facial hair, tattoo, earrings, chain and outfit. The car is the same single vehicle throughout. Stages 3, 4, 5, 6 and 8 read as one continuous street. Light stays flat overcast daylight from first frame to last. Lip-sync to @video1 is unbroken from 0s to 30s with zero silent frames.
```

#### 07. Lip-sync (consignes de la page)

```
Use an MP4 with a black video as the audio reference, not an MP3
Lip syncing to the ad-libs? In Suno go to Download → Stems and split the vocals
Pick the vocal you want, render it as an MP4 and use that instead
```

#### Fichier skill « seedance-25-prompt-builder » : le gabarit maître

Source : https://www.dropbox.com/scl/fi/pkbz11zxe2qghr10tyquk/seedance-25-prompt-builder.md?rlkey=8mb3p4inv4zn6jlm16ygg0hfv&st=hwhdewyz&dl=0 (lien de la page). Le fichier complet fait 150 lignes et il est gardé dans le scratchpad. Il contient aussi : la formule de base, la discipline des étapes, les règles de références (jusqu'à 50 références, 30 images, 10 vidéos et 10 audios, 30 s cumulées), la syntaxe audio (`()` musique, `<>` bruitages, `{}` dialogue, `[]` sous-titres), les conseils contre les refus de ressemblance et une liste de contrôle. Voici le gabarit maître :

```
[GOAL]
<Video type> + <central subject(s)> + <one-sentence summary of the primary event/story> + <total duration>.

[CONTINUITY]  (skip only for a single uninterrupted shot with no recurring subject)
Subject(s): fixed appearance, clothing, and traits that must never change.
Scene: location, layout, and elements that must stay recognizable shot to shot.
Props: bound explicitly to their owner/location ("the same key", "the same door") - never leave the model to infer which object is which.

[STAGE 1 | time range | short label]   (or [SHOT 1 | ...] for a storyboard/shot-list style video)
Initial state: <carries over from the previous stage, if any>.
Primary event: <ONE main change - resist stacking many sub-actions into a short range>.
End state: <what must be directly visible when this stage ends>.
Cut type: CUT / HARD CUT / NO CUT (state explicitly when it matters).

[STAGE 2 | time range | short label]
...repeat, each stage building on the last...

[VISUAL STYLE]
Color grade, lighting logic, grain/texture, lens feel, overall mood - stated once so it holds across every stage instead of drifting.

[CAMERA AND PERFORMANCE]  (include when there's a performer or nuanced blocking)
General movement/cut rules. Translate any abstract emotion into 2-4 directly observable cues (breathing, gaze, hands, jaw) rather than naming the emotion alone - "afraid" is an instruction the model has to interpret; "shallow breathing, trembling fingers, widened eyes" is something it can render.

[AUDIO]
() for music/score, <> for sound effects/ambience, {} for dialogue (state the language before non-Chinese lines), [] for subtitles. State "no dialogue / no subtitles" explicitly if none are wanted - don't leave it implicit.

[EXCLUSIONS]  (not official Seedance syntax, but consistently effective)
A short negative list of anything that must never appear: specific things the audience/character must never see, gore level, text/logos/watermarks, or anything that risks reading as a real or copyrighted likeness (see IP section below).

[MAINTAIN CONSISTENCY]
One closing line reinforcing subject identity, headcount, spatial layout, and axis of action across the whole sequence.
```

---

## 2. Andy Lo : « How I Used $0 to Create 1000+ Videos on Autopilot With This AI Agent System (No Paid API Needed) »

### Fiche

- URL : https://www.youtube.com/watch?v=PeelSIEewUY
- Chaîne : Andy Lo, 95 100 abonnés.
- Publiée le **12 mars 2025**, donc vieille de 20 mois. Durée 45 min 32 s. 287 796 vues.
- Chapitres : intro, présentation de sa communauté, démonstration, installation de n8n en local avec Docker, API YouTube, API Google Sheets, schéma du tableur, téléchargement automatique de vidéos « libres de droits » sur YouTube, idem pour la musique, génération et mise en ligne, bonus génération d'idées.
- Description : liens vers ses communautés Skool (gratuite et premium), un formulaire d'accompagnement payant, un lien affilié n8n.
- Transcription : complète.
- Ressources : le modèle de workflow et les bouts de code sont réservés à sa communauté Skool (« for our community members, just copy this »). Ils ne sont pas publics. Je ne m'y suis pas inscrit.

### Ce que contient vraiment la vidéo

Il n'y a **aucune génération vidéo par IA**. Le système fait ceci :
1. n8n tourne dans Docker sur son PC. Il y installe FFmpeg et yt-dlp.
2. Un Google Sheet liste des URL YouTube de séquences et de musiques « libres de droits ». yt-dlp les télécharge, cinq par heure. Lui-même prévient qu'au-delà, YouTube peut bannir l'adresse IP.
3. DeepSeek écrit des titres et des citations de motivation, collées dans le tableur.
4. Chaque jour, FFmpeg tire au hasard une séquence et une musique, pose un voile noir et le texte de la citation, sort une vidéo verticale 9:16.
5. L'API YouTube la met en ligne et le tableur note le lien.

L'« agent IA » se résume à un appel LLM qui écrit des citations. Le « 0 $ » est vrai : n8n auto-hébergé, DeepSeek gratuit, YouTube gratuit.

### Mon avis

La promesse ne tient pas pour Riot Machine. C'est une usine à vidéos de citations sur fond de stock, pas un outil de création. Rien ne sert pour un clip musical avec des personnages récurrents.

Risques, si quelqu'un voulait l'appliquer :
- Les conditions d'utilisation de YouTube interdisent de télécharger un contenu sans fonction de téléchargement fournie par YouTube ou sans autorisation. Le workflow repose sur yt-dlp.
- Depuis le 15 juillet 2025, YouTube a renommé sa règle « contenu répétitif » en « contenu inauthentique » et renforcé son application. Les vidéos produites en masse sur un même gabarit ne sont pas monétisables. La vidéo est antérieure à ce changement.
- Les « vues par millions » citées en ouverture sont celles d'un autre compte, pas le résultat de ce workflow.

### Ce qu'on reprend

Presque rien. Une seule idée générale : un tableur ou une base comme file d'attente, avec une colonne de statut que l'automate met à jour. Le studio le fait déjà avec `riot.db`.

### Prompts récupérés

Aucun. Le prompt DeepSeek des citations et le code sont dans sa communauté Skool, pas dans la description.

---

## 3. AI VIDEOS : « I Built My Own AI Studio on the Higgsfield API (No Coding) »

### Fiche

- URL : https://www.youtube.com/watch?v=0869g9pPJWI
- Chaîne : AI VIDEOS, 34 100 abonnés.
- Publiée le 30 septembre 2026. Durée 7 min 04 s. 11 791 vues.
- **Vidéo sponsorisée** : mot-dièse #HiggsfieldPartner, lien affilié en tête de description.
- Chapitres : console de l'API, porte-monnaie au lieu d'abonnement, prix par image et par seconde, prix bloqué un an, clé d'API, Claude Code construit l'app, premier appel, image Soul, vidéo Kling 3.0, facture, intérêt pour les développeurs, vidéo officielle de lancement, comment démarrer.
- Transcription : complète. Pas de prompt publié.

### Ce que contient la vidéo

1. Inscription sur console.higgsfield.ai. Un catalogue : Seedance 2.5, Kling 3.0, MiniMax H3, Higgsfield Soul et d'autres.
2. Paiement par porte-monnaie prépayé, sans abonnement. Prix par image ou par seconde. Un bouton compare les prix avec d'autres fournisseurs.
3. Remises annoncées : Kling 3.0 à -45 %, Seedance 2.5 à -30 %. 15 % de remise à l'inscription. La première semaine, un modèle d'image et deux modèles vidéo jusqu'à -50 %. 15 $ de crédits offerts si on vérifie une adresse mail professionnelle. Prix bloqué un an si on contacte les ventes pendant la première semaine.
4. Une seule clé pour tous les modèles, même forme de requête, 20 générations en parallèle.
5. Il demande à Claude Code de construire une mini-app : un champ de prompt, un bouton image (Soul), un bouton animation (Kling 3.0), le prix affiché avant chaque génération. L'app appelle d'abord un point d'**estimation** du prix : 0,004 $ pour une image Soul. Puis la requête renvoie un identifiant et un lien de statut. L'animation Kling 3.0 Turbo, 5 s en 720p, est estimée à environ 0,31 $ avec la remise de 45 %.
6. Arguments finaux : générations ratées non facturées, pas d'entraînement sur les données API, pas de filtre Higgsfield ajouté aux modèles.

### Ressemblances avec le studio

C'est le même principe que Riot Machine : Claude Code construit un studio maison sur une API de génération, et le coût s'affiche avant chaque dépense. La ressemblance s'arrête là. L'app de la vidéo fait deux boutons. Riot Machine a les portes de validation, les agents, le routage par coût, le budget par clip, le contrôle et le montage.

### Mon avis

C'est une publicité honnête dans sa forme (le partenariat est déclaré), mais une publicité. Aucun chiffre n'est vérifié par un tiers.
- La page de documentation publique (docs.higgsfield.ai) ne donne aucun prix. Je n'ai pas trouvé de source indépendante sur les prix de l'API.
- Les remises de la première semaine poussent à s'inscrire vite. La bonne attitude : ne s'inscrire que le jour où un test est prêt, pour utiliser la fenêtre de 7 jours.
- Higgsfield traîne des plaintes sur la facturation et les résiliations dans ses formules grand public (articles de GritDaily, WebProNews, avis Trustpilot repris par plusieurs sites ; je n'ai pas ouvert Trustpilot). Le porte-monnaie prépayé de l'API limite ce risque au montant chargé.
- Comparaison sur ce qu'on sait : Kling 3.0 Turbo 720p à environ 0,062 $/s remisé, contre Veo 3.1 Lite 720p sans son à 0,03 $/s et Veo 3.1 Fast 720p sans son à 0,08 $/s sur Vertex.

### Ce qu'on peut reprendre

1. **Higgsfield API comme fournisseur candidat**, marqué `to_test`. Son intérêt : Seedance 2.5 (la voie de Dan Kieft) et Soul, qu'on ne trouve pas ailleurs selon la vidéo. Le point d'estimation colle au principe « rien n'est dépensé avant ».
2. **L'appel d'estimation avant chaque génération**, quand un fournisseur en propose un, pour remplacer le prix calculé depuis `config/models.yaml`.
3. **L'affirmation « pas de filtre ajouté »** mérite un test avec la canon v1 de JJ, refusée par Veo. Non vérifié.

### Prompts récupérés

Un seul, cité oralement à 4 min 26 s : « an old fisherman on a wooden pier at dawn ». Rien d'autre n'est publié.

---

## 4. Tao Prompts : « How to Make a Professional Music Video with AI (Full Guide) »

### Fiche

- URL : https://www.youtube.com/watch?v=M7p7HrJjcdA
- Chaîne : Tao Prompts, 198 000 abonnés.
- Publiée le 6 juillet 2026. Durée 18 min 58 s. 67 998 vues.
- Description : lien affilié OpenArt, prompt de la planche de personnage, liste de 20 angles, lien vers ses guides PDF payants (Gumroad), Instagram.
- Chapitres : 0:00 intro, 0:57 personnage et décor, 2:32 angles avec le « burst mode », 6:10 chanteuse et lip-sync, 14:44 version 1 du clip, 15:17 clip fait par l'agent IA d'OpenArt, 17:57 la chanson avec Suno.
- Transcription : complète.

### Ce que contient la vidéo

Outils : OpenArt (plateforme qui regroupe les modèles), GPT Image 2 pour la planche, Seedance 2.0 pour la vidéo, Claude pour extraire des images d'une vidéo, Suno et Gemini pour la musique.

Méthode :
1. **Planche de personnage en 4K**, quatre colonnes (face, profil gauche, profil droit, dos), chaque colonne avec un plan en pied et un portrait.
2. **Plan de base** : la planche + une image de cage de verre, et le prompt « mets la femme dans la cage, change sa robe en satin rouge ».
3. **« Burst mode »** : une seule génération Seedance 2.0 de 7 s en 4K, avec la consigne de faire 20 plans en rafale et la liste de 20 angles. Il ne garde pas la vidéo. Il demande à Claude d'en extraire 20 images clés, qui deviennent les images de départ des plans. Le modèle ne respecte pas tous les angles, mais il en sort assez.
4. **Lip-sync par segments** : il coupe la chanson en segments qui se chevauchent d'une seconde (0-6 s, 5-14 s, 13-23 s). Chaque segment est exporté en **MP4 à image noire**. Dans le prompt : l'action, **les paroles du segment**, « un seul plan continu », « pas de sous-titres ». Il règle la durée un peu au-dessus de celle de l'audio (7 s pour 6 s). Il génère en 1080p.
5. **Expressivité** : une ligne « She gestures with her hands » suffit à rendre le jeu plus vivant.
6. **Angle imposé** : même si l'image de départ montre déjà l'angle, il faut le décrire dans le prompt. Sinon le modèle choisit son propre cadrage.
7. Au montage, il coupe le son des clips et garde la piste Suno. Il combine des morceaux de plusieurs prises.
8. L'agent « réalisateur » d'OpenArt fait un clip entier tout seul. Son verdict : plus rapide, moins bon, moins de plans chantés, transitions faibles.

### Mon avis

Bonne source pratique, moins exigeante que Dan Kieft sur la direction artistique. Deux techniques sont directement utiles : le burst mode pour fabriquer des angles cohérents d'un personnage, et le lip-sync par segments chevauchants avec les paroles dans le prompt. Il est affilié à OpenArt et ne donne aucun coût.

### Ce qu'on reprend

1. **Les paroles du segment dans le prompt de lip-sync**, et « single continuous shot, no subtitles ».
2. **Les segments audio qui se chevauchent** d'une seconde, pour avoir de la marge au montage.
3. **Le burst mode** comme alternative au pack d'angles quand les générateurs d'images gratuits ne tiennent pas l'identité. À tester en basse résolution d'abord : des images tirées d'une vidéo 720p sont petites, il faudra les agrandir (Topaz, 0,08 $ dans le studio).
4. **Toujours écrire l'angle dans le prompt vidéo**, même quand l'image de départ le montre.
5. **Sa planche en quatre colonnes** comme variante de celle de Dan Kieft.

### Prompts réutilisables ?

Oui pour deux d'entre eux : la planche et la liste d'angles. Les deux viennent de la description. La liste d'angles est écrite pour sa scène (cage de cristal) : il faut remplacer le décor. Les prompts de lip-sync ne sont pas publiés. La transcription n'en donne que des paraphrases, citées plus bas.

#### Prompt de la planche de personnage (description, mot pour mot)

```
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

#### Liste d'angles pour le burst mode (description, mot pour mot)

```
Camera Angles for Burst Mode:
1. Medium front shot, she sings directly into camera.
2. Close-up as she performs.
3. Tight close-up on her eyes looking through the crystal glass.
4. Profile close-up with crystal reflections across her face.
5. Three-quarter full-body shot inside the crystal cage.
6. Medium shot as she gently places a hand against the glass.
7. Close-up of her hand resting on the crystal wall.
8. Three-quarter angle as she turns toward camera.
9. Tight close-up as she closes her eyes during an emotional lyric.
10. Low-angle medium shot emphasizing the towering crystal cage.
11. Wide shot centered on the cage with crystal statues dancing around her.
12. Side profile as she leans against the crystal wall.
13. Medium front shot maintaining direct eye contact with camera.
14. Close-up framed through the edge of the crystal with soft refractions.
15. Medium full-body shot as she walks inside the cage.
16. Over-the-shoulder shot looking toward the crystal statues.
17. Low-angle full-body shot inside the crystal cage.
18. Tight close-up as she sings with a subtle head tilt.
19. Medium shot with her forehead resting against the crystal glass.
20. Wide shot revealing the full crystal cage surrounded by dancing crystal statues.
```

#### Prompts cités oralement (transcription, pas de texte publié)

- Burst mode, 3 min 41 s : « generate 20 shots in rapid fire inside a music video of the scene of the woman stuck inside the glass cage. She is wearing a bright red satin dress. » Suivi de la liste d'angles.
- Ligne ajoutée pour l'expressivité, 10 min 06 s : « She gestures with her hands. »
- Plan large, 10 min 46 s : « The woman wearing the red dress inside the glass cage dances and sings the song from the video. »
- Angle imposé, 11 min 33 s : « start with a side profile of the woman wearing the red dress inside the glass cage ».

---

## 5. Code With Yousaf : « Free Daily AI API Key! GLM-5.3 Flash + DeepSeek V4.1 Flash »

### Fiche

- URL : https://www.youtube.com/watch?v=OLftEewg4_s
- Chaîne : Code With Yousaf, 56 400 abonnés.
- Publiée le 29 octobre 2026. Durée 6 min 40 s. 17 940 vues.
- Description : liens vers zro.moonmath.ai (présentation, modèles, démarrage rapide). Avertissement de l'auteur : « Free usage limits, model availability, and daily reset rules may change. »
- Pas de chapitres. Transcription complète.

### Vérification : quel service, pour quoi faire

**La vidéo ne parle pas de génération vidéo.** Le titre et la transcription portent sur une clé d'API pour deux modèles de **texte** (LLM) : GLM-5.3 Flash et DeepSeek V4.1 Flash. Il les branche dans OpenCode, un agent de code, et leur envoie « hello ». Aucune image, aucune vidéo.

Le service : **Zro, de MoonMath.ai** (zro.moonmath.ai), un fournisseur d'inférence LLM.

### Conditions vérifiées

- **Gratuit** : la page des prix dit « Free plan for Flash models » et « Free daily usage on GLM-5.3 Flash and DeepSeek V4.1 Flash. Resets every day. » Elle ne donne **aucun volume**. La page « Plans and billing » de la documentation ne mentionne pas l'offre gratuite.
- **Volume réel** : mesuré par le youtubeur lui-même, 8 requêtes ont consommé 8 % du quota du jour. Il en déduit environ 100 petites requêtes par jour. Sa conclusion : « the free limit is low », bon pour tester ou pour des étudiants.
- **Formules payantes** : Pro à 20 $ par mois (budget de 40 $), Max à 60 $ (budget de 120 $). Les abonnés d'avant le changement d'octobre 2026 gardent 60 $ et 300 $ de budget. L'offre a donc déjà été réduite une fois.
- **Prix à l'usage** : GLM-5.3 Flash à 0,15 $ / 0,50 $ par million de jetons en entrée / sortie, DeepSeek V4.1 Flash à 0,30 $ / 1,10 $.
- **Clé** : chaque clé a un plafond de dépense (25 $ proposé par défaut dans la vidéo), une région, une date d'expiration, et se révoque.
- **Conditions d'utilisation** : interdiction de revendre ou de sous-licencier l'accès ou les clés, de les partager, d'ouvrir plusieurs comptes pour cumuler les offres gratuites. Pas de conservation des prompts et réponses, pas d'entraînement sur les requêtes, selon leurs termes. **Aucune clause de droit applicable**, et pas d'adresse de la société.

### Réponses aux questions

- **Vraiment gratuit ?** Oui, pour un petit volume de texte, sans volume garanti.
- **Durable ?** Rien ne le garantit. Le service peut changer, il a déjà réduit ses budgets en octobre 2026, et le youtubeur prévient lui-même.
- **Limites** : environ 100 petites requêtes par jour, deux modèles « Flash » seulement, aucune image ni vidéo.
- **Filigrane** : sans objet, c'est du texte.
- **Revente d'accès** : interdite par les conditions.
- **Sécurité de la clé** : la clé reste dans `.env`, jamais dans le code ni le navigateur. Fixer le plafond de dépense au minimum et une date d'expiration. Les conditions ne disent pas qui répond d'une clé volée, mais elles rendent le titulaire responsable de tout ce qui passe par son compte.
- **Risque principal** : un opérateur peu identifié, sans juridiction déclarée.

### Mon avis

Hors sujet pour la vidéo. Le titre parle d'« AI API Key » : la promesse « gratuite pour générer des vidéos » ne figure ni dans le titre, ni dans la description, ni dans la vidéo. Usage possible pour le studio : un LLM gratuit de secours pour réécrire des prompts. Le studio travaille déjà avec Claude Code : je ne vois pas de raison de l'ajouter.

### Prompts récupérés

Aucun, à part le « hello » de test.

---

## 7. Ressources à capitaliser

| Ressource | Accès | Ce qu'elle apporte |
|---|---|---|
| Page de prompts de Dan Kieft (suno-seedance-music-video.vercel.app) | gratuite | Tous les prompts du clip : Suno, visage, planche, décors, angles, prompt en un coup, lip-sync |
| Fichier skill « seedance-25-prompt-builder.md » (Dropbox) | gratuit, copie locale | Structure de prompt par étapes, règles de références, syntaxe audio, conseils anti-refus de ressemblance, liste de contrôle. À adapter : retirer la ligne finale affiliée. Le fichier annexe n'est pas publié |
| Communauté Skool NextGenAI de Dan Kieft (skool.com/nextgenai) | gratuite « pour l'instant », 66 200 membres | Bibliothèques de prompts, gabarits, comparatifs. Pas exploré |
| aicameramovements.com | gratuit, éditeur non nommé | 46 mouvements de caméra en 7 catégories, avec un aperçu et un prompt à copier pour chacun. Bon pour le guide du prompteur |
| Description de la vidéo Tao Prompts | gratuite | Prompt de planche en quatre colonnes, liste de 20 angles |
| Guides PDF de Tao Prompts (taoprompts.gumroad.com) | payants, non achetés | Mouvements de caméra dans Kling (10 $), tous les angles dans Nano Banana Pro (18 $), design de personnage (5 $), composition cinématographique (5 $), photo cinématographique (10 $), angles dans Midjourney (10 $), photoréalisme Midjourney V6 (10 $). Le plus utile pour le studio : Kling camera motion |
| Documentation Higgsfield API (docs.higgsfield.ai, index llms.txt) | gratuite | De quoi écrire un adaptateur si on teste Higgsfield. Pas de prix publics |
| Page des prix Vertex AI | officielle | Prix Veo et Omni Flash à jour. À relire avant chaque mise à jour de `config/models.yaml` |
| Page d'aide Google Flow sur les crédits | officielle | Coût des essais manuels Veo gratuits |
| Billet Segmind sur Seedance 2.5 et article Hackernoon sur les brouillons | gratuits | Prix par seconde mesurés, calcul du seuil de rentabilité d'un brouillon |
| Stems de Suno (Download, puis Stems) | dans Suno | Voix principale séparée des chœurs et ad-libs, pour un lip-sync propre |
| Zro de MoonMath | gratuit, limité | LLM texte gratuit de secours. Faible intérêt |
| Workflow d'Andy Lo | réservé à sa communauté | Aucun intérêt pour le studio |

---

## 8. Sources

Vidéos (métadonnées et transcriptions récupérées avec yt-dlp le 1er novembre 2026) :
- Dan Kieft, https://www.youtube.com/watch?v=BKDrtzJktO0
- Andy Lo, https://www.youtube.com/watch?v=PeelSIEewUY
- AI VIDEOS, https://www.youtube.com/watch?v=0869g9pPJWI
- Tao Prompts, https://www.youtube.com/watch?v=M7p7HrJjcdA
- Code With Yousaf, https://www.youtube.com/watch?v=OLftEewg4_s

Pages liées aux vidéos :
- Page de prompts de Dan Kieft : https://dankieft.com/aimusicvideo, redirigée vers https://suno-seedance-music-video.vercel.app/
- Skill de Dan Kieft : https://www.dropbox.com/scl/fi/pkbz11zxe2qghr10tyquk/seedance-25-prompt-builder.md?rlkey=8mb3p4inv4zn6jlm16ygg0hfv&st=hwhdewyz&dl=0
- Communauté NextGenAI : https://www.skool.com/nextgenai/about
- Mouvements de caméra : https://aicameramovements.com/
- Guides de Tao Prompts : https://taoprompts.gumroad.com/
- Documentation Higgsfield : https://docs.higgsfield.ai
- Zro de MoonMath : https://zro.moonmath.ai/overview, https://zro.moonmath.ai/pricing, https://zro.moonmath.ai/docs/models, https://zro.moonmath.ai/docs/plans, https://zro.moonmath.ai/terms

Prix et documentation officiels :
- Prix Vertex AI (Veo, Omni Flash) : https://cloud.google.com/vertex-ai/generative-ai/pricing
- Référence de l'API Veo sur Vertex : https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation (version allemande : ?hl=de)
- Premier et dernier image avec Veo : https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-first-and-last-frames
- Crédits Google Flow : https://support.google.com/flow/answer/16526234

Articles et analyses :
- Higgsfield, prix de Seedance 2.5 (20 octobre 2026) : https://higgsfield.ai/blog/seedance-2-5-pricing-2026
- Segmind, prix de Seedance 2.5 testés (7 août 2026) : https://blog.segmind.com/seedance-2-5-api-pricing-5-clips-tested-real-costs/
- Hackernoon, le mode brouillon (22 octobre 2026) : https://hackernoon.com/ai-video-draft-mode-doesnt-make-renders-cheaper-it-makes-mistakes-cheaper
- Atlas Cloud, prix de Seedance 2.5 par fournisseur : https://ask.atlascloud.ai/seedance-2-5-api-transparent-pricing-no-enterprise-contract
- Guide des brouillons 480p : https://aivideomaker.ai/blog/free-ai-video-generator-480p-drafts
- Prix Veo 3.1 par niveau (tiers) : https://benchlm.ai/media-pricing/veo
- Crédits gratuits des générateurs (sources intéressées) : https://dreamina.capcut.com/ai-video/free-ai-video-generators-recurring-credits-vs-trials-2026, https://www.krea.ai/blog/best-free-ai-video-generators-in-2026
- Critiques de Higgsfield : https://gritdaily.com/kazakh-startup-higgsfield-criticism/, https://www.webpronews.com/higgsfields-300-million-rocket-ride-how-an-ai-video-startups-meteoric-growth-unleashed-a-firestorm-of-creator-backlash-and-ethical-reckoning
- Comparatif Higgsfield et Kling : https://creatify.ai/blog/higgsfield-vs-kling-ai-quality-cost-per-second-and-which-to-use-for-ads-in-2026
- Règle YouTube sur le contenu inauthentique : https://www.tubefilter.com/2025/07/03/youtube-crackdown-repetitive-non-original-content/amp/, https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/
- Conditions d'utilisation de YouTube : https://www.youtube.com/t/terms

Documents internes relus pour la comparaison : `/home/michael/projets/riotmachine/docs/PROCESS.md`, `/home/michael/projets/riotmachine/docs/FOURNISSEURS.md`, `/home/michael/projets/riotmachine/riotmachine/providers/vertex.py`.

Contenus non accessibles :
- Le fichier `references/advanced-techniques.md` cité par le skill de Dan Kieft : non publié.
- Les modèles de workflow d'Andy Lo : réservés à sa communauté Skool.
- Les prompts de lip-sync de Tao Prompts : non publiés, seulement paraphrasés à l'oral.
- Les prix de l'API Higgsfield : non publiés sur la documentation, seulement montrés dans la vidéo sponsorisée.
- Le volume exact de l'offre gratuite de Zro : non publié.
- La version anglaise de la référence de l'API Veo : page non extractible ; la version allemande a servi.
