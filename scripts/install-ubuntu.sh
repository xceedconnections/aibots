#!/usr/bin/env bash
# Local-tree installer (Ubuntu / Debian). Prefer:
#   curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aibots}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ADMIN_EMAIL="${ADMIN_EMAIL:-xceedconnections@gmail.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Openaccount@123}"

echo "==> AIBOTS installer (local tree)"
echo "    Source: $REPO_DIR"
echo "    Target: $APP_DIR"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/install-ubuntu.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
echo "==> OS: ${PRETTY_NAME:-$ID}"

apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release git ufw jq rsync openssl

install_docker() {
  echo "==> Installing Docker via get.docker.com"
  rm -f /etc/apt/sources.list.d/docker.list
  rm -f /etc/apt/keyrings/docker.gpg
  apt-get update -y || true
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  docker compose version >/dev/null 2>&1 || apt-get install -y docker-compose-plugin || true
}

if ! command -v docker >/dev/null 2>&1; then
  install_docker
elif ! docker compose version >/dev/null 2>&1; then
  install_docker
else
  echo "==> Docker OK: $(docker --version)"
fi

mkdir -p "$APP_DIR"
rsync -a \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'data/models' \
  --exclude 'data/recordings' \
  --exclude 'data/asterisk' \
  "$REPO_DIR/" "$APP_DIR/"

mkdir -p "$APP_DIR/data/models/piper" "$APP_DIR/data/recordings" "$APP_DIR/data/asterisk"
chmod +x "$APP_DIR"/scripts/*.sh "$APP_DIR"/install.sh 2>/dev/null || true

if [[ ! -f "$APP_DIR/data/asterisk/pjsip_identify.conf" ]]; then
  cat > "$APP_DIR/data/asterisk/pjsip_identify.conf" <<'EOF'
; Auto-generated — IP-based VICIdial peers (no SIP registration)
[vicidial-identify]
type=identify
endpoint=vicidial
EOF
fi

cd "$APP_DIR"

DETECT_IP="$(curl -4 -fsS --max-time 5 https://ifconfig.me 2>/dev/null || true)"
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
LOCAL_IP="${LOCAL_IP:-127.0.0.1}"
PUBLIC_IP="${PUBLIC_IP:-${DETECT_IP:-$LOCAL_IP}}"
VICIDIAL_IP="${VICIDIAL_IP:-}"
SIP_PASS="${AIBOTS_SIP_PASSWORD:-aibotsSipPass123}"
SECRET="$(openssl rand -hex 32)"
DB_PASS="$(openssl rand -hex 12)"

[[ -f .env ]] || cp .env.example .env

set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

set_env "SECRET_KEY" "$SECRET"
set_env "PUBLIC_IP" "$PUBLIC_IP"
set_env "AIBOTS_SIP_PASSWORD" "$SIP_PASS"
set_env "ASTERISK_AMI_HOST" "${VICIDIAL_IP:-127.0.0.1}"
set_env "ADMIN_EMAIL" "$ADMIN_EMAIL"
set_env "ADMIN_PASSWORD" "$ADMIN_PASSWORD"
set_env "POSTGRES_PASSWORD" "$DB_PASS"
set_env "DATABASE_URL" "postgresql+asyncpg://aibots:${DB_PASS}@postgres:5432/aibots"
set_env "SIMULATE_MODE" "true"
set_env "SIP_MODE" "ip"

sed -i "s|YOUR_AIBOTS_PUBLIC_IP|${PUBLIC_IP}|g" .env
sed -i "s|YOUR_VICIDIAL_IP|${VICIDIAL_IP:-127.0.0.1}|g" .env
sed -i "s|YOUR_SERVER_IP|${LOCAL_IP}|g" .env
sed -i "s|change-me-to-a-long-random-string|${SECRET}|g" .env

if [[ -n "${VICIDIAL_IP}" ]]; then
  cat > "$APP_DIR/data/asterisk/pjsip_identify.conf" <<EOF
; Auto-generated — IP-based VICIdial peers (no SIP registration)
[vicidial-identify]
type=identify
endpoint=vicidial
match=${VICIDIAL_IP}
EOF
fi

ufw allow OpenSSH || true
ufw allow 80/tcp || true
ufw allow 3000/tcp || true
ufw allow 8000/tcp || true
ufw allow 5060/udp || true
ufw allow 5060/tcp || true
ufw allow 10000:10100/udp || true
ufw --force enable || true

docker compose pull || true
docker compose build
docker compose up -d

for i in $(seq 1 90); do
  curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break
  sleep 3
done

if [[ "${SKIP_MODELS:-0}" != "1" ]]; then
  docker exec aibots-ollama ollama pull qwen2.5:7b-instruct || true
  PIPER_DIR="$APP_DIR/data/models/piper" bash "$APP_DIR/scripts/download-models.sh" || true
fi

cat > "$APP_DIR/INSTALL-INFO.txt" <<EOF
Portal: http://${LOCAL_IP}:3000
Login:  ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}
PUBLIC_IP=${PUBLIC_IP}
SIP_MODE=ip
EOF
chmod 600 "$APP_DIR/INSTALL-INFO.txt"

echo "Installed. Portal http://${LOCAL_IP}:3000  Login ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}"
echo "Add Vicidial dialers later: Portal → VICIdial Servers (IP-based, no registration)"
