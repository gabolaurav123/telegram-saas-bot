from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0007_user_language_currency"
down_revision = "0006_schema_indexes"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("users", "preferred_language"):
        op.add_column(
            "users",
            sa.Column("preferred_language", sa.String(length=8), server_default="es", nullable=False),
        )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_users_preferred_language" ON "users" ("preferred_language")')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "ix_users_preferred_language"')
    if _has_column("users", "preferred_language"):
        op.drop_column("users", "preferred_language")
