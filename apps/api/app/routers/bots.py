from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.bot_loader import bot_to_out, get_bot, load_answers, load_answers_map, question_to_out
from app.database import get_db
from app.models import Answer, Bot, Question, User
from app.schemas import (
    AnswerCreate,
    AnswerOut,
    AnswerUpdate,
    BotCreate,
    BotListItem,
    BotOut,
    BotUpdate,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
)
from app.seed import seed_sample_bot

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("", response_model=list[BotListItem])
async def list_bots(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Bot).order_by(Bot.id.desc()))
    return result.scalars().all()


@router.post("/seed-sample", response_model=BotOut)
async def seed_sample(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Create the ACA Qualifier sample bot if missing."""
    bot = await seed_sample_bot(db)
    loaded = await get_bot(db, bot.id)
    return await bot_to_out(db, loaded)


@router.post("", response_model=BotOut, status_code=201)
async def create_bot(
    payload: BotCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    bot = Bot(**payload.model_dump())
    db.add(bot)
    await db.flush()
    loaded = await get_bot(db, bot.id)
    return await bot_to_out(db, loaded)


@router.get("/{bot_id}", response_model=BotOut)
async def get_bot_route(
    bot_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    bot = await get_bot(db, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    return await bot_to_out(db, bot)


@router.patch("/{bot_id}", response_model=BotOut)
async def update_bot(
    bot_id: int,
    payload: BotUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    bot = await get_bot(db, bot_id)
    if not bot:
        raise HTTPException(404, "Bot not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(bot, k, v)
    await db.flush()
    bot = await get_bot(db, bot_id)
    return await bot_to_out(db, bot)


@router.delete("/{bot_id}", status_code=204)
async def delete_bot(
    bot_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Bot).where(Bot.id == bot_id))
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")
    await db.delete(bot)


@router.post("/{bot_id}/clone", response_model=BotOut, status_code=201)
async def clone_bot(
    bot_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    src = await get_bot(db, bot_id)
    if not src:
        raise HTTPException(404, "Bot not found")

    amap = await load_answers_map(db, [q.id for q in (src.questions or [])])

    clone = Bot(
        name=f"{src.name} (Copy)",
        campaign=src.campaign,
        transfer_campaign=src.transfer_campaign,
        language=src.language,
        voice=src.voice,
        model=src.model,
        temperature=src.temperature,
        greeting=src.greeting,
        active=False,
        description=src.description,
    )
    db.add(clone)
    await db.flush()

    q_map: dict[int, int] = {}
    for q in src.questions or []:
        nq = Question(
            bot_id=clone.id,
            sort_order=q.sort_order,
            prompt=q.prompt,
            variable_name=q.variable_name,
            timeout_ms=q.timeout_ms,
            max_retries=q.max_retries,
            is_start=q.is_start,
        )
        db.add(nq)
        await db.flush()
        q_map[q.id] = nq.id

    for old_qid, answers in amap.items():
        for a in answers:
            db.add(
                Answer(
                    question_id=q_map[old_qid],
                    intent=a.intent,
                    keywords=list(a.keywords or []),
                    next_question_id=q_map.get(a.next_question_id) if a.next_question_id else None,
                    action=a.action,
                    store_value=a.store_value,
                    priority=a.priority,
                )
            )
    await db.flush()
    bot = await get_bot(db, clone.id)
    return await bot_to_out(db, bot)


@router.post("/{bot_id}/questions", response_model=QuestionOut, status_code=201)
async def add_question(
    bot_id: int,
    payload: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    bot = (await db.execute(select(Bot).where(Bot.id == bot_id))).scalar_one_or_none()
    if not bot:
        raise HTTPException(404, "Bot not found")

    data = payload.model_dump(exclude={"answers"})
    q = Question(bot_id=bot_id, **data)
    db.add(q)
    await db.flush()
    for a in payload.answers:
        db.add(Answer(question_id=q.id, **a.model_dump()))
    await db.flush()
    return await question_to_out(db, q)


@router.patch("/questions/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(q, k, v)
    await db.flush()
    await db.refresh(q)
    return await question_to_out(db, q)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    # delete answers first
    answers = await load_answers(db, question_id)
    for a in answers:
        await db.delete(a)
    await db.delete(q)


@router.post("/questions/{question_id}/answers", response_model=AnswerOut, status_code=201)
async def add_answer(
    question_id: int,
    payload: AnswerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = (await db.execute(select(Question).where(Question.id == question_id))).scalar_one_or_none()
    if not q:
        raise HTTPException(404, "Question not found")
    a = Answer(question_id=question_id, **payload.model_dump())
    db.add(a)
    await db.flush()
    await db.refresh(a)
    return a


@router.patch("/answers/{answer_id}", response_model=AnswerOut)
async def update_answer(
    answer_id: int,
    payload: AnswerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    a = (await db.execute(select(Answer).where(Answer.id == answer_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Answer not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await db.flush()
    await db.refresh(a)
    return a


@router.delete("/answers/{answer_id}", status_code=204)
async def delete_answer(
    answer_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    a = (await db.execute(select(Answer).where(Answer.id == answer_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Answer not found")
    await db.delete(a)
