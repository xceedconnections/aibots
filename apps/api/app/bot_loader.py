"""Load bots/questions/answers without ORM relationships on Answer."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Answer, Bot, Question
from app.schemas import AnswerOut, BotOut, QuestionOut


async def load_answers(db: AsyncSession, question_id: int) -> list[Answer]:
    result = await db.execute(
        select(Answer)
        .where(Answer.question_id == question_id)
        .order_by(Answer.priority.desc(), Answer.id.asc())
    )
    return list(result.scalars().all())


async def load_answers_map(db: AsyncSession, question_ids: list[int]) -> dict[int, list[Answer]]:
    if not question_ids:
        return {}
    result = await db.execute(
        select(Answer)
        .where(Answer.question_id.in_(question_ids))
        .order_by(Answer.priority.desc(), Answer.id.asc())
    )
    out: dict[int, list[Answer]] = {qid: [] for qid in question_ids}
    for ans in result.scalars().all():
        out.setdefault(ans.question_id, []).append(ans)
    return out


async def get_bot(db: AsyncSession, bot_id: int) -> Optional[Bot]:
    result = await db.execute(
        select(Bot).options(selectinload(Bot.questions)).where(Bot.id == bot_id)
    )
    return result.scalar_one_or_none()


async def bot_to_out(db: AsyncSession, bot: Bot) -> BotOut:
    questions = sorted(bot.questions or [], key=lambda q: q.sort_order)
    amap = await load_answers_map(db, [q.id for q in questions])
    q_outs: list[QuestionOut] = []
    for q in questions:
        answers = [AnswerOut.model_validate(a) for a in amap.get(q.id, [])]
        q_outs.append(
            QuestionOut(
                id=q.id,
                bot_id=q.bot_id,
                prompt=q.prompt,
                sort_order=q.sort_order,
                variable_name=q.variable_name,
                timeout_ms=q.timeout_ms,
                max_retries=q.max_retries,
                is_start=q.is_start,
                answers=answers,
            )
        )
    return BotOut(
        id=bot.id,
        name=bot.name,
        campaign=bot.campaign,
        transfer_campaign=bot.transfer_campaign,
        language=bot.language,
        voice=bot.voice,
        model=bot.model,
        temperature=bot.temperature,
        greeting=bot.greeting,
        active=bot.active,
        description=bot.description,
        created_at=bot.created_at,
        updated_at=bot.updated_at,
        questions=q_outs,
    )


async def question_to_out(db: AsyncSession, q: Question) -> QuestionOut:
    answers = [AnswerOut.model_validate(a) for a in await load_answers(db, q.id)]
    return QuestionOut(
        id=q.id,
        bot_id=q.bot_id,
        prompt=q.prompt,
        sort_order=q.sort_order,
        variable_name=q.variable_name,
        timeout_ms=q.timeout_ms,
        max_retries=q.max_retries,
        is_start=q.is_start,
        answers=answers,
    )
