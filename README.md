# AIBOTS — Self-hosted VICIdial AI Voice Platform

Fully self-hosted AI voice agents for VICIdial — **same carrier pattern as commercial AI bots**:

- Portal to create bots, scripts, Q&A, transfer rules
- Local LLM (Ollama / Qwen) — **no OpenAI**
- Faster-Whisper STT + Piper TTS
- VICIdial integration via **SIP carriers only** (no Vicidial scripts)
- Transfer qualified callers to closers via **virtual DID**

**Repo:** [github.com/xceedconnections/aibots](https://github.com/xceedconnections/aibots)

## Integration mode (vendor-style)

On VICIdial you only configure:

1. **AI carrier** — dialplan with `X-VICIdial-*` headers → `Dial(SIP/aibots@AIBOTS_IP)`
2. **Remote agents** (e.g. 27001)
3. **Virtual DIDs** → closer in-groups (e.g. 106027001)
4. Optional **Ctransfer** carrier for Vicidial-side transfer prefixes

No Start Call URL. No custom AGI. No `manager.conf` edits.

See **[docs/SIP-CARRIER.md](docs/SIP-CARRIER.md)** and portal page **SIP Carrier**.

## One-line install (Ubuntu / Debian)

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
```

Full guide: **[INSTALL.md](INSTALL.md)** · VICIdial: **[docs/VICIDIAL.md](docs/VICIDIAL.md)** · Carrier: **[docs/SIP-CARRIER.md](docs/SIP-CARRIER.md)**

After install open `http://SERVER_IP:3000`  
Login is printed by the installer (also `/opt/aibots/INSTALL-INFO.txt`).

### Portal (CRM-style, like AI AMD)

- **Dashboard** — live stats  
- **Campaigns** — AI campaigns + dialplan copy  
- **Bots / Scripts** — qualification scripts  
- **VICIdial Servers** — register dialers  
- **SIP Carrier** — Vicidial carrier paste pack  
- **Settings** — PUBLIC_IP, SIP password, defaults  
- **Calls** — session history  

## Architecture

```
VICIdial campaign (AI carrier)
      │  SIP + X-VICIdial-* headers
      ▼
AIBOTS Asterisk ──AudioSocket──► AI Worker (Whisper / Qwen / Piper)
      │
      ▼ (qualified)
Dial virtual DID ──► VICIdial inbound DID ──► closer agents
```

## Requirements (Ubuntu AI server)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| OS | Ubuntu 22.04 / 24.04 | 24.04 |
| CPU | 8 cores | 16–32 cores |
| RAM | 16 GB | 32–64 GB |
| Disk | 80 GB SSD | 200 GB+ |
| GPU | optional | RTX 4070+ / L4 |

VICIdial stays on its own server. This stack is the AI box.

## Quick install (already cloned)

```bash
cd aibots
sudo bash scripts/install-ubuntu.sh
```

### Access

| Service | URL |
|---------|-----|
| Portal | `http://SERVER_IP:3000` |
| API docs | `http://SERVER_IP:8000/docs` |
| Nginx | `http://SERVER_IP/` |

## Manual start

```bash
cp .env.example .env
# set PUBLIC_IP, AIBOTS_SIP_PASSWORD, ASTERISK_AMI_HOST=VICIdial IP

docker compose up -d --build
docker exec aibots-ollama ollama pull qwen2.5:7b-instruct
bash scripts/download-models.sh
```

## Portal workflow

1. Sign in
2. Open **SIP Carrier** — copy Vicidial dialplan / peer settings
3. Open **Bots** — set **Client ID**, **Remote Agent**, **Transfer DID**
4. Edit questions / answers (`continue`, `transfer`, `hangup`)
5. **Run test call** (simulate) or dial live through the Vicidial carrier

## Stack

| Component | Tech |
|-----------|------|
| API | FastAPI + SQLAlchemy |
| DB | PostgreSQL + Redis |
| Portal | React (Vite) |
| LLM | Ollama · Qwen2.5 7B Instruct |
| STT | Faster-Whisper |
| TTS | Piper |
| Telephony | Asterisk PJSIP + AudioSocket (SIP carrier) |

## Project layout

```
AIBOTS/
├── install.sh
├── apps/api
├── apps/worker
├── apps/portal
├── docker/asterisk
├── scripts/
└── docs/
```

## Simulate vs live audio

`SIMULATE_MODE=true` keeps portal test calls working. Live SIP INVITEs set `simulate=false` automatically.

## GPU (optional)

In `docker-compose.yml`, uncomment the `ollama` GPU deploy section and install [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-container-toolkit).

Also set:

```
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

## License

Internal / self-hosted use. Models (Qwen, Whisper, Piper) follow their upstream licenses.
