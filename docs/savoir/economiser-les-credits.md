# Économiser les crédits

Comment obtenir un résultat pro au moindre coût : prix réels, quand faire un brouillon, quels modèles, quelles astuces. Recherche du 1er novembre 2026.


Chaque astuce est suivie de sa source et de ce qu'elle donne pour Riot Machine. « Déjà fait » renvoie à `docs/PROCESS.md` ou `docs/FOURNISSEURS.md`.

### Les prix qui commandent tout (Vertex AI, page officielle lue le 1er novembre 2026)

Prix par seconde de vidéo :

| Modèle | Avec son 720p | Avec son 1080p | Sans son 720p | Sans son 1080p | 4K sans son |
|---|---|---|---|---|---|
| Veo 3.1 | 0,40 $ | 0,40 $ | 0,20 $ | 0,20 $ | 0,40 $ |
| Veo 3.1 Fast | 0,10 $ | 0,12 $ | 0,08 $ | 0,10 $ | 0,25 $ |
| Veo 3.1 Lite | 0,05 $ | 0,08 $ | 0,03 $ | 0,05 $ | non |

Gemini Omni Flash sur Vertex est facturé en jetons : 17,50 $ par million de jetons de vidéo en sortie. La page donne 1 931 jetons par seconde en 360p, 5 792 en 720p, 8 688 en 1080p. Mon calcul : environ 0,034 $/s en 360p, 0,10 $/s en 720p, 0,15 $/s en 1080p, son compris.

### Itérer en image avant la vidéo

- Source : Dan Kieft (« les images coûtent très peu, essayez plusieurs modèles ») ; guide aivideomaker.ai (figer l'image avant de dépenser en vidéo).
- Studio : déjà fait (visuel draft gratuit, validation avant toute vidéo). À ajouter : la planche à trois panneaux de Dan comme référence, et la règle « écrire l'angle dans le prompt vidéo » de Tao.

### Tests en basse résolution et en durée minimale

- Source : Dan Kieft à 15 min 13 s (« réglage plus bas d'abord ») ; Segmind (480p à 0,1065 $/s, 720p à 0,2389 $/s, soit 2,25 fois plus) ; Higgsfield (8 s : 24 crédits en 480p, 56 en 720p, 128 en 1080p).
- Nuance importante (Hackernoon, 22 octobre 2026, d'après Segmind) : le brouillon ne rend pas le plan moins cher, il rend l'erreur moins chère. Sur une seule prise réussie, brouillon + final coûte 18 % de plus. Le seuil de rentabilité est de 1,22 prise rejetée. Une prise ratée puis une bonne : 32 % d'économie. Quatre ratées : 62 %.
- Règle qui en découle : faire un brouillon seulement quand on sait nommer le risque (mouvement de caméra jamais testé, lip-sync, référence de personnage pas encore éprouvée, plan cher). Pas de brouillon « au cas où ».
- **Piège propre à Veo** : en Veo 3.1 standard, le 720p et le 1080p coûtent le même prix. Le 720p n'a aucun intérêt sur ce modèle. En Fast, le 1080p ne coûte que 0,02 $/s de plus que le 720p : agrandir un 720p ne vaut le coup que si l'agrandissement coûte moins de 0,02 $/s.
- Studio : la règle des tests au minimum existe déjà (2 s ~420p, ou 4 s 720p chez Veo). À ajouter : la décision « brouillon ou pas » plan par plan, selon le risque.

### Modèles « fast » et « lite »

- Source : Vertex. Lite sans son en 720p à 0,03 $/s, soit 0,12 $ pour un plan de 4 s, presque 7 fois moins que Veo 3.1 standard.
- Studio : Lite est marqué `to_test` car l'image vers vidéo n'était pas confirmée. Un test de 4 s en 720p sans son coûte 0,12 $ sur les crédits. C'est le test le plus rentable à faire.
- Omni Flash en 360p (environ 0,034 $/s) peut servir de brouillon de mouvement sur les crédits Google. À tester.

### Seeds

- Source : référence de l'API Veo sur Vertex (version allemande lue ; la version anglaise n'a pas pu être extraite). Le paramètre `seed` (uint32) : même seed et mêmes paramètres donnent les mêmes vidéos.
- Limite : changer la résolution, le modèle ou le prompt change les paramètres. Un brouillon en Fast ne se reproduit donc pas à l'identique en Veo 3.1 standard. Segmind affirme qu'un seed fixe fait correspondre l'aperçu 480p et le rendu 720p chez Seedance 2.5 : je ne l'ai pas vu confirmé ailleurs.
- Studio : le code Vertex passe déjà un `seed` (`riotmachine/providers/vertex.py`, ligne 70). Usage utile : garder le seed d'une prise presque bonne et ne changer qu'une ligne du prompt.

### Premier et dernier image

- Source : référence de l'API Veo. `lastFrame` est accepté par `veo-3.1-generate-001`. Le guide Google « first and last frames » donne des durées de 4, 6 ou 8 s.
- Intérêt : imposer la fin du plan réduit les mouvements imprévus, donc les reprises. La dernière image d'un plan peut servir de première image au suivant pour un raccord. Les images de fin se fabriquent gratuitement (FLUX.1 Kontext, Qwen Image Edit sur Hugging Face).
- L'extension de vidéo n'est documentée que pour les modèles en préversion (`veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`).

### Découper en plans courts, ou les regrouper

- Chez Veo, un plan de moins de 4 s se paie 4 s. Le studio a déjà vu que fusionner deux plans voisins coûte moins cher.
- Chez Seedance 2.5, une prise de 15 s peut contenir 15 coupes (Dan Kieft) : 0,24 $ par plan en 720p chez Segmind.
- Tao Prompts : segments de lip-sync de 6 à 10 s qui se chevauchent d'une seconde, pour garder de la marge au montage.

### Refaire un passage plutôt que tout le plan

- Au montage : Dan et Tao coupent la bonne seconde et combinent plusieurs prises au lieu de relancer.
- Remplacement de personnage : Dan garde un mouvement réussi et change le personnage avec Higgsfield Genjutsu.
- Lip-sync : Tao refait seulement le segment raté, pas tout le plan. Dan refait seulement la voix fautive grâce aux stems.
- Studio : la route `finition` permet déjà de refaire seulement le lip-sync.

### Upscale à la fin

- Studio : déjà fait (Topaz à 0,08 $ pour les images, SeedVR pour la vidéo, retouche des visages désactivée).
- Rappel Vertex : générer directement en 1080p coûte souvent à peine plus que le 720p. Comparer avant d'agrandir.

### Crédits gratuits quotidiens des plateformes (usage manuel, sur leur site)

- **Google Flow** (page d'aide officielle) : 50 crédits par jour, avec ou sans abonnement, non cumulables. Veo 3.1 Lite coûte 10 crédits, Fast 20, Quality 100 (vidéo de 8 s). Cela fait 5 essais Lite ou 2 essais Fast gratuits par jour. AI Plus ajoute 200 crédits par mois, AI Pro 1 000.
- **Kling** : environ 66 crédits par jour, sortie avec filigrane (sites tiers, chiffres non officiels).
- **Dreamina** (Seedance) : 120 crédits par jour selon les guides de Dreamina. Moins qu'un clip Seedance 2.5 en 1080p d'après Higgsfield. Possiblement sans filigrane selon des sources intéressées.
- **PixVerse** : 30 à 60 crédits par jour selon les sources. **Vidu** : environ 20 crédits par jour. **Hailuo** : chiffres contradictoires.
- Studio : la règle existe déjà. Ces crédits servent à tester un prompt à la main, jamais par automate (conditions d'utilisation, filigrane).

### Plans d'abonnement

- **Higgsfield Plus** : 49 $ par mois pour 1 000 crédits, soit environ 140 s de Seedance 2.5 en 720p. Ultra : 3 000, 6 000 ou 9 000 crédits pour 129, 220 ou 310 $. Les crédits expirent (90 jours selon des sites tiers).
- **Google AI Pro** : 1 000 crédits Flow par mois. Je n'ai pas vérifié son prix.
- Pour le studio : un abonnement web ne se pilote pas par API. L'API à l'usage reste la bonne voie. Un abonnement ne vaut que pour un usage manuel intense pendant un mois.

### Éviter les rerolls inutiles

- Prompt structuré par étapes, avec état final et liste d'exclusions (skill de Dan).
- Durée réglée égale à la durée écrite dans le prompt (Dan, 15 min 30 s).
- Paroles dans le prompt de lip-sync (Tao).
- Angle écrit dans le prompt, même s'il est visible sur l'image (Tao).
- Audio en MP4 noir et stem de la seule voix voulue (Dan, Tao).
- Émotions traduites en signes visibles : souffle, regard, mains, mâchoire (skill de Dan).
- Un seul changement principal par étape (skill de Dan).
- Générations ratées ou refusées en validation : non facturées chez Segmind (constaté) et chez Higgsfield (annoncé). Chez Veo, le studio a constaté qu'un refus à l'entrée ne produit rien.

### Le calendrier des crédits Google

- Les 300 $ courent jusqu'au 27 janvier 2027. Veo 3.1 GA est annoncé retiré au plus tôt le 17 novembre 2026. Si le retrait tombe, il faudra basculer les crédits sur le successeur (Gemini Omni Flash). Ses prix Vertex sont connus, voir le tableau plus haut.

---

