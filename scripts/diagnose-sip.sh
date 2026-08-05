#!/usr/bin/env bash
# Quick SIP/AudioSocket diagnostics on the AIBOTS host
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/aibots}"
cd "$APP_DIR"

echo "==> Containers"
docker compose ps

echo ""
echo "==> Dialplan inside Asterisk (must show AudioSocket(uuid,worker:9092))"
docker exec aibots-asterisk grep -n "AudioSocket\|new-uuid\|ASUUID" /etc/asterisk/extensions.conf || true

echo ""
echo "==> Modules"
docker exec aibots-asterisk asterisk -rx "module show like audiosocket" || true
docker exec aibots-asterisk asterisk -rx "module show like curl" || true
docker exec aibots-asterisk asterisk -rx "module show like md5" || true

echo ""
echo "==> DNS from Asterisk → api / worker"
docker exec aibots-asterisk getent hosts api worker 2>/dev/null || \
  docker exec aibots-asterisk ping -c1 -W1 api 2>/dev/null || true

echo ""
echo "==> CURL from Asterisk container to API"
docker exec aibots-asterisk curl -fsS "http://api:8000/internal/sip/ping" || echo "FAIL ping"
docker exec aibots-asterisk curl -fsS "http://api:8000/internal/sip/new-uuid" || echo "FAIL uuid"

echo ""
echo "==> Recent API SIP lines"
docker logs --tail 40 aibots-api 2>&1 | grep -iE 'call-start|SIP|uuid' || true

echo ""
echo "==> Recent worker AudioSocket"
docker logs --tail 40 aibots-worker 2>&1 | grep -iE 'AudioSocket|Live call|BOT:|UUID' || true

echo ""
echo "==> Recent Asterisk verbose (AIBOTS markers)"
docker logs --tail 100 aibots-asterisk 2>&1 | grep -iE 'AIBOTS|AudioSocket|Failed to parse UUID|call-start' || true

echo ""
echo "==> Portal DB call count (via API)"
curl -fsS "http://127.0.0.1:8000/calls?limit=5" 2>/dev/null | head -c 500 || echo "(auth may be required)"

echo ""
echo "Place a test call, then re-run this script."
