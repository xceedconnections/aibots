import json
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import ActionType, Bot, CallSession, CallStatus
from app.schemas import CallSessionOut, CallStartResponse, CallTurnRequest, DecisionResult, VicidialStartPayload
from app.services.decision_engine import get_start_question, process_turn
from app.services.vicidial import transfer_to_closer, update_lead_fields

router = APIRouter(tags=["webhooks"])
settings = get_settings()


async def enqueue_call(session_id: int, payload: dict):
    """Push new call job to Redis for the AI worker / AudioSocket."""
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        job = {
            "call_session_id": session_id,
            **payload,
            "simulate": payload.get("simulate", True),
        }
        uid = job.get("uniqueid") or job.get("call_id") or job.get("vicidial_call_id")
        await r.lpush("aibots:call_queue", json.dumps(job))
        await r.set(f"aibots:call:{session_id}:status", "queued")
        if uid and not job.get("simulate", True):
            await r.setex(f"aibots:sip:{uid}", 180, json.dumps(job))
    finally:
        await r.aclose()


@router.get("/webhook/vicidial/start", response_model=CallStartResponse)
async def vicidial_start_get(request: Request, db: AsyncSession = Depends(get_db)):
    """Asterisk dialplan CURL uses GET with query params."""
    q = dict(request.query_params)
    payload = VicidialStartPayload(
        call_id=q.get("call_id") or q.get("uniqueid"),
        lead_id=q.get("lead_id"),
        phone=q.get("phone") or q.get("phone_number"),
        campaign=q.get("campaign") or q.get("campaign_id"),
        bot_id=int(q["bot_id"]) if q.get("bot_id") else None,
        uniqueid=q.get("uniqueid") or q.get("call_id"),
        channel=q.get("channel"),
        extra={**q, "simulate": q.get("simulate", "false")},
    )
    return await vicidial_start(payload, db)


@router.post("/webhook/vicidial/start", response_model=CallStartResponse)
async def vicidial_start(payload: VicidialStartPayload, db: AsyncSession = Depends(get_db)):
    """
    Start AI session — used by:
      - Portal test calls
      - Asterisk dialplan CURL (SIP carrier mode)
      - Optional VICIdial Start URL (legacy)
    """
    bot: Bot | None = None
    if payload.bot_id:
        bot = (await db.execute(select(Bot).where(Bot.id == payload.bot_id, Bot.active == True))).scalar_one_or_none()  # noqa: E712
    if not bot and payload.campaign:
        bot = (
            await db.execute(
                select(Bot).where(Bot.campaign == payload.campaign, Bot.active == True).order_by(Bot.id.desc())  # noqa: E712
            )
        ).scalars().first()
    if not bot:
        bot = (
            await db.execute(select(Bot).where(Bot.active == True).order_by(Bot.id.desc()))  # noqa: E712
        ).scalars().first()
    if not bot:
        raise HTTPException(404, "No active bot found for this campaign")

    start_q = await get_start_question(db, bot.id)
    call_uid = payload.call_id or payload.uniqueid

    session = CallSession(
        bot_id=bot.id,
        vicidial_call_id=call_uid,
        lead_id=payload.lead_id,
        phone=payload.phone,
        campaign=payload.campaign or bot.campaign,
        status=CallStatus.STARTED,
        current_question_id=start_q.id if start_q else None,
        variables={},
        transcript=[{"role": "bot", "text": bot.greeting}],
        transfer_campaign=bot.transfer_campaign,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # SIP carrier = live; portal test uses phone 555* or extra.simulate=true
    extra = payload.extra or {}
    is_sim = str(extra.get("simulate", "")).lower() in ("1", "true", "yes")
    if (payload.phone or "").startswith("555"):
        is_sim = True

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
    )


@router.post("/webhook/vicidial/start/form", response_model=CallStartResponse)
async def vicidial_start_form(request: Request, db: AsyncSession = Depends(get_db)):
    """Accept application/x-www-form-urlencoded from VICIdial URL posts."""
    form = await request.form()
    data = {k: str(v) for k, v in form.items()}
    query = dict(request.query_params)
    merged = {**query, **data}
    payload = VicidialStartPayload(
        call_id=merged.get("call_id") or merged.get("uniqueid"),
        lead_id=merged.get("lead_id"),
        phone=merged.get("phone_number") or merged.get("phone"),
        campaign=merged.get("campaign") or merged.get("campaign_id"),
        bot_id=int(merged["bot_id"]) if merged.get("bot_id") else None,
        uniqueid=merged.get("uniqueid"),
        channel=merged.get("channel"),
        extra=merged,
    )
    return await vicidial_start(payload, db)


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
        transfer = await transfer_to_closer(
            phone=session.phone,
            lead_id=session.lead_id,
            campaign=session.campaign,
            closer_campaign=decision.transfer_campaign or bot.transfer_campaign,
            call_id=session.vicidial_call_id,
        )
        if session.lead_id and session.variables:
            flat = {f"vendor_lead_code": json.dumps(session.variables)}
            # Best-effort field push
            await update_lead_fields(session.lead_id, {"comments": json.dumps(session.variables)[:255]})
        session.status = CallStatus.TRANSFERRED
        session.ended_at = datetime.now(timezone.utc)
        decision.variables["_transfer"] = transfer

    if decision.action == ActionType.HANGUP and decision.done:
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
