# Deploy AIBOTS on a fresh Ubuntu server

## Fastest path (from GitHub)

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
```

Full guide: [INSTALL.md](../INSTALL.md)

**First run: 15–40 minutes** (Docker images + ~4GB LLM download).

## Alternative — clone then install

```bash
git clone https://github.com/xceedconnections/aibots.git
cd aibots
sudo bash scripts/install-ubuntu.sh
```

## After install

| Service | URL |
|---------|-----|
| Portal | `http://SERVER_IP:3000` |
| API | `http://SERVER_IP:8000` |
| API docs | `http://SERVER_IP:8000/docs` |
| Nginx | `http://SERVER_IP/` |

Login: `xceedconnections@gmail.com` / `Openaccount@123`

### Configure

```bash
sudo nano /opt/aibots/.env
```

Set at minimum:

```
VITE_API_URL=http://YOUR_UBUNTU_IP:8000
CORS_ORIGINS=http://YOUR_UBUNTU_IP:3000,http://YOUR_UBUNTU_IP
ADMIN_PASSWORD=YourStrongPassword
VICIDIAL_URL=http://YOUR_VICIDIAL_IP/vicidial
VICIDIAL_USER=6666
VICIDIAL_PASS=your_api_pass
ASTERISK_AMI_HOST=YOUR_VICIDIAL_IP
ASTERISK_AMI_SECRET=ami_secret
```

Rebuild portal after changing `VITE_API_URL`:

```bash
cd /opt/aibots
sudo docker compose up -d --build portal
```

### Test without VICIdial

```bash
cd /opt/aibots
sudo bash scripts/test-call.sh
sudo docker logs -f aibots-worker
```

### Point VICIdial at AIBOTS (SIP carrier only — no HTTP webhook)

On VICIdial you only configure:

1. AI SIP carrier → AIBOTS IP (IP peer, no registration)
2. Remote agents
3. Virtual DIDs → closer in-groups
4. Optional Ctransfer carrier

**Do not** set any Start Call URL / Dispo URL / webhook on Vicidial.
Vicidial never calls AIBOTS over HTTP — only SIP.

Portal → **SIP Carrier** and **VICIdial Servers** have the copy-paste pack.
Details: [SIP-CARRIER.md](SIP-CARRIER.md) · [VICIDIAL.md](VICIDIAL.md)

## Useful commands

```bash
cd /opt/aibots
sudo docker compose ps
sudo docker compose logs -f api
sudo docker compose logs -f worker
sudo docker compose restart
sudo docker exec aibots-ollama ollama list
```

## Server sizing

- CPU-only: OK for testing / few calls
- GPU (RTX 4070+): recommended for production concurrency
