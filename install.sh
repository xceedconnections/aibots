#!/usr/bin/env bash
# ============================================================
# AIBOTS — one-line installer for Ubuntu / Debian
#
#   curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
#
# Optional env vars:
#   APP_DIR=/opt/aibots
#   BRANCH=main
#   PUBLIC_IP=1.2.3.4
#   VICIDIAL_IP=5.6.7.8        # optional seed; add more later in portal
#   ADMIN_PASSWORD=Openaccount@123
#   SKIP_MODELS=1
# ============================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/xceedconnections/aibots.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/aibots}"
SRC_DIR="${SRC_DIR:-/opt/aibots-src}"
ADMIN_EMAIL="${ADMIN_EMAIL:-xceedconnections@gmail.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Openaccount@123}"

echo "============================================================"
echo " AIBOTS installer (Ubuntu / Debian)"
echo " Repo:   $REPO_URL"
echo " Branch: $BRANCH"
echo " Target: $APP_DIR"
echo "============================================================"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "ERROR: run as root, e.g.:"
  echo "  curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

if ! command -v apt-get >/dev/null 2>&1; then
  echo "ERROR: This installer supports Ubuntu/Debian (apt)."
  exit 1
fi

. /etc/os-release
echo "==> OS: ${PRETTY_NAME:-$ID $VERSION_ID}"

echo "==> Installing base packages"
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release git ufw jq rsync openssl

install_docker() {
  echo "==> Installing Docker (official get.docker.com — auto-detects Debian/Ubuntu)"
  # Remove broken leftover from a previous failed attempt (e.g. ubuntu bookworm on Debian)
  rm -f /etc/apt/sources.list.d/docker.list
  rm -f /etc/apt/keyrings/docker.gpg
  apt-get update -y || true

  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker

  # Ensure compose plugin exists
  if ! docker compose version >/dev/null 2>&1; then
    apt-get install -y docker-compose-plugin || true
  fi
  docker --version
  docker compose version
}

if ! command -v docker >/dev/null 2>&1; then
  install_docker
elif ! docker compose version >/dev/null 2>&1; then
  echo "==> Docker present but Compose missing — repairing"
  install_docker
else
  echo "==> Docker already OK: $(docker --version)"
fi

echo "==> Cloning AIBOTS ($BRANCH)"
rm -rf "$SRC_DIR"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$SRC_DIR"

echo "==> Syncing to $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'data/models' \
  --exclude 'data/recordings' \
  --exclude 'data/asterisk' \
  "$SRC_DIR/" "$APP_DIR/"

mkdir -p "$APP_DIR/data/models/piper" "$APP_DIR/data/recordings" "$APP_DIR/data/asterisk"
chmod +x "$APP_DIR"/scripts/*.sh "$APP_DIR"/install.sh 2>/dev/null || true

# Seed IP-based identify file (Vicidial servers added later in portal)
if [[ ! -f "$APP_DIR/data/asterisk/pjsip_identify.conf" ]]; then
  cat > "$APP_DIR/data/asterisk/pjsip_identify.conf" <<'EOF'
; Auto-generated — IP-based VICIdial peers (no SIP registration)
; Portal → VICIdial Servers updates this file
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
# Optional seed IP — portal can add more Vicidial servers later (IP-based)
VICIDIAL_IP="${VICIDIAL_IP:-}"
SIP_PASS="${AIBOTS_SIP_PASSWORD:-aibotsSipPass123}"
SECRET="$(openssl rand -hex 32)"
DB_PASS="$(openssl rand -hex 12)"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

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

# If a seed Vicidial IP was provided, put it in identify file
if [[ -n "${VICIDIAL_IP}" ]]; then
  cat > "$APP_DIR/data/asterisk/pjsip_identify.conf" <<EOF
; Auto-generated — IP-based VICIdial peers (no SIP registration)
[vicidial-identify]
type=identify
endpoint=vicidial
match=${VICIDIAL_IP}
EOF
fi

echo "==> Firewall (SSH, HTTP, SIP, RTP)"
ufw allow OpenSSH || true
ufw allow 80/tcp || true
ufw allow 3000/tcp || true
ufw allow 8000/tcp || true
ufw allow 5060/udp || true
ufw allow 5060/tcp || true
ufw allow 10000:10100/udp || true
ufw --force enable || true

echo "==> Building and starting containers"
docker compose pull || true
docker compose build
docker compose up -d

echo "==> Waiting for API health"
API_OK=0
for i in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "API is up"
    API_OK=1
    break
  fi
  sleep 3
done
if [[ "$API_OK" != "1" ]]; then
  echo "WARN: API not healthy yet — check: docker logs aibots-api"
fi

if [[ "${SKIP_MODELS:-0}" != "1" ]]; then
  echo "==> Pulling LLM model (qwen2.5:7b-instruct)"
  docker exec aibots-ollama ollama pull qwen2.5:7b-instruct || \
    echo "WARN: ollama pull failed — run later: docker exec aibots-ollama ollama pull qwen2.5:7b-instruct"
  if [[ -x "$APP_DIR/scripts/download-models.sh" ]]; then
    PIPER_DIR="$APP_DIR/data/models/piper" bash "$APP_DIR/scripts/download-models.sh" || true
  fi
fi

cat > "$APP_DIR/INSTALL-INFO.txt" <<EOF
AIBOTS installed $(date -u +%Y-%m-%dT%H:%M:%SZ)
Portal:   http://${LOCAL_IP}:3000
Nginx:    http://${LOCAL_IP}/
API:      http://${LOCAL_IP}:8000
Login:    ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}
PUBLIC_IP=${PUBLIC_IP}
SIP_MODE=ip (no registration — add Vicidial server IPs in portal)
AIBOTS_SIP_PASSWORD=${SIP_PASS}
App dir:  ${APP_DIR}
EOF
chmod 600 "$APP_DIR/INSTALL-INFO.txt"

echo ""
echo "============================================================"
echo " AIBOTS is installed"
echo "============================================================"
echo " Portal:     http://${LOCAL_IP}:3000"
echo " Login:      ${ADMIN_EMAIL}"
echo " Password:   ${ADMIN_PASSWORD}"
echo " PUBLIC_IP:  ${PUBLIC_IP}"
echo ""
echo " Next:"
echo "  1. Open portal → VICIdial Servers → Add each dialer by IP"
echo "  2. Portal → Campaigns / Bots → Client ID, Remote Agent, Transfer DID"
echo "  3. Portal → SIP Carrier → copy IP-based peer + dialplan into Vicidial"
echo "============================================================"
