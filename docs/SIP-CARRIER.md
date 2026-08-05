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
SIMULATE_MODE=false
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
same => n,Dial(SIP/aibots/27001,60,tT)
same => n,Hangup()

exten => _27002,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,AGI(agi-set_variables.agi,)
same => n,SIPAddHeader(X-VICIdial-Lead-Id: ${lead_id})
same => n,SIPAddHeader(X-VICIdial-Caller-Id: ${phone_number})
same => n,SIPAddHeader(X-VICIdial-Client-Id: CID_0006-b)
same => n,SIPAddHeader(X-VICIdial-User-Id: 27016)
same => n,SIPAddHeader(X-VICIdial-Campaign-Id: ${campaign_id})
same => n,Dial(SIP/aibots/27002,60,tT)
same => n,Hangup()
```

Use `Dial(SIP/aibots/27001)` so the SIP Request-URI has a numeric user (not bare `Dial(SIP/aibots)`, which often sends URI user=`aibots` or the IP and used to 404 on AIBOTS).

**Critical:** Portal → VICIdial Servers must list the Vicibox **public** SIP source IP (what AIBOTS sees on UDP/5060). Private LAN IPs in the allow-list will drop the INVITE — portal Calls stays empty and there is no bot audio.

On VICIdial Asterisk, SIP peer toward AIBOTS (portal **SIP Carrier** shows exact text):

```
[aibots]
host=YOUR_AIBOTS_IP
type=peer
disallow=all
allow=ulaw
insecure=port,invite
nat=force_rport,comedia
qualify=yes
; DO NOT set username= or secret= — that causes:
;   Failed to authenticate on INVITE → CONGESTION → instant hangup
```

Also fix DNS if logs show `Unable to lookup 'vicibox9'`:
`echo '127.0.0.1 vicibox9' >> /etc/hosts` (or the real LAN IP).

### Vicibox `[from-aibots]` (Custom Dialplan Entry)

Use this **only** (Admin → System Settings → Custom Dialplan Entry).  
Do **not** add `exten => _X.,1,Goto(default,${EXTEN},1)` — that often breaks outbound and plays *“number not in service”*.

```
[from-aibots]
exten => _1060XXXXXX,1,Goto(default,${EXTEN},1)
exten => _.,1,NoOp(Ignore AIBOTS signalling ${EXTEN})
 same => n,Hangup()
```

Peer `[aibots]` must use `context=from-aibots`.

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
