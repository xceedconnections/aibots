# AIBOTS Installation (Ubuntu / Debian)

Self-hosted VICIdial AI Voice Bot platform with a CRM-style portal
(Campaigns, VICIdial Servers, SIP Carrier, Settings) — same look as AI AMD.

## One-line install (recommended)

On a **fresh Ubuntu 22.04 / 24.04 or Debian 12** server:

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
```

This will:

1. Install Docker + Compose  
2. Clone [xceedconnections/aibots](https://github.com/xceedconnections/aibots)  
3. Deploy to `/opt/aibots`  
4. Start Postgres, Redis, Ollama, API, Worker, Asterisk, Portal, Nginx  
5. Pull `qwen2.5:7b-instruct`  
6. Download Piper TTS voice  
7. Open firewall for HTTP + SIP/RTP  
8. Write `/opt/aibots/INSTALL-INFO.txt` with login + IPs  

**First run: 15–40 minutes** (images + ~4GB model).

### Optional overrides

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | \
  sudo PUBLIC_IP=203.0.113.10 \
       VICIDIAL_IP=198.51.100.20 \
       ADMIN_PASSWORD='YourStrongPass!' \
       AIBOTS_SIP_PASSWORD='aibotsSipPass123' \
       bash
```

Skip large model downloads (install stack only):

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | \
  sudo SKIP_MODELS=1 bash
```

## Fix broken Docker apt on Debian (ubuntu/bookworm 404)

If install failed with `download.docker.com/linux/ubuntu bookworm`:

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/scripts/fix-docker-debian.sh | sudo bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | \
  sudo ADMIN_PASSWORD='Openaccount@123' bash
```

Or manually:

```bash
sudo rm -f /etc/apt/sources.list.d/docker.list
sudo apt-get update -y
curl -fsSL https://get.docker.com | sudo sh
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
```

## After install — add Vicidial servers later

Install does **not** require Vicidial upfront. In the portal:

1. **VICIdial Servers** → Add each dialer **by IP** (IP-based peer, no SIP registration)
2. **Campaigns / Bots** → Client ID, Remote Agent, Transfer DID
3. **SIP Carrier** → copy IP peer + dialplan into Vicidial

Default login password: `Openaccount@123`

### Portal menu (CRM-style)

| Page | Purpose |
|------|---------|
| Dashboard | Calls / transfer stats |
| Campaigns | AI campaigns + copy-paste carrier dialplan |
| Bots / Scripts | Qualification scripts & answers |
| Calls | Call sessions |
| VICIdial Servers | Register dialer boxes |
| SIP Carrier | Full Vicidial carrier peer + dialplans |
| Settings | PUBLIC_IP, SIP password, defaults |

## Manual install (already cloned)

```bash
git clone https://github.com/xceedconnections/aibots.git
cd aibots
sudo bash scripts/install-ubuntu.sh
```

## Requirements

| | Minimum | Recommended |
|--|---------|-------------|
| OS | Ubuntu 22.04+ / Debian 12 | Ubuntu 24.04 |
| CPU | 8 cores | 16–32 |
| RAM | 16 GB | 32–64 GB |
| Disk | 80 GB SSD | 200 GB+ |
| GPU | optional | RTX 4070+ / L4 |

## VICIdial (carrier only)

No scripts on Vicidial. Configure:

1. AI SIP carrier → AIBOTS  
2. Remote agents  
3. Virtual DIDs → closer in-groups  

See [docs/SIP-CARRIER.md](docs/SIP-CARRIER.md) and portal **SIP Carrier**.

## Useful commands

```bash
cd /opt/aibots
sudo docker compose ps
sudo docker compose logs -f api worker asterisk
sudo docker compose restart
sudo cat /opt/aibots/INSTALL-INFO.txt
```

## Uninstall

```bash
cd /opt/aibots
sudo docker compose down -v
sudo rm -rf /opt/aibots /opt/aibots-src
```
