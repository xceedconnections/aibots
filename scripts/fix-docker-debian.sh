#!/usr/bin/env bash
# Fix a broken Debian install that pointed Docker apt at ubuntu/bookworm
# Run on the AIBOTS server as root, then re-run install.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "==> Removing broken Docker apt repo (ubuntu/bookworm on Debian)"
rm -f /etc/apt/sources.list.d/docker.list
rm -f /etc/apt/keyrings/docker.gpg
apt-get update -y

echo "==> Installing Docker via get.docker.com"
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker --version
docker compose version || apt-get install -y docker-compose-plugin

echo "==> Docker OK. Now re-run AIBOTS install:"
echo "  curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo ADMIN_PASSWORD='Openaccount@123' bash"
