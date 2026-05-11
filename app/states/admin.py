from aiogram.fsm.state import State, StatesGroup


class AdminPlanStates(StatesGroup):
    waiting_create_payload = State()
    waiting_message_method = State()
    waiting_message_template = State()
    waiting_link_channel = State()
    waiting_link_group = State()


class AdminPaymentMethodStates(StatesGroup):
    waiting_create_payload = State()


class AdminChatStates(StatesGroup):
    waiting_manual_chat = State()


class AdminUserStates(StatesGroup):
    waiting_add_admin = State()
    waiting_remove_admin = State()


class AdminPaymentReviewStates(StatesGroup):
    waiting_rejection_reason = State()


class AddMemberStates(StatesGroup):
    waiting_amount = State()


class BroadcastStates(StatesGroup):
    waiting_content = State()


class ExportClientStates(StatesGroup):
    waiting_date_range = State()
