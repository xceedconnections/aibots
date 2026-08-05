#!/bin/sh
# ============================================================
# AIBOTS — restrict Asterisk SIP/RTP to portal Vicidial IPs only
# Runs in privileged host-network container (DOCKER-USER chain).
#
# Reads: /allowed_ips.txt  (one IPv4 per line)
# ============================================================
set -eu

IPS_FILE="${IPS_FILE:-/allowed_ips.txt}"
CHAIN="AIBOTS_FILTER"

# Collect IPv4s
IPS=""
if [ -f "$IPS_FILE" ]; then
  IPS=$(grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' "$IPS_FILE" | sort -u || true)
fi

# Ensure chain exists and is empty
iptables -N "$CHAIN" 2>/dev/null || true
iptables -F "$CHAIN"

# Jump from DOCKER-USER (Docker publishes 5060/RTP here)
if ! iptables -C DOCKER-USER -j "$CHAIN" 2>/dev/null; then
  iptables -I DOCKER-USER 1 -j "$CHAIN"
fi

# Also cover host INPUT (in case something binds on host)
iptables -N "${CHAIN}_IN" 2>/dev/null || true
iptables -F "${CHAIN}_IN"
if ! iptables -C INPUT -j "${CHAIN}_IN" 2>/dev/null; then
  iptables -I INPUT 1 -j "${CHAIN}_IN"
fi

build_chain() {
  c="$1"
  # Always allow established media/signaling return traffic
  iptables -A "$c" -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN 2>/dev/null \
    || iptables -A "$c" -m state --state RELATED,ESTABLISHED -j RETURN 2>/dev/null \
    || true

  # Allow localhost
  iptables -A "$c" -s 127.0.0.1 -p udp --dport 5060 -j RETURN
  iptables -A "$c" -s 127.0.0.1 -p tcp --dport 5060 -j RETURN

  if [ -z "$IPS" ]; then
    # No Vicidial IPs yet — DROP public SIP scanners; no dialers allowed until portal add
    iptables -A "$c" -p udp --dport 5060 -j DROP
    iptables -A "$c" -p tcp --dport 5060 -j DROP
    iptables -A "$c" -p udp --dport 10000:10100 -j DROP
    iptables -A "$c" -j RETURN
    return
  fi

  for ip in $IPS; do
    iptables -A "$c" -s "$ip" -p udp --dport 5060 -j RETURN
    iptables -A "$c" -s "$ip" -p tcp --dport 5060 -j RETURN
    iptables -A "$c" -s "$ip" -p udp --dport 10000:10100 -j RETURN
  done

  # Block everyone else on SIP + RTP used by Asterisk
  iptables -A "$c" -p udp --dport 5060 -j DROP
  iptables -A "$c" -p tcp --dport 5060 -j DROP
  iptables -A "$c" -p udp --dport 10000:10100 -j DROP
  iptables -A "$c" -j RETURN
}

build_chain "$CHAIN"
build_chain "${CHAIN}_IN"

COUNT=$(echo "$IPS" | grep -c . 2>/dev/null || echo 0)
echo "aibots-firewall: allowed SIP/RTP from ${COUNT} IP(s)"
if [ -n "$IPS" ]; then
  echo "$IPS" | sed 's/^/  allow /'
fi
