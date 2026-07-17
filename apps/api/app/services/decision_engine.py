"""
Deterministic conversation decision engine.

Flow control lives here. The LLM is only used as a fallback NLU
when keyword matching is inconclusive.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import ActionType, Answer, Bot, CallSession, CallStatus, Question
from app.schemas import DecisionResult

settings = get_settings()


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def keyword_match(transcript: str, keywords: list[str]) -> float:
    """Return confidence 0-1 based on keyword hits."""
    if not keywords:
        return 0.0
    norm = normalize_text(transcript)
    tokens = set(norm.split())
    hits = 0
    for kw in keywords:
        k = normalize_text(kw)
        if not k:
            continue
        if " " in k:
            if k in norm:
                hits += 1
        elif k in tokens:
            hits += 1
    if hits == 0:
        return 0.0
    return min(1.0, 0.55 + (hits * 0.2))


async def llm_classify_intent(
    transcript: str,
    intents: list[str],
    question_prompt: str,
    model: str,
    temperature: float,
) -> tuple[Optional[str], float]:
    """Ask local Ollama to pick an intent. Returns (intent, confidence)."""
    if not intents:
        return None, 0.0

    system = (
        "You are an intent classifier for a call-center script. "
        "Reply with ONLY the intent label from the list, nothing else. "
        "If unsure, reply UNKNOWN."
    )
    user = (
        f"Question asked: {question_prompt}\n"
        f"Customer said: {transcript}\n"
        f"Possible intents: {', '.join(intents)}\n"
        f"Intent:"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": f"{system}\n\n{user}",
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": 16},
                },
            )
            if resp.status_code != 200:
                return None, 0.0
            raw = (resp.json().get("response") or "").strip().upper()
            for intent in intents:
                if intent.upper() in raw or raw in intent.upper():
                    return intent, 0.75
            if "UNKNOWN" in raw:
                return None, 0.0
            return None, 0.0
    except Exception:
        return None, 0.0


async def load_question(db: AsyncSession, question_id: int) -> Optional[Question]:
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.answers))
        .where(Question.id == question_id)
    )
    return result.scalar_one_or_none()


async def get_start_question(db: AsyncSession, bot_id: int) -> Optional[Question]:
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.answers))
        .where(Question.bot_id == bot_id)
        .order_by(Question.is_start.desc(), Question.sort_order.asc())
    )
    questions = result.scalars().all()
    if not questions:
        return None
    for q in questions:
        if q.is_start:
            return q
    return questions[0]


def pick_best_answer(transcript: str, answers: list[Answer]) -> tuple[Optional[Answer], float]:
    best: Optional[Answer] = None
    best_score = 0.0
    sorted_answers = sorted(answers, key=lambda a: a.priority, reverse=True)
    for ans in sorted_answers:
        score = keyword_match(transcript, ans.keywords or [])
        if score > best_score:
            best_score = score
            best = ans
    return best, best_score


async def process_turn(
    db: AsyncSession,
    session: CallSession,
    bot: Bot,
    transcript: str,
) -> DecisionResult:
    transcript = (transcript or "").strip()
    variables = dict(session.variables or {})
    history = list(session.transcript or [])
    history.append({"role": "user", "text": transcript})

    if not session.current_question_id:
        # No more questions — transfer if we have transfer campaign
        reply = "Thank you. Please hold while I connect you with a specialist."
        history.append({"role": "bot", "text": reply})
        session.transcript = history
        session.status = CallStatus.QUALIFIED
        return DecisionResult(
            action=ActionType.TRANSFER,
            reply_text=reply,
            variables=variables,
            transfer_campaign=bot.transfer_campaign,
            done=True,
            confidence=1.0,
        )

    question = await load_question(db, session.current_question_id)
    if not question:
        reply = "I'm sorry, something went wrong. Goodbye."
        session.status = CallStatus.FAILED
        return DecisionResult(action=ActionType.HANGUP, reply_text=reply, done=True)

    answers = list(question.answers or [])
    matched, confidence = pick_best_answer(transcript, answers)

    # LLM fallback when keyword confidence is low
    if (matched is None or confidence < 0.55) and answers:
        intents = [a.intent for a in answers]
        llm_intent, llm_conf = await llm_classify_intent(
            transcript,
            intents,
            question.prompt,
            bot.model or settings.llm_model,
            bot.temperature if bot.temperature is not None else settings.llm_temperature,
        )
        if llm_intent:
            for a in answers:
                if a.intent.lower() == llm_intent.lower():
                    matched = a
                    confidence = llm_conf
                    break

    # Still unclear — ask again
    if matched is None or confidence < 0.45:
        session.retry_count = (session.retry_count or 0) + 1
        max_retries = question.max_retries or settings.max_question_retries
        if session.retry_count > max_retries:
            reply = "Thank you for your time. Have a great day. Goodbye."
            history.append({"role": "bot", "text": reply})
            session.transcript = history
            session.status = CallStatus.REJECTED
            session.current_question_id = None
            return DecisionResult(
                action=ActionType.HANGUP,
                reply_text=reply,
                variables=variables,
                done=True,
                confidence=confidence,
            )
        reply = f"Sorry, I didn't catch that. {question.prompt}"
        history.append({"role": "bot", "text": reply})
        session.transcript = history
        session.status = CallStatus.IN_PROGRESS
        return DecisionResult(
            action=ActionType.REPEAT,
            reply_text=reply,
            next_question_id=question.id,
            variables=variables,
            confidence=confidence,
        )

    # Matched answer — apply action
    session.retry_count = 0
    if question.variable_name:
        value = matched.store_value if matched.store_value is not None else matched.intent
        variables[question.variable_name] = value
    session.variables = variables

    action = matched.action or ActionType.CONTINUE

    if action == ActionType.TRANSFER:
        reply = "Great, you qualify. Please hold while I transfer you to a specialist."
        history.append({"role": "bot", "text": reply})
        session.transcript = history
        session.status = CallStatus.QUALIFIED
        session.transfer_campaign = bot.transfer_campaign
        session.current_question_id = None
        return DecisionResult(
            action=ActionType.TRANSFER,
            intent=matched.intent,
            confidence=confidence,
            reply_text=reply,
            variables=variables,
            transfer_campaign=bot.transfer_campaign,
            done=True,
        )

    if action == ActionType.HANGUP:
        reply = "Thank you for your time. Goodbye."
        history.append({"role": "bot", "text": reply})
        session.transcript = history
        session.status = CallStatus.REJECTED
        session.current_question_id = None
        return DecisionResult(
            action=ActionType.HANGUP,
            intent=matched.intent,
            confidence=confidence,
            reply_text=reply,
            variables=variables,
            done=True,
        )

    if action == ActionType.REPEAT:
        reply = question.prompt
        history.append({"role": "bot", "text": reply})
        session.transcript = history
        return DecisionResult(
            action=ActionType.REPEAT,
            intent=matched.intent,
            confidence=confidence,
            reply_text=reply,
            next_question_id=question.id,
            variables=variables,
        )

    # CONTINUE / STORE → next question
    next_q: Optional[Question] = None
    if matched.next_question_id:
        next_q = await load_question(db, matched.next_question_id)
    else:
        # Fall through to next sort_order
        result = await db.execute(
            select(Question)
            .options(selectinload(Question.answers))
            .where(
                Question.bot_id == bot.id,
                Question.sort_order > question.sort_order,
            )
            .order_by(Question.sort_order.asc())
        )
        next_q = result.scalars().first()

    if next_q:
        reply = next_q.prompt
        history.append({"role": "bot", "text": reply})
        session.transcript = history
        session.current_question_id = next_q.id
        session.status = CallStatus.IN_PROGRESS
        return DecisionResult(
            action=ActionType.CONTINUE,
            intent=matched.intent,
            confidence=confidence,
            reply_text=reply,
            next_question_id=next_q.id,
            variables=variables,
        )

    # No more questions → qualify & transfer
    reply = "Thank you. Please hold while I connect you with a specialist."
    history.append({"role": "bot", "text": reply})
    session.transcript = history
    session.status = CallStatus.QUALIFIED
    session.current_question_id = None
    session.transfer_campaign = bot.transfer_campaign
    return DecisionResult(
        action=ActionType.TRANSFER,
        intent=matched.intent,
        confidence=confidence,
        reply_text=reply,
        variables=variables,
        transfer_campaign=bot.transfer_campaign,
        done=True,
    )
