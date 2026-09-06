from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.payment_method import PaymentMethod
from app.models.plan import Plan
from app.utils.i18n import LANGUAGE_LABELS, t
from app.utils.text import money


def main_menu_keyboard(mini_app_url: str | None = None, language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(language, "btn.buy_membership"), callback_data="main:plans")
    builder.button(text=t(language, "btn.view_plans"), callback_data="main:plans")
    builder.button(text=t(language, "btn.membership_status"), callback_data="main:membership")
    builder.button(text=t(language, "btn.renew"), callback_data="main:plans")
    builder.button(text=t(language, "btn.support"), callback_data="main:support")
    builder.button(text=t(language, "btn.faq"), callback_data="main:faq")
    builder.button(text=t(language, "btn.language"), callback_data="lang:select")
    if mini_app_url:
        builder.button(text=t(language, "btn.mini_app"), web_app=WebAppInfo(url=mini_app_url))
    builder.adjust(1, 2, 2, 2, 1)
    return builder.as_markup()


def plans_keyboard(plans: list[Plan], language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        label = f"{plan.name} - {money(plan.price, plan.currency)}"
        builder.button(text=label, callback_data=f"plan:view:{plan.id}")
    builder.button(text=t(language, "btn.back"), callback_data="main:menu")
    builder.adjust(1)
    return builder.as_markup()


def plan_detail_keyboard(plan_id: int, language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(language, "btn.buy"), callback_data=f"plan:buy:{plan_id}")
    builder.button(text=t(language, "btn.back_to_plans"), callback_data="main:plans")
    builder.adjust(1)
    return builder.as_markup()


def payment_methods_keyboard(plan_id: int, methods: list[PaymentMethod], language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for method in methods:
        builder.button(text=method.name, callback_data=f"paymethod:{plan_id}:{method.id}")
    builder.button(text=t(language, "btn.back"), callback_data=f"plan:view:{plan_id}")
    builder.adjust(1)
    return builder.as_markup()


def renewal_keyboard(membership_id: int, language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(language, "btn.renew_now"), callback_data=f"renew:membership:{membership_id}")
    builder.button(text=t(language, "btn.view_plans"), callback_data="main:plans")
    builder.adjust(1)
    return builder.as_markup()


def renewal_payment_methods_keyboard(
    *,
    membership_id: int,
    plan_id: int,
    methods: list[PaymentMethod],
    language: str = "es",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for method in methods:
        builder.button(
            text=method.name,
            callback_data=f"renewmethod:{membership_id}:{plan_id}:{method.id}",
        )
    builder.button(text=t(language, "btn.cancel"), callback_data="main:menu")
    builder.adjust(1)
    return builder.as_markup()


def cancel_purchase_keyboard(language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(language, "btn.cancel"), callback_data="purchase:cancel")
    return builder.as_markup()


def language_keyboard(
    current_language: str,
    supported_languages: list[str],
    *,
    back_callback: str = "main:menu",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in supported_languages:
        normalized = code.lower().strip()
        label = LANGUAGE_LABELS.get(normalized, normalized.upper())
        prefix = "ON " if normalized == current_language else ""
        builder.button(text=f"{prefix}{label}", callback_data=f"lang:set:{normalized}")
    builder.button(text=t(current_language, "btn.back"), callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def support_keyboard(language: str = "es") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(language, "btn.buy_membership"), callback_data="main:plans")
    builder.button(text=t(language, "btn.back"), callback_data="main:menu")
    builder.adjust(1)
    return builder.as_markup()
