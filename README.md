# Riot Machine

Le studio multi-agent qui produit les clips du groupe IA, à commencer par **JJ**.

Tu es scénariste et réalisateur : tu déposes un morceau et un script, tu valides
à chaque étape depuis ton téléphone, et une équipe d'agents Claude s'occupe de
toute la production technique.

```
 toi (régie web + Telegram)                      PC Linux de la maison
 ─────────────────────────                      ──────────────────────────────────────────
 dépose morceau + script  ───────────────────▶  base SQLite + studio/ (fichiers)
                                                      │
 « 6 images à valider »   ◀── Telegram ───────  worker (tourne en continu)
                                                 ├─ suit les générations fal toutes les 30 s
 valide / commente        ───────────────────▶  ├─ lance rendu final + lip-sync
                                                 └─ réveille Claude Code : claude -p "/prod <clip>"
                                                        └─ orchestrateur + 7 agents (ton abonnement Claude)
                                                              │
                                                     fal.ai (images, vidéos, upscale, lip-sync)
```

## L'équipe

| Agent | Rôle | Modèle |
|---|---|---|
| orchestrateur | chef de production : fait avancer les plans, trie tes retours | défaut de Claude Code |
| `script-doctor` | relit ton script, transforme tes plans (et tes timecodes) en plans de production | Opus |
| `directeur-casting` | fabrique les packs de référence photoréalistes des personnages | Opus |
| `storyboard` | image clé de chaque plan (point de départ de la vidéo) | Sonnet |
| `controleur` | contrôle indépendant : identité, mains, artefacts, avant que tu ne voies | Sonnet |
| `routeur` | choisit le modèle vidéo le moins cher qui fera le travail | Sonnet |
| `prompteur` | écrit le prompt vidéo adapté au modèle choisi | Sonnet |
| `finition` | dépanne le rendu final, l'upscale et le lip-sync | Sonnet |

Tu valides à quatre moments : le **découpage**, les **images**, les **drafts**
(480p) et les **finals**. Tout le reste est automatique.

## Comment un clip avance

| Étape | Qui produit | Ce que tu fais |
|---|---|---|
| 1. Concept | Toi | Régie → **Nouveau clip** : morceau, voix isolée, pitch, concept, dossier de réalisation (PDF, Word, texte, images), paroles, format, budget. |
| 2. Découpage | Toi, puis le `script-doctor` | Onglet **Découpage** : tes blocs (intro, couplet, refrain…) et les plans de chaque bloc avec leurs timecodes. Ou bien le découpage est dans ton dossier. Onglet **Dossier** → « Envoyer au script doctor ». Il complète chaque plan (cadrage, mouvement, plan chanté), tu valides. |
| 3. Visuel draft | `storyboard` puis `controleur` | Tu valides chaque visuel, ou tu écris ce qu'il faut changer. |
| 4. Visuel HD | Automatique | L'image validée est agrandie sans être redessinée. Le `controleur` vérifie qu'elle est fidèle ; tu n'es sollicité qu'en cas d'écart (comparateur à curseur). |
| 5. Plan vidéo | `routeur` puis `prompteur` | Tu vois le fournisseur, le modèle, sa raison, le coût estimé et le prompt. Tu peux changer de modèle ou retoucher le prompt. Rien n'est dépensé avant ta validation. |
| 6. Vidéo draft | Automatique, puis `controleur` | Tu valides la vidéo draft. |
| 7. Vidéo HD + lip-sync | Automatique | Agrandissement de la draft validée, puis lip-sync des plans chantés. Tu valides le final. |
| 8. Montage | Automatique | « Monter le clip » assemble la meilleure version de chaque plan sur le morceau, à tout moment. |

Chaque plan avance à son rythme. Dans l'onglet **Plans**, la timeline du morceau
montre les blocs et l'état de chaque plan ; les blocs se replient ; un clic sur
un plan ouvre son détail avec ses six étapes (visuel draft, visuel HD, plan vidéo,
vidéo draft, vidéo HD, lip-sync). « Prochain à valider » enchaîne les validations.

Quand tu demandes une modif, écris simplement ce que tu veux. L'orchestrateur
renvoie le plan au bon endroit : visuel (`storyboard`), HD, mouvement
(`prompteur`), rendu insuffisant (`routeur`, qui monte d'un palier) ou finition.

## Les fournisseurs vidéo

`config/models.yaml` déclare les fournisseurs. **fal.ai** est branché (une seule
clé pour Kling, Seedance, Wan, MiniMax et les outils de finition). Kling en direct,
Google Veo et Runway sont déclarés mais pas encore branchés : ils apparaissent
grisés dans le choix du modèle. `riot providers` donne l'état de chacun.

## Les paliers et les coûts

Définis dans `config/models.yaml` (prix fal vérifiés le 22/10/2026) :

| Palier | Modèle | Pour | Ordre de prix |
|---|---|---|---|
| eco | Wan 3.0, draft 480p + upscale | plans calmes, gros plans, objets | ~0,25 $ le draft de 5 s |
| standard | Kling 3 standard | marche, travelling, gestes | ~0,42 $ le plan de 5 s |
| premium | Seedance 2.0, draft 480p + upscale | danse, plans larges animés | ~0,68 $ le draft de 5 s |

S'y ajoutent l'image clé (~0,08 $), l'upscale (~0,05 $/s) et le lip-sync
(~0,08 $/s, plans chantés seulement). Les vidéos sont générées **sans son** : la
musique vient de Suno, ça évite de payer 50 à 100 % de plus.

Chaque clip a un budget (80 $ par défaut). Les agents s'arrêtent et te
préviennent s'il est atteint ; tu peux le changer dans la régie.

> Les endpoints Veo 3.1 de fal sont annoncés dépréciés le 17/11/2026 : ils ne
> sont pas utilisés.

## Le référentiel des personnages

Dans la régie, onglet **Personnages** :

1. Tu déposes le **brouillon de la canon** (l'image que tu as faite).
2. La **canon HD** est générée seule. Tu la compares au brouillon avec le curseur :
   tu la valides, tu la fais refaire (avec l'autre outil d'agrandissement), ou tu
   gardes le brouillon tel quel.
3. Tu écris tes **instructions** pour le pack (angles, plans en pied, expressions,
   lumières, tenues, détails) et tu lances le pack : le `directeur-casting` le génère.
4. Tu gardes ou rejettes chaque image, puis tu **valides la version**.

```
studio/characters/jj/
├── character.yaml        fiche (import initial)
├── brief-v2.md           brief du prochain pack, avec les points à trancher
├── v1/                   une version = un pack figé
│   ├── canon.jpg         l'image de vérité, référence n°1 de tous les appels
│   ├── adn.md            identité (texte injecté dans les prompts), règles Toujours / Jamais
│   ├── silhouette.md
│   └── turnaround/  fullbody/  expressions/  lighting/  details/
└── looks/<look>/         tenues et styles, réutilisables d'un clip à l'autre
```

- Un clip **épingle** une version : faire évoluer JJ en v2 ne casse pas un clip en cours.
- Seule une version que tu as **validée** peut être castée.
- Les agents proposent, toi seul choisis la canon et valides une version.
- Un groupe (`studio/groups/`) référence des personnages et leurs versions.

Le brief
`brief-v2.md` liste ce qu'il faut trancher pour la v2 de JJ (taches de rousseur,
reflets, yeux) : les deux images actuelles ne décrivent pas tout à fait la même
personne, c'est la première cause du manque de réalisme.

---

## Installation sur le PC Linux

### 1. Le dépôt et les dépendances

```bash
sudo apt install git python3 python3-venv ffmpeg rsync
git clone https://github.com/mimimimichel/riotmachine.git ~/riotmachine
cd ~/riotmachine
bash deploy/install.sh
sudo loginctl enable-linger $USER     # services actifs sans session ouverte
```

Le script crée l'environnement Python, le fichier `.env`, la base, et lance
trois services utilisateur : la régie, le worker et la sauvegarde quotidienne.

### 2. Claude Code avec ton abonnement

Installe Claude Code (doc : https://code.claude.com/docs/en/setup), puis :

```bash
cd ~/riotmachine
claude          # puis /login avec ton compte Claude (Pro ou Max)
```

Vérifie que **`ANTHROPIC_API_KEY` n'est pas définie** dans ton environnement :
sinon Claude Code facture l'API au lieu de l'abonnement (le worker la retire de
toute façon pour ses propres appels).

Les permissions des agents sont dans `.claude/settings.json` : ils peuvent
utiliser `riot`, `ffmpeg`, lire le projet et écrire dans `studio/`, mais pas
valider à ta place, supprimer des fichiers, toucher à `config/` ou lire `.env`.

### 3. fal.ai

Crée une clé sur https://fal.ai/dashboard/keys, ajoute du crédit, et mets-la dans
`.env` (`FAL_KEY=…`). Sans clé, tout tourne en **simulation** : images et vidéos
factices, aucune dépense.

### 4. Tailscale (accès depuis ton téléphone)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Installe l'app Tailscale sur ton téléphone avec le même compte. La régie est
alors sur `http://<nom-du-pc>:8420`. Mets cette adresse dans `.env`
(`RIOT_REGIE_URL`) pour que les liens des notifications fonctionnent. Pour
n'écouter que sur Tailscale : `RIOT_REGIE_HOST=<IP Tailscale du PC>` (`tailscale ip -4`).

### 5. Telegram (notifications)

1. Sur Telegram, écris à **@BotFather** → `/newbot` → récupère le token.
2. Envoie un message à ton nouveau bot, puis ouvre
   `https://api.telegram.org/bot<TOKEN>/getUpdates` : ton identifiant est dans `chat.id`.
3. Mets `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` dans `.env`, puis :

```bash
systemctl --user restart riotmachine-worker
.venv/bin/riot notify "Riot Machine est en ligne"
```

### 6. Essayer sans rien dépenser

```bash
.venv/bin/riot demo
```

Crée « Premier clip (démo) », entièrement simulé, avec des plans à toutes les
étapes : de quoi découvrir la régie. Les clips `demo-…` ne déclenchent jamais
d'agent ni de dépense. `riot demo --reset` le supprime.

---

## Au quotidien

| Je veux… | Où |
|---|---|
| démarrer un clip | régie → Studio → Nouveau clip (ou `/nouveau-clip` dans Claude Code) |
| valider, commenter, comparer les versions | régie → le clip → Plans (« Prochain à valider ») |
| voir un plan dans le morceau | bouton « Lire dans le morceau » ou clic sur la bande |
| un montage du clip | bouton « Monter le clip » |
| créer ou faire évoluer un personnage | régie → Personnages |
| faire le point | `/etat` dans Claude Code, ou `riot status` |
| relancer l'orchestrateur à la main | `/prod <clip>` dans Claude Code |

Commandes utiles :

```bash
riot status [clip]                 # vue d'ensemble
riot cost <clip>                   # détail des dépenses
riot events --clip <clip>          # journal
riot backup /media/disque-externe  # sauvegarde à la demande
journalctl --user -u riotmachine-worker -f    # ce que fait le worker
ls studio/logs/                    # journaux des passages de Claude Code
```

## Configuration

- `config/models.yaml` : modèles, prix, paliers, règles de routage, guides de
  prompt par modèle, contrôle qualité, budget par défaut. C'est là qu'on change
  de modèle quand un meilleur sort.
- `.env` : clés et réglages (voir `.env.example`).
- `.claude/agents/*.md` : le rôle et les consignes de chaque agent.
- `CLAUDE.md` : les règles de l'orchestrateur.

## Plus tard : passer en ligne

Tout est rangé pour que la migration soit simple : la base passe dans
`riotmachine/db.py` (SQLite → **Turso**, du SQLite hébergé), les fichiers dans
`studio/` (→ **Cloudflare R2**). La régie peut alors être déployée sur Vercel en
branchant le dépôt depuis le compte voulu.

## Développement

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Les tests font tourner un clip complet en simulation : découpage, images,
contrôle, drafts, retour, finals, lip-sync, montage, budget et casting.
