"""
AI call worker.

Pulls jobs from Redis queue `aibots:call_queue` and runs the conversation loop:
  speak greeting → speak question → (listen/STT) → POST /calls/{id}/turn → speak reply → ...

While Asterisk RTP bridge is not yet connected, SIMULATE_MODE=true runs a
text-driven dry-run using sample answers so you can validate the full stack.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx
import redis.asyncio as redis

from worker.config import get_settings
from worker.stt import transcribe_file
from worker.tts import synthesize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aibots.worker")
settings = get_settings()

# Demo answers used only in simulate mode (scripted ACA sample bot)
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


async def api_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{settings.api_internal_url}{path}")
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
    """Return next scripted customer answer for dry-run testing."""
    idx = turn
    if idx >= len(SIMULATE_ANSWERS):
        return "yes"
    text = SIMULATE_ANSWERS[idx]
    logger.info("[call %s] CUSTOMER (sim): %s", call_id, text)
    await asyncio.sleep(0.5)
    return text


async def listen_from_file(audio_path: str) -> str:
    return await asyncio.to_thread(transcribe_file, audio_path)


async def handle_call(job: dict):
    call_id = job["call_session_id"]
    voice = job.get("voice")
    greeting = job.get("greeting") or "Hello."
    first_q = job.get("first_question")

    logger.info("=== Starting call session %s ===", call_id)
    r = redis.from_url(settings.redis_url, decode_responses=True)
    await r.set(f"aibots:call:{call_id}:status", "active")

    turn = 0
    try:
        await speak(greeting, voice, call_id, turn)
        turn += 1
        if first_q:
            await speak(first_q, voice, call_id, turn)
            turn += 1

        customer_turn = 0
        while True:
            if settings.simulate_mode:
                transcript = await listen_simulate(call_id, customer_turn)
            else:
                # Production: worker waits for audio chunk path published by RTP bridge
                audio_key = f"aibots:call:{call_id}:audio"
                audio_path = await r.blpop(audio_key, timeout=60)
                if not audio_path:
                    logger.warning("[call %s] listen timeout", call_id)
                    transcript = ""
                else:
                    transcript = await listen_from_file(audio_path[1])

            customer_turn += 1
            decision = await api_post(
                f"/calls/{call_id}/turn",
                {"call_session_id": call_id, "transcript": transcript},
            )

            reply = decision.get("reply_text") or ""
            if reply:
                await speak(reply, voice, call_id, turn)
                turn += 1

            action = decision.get("action")
            done = decision.get("done", False)
            logger.info(
                "[call %s] action=%s intent=%s confidence=%s done=%s",
                call_id,
                action,
                decision.get("intent"),
                decision.get("confidence"),
                done,
            )

            if done or action in ("transfer", "hangup"):
                break

            if customer_turn > 20:
                logger.warning("[call %s] max turns reached", call_id)
                break

        await api_post(f"/calls/{call_id}/end", {})
        await r.set(f"aibots:call:{call_id}:status", "done")
        logger.info("=== Finished call session %s ===", call_id)
    except Exception as exc:
        logger.exception("Call %s failed: %s", call_id, exc)
        await r.set(f"aibots:call:{call_id}:status", f"error:{exc}")
    finally:
        await r.aclose()


async def worker_loop():
    logger.info(
        "AIBOTS worker starting (simulate_mode=%s, redis=%s)",
        settings.simulate_mode,
        settings.redis_url,
    )
    # Wait for API health
    for i in range(60):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{settings.api_internal_url}/health")
                if r.status_code == 200:
                    logger.info("API is healthy")
                    break
        except Exception:
            pass
        await asyncio.sleep(2)
    else:
        logger.error("API not reachable — continuing anyway")

    sem = asyncio.Semaphore(settings.max_concurrent_calls)
    r = redis.from_url(settings.redis_url, decode_responses=True)

    async def run_job(raw: str):
        async with sem:
            job = json.loads(raw)
            await handle_call(job)

    while True:
        try:
            item = await r.brpop("aibots:call_queue", timeout=5)
            if not item:
                continue
            _, raw = item
            asyncio.create_task(run_job(raw))
        except Exception as exc:
            logger.error("Queue loop error: %s", exc)
            await asyncio.sleep(2)


def main():
    sim = os.getenv("SIMULATE_MODE", "true").lower()
    if sim in ("0", "false", "no"):
        settings.simulate_mode = False
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
