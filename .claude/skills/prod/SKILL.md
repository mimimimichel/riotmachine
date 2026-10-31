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

0. **Scénariste** (`needs_agent` contient « scenariste ») → délègue à l'agent
   `scenariste` : il lit le brainstorm collé par Michael et dépose ses propositions.
   Puis continue (les propositions attendent Michael, rien d'autre ne dépend d'elles).
0 bis. **Sources à relire** (`needs_agent` contient « sources à relire ») → délègue à
   l'agent `script-doctor` : il lit les nouvelles sources de Michael (conversations,
   transcriptions, notes), met à jour la mémoire de réalisation (`riot clip memoire`)
   et, avant validation du découpage, reprend les plans concernés.
1. **Étape `script`** (Michael a envoyé son dossier) → délègue à l'agent
   `script-doctor` (outil Agent) : lecture du dossier, découpage en blocs et plans,
   import, passage en `decoupage_review`. Puis arrête-toi : Michael valide.
2. **Retours sur le découpage** (`pending_reviews` de gate `decoupage`) → agent
   `script-doctor` pour corriger. Puis continue avec les blocs déjà validés.

**Production bloc par bloc.** Michael valide le découpage bloc par bloc. Un plan est
en production quand `en_production` vaut `true` dans `riot clip show` : seuls ces
plans passent par les étapes 4 à 8, même si le clip est encore à l'étape
`decoupage_review`. Ne touche jamais aux plans des autres blocs.
3. **Décors** (`needs_agent` contient « decorateur ») → délègue à l'agent
   `decorateur` : repérage des décors, objets et figurants, fiches, liens avec les
   plans (un élément = une image, pas d'états). Il ne lance aucune image. Les visuels des plans ne partent qu'une
   fois les décors repérés (`riot element done`) et leurs références gardées.
   Si la raison est « image(s) de départ à regarder », Michael a déposé une image
   ou demandé un prompt : le décorateur regarde ses images de départ, réécrit la
   fiche et le prompt HD d'après elles (`riot element describe`), sans rien d'autre.
   Le repérage ne part que lorsque tous les plans ont leur prompt détaillé.
4. **Plans `change_requested`** → trie toi-même chaque retour de Michael
   (`riot review list --clip $ARGUMENTS`, tableau des routes dans CLAUDE.md),
   puis `riot review handle`. Les plans repartent à la bonne étape et sont traités
   aux étapes suivantes de ce même passage.
5. **Plans `failed`** → lis `historique` (`riot shot show`) : la dernière remarque
   de la machine donne l'erreur ; `failed_step` dit l'étape qui a échoué. Erreur passagère : `riot shot retry <id>`.
   Vidéo HD / lip-sync : agent `finition`. Visuel ou vidéo refusé par le fournisseur
   (contenu, paramètre) : ajuste le prompt via l'agent concerné. Si tu es bloqué,
   `riot notify` à Michael avec le problème en une phrase.
6. **Plans `image_qc`, `hd_qc` et `draft_qc`** → agent `controleur` (tous les plans
   du lot dans une seule délégation, en précisant le statut de chacun).
7. **Plans `image_todo`** → agent `storyboard`, par lots de 6 plans maximum, un
   bloc après l'autre (plusieurs agents en parallèle si besoin). Donne-leur le slug
   du clip, le nom du bloc et les ids. Lance d'abord le premier plan de chaque bloc :
   une fois validé par Michael, son visuel sert de référence de lumière aux autres.
8. **Plans `prompt_todo`** → agent `routeur` sur tout le lot (un plan dont
   `route_reason` vaut « Choisi par Michael » garde son modèle), puis agent
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
