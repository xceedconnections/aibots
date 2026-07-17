# Vendor-style SIP Carrier Mode (like commercial AI bots)

AIBOTS can integrate the same way most AI dialer vendors do:

1. You create a **Carrier** in VICIdial pointing at AIBOTS SIP
2. Your campaign uses that carrier
3. When the customer answers, audio goes to AIBOTS Asterisk → AI engine
4. When qualified, call transfers to your closer campaign

**No Start Call URL required. No editing VICIdial `manager.conf` required** for the basic SIP path.

## Architecture

```
VICIdial Campaign
      │
      │ Carrier: AIBOTS (SIP)
      ▼
AIBOTS Asterisk :5060
      │
      ├─ CURL → API (start session / load bot script)
      └─ AudioSocket → Worker (Whisper + Piper + decision engine)
              │
              ▼ (qualified)
         Transfer → closer via SIP/AMI
```

## Portal

Open **SIP Carrier** in the portal for copy-paste values.

## .env on AIBOTS

```env
PUBLIC_IP=168.119.115.117
AIBOTS_SIP_PASSWORD=aibotsSipPass123
ASTERISK_AMI_HOST=62.238.46.190
SIMULATE_MODE=true
```

`SIMULATE_MODE=true` keeps portal **Run test call** working. Live SIP calls set `simulate=false` automatically.

## Start Asterisk

```bash
cd /opt/aibots
# set PUBLIC_IP + AIBOTS_SIP_PASSWORD in .env
sudo ufw allow from YOUR_VICIDIAL_IP to any port 5060 proto udp
sudo ufw allow from YOUR_VICIDIAL_IP to any port 10000:10100 proto udp
sudo docker compose up -d --build asterisk worker api portal
```

## VICIdial steps

1. **Admin → Carriers → Add**
   - Account: `AIBOTS`
   - Protocol: `SIP`
   - Globals: `SIP/aibots@YOUR_AIBOTS_IP`
2. On VICIdial Asterisk, add SIP peer (or PJSIP equivalent) to AIBOTS host (portal shows exact text).
3. Assign carrier **AIBOTS** to your outbound campaign.
4. In AIBOTS portal bot: set **Campaign** + **Transfer campaign** to match VICIdial.

## Test without live dials

Portal → Bot → **Run test call** (simulate).

## Live path checklist

- [ ] `PUBLIC_IP` correct
- [ ] UDP 5060 + RTP open from VICIdial IP
- [ ] Carrier assigned to campaign
- [ ] Bot campaign name matches
- [ ] `docker logs -f aibots-asterisk`
- [ ] `docker logs -f aibots-worker`

## Notes

- First live audio quality depends on Piper model download + Whisper model load.
- Closer transfer dialplan may need tuning for your in-group; share closer name for exact Dial() string.
- Legacy Start Call URL + AMI still exist as fallback but are not required for carrier mode.
