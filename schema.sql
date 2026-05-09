-- PostgreSQL schema reference.
-- The authoritative migration is migrations/versions/0001_initial.py.
-- Generate exact SQL for your configured database with:
--   alembic upgrade head --sql

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(128),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(16),
    is_bot BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ,
    banned_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE admins (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    telegram_id BIGINT NOT NULL UNIQUE,
    role VARCHAR(32) NOT NULL DEFAULT 'MODERATOR',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    permissions JSON NOT NULL DEFAULT '{}',
    added_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    deactivated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plans (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(140) NOT NULL,
    description TEXT,
    price NUMERIC(12,2) NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    duration_days INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 100,
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payment_methods (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    provider VARCHAR(32) NOT NULL DEFAULT 'CUSTOM',
    instructions TEXT NOT NULL,
    qr_file_id VARCHAR(255),
    account_data JSON NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    username VARCHAR(128),
    kind VARCHAR(32) NOT NULL DEFAULT 'CHANNEL',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    require_join_approval BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json JSON NOT NULL DEFAULT '{}',
    added_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE groups (
    id SERIAL PRIMARY KEY,
    telegram_chat_id BIGINT NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    username VARCHAR(128),
    kind VARCHAR(32) NOT NULL DEFAULT 'SUPERGROUP',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    require_join_approval BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json JSON NOT NULL DEFAULT '{}',
    added_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plan_channels (
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, channel_id)
);

CREATE TABLE plan_groups (
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, group_id)
);

CREATE TABLE plan_payment_methods (
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    payment_method_id INTEGER NOT NULL REFERENCES payment_methods(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, payment_method_id)
);

CREATE TABLE plan_payment_messages (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    payment_method_id INTEGER NOT NULL REFERENCES payment_methods(id) ON DELETE CASCADE,
    message_template TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (plan_id, payment_method_id)
);

CREATE TABLE payment_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
    payment_method_id INTEGER NOT NULL REFERENCES payment_methods(id) ON DELETE RESTRICT,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    amount NUMERIC(12,2) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    proof_kind VARCHAR(32),
    proof_file_id VARCHAR(255),
    proof_file_unique_id VARCHAR(255),
    proof_message_id INTEGER,
    admin_note TEXT,
    rejection_reason TEXT,
    metadata_json JSON NOT NULL DEFAULT '{}',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
    payment_request_id INTEGER UNIQUE REFERENCES payment_requests(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    starts_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    cancelled_at TIMESTAMPTZ,
    revoke_reason TEXT,
    reminder_3d_sent BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_1d_sent BOOLEAN NOT NULL DEFAULT FALSE,
    expired_notified BOOLEAN NOT NULL DEFAULT FALSE,
    access_payload JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    action VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'INFO',
    message TEXT NOT NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    target_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    details JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(120) NOT NULL UNIQUE,
    value JSON NOT NULL DEFAULT '{}',
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    membership_id INTEGER REFERENCES memberships(id) ON DELETE CASCADE,
    kind VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    scheduled_for TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    payload JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE statistics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    metric VARCHAR(80) NOT NULL,
    value NUMERIC(14,2) NOT NULL DEFAULT 0,
    metadata_json JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (date, metric)
);

