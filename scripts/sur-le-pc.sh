#!/usr/bin/env bash
# Riot Machine — tout ce qui ne peut se faire que sur le PC (D12). Sans danger à relancer.
#
#   bash ~/riotmachine/scripts/sur-le-pc.sh
#
# Ce que fait le script, à chaque lancement :
#   1. copie datée de studio/riot.db (copie à chaud, cohérente) et de studio/clips/,
#      hors du dépôt, dans ~/riotmachine-sauvegardes/<date>/ ; rien n'est jamais effacé ;
#   2. relevé de ce qui tourne : timers et services systemd, crontab, processus,
#      lancements d'agents Claude des dernières 24 h et des 7 derniers jours ;
#   3. copie de travail de la branche v3 dans ~/riotmachine-v3 (worktree git), mise à jour,
#      avec son propre environnement Python ; le dépôt v1 (~/riotmachine) et ses services
#      ne sont pas touchés ;
#   4. tests de la v3 sur le PC, avec leur durée ;
#   5. essai à blanc de la migration v1 -> v3 sur la copie de riot.db (rien n'est écrit
#      ailleurs que dans le rapport) ;
#   6. rapport dans docs/rapports/ de la branche v3, commité et poussé si le PC peut pousser.
# Aucun secret ne part dans le rapport : les lignes qui ressemblent à une clé sont masquées.
#
# Variables facultatives : RIOT_REPO (dépôt v1, défaut ~/riotmachine),
# RIOT_SAUVEGARDES (défaut ~/riotmachine-sauvegardes), RIOT_V3_DIR (défaut ~/riotmachine-v3).

set -uo pipefail

REPO="${RIOT_REPO:-$HOME/riotmachine}"
SAVE_ROOT="${RIOT_SAUVEGARDES:-$HOME/riotmachine-sauvegardes}"
WT="${RIOT_V3_DIR:-$HOME/riotmachine-v3}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DAY="$(date '+%d/%m/%Y %H:%M')"
SAVE="$SAVE_ROOT/$STAMP"
TMP="$(mktemp -d)"
OUT="$TMP/rapport.md"
trap 'rm -rf "$TMP"' EXIT

say() { echo "== $*"; }
md() { printf '%s\n' "$*" >> "$OUT"; }
# masque les secrets et le dossier personnel avant que le texte n'entre dans le rapport
clean() { sed -E -e "s#$HOME#~#g" \
  -e 's/((token|key|secret|password|passwd|api)[A-Za-z0-9_]*[=: ]+)[^ "]+/\1***/Ig'; }
block() { md '```'; clean >> "$OUT"; md '```'; }

PY3="$(command -v python3 || true)"
[ -n "$PY3" ] || { echo "python3 introuvable : impossible de continuer"; exit 1; }
[ -d "$REPO/.git" ] || { echo "Dépôt introuvable : $REPO (pose RIOT_REPO)"; exit 1; }

md "# Rapport du PC — $DAY"
md ""
md "Produit par \`scripts/sur-le-pc.sh\`. Chemins : \`~\` = dossier personnel."
md ""

# --- 1. Sauvegarde --------------------------------------------------------------
say "1/6 Sauvegarde datée"
mkdir -p "$SAVE"
md "## 1. Sauvegarde"
md ""
DB="$REPO/studio/riot.db"
if [ -f "$DB" ]; then
  if "$PY3" - "$DB" "$SAVE/riot.db" <<'EOF'
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
print(ok)
sys.exit(0 if ok == "ok" else 1)
EOF
  then md "- \`riot.db\` copiée et vérifiée (intégrité ok) : \`$(echo "$SAVE/riot.db" | clean)\` ($(du -h "$SAVE/riot.db" | cut -f1))"
  else md "- **Copie de \`riot.db\` en échec** : voir la sortie du script."; fi
else
  md "- Pas de \`studio/riot.db\` dans \`$(echo "$REPO" | clean)\`."
fi
for d in clips characters; do
  if [ -d "$REPO/studio/$d" ]; then
    cp -a "$REPO/studio/$d" "$SAVE/$d" \
      && md "- \`studio/$d/\` copié : $(du -sh "$SAVE/$d" | cut -f1), $(find "$SAVE/$d" -type f | wc -l) fichiers" \
      || md "- **Copie de \`studio/$d/\` en échec**"
  fi
done
md "- Dossier : \`$(echo "$SAVE" | clean)\`. Les copies précédentes sont gardées : $(ls -1 "$SAVE_ROOT" | wc -l) au total."
md ""

# --- 2. Ce qui tourne -------------------------------------------------------------
say "2/6 Timers, services, crontab, agents"
md "## 2. Ce qui tourne"
md ""
md "### Timers systemd (utilisateur)"
{ systemctl --user list-timers --all --no-pager 2>&1 || true; } | block
md "### Services Riot Machine (utilisateur)"
{ systemctl --user list-units 'riotmachine*' --all --no-pager 2>&1 || true; } | block
md "### Timers systemd (système), lignes qui parlent de riot ou claude"
{ systemctl list-timers --all --no-pager 2>&1 | grep -Ei 'riot|claude' || echo "(aucun)"; } | block
md "### Crontab"
{ crontab -l 2>&1 || true; } | block
md "### Processus en cours"
{ pgrep -af 'riot (worker|regie)|claude -p' 2>/dev/null || echo "(aucun)"; } | block
md "### Réglages de la boucle v1 (.env, variables RIOT_ sans secret)"
{ grep -E '^RIOT_(POLL|AGENT|CLAUDE_MODEL|AGENTS)' "$REPO/.env" 2>/dev/null || echo "(valeurs par défaut : tour toutes les 30 s, 2 relances au plus)"; } | block
if [ -f "$SAVE/riot.db" ]; then
  md "### Lancements d'agents Claude par le worker v1"
  "$PY3" - "$SAVE/riot.db" <<'EOF' | block
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
if not c.execute("SELECT 1 FROM sqlite_master WHERE name='agent_runs'").fetchone():
    print("(pas de table agent_runs)"); sys.exit()
for label, since in (("24 dernières heures", "-1 day"), ("7 derniers jours", "-7 days")):
    n, dur = c.execute("SELECT COUNT(*), COALESCE(SUM(strftime('%s', ended_at) - strftime('%s', started_at)), 0) "
                       "FROM agent_runs WHERE started_at >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)", (since,)).fetchone()
    print(f"{label} : {n} lancement(s), {int(dur) // 60} min au total")
print("Derniers lancements :")
for r in c.execute("SELECT started_at, clip_slug, exit_code, reason FROM agent_runs ORDER BY id DESC LIMIT 10"):
    print(f"  {r[0]}  {r[1]}  code {r[2]}  {(r[3] or '')[:90]}")
EOF
fi
md ""

# --- 3. Copie de travail v3 --------------------------------------------------------
say "3/6 Copie de travail de la branche v3"
md "## 3. Branche v3 sur le PC"
md ""
git -C "$REPO" fetch -q origin v3 2>&1 | clean
if [ ! -e "$WT/.git" ]; then
  if git -C "$REPO" show-ref -q --verify refs/heads/v3; then
    git -C "$REPO" worktree add -q "$WT" v3 2>&1 | clean
  else
    git -C "$REPO" worktree add -q -b v3 "$WT" origin/v3 2>&1 | clean
  fi
fi
if [ -e "$WT/.git" ]; then
  git -C "$WT" pull -q --ff-only origin v3 2>&1 | clean
  md "- Copie de travail : \`$(echo "$WT" | clean)\`, commit \`$(git -C "$WT" rev-parse --short HEAD)\`."
  # le crochet de pré-commit v3 ne vaut que pour cette copie ; le dépôt v1 garde le sien (D24)
  git -C "$WT" config extensions.worktreeConfig true
  git -C "$WT" config --worktree core.hooksPath "$WT/deploy/hooks"
  md "- Crochet de pré-commit v3 actif dans cette copie."
else
  md "- **Impossible de créer la copie de travail v3** : voir la sortie du script."
fi
VENV="$WT/.venv-v3"
if [ -e "$WT/.git" ]; then
  [ -x "$VENV/bin/python" ] || "$PY3" -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1
  if "$VENV/bin/pip" install -q -e "$WT[dev]" >"$TMP/pip.log" 2>&1; then
    md "- Environnement Python v3 prêt (\`.venv-v3\`)."
  else
    md "- **Installation des dépendances v3 en échec** :"; tail -5 "$TMP/pip.log" | block
  fi
fi
md ""

# --- 4. Tests ----------------------------------------------------------------------
say "4/6 Tests de la v3"
md "## 4. Tests de la v3 sur le PC"
md ""
if [ -x "$VENV/bin/python" ]; then
  T0=$(date +%s)
  if (cd "$WT" && "$VENV/bin/python" -m pytest -q -p no:cacheprovider tests >"$TMP/tests.log" 2>&1); then R="verts"; else R="**en échec**"; fi
  md "- Tests $R en $(( $(date +%s) - T0 )) s : $(tail -1 "$TMP/tests.log" | clean)"
  [ "$R" = "verts" ] || tail -30 "$TMP/tests.log" | block
fi
md ""

# --- 5. Essai à blanc de la migration ----------------------------------------------
say "5/6 Essai à blanc de la migration"
md "## 5. Migration v1 -> v3, essai à blanc sur la copie"
md ""
MIG="$WT/docs/rapports/migration-v1-essai-pc-$STAMP.md"
if [ -f "$SAVE/riot.db" ] && [ -x "$VENV/bin/riot" ]; then
  mkdir -p "$WT/docs/rapports" "$TMP/studio"
  if RIOT_STUDIO_ROOT="$TMP/studio" "$VENV/bin/riot" migrer-v1 --depuis "$SAVE/riot.db" --essai --rapport "$MIG" >"$TMP/mig.log" 2>&1
  then md "- Essai conforme. Rapport détaillé : \`docs/rapports/$(basename "$MIG")\`."
  else md "- **Essai non conforme** :"; clean < "$TMP/mig.log" | tail -10 | block
       [ -f "$MIG" ] && md "- Rapport détaillé : \`docs/rapports/$(basename "$MIG")\`."; fi
  [ -f "$MIG" ] && sed -i -E "s#$HOME#~#g" "$MIG"
else
  md "- Essai non lancé (pas de copie de riot.db ou pas d'environnement v3)."
fi
md ""

# --- 6. Rapport ----------------------------------------------------------------------
say "6/6 Rapport"
if [ -e "$WT/.git" ]; then
  mkdir -p "$WT/docs/rapports"
  DEST="$WT/docs/rapports/sur-le-pc-$STAMP.md"
  cp "$OUT" "$DEST"
  git -C "$WT" add docs/rapports
  if RIOT_PYTHON="$VENV/bin/python" git -C "$WT" commit -q -m "Rapport du PC ($DAY) : sauvegarde, timers, tests, essai de migration" 2>"$TMP/commit.log"; then
    if git -C "$WT" pull -q --rebase origin v3 2>/dev/null && git -C "$WT" push -q origin HEAD:v3 2>"$TMP/push.log"; then
      echo "Rapport poussé sur la branche v3 : docs/rapports/sur-le-pc-$STAMP.md"
    else
      echo "Rapport commité dans $DEST, mais pas poussé (pas d'accès en écriture depuis ce PC ?)."
    fi
  else
    echo "Rapport écrit dans $DEST (commit refusé : voir $TMP/commit.log)."; cat "$TMP/commit.log"
  fi
else
  mkdir -p "$SAVE"; cp "$OUT" "$SAVE/rapport.md"
  echo "Rapport écrit dans $SAVE/rapport.md"
fi
echo "Sauvegarde : $SAVE"
