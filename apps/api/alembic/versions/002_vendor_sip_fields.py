"""Vendor SIP fields: client_id, remote_agent, transfer_did

Revision ID: 002_vendor_sip
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_vendor_sip"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bots", sa.Column("client_id", sa.String(100), nullable=True))
    op.add_column("bots", sa.Column("remote_agent", sa.String(50), nullable=True))
    op.add_column("bots", sa.Column("transfer_did", sa.String(30), nullable=True))
    op.create_index("ix_bots_client_id", "bots", ["client_id"])
    op.create_index("ix_bots_remote_agent", "bots", ["remote_agent"])


def downgrade() -> None:
    op.drop_index("ix_bots_remote_agent", table_name="bots")
    op.drop_index("ix_bots_client_id", table_name="bots")
    op.drop_column("bots", "transfer_did")
    op.drop_column("bots", "remote_agent")
    op.drop_column("bots", "client_id")
