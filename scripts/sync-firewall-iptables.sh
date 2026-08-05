#!/bin/sh
# ============================================================
# AIBOTS — restrict Asterisk SIP/RTP to portal Vicidial IPs only
# Runs in privileged host-network container (DOCKER-USER chain).
#
# Reads: /allowed_ips.txt  (one IPv4 per line)
# Env:   AIBOTS_SIP_OPEN=1  → allow all SIP/RTP (debug only)
# ============================================================
set -eu

IPS_FILE="${IPS_FILE:-/allowed_ips.txt}"
CHAIN="AIBOTS_FILTER"
OPEN="${AIBOTS_SIP_OPEN:-0}"

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

  # Allow localhost + docker bridge (compose health / internal)
  iptables -A "$c" -s 127.0.0.1 -p udp --dport 5060 -j RETURN
  iptables -A "$c" -s 127.0.0.1 -p tcp --dport 5060 -j RETURN
  iptables -A "$c" -s 172.16.0.0/12 -p udp --dport 5060 -j RETURN
  iptables -A "$c" -s 172.16.0.0/12 -p tcp --dport 5060 -j RETURN

  if [ "$OPEN" = "1" ] || [ "$OPEN" = "true" ] || [ "$OPEN" = "yes" ]; then
    echo "aibots-firewall: AIBOTS_SIP_OPEN=1 — allowing ALL SIP/RTP (debug)"
    iptables -A "$c" -p udp --dport 5060 -j RETURN
    iptables -A "$c" -p tcp --dport 5060 -j RETURN
    iptables -A "$c" -p udp --dport 10000:10100 -j RETURN
    iptables -A "$c" -j RETURN
    return
  fi

  if [ -z "$IPS" ]; then
    # No Vicidial IPs yet — DROP public SIP scanners; no dialers allowed until portal add
    echo "aibots-firewall: WARNING no allowed IPs — dropping all public SIP/RTP"
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

  # Log then drop (rate-limited) so diagnose can see hits
  iptables -A "$c" -p udp --dport 5060 -m limit --limit 2/min -j LOG \
    --log-prefix "AIBOTS-SIP-DROP " --log-level 4 2>/dev/null || true
  iptables -A "$c" -p tcp --dport 5060 -m limit --limit 2/min -j LOG \
    --log-prefix "AIBOTS-SIP-DROP " --log-level 4 2>/dev/null || true

  # Block everyone else on SIP + RTP used by Asterisk
  iptables -A "$c" -p udp --dport 5060 -j DROP
  iptables -A "$c" -p tcp --dport 5060 -j DROP
  iptables -A "$c" -p udp --dport 10000:10100 -j DROP
  iptables -A "$c" -j RETURN
}

build_chain "$CHAIN"
build_chain "${CHAIN}_IN"

COUNT=$(echo "$IPS" | grep -c . 2>/dev/null || echo 0)
echo "aibots-firewall: allowed SIP/RTP from ${COUNT} IP(s) (OPEN=$OPEN)"
if [ -n "$IPS" ]; then
  echo "$IPS" | sed 's/^/  allow /'
fi
