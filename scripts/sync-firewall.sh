#!/usr/bin/env bash
# ============================================================
# Host UFW helper (optional). Prefer docker aibots-firewall service.
#   sudo bash /opt/aibots/scripts/sync-firewall.sh
# ============================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aibots}"
IPS_FILE="${IPS_FILE:-$APP_DIR/data/asterisk/allowed_ips.txt}"
IDENTIFY="${IDENTIFY:-$APP_DIR/data/asterisk/pjsip_identify.conf}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root"
  exit 1
fi

command -v ufw >/dev/null || { echo "ufw not installed"; exit 1; }

# Build IP list from allowed_ips.txt or identify conf
mapfile -t IPS < <(
  {
    [[ -f "$IPS_FILE" ]] && cat "$IPS_FILE"
    [[ -f "$IDENTIFY" ]] && grep -E '^match=' "$IDENTIFY" | cut -d= -f2
  } | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | sort -u
)

echo "==> Syncing UFW for AIBOTS SIP (IPs: ${#IPS[@]})"

# Delete previous aibots-sip rules (numbered delete from high to low)
while true; do
  NUM=$(ufw status numbered 2>/dev/null | grep -F 'aibots-sip' | head -1 | sed -n 's/^\[\s*\([0-9]\+\)\].*/\1/p' || true)
  [[ -z "${NUM:-}" ]] && break
  yes | ufw delete "$NUM" >/dev/null || break
done

# Prefer docker firewall; still remove world-open SIP if present
while true; do
  NUM=$(ufw status numbered 2>/dev/null | grep -E '5060/(udp|tcp).*ALLOW IN.*Anywhere' | head -1 | sed -n 's/^\[\s*\([0-9]\+\)\].*/\1/p' || true)
  [[ -z "${NUM:-}" ]] && break
  yes | ufw delete "$NUM" >/dev/null || break
done

for ip in "${IPS[@]:-}"; do
  [[ -z "$ip" ]] && continue
  ufw allow from "$ip" to any port 5060 proto udp comment 'aibots-sip' || true
  ufw allow from "$ip" to any port 5060 proto tcp comment 'aibots-sip' || true
  ufw allow from "$ip" to any port 10000:10100 proto udp comment 'aibots-sip' || true
  echo "  allow $ip → 5060 + RTP"
done

# Deny public SIP (allows above take precedence for listed IPs)
ufw deny 5060/udp comment 'aibots-sip' || true
ufw deny 5060/tcp comment 'aibots-sip' || true

ufw reload || true
echo "Done. Portal → VICIdial Servers controls the allow-list."
