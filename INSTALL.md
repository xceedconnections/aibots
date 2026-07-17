# Installation Guide

Self-hosted VICIdial AI Voice Bot platform — **no paid AI APIs**.

## One-line install (recommended)

On a **fresh Ubuntu 22.04 or 24.04** server:

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
```

This will:

1. Install Docker + dependencies  
2. Clone [xceedconnections/aibots](https://github.com/xceedconnections/aibots)  
3. Deploy to `/opt/aibots`  
4. Start Postgres, Redis, Ollama, API, Worker, Portal, Nginx  
5. Pull `qwen2.5:7b-instruct`  
6. Download Piper TTS voice  

**First run: 15–40 minutes** (images + ~4GB model).

### Optional overrides

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | \
  sudo APP_DIR=/opt/aibots BRANCH=main bash
```

## After install

| Service | URL |
|---------|-----|
| Portal | `http://SERVER_IP:3000` |
| API | `http://SERVER_IP:8000` |
| API docs | `http://SERVER_IP:8000/docs` |
| Nginx | `http://SERVER_IP/` |

**Login:** `xceedconnections@gmail.com` / `Openaccount@123`

### Configure

```bash
sudo nano /opt/aibots/.env
```

Set:

- `VITE_API_URL=http://YOUR_SERVER_IP:8000`
- `VICIDIAL_URL`, `VICIDIAL_USER`, `VICIDIAL_PASS`
- `ASTERISK_AMI_*`
- `ADMIN_PASSWORD` (change default)

Rebuild portal if you changed `VITE_API_URL`:

```bash
cd /opt/aibots
sudo docker compose up -d --build portal
```

### Test call (no VICIdial yet)

```bash
cd /opt/aibots
sudo bash scripts/test-call.sh
sudo docker logs -f aibots-worker
```

## Manual install (clone first)

```bash
git clone https://github.com/xceedconnections/aibots.git
cd aibots
sudo bash scripts/install-ubuntu.sh
```

Or:

```bash
git clone https://github.com/xceedconnections/aibots.git /opt/aibots-src
cd /opt/aibots-src
cp .env.example .env
# edit .env
sudo docker compose up -d --build
sudo docker exec aibots-ollama ollama pull qwen2.5:7b-instruct
sudo bash scripts/download-models.sh
```

## Server requirements

| | Minimum | Recommended |
|--|---------|-------------|
| OS | Ubuntu 22.04+ | 24.04 |
| CPU | 8 cores | 16–32 |
| RAM | 16 GB | 32–64 GB |
| Disk | 80 GB SSD | 200 GB+ |
| GPU | optional | RTX 4070+ / L4 |

## VICIdial webhook

```
http://AIBOTS_IP/webhook/vicidial/start?campaign=ACA2026&bot_id=1
```

Full guide: [docs/VICIDIAL.md](docs/VICIDIAL.md)

## Useful commands

```bash
cd /opt/aibots
sudo docker compose ps
sudo docker compose logs -f
sudo docker compose restart
sudo docker exec aibots-ollama ollama list
```

## Uninstall

```bash
cd /opt/aibots
sudo docker compose down -v
sudo rm -rf /opt/aibots /opt/aibots-src
```
