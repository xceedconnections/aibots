#!/usr/bin/env bash
# Run on VICIBOX as root — finds why "number not in service" plays after answer
set -euo pipefail

echo "========== sip peer aibots =========="
asterisk -rx "sip show peer aibots" 2>&1 | egrep -i 'Context|Status|Host|Username|Secret|Insecure|Addr|tohost' || \
  asterisk -rx "sip show peer aibots" 2>&1 | head -40

echo ""
echo "========== dialplan 27001@default =========="
asterisk -rx "dialplan show 27001@default" 2>&1 || true

echo ""
echo "========== dialplan from-aibots =========="
asterisk -rx "dialplan show from-aibots" 2>&1 || true

echo ""
echo "========== who plays ss-noservice =========="
asterisk -rx "dialplan show" 2>&1 | grep -i 'ss-noservice\|not in service\|Congestion\|Invalid' | head -40 || true
grep -RIn 'ss-noservice\|not.in.service' /etc/asterisk/*.conf 2>/dev/null | head -40 || true

echo ""
echo "========== carrier / 27001 mentions =========="
grep -RIn '27001\|aibots\|from-aibots' /etc/asterisk/*.conf 2>/dev/null | head -60 || true

echo ""
echo "========== DONE =========="
echo "Next: asterisk -rvvv   then place ONE call."
echo "When you hear 'not in service', look for: Playback / ss-noservice / 27001 / aibots / CHANUNAVAIL"
