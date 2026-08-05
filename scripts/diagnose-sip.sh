#!/usr/bin/env bash
# Quick SIP/AudioSocket diagnostics on the AIBOTS host
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/aibots}"
cd "$APP_DIR"

echo "==> Containers"
docker compose ps

echo ""
echo "==> allowed_ips.txt (firewall allow-list — MUST be Vicibox PUBLIC IP)"
cat -n data/asterisk/allowed_ips.txt 2>/dev/null || echo "(missing)"

echo ""
echo "==> AIBOTS_SIP_OPEN / PUBLIC_IP from .env"
grep -E '^(AIBOTS_SIP_OPEN|PUBLIC_IP|ASTERISK_AMI_HOST)=' .env 2>/dev/null || true

echo ""
echo "==> Firewall container log"
docker logs --tail 15 aibots-firewall 2>&1 || true

echo ""
echo "==> iptables AIBOTS_FILTER (DROP counters rise if Vicibox IP is wrong)"
iptables -L AIBOTS_FILTER -n -v 2>/dev/null | head -40 || echo "(run as root for iptables)"

echo ""
echo "==> Dialplan inside Asterisk"
docker exec aibots-asterisk grep -n "AudioSocket\|new-uuid\|ASUUID" /etc/asterisk/extensions.conf || true

echo ""
echo "==> Identify (must include match=0.0.0.0/0)"
docker exec aibots-asterisk cat /etc/asterisk/pjsip_identify.conf || true

echo ""
echo "==> Modules"
docker exec aibots-asterisk asterisk -rx "module show like audiosocket" || true
docker exec aibots-asterisk asterisk -rx "module show like curl" || true

echo ""
echo "==> PJSIP endpoints"
docker exec aibots-asterisk asterisk -rx "pjsip show endpoints" || true
docker exec aibots-asterisk asterisk -rx "pjsip show identifies" || true

echo ""
echo "==> DNS + CURL from Asterisk → API"
docker exec aibots-asterisk getent hosts api worker 2>/dev/null || true
docker exec aibots-asterisk curl -fsS "http://api:8000/internal/sip/ping" || echo "FAIL ping"
echo
docker exec aibots-asterisk curl -fsS "http://api:8000/internal/sip/new-uuid" || echo "FAIL uuid"
echo

echo ""
echo "==> Recent API SIP call-start (live calls)"
docker logs --tail 60 aibots-api 2>&1 | grep -iE 'call-start|SIP call-start' || echo "(none — Vicidial SIP is NOT hitting AIBOTS)"

echo ""
echo "==> Recent worker AudioSocket"
docker logs --tail 40 aibots-worker 2>&1 | grep -iE 'AudioSocket|Live call|BOT:|UUID' || echo "(none)"

echo ""
echo "==> Recent Asterisk AIBOTS markers"
docker logs --tail 120 aibots-asterisk 2>&1 | grep -iE 'AIBOTS|AudioSocket|from-vicidial|Failed to parse UUID' || echo "(none — no dialplan hits)"

echo ""
echo "==> dmesg SIP drops (if logged)"
dmesg 2>/dev/null | grep -i 'AIBOTS-SIP-DROP' | tail -10 || true

echo ""
echo "If call-start is none during a live dial:"
echo "  1) Put Vicibox PUBLIC IP in Portal → VICIdial Servers → Sync"
echo "  2) Or debug open:  echo AIBOTS_SIP_OPEN=1 >> .env && docker compose up -d firewall"
echo "  3) On Vicibox use: Dial(SIP/aibots)  with peer host=AIBOTS_PUBLIC_IP (not @wrong-IP)"
echo "  4) During a call:  tcpdump -n -i any udp port 5060"
