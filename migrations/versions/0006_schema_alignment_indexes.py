from __future__ import annotations

from alembic import op


revision = "0006_schema_indexes"
down_revision = "0005_crm_growth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in [
        "automation_jobs",
        "automation_rules",
        "broadcast_jobs",
        "broadcast_recipients",
        "campaigns",
        "coupon_redemptions",
        "coupons",
        "crm_state_history",
        "crm_tags",
        "external_payment_sessions",
        "funnel_events",
        "generated_invite_links",
        "inbox_messages",
        "membership_access_events",
        "outbound_messages",
        "payment_receipts",
        "provider_webhook_events",
        "quick_replies",
        "referrals",
        "support_reply_maps",
        "support_threads",
        "telegram_stars_payments",
        "user_notes",
        "user_tags",
    ]:
        op.execute(f'CREATE INDEX IF NOT EXISTS "ix_{table_name}_created_at" ON "{table_name}" ("created_at")')

    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_generated_invite_links_used_by_user_id" '
        'ON "generated_invite_links" ("used_by_user_id")'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "ix_generated_invite_links_used_by_user_id"')
    for table_name in [
        "user_tags",
        "user_notes",
        "telegram_stars_payments",
        "support_threads",
        "support_reply_maps",
        "referrals",
        "quick_replies",
        "provider_webhook_events",
        "payment_receipts",
        "outbound_messages",
        "membership_access_events",
        "inbox_messages",
        "generated_invite_links",
        "funnel_events",
        "external_payment_sessions",
        "crm_tags",
        "crm_state_history",
        "coupons",
        "coupon_redemptions",
        "campaigns",
        "broadcast_recipients",
        "broadcast_jobs",
        "automation_rules",
        "automation_jobs",
    ]:
        op.execute(f'DROP INDEX IF EXISTS "ix_{table_name}_created_at"')
