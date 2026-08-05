#!/usr/bin/env bash
# ============================================================
# Update existing AIBOTS install to latest git (no reinstall)
#
#   cd /opt/aibots && sudo bash scripts/update.sh
#
# Or one-liner after push:
#   curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/scripts/update.sh | sudo bash
# ============================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aibots}"
SRC_DIR="${SRC_DIR:-/opt/aibots-src}"
REPO_URL="${REPO_URL:-https://github.com/xceedconnections/aibots.git}"
BRANCH="${BRANCH:-main}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/update.sh"
  exit 1
fi

echo "==> Updating AIBOTS in $APP_DIR (branch $BRANCH)"

# Prefer refreshing from a fresh clone so we always get latest main
if [[ -d "$SRC_DIR/.git" ]]; then
  git -C "$SRC_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$SRC_DIR" checkout -f "$BRANCH"
  git -C "$SRC_DIR" reset --hard "origin/$BRANCH"
else
  rm -rf "$SRC_DIR"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$SRC_DIR"
fi

mkdir -p "$APP_DIR/data/models/piper" "$APP_DIR/data/recordings" "$APP_DIR/data/asterisk"
if [[ ! -f "$APP_DIR/data/asterisk/pjsip_identify.conf" ]]; then
  cat > "$APP_DIR/data/asterisk/pjsip_identify.conf" <<'EOF'
; IP-based VICIdial peers — no SIP registration
[vicidial-identify]
type=identify
endpoint=vicidial
EOF
fi

# Keep .env and data; refresh code
rsync -a \
  --exclude '.git' \
  --exclude '.env' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'data/' \
  "$SRC_DIR/" "$APP_DIR/"

chmod +x "$APP_DIR"/scripts/*.sh "$APP_DIR"/install.sh 2>/dev/null || true
cd "$APP_DIR"

# Ensure new env keys exist without overwriting secrets
grep -q '^SIP_MODE=' .env 2>/dev/null || echo 'SIP_MODE=ip' >> .env
grep -q '^ADMIN_PASSWORD=' .env 2>/dev/null || echo 'ADMIN_PASSWORD=Openaccount@123' >> .env

echo "==> Rebuilding containers (api, portal, asterisk, worker)"
docker compose up -d --build api portal asterisk worker

echo "==> Waiting for API"
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "API OK"
    break
  fi
  sleep 2
done

echo ""
echo "Update complete."
echo "  Portal: http://$(hostname -I | awk '{print $1}'):3000"
echo "  Login:  see ADMIN_EMAIL / ADMIN_PASSWORD in $APP_DIR/.env"
echo "  Vicidial: carriers + DIDs + remote agents only (no webhooks)"
echo ""
echo "Hard refresh browser (Ctrl+F5). Check Portal → SIP Carrier / VICIdial Servers."
