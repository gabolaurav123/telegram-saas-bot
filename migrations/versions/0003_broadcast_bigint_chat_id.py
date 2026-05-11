from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_broadcast_bigint_chat_id"
down_revision = "0002_growth_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "broadcast_jobs",
        "source_chat_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "broadcast_jobs",
        "source_chat_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )

