"""
AIBOTS SQLAlchemy models.

CRITICAL: answers.next_question_id must NEVER be a ForeignKey("questions.id").
Two FKs to questions breaks Mapper[Question].answers permanently.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import enum

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    pass


def utcnow():
    return datetime.now(timezone.utc)


class ActionType(str, enum.Enum):
    CONTINUE = "continue"
    TRANSFER = "transfer"
    HANGUP = "hangup"
    REPEAT = "repeat"
    CALLBACK = "callback"
    HUMAN = "human"
    STORE = "store"


class CallStatus(str, enum.Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"
    TRANSFERRED = "transferred"
    REJECTED = "rejected"
    HANGUP = "hangup"
    FAILED = "failed"
    COMPLETED = "completed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="Admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    campaign: Mapped[str] = mapped_column(String(100), index=True)
    transfer_campaign: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(20), default="en")
    voice: Mapped[str] = mapped_column(String(50), default="en_US-lessac-medium")
    model: Mapped[str] = mapped_column(String(100), default="qwen2.5:7b-instruct")
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    greeting: Mapped[str] = mapped_column(Text, default="Hello, thank you for taking our call.")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    prompt: Mapped[str] = mapped_column(Text)
    variable_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=8000)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    is_start: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent: Mapped[str] = mapped_column(String(100), index=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    # Plain int — NOT a ForeignKey (prevents dual-path mapper error)
    next_question_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[ActionType] = mapped_column(Enum(ActionType), default=ActionType.CONTINUE)
    store_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)


class CallSession(Base):
    __tablename__ = "call_sessions"
    __table_args__ = (Index("ix_call_vicidial", "vicidial_call_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bots.id"), nullable=True)
    vicidial_call_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    campaign: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus), default=CallStatus.STARTED)
    current_question_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    transfer_campaign: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Relationships configured AFTER all tables exist, with explicit foreign_keys
# using real Column objects. This is the reliable fix for dual-FK ambiguity.
# ---------------------------------------------------------------------------
Bot.questions = relationship(
    Question,
    back_populates="bot",
    cascade="all, delete-orphan",
    order_by=Question.sort_order,
    foreign_keys=[Question.bot_id],
)
Question.bot = relationship(
    Bot,
    back_populates="questions",
    foreign_keys=[Question.bot_id],
)

Question.answers = relationship(
    Answer,
    back_populates="question",
    cascade="all, delete-orphan",
    foreign_keys=[Answer.question_id],
)
Answer.question = relationship(
    Question,
    back_populates="answers",
    foreign_keys=[Answer.question_id],
)

Bot.calls = relationship(
    CallSession,
    back_populates="bot",
    foreign_keys=[CallSession.bot_id],
)
CallSession.bot = relationship(
    Bot,
    back_populates="calls",
    foreign_keys=[CallSession.bot_id],
)
