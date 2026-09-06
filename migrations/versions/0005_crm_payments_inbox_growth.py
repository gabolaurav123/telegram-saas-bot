from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0005_crm_growth"
down_revision = "0004_access_events"
branch_labels = None
depends_on = None

_TABLES_CACHE: set[str] | None = None
_COLUMNS_CACHE: dict[str, set[str]] = {}


def upgrade() -> None:
    _add_user_columns()
    _add_payment_request_columns()
    _add_membership_columns()
    _add_support_thread_columns()
    _create_crm_tables()
    _create_messaging_tables()
    _create_payment_integration_tables()
    _create_growth_tables()
    _create_automation_tables()


def downgrade() -> None:
    for table_name in [
        "automation_jobs",
        "automation_rules",
        "coupon_redemptions",
        "coupons",
        "referrals",
        "campaigns",
        "provider_webhook_events",
        "external_payment_sessions",
        "telegram_stars_payments",
        "payment_receipts",
        "inbox_messages",
        "outbound_messages",
        "quick_replies",
        "funnel_events",
        "crm_state_history",
        "user_notes",
        "user_tags",
        "crm_tags",
    ]:
        if _has_table(table_name):
            op.drop_table(table_name)

    _drop_column_if_exists("support_threads", "resolved_at")
    _drop_column_if_exists("support_threads", "unread_user_count")
    _drop_column_if_exists("support_threads", "unread_admin_count")
    _drop_fk_if_exists("support_threads", "fk_support_threads_assigned_admin_user_id_users")
    _drop_column_if_exists("support_threads", "assigned_admin_user_id")

    for column in ["restored_at", "refunded_at", "suspended_at"]:
        _drop_column_if_exists("memberships", column)

    for column in [
        "reference",
        "invoice_payload",
        "telegram_payment_charge_id",
        "provider_payment_id",
        "receipt_warning_count",
        "receipt_perceptual_hash",
        "receipt_sha256",
    ]:
        _drop_column_if_exists("payment_requests", column)

    _drop_fk_if_exists("users", "fk_users_referred_by_user_id_users")
    for column in [
        "metadata_json",
        "delivery_status",
        "is_vip",
        "internal_notes",
        "referred_by_user_id",
        "referral_code",
        "campaign",
        "source",
        "start_parameter",
        "crm_status",
        "blocked_at",
        "last_contacted_at",
        "last_start_at",
        "first_started_at",
        "chat_id",
    ]:
        _drop_column_if_exists("users", column)


def _add_user_columns() -> None:
    _add_column_if_missing("users", sa.Column("chat_id", sa.BigInteger(), nullable=True))
    _add_column_if_missing("users", sa.Column("first_started_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("users", sa.Column("last_start_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("users", sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("users", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing(
        "users",
        sa.Column("crm_status", sa.String(length=32), server_default="LEAD", nullable=False),
    )
    _add_column_if_missing("users", sa.Column("start_parameter", sa.String(length=255), nullable=True))
    _add_column_if_missing("users", sa.Column("source", sa.String(length=120), nullable=True))
    _add_column_if_missing("users", sa.Column("campaign", sa.String(length=120), nullable=True))
    _add_column_if_missing("users", sa.Column("referral_code", sa.String(length=64), nullable=True))
    _add_column_if_missing("users", sa.Column("referred_by_user_id", sa.Integer(), nullable=True))
    _add_column_if_missing("users", sa.Column("internal_notes", sa.Text(), nullable=True))
    _add_column_if_missing(
        "users",
        sa.Column("is_vip", sa.Boolean(), server_default="false", nullable=False),
    )
    _add_column_if_missing(
        "users",
        sa.Column("delivery_status", sa.String(length=32), server_default="UNKNOWN", nullable=False),
    )
    _add_column_if_missing(
        "users",
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    _create_fk_if_missing(
        "users",
        "fk_users_referred_by_user_id_users",
        "users",
        ["referred_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for column in [
        "chat_id",
        "first_started_at",
        "last_start_at",
        "last_contacted_at",
        "blocked_at",
        "crm_status",
        "source",
        "campaign",
        "referral_code",
        "referred_by_user_id",
        "is_vip",
    ]:
        _create_index_if_missing(f"ix_users_{column}", "users", [column], unique=column == "referral_code")
    op.execute("UPDATE users SET chat_id = telegram_id WHERE chat_id IS NULL")
    op.execute("UPDATE users SET first_started_at = registered_at WHERE first_started_at IS NULL")
    op.execute("UPDATE users SET last_contacted_at = registered_at WHERE last_contacted_at IS NULL")


def _add_payment_request_columns() -> None:
    _add_column_if_missing("payment_requests", sa.Column("receipt_sha256", sa.String(length=64), nullable=True))
    _add_column_if_missing(
        "payment_requests",
        sa.Column("receipt_perceptual_hash", sa.String(length=64), nullable=True),
    )
    _add_column_if_missing(
        "payment_requests",
        sa.Column("receipt_warning_count", sa.Integer(), server_default="0", nullable=False),
    )
    _add_column_if_missing("payment_requests", sa.Column("provider_payment_id", sa.String(length=255), nullable=True))
    _add_column_if_missing(
        "payment_requests",
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=True),
    )
    _add_column_if_missing("payment_requests", sa.Column("invoice_payload", sa.String(length=128), nullable=True))
    _add_column_if_missing("payment_requests", sa.Column("reference", sa.String(length=255), nullable=True))
    for column in [
        "receipt_sha256",
        "receipt_perceptual_hash",
        "provider_payment_id",
        "telegram_payment_charge_id",
        "invoice_payload",
        "reference",
    ]:
        _create_index_if_missing(
            f"ix_payment_requests_{column}",
            "payment_requests",
            [column],
            unique=column in {"telegram_payment_charge_id", "invoice_payload"},
        )


def _add_membership_columns() -> None:
    _add_column_if_missing("memberships", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("memberships", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("memberships", sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True))


def _add_support_thread_columns() -> None:
    _add_column_if_missing("support_threads", sa.Column("assigned_admin_user_id", sa.Integer(), nullable=True))
    _add_column_if_missing(
        "support_threads",
        sa.Column("unread_admin_count", sa.Integer(), server_default="0", nullable=False),
    )
    _add_column_if_missing(
        "support_threads",
        sa.Column("unread_user_count", sa.Integer(), server_default="0", nullable=False),
    )
    _add_column_if_missing("support_threads", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    _create_fk_if_missing(
        "support_threads",
        "fk_support_threads_assigned_admin_user_id_users",
        "users",
        ["assigned_admin_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_index_if_missing(
        "ix_support_threads_assigned_admin_user_id",
        "support_threads",
        ["assigned_admin_user_id"],
    )
    _create_index_if_missing("ix_support_threads_resolved_at", "support_threads", ["resolved_at"])


def _create_crm_tables() -> None:
    if not _has_table("crm_tags"):
        op.create_table(
            "crm_tags",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("color", sa.String(length=32), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
            *_timestamps(),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_crm_tags_name"),
        )
        _create_index_if_missing("ix_crm_tags_name", "crm_tags", ["name"], unique=True)
        _create_index_if_missing("ix_crm_tags_is_active", "crm_tags", ["is_active"])

    if not _has_table("user_tags"):
        op.create_table(
            "user_tags",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.Column("added_by_user_id", sa.Integer(), nullable=True),
            *_timestamps(),
            sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tag_id"], ["crm_tags.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "tag_id", name="uq_user_tag"),
        )
        _create_index_if_missing("ix_user_tags_user_id", "user_tags", ["user_id"])
        _create_index_if_missing("ix_user_tags_tag_id", "user_tags", ["tag_id"])
        _create_index_if_missing("ix_user_tags_added_by_user_id", "user_tags", ["added_by_user_id"])

    if not _has_table("user_notes"):
        op.create_table(
            "user_notes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("is_internal", sa.Boolean(), server_default="true", nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_index_if_missing("ix_user_notes_user_id", "user_notes", ["user_id"])
        _create_index_if_missing("ix_user_notes_author_user_id", "user_notes", ["author_user_id"])

    if not _has_table("crm_state_history"):
        op.create_table(
            "crm_state_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("from_status", sa.String(length=32), nullable=True),
            sa.Column("to_status", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.String(length=255), nullable=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_index_if_missing("ix_crm_state_history_user_id", "crm_state_history", ["user_id"])
        _create_index_if_missing("ix_crm_state_history_to_status", "crm_state_history", ["to_status"])
        _create_index_if_missing("ix_crm_state_history_actor_user_id", "crm_state_history", ["actor_user_id"])
        _create_index_if_missing("ix_crm_state_history_changed_at", "crm_state_history", ["changed_at"])

    if not _has_table("funnel_events"):
        op.create_table(
            "funnel_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("event_name", sa.String(length=80), nullable=False),
            sa.Column("source", sa.String(length=120), nullable=True),
            sa.Column("campaign", sa.String(length=120), nullable=True),
            sa.Column("plan_id", sa.Integer(), nullable=True),
            sa.Column("payment_request_id", sa.Integer(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ["user_id", "event_name", "source", "campaign", "plan_id", "payment_request_id", "occurred_at"]:
            _create_index_if_missing(f"ix_funnel_events_{column}", "funnel_events", [column])


def _create_messaging_tables() -> None:
    if not _has_table("outbound_messages"):
        op.create_table(
            "outbound_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("target_user_id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
            sa.Column("telegram_message_id", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(length=40), server_default="ADMIN_DIRECT", nullable=False),
            sa.Column("content_type", sa.String(length=40), server_default="text", nullable=False),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ["target_user_id", "actor_user_id", "telegram_chat_id", "telegram_message_id", "status", "sent_at", "failed_at"]:
            _create_index_if_missing(f"ix_outbound_messages_{column}", "outbound_messages", [column])

    if not _has_table("inbox_messages"):
        op.create_table(
            "inbox_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("support_thread_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("admin_user_id", sa.Integer(), nullable=True),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
            sa.Column("telegram_message_id", sa.Integer(), nullable=True),
            sa.Column("content_type", sa.String(length=40), nullable=False),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("file_id", sa.String(length=255), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["support_thread_id"], ["support_threads.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in [
            "support_thread_id",
            "user_id",
            "admin_user_id",
            "direction",
            "telegram_chat_id",
            "telegram_message_id",
            "sent_at",
        ]:
            _create_index_if_missing(f"ix_inbox_messages_{column}", "inbox_messages", [column])

    if not _has_table("quick_replies"):
        op.create_table(
            "quick_replies",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("command", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            *_timestamps(),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("command", name="uq_quick_replies_command"),
        )
        _create_index_if_missing("ix_quick_replies_command", "quick_replies", ["command"])
        _create_index_if_missing("ix_quick_replies_is_active", "quick_replies", ["is_active"])
        _create_index_if_missing("ix_quick_replies_created_by_user_id", "quick_replies", ["created_by_user_id"])


def _create_payment_integration_tables() -> None:
    if not _has_table("payment_receipts"):
        op.create_table(
            "payment_receipts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("payment_request_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("proof_kind", sa.String(length=32), nullable=False),
            sa.Column("file_id", sa.String(length=255), nullable=False),
            sa.Column("file_unique_id", sa.String(length=255), nullable=True),
            sa.Column("sha256", sa.String(length=64), nullable=True),
            sa.Column("perceptual_hash", sa.String(length=64), nullable=True),
            sa.Column("duplicate_of_payment_request_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="CLEAN", nullable=False),
            sa.Column("warning_text", sa.Text(), nullable=True),
            sa.Column("warnings_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["duplicate_of_payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("payment_request_id", name="uq_payment_receipts_payment_request"),
        )
        for column in [
            "payment_request_id",
            "user_id",
            "file_unique_id",
            "sha256",
            "perceptual_hash",
            "duplicate_of_payment_request_id",
            "status",
        ]:
            _create_index_if_missing(f"ix_payment_receipts_{column}", "payment_receipts", [column])

    if not _has_table("telegram_stars_payments"):
        op.create_table(
            "telegram_stars_payments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("payment_request_id", sa.Integer(), nullable=True),
            sa.Column("invoice_payload", sa.String(length=128), nullable=False),
            sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=True),
            sa.Column("provider_payment_charge_id", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="INVOICE_CREATED", nullable=False),
            sa.Column("amount_stars", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=8), server_default="XTR", nullable=False),
            sa.Column("subscription_period", sa.Integer(), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("invoice_payload", name="uq_stars_invoice_payload"),
            sa.UniqueConstraint("telegram_payment_charge_id", name="uq_stars_charge_id"),
        )
        for column in [
            "user_id",
            "plan_id",
            "payment_request_id",
            "invoice_payload",
            "telegram_payment_charge_id",
            "provider_payment_charge_id",
            "status",
            "paid_at",
            "refunded_at",
        ]:
            _create_index_if_missing(f"ix_telegram_stars_payments_{column}", "telegram_stars_payments", [column])

    if not _has_table("external_payment_sessions"):
        op.create_table(
            "external_payment_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("payment_request_id", sa.Integer(), nullable=True),
            sa.Column("provider", sa.String(length=80), nullable=False),
            sa.Column("provider_session_id", sa.String(length=255), nullable=False),
            sa.Column("checkout_url", sa.Text(), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="CREATED", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "provider_session_id", name="uq_external_payment_session"),
        )
        for column in ["user_id", "plan_id", "payment_request_id", "provider", "provider_session_id", "status", "expires_at"]:
            _create_index_if_missing(f"ix_external_payment_sessions_{column}", "external_payment_sessions", [column])

    if not _has_table("provider_webhook_events"):
        op.create_table(
            "provider_webhook_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=80), nullable=False),
            sa.Column("event_id", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="RECEIVED", nullable=False),
            sa.Column("payload_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            *_timestamps(),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "event_id", name="uq_provider_webhook_event"),
        )
        for column in ["provider", "event_id", "status", "processed_at"]:
            _create_index_if_missing(f"ix_provider_webhook_events_{column}", "provider_webhook_events", [column])


def _create_growth_tables() -> None:
    if not _has_table("coupons"):
        op.create_table(
            "coupons",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("coupon_type", sa.String(length=32), nullable=False),
            sa.Column("value", sa.Numeric(12, 2), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=True),
            sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column("uses_per_user", sa.Integer(), server_default="1", nullable=False),
            sa.Column("new_users_only", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("expired_users_only", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_coupons_code"),
        )
        for column in ["code", "coupon_type", "plan_id", "start_date", "end_date", "enabled"]:
            _create_index_if_missing(f"ix_coupons_{column}", "coupons", [column], unique=column == "code")

    if not _has_table("coupon_redemptions"):
        op.create_table(
            "coupon_redemptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("coupon_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("payment_request_id", sa.Integer(), nullable=True),
            sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("coupon_id", "user_id", "payment_request_id", name="uq_coupon_redemption_payment"),
        )
        for column in ["coupon_id", "user_id", "payment_request_id", "redeemed_at"]:
            _create_index_if_missing(f"ix_coupon_redemptions_{column}", "coupon_redemptions", [column])

    if not _has_table("referrals"):
        op.create_table(
            "referrals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("referrer_user_id", sa.Integer(), nullable=False),
            sa.Column("referred_user_id", sa.Integer(), nullable=False),
            sa.Column("first_payment_request_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
            sa.Column("revenue", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("reward_granted_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamps(),
            sa.ForeignKeyConstraint(["first_payment_request_id"], ["payment_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("referrer_user_id", "referred_user_id", name="uq_referral_pair"),
        )
        for column in ["referrer_user_id", "referred_user_id", "first_payment_request_id", "status", "reward_granted_at"]:
            _create_index_if_missing(f"ix_referrals_{column}", "referrals", [column])

    if not _has_table("campaigns"):
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=120), nullable=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("start_parameter", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            *_timestamps(),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("start_parameter", name="uq_campaigns_start_parameter"),
        )
        for column in ["source", "name", "start_parameter", "is_active"]:
            _create_index_if_missing(f"ix_campaigns_{column}", "campaigns", [column], unique=column == "start_parameter")


def _create_automation_tables() -> None:
    if not _has_table("automation_rules"):
        op.create_table(
            "automation_rules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("trigger", sa.String(length=80), nullable=False),
            sa.Column("delay_seconds", sa.Integer(), server_default="0", nullable=False),
            sa.Column("conditions_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("action_payload_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            *_timestamps(),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ["trigger", "action", "enabled", "created_by_user_id"]:
            _create_index_if_missing(f"ix_automation_rules_{column}", "automation_rules", [column])

    if not _has_table("automation_jobs"):
        op.create_table(
            "automation_jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("rule_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("trigger", sa.String(length=80), nullable=False),
            sa.Column("dedupe_key", sa.String(length=255), nullable=False),
            sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
            sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamps(),
            sa.ForeignKeyConstraint(["rule_id"], ["automation_rules.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dedupe_key", name="uq_automation_jobs_dedupe_key"),
        )
        for column in ["rule_id", "user_id", "trigger", "dedupe_key", "run_at", "status", "executed_at"]:
            _create_index_if_missing(f"ix_automation_jobs_{column}", "automation_jobs", [column], unique=column == "dedupe_key")


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    global _TABLES_CACHE
    if _TABLES_CACHE is None:
        _TABLES_CACHE = set(_inspector().get_table_names())
    return table_name in _TABLES_CACHE


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    if table_name not in _COLUMNS_CACHE:
        _COLUMNS_CACHE[table_name] = {column["name"] for column in _inspector().get_columns(table_name)}
    return column_name in _COLUMNS_CACHE[table_name]


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    indexes = {index["name"] for index in _inspector().get_indexes(table_name)}
    constraints = {constraint["name"] for constraint in _inspector().get_unique_constraints(table_name)}
    return index_name in indexes or index_name in constraints


def _has_fk(table_name: str, fk_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return fk_name in {constraint["name"] for constraint in _inspector().get_foreign_keys(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _has_table(table_name) and not _has_column(table_name, column.name):
        op.add_column(table_name, column)
        _COLUMNS_CACHE.setdefault(table_name, set()).add(column.name)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_table(table_name) and _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    unique_sql = "UNIQUE " if unique else ""
    column_sql = ", ".join(f'"{column}"' for column in columns)
    op.execute(f'CREATE {unique_sql}INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ({column_sql})')


def _create_fk_if_missing(
    source_table: str,
    name: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str | None = None,
) -> None:
    if _has_table(source_table) and _has_table(referent_table) and not _has_fk(source_table, name):
        op.create_foreign_key(name, source_table, referent_table, local_cols, remote_cols, ondelete=ondelete)


def _drop_fk_if_exists(table_name: str, name: str) -> None:
    if _has_table(table_name) and _has_fk(table_name, name):
        op.drop_constraint(name, table_name, type_="foreignkey")
