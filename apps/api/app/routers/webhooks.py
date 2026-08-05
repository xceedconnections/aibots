import json
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import ActionType, Bot, CallSession, CallStatus
from app.schemas import CallSessionOut, CallStartResponse, CallTurnRequest, DecisionResult, VicidialStartPayload
from app.services.decision_engine import get_start_question, process_turn
from app.services.vicidial import mark_sip_hangup, transfer_to_closer, update_lead_fields

router = APIRouter(tags=["sip-internal"])
settings = get_settings()


async def enqueue_call(session_id: int, payload: dict):
    """
    Queue call for worker.
    - simulate=True  → portal test queue (text dry-run)
    - simulate=False → live SIP: Redis key for AudioSocket (must be ready before AudioSocket connects)
    """
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        is_sim = bool(payload.get("simulate", False))
        job = {
            "call_session_id": session_id,
            **payload,
            "simulate": is_sim,
        }
        uid = (job.get("uniqueid") or job.get("call_id") or job.get("vicidial_call_id") or "").strip()
        await r.set(f"aibots:call:{session_id}:status", "queued")

        if is_sim:
            await r.lpush("aibots:call_queue", json.dumps(job))
            return

        # Live SIP — stash BEFORE dialplan reaches AudioSocket
        if uid:
            raw = json.dumps(job)
            await r.setex(f"aibots:sip:{uid}", 300, raw)
            # Also push queue as safety net (worker will re-stash, not simulate)
            await r.lpush("aibots:call_queue", raw)
            tdid = job.get("transfer_did")
            if tdid:
                await r.setex(f"aibots:sip:{uid}:transfer_did", 600, str(tdid))
        else:
            await r.lpush("aibots:call_queue", json.dumps(job))
    finally:
        await r.aclose()


async def resolve_bot(db: AsyncSession, payload: VicidialStartPayload) -> Bot | None:
    """
    Match bot from SIP headers (vendor way — no Vicidial HTTP webhook):
      1) bot_id
      2) X-VICIdial-Client-Id  (client_id)
      3) X-VICIdial-User-Id    (remote_agent)
      4) campaign_id
      5) any active bot
    """
    if payload.bot_id:
        bot = (
            await db.execute(select(Bot).where(Bot.id == payload.bot_id, Bot.active == True))  # noqa: E712
        ).scalar_one_or_none()
        if bot:
            return bot

    if payload.client_id:
        bot = (
            await db.execute(
                select(Bot)
                .where(Bot.client_id == payload.client_id, Bot.active == True)  # noqa: E712
                .order_by(Bot.id.desc())
            )
        ).scalars().first()
        if bot:
            return bot

    if payload.remote_agent:
        bot = (
            await db.execute(
                select(Bot)
                .where(Bot.remote_agent == payload.remote_agent, Bot.active == True)  # noqa: E712
                .order_by(Bot.id.desc())
            )
        ).scalars().first()
        if bot:
            return bot

    if payload.campaign:
        bot = (
            await db.execute(
                select(Bot)
                .where(Bot.campaign == payload.campaign, Bot.active == True)  # noqa: E712
                .order_by(Bot.id.desc())
            )
        ).scalars().first()
        if bot:
            return bot

    return (
        await db.execute(select(Bot).where(Bot.active == True).order_by(Bot.id.desc()))  # noqa: E712
    ).scalars().first()


def _payload_from_query(q: dict) -> VicidialStartPayload:
    return VicidialStartPayload(
        call_id=q.get("call_id") or q.get("uniqueid"),
        lead_id=q.get("lead_id"),
        phone=q.get("phone") or q.get("phone_number"),
        campaign=q.get("campaign") or q.get("campaign_id"),
        bot_id=int(q["bot_id"]) if q.get("bot_id") else None,
        client_id=q.get("client_id") or q.get("Client-Id") or q.get("X-VICIdial-Client-Id"),
        remote_agent=q.get("remote_agent") or q.get("user_id") or q.get("X-VICIdial-User-Id"),
        uniqueid=q.get("uniqueid") or q.get("call_id"),
        channel=q.get("channel"),
        extra={**q, "simulate": q.get("simulate", "false")},
    )


@router.get("/internal/sip/call-start", response_model=CallStartResponse)
async def sip_call_start_get(request: Request, db: AsyncSession = Depends(get_db)):
    """INTERNAL — AIBOTS Asterisk CURL only. Vicidial never hits this URL."""
    return await sip_call_start(_payload_from_query(dict(request.query_params)), db)


@router.post("/internal/sip/call-start", response_model=CallStartResponse)
async def sip_call_start(payload: VicidialStartPayload, db: AsyncSession = Depends(get_db)):
    """
    Start AI session from SIP INVITE headers.
    Called by AIBOTS Asterisk dialplan (docker network) or portal simulate tests.
    NOT a Vicidial Start Call URL — Vicidial only uses SIP carriers.

    Always creates a CallSession so the portal Lists every SIP hit.
    """
    bot = await resolve_bot(db, payload)
    call_uid = (payload.call_id or payload.uniqueid or "").strip() or None
    extra = payload.extra or {}
    is_sim = str(extra.get("simulate", "")).lower() in ("1", "true", "yes")
    if (payload.phone or "").startswith("555"):
        is_sim = True

    if not bot:
        # Still record the hit — portal must show every call that reached AIBOTS
        session = CallSession(
            bot_id=None,
            vicidial_call_id=call_uid,
            lead_id=payload.lead_id,
            phone=payload.phone,
            campaign=payload.campaign,
            status=CallStatus.FAILED,
            variables={
                "error": "no_active_bot",
                "client_id": payload.client_id,
                "remote_agent": payload.remote_agent,
            },
            transcript=[{"role": "system", "text": "SIP hit but no active bot matched"}],
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return CallStartResponse(
            call_session_id=session.id,
            bot_id=None,
            greeting="",
            first_question=None,
            first_question_id=None,
            status=session.status,
            transfer_did=None,
            client_id=payload.client_id,
            remote_agent=payload.remote_agent,
        )

    start_q = await get_start_question(db, bot.id)

    session = CallSession(
        bot_id=bot.id,
        vicidial_call_id=call_uid,
        lead_id=payload.lead_id,
        phone=payload.phone,
        campaign=payload.campaign or bot.campaign,
        status=CallStatus.STARTED,
        current_question_id=start_q.id if start_q else None,
        variables={
            "client_id": payload.client_id or bot.client_id,
            "remote_agent": payload.remote_agent or bot.remote_agent,
            "transfer_did": bot.transfer_did,
        },
        transcript=[{"role": "bot", "text": bot.greeting}],
        transfer_campaign=bot.transfer_campaign,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    await enqueue_call(
        session.id,
        {
            "channel": payload.channel,
            "phone": payload.phone,
            "campaign": session.campaign,
            "bot_id": bot.id,
            "greeting": bot.greeting,
            "first_question": start_q.prompt if start_q else None,
            "voice": bot.voice,
            "uniqueid": call_uid,
            "call_id": call_uid,
            "vicidial_call_id": call_uid,
            "simulate": is_sim,
            "transfer_campaign": bot.transfer_campaign,
            "transfer_did": bot.transfer_did,
            "client_id": bot.client_id,
            "remote_agent": bot.remote_agent,
            "lead_id": payload.lead_id,
        },
    )

    session.status = CallStatus.IN_PROGRESS
    return CallStartResponse(
        call_session_id=session.id,
        bot_id=bot.id,
        greeting=bot.greeting,
        first_question=start_q.prompt if start_q else None,
        first_question_id=start_q.id if start_q else None,
        status=session.status,
        transfer_did=bot.transfer_did,
        client_id=bot.client_id,
        remote_agent=bot.remote_agent,
    )


@router.get("/internal/sip/{uniqueid}/xfer")
async def sip_xfer_target(uniqueid: str):
    """INTERNAL — plain-text Transfer DID for AIBOTS Asterisk after AudioSocket."""
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        did = await r.get(f"aibots:sip:{uniqueid}:xfer")
        return Response(content=did or "", media_type="text/plain")
    finally:
        await r.aclose()


@router.get("/internal/sip/{uniqueid}/transfer-did")
async def sip_default_transfer_did(uniqueid: str):
    """INTERNAL — fallback Transfer DID."""
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        did = await r.get(f"aibots:sip:{uniqueid}:xfer")
        if not did:
            did = await r.get(f"aibots:sip:{uniqueid}:transfer_did")
        return Response(content=did or "", media_type="text/plain")
    finally:
        await r.aclose()


@router.post("/calls/{session_id}/turn", response_model=DecisionResult)
async def call_turn(
    session_id: int,
    payload: CallTurnRequest,
    db: AsyncSession = Depends(get_db),
):
    """Worker posts customer transcript; returns next bot reply + action."""
    result = await db.execute(
        select(CallSession).where(CallSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Call session not found")

    bot_result = await db.execute(
        select(Bot).options(selectinload(Bot.questions)).where(Bot.id == session.bot_id)
    )
    bot = bot_result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")

    decision = await process_turn(db, session, bot, payload.transcript)

    if decision.action == ActionType.TRANSFER and decision.done:
        transfer_did = decision.transfer_did or bot.transfer_did
        transfer = await transfer_to_closer(
            phone=session.phone,
            lead_id=session.lead_id,
            campaign=session.campaign,
            closer_campaign=decision.transfer_campaign or bot.transfer_campaign,
            call_id=session.vicidial_call_id,
            transfer_did=transfer_did,
        )
        if session.lead_id and session.variables:
            await update_lead_fields(session.lead_id, {"comments": json.dumps(session.variables)[:255]})
        session.status = CallStatus.TRANSFERRED
        session.ended_at = datetime.now(timezone.utc)
        decision.transfer_did = transfer_did
        decision.variables["_transfer"] = transfer

    if decision.action == ActionType.HANGUP and decision.done:
        await mark_sip_hangup(session.vicidial_call_id)
        session.ended_at = datetime.now(timezone.utc)
        if session.status not in (CallStatus.REJECTED, CallStatus.FAILED):
            session.status = CallStatus.COMPLETED

    await db.flush()
    return decision


@router.get("/calls/{session_id}", response_model=CallSessionOut)
async def get_call(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CallSession).where(CallSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Call session not found")
    return session


@router.get("/calls", response_model=list[CallSessionOut])
async def list_calls(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CallSession).order_by(CallSession.id.desc()).limit(min(limit, 200))
    )
    return result.scalars().all()


@router.post("/calls/{session_id}/end", response_model=CallSessionOut)
async def end_call(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CallSession).where(CallSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Call session not found")
    now = datetime.now(timezone.utc)
    session.ended_at = now
    if session.started_at:
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        session.duration_seconds = int((now - started).total_seconds())
    if session.status in (CallStatus.STARTED, CallStatus.IN_PROGRESS):
        session.status = CallStatus.COMPLETED
    await db.flush()
    return session
