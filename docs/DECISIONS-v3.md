# Riot Machine — Décisions v3

Décisions de Michael qui complètent ou précisent `SPEC-v3.md` et
`PRODUCTION-PLANS-v3.md`. Les amendements proposés plus bas ne sont **pas
appliqués** : ils attendent l'accord de Michael.

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

## Amendements proposés (non appliqués)

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
