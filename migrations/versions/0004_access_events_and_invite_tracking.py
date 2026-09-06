from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0004_access_events"
down_revision = "0003_broadcast_bigint_chat_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if _has_column("generated_invite_links", "membership_id") and _has_table("membership_access_events"):
        return
    op.add_column("generated_invite_links", sa.Column("membership_id", sa.Integer(), nullable=True))
    op.add_column("generated_invite_links", sa.Column("payment_request_id", sa.Integer(), nullable=True))
    op.add_column("generated_invite_links", sa.Column("approved_by_user_id", sa.Integer(), nullable=True))
    op.add_column("generated_invite_links", sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "generated_invite_links",
        sa.Column("join_confirmed", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("generated_invite_links", sa.Column("revoked_reason", sa.String(length=120), nullable=True))
    op.add_column("generated_invite_links", sa.Column("last_reissued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "generated_invite_links",
        sa.Column("reissue_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        "fk_generated_invite_links_membership_id_memberships",
        "generated_invite_links",
        "memberships",
        ["membership_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_generated_invite_links_payment_request_id_payment_requests",
        "generated_invite_links",
        "payment_requests",
        ["payment_request_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_generated_invite_links_approved_by_user_id_users",
        "generated_invite_links",
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_generated_invite_links_membership_id", "generated_invite_links", ["membership_id"])
    op.create_index("ix_generated_invite_links_payment_request_id", "generated_invite_links", ["payment_request_id"])
    op.create_index("ix_generated_invite_links_approved_by_user_id", "generated_invite_links", ["approved_by_user_id"])
    op.create_index("ix_generated_invite_links_joined_at", "generated_invite_links", ["joined_at"])
    op.create_index("ix_generated_invite_links_join_confirmed", "generated_invite_links", ["join_confirmed"])

    op.create_table(
        "membership_access_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=True),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("generated_invite_link_id", sa.Integer(), nullable=True),
        sa.Column("event_kind", sa.String(length=32), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_title", sa.String(length=255), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("join_confirmed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kick_result", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generated_invite_link_id"], ["generated_invite_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_membership_access_events_user_id", "membership_access_events", ["user_id"])
    op.create_index("ix_membership_access_events_membership_id", "membership_access_events", ["membership_id"])
    op.create_index("ix_membership_access_events_plan_id", "membership_access_events", ["plan_id"])
    op.create_index(
        "ix_membership_access_events_generated_invite_link_id",
        "membership_access_events",
        ["generated_invite_link_id"],
    )
    op.create_index("ix_membership_access_events_event_kind", "membership_access_events", ["event_kind"])
    op.create_index("ix_membership_access_events_telegram_chat_id", "membership_access_events", ["telegram_chat_id"])
    op.create_index("ix_membership_access_events_channel_id", "membership_access_events", ["channel_id"])
    op.create_index("ix_membership_access_events_group_id", "membership_access_events", ["group_id"])
    op.create_index("ix_membership_access_events_approved_by_user_id", "membership_access_events", ["approved_by_user_id"])
    op.create_index("ix_membership_access_events_event_at", "membership_access_events", ["event_at"])


def downgrade() -> None:
    op.drop_table("membership_access_events")
    op.drop_index("ix_generated_invite_links_join_confirmed", table_name="generated_invite_links")
    op.drop_index("ix_generated_invite_links_joined_at", table_name="generated_invite_links")
    op.drop_index("ix_generated_invite_links_approved_by_user_id", table_name="generated_invite_links")
    op.drop_index("ix_generated_invite_links_payment_request_id", table_name="generated_invite_links")
    op.drop_index("ix_generated_invite_links_membership_id", table_name="generated_invite_links")
    op.drop_constraint(
        "fk_generated_invite_links_approved_by_user_id_users",
        "generated_invite_links",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_generated_invite_links_payment_request_id_payment_requests",
        "generated_invite_links",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_generated_invite_links_membership_id_memberships",
        "generated_invite_links",
        type_="foreignkey",
    )
    op.drop_column("generated_invite_links", "reissue_count")
    op.drop_column("generated_invite_links", "last_reissued_at")
    op.drop_column("generated_invite_links", "revoked_reason")
    op.drop_column("generated_invite_links", "join_confirmed")
    op.drop_column("generated_invite_links", "joined_at")
    op.drop_column("generated_invite_links", "approved_by_user_id")
    op.drop_column("generated_invite_links", "payment_request_id")
    op.drop_column("generated_invite_links", "membership_id")


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
