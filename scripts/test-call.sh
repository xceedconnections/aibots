#!/usr/bin/env bash
# Quick simulated call against running API (no VICIdial needed)
set -euo pipefail
API="${API:-http://127.0.0.1:8000}"
CAMPAIGN="${CAMPAIGN:-ACA2026}"

echo "Starting test call via $API ..."
curl -sS -X POST "$API/internal/sip/call-start" \
  -H 'Content-Type: application/json' \
  -d "{
    \"campaign\": \"$CAMPAIGN\",
    \"phone\": \"5551234567\",
    \"lead_id\": \"TEST$(date +%s)\",
    \"call_id\": \"sim-$(date +%s)\",
    \"extra\": {\"simulate\": true}
  }" | jq .

echo ""
echo "Watch: docker logs -f aibots-worker"
echo "Calls:  curl -s $API/calls | jq ."
