#!/usr/bin/env bash
# ============================================================
# AIBOTS — one-line installer (clone from GitHub + setup)
#
#   curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
#
# Optional env vars:
#   APP_DIR=/opt/aibots
#   BRANCH=main
#   REPO_URL=https://github.com/xceedconnections/aibots.git
# ============================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/xceedconnections/aibots.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/aibots}"
SRC_DIR="${SRC_DIR:-/opt/aibots-src}"

echo "============================================================"
echo " AIBOTS installer (from GitHub)"
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

echo "==> Installing git + curl (if needed)"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl git
else
  echo "ERROR: This installer supports Ubuntu/Debian (apt)."
  exit 1
fi

echo "==> Cloning AIBOTS"
rm -rf "$SRC_DIR"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$SRC_DIR"

chmod +x "$SRC_DIR"/scripts/*.sh "$SRC_DIR"/install.sh 2>/dev/null || true

echo "==> Running Ubuntu setup"
APP_DIR="$APP_DIR" REPO_DIR="$SRC_DIR" bash "$SRC_DIR/scripts/install-ubuntu.sh"

echo ""
echo "Done. Docs: https://github.com/xceedconnections/aibots#readme"
