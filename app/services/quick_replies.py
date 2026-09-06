from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LogAction
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.services.logs import log_event


DEFAULT_QUICK_REPLIES = [
    {
        "command": "/recibo",
        "title": "Solicitar comprobante",
        "body": "Necesitamos que envies una imagen o documento del comprobante dentro del flujo de compra para poder revisar tu pago.",
    },
    {
        "command": "/revision",
        "title": "Pago en revision",
        "body": "Tu pago esta en revision. Te notificaremos apenas sea aprobado o rechazado por un administrador.",
    },
    {
        "command": "/renovar",
        "title": "Renovacion manual",
        "body": "Para renovar, presiona Renovar ahora o entra a /plans, elige tu plan y envia un nuevo comprobante. No hay renovaciones automaticas.",
    },
]


async def ensure_default_quick_replies(session: AsyncSession) -> None:
    for payload in DEFAULT_QUICK_REPLIES:
        command = normalize_quick_reply_command(payload["command"])
        if await session.scalar(select(QuickReply.id).where(QuickReply.command == command)):
            continue
        session.add(
            QuickReply(
                command=command,
                title=payload["title"],
                body=payload["body"],
            )
        )


async def list_quick_replies(session: AsyncSession, *, only_active: bool = True) -> list[QuickReply]:
    stmt = select(QuickReply).order_by(QuickReply.sort_order, QuickReply.title)
    if only_active:
        stmt = stmt.where(QuickReply.is_active.is_(True))
    result = await session.scalars(stmt)
    return list(result)


async def get_quick_reply_by_command(session: AsyncSession, command: str) -> QuickReply | None:
    normalized = normalize_quick_reply_command(command)
    if not normalized:
        return None
    return await session.scalar(
        select(QuickReply).where(
            QuickReply.command == normalized,
            QuickReply.is_active.is_(True),
        )
    )


async def create_quick_reply(
    session: AsyncSession,
    *,
    command: str,
    title: str,
    body: str,
    actor: User,
) -> QuickReply:
    normalized = normalize_quick_reply_command(command)
    if not normalized:
        raise ValueError("Comando invalido.")
    existing = await session.scalar(select(QuickReply).where(QuickReply.command == normalized))
    if existing:
        raise ValueError("Ya existe una respuesta rapida con ese comando.")
    reply = QuickReply(
        command=normalized,
        title=title.strip()[:120],
        body=body.strip(),
        created_by_user_id=actor.id,
    )
    session.add(reply)
    await session.flush()
    await log_event(
        session,
        LogAction.QUICK_REPLY_CREATED,
        f"Quick reply creada: {normalized}",
        actor_user_id=actor.id,
        details={"quick_reply_id": reply.id, "command": normalized},
    )
    return reply


def normalize_quick_reply_command(command: str) -> str:
    value = command.strip().lower()
    if not value:
        return ""
    if not value.startswith("/"):
        value = "/" + value
    return value[:40]
