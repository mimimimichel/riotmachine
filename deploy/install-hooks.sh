#!/usr/bin/env bash
# Installe les hooks git du dépôt (R-G2) : .git/hooks/<nom> -> deploy/hooks/<nom>
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$REPO/.git" ] || { echo "pas un dépôt git : $REPO"; exit 1; }
for hook in "$REPO"/deploy/hooks/*; do
  name="$(basename "$hook")"
  ln -sfn "../../deploy/hooks/$name" "$REPO/.git/hooks/$name"
  echo "hook installé : $name"
done
