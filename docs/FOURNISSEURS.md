# Fournisseurs et modèles vidéo

Complément de [PROCESS.md](PROCESS.md), section 5. Prix et spécifications vérifiés
le 22 octobre 2026 sur les documentations officielles. **Les prix bougent vite** :
à revérifier régulièrement, et à corriger dans `config/models.yaml`.

## La règle

1. Le palier du plan (`eco`, `standard`, `premium`) vient de son mouvement et de son cadrage.
2. Parmi les offres des fournisseurs **branchés** (clé présente dans `.env`) qui
   tiennent ce palier, le format du clip et la durée du plan, le routage prend la
   moins chère, **tout compris** (vidéo draft, vidéo HD, lip-sync).
3. Une offre couverte par des **crédits gratuits ou prépayés** compte pour 0 $ :
   elle passe devant tant que l'enveloppe n'est pas vide.
4. Une offre marquée `to_test` n'est jamais choisie automatiquement. Michael peut
   la choisir à la main dans le plan vidéo ; une fois jugée bonne, on retire la marque.
5. Le son natif est toujours coupé (la musique vient de Suno). Quand un modèle ne
   permet pas de le couper, la piste est retirée après téléchargement, mais on paie
   le tarif avec son.

Dans la régie, la page **Fournisseurs** montre l'état de chacun, les crédits
restants, toutes les offres classées par coût et le carnet de rodage.

## Les fournisseurs branchés

### fal.ai (indispensable)

- **Rôle** : visuels draft (Nano Banana), visuel HD (Topaz), vidéo HD (SeedVR),
  lip-sync, et une partie des modèles vidéo (Kling 3, Seedance 2, Wan 3, MiniMax H3).
- **Clé** : fal.ai/dashboard/keys → `.env` : `FAL_KEY`. Sans elle, toute la machine
  reste en simulation.

### Google Cloud, Vertex AI (Veo 3.1)

- **Rôle** : Veo 3.1 Fast et Veo 3.1, générés directement en 1080p, sans son.
- **Prix sans son** : Veo 3.1 Fast 0,08 $/s en 720p et 0,10 $/s en 1080p ;
  Veo 3.1 0,20 $/s ; Veo 3.1 Lite 0,03 à 0,05 $/s (préversion, image vers vidéo
  non confirmé : marqué `to_test`).
- **Crédits** : c'est la seule voie payable par les **300 $ de l'essai Google
  Cloud**. L'API Gemini (AI Studio) et Runway ne le sont pas.
- **Limites** : formats 16:9 et 9:16 seulement (pas de carré) ; durées 4, 6 ou 8 s ;
  région us-central1. Les modèles GA ont une date de retrait annoncée au plus tôt
  le **17/11/2026** : surveiller leur successeur.

**Mise en place (à faire par Michael, une fois)**

1. Créer le compte d'essai sur cloud.google.com/free, avec un compte Google
   éligible et une carte bancaire. Le crédit vaut 90 jours. Passer en compte payant
   n'est pas obligatoire ; si on le fait, le crédit restant est conservé.
2. Dans la console : créer un projet, noter son identifiant, puis activer l'API
   « Vertex AI ».
3. Créer un compte de service avec le rôle **Vertex AI User**.
4. Au choix :
   - **clé API liée au compte de service** (le plus simple) : page Identifiants →
     Créer une clé API → cocher « Authentifier les appels via un compte de service »
     → restreindre la clé à l'API Vertex AI. Mettre `VERTEX_API_KEY` dans `.env` ;
   - ou **clé JSON du compte de service** : la télécharger sur le PC et mettre son
     chemin dans `GOOGLE_APPLICATION_CREDENTIALS`.
5. Dans `.env` : `VERTEX_PROJECT=<identifiant du projet>`.
6. Dans `config/models.yaml`, ouvrir l'enveloppe :
   `credits: {label: "crédits Google Cloud", usd: 300, start: "<date>", expires: "<date + 90 jours>"}`.
7. Lancer un premier plan vidéo de test. Un refus 403 ou 429 au premier appel
   signalerait une restriction des comptes d'essai sur Veo (cas évoqué sur des
   forums, non documenté par Google).

### Kling AI, API officielle

- **Rôle** : Kling 2.6 et 2.5 Turbo, **les moins chers en 1080p** (0,07 $/s, 5 ou
  10 s) ; Kling 3.0 (0,112 $/s en 1080p, 3 à 15 s).
- **Paiement** : prépayé par packs non remboursables (pack d'essai annoncé à
  9,80 $, à vérifier à l'achat). L'abonnement du site web ne donne pas accès à l'API.
  Déclarer le pack comme enveloppe `credits` du fournisseur `kling`.
- **Clé** : console développeur de kling.ai → clé API → `.env` : `KLING_API_KEY`.
- **Limites** : pas de negative prompt (les interdits passent dans le prompt) ; la
  sortie suit le ratio de l'image de départ ; vidéos effacées après 30 jours.

### Runway

- **Rôle** : une seule clé pour Veo 3.1 Fast (0,10 $/s), Kling 3.0 Pro (0,12 $/s),
  Seedance 2.5 (0,30 $/s en 720p), Gen-4 Turbo (0,05 $/s en 720p), Hailuo 3,
  et Grok Imagine 1.5 Lite (0,03 $/s en 720p, qualité à tester).
- **Paiement** : crédits achetés à 0,01 $ l'unité.
- **Clé** : dev.runwayml.com → `.env` : `RUNWAYML_API_SECRET`.
- **Limites** : image de départ de 5 Mo maximum une fois encodée ; liens de sortie
  valables 24 à 48 h (la machine télécharge tout de suite).

### Google Gemini API (AI Studio)

- **Rôle** : Gemini Omni Flash (0,10 $/s en 720p, 0,15 $/s en 1080p). Veo 3.1 n'y
  est plus disponible depuis le 22/10/2026.
- **Limites** : le son ne peut pas être coupé (retiré après coup, mais payé) ;
  pas de carré ; non payable par les crédits Google Cloud.
- **Clé** : aistudio.google.com → `.env` : `GEMINI_API_KEY`.

## Crédits gratuits des applications web

Google Flow, Kling, Dreamina, PixVerse, Vidu et Hailuo offrent des crédits
quotidiens, mais **seulement dans leur site ou leur application**, pas par API.
Les automatiser voudrait dire piloter ces sites dans un navigateur : c'est fragile
et souvent contraire à leurs conditions d'utilisation, et leurs sorties portent
souvent un filigrane. On s'en sert à la main pour **tester des prompts** avant de
lancer une génération payante.

## Ajouter un fournisseur ou une offre

- **Nouvelle offre chez un fournisseur branché** : ajouter une entrée dans
  `models:` de `config/models.yaml` (fournisseur, prix, durées, formats, paliers
  tenus, `to_test: true` au début). Aucun code à écrire.
- **Nouveau fournisseur** : écrire son adaptateur dans `riotmachine/providers/`
  (`submit`, `status`, `result`, `download`), le déclarer dans `providers:` de la
  config, l'ajouter à `IMPLEMENTED_PROVIDERS` dans `riotmachine/routing.py`, et
  écrire son test dans `tests/test_providers.py`.
