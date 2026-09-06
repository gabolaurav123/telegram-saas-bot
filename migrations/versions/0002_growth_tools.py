from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0002_growth_tools"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _has_table("generated_invite_links"):
        op.create_table(
            "generated_invite_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_user_id", sa.Integer(), nullable=True),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_title", sa.String(length=255), nullable=False),
        sa.Column("invite_link", sa.Text(), nullable=False),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("used_by_user_id", sa.Integer(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["used_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_link"),
        )
        op.create_index("ix_generated_invite_links_creator_user_id", "generated_invite_links", ["creator_user_id"])
        op.create_index("ix_generated_invite_links_plan_id", "generated_invite_links", ["plan_id"])
        op.create_index("ix_generated_invite_links_channel_id", "generated_invite_links", ["channel_id"])
        op.create_index("ix_generated_invite_links_group_id", "generated_invite_links", ["group_id"])
        op.create_index("ix_generated_invite_links_telegram_chat_id", "generated_invite_links", ["telegram_chat_id"])
        op.create_index("ix_generated_invite_links_expire_at", "generated_invite_links", ["expire_at"])
        op.create_index("ix_generated_invite_links_is_used", "generated_invite_links", ["is_used"])
        op.create_index("ix_generated_invite_links_revoked_at", "generated_invite_links", ["revoked_at"])

    if not _has_table("broadcast_jobs"):
        op.create_table(
            "broadcast_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("target", sa.String(length=40), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
        sa.Column("source_chat_id", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_broadcast_jobs_created_by_user_id", "broadcast_jobs", ["created_by_user_id"])
        op.create_index("ix_broadcast_jobs_target", "broadcast_jobs", ["target"])
        op.create_index("ix_broadcast_jobs_plan_id", "broadcast_jobs", ["plan_id"])

    if not _has_table("broadcast_recipients"):
        op.create_table(
            "broadcast_recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["broadcast_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "user_id", name="uq_broadcast_recipient_job_user"),
        )
        op.create_index("ix_broadcast_recipients_job_id", "broadcast_recipients", ["job_id"])
        op.create_index("ix_broadcast_recipients_user_id", "broadcast_recipients", ["user_id"])

    if not _has_table("support_threads"):
        op.create_table(
            "support_threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="OPEN", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_support_threads_user_id", "support_threads", ["user_id"])
        op.create_index("ix_support_threads_status", "support_threads", ["status"])
        op.create_index("ix_support_threads_last_message_at", "support_threads", ["last_message_at"])

    if not _has_table("support_reply_maps"):
        op.create_table(
            "support_reply_maps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("admin_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_message_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["support_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admin_chat_id", "admin_message_id", name="uq_support_reply_admin_message"),
        )
        op.create_index("ix_support_reply_maps_thread_id", "support_reply_maps", ["thread_id"])
        op.create_index("ix_support_reply_maps_user_id", "support_reply_maps", ["user_id"])
        op.create_index("ix_support_reply_maps_admin_chat_id", "support_reply_maps", ["admin_chat_id"])
        op.create_index("ix_support_reply_maps_admin_message_id", "support_reply_maps", ["admin_message_id"])


def downgrade() -> None:
    op.drop_table("support_reply_maps")
    op.drop_table("support_threads")
    op.drop_table("broadcast_recipients")
    op.drop_table("broadcast_jobs")
    op.drop_table("generated_invite_links")


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()
