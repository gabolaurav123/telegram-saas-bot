from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentProvider
from app.models.payment_method import PaymentMethod


DEFAULT_METHODS = [
    {
        "name": "PayPal",
        "provider": PaymentProvider.PAYPAL,
        "instructions": (
            "Envia el pago por PayPal a tu correo configurado y adjunta la captura "
            "o recibo de la operacion."
        ),
        "sort_order": 10,
    },
    {
        "name": "Transferencia bancaria",
        "provider": PaymentProvider.BANK_TRANSFER,
        "instructions": (
            "Realiza la transferencia bancaria a la cuenta configurada por el equipo "
            "y envia el comprobante en esta conversacion."
        ),
        "sort_order": 20,
    },
]


async def ensure_default_payment_methods(session: AsyncSession) -> None:
    for payload in DEFAULT_METHODS:
        existing = await session.scalar(
            select(PaymentMethod).where(PaymentMethod.name == payload["name"])
        )
        if existing is None:
            session.add(PaymentMethod(**payload))


async def list_payment_methods(
    session: AsyncSession,
    *,
    only_active: bool = False,
) -> list[PaymentMethod]:
    stmt = select(PaymentMethod).order_by(PaymentMethod.sort_order, PaymentMethod.name)
    if only_active:
        stmt = stmt.where(PaymentMethod.is_active.is_(True))
    result = await session.scalars(stmt)
    return list(result)


async def get_payment_method(session: AsyncSession, method_id: int) -> PaymentMethod | None:
    return await session.get(PaymentMethod, method_id)


async def create_payment_method(
    session: AsyncSession,
    *,
    name: str,
    provider: PaymentProvider,
    instructions: str,
    account_data: dict | None = None,
) -> PaymentMethod:
    method = PaymentMethod(
        name=name.strip(),
        provider=provider,
        instructions=instructions.strip(),
        account_data=account_data or {},
    )
    session.add(method)
    await session.flush()
    return method


async def toggle_payment_method(session: AsyncSession, method_id: int) -> PaymentMethod:
    method = await session.get(PaymentMethod, method_id)
    if method is None:
        raise ValueError("Metodo de pago no encontrado.")
    method.is_active = not method.is_active
    return method

