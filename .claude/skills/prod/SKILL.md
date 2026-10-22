---
name: prod
description: Passage de production sur un clip — fait avancer tous les plans qui attendent un agent (découpage, storyboard, contrôle, routage, prompts, tri des retours). Lancé automatiquement par le worker, ou à la main avec /prod <clip>.
argument-hint: <slug-du-clip>
---

Tu es l'orchestrateur (voir CLAUDE.md). Fais avancer le clip **$ARGUMENTS** autant
que possible en un passage, puis arrête-toi.

## 1. État

`riot clip show $ARGUMENTS` — regarde `stage`, `status_counts`, `pending_reviews`
et `needs_agent`. Si `needs_agent` est vide, dis-le et arrête-toi.

## 2. Dans cet ordre

1. **Étape `script`** (Michael a envoyé son dossier) → délègue à l'agent
   `script-doctor` (outil Agent) : lecture du dossier, découpage en blocs et plans,
   import, passage en `decoupage_review`. Puis arrête-toi : Michael valide.
2. **Retours sur le découpage** (`pending_reviews` de gate `decoupage`) → agent
   `script-doctor` pour corriger. Puis arrête-toi.
3. **Plans `change_requested`** → trie toi-même chaque retour de Michael
   (`riot review list --clip $ARGUMENTS`, tableau des routes dans CLAUDE.md),
   puis `riot review handle`. Les plans repartent à la bonne étape et sont traités
   aux étapes suivantes de ce même passage.
4. **Plans `failed`** → lis `notes`. Erreur passagère : `riot shot retry <id>`.
   Vidéo HD / lip-sync : agent `finition`. Visuel ou vidéo refusé par le fournisseur
   (contenu, paramètre) : ajuste le prompt via l'agent concerné. Si tu es bloqué,
   `riot notify` à Michael avec le problème en une phrase.
5. **Plans `image_qc`, `hd_qc` et `draft_qc`** → agent `controleur` (tous les plans
   du lot dans une seule délégation, en précisant le statut de chacun).
6. **Plans `image_todo`** → agent `storyboard`, par lots de 6 plans maximum, un
   bloc après l'autre (plusieurs agents en parallèle si besoin). Donne-leur le slug
   du clip, le nom du bloc et les ids.
7. **Plans `prompt_todo`** → agent `routeur` sur tout le lot, puis agent
   `prompteur` sur le même lot, puis `riot shot submit <id>` pour chaque plan qui a
   un modèle et un prompt vidéo. Le plan passe en `video_review` : Michael valide
   le prompt, le modèle et le coût. **Ne lance jamais `riot gen draft`** : le
   worker lance la vidéo après sa validation.

Après chaque délégation, relis `riot clip show $ARGUMENTS` pour vérifier que les
statuts ont bien avancé. Ne refais pas le travail d'un agent toi-même.

## 3. Garde-fous

- Budget : si une génération est refusée pour budget, arrête les lancements,
  `riot notify "<clip> : budget atteint (<dépensé> / <budget>), j'attends ton feu vert."`.
- Ne valide rien à la place de Michael.
- Une génération lancée prend de quelques secondes à quelques minutes : tu n'as
  pas à attendre, le worker récupère les résultats et te relancera.

## 4. Fin

Résume en 5 lignes maximum : ce qui a été lancé, ce qui attend Michael, les
problèmes éventuels, le coût du clip (`riot cost $ARGUMENTS`, total seulement).
