-- PostgreSQL schema reference generated from SQLAlchemy metadata.
-- Authoritative migrations live in migrations/versions.
-- For deployment use: alembic upgrade head


CREATE TABLE campaigns (
	id SERIAL NOT NULL, 
	source VARCHAR(120), 
	name VARCHAR(120) NOT NULL, 
	start_parameter VARCHAR(255) NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_campaigns PRIMARY KEY (id), 
	CONSTRAINT uq_campaigns_start_parameter UNIQUE (start_parameter)
);

CREATE INDEX ix_campaigns_created_at ON campaigns (created_at);
CREATE INDEX ix_campaigns_is_active ON campaigns (is_active);
CREATE INDEX ix_campaigns_name ON campaigns (name);
CREATE INDEX ix_campaigns_source ON campaigns (source);
CREATE UNIQUE INDEX ix_campaigns_start_parameter ON campaigns (start_parameter);


CREATE TABLE crm_tags (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	color VARCHAR(32), 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_crm_tags PRIMARY KEY (id), 
	CONSTRAINT uq_crm_tags_name UNIQUE (name)
);

CREATE INDEX ix_crm_tags_created_at ON crm_tags (created_at);
CREATE INDEX ix_crm_tags_is_active ON crm_tags (is_active);
CREATE UNIQUE INDEX ix_crm_tags_name ON crm_tags (name);


CREATE TABLE payment_methods (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	provider VARCHAR(32) DEFAULT 'CUSTOM' NOT NULL, 
	instructions TEXT NOT NULL, 
	qr_file_id VARCHAR(255), 
	account_data JSON DEFAULT '{}' NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	sort_order INTEGER DEFAULT '100' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_payment_methods PRIMARY KEY (id), 
	CONSTRAINT uq_payment_methods_name UNIQUE (name)
);

CREATE INDEX ix_payment_methods_created_at ON payment_methods (created_at);
CREATE INDEX ix_payment_methods_is_active ON payment_methods (is_active);
CREATE INDEX ix_payment_methods_provider ON payment_methods (provider);


CREATE TABLE plans (
	id SERIAL NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	description TEXT, 
	price NUMERIC(12, 2) NOT NULL, 
	currency VARCHAR(8) DEFAULT 'USD' NOT NULL, 
	duration_days INTEGER NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	sort_order INTEGER DEFAULT '100' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_plans PRIMARY KEY (id)
);

CREATE INDEX ix_plans_created_at ON plans (created_at);
CREATE INDEX ix_plans_is_active ON plans (is_active);
CREATE UNIQUE INDEX ix_plans_slug ON plans (slug);


CREATE TABLE provider_webhook_events (
	id SERIAL NOT NULL, 
	provider VARCHAR(80) NOT NULL, 
	event_id VARCHAR(255) NOT NULL, 
	status VARCHAR(32) DEFAULT 'RECEIVED' NOT NULL, 
	payload_json JSON DEFAULT '{}' NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_provider_webhook_events PRIMARY KEY (id), 
	CONSTRAINT uq_provider_webhook_event UNIQUE (provider, event_id)
);

CREATE INDEX ix_provider_webhook_events_created_at ON provider_webhook_events (created_at);
CREATE INDEX ix_provider_webhook_events_event_id ON provider_webhook_events (event_id);
CREATE INDEX ix_provider_webhook_events_processed_at ON provider_webhook_events (processed_at);
CREATE INDEX ix_provider_webhook_events_provider ON provider_webhook_events (provider);
CREATE INDEX ix_provider_webhook_events_status ON provider_webhook_events (status);


CREATE TABLE settings (
	id SERIAL NOT NULL, 
	key VARCHAR(120) NOT NULL, 
	value JSON DEFAULT '{}' NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_settings PRIMARY KEY (id)
);

CREATE INDEX ix_settings_created_at ON settings (created_at);
CREATE UNIQUE INDEX ix_settings_key ON settings (key);


CREATE TABLE statistics (
	id SERIAL NOT NULL, 
	date DATE NOT NULL, 
	metric VARCHAR(80) NOT NULL, 
	value NUMERIC(14, 2) DEFAULT '0' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_statistics PRIMARY KEY (id), 
	CONSTRAINT uq_statistics_date_metric UNIQUE (date, metric)
);

CREATE INDEX ix_statistics_created_at ON statistics (created_at);
CREATE INDEX ix_statistics_date ON statistics (date);
CREATE INDEX ix_statistics_metric ON statistics (metric);


CREATE TABLE users (
	id SERIAL NOT NULL, 
	telegram_id BIGINT NOT NULL, 
	chat_id BIGINT, 
	username VARCHAR(128), 
	first_name VARCHAR(255), 
	last_name VARCHAR(255), 
	language_code VARCHAR(16), 
	is_bot BOOLEAN DEFAULT 'false' NOT NULL, 
	status VARCHAR(32) DEFAULT 'ACTIVE' NOT NULL, 
	registered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	first_started_at TIMESTAMP WITH TIME ZONE, 
	last_start_at TIMESTAMP WITH TIME ZONE, 
	last_seen_at TIMESTAMP WITH TIME ZONE, 
	last_contacted_at TIMESTAMP WITH TIME ZONE, 
	banned_at TIMESTAMP WITH TIME ZONE, 
	blocked_at TIMESTAMP WITH TIME ZONE, 
	crm_status VARCHAR(32) DEFAULT 'LEAD' NOT NULL, 
	start_parameter VARCHAR(255), 
	source VARCHAR(120), 
	campaign VARCHAR(120), 
	referral_code VARCHAR(64), 
	referred_by_user_id INTEGER, 
	internal_notes TEXT, 
	is_vip BOOLEAN DEFAULT 'false' NOT NULL, 
	delivery_status VARCHAR DEFAULT 'UNKNOWN' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT fk_users_referred_by_user_id_users FOREIGN KEY(referred_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_users_blocked_at ON users (blocked_at);
CREATE INDEX ix_users_campaign ON users (campaign);
CREATE INDEX ix_users_chat_id ON users (chat_id);
CREATE INDEX ix_users_created_at ON users (created_at);
CREATE INDEX ix_users_crm_status ON users (crm_status);
CREATE INDEX ix_users_first_started_at ON users (first_started_at);
CREATE INDEX ix_users_is_vip ON users (is_vip);
CREATE INDEX ix_users_last_contacted_at ON users (last_contacted_at);
CREATE INDEX ix_users_last_start_at ON users (last_start_at);
CREATE UNIQUE INDEX ix_users_referral_code ON users (referral_code);
CREATE INDEX ix_users_referred_by_user_id ON users (referred_by_user_id);
CREATE INDEX ix_users_registered_at ON users (registered_at);
CREATE INDEX ix_users_source ON users (source);
CREATE INDEX ix_users_status ON users (status);
CREATE UNIQUE INDEX ix_users_telegram_id ON users (telegram_id);
CREATE INDEX ix_users_username ON users (username);


CREATE TABLE admins (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	telegram_id BIGINT NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	permissions JSON DEFAULT '{}' NOT NULL, 
	added_by_id INTEGER, 
	deactivated_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_admins PRIMARY KEY (id), 
	CONSTRAINT uq_admins_telegram_id UNIQUE (telegram_id), 
	CONSTRAINT fk_admins_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_admins_added_by_id_users FOREIGN KEY(added_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_admins_created_at ON admins (created_at);
CREATE INDEX ix_admins_is_active ON admins (is_active);
CREATE INDEX ix_admins_role ON admins (role);
CREATE INDEX ix_admins_telegram_id ON admins (telegram_id);
CREATE UNIQUE INDEX ix_admins_user_id ON admins (user_id);


CREATE TABLE automation_rules (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	trigger VARCHAR(80) NOT NULL, 
	delay_seconds INTEGER DEFAULT '0' NOT NULL, 
	conditions_json JSON DEFAULT '{}' NOT NULL, 
	action VARCHAR(80) NOT NULL, 
	action_payload_json JSON DEFAULT '{}' NOT NULL, 
	enabled BOOLEAN DEFAULT 'true' NOT NULL, 
	created_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_automation_rules PRIMARY KEY (id), 
	CONSTRAINT fk_automation_rules_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_rules_action ON automation_rules (action);
CREATE INDEX ix_automation_rules_created_at ON automation_rules (created_at);
CREATE INDEX ix_automation_rules_created_by_user_id ON automation_rules (created_by_user_id);
CREATE INDEX ix_automation_rules_enabled ON automation_rules (enabled);
CREATE INDEX ix_automation_rules_trigger ON automation_rules (trigger);


CREATE TABLE broadcast_jobs (
	id SERIAL NOT NULL, 
	created_by_user_id INTEGER, 
	target VARCHAR(40) NOT NULL, 
	plan_id INTEGER, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	source_chat_id BIGINT NOT NULL, 
	source_message_id INTEGER NOT NULL, 
	total INTEGER DEFAULT '0' NOT NULL, 
	sent INTEGER DEFAULT '0' NOT NULL, 
	failed INTEGER DEFAULT '0' NOT NULL, 
	blocked INTEGER DEFAULT '0' NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_broadcast_jobs PRIMARY KEY (id), 
	CONSTRAINT fk_broadcast_jobs_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_broadcast_jobs_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE SET NULL
);

CREATE INDEX ix_broadcast_jobs_created_at ON broadcast_jobs (created_at);
CREATE INDEX ix_broadcast_jobs_created_by_user_id ON broadcast_jobs (created_by_user_id);
CREATE INDEX ix_broadcast_jobs_plan_id ON broadcast_jobs (plan_id);
CREATE INDEX ix_broadcast_jobs_target ON broadcast_jobs (target);


CREATE TABLE channels (
	id SERIAL NOT NULL, 
	telegram_chat_id BIGINT NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	username VARCHAR(128), 
	kind VARCHAR(32) DEFAULT 'CHANNEL' NOT NULL, 
	description TEXT, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	require_join_approval BOOLEAN DEFAULT 'false' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	added_by_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_channels PRIMARY KEY (id), 
	CONSTRAINT fk_channels_added_by_id_users FOREIGN KEY(added_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_channels_created_at ON channels (created_at);
CREATE INDEX ix_channels_is_active ON channels (is_active);
CREATE INDEX ix_channels_kind ON channels (kind);
CREATE UNIQUE INDEX ix_channels_telegram_chat_id ON channels (telegram_chat_id);
CREATE INDEX ix_channels_username ON channels (username);


CREATE TABLE coupons (
	id SERIAL NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	coupon_type VARCHAR(32) NOT NULL, 
	value NUMERIC(12, 2) NOT NULL, 
	plan_id INTEGER, 
	start_date TIMESTAMP WITH TIME ZONE, 
	end_date TIMESTAMP WITH TIME ZONE, 
	max_uses INTEGER, 
	uses_per_user INTEGER DEFAULT '1' NOT NULL, 
	new_users_only BOOLEAN DEFAULT 'false' NOT NULL, 
	expired_users_only BOOLEAN DEFAULT 'false' NOT NULL, 
	enabled BOOLEAN DEFAULT 'true' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_coupons PRIMARY KEY (id), 
	CONSTRAINT uq_coupons_code UNIQUE (code), 
	CONSTRAINT fk_coupons_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ix_coupons_code ON coupons (code);
CREATE INDEX ix_coupons_coupon_type ON coupons (coupon_type);
CREATE INDEX ix_coupons_created_at ON coupons (created_at);
CREATE INDEX ix_coupons_enabled ON coupons (enabled);
CREATE INDEX ix_coupons_end_date ON coupons (end_date);
CREATE INDEX ix_coupons_plan_id ON coupons (plan_id);
CREATE INDEX ix_coupons_start_date ON coupons (start_date);


CREATE TABLE crm_state_history (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	from_status VARCHAR(32), 
	to_status VARCHAR(32) NOT NULL, 
	reason VARCHAR(255), 
	actor_user_id INTEGER, 
	changed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_crm_state_history PRIMARY KEY (id), 
	CONSTRAINT fk_crm_state_history_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_crm_state_history_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_state_history_actor_user_id ON crm_state_history (actor_user_id);
CREATE INDEX ix_crm_state_history_changed_at ON crm_state_history (changed_at);
CREATE INDEX ix_crm_state_history_created_at ON crm_state_history (created_at);
CREATE INDEX ix_crm_state_history_to_status ON crm_state_history (to_status);
CREATE INDEX ix_crm_state_history_user_id ON crm_state_history (user_id);


CREATE TABLE groups (
	id SERIAL NOT NULL, 
	telegram_chat_id BIGINT NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	username VARCHAR(128), 
	kind VARCHAR(32) DEFAULT 'SUPERGROUP' NOT NULL, 
	description TEXT, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	require_join_approval BOOLEAN DEFAULT 'false' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	added_by_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_groups PRIMARY KEY (id), 
	CONSTRAINT fk_groups_added_by_id_users FOREIGN KEY(added_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_groups_created_at ON groups (created_at);
CREATE INDEX ix_groups_is_active ON groups (is_active);
CREATE INDEX ix_groups_kind ON groups (kind);
CREATE UNIQUE INDEX ix_groups_telegram_chat_id ON groups (telegram_chat_id);
CREATE INDEX ix_groups_username ON groups (username);


CREATE TABLE logs (
	id SERIAL NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	severity VARCHAR(16) DEFAULT 'INFO' NOT NULL, 
	message TEXT NOT NULL, 
	actor_user_id INTEGER, 
	target_user_id INTEGER, 
	details JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_logs PRIMARY KEY (id), 
	CONSTRAINT fk_logs_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_logs_target_user_id_users FOREIGN KEY(target_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_logs_action ON logs (action);
CREATE INDEX ix_logs_created_at ON logs (created_at);
CREATE INDEX ix_logs_severity ON logs (severity);


CREATE TABLE outbound_messages (
	id SERIAL NOT NULL, 
	target_user_id INTEGER NOT NULL, 
	actor_user_id INTEGER, 
	telegram_chat_id BIGINT NOT NULL, 
	telegram_message_id INTEGER, 
	source VARCHAR(40) DEFAULT 'ADMIN_DIRECT' NOT NULL, 
	content_type VARCHAR(40) DEFAULT 'text' NOT NULL, 
	text TEXT, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	failed_at TIMESTAMP WITH TIME ZONE, 
	error TEXT, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_outbound_messages PRIMARY KEY (id), 
	CONSTRAINT fk_outbound_messages_target_user_id_users FOREIGN KEY(target_user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_outbound_messages_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_outbound_messages_actor_user_id ON outbound_messages (actor_user_id);
CREATE INDEX ix_outbound_messages_created_at ON outbound_messages (created_at);
CREATE INDEX ix_outbound_messages_failed_at ON outbound_messages (failed_at);
CREATE INDEX ix_outbound_messages_sent_at ON outbound_messages (sent_at);
CREATE INDEX ix_outbound_messages_status ON outbound_messages (status);
CREATE INDEX ix_outbound_messages_target_user_id ON outbound_messages (target_user_id);
CREATE INDEX ix_outbound_messages_telegram_chat_id ON outbound_messages (telegram_chat_id);
CREATE INDEX ix_outbound_messages_telegram_message_id ON outbound_messages (telegram_message_id);


CREATE TABLE payment_requests (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	payment_method_id INTEGER NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	currency VARCHAR(8) NOT NULL, 
	proof_kind VARCHAR(32), 
	proof_file_id VARCHAR(255), 
	proof_file_unique_id VARCHAR(255), 
	proof_message_id INTEGER, 
	receipt_sha256 VARCHAR(64), 
	receipt_perceptual_hash VARCHAR(64), 
	receipt_warning_count INTEGER DEFAULT '0' NOT NULL, 
	provider_payment_id VARCHAR(255), 
	telegram_payment_charge_id VARCHAR(255), 
	invoice_payload VARCHAR(128), 
	reference VARCHAR(255), 
	admin_note TEXT, 
	rejection_reason TEXT, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	reviewed_by_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_payment_requests PRIMARY KEY (id), 
	CONSTRAINT fk_payment_requests_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_payment_requests_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_payment_requests_payment_method_id_payment_methods FOREIGN KEY(payment_method_id) REFERENCES payment_methods (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_payment_requests_reviewed_by_id_users FOREIGN KEY(reviewed_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_payment_requests_created_at ON payment_requests (created_at);
CREATE UNIQUE INDEX ix_payment_requests_invoice_payload ON payment_requests (invoice_payload);
CREATE INDEX ix_payment_requests_payment_method_id ON payment_requests (payment_method_id);
CREATE INDEX ix_payment_requests_plan_id ON payment_requests (plan_id);
CREATE INDEX ix_payment_requests_provider_payment_id ON payment_requests (provider_payment_id);
CREATE INDEX ix_payment_requests_receipt_perceptual_hash ON payment_requests (receipt_perceptual_hash);
CREATE INDEX ix_payment_requests_receipt_sha256 ON payment_requests (receipt_sha256);
CREATE INDEX ix_payment_requests_reference ON payment_requests (reference);
CREATE INDEX ix_payment_requests_status ON payment_requests (status);
CREATE INDEX ix_payment_requests_submitted_at ON payment_requests (submitted_at);
CREATE UNIQUE INDEX ix_payment_requests_telegram_payment_charge_id ON payment_requests (telegram_payment_charge_id);
CREATE INDEX ix_payment_requests_user_id ON payment_requests (user_id);


CREATE TABLE plan_payment_messages (
	id SERIAL NOT NULL, 
	plan_id INTEGER NOT NULL, 
	payment_method_id INTEGER NOT NULL, 
	message_template TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_plan_payment_messages PRIMARY KEY (id), 
	CONSTRAINT uq_plan_payment_message_pair UNIQUE (plan_id, payment_method_id), 
	CONSTRAINT fk_plan_payment_messages_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	CONSTRAINT fk_plan_payment_messages_payment_method_id_payment_methods FOREIGN KEY(payment_method_id) REFERENCES payment_methods (id) ON DELETE CASCADE
);

CREATE INDEX ix_plan_payment_messages_created_at ON plan_payment_messages (created_at);
CREATE INDEX ix_plan_payment_messages_payment_method_id ON plan_payment_messages (payment_method_id);
CREATE INDEX ix_plan_payment_messages_plan_id ON plan_payment_messages (plan_id);


CREATE TABLE plan_payment_methods (
	plan_id INTEGER NOT NULL, 
	payment_method_id INTEGER NOT NULL, 
	CONSTRAINT pk_plan_payment_methods PRIMARY KEY (plan_id, payment_method_id), 
	CONSTRAINT fk_plan_payment_methods_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	CONSTRAINT fk_plan_payment_methods_payment_method_id_payment_methods FOREIGN KEY(payment_method_id) REFERENCES payment_methods (id) ON DELETE CASCADE
);


CREATE TABLE quick_replies (
	id SERIAL NOT NULL, 
	command VARCHAR(40) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	body TEXT NOT NULL, 
	sort_order INTEGER DEFAULT '100' NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_quick_replies PRIMARY KEY (id), 
	CONSTRAINT uq_quick_replies_command UNIQUE (command), 
	CONSTRAINT fk_quick_replies_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_quick_replies_command ON quick_replies (command);
CREATE INDEX ix_quick_replies_created_at ON quick_replies (created_at);
CREATE INDEX ix_quick_replies_created_by_user_id ON quick_replies (created_by_user_id);
CREATE INDEX ix_quick_replies_is_active ON quick_replies (is_active);


CREATE TABLE support_threads (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	status VARCHAR DEFAULT 'OPEN' NOT NULL, 
	assigned_admin_user_id INTEGER, 
	unread_admin_count INTEGER DEFAULT '0' NOT NULL, 
	unread_user_count INTEGER DEFAULT '0' NOT NULL, 
	last_message_at TIMESTAMP WITH TIME ZONE, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_support_threads PRIMARY KEY (id), 
	CONSTRAINT uq_support_threads_user_id UNIQUE (user_id), 
	CONSTRAINT fk_support_threads_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_support_threads_assigned_admin_user_id_users FOREIGN KEY(assigned_admin_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_support_threads_assigned_admin_user_id ON support_threads (assigned_admin_user_id);
CREATE INDEX ix_support_threads_created_at ON support_threads (created_at);
CREATE INDEX ix_support_threads_last_message_at ON support_threads (last_message_at);
CREATE INDEX ix_support_threads_resolved_at ON support_threads (resolved_at);
CREATE INDEX ix_support_threads_status ON support_threads (status);
CREATE INDEX ix_support_threads_user_id ON support_threads (user_id);


CREATE TABLE user_notes (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	author_user_id INTEGER, 
	note TEXT NOT NULL, 
	is_internal BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_user_notes PRIMARY KEY (id), 
	CONSTRAINT fk_user_notes_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_user_notes_author_user_id_users FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_user_notes_author_user_id ON user_notes (author_user_id);
CREATE INDEX ix_user_notes_created_at ON user_notes (created_at);
CREATE INDEX ix_user_notes_user_id ON user_notes (user_id);


CREATE TABLE user_tags (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, 
	added_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_user_tags PRIMARY KEY (id), 
	CONSTRAINT uq_user_tag UNIQUE (user_id, tag_id), 
	CONSTRAINT fk_user_tags_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_user_tags_tag_id_crm_tags FOREIGN KEY(tag_id) REFERENCES crm_tags (id) ON DELETE CASCADE, 
	CONSTRAINT fk_user_tags_added_by_user_id_users FOREIGN KEY(added_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_user_tags_added_by_user_id ON user_tags (added_by_user_id);
CREATE INDEX ix_user_tags_created_at ON user_tags (created_at);
CREATE INDEX ix_user_tags_tag_id ON user_tags (tag_id);
CREATE INDEX ix_user_tags_user_id ON user_tags (user_id);


CREATE TABLE automation_jobs (
	id SERIAL NOT NULL, 
	rule_id INTEGER, 
	user_id INTEGER, 
	trigger VARCHAR(80) NOT NULL, 
	dedupe_key VARCHAR(255) NOT NULL, 
	run_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	last_error TEXT, 
	payload_json JSON DEFAULT '{}' NOT NULL, 
	executed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_automation_jobs PRIMARY KEY (id), 
	CONSTRAINT uq_automation_jobs_dedupe_key UNIQUE (dedupe_key), 
	CONSTRAINT fk_automation_jobs_rule_id_automation_rules FOREIGN KEY(rule_id) REFERENCES automation_rules (id) ON DELETE SET NULL, 
	CONSTRAINT fk_automation_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_automation_jobs_created_at ON automation_jobs (created_at);
CREATE UNIQUE INDEX ix_automation_jobs_dedupe_key ON automation_jobs (dedupe_key);
CREATE INDEX ix_automation_jobs_executed_at ON automation_jobs (executed_at);
CREATE INDEX ix_automation_jobs_rule_id ON automation_jobs (rule_id);
CREATE INDEX ix_automation_jobs_run_at ON automation_jobs (run_at);
CREATE INDEX ix_automation_jobs_status ON automation_jobs (status);
CREATE INDEX ix_automation_jobs_trigger ON automation_jobs (trigger);
CREATE INDEX ix_automation_jobs_user_id ON automation_jobs (user_id);


CREATE TABLE broadcast_recipients (
	id SERIAL NOT NULL, 
	job_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	last_error VARCHAR(500), 
	sent_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_broadcast_recipients PRIMARY KEY (id), 
	CONSTRAINT uq_broadcast_recipient_job_user UNIQUE (job_id, user_id), 
	CONSTRAINT fk_broadcast_recipients_job_id_broadcast_jobs FOREIGN KEY(job_id) REFERENCES broadcast_jobs (id) ON DELETE CASCADE, 
	CONSTRAINT fk_broadcast_recipients_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_broadcast_recipients_created_at ON broadcast_recipients (created_at);
CREATE INDEX ix_broadcast_recipients_job_id ON broadcast_recipients (job_id);
CREATE INDEX ix_broadcast_recipients_user_id ON broadcast_recipients (user_id);


CREATE TABLE coupon_redemptions (
	id SERIAL NOT NULL, 
	coupon_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	payment_request_id INTEGER, 
	discount_amount NUMERIC(12, 2) NOT NULL, 
	redeemed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_coupon_redemptions PRIMARY KEY (id), 
	CONSTRAINT uq_coupon_redemption_payment UNIQUE (coupon_id, user_id, payment_request_id), 
	CONSTRAINT fk_coupon_redemptions_coupon_id_coupons FOREIGN KEY(coupon_id) REFERENCES coupons (id) ON DELETE CASCADE, 
	CONSTRAINT fk_coupon_redemptions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_coupon_redemptions_payment_request_id_payment_requests FOREIGN KEY(payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL
);

CREATE INDEX ix_coupon_redemptions_coupon_id ON coupon_redemptions (coupon_id);
CREATE INDEX ix_coupon_redemptions_created_at ON coupon_redemptions (created_at);
CREATE INDEX ix_coupon_redemptions_payment_request_id ON coupon_redemptions (payment_request_id);
CREATE INDEX ix_coupon_redemptions_redeemed_at ON coupon_redemptions (redeemed_at);
CREATE INDEX ix_coupon_redemptions_user_id ON coupon_redemptions (user_id);


CREATE TABLE external_payment_sessions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	payment_request_id INTEGER, 
	provider VARCHAR(80) NOT NULL, 
	provider_session_id VARCHAR(255) NOT NULL, 
	checkout_url TEXT NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	currency VARCHAR(8) NOT NULL, 
	status VARCHAR(32) DEFAULT 'CREATED' NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_external_payment_sessions PRIMARY KEY (id), 
	CONSTRAINT uq_external_payment_session UNIQUE (provider, provider_session_id), 
	CONSTRAINT fk_external_payment_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_external_payment_sessions_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_external_payment_sessions_payment_request_id_payment_46be FOREIGN KEY(payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL
);

CREATE INDEX ix_external_payment_sessions_created_at ON external_payment_sessions (created_at);
CREATE INDEX ix_external_payment_sessions_expires_at ON external_payment_sessions (expires_at);
CREATE INDEX ix_external_payment_sessions_payment_request_id ON external_payment_sessions (payment_request_id);
CREATE INDEX ix_external_payment_sessions_plan_id ON external_payment_sessions (plan_id);
CREATE INDEX ix_external_payment_sessions_provider ON external_payment_sessions (provider);
CREATE INDEX ix_external_payment_sessions_provider_session_id ON external_payment_sessions (provider_session_id);
CREATE INDEX ix_external_payment_sessions_status ON external_payment_sessions (status);
CREATE INDEX ix_external_payment_sessions_user_id ON external_payment_sessions (user_id);


CREATE TABLE funnel_events (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	event_name VARCHAR(80) NOT NULL, 
	source VARCHAR(120), 
	campaign VARCHAR(120), 
	plan_id INTEGER, 
	payment_request_id INTEGER, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_funnel_events PRIMARY KEY (id), 
	CONSTRAINT fk_funnel_events_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_funnel_events_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE SET NULL, 
	CONSTRAINT fk_funnel_events_payment_request_id_payment_requests FOREIGN KEY(payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL
);

CREATE INDEX ix_funnel_events_campaign ON funnel_events (campaign);
CREATE INDEX ix_funnel_events_created_at ON funnel_events (created_at);
CREATE INDEX ix_funnel_events_event_name ON funnel_events (event_name);
CREATE INDEX ix_funnel_events_occurred_at ON funnel_events (occurred_at);
CREATE INDEX ix_funnel_events_payment_request_id ON funnel_events (payment_request_id);
CREATE INDEX ix_funnel_events_plan_id ON funnel_events (plan_id);
CREATE INDEX ix_funnel_events_source ON funnel_events (source);
CREATE INDEX ix_funnel_events_user_id ON funnel_events (user_id);


CREATE TABLE inbox_messages (
	id SERIAL NOT NULL, 
	support_thread_id INTEGER, 
	user_id INTEGER NOT NULL, 
	admin_user_id INTEGER, 
	direction VARCHAR(16) NOT NULL, 
	telegram_chat_id BIGINT NOT NULL, 
	telegram_message_id INTEGER, 
	content_type VARCHAR(40) NOT NULL, 
	text TEXT, 
	file_id VARCHAR(255), 
	sent_at TIMESTAMP WITH TIME ZONE, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_inbox_messages PRIMARY KEY (id), 
	CONSTRAINT fk_inbox_messages_support_thread_id_support_threads FOREIGN KEY(support_thread_id) REFERENCES support_threads (id) ON DELETE CASCADE, 
	CONSTRAINT fk_inbox_messages_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_inbox_messages_admin_user_id_users FOREIGN KEY(admin_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_inbox_messages_admin_user_id ON inbox_messages (admin_user_id);
CREATE INDEX ix_inbox_messages_created_at ON inbox_messages (created_at);
CREATE INDEX ix_inbox_messages_direction ON inbox_messages (direction);
CREATE INDEX ix_inbox_messages_sent_at ON inbox_messages (sent_at);
CREATE INDEX ix_inbox_messages_support_thread_id ON inbox_messages (support_thread_id);
CREATE INDEX ix_inbox_messages_telegram_chat_id ON inbox_messages (telegram_chat_id);
CREATE INDEX ix_inbox_messages_telegram_message_id ON inbox_messages (telegram_message_id);
CREATE INDEX ix_inbox_messages_user_id ON inbox_messages (user_id);


CREATE TABLE memberships (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	payment_request_id INTEGER, 
	status VARCHAR(32) DEFAULT 'ACTIVE' NOT NULL, 
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	suspended_at TIMESTAMP WITH TIME ZONE, 
	refunded_at TIMESTAMP WITH TIME ZONE, 
	restored_at TIMESTAMP WITH TIME ZONE, 
	revoke_reason TEXT, 
	reminder_3d_sent BOOLEAN DEFAULT 'false' NOT NULL, 
	reminder_1d_sent BOOLEAN DEFAULT 'false' NOT NULL, 
	expired_notified BOOLEAN DEFAULT 'false' NOT NULL, 
	access_payload JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_memberships PRIMARY KEY (id), 
	CONSTRAINT fk_memberships_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_memberships_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_memberships_payment_request_id_payment_requests FOREIGN KEY(payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL
);

CREATE INDEX ix_memberships_created_at ON memberships (created_at);
CREATE INDEX ix_memberships_expires_at ON memberships (expires_at);
CREATE UNIQUE INDEX ix_memberships_payment_request_id ON memberships (payment_request_id);
CREATE INDEX ix_memberships_plan_id ON memberships (plan_id);
CREATE INDEX ix_memberships_status ON memberships (status);
CREATE INDEX ix_memberships_user_id ON memberships (user_id);


CREATE TABLE payment_receipts (
	id SERIAL NOT NULL, 
	payment_request_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	proof_kind VARCHAR(32) NOT NULL, 
	file_id VARCHAR(255) NOT NULL, 
	file_unique_id VARCHAR(255), 
	sha256 VARCHAR(64), 
	perceptual_hash VARCHAR(64), 
	duplicate_of_payment_request_id INTEGER, 
	status VARCHAR(32) DEFAULT 'CLEAN' NOT NULL, 
	warning_text TEXT, 
	warnings_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_payment_receipts PRIMARY KEY (id), 
	CONSTRAINT uq_payment_receipts_payment_request UNIQUE (payment_request_id), 
	CONSTRAINT fk_payment_receipts_payment_request_id_payment_requests FOREIGN KEY(payment_request_id) REFERENCES payment_requests (id) ON DELETE CASCADE, 
	CONSTRAINT fk_payment_receipts_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_payment_receipts_duplicate_of_payment_request_id_pay_4697 FOREIGN KEY(duplicate_of_payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL
);

CREATE INDEX ix_payment_receipts_created_at ON payment_receipts (created_at);
CREATE INDEX ix_payment_receipts_duplicate_of_payment_request_id ON payment_receipts (duplicate_of_payment_request_id);
CREATE INDEX ix_payment_receipts_file_unique_id ON payment_receipts (file_unique_id);
CREATE INDEX ix_payment_receipts_payment_request_id ON payment_receipts (payment_request_id);
CREATE INDEX ix_payment_receipts_perceptual_hash ON payment_receipts (perceptual_hash);
CREATE INDEX ix_payment_receipts_sha256 ON payment_receipts (sha256);
CREATE INDEX ix_payment_receipts_status ON payment_receipts (status);
CREATE INDEX ix_payment_receipts_user_id ON payment_receipts (user_id);


CREATE TABLE plan_channels (
	plan_id INTEGER NOT NULL, 
	channel_id INTEGER NOT NULL, 
	CONSTRAINT pk_plan_channels PRIMARY KEY (plan_id, channel_id), 
	CONSTRAINT fk_plan_channels_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	CONSTRAINT fk_plan_channels_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE CASCADE
);


CREATE TABLE plan_groups (
	plan_id INTEGER NOT NULL, 
	group_id INTEGER NOT NULL, 
	CONSTRAINT pk_plan_groups PRIMARY KEY (plan_id, group_id), 
	CONSTRAINT fk_plan_groups_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	CONSTRAINT fk_plan_groups_group_id_groups FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE
);


CREATE TABLE referrals (
	id SERIAL NOT NULL, 
	referrer_user_id INTEGER NOT NULL, 
	referred_user_id INTEGER NOT NULL, 
	first_payment_request_id INTEGER, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	revenue NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
	reward_granted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_referrals PRIMARY KEY (id), 
	CONSTRAINT uq_referral_pair UNIQUE (referrer_user_id, referred_user_id), 
	CONSTRAINT fk_referrals_referrer_user_id_users FOREIGN KEY(referrer_user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_referrals_referred_user_id_users FOREIGN KEY(referred_user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_referrals_first_payment_request_id_payment_requests FOREIGN KEY(first_payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL
);

CREATE INDEX ix_referrals_created_at ON referrals (created_at);
CREATE INDEX ix_referrals_first_payment_request_id ON referrals (first_payment_request_id);
CREATE INDEX ix_referrals_referred_user_id ON referrals (referred_user_id);
CREATE INDEX ix_referrals_referrer_user_id ON referrals (referrer_user_id);
CREATE INDEX ix_referrals_reward_granted_at ON referrals (reward_granted_at);
CREATE INDEX ix_referrals_status ON referrals (status);


CREATE TABLE support_reply_maps (
	id SERIAL NOT NULL, 
	thread_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	admin_chat_id BIGINT NOT NULL, 
	admin_message_id INTEGER NOT NULL, 
	user_message_id INTEGER, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_support_reply_maps PRIMARY KEY (id), 
	CONSTRAINT uq_support_reply_admin_message UNIQUE (admin_chat_id, admin_message_id), 
	CONSTRAINT fk_support_reply_maps_thread_id_support_threads FOREIGN KEY(thread_id) REFERENCES support_threads (id) ON DELETE CASCADE, 
	CONSTRAINT fk_support_reply_maps_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_support_reply_maps_admin_chat_id ON support_reply_maps (admin_chat_id);
CREATE INDEX ix_support_reply_maps_admin_message_id ON support_reply_maps (admin_message_id);
CREATE INDEX ix_support_reply_maps_created_at ON support_reply_maps (created_at);
CREATE INDEX ix_support_reply_maps_thread_id ON support_reply_maps (thread_id);
CREATE INDEX ix_support_reply_maps_user_id ON support_reply_maps (user_id);


CREATE TABLE telegram_stars_payments (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	payment_request_id INTEGER, 
	invoice_payload VARCHAR(128) NOT NULL, 
	telegram_payment_charge_id VARCHAR(255), 
	provider_payment_charge_id VARCHAR(255), 
	status VARCHAR(32) DEFAULT 'INVOICE_CREATED' NOT NULL, 
	amount_stars INTEGER NOT NULL, 
	currency VARCHAR(8) DEFAULT 'XTR' NOT NULL, 
	subscription_period INTEGER, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	refunded_at TIMESTAMP WITH TIME ZONE, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_telegram_stars_payments PRIMARY KEY (id), 
	CONSTRAINT uq_stars_invoice_payload UNIQUE (invoice_payload), 
	CONSTRAINT uq_stars_charge_id UNIQUE (telegram_payment_charge_id), 
	CONSTRAINT fk_telegram_stars_payments_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_telegram_stars_payments_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_telegram_stars_payments_payment_request_id_payment_requests FOREIGN KEY(payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL
);

CREATE INDEX ix_telegram_stars_payments_created_at ON telegram_stars_payments (created_at);
CREATE INDEX ix_telegram_stars_payments_invoice_payload ON telegram_stars_payments (invoice_payload);
CREATE INDEX ix_telegram_stars_payments_paid_at ON telegram_stars_payments (paid_at);
CREATE INDEX ix_telegram_stars_payments_payment_request_id ON telegram_stars_payments (payment_request_id);
CREATE INDEX ix_telegram_stars_payments_plan_id ON telegram_stars_payments (plan_id);
CREATE INDEX ix_telegram_stars_payments_provider_payment_charge_id ON telegram_stars_payments (provider_payment_charge_id);
CREATE INDEX ix_telegram_stars_payments_refunded_at ON telegram_stars_payments (refunded_at);
CREATE INDEX ix_telegram_stars_payments_status ON telegram_stars_payments (status);
CREATE INDEX ix_telegram_stars_payments_telegram_payment_charge_id ON telegram_stars_payments (telegram_payment_charge_id);
CREATE INDEX ix_telegram_stars_payments_user_id ON telegram_stars_payments (user_id);


CREATE TABLE generated_invite_links (
	id SERIAL NOT NULL, 
	creator_user_id INTEGER, 
	plan_id INTEGER NOT NULL, 
	membership_id INTEGER, 
	payment_request_id INTEGER, 
	approved_by_user_id INTEGER, 
	channel_id INTEGER, 
	group_id INTEGER, 
	telegram_chat_id BIGINT NOT NULL, 
	chat_title VARCHAR(255) NOT NULL, 
	invite_link TEXT NOT NULL, 
	expire_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	is_used BOOLEAN DEFAULT 'false' NOT NULL, 
	used_by_user_id INTEGER, 
	used_at TIMESTAMP WITH TIME ZONE, 
	joined_at TIMESTAMP WITH TIME ZONE, 
	join_confirmed BOOLEAN DEFAULT 'false' NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	revoked_reason VARCHAR(120), 
	last_reissued_at TIMESTAMP WITH TIME ZONE, 
	reissue_count INTEGER DEFAULT '0' NOT NULL, 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_generated_invite_links PRIMARY KEY (id), 
	CONSTRAINT fk_generated_invite_links_creator_user_id_users FOREIGN KEY(creator_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_generated_invite_links_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	CONSTRAINT fk_generated_invite_links_membership_id_memberships FOREIGN KEY(membership_id) REFERENCES memberships (id) ON DELETE SET NULL, 
	CONSTRAINT fk_generated_invite_links_payment_request_id_payment_requests FOREIGN KEY(payment_request_id) REFERENCES payment_requests (id) ON DELETE SET NULL, 
	CONSTRAINT fk_generated_invite_links_approved_by_user_id_users FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_generated_invite_links_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL, 
	CONSTRAINT fk_generated_invite_links_group_id_groups FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE SET NULL, 
	CONSTRAINT uq_generated_invite_links_invite_link UNIQUE (invite_link), 
	CONSTRAINT fk_generated_invite_links_used_by_user_id_users FOREIGN KEY(used_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_generated_invite_links_approved_by_user_id ON generated_invite_links (approved_by_user_id);
CREATE INDEX ix_generated_invite_links_channel_id ON generated_invite_links (channel_id);
CREATE INDEX ix_generated_invite_links_created_at ON generated_invite_links (created_at);
CREATE INDEX ix_generated_invite_links_creator_user_id ON generated_invite_links (creator_user_id);
CREATE INDEX ix_generated_invite_links_expire_at ON generated_invite_links (expire_at);
CREATE INDEX ix_generated_invite_links_group_id ON generated_invite_links (group_id);
CREATE INDEX ix_generated_invite_links_is_used ON generated_invite_links (is_used);
CREATE INDEX ix_generated_invite_links_join_confirmed ON generated_invite_links (join_confirmed);
CREATE INDEX ix_generated_invite_links_joined_at ON generated_invite_links (joined_at);
CREATE INDEX ix_generated_invite_links_membership_id ON generated_invite_links (membership_id);
CREATE INDEX ix_generated_invite_links_payment_request_id ON generated_invite_links (payment_request_id);
CREATE INDEX ix_generated_invite_links_plan_id ON generated_invite_links (plan_id);
CREATE INDEX ix_generated_invite_links_revoked_at ON generated_invite_links (revoked_at);
CREATE INDEX ix_generated_invite_links_telegram_chat_id ON generated_invite_links (telegram_chat_id);
CREATE INDEX ix_generated_invite_links_used_by_user_id ON generated_invite_links (used_by_user_id);


CREATE TABLE notifications (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	membership_id INTEGER, 
	kind VARCHAR(32) NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	scheduled_for TIMESTAMP WITH TIME ZONE, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	payload JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_notifications PRIMARY KEY (id), 
	CONSTRAINT fk_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_notifications_membership_id_memberships FOREIGN KEY(membership_id) REFERENCES memberships (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_created_at ON notifications (created_at);
CREATE INDEX ix_notifications_kind ON notifications (kind);
CREATE INDEX ix_notifications_membership_id ON notifications (membership_id);
CREATE INDEX ix_notifications_scheduled_for ON notifications (scheduled_for);
CREATE INDEX ix_notifications_status ON notifications (status);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);


CREATE TABLE membership_access_events (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	membership_id INTEGER, 
	plan_id INTEGER, 
	generated_invite_link_id INTEGER, 
	event_kind VARCHAR(32) NOT NULL, 
	telegram_chat_id BIGINT NOT NULL, 
	chat_title VARCHAR(255) NOT NULL, 
	channel_id INTEGER, 
	group_id INTEGER, 
	approved_by_user_id INTEGER, 
	join_confirmed BOOLEAN DEFAULT 'false' NOT NULL, 
	event_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	kick_result VARCHAR(80), 
	metadata_json JSON DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_membership_access_events PRIMARY KEY (id), 
	CONSTRAINT fk_membership_access_events_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_membership_access_events_membership_id_memberships FOREIGN KEY(membership_id) REFERENCES memberships (id) ON DELETE SET NULL, 
	CONSTRAINT fk_membership_access_events_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE SET NULL, 
	CONSTRAINT fk_membership_access_events_generated_invite_link_id_ge_4c38 FOREIGN KEY(generated_invite_link_id) REFERENCES generated_invite_links (id) ON DELETE SET NULL, 
	CONSTRAINT fk_membership_access_events_channel_id_channels FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE SET NULL, 
	CONSTRAINT fk_membership_access_events_group_id_groups FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE SET NULL, 
	CONSTRAINT fk_membership_access_events_approved_by_user_id_users FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_membership_access_events_approved_by_user_id ON membership_access_events (approved_by_user_id);
CREATE INDEX ix_membership_access_events_channel_id ON membership_access_events (channel_id);
CREATE INDEX ix_membership_access_events_created_at ON membership_access_events (created_at);
CREATE INDEX ix_membership_access_events_event_at ON membership_access_events (event_at);
CREATE INDEX ix_membership_access_events_event_kind ON membership_access_events (event_kind);
CREATE INDEX ix_membership_access_events_generated_invite_link_id ON membership_access_events (generated_invite_link_id);
CREATE INDEX ix_membership_access_events_group_id ON membership_access_events (group_id);
CREATE INDEX ix_membership_access_events_membership_id ON membership_access_events (membership_id);
CREATE INDEX ix_membership_access_events_plan_id ON membership_access_events (plan_id);
CREATE INDEX ix_membership_access_events_telegram_chat_id ON membership_access_events (telegram_chat_id);
CREATE INDEX ix_membership_access_events_user_id ON membership_access_events (user_id);
