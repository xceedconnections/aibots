# VICIdial setup (carrier-only — no webhooks)

**Do not** set Start Call URL, Dispo URL, or any HTTP webhook on VICIdial.

Commercial AI bots only need:

1. AI SIP **carrier** (IP peer → AIBOTS)
2. **Remote agents**
3. Virtual **DIDs** → closer in-groups
4. Optional **Ctransfer** carrier

Full dialplans: [SIP-CARRIER.md](SIP-CARRIER.md) · Portal → **SIP Carrier**

## Call path

```
Vicidial campaign (AI carrier)
   → SIP INVITE + X-VICIdial-* headers
   → AIBOTS Asterisk answers + AI
   → (qualified) Dial Transfer DID back to Vicidial
   → closer agents
```

Vicidial never calls `http://AIBOTS/...` — only SIP.

## What AIBOTS reads from the SIP INVITE

| Header | Used for |
|--------|----------|
| `X-VICIdial-Lead-Id` | Lead id |
| `X-VICIdial-Caller-Id` | Customer phone |
| `X-VICIdial-Client-Id` | Which bot (Client ID) |
| `X-VICIdial-User-Id` | Remote agent / bot match |
| `X-VICIdial-Campaign-Id` | Campaign match fallback |

## Transfer

Bot action `transfer` → AIBOTS dials the bot **Transfer DID** into Vicidial SIP.
That DID must be an inbound virtual DID routed to closers.

## Test without live dials

Portal → Bot → **Run test call** (simulate), or:

```bash
bash scripts/test-call.sh
docker logs -f aibots-worker
```
