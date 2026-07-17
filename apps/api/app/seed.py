"""Seed admin user + sample ACA qualifier bot."""
import asyncio
import logging

from sqlalchemy import select

from app.auth import hash_password
from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import ActionType, Answer, Bot, Question, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")
settings = get_settings()


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == settings.admin_email))
        admin = existing.scalar_one_or_none()
        if not admin:
            # Migrate legacy default account if present
            legacy = await db.execute(select(User).where(User.email == "admin@aibots.local"))
            admin = legacy.scalar_one_or_none()
            if admin:
                admin.email = settings.admin_email
                admin.hashed_password = hash_password(settings.admin_password)
                admin.is_active = True
                logger.info("Migrated admin to %s", settings.admin_email)
            else:
                db.add(
                    User(
                        email=settings.admin_email,
                        hashed_password=hash_password(settings.admin_password),
                        full_name="Admin",
                    )
                )
                logger.info("Created admin user: %s", settings.admin_email)
        else:
            # Keep password in sync with env on seed (setup / recovery)
            admin.hashed_password = hash_password(settings.admin_password)
            admin.is_active = True
            logger.info("Updated admin password for %s", settings.admin_email)

        bot_exists = await db.execute(select(Bot).where(Bot.name == "ACA Qualifier"))
        if bot_exists.scalar_one_or_none():
            await db.commit()
            logger.info("Sample bot already exists")
            return

        bot = Bot(
            name="ACA Qualifier",
            campaign="ACA2026",
            transfer_campaign="ACA_CLOSERS",
            language="en",
            voice="en_US-lessac-medium",
            model=settings.llm_model,
            temperature=0.2,
            greeting="Hello, this is Alex calling about your health insurance options. Do you have a moment?",
            active=True,
            description="Sample ACA qualification script with transfer to closer campaign.",
        )
        db.add(bot)
        await db.flush()

        q1 = Question(
            bot_id=bot.id,
            sort_order=1,
            prompt="Am I speaking with the person who requested information about health coverage?",
            variable_name="is_correct_person",
            is_start=True,
            max_retries=2,
        )
        q2 = Question(
            bot_id=bot.id,
            sort_order=2,
            prompt="Are you between the ages of 18 and 64?",
            variable_name="age_ok",
            max_retries=2,
        )
        q3 = Question(
            bot_id=bot.id,
            sort_order=3,
            prompt="Do you currently have Medicare?",
            variable_name="has_medicare",
            max_retries=2,
        )
        q4 = Question(
            bot_id=bot.id,
            sort_order=4,
            prompt="Are you interested in reviewing affordable coverage options today?",
            variable_name="interested",
            max_retries=2,
        )
        db.add_all([q1, q2, q3, q4])
        await db.flush()

        # Q1 answers
        db.add_all(
            [
                Answer(
                    question_id=q1.id,
                    intent="YES",
                    keywords=["yes", "yeah", "yep", "correct", "sure", "speaking", "this is"],
                    next_question_id=q2.id,
                    action=ActionType.CONTINUE,
                    store_value="yes",
                    priority=10,
                ),
                Answer(
                    question_id=q1.id,
                    intent="NO",
                    keywords=["no", "nope", "wrong", "not me", "incorrect"],
                    action=ActionType.HANGUP,
                    store_value="no",
                    priority=10,
                ),
            ]
        )
        # Q2
        db.add_all(
            [
                Answer(
                    question_id=q2.id,
                    intent="YES",
                    keywords=["yes", "yeah", "yep", "i am", "between", "correct"],
                    next_question_id=q3.id,
                    action=ActionType.CONTINUE,
                    store_value="yes",
                    priority=10,
                ),
                Answer(
                    question_id=q2.id,
                    intent="NO",
                    keywords=["no", "nope", "older", "younger", "65", "medicare age"],
                    action=ActionType.HANGUP,
                    store_value="no",
                    priority=10,
                ),
            ]
        )
        # Q3 — Medicare NO qualifies to continue; YES hangup (typical ACA filter)
        db.add_all(
            [
                Answer(
                    question_id=q3.id,
                    intent="NO",
                    keywords=["no", "nope", "do not", "don't", "dont", "not on medicare"],
                    next_question_id=q4.id,
                    action=ActionType.CONTINUE,
                    store_value="no",
                    priority=10,
                ),
                Answer(
                    question_id=q3.id,
                    intent="YES",
                    keywords=["yes", "yeah", "i have", "medicare", "on medicare"],
                    action=ActionType.HANGUP,
                    store_value="yes",
                    priority=10,
                ),
            ]
        )
        # Q4 — interested → transfer
        db.add_all(
            [
                Answer(
                    question_id=q4.id,
                    intent="YES",
                    keywords=["yes", "yeah", "sure", "interested", "okay", "ok", "please"],
                    action=ActionType.TRANSFER,
                    store_value="yes",
                    priority=10,
                ),
                Answer(
                    question_id=q4.id,
                    intent="NO",
                    keywords=["no", "nope", "not interested", "busy", "later"],
                    action=ActionType.HANGUP,
                    store_value="no",
                    priority=10,
                ),
            ]
        )

        await db.commit()
        logger.info("Seeded sample bot 'ACA Qualifier' (id=%s)", bot.id)


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception:
        logger.exception("Seed failed — API will still try to start")
        raise
