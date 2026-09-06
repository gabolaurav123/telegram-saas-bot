from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DeliveryStatus, LogAction
from app.models.messaging import OutboundMessage
from app.models.user import User
from app.services.logs import log_event
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class MessagingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def send_text_to_user(
        self,
        *,
        bot: Bot,
        target: User,
        text: str,
        actor: User | None = None,
        source: str = "ADMIN_DIRECT",
        metadata: dict | None = None,
    ) -> OutboundMessage:
        chat_id = target.chat_id or target.telegram_id
        record = OutboundMessage(
            target_user_id=target.id,
            actor_user_id=actor.id if actor else None,
            telegram_chat_id=chat_id,
            source=source,
            content_type="text",
            text=text,
            metadata_json=metadata or {},
        )
        self.session.add(record)
        await self.session.flush()
        try:
            sent = await bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
        except TelegramForbiddenError as exc:
            record.status = DeliveryStatus.BLOCKED
            record.failed_at = utc_now()
            record.error = str(exc)
            target.delivery_status = DeliveryStatus.BLOCKED.value
            target.blocked_at = utc_now()
            await log_event(
                self.session,
                LogAction.DIRECT_MESSAGE_FAILED,
                f"Mensaje directo bloqueado por usuario {target.telegram_id}",
                actor_user_id=actor.id if actor else None,
                target_user_id=target.id,
                details={"error": str(exc), "source": source},
            )
            return record
        except TelegramAPIError as exc:
            logger.exception("Could not send direct message to user %s", target.telegram_id)
            record.status = DeliveryStatus.FAILED
            record.failed_at = utc_now()
            record.error = str(exc)
            target.delivery_status = DeliveryStatus.FAILED.value
            await log_event(
                self.session,
                LogAction.DIRECT_MESSAGE_FAILED,
                f"Mensaje directo fallido para {target.telegram_id}",
                actor_user_id=actor.id if actor else None,
                target_user_id=target.id,
                details={"error": str(exc), "source": source},
            )
            return record

        record.status = DeliveryStatus.SENT
        record.telegram_message_id = sent.message_id
        record.sent_at = utc_now()
        target.delivery_status = DeliveryStatus.SENT.value
        target.last_contacted_at = utc_now()
        await log_event(
            self.session,
            LogAction.DIRECT_MESSAGE_SENT,
            f"Mensaje directo enviado a {target.telegram_id}",
            actor_user_id=actor.id if actor else None,
            target_user_id=target.id,
            details={"outbound_message_id": record.id, "source": source},
        )
        return record

    async def copy_admin_reply_to_user(
        self,
        *,
        bot: Bot,
        admin_message: Message,
        target: User,
        actor: User,
        source: str = "SUPPORT_REPLY",
        metadata: dict | None = None,
    ) -> OutboundMessage:
        chat_id = target.chat_id or target.telegram_id
        record = OutboundMessage(
            target_user_id=target.id,
            actor_user_id=actor.id,
            telegram_chat_id=chat_id,
            source=source,
            content_type=admin_message.content_type,
            text=admin_message.text or admin_message.caption,
            metadata_json=metadata or {},
        )
        self.session.add(record)
        await self.session.flush()
        try:
            copied = await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=admin_message.chat.id,
                message_id=admin_message.message_id,
            )
        except TelegramForbiddenError as exc:
            record.status = DeliveryStatus.BLOCKED
            record.failed_at = utc_now()
            record.error = str(exc)
            target.delivery_status = DeliveryStatus.BLOCKED.value
            target.blocked_at = utc_now()
            await log_event(
                self.session,
                LogAction.DIRECT_MESSAGE_FAILED,
                f"Respuesta soporte bloqueada por usuario {target.telegram_id}",
                actor_user_id=actor.id,
                target_user_id=target.id,
                details={"error": str(exc), "source": source},
            )
            return record
        except TelegramAPIError as exc:
            record.status = DeliveryStatus.FAILED
            record.failed_at = utc_now()
            record.error = str(exc)
            target.delivery_status = DeliveryStatus.FAILED.value
            await log_event(
                self.session,
                LogAction.DIRECT_MESSAGE_FAILED,
                f"Respuesta soporte fallida para {target.telegram_id}",
                actor_user_id=actor.id,
                target_user_id=target.id,
                details={"error": str(exc), "source": source},
            )
            return record

        record.status = DeliveryStatus.SENT
        record.telegram_message_id = copied.message_id
        record.sent_at = utc_now()
        target.delivery_status = DeliveryStatus.SENT.value
        target.last_contacted_at = utc_now()
        await log_event(
            self.session,
            LogAction.DIRECT_MESSAGE_SENT,
            f"Respuesta soporte enviada a {target.telegram_id}",
            actor_user_id=actor.id,
            target_user_id=target.id,
            details={"outbound_message_id": record.id, "source": source},
        )
        return record
