from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.filters.support_reply import SupportReplyTargetFilter
from app.handlers import support as support_handlers
from app.keyboards.admin import admin_menu_keyboard
from app.models.enums import DeliveryStatus, Role


class AdminNavigationTests(unittest.TestCase):
    def test_owner_settings_exposes_access_links_directly(self) -> None:
        keyboard = admin_menu_keyboard(Role.OWNER, "https://example.com/admin", "es")
        callbacks = {
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        }

        self.assertIn("adm:links", callbacks)

    def test_moderator_does_not_receive_access_link_controls(self) -> None:
        keyboard = admin_menu_keyboard(Role.MODERATOR, None, "es")
        callbacks = {
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data
        }

        self.assertNotIn("adm:links", callbacks)


class SupportReplyFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_mapped_bot_replies_match(self) -> None:
        session = SimpleNamespace(scalar=AsyncMock(return_value=42))
        message = SimpleNamespace(
            chat=SimpleNamespace(id=100),
            reply_to_message=SimpleNamespace(message_id=200),
        )

        matched = await SupportReplyTargetFilter()(message, session)

        self.assertTrue(matched)
        session.scalar.assert_awaited_once()

    async def test_normal_message_does_not_query_mappings(self) -> None:
        session = SimpleNamespace(scalar=AsyncMock())
        message = SimpleNamespace(chat=SimpleNamespace(id=100), reply_to_message=None)

        matched = await SupportReplyTargetFilter()(message, session)

        self.assertFalse(matched)
        session.scalar.assert_not_awaited()


class SupportReplyHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_plain_reply_bypasses_stale_admin_form_and_clears_state(self) -> None:
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=1),
            text="Hola, ya revisamos tu solicitud.",
            bot=object(),
            reply=AsyncMock(),
        )
        state = SimpleNamespace(clear=AsyncMock())
        session = object()
        settings = object()
        outbound = SimpleNamespace(status=DeliveryStatus.SENT)

        with (
            patch.object(support_handlers, "get_role", AsyncMock(return_value=Role.OWNER)),
            patch.object(
                support_handlers,
                "get_or_create_user",
                AsyncMock(return_value=SimpleNamespace(id=10)),
            ),
            patch.object(
                support_handlers,
                "get_quick_reply_by_command",
                AsyncMock(),
            ) as quick_reply,
            patch.object(
                support_handlers,
                "bridge_admin_reply",
                AsyncMock(return_value=outbound),
            ) as bridge,
        ):
            await support_handlers.admin_reply_bridge(message, state, session, settings)

        quick_reply.assert_not_awaited()
        bridge.assert_awaited_once()
        state.clear.assert_awaited_once()
        message.reply.assert_awaited_once_with("Respuesta enviada al usuario.")


if __name__ == "__main__":
    unittest.main()
