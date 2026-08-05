# SIP Carrier Mode — commercial AI bot pattern (no Vicidial webhooks)

VICIdial only needs:

1. An **AI carrier** (IP peer + dialplan → AIBOTS)
2. A **transfer / Ctransfer carrier** (optional prefixes)
3. **Remote agents** (e.g. 27001)
4. **Virtual DIDs** routed to closer in-groups (e.g. 106027001)

**No Start Call URL. No Dispo URL. No HTTP webhook on Vicidial.**
Vicidial talks to AIBOTS over **SIP only** (same as other AI bot vendors).

## Call flow

```
Outbound campaign (carrier = AIBOTS)
      │
      │ Dial(SIP/aibots@AIBOTS_IP) + X-VICIdial-* headers
      ▼
AIBOTS Asterisk
      │  reads Lead-Id, Caller-Id, Client-Id, User-Id, Campaign-Id
      ├─ CURL → API (pick bot by Client-Id / Remote Agent)
      └─ AudioSocket → AI (Whisper + script + Piper)
              │
              ▼ qualified
         Dial(PJSIP/{TRANSFER_DID}@vicidial-out)
              │
              ▼
VICIdial inbound DID → closer in-group → live agent
```

## AIBOTS `.env`

```env
PUBLIC_IP=YOUR_AIBOTS_PUBLIC_IP
AIBOTS_SIP_PASSWORD=aibotsSipPass123
ASTERISK_AMI_HOST=YOUR_VICIDIAL_IP
SIMULATE_MODE=true
```

```bash
sudo ufw allow from YOUR_VICIDIAL_IP to any port 5060 proto udp
sudo ufw allow from YOUR_VICIDIAL_IP to any port 10000:10100 proto udp
cd /opt/aibots && sudo docker compose up -d --build asterisk worker api portal
```

## VICIdial — AI Carrier dialplan

Paste into **Admin → Carriers → AIBOTS → Dialplan** (match Client-Id / User-Id to bots):

```
exten => _27001,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,AGI(agi-set_variables.agi,)
same => n,SIPAddHeader(X-VICIdial-Lead-Id: ${lead_id})
same => n,SIPAddHeader(X-VICIdial-Caller-Id: ${phone_number})
same => n,SIPAddHeader(X-VICIdial-Client-Id: CID_0006-a)
same => n,SIPAddHeader(X-VICIdial-User-Id: 27001)
same => n,SIPAddHeader(X-VICIdial-Campaign-Id: ${campaign_id})
same => n,Dial(SIP/aibots@YOUR_AIBOTS_IP)
same => n,Hangup()

exten => _27002,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,AGI(agi-set_variables.agi,)
same => n,SIPAddHeader(X-VICIdial-Lead-Id: ${lead_id})
same => n,SIPAddHeader(X-VICIdial-Caller-Id: ${phone_number})
same => n,SIPAddHeader(X-VICIdial-Client-Id: CID_0006-b)
same => n,SIPAddHeader(X-VICIdial-User-Id: 27016)
same => n,SIPAddHeader(X-VICIdial-Campaign-Id: ${campaign_id})
same => n,Dial(SIP/aibots@YOUR_AIBOTS_IP)
same => n,Hangup()
```

Globals example: `SIP/aibots@YOUR_AIBOTS_IP`

On VICIdial Asterisk, SIP peer toward AIBOTS (portal **SIP Carrier** shows exact text):

```
[aibots]
host=YOUR_AIBOTS_IP
username=aibots
secret=aibotsSipPass123
type=peer
disallow=all
allow=ulaw
insecure=port,invite
nat=force_rport,comedia
```

## VICIdial — virtual DIDs

Create DIDs e.g. `106027001`, `106027002` and route each to a closer in-group.

## VICIdial — optional Ctransfer carrier

```
exten => _37000,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,Set(DID=106027001)
same => n,Dial(SIP/Ctransfer1/${DID},,tTor)
same => n,Hangup()

exten => _67000,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,Set(DID=106027001)
same => n,Dial(SIP/Ctransfer1/${DID},,tTor)
same => n,Hangup()

exten => _67001,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,Set(DID=106027002)
same => n,Dial(SIP/Ctransfer1/${DID},,tTor)
same => n,Hangup()
```

AIBOTS itself dials the virtual DID directly on transfer; Ctransfer is only needed if you also use Vicidial-side transfer prefixes.

## VICIdial — remote agents

Create remote agents `27001`, `27016`, etc. matching `X-VICIdial-User-Id`.

## AIBOTS portal — bot fields

| Field | Example | Maps to |
|-------|---------|---------|
| Client ID | `CID_0006-a` | `X-VICIdial-Client-Id` |
| Remote Agent | `27001` | `X-VICIdial-User-Id` |
| Transfer DID | `106027001` | Virtual DID → closers |
| Campaign | your campaign id | `X-VICIdial-Campaign-Id` |
| Transfer campaign | closer in-group name | labeling / optional API |

Portal → **SIP Carrier** has the full copy-paste pack.

## Checklist

- [ ] `PUBLIC_IP` + SIP password set; Asterisk container up
- [ ] UDP 5060 + RTP open from Vicidial IP
- [ ] AI carrier + dialplan + SIP peer on Vicidial
- [ ] Remote agents created
- [ ] Virtual DIDs → closer groups
- [ ] Bot Client ID / Remote Agent / Transfer DID match dialplan
- [ ] Carrier assigned to outbound campaign
- [ ] `docker logs -f aibots-asterisk` and `aibots-worker` on first live dial
