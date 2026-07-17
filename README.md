# AIBOTS — Self-hosted VICIdial AI Voice Platform

Fully self-hosted AI voice agents for VICIdial:

- Portal to create bots, scripts, Q&A, transfer rules
- Local LLM (Ollama / Qwen) — **no OpenAI**
- Faster-Whisper STT + Piper TTS
- Webhook integration with VICIdial
- Transfer qualified callers to closer campaigns

**Repo:** [github.com/xceedconnections/aibots](https://github.com/xceedconnections/aibots)

## Integration mode (vendor-style)

Primary integration is **SIP Carrier** (same pattern as commercial AI bots):

- VICIdial → Carriers → point at AIBOTS SIP
- No Start Call URL required
- See **[docs/SIP-CARRIER.md](docs/SIP-CARRIER.md)** and portal page **SIP Carrier**

## One-line install (Ubuntu)

```bash
curl -fsSL https://raw.githubusercontent.com/xceedconnections/aibots/main/install.sh | sudo bash
```

Full guide: **[INSTALL.md](INSTALL.md)** · VICIdial setup: **[docs/VICIDIAL.md](docs/VICIDIAL.md)** · Deploy notes: **[docs/DEPLOY-UBUNTU.md](docs/DEPLOY-UBUNTU.md)**

After install open `http://SERVER_IP:3000`  
Login: `xceedconnections@gmail.com` / `Openaccount@123`

## Architecture

```
VICIdial ──webhook──► FastAPI API ──queue──► AI Worker
                           │                    │
                      PostgreSQL          Whisper / Piper / Ollama
                      Redis                   │
                           │                  ▼
                        Portal ◄──────── Decision Engine
                                              │
                                              ▼
                                    VICIdial API / AMI Transfer
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
# edit YOUR_SERVER_IP, secrets, VICIdial settings

docker compose up -d --build
docker exec aibots-ollama ollama pull qwen2.5:7b-instruct
bash scripts/download-models.sh
bash scripts/test-call.sh
docker logs -f aibots-worker
```

## Portal workflow

1. Sign in
2. Open **Bots** — sample **ACA Qualifier** is seeded
3. Edit questions / answers / actions (`continue`, `transfer`, `hangup`)
4. Set **campaign** + **transfer campaign** to match VICIdial
5. Click **Run test call** (simulate mode walks the script)
6. Watch **Calls** + worker logs

## VICIdial

See [docs/VICIDIAL.md](docs/VICIDIAL.md).

Webhook:

```
http://AIBOTS_IP/webhook/vicidial/start?campaign=ACA2026&bot_id=1
```

## Stack

| Component | Tech |
|-----------|------|
| API | FastAPI + SQLAlchemy |
| DB | PostgreSQL + Redis |
| Portal | React (Vite) |
| LLM | Ollama · Qwen2.5 7B Instruct |
| STT | Faster-Whisper |
| TTS | Piper |
| Telephony | VICIdial Agent API + Asterisk AMI |

## Project layout

```
AIBOTS/
├── install.sh        # curl | bash entrypoint
├── apps/api          # FastAPI control plane
├── apps/worker       # Per-call STT→NLU→TTS worker
├── apps/portal       # Admin UI
├── docker/nginx
├── scripts/          # Ubuntu install + helpers
└── docs/
```

## Simulate vs live audio

Default: `SIMULATE_MODE=true` on the worker — validates scripts and transfer without RTP.

When Asterisk media bridge is ready, set `SIMULATE_MODE=false` and publish customer audio paths to Redis list `aibots:call:{id}:audio`.

## GPU (optional)

In `docker-compose.yml`, uncomment the `ollama` GPU deploy section and install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

Also set in `.env`:

```
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

## License

Internal / self-hosted use. Models (Qwen, Whisper, Piper) follow their upstream licenses.
