"""
AIBOTS call worker — vendor SIP mode + simulate mode.

- SIMULATE_MODE=true: scripted text dry-run (portal test calls)
- SIMULATE_MODE=false: AudioSocket server for live Asterisk SIP calls
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import httpx
import redis.asyncio as redis

from worker.audiosocket import CallAudioBridge, pcm8k_to_wav, read_frame, TYPE_UUID, TYPE_HANGUP
from worker.config import get_settings
from worker.stt import transcribe_file
from worker.tts import synthesize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aibots.worker")
settings = get_settings()

SIMULATE_ANSWERS = [
    "Yes, this is me.",
    "Yes I am between 18 and 64.",
    "No I do not have Medicare.",
    "Yes I am interested.",
]


async def api_post(path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{settings.api_internal_url}{path}", json=payload)
        r.raise_for_status()
        return r.json()


async def speak(text: str, voice: str | None, call_id: int, turn: int) -> str:
    out_dir = Path("/recordings") / str(call_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / f"bot_{turn}.wav")
    path = await asyncio.to_thread(synthesize, text, out_path, voice)
    logger.info("[call %s] BOT: %s", call_id, text)
    return path


async def listen_simulate(call_id: int, turn: int) -> str:
    idx = turn
    text = SIMULATE_ANSWERS[idx] if idx < len(SIMULATE_ANSWERS) else "yes"
    logger.info("[call %s] CUSTOMER (sim): %s", call_id, text)
    await asyncio.sleep(0.4)
    return text


async def handle_call_simulate(job: dict):
    call_id = job["call_session_id"]
    voice = job.get("voice")
    greeting = job.get("greeting") or "Hello."
    first_q = job.get("first_question")
    turn = 0
    await speak(greeting, voice, call_id, turn)
    turn += 1
    if first_q:
        await speak(first_q, voice, call_id, turn)
        turn += 1

    customer_turn = 0
    while customer_turn < 20:
        transcript = await listen_simulate(call_id, customer_turn)
        customer_turn += 1
        decision = await api_post(
            f"/calls/{call_id}/turn",
            {"call_session_id": call_id, "transcript": transcript},
        )
        reply = decision.get("reply_text") or ""
        if reply:
            await speak(reply, voice, call_id, turn)
            turn += 1
        if decision.get("done") or decision.get("action") in ("transfer", "hangup"):
            break
    await api_post(f"/calls/{call_id}/end", {})


async def run_live_session(bridge: CallAudioBridge, session: dict, voice: str | None):
    call_id = session["call_session_id"]
    turn = 0

    async def say(text: str):
        nonlocal turn
        wav = await speak(text, voice, call_id, turn)
        turn += 1
        await bridge.play_wav(wav)

    await say(session.get("greeting") or "Hello.")
    if session.get("first_question"):
        await say(session["first_question"])

    for _ in range(20):
        pcm = await bridge.listen()
        if not pcm:
            transcript = ""
        else:
            wav_path = tempfile.mktemp(suffix=".wav")
            pcm8k_to_wav(pcm, wav_path)
            transcript = await asyncio.to_thread(transcribe_file, wav_path)
            Path(wav_path).unlink(missing_ok=True)
        logger.info("[call %s] CUSTOMER: %s", call_id, transcript)

        decision = await api_post(
            f"/calls/{call_id}/turn",
            {"call_session_id": call_id, "transcript": transcript or ""},
        )
        reply = decision.get("reply_text") or ""
        if reply:
            await say(reply)

        action = decision.get("action")
        if decision.get("done") or action in ("transfer", "hangup"):
            if action == "transfer":
                # Signal Asterisk via Redis for AMI redirect (optional)
                r = redis.from_url(settings.redis_url, decode_responses=True)
                await r.publish(
                    "aibots:transfer",
                    json.dumps(
                        {
                            "call_session_id": call_id,
                            "channel": session.get("channel"),
                            "closer": decision.get("transfer_campaign"),
                        }
                    ),
                )
                await r.aclose()
            break

    await api_post(f"/calls/{call_id}/end", {})


async def audiosocket_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    logger.info("AudioSocket connection from %s", peer)
    bridge = CallAudioBridge(reader, writer)
    unique = ""

    # Read first frames for UUID / bind to queued session
    try:
        for _ in range(5):
            frame = await asyncio.wait_for(read_frame(reader), timeout=5)
            if not frame:
                break
            ftype, payload = frame
            if ftype == TYPE_UUID:
                unique = payload.decode("utf-8", errors="ignore")
                bridge.uuid = unique
                break
            if ftype == TYPE_HANGUP:
                writer.close()
                return
    except Exception as exc:
        logger.warning("AudioSocket handshake: %s", exc)

    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        # Sessions keyed by Asterisk UNIQUEID after webhook start
        raw = None
        if unique:
            raw = await r.get(f"aibots:sip:{unique}")
        if not raw:
            # fallback: latest queued job
            item = await r.lpop("aibots:call_queue")
            raw = item
        if not raw:
            logger.error("No call session for AudioSocket uuid=%s", unique)
            writer.close()
            return

        job = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(job, str):
            job = json.loads(job)

        # Ensure we have greeting fields
        if "greeting" not in job and job.get("call_session_id"):
            sess = await api_get_session(job["call_session_id"])
            job.update(sess)

        await run_live_session(bridge, job, job.get("voice"))
    except Exception:
        logger.exception("Live call failed")
    finally:
        await r.aclose()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def api_get_session(call_id: int) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        # minimal — greeting already in queue job usually
        return {"call_session_id": call_id}


async def queue_loop():
    r = redis.from_url(settings.redis_url, decode_responses=True)
    while True:
        try:
            item = await r.brpop("aibots:call_queue", timeout=2)
            if not item:
                continue
            _, raw = item
            job = json.loads(raw)
            # Simulate jobs (portal test) always handled here
            if settings.simulate_mode or job.get("simulate", True):
                asyncio.create_task(handle_call_simulate(job))
            else:
                # Live SIP: stash by uniqueid for AudioSocket pickup
                uid = job.get("vicidial_call_id") or job.get("uniqueid") or ""
                if uid:
                    await r.setex(f"aibots:sip:{uid}", 120, json.dumps(job))
                else:
                    await r.lpush("aibots:call_queue_live", json.dumps(job))
        except Exception as exc:
            logger.error("Queue error: %s", exc)
            await asyncio.sleep(1)


async def main_async():
    sim = os.getenv("SIMULATE_MODE", "true").lower()
    if sim in ("0", "false", "no"):
        settings.simulate_mode = False

    logger.info("Worker starting simulate_mode=%s", settings.simulate_mode)

    # Wait for API
    for _ in range(60):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                if (await client.get(f"{settings.api_internal_url}/health")).status_code == 200:
                    break
        except Exception:
            pass
        await asyncio.sleep(2)

    tasks = [asyncio.create_task(queue_loop())]
    # Always listen for SIP AudioSocket (vendor mode)
    server = await asyncio.start_server(audiosocket_handler, "0.0.0.0", 9092)
    logger.info("AudioSocket listening on 0.0.0.0:9092")
    tasks.append(asyncio.create_task(server.serve_forever()))
    await asyncio.gather(*tasks)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
