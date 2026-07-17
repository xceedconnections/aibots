#!/usr/bin/env bash
# ============================================================
# AIBOTS — Ubuntu 22.04 / 24.04 setup (repo already on disk)
#
# Prefer one-liner from GitHub:
#   curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
#
# Or after clone:
#   sudo bash scripts/install-ubuntu.sh
# ============================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aibots}"
# When invoked from install.sh, REPO_DIR is the cloned source.
# When invoked from a local checkout, use parent of scripts/.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

echo "==> AIBOTS installer"
echo "    Source: $REPO_DIR"
echo "    Target: $APP_DIR"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/install-ubuntu.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "==> Updating apt"
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release git ufw jq rsync openssl

echo "==> Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

echo "==> Copying project to $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'data/models' \
  --exclude 'data/recordings' \
  "$REPO_DIR/" "$APP_DIR/"

mkdir -p "$APP_DIR/data/models/piper" "$APP_DIR/data/recordings"
chmod +x "$APP_DIR"/scripts/*.sh "$APP_DIR"/install.sh 2>/dev/null || true

cd "$APP_DIR"

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
SERVER_IP="${SERVER_IP:-127.0.0.1}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  sed -i "s|YOUR_SERVER_IP|$SERVER_IP|g" .env
  SECRET=$(openssl rand -hex 32)
  sed -i "s|change-me-to-a-long-random-string|$SECRET|g" .env
  echo "==> Created .env with SERVER_IP=$SERVER_IP"
  echo "    EDIT .env and set VICIDIAL_* + ADMIN_PASSWORD before production use"
else
  echo "==> Keeping existing .env"
fi

echo "==> Opening firewall ports (22, 80, 3000, 8000, 11434)"
ufw allow OpenSSH || true
ufw allow 80/tcp || true
ufw allow 3000/tcp || true
ufw allow 8000/tcp || true
ufw allow 11434/tcp || true
ufw --force enable || true

echo "==> Building and starting containers (this can take several minutes)"
docker compose pull || true
docker compose build
docker compose up -d

echo "==> Waiting for API health"
for i in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "API is up"
    break
  fi
  sleep 3
done

echo "==> Pulling LLM model into Ollama (qwen2.5:7b-instruct) — large download"
docker exec aibots-ollama ollama pull qwen2.5:7b-instruct || \
  echo "WARN: ollama pull failed — run later: docker exec aibots-ollama ollama pull qwen2.5:7b-instruct"

echo "==> Downloading Piper voice model"
PIPER_DIR="$APP_DIR/data/models/piper" bash "$APP_DIR/scripts/download-models.sh" || true

echo ""
echo "============================================================"
echo " AIBOTS is installed"
echo "============================================================"
echo " Portal:   http://$SERVER_IP:3000"
echo " API:      http://$SERVER_IP:8000"
echo " API docs: http://$SERVER_IP:8000/docs"
echo " Nginx:    http://$SERVER_IP/"
echo ""
echo " Login:    admin@aibots.local / ChangeMe123!  (change in .env)"
echo ""
echo " Next:"
echo "  1. Edit $APP_DIR/.env  (VICIdial URL, passwords, VITE_API_URL)"
echo "  2. cd $APP_DIR && docker compose up -d --build portal"
echo "  3. Open portal → Bots → ACA Qualifier → Run test call"
echo "  4. Point VICIdial Start URL to:"
echo "     http://$SERVER_IP/webhook/vicidial/start"
echo "  5. Docs: https://github.com/xceedconnections/aibots/blob/main/INSTALL.md"
echo "============================================================"
