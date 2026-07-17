# VICIdial ↔ AIBOTS Integration

## 1. Campaign Start Call URL

In VICIdial Admin → Campaigns → your outbound campaign:

**Start Call URL** (or similar Dispo / external URL field your build supports):

```
http://AIBOTS_SERVER_IP/webhook/vicidial/start?campaign=ACA2026&bot_id=1
```

Or POST form fields to:

```
http://AIBOTS_SERVER_IP/webhook/vicidial/start/form
```

Supported fields:

| Field | Description |
|-------|-------------|
| `call_id` / `uniqueid` | Asterisk uniqueid / call id |
| `lead_id` | VICIdial lead id |
| `phone` / `phone_number` | Customer number |
| `campaign` / `campaign_id` | Maps to bot.campaign |
| `bot_id` | Optional explicit bot |
| `channel` | Asterisk channel name (for AMI redirect) |

## 2. API User

Create a VICIdial API user (e.g. user `6666`) with:

- Non-Agent API access
- Modify leads
- Remote agent / call control if available

Put credentials in AIBOTS `.env`:

```
VICIDIAL_URL=http://VICIDIAL_IP/vicidial
VICIDIAL_USER=6666
VICIDIAL_PASS=xxxxxxxx
```

## 3. Closer campaign

Create (or use) a closer / inbound group campaign, e.g. `ACA_CLOSERS`.

In AIBOTS portal → Bot settings → **Transfer campaign** = `ACA_CLOSERS`.

## 4. AMI user (for live transfer)

On Asterisk (`/etc/asterisk/manager.conf`):

```
[aibots]
secret = ami_secret
deny=0.0.0.0/0.0.0.0
permit=AIBOTS_SERVER_IP/255.255.255.255
read = system,call,agent
write = system,call,agent,originate
```

Match `.env`:

```
ASTERISK_AMI_HOST=VICIDIAL_IP
ASTERISK_AMI_PORT=5038
ASTERISK_AMI_USER=aibots
ASTERISK_AMI_SECRET=ami_secret
```

Load dialplan from `docs/asterisk-aibots-transfer.conf`.

## 5. Audio path (phase 2)

MVP runs in **simulate mode** (scripted text answers) to validate scripts + transfer API.

Live audio bridge options:

1. Local channel / ARI external media into AIBOTS worker RTP
2. SIP trunk from Asterisk to a small FreeSWITCH/Janus media service
3. Custom AGI streaming PCM to worker Redis audio queue

Set in worker env when ready:

```
SIMULATE_MODE=false
```

## 6. Test without VICIdial

```bash
bash scripts/test-call.sh
docker logs -f aibots-worker
```
