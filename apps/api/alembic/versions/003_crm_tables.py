"""Vendor SIP fields + CRM tables

Revision ID: 003_crm_tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_crm_tables"
down_revision: Union[str, None] = "002_vendor_sip"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vicidial_servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("sip_ip", sa.String(100), nullable=True),
        sa.Column("api_url", sa.String(255), nullable=True),
        sa.Column("api_user", sa.String(50), nullable=True),
        sa.Column("api_pass", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_vicidial_servers_name", "vicidial_servers", ["name"])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index("ix_vicidial_servers_name", table_name="vicidial_servers")
    op.drop_table("vicidial_servers")
