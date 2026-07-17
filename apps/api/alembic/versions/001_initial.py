"""Initial schema

Revision ID: 001_initial
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), server_default="Admin"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "bots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("campaign", sa.String(100), nullable=False),
        sa.Column("transfer_campaign", sa.String(100), nullable=False),
        sa.Column("language", sa.String(20), server_default="en"),
        sa.Column("voice", sa.String(50), server_default="en_US-lessac-medium"),
        sa.Column("model", sa.String(100), server_default="qwen2.5:7b-instruct"),
        sa.Column("temperature", sa.Float(), server_default="0.2"),
        sa.Column("greeting", sa.Text()),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_bots_name", "bots", ["name"])
    op.create_index("ix_bots_campaign", "bots", ["campaign"])

    action_enum = sa.Enum(
        "continue", "transfer", "hangup", "repeat", "callback", "human", "store",
        name="actiontype",
    )
    call_enum = sa.Enum(
        "started", "in_progress", "qualified", "transferred", "rejected",
        "hangup", "failed", "completed",
        name="callstatus",
    )
    action_enum.create(op.get_bind(), checkfirst=True)
    call_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_id", sa.Integer(), sa.ForeignKey("bots.id", ondelete="CASCADE")),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("variable_name", sa.String(100), nullable=True),
        sa.Column("timeout_ms", sa.Integer(), server_default="8000"),
        sa.Column("max_retries", sa.Integer(), server_default="2"),
        sa.Column("is_start", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_questions_bot_id", "questions", ["bot_id"])

    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE")),
        sa.Column("intent", sa.String(100), nullable=False),
        sa.Column("keywords", sa.JSON()),
        sa.Column("next_question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", action_enum, server_default="continue"),
        sa.Column("store_value", sa.String(255), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_answers_question_id", "answers", ["question_id"])
    op.create_index("ix_answers_intent", "answers", ["intent"])

    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_id", sa.Integer(), sa.ForeignKey("bots.id"), nullable=True),
        sa.Column("vicidial_call_id", sa.String(100), nullable=True),
        sa.Column("lead_id", sa.String(50), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("campaign", sa.String(100), nullable=True),
        sa.Column("status", call_enum, server_default="started"),
        sa.Column("current_question_id", sa.Integer(), nullable=True),
        sa.Column("variables", sa.JSON()),
        sa.Column("transcript", sa.JSON()),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("transfer_campaign", sa.String(100), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_call_vicidial", "call_sessions", ["vicidial_call_id"])


def downgrade() -> None:
    op.drop_table("call_sessions")
    op.drop_table("answers")
    op.drop_table("questions")
    op.drop_table("bots")
    op.drop_table("users")
    sa.Enum(name="actiontype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="callstatus").drop(op.get_bind(), checkfirst=True)
