#!/usr/bin/env bash
# Quick health check for AIBOTS stack
set -euo pipefail
cd "${APP_DIR:-/opt/aibots}"

echo "==> Containers"
docker compose ps

echo ""
echo "==> API health (localhost:8000)"
curl -fsS http://127.0.0.1:8000/health && echo || echo "FAIL: API not responding on :8000"

echo ""
echo "==> API via portal proxy (:3000/api/health)"
curl -fsS http://127.0.0.1:3000/api/health && echo || echo "FAIL: portal /api proxy"

echo ""
echo "==> Last API logs"
docker logs --tail 40 aibots-api 2>&1 || true

echo ""
echo "==> Last portal logs"
docker logs --tail 20 aibots-portal 2>&1 || true
