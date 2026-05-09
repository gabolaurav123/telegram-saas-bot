from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.payment_method import PaymentMethod
from app.models.plan import Plan
from app.utils.text import money


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ver planes", callback_data="main:plans")
    builder.button(text="Comprar membresia", callback_data="main:plans")
    builder.button(text="Estado de membresia", callback_data="main:membership")
    builder.button(text="Soporte", callback_data="main:support")
    builder.button(text="FAQ", callback_data="main:faq")
    builder.button(text="Renovar membresia", callback_data="main:plans")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def plans_keyboard(plans: list[Plan]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        label = f"{plan.name} - {money(plan.price, plan.currency)}"
        builder.button(text=label, callback_data=f"plan:view:{plan.id}")
    builder.button(text="Volver", callback_data="main:menu")
    builder.adjust(1)
    return builder.as_markup()


def plan_detail_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Comprar", callback_data=f"plan:buy:{plan_id}")
    builder.button(text="Volver a planes", callback_data="main:plans")
    builder.adjust(1)
    return builder.as_markup()


def payment_methods_keyboard(plan_id: int, methods: list[PaymentMethod]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for method in methods:
        builder.button(text=method.name, callback_data=f"paymethod:{plan_id}:{method.id}")
    builder.button(text="Volver", callback_data=f"plan:view:{plan_id}")
    builder.adjust(1)
    return builder.as_markup()


def cancel_purchase_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Cancelar", callback_data="purchase:cancel")
    return builder.as_markup()

