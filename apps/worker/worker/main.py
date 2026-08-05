"""
AIBOTS call worker — vendor SIP mode + simulate mode.

- Portal test jobs: simulate=true → scripted dry-run (no phone audio)
- Live SIP jobs: simulate=false → AudioSocket only (never use global SIMULATE_MODE for phone)
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

from worker.audiosocket import (
    CallAudioBridge,
    decode_uuid_payload,
    pcm8k_to_wav,
    read_frame,
    TYPE_HANGUP,
    TYPE_UUID,
)
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


async def _with_keepalive(bridge: CallAudioBridge, coro):
    """Run blocking work while sending silence so Asterisk AudioSocket idle timeout (~2s) does not fire."""
    task = asyncio.create_task(coro)
    try:
        while not task.done():
            await bridge.keepalive(200)
            await asyncio.sleep(0.05)
        return await task
    except Exception:
        task.cancel()
        raise


async def run_live_session(bridge: CallAudioBridge, session: dict, voice: str | None):
    call_id = session["call_session_id"]
    turn = 0

    async def say(text: str):
        nonlocal turn
        wav = await _with_keepalive(
            bridge, speak(text, voice, call_id, turn)
        )
        turn += 1
        await bridge.play_wav(wav)

    greeting = session.get("greeting") or "Hello, thank you for taking our call."
    await say(greeting)
    if session.get("first_question"):
        await say(session["first_question"])

    for _ in range(20):
        pcm = await bridge.listen()
        if not pcm:
            transcript = ""
        else:
            wav_path = tempfile.mktemp(suffix=".wav")
            pcm8k_to_wav(pcm, wav_path)

            async def _stt():
                return await asyncio.to_thread(transcribe_file, wav_path)

            transcript = await _with_keepalive(bridge, _stt())
            Path(wav_path).unlink(missing_ok=True)
        logger.info("[call %s] CUSTOMER: %s", call_id, transcript)

        decision = await _with_keepalive(
            bridge,
            api_post(
                f"/calls/{call_id}/turn",
                {"call_session_id": call_id, "transcript": transcript or ""},
            ),
        )
        reply = decision.get("reply_text") or ""
        if reply:
            await say(reply)

        action = decision.get("action")
        if decision.get("done") or action in ("transfer", "hangup"):
            if action == "transfer":
                r = redis.from_url(settings.redis_url, decode_responses=True)
                try:
                    uid = session.get("uniqueid") or session.get("vicidial_call_id") or ""
                    did = decision.get("transfer_did") or session.get("transfer_did") or ""
                    if uid and did:
                        await r.setex(f"aibots:sip:{uid}:xfer", 300, did)
                        await r.publish(
                            "aibots:transfer",
                            json.dumps(
                                {
                                    "call_session_id": call_id,
                                    "channel": session.get("channel"),
                                    "transfer_did": did,
                                    "closer": decision.get("transfer_campaign"),
                                }
                            ),
                        )
                finally:
                    await r.aclose()
            break

    await api_post(f"/calls/{call_id}/end", {})


async def _load_live_job(r, unique: str) -> dict | None:
    """Wait briefly for API enqueue (CURL → Redis) then load job."""
    if not unique:
        return None
    keys = [f"aibots:sip:{unique}", f"aibots:sip:{unique.lower()}"]
    for _ in range(30):  # ~6s
        for key in keys:
            raw = await r.get(key)
            if raw:
                job = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(job, str):
                    job = json.loads(job)
                return job
        await asyncio.sleep(0.2)
    return None


async def audiosocket_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    logger.info("AudioSocket connection from %s", peer)
    bridge = CallAudioBridge(reader, writer)
    unique = ""

    try:
        for _ in range(5):
            frame = await asyncio.wait_for(read_frame(reader), timeout=5)
            if not frame:
                break
            ftype, payload = frame
            if ftype == TYPE_UUID:
                unique = decode_uuid_payload(payload)
                bridge.uuid = unique
                logger.info("AudioSocket UUID=%s (payload_len=%s)", unique, len(payload))
                break
            if ftype == TYPE_HANGUP:
                writer.close()
                return
    except Exception as exc:
        logger.warning("AudioSocket handshake: %s", exc)

    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        job = await _load_live_job(r, unique)
        if not job:
            logger.error("No call session for AudioSocket uuid=%s — check CURL call-start", unique)
            # Play a short tone of silence then close (avoid abrupt)
            try:
                await bridge.keepalive(400)
            except Exception:
                pass
            writer.close()
            return

        job["simulate"] = False
        if "uniqueid" not in job:
            job["uniqueid"] = unique
        logger.info(
            "Live call session=%s phone=%s campaign=%s uuid=%s",
            job.get("call_session_id"),
            job.get("phone"),
            job.get("campaign"),
            unique,
        )
        await run_live_session(bridge, job, job.get("voice"))
    except Exception:
        logger.exception("Live call failed uuid=%s", unique)
    finally:
        await r.aclose()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def queue_loop():
    """Only portal simulate jobs. Live SIP jobs are picked up via AudioSocket + Redis key."""
    r = redis.from_url(settings.redis_url, decode_responses=True)
    while True:
        try:
            item = await r.brpop("aibots:call_queue", timeout=2)
            if not item:
                continue
            _, raw = item
            job = json.loads(raw)
            if job.get("simulate") is True or str(job.get("simulate", "")).lower() in ("1", "true", "yes"):
                logger.info("Simulate job session=%s", job.get("call_session_id"))
                asyncio.create_task(handle_call_simulate(job))
            else:
                uid = job.get("vicidial_call_id") or job.get("uniqueid") or ""
                if uid:
                    await r.setex(f"aibots:sip:{uid}", 300, json.dumps(job))
                    logger.info("Stashed live SIP job uuid=%s session=%s", uid, job.get("call_session_id"))
                else:
                    logger.warning("Live job without uniqueid: %s", job)
        except Exception as exc:
            logger.error("Queue error: %s", exc)
            await asyncio.sleep(1)


async def main_async():
    sim = os.getenv("SIMULATE_MODE", "false").lower()
    settings.simulate_mode = sim in ("1", "true", "yes")

    logger.info(
        "Worker starting (portal simulate flag=%s; live SIP always uses AudioSocket)",
        settings.simulate_mode,
    )

    for _ in range(60):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                if (await client.get(f"{settings.api_internal_url}/health")).status_code == 200:
                    break
        except Exception:
            pass
        await asyncio.sleep(2)

    tasks = [asyncio.create_task(queue_loop())]
    server = await asyncio.start_server(audiosocket_handler, "0.0.0.0", 9092)
    logger.info("AudioSocket listening on 0.0.0.0:9092")
    tasks.append(asyncio.create_task(server.serve_forever()))
    await asyncio.gather(*tasks)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
