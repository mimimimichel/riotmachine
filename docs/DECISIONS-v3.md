# Riot Machine — Décisions v3

Décisions qui complètent ou précisent `SPEC-v3.md` et `PRODUCTION-PLANS-v3.md`.
D1 à D16 sont de Michael. À partir de D17, ce sont des choix d'exécution faits
par Claude selon la règle D11 (l'option la plus simple conforme à la spec).

## Décisions

| N° | Date | Question | Décision |
|---|---|---|---|
| D1 | 13/11/2026 | Modifier le code en place ou repartir d'un squelette neuf ? | **Squelette neuf**, dans ce dépôt, sur la branche `v3`. Un script migre l'ancienne base vers le nouveau schéma ; il est testé sur une copie de `riot.db`. Rien n'est supprimé ; `v1-final` reste exécutable. |
| D2 | 13/11/2026 | Les crédits offerts sont-ils soumis à accord ? Comment se compte le plafond du clip zéro ? | Les crédits offerts sont soumis à l'accord de Michael comme toute dépense. Le plafond de 10 $ du clip zéro se compte en crédits consommés. |
| D3 | 13/11/2026 | Les modèles d'image et de lip-sync sont-ils dans le catalogue ? | Oui, dans le même catalogue que la vidéo : capacités, offres, prix, réserve. |
| D4 | 13/11/2026 | Le lip-sync fait-il partie du clip zéro ? | Non : hors clip zéro, en P1. |
| D5 | 13/11/2026 | Une séquence peut-elle être à cheval sur deux blocs ? | Oui. Seuls les plans des blocs validés se tournent ; une prise ne regroupe que des plans de blocs validés. |
| D6 | 13/11/2026 | Composition stricte (mode première + dernière image, sans référence chez Veo) ? | P1. Les deux images sont générées avec les références du personnage. Pour le clip zéro, ces plans partent en mode références. |
| D7 | 13/11/2026 | Que deviennent les anciens visuels de « Nobody Saw » ? | Archivés, rattachés à leur plan, consultables, jamais utilisés d'office. Michael peut en choisir un comme image maîtresse. |
| D8 | 13/11/2026 | R-H26 en P0 ? | Gardée en P0 mais réduite, en dernier du lot 6. Déclencheur : Michael abandonne ou modifie un plan. Le script-doctor écrit 2 ou 3 propositions à partir de la fiche d'impact, le planificateur les chiffre, Michael choisit, la révision est annulable. La détection continue reste en P1 (R-H27). Si le lot 6 déborde, Michael décide. |
| D9 | 13/11/2026 | Que peuvent écrire les agents ? | Aucun agent n'écrit dans `riot.db`, `config/` ni `.env`. Les agents n'agissent que par la CLI. |
| D10 | 13/11/2026 | D'où peut venir l'auteur « michael » d'une écriture ? | Seulement de la régie authentifiée, jamais d'une variable d'environnement ni de la CLI. |
| D11 | 13/11/2026 | Que demander à Michael ? | Claude fait tout lui-même. Il ne pose une question que pour une décision créative, une dépense ou un vrai choix de conception. Pour le reste, il prend l'option la plus simple conforme à la spec et la note ici. |
| D12 | 13/11/2026 | Comment faire ce qui ne se fait que sur le PC (sauvegarde de `riot.db` et des clips, timers, crontab, essai de migration sur la vraie base) ? | Un script unique, `scripts/sur-le-pc.sh`, sans danger à relancer, qui fait tout et produit un rapport dans `docs/rapports/`. Il est tenu à jour à chaque lot. |
| D13 | 13/11/2026 | Où vit l'ancien code ? | Dans `legacy/` sur la branche `v3`, jamais importé par le nouveau code. Le nouveau code est dans `riotmachine/`. |
| D14 | 13/11/2026 | R-A2 au lot 1 ? | Identifiants, retours et historique testés au lot 1. Le critère sur les prises est complété au lot 2. |
| D15 | 13/11/2026 | Migration de l'ancienne base ? | Ossature au lot 1. Chaque table est migrée au lot où elle naît. Tests sur une base v8 générée par le code de `legacy/` (clip de démonstration, plus un clip de 12 blocs et 64 plans). Mode d'essai à blanc sur une copie, avec rapport. |
| D16 | 13/11/2026 | Usurpation d'identité entre agents ? | Pas avant le clip zéro. **P2** : un jeton par agent pour qu'un agent ne puisse pas se faire passer pour un autre. |
| D17 | 13/11/2026 | Où est la base v3 ? | `studio/riot-v3.db`, à côté de `riot.db`. La base v1 n'est jamais modifiée par la v3 : `v1-final` continue de tourner dessus. |
| D18 | 13/11/2026 | Comment appliquer R-T10 sans gêner le développement ? | Les permissions des agents sont dans `config/agents-permissions.json`, que le lanceur d'agents (lot 5) passera à `claude --settings`. L'ancien `.claude/settings.json`, qui interdisait aussi `git push` et `config/` aux sessions de développement, est rangé dans `legacy/.claude/`. |
| D19 | 13/11/2026 | Qui peut signer une écriture ? | Trois sortes d'auteurs : `michael`, `agent:<nom>`, `code:<module>`. Michael peut écrire tous les champs. Les champs de baseline (mots d'un plan, intention d'un bloc, brief, texte d'un retour) n'acceptent que `michael`. La CLI refuse `michael`, que ce soit en option ou par `RIOT_ACTOR`. |
| D20 | 13/11/2026 | Que devient le texte du clip v1 (`pitch`, `concept`) ? | Il forme le brief (baseline) : pitch, une ligne vide, puis concept. |
| D21 | 13/11/2026 | L'historique v1 (`changes`) est-il importé ? | Non : les noms de champs ont changé. L'ancienne base reste intacte et consultable ; la v3 démarre son historique à la migration, et chaque ligne importée est journalisée par `code:migration-v1`. |
| D22 | 13/11/2026 | Que fait le worker au redémarrage d'une génération partie sans réponse du fournisseur ? | Si le fournisseur sait retrouver une génération par sa clé (champ du catalogue), il la retrouve. Sinon, la génération passe « à vérifier », Michael est prévenu, et elle n'est jamais relancée d'office. |
| D23 | 13/11/2026 | Où sont les mots de Michael et leur version de production ? | Plan : `words` (Michael) et `production_text` (agents). Bloc : `intention` (Michael) et `production_notes` (agents). Clip : `brief` (Michael). Retour : `text` (Michael). La note d'intention (lot 4) et les instructions de casting (lot 2) suivront la même règle à leur création. |
| D24 | 13/11/2026 | Le crochet de pré-commit est-il « en place » sur une copie neuve du dépôt ? | Le test vérifie le crochet du dépôt (`deploy/hooks/pre-commit`, sans porte de sortie). Il s'installe par `deploy/install-hooks.sh`. Sur le PC, `scripts/sur-le-pc.sh` l'active pour la seule copie de travail v3 (`core.hooksPath` propre à cette copie), sans toucher au crochet du dépôt v1. |
| D25 | 13/11/2026 | Les deux scénarios complets de R-G2 ? | Ils demandent séquences, prises et planificateur : écrits au lot 3, complétés jusqu'au lot 6. |
| D26 | 13/11/2026 | La migration de la base v1 peut-elle écrire les champs de baseline ? | Oui, et seulement elle (`code:migration-v1`) : elle recopie les mots de Michael tels quels, ce que vérifie un contrôle du rapport. Aucun autre auteur que Michael ne les écrit. |
| D27 | 13/11/2026 | Comment Michael est-il prévenu d'une génération « à vérifier » ? | Au lot 1, la génération porte un message clair et `resume` le renvoie. La notification (Telegram, R-D5) et l'affichage dans la régie arrivent avec leurs lots. |
| D28 | 13/11/2026 | Comment le PC fait-il tourner la v3 sans gêner la v1 ? | Une copie de travail git de la branche `v3` dans `~/riotmachine-v3`, avec son propre environnement Python (`.venv-v3`). `~/riotmachine` reste sur la v1 et ses services ne sont pas touchés. |
| D29 | 13/11/2026 | Que peut contenir un rapport du PC, puisque le dépôt est public ? | Ni secret ni chemin personnel : les lignes qui ressemblent à une clé sont masquées et le dossier personnel devient `~`. Les noms de clips et de plans y figurent. |
| D30 | 15/11/2026 | Squelette neuf (D1) ou évolution de la v1 ? | **Évolution de la v1**, sur la branche `v3-evolution`, pour tourner le clip zéro au plus vite. Remplace D1, D13, D17 et D28 : pas de `legacy/`, pas de seconde base, une seule régie à la même adresse. La base v1 reçoit des migrations numérotées (R-G3), sans rien supprimer. La branche `v3` reste en réserve. |
| D31 | 15/11/2026 | Retour arrière ? | Sauvegarde complète dans `~/riotmachine-sauvegardes/2026-11-15-v1/` (code en bundle git, base, arbre de travail avec `.env`, `config/`, `studio/`, services) et étiquette `v1-avant-v3`. `~/riotmachine-sauvegardes/revenir-v1.sh` remet tout et redémarre la régie ; il met d'abord l'état courant de côté. |
| D32 | 15/11/2026 | R-T1 avant le clip zéro : comment l'appliquer sans casser la production v1 ? | Le worker dépose des demandes d'agent (`agent_queue`) et ne lance que les demandes accordées. Mode par défaut « sur accord » ; mode « automatique » sous plafond du jour. Réglages dans la régie (page Conso), stockés dans `settings_kv`. |
| D33 | 15/11/2026 | Comment mesurer et borner la consommation (R-T4) ? | `claude -p --output-format json --max-budget-usd <plafond du passage>` ; coût, tours et jetons relevés à la fin du passage dans `agent_runs`. Plafond du jour 3 $, plafond du passage 1 $ par défaut. Sur l'abonnement, le coût affiché est un équivalent API. |
| D34 | 15/11/2026 | Permissions des agents (R-T10, D18) ? | `.claude/settings.json` devient `config/agents-permissions.json`, passé à chaque passage par `--settings`. Les sessions de développement ne sont plus bridées par les interdits des agents. |
| D35 | 15/11/2026 | Règle de Michael (15/11) sur les choix de modèle et d'option | Chaque option (modèle, résolution, durée, mode) affiche son prix, et la régie annonce avant le choix ce qu'il obligerait à refaire ou à recouper (plan trop long pour l'offre, prises à refaire, découpage à revoir). |

## Amendements de D1 à D10

Appliqués le 13/11/2026 (spec 3.1), à `SPEC-v3.md` et aux documents qui en font
partie (`PRODUCTION-PLANS-v3.md`) ou qu'il cite (`VISION-v3.md`, pour D2).

| Décision | Document, endroit | Amendement proposé |
|---|---|---|
| D1 | `SPEC-v3.md` R-G3, critère | Ajouter : « Le script de migration de la base v1 vers le schéma v3 est testé sur une copie de `riot.db` : aucune ligne perdue, identifiants conservés. » |
| D1 | `SPEC-v3.md` §8, lot 0 | « Branche `v3` partie de `v1-final` ; squelette neuf ; `v1-final` reste exécutable. » |
| D2 | `PRODUCTION-PLANS-v3.md` §11, 1er point | « Toute génération payante, **crédits offerts compris**, attend un accord… » |
| D2 | `VISION-v3.md` §3, phase 0 | « monté, pour moins de 10 $ **de crédits consommés** ». |
| D3 | `PRODUCTION-PLANS-v3.md` §6, 1re phrase | « `config/models.yaml` est la seule source des capacités et des prix **des modèles de vidéo, d'image et de lip-sync**. » Ajouter au catalogue un champ `kind: video | image | lipsync`. |
| D4 | `PRODUCTION-PLANS-v3.md` §12, étape 6 | Ajouter « (P1, hors clip zéro) ». |
| D5 | `PRODUCTION-PLANS-v3.md` §4, ligne Séquence | Ajouter : « Une séquence peut couvrir plusieurs blocs. Seuls les plans des blocs validés se tournent ; une prise ne regroupe que des plans de blocs validés. » |
| D5 | `SPEC-v3.md` R-B1, critère | Ajouter : « Une séquence à cheval sur les blocs 1 et 2, bloc 1 seul validé : le planificateur ne propose que des prises des plans du bloc 1. » |
| D6 | `PRODUCTION-PLANS-v3.md` §7 et §8.3 | Profil `composition_stricte` et règle « plan `composition: stricte` seul, en mode première + dernière image » marqués **P1**. Ajouter : « Les deux images sont générées avec les références du personnage. Jusqu'au clip zéro, un plan à composition stricte part en mode références. » |
| D7 | `PRODUCTION-PLANS-v3.md` §4, dernière phrase | « Les anciens visuels de plan sont archivés et rattachés à leur plan : consultables, jamais envoyés à un modèle, sauf si Michael en choisit un comme image maîtresse. » |
| D8 | `PRODUCTION-PLANS-v3.md` R-H26 | Énoncé réduit : « Déclencheur : Michael abandonne ou modifie un plan. Fiche d'impact (code), 2 ou 3 propositions du script-doctor, chiffrées par le planificateur, choix de Michael, révision annulable. » Critère inchangé. La détection d'anomalies (§14.1, « La machine détecte une anomalie ») passe sous R-H27 (P1). |
| D8 | `SPEC-v3.md` §8, lot 6 | R-H26 en dernier du lot. |
| D9 | `SPEC-v3.md` §7, nouvelle exigence R-T10 (P0) | « Aucun agent n'écrit dans `riot.db`, `config/` ni `.env` ; les agents n'agissent que par la CLI. Critère : les permissions des agents refusent ces chemins ; un test le vérifie. » |
| D10 | `SPEC-v3.md` R-A4, énoncé | Ajouter : « L'auteur `michael` ne vient que de la régie authentifiée ; la CLI et les variables d'environnement ne peuvent pas le donner. » Critère : « `RIOT_ACTOR=michael riot …` est refusé. » |
