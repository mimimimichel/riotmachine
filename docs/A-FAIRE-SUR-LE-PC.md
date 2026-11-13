# À faire sur le PC de Michael (consignes pour Claude Code sur le PC)

Michael n'est pas développeur. Il ne lance aucune commande lui-même et ne
vérifie rien à la main. Tu fais tout, tu lui parles simplement, en français,
sans jargon. Tu ne lui poses une question que pour une décision créative, une
dépense, ou pour revenir en arrière.

## 0. Vérifier que tu es sur le bon ordinateur

`~/riotmachine/studio/riot.db` doit exister. Sinon, dis-le en une phrase et
arrête-toi.

## 1. Que tout marche comme avant

1. Copie datée de `studio/riot.db` (copie SQLite à chaud) et de `studio/clips/`
   dans `~/riotmachine-sauvegardes/<date>/`. Ne supprime jamais rien.
2. Services de la v1 : `systemctl --user status riotmachine-regie riotmachine-worker`.
   S'ils sont arrêtés, remets-les en route (`systemctl --user start …`) et
   vérifie que la régie répond à son adresse habituelle (port 8420 par défaut).
3. Mode de travail d'avant, sans demander d'autorisation à chaque action :
   écris `~/riotmachine/.claude/settings.local.json` (fichier local, non suivi
   par git) qui autorise ce dont tu as besoin pour développer et déployer :
   `Bash(git *)`, `Bash(python3 *)`, `Bash(.venv/bin/*)`, `Bash(riot *)`,
   `Bash(systemctl --user *)`, `Bash(ffmpeg *)`, `Bash(ffprobe *)`,
   `Bash(sqlite3 *)`, `Bash(curl *)`, `Bash(ls *)`, `Bash(cp *)`, `Bash(mkdir *)`,
   `Read`, `Edit`, `Write`, `Glob`, `Grep`. Explique à Michael en une ligne qu'à
   la prochaine ouverture il lui suffit d'accepter une fois « faire confiance à
   ce dossier ».
4. Dis à Michael, en trois lignes, ce qui tournait, ce que tu as remis en route
   et où sont les sauvegardes.

## 2. Le besoin (approuvé par Michael)

Tourner au plus vite le bloc 1 de « Nobody Saw » avec le nouveau workflow :
plan de tournage par séquence, vidéo générée directement à partir des
références (sans visuel intermédiaire), dérushage plan par plan, montage.
Une seule Riot Machine, à la même adresse, avec retour possible à l'état
d'avant. Consommation de Claude réduite.

Les besoins fonctionnels sont dans `docs/VISION-v3.md`, `docs/SPEC-v3.md`,
`docs/PRODUCTION-PLANS-v3.md` (branche `v3` sur GitHub). La technique y est
indicative : les choix techniques sont les tiens.

## 3. L'approche retenue

- On fait évoluer la Riot Machine actuelle (code de `v1-final`) sur une branche
  de travail, au lieu de la reconstruire. La branche `v3` sert de réserve :
  documents, et briques réutilisables (`riotmachine/store.py`,
  `riotmachine/generations.py` dans `v3`) pour l'historique et l'absence de
  double dépense.
- Avant chaque mise à jour du PC : sauvegarde de la base et des clips, et
  étiquette git de l'état d'avant. Un bouton « Revenir à la version d'avant »
  dans la régie remet le code et la base d'avant (avec confirmation).
- `main` n'est déplacé que sur décision de Michael.

Étapes, chacune testée en simulation, puis déployée sur le PC (redémarrage des
services), puis résumée à Michael en trois lignes avec ce qu'il peut essayer :

1. Consommation : plus aucun réveil automatique de Claude par le worker ; un
   agent ne part que sur un clic de Michael. Page « Consommation ».
2. Séquences : les plans du bloc 1 regroupés par séquence dans le découpage,
   avec une étiquette « Veo Fast · N prises · coût · crédits Google ».
3. Plan de tournage par séquence : prises proposées, références de JJ envoyées
   directement à Veo (mode références de Vertex, voir
   `studio/tests/veo-modes-2026-11-11/RAPPORT.md` et `scripts/test_veo_modes.py`),
   coût total, bouton unique « Accorder et tourner ».
4. Dérushage : un plan à la fois, en boucle sur la musique ; Garder, Refaire avec
   motif ; fenêtre réglable dans la prise gardée.
5. Montage du bloc 1 sur le morceau, mis à jour quand une prise est gardée.

Aucune dépense réelle sans l'accord de Michael sur un montant affiché. Le
premier vrai tournage du bloc 1 se fait après l'étape 5, sur les crédits
Google, avec un budget qu'il valide.
