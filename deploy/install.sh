#!/usr/bin/env bash
# Installation de Riot Machine sur le PC Linux (Debian / Ubuntu).
# À lancer depuis le dossier du dépôt cloné dans ~/riotmachine :
#   cd ~/riotmachine && bash deploy/install.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

if [ "$REPO" != "$HOME/riotmachine" ]; then
  echo "⚠  Les services systemd supposent que le dépôt est dans ~/riotmachine (ici : $REPO)."
  echo "   Déplace-le ou adapte les chemins dans deploy/*.service."
fi

echo "== Dépendances système"
missing=()
for cmd in python3 ffmpeg ffprobe rsync; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
python3 -c "import venv" 2>/dev/null || missing+=("python3-venv")
if [ ${#missing[@]} -gt 0 ]; then
  echo "Manquant : ${missing[*]}"
  echo "Installe d'abord : sudo apt install python3 python3-venv ffmpeg rsync"
  exit 1
fi

echo "== Environnement Python (.venv)"
[ -x .venv/bin/pip ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "== .env créé : remplis FAL_KEY et Telegram (nano .env)"
fi

echo "== Base et référentiel"
.venv/bin/riot init

echo "== Services (systemd utilisateur)"
mkdir -p "$HOME/.config/systemd/user"
cp deploy/riotmachine-*.service deploy/riotmachine-*.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now riotmachine-regie.service riotmachine-worker.service riotmachine-backup.timer

if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
  echo
  echo "Pour que les services tournent sans session ouverte (PC sans écran), lance une fois :"
  echo "  sudo loginctl enable-linger $USER"
fi

echo
command -v claude >/dev/null 2>&1 || echo "⚠  Claude Code n'est pas installé : voir README, section 2."
echo "✓ Installé. Régie : http://$(hostname):8420  —  journal du worker : journalctl --user -u riotmachine-worker -f"
