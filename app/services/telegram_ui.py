from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    MenuButtonCommands,
    MenuButtonWebApp,
    WebAppInfo,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.enums import Role
from app.services.admins import list_admins, permissions_for


logger = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Abrir el menu principal"),
    BotCommand(command="plans", description="Ver y comprar membresias"),
    BotCommand(command="profile", description="Consultar mi membresia"),
    BotCommand(command="support", description="Hablar con soporte"),
    BotCommand(command="language", description="Cambiar idioma"),
    BotCommand(command="help", description="Ayuda y preguntas frecuentes"),
    BotCommand(command="id", description="Ver mi Telegram ID"),
]

async def configure_telegram_ui(bot: Bot, session: AsyncSession, settings: Settings) -> None:
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    if settings.mini_app_client_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Abrir membresias",
                web_app=WebAppInfo(url=settings.mini_app_client_url),
            )
        )
    else:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    admins = await list_admins(session)
    admin_roles = {admin.telegram_id: admin.role for admin in admins}
    admin_roles.update({telegram_id: Role.OWNER for telegram_id in settings.owner_ids})
    for telegram_id, role in admin_roles.items():
        try:
            await bot.set_my_commands(_commands_for(role), scope=BotCommandScopeChat(chat_id=telegram_id))
            if settings.mini_app_admin_url and permissions_for(role).view_stats:
                await bot.set_chat_menu_button(
                    chat_id=telegram_id,
                    menu_button=MenuButtonWebApp(
                        text="Panel administrativo",
                        web_app=WebAppInfo(url=settings.mini_app_admin_url),
                    ),
                )
            elif settings.mini_app_client_url:
                await bot.set_chat_menu_button(
                    chat_id=telegram_id,
                    menu_button=MenuButtonWebApp(
                        text="Abrir membresias",
                        web_app=WebAppInfo(url=settings.mini_app_client_url),
                    ),
                )
        except TelegramAPIError as exc:
            logger.warning("Could not configure Telegram UI for admin %s: %s", telegram_id, exc)

    logger.info(
        "Telegram commands and menu buttons configured | admins=%s client_mini_app=%s admin_mini_app=%s",
        len(admin_roles),
        bool(settings.mini_app_client_url),
        bool(settings.mini_app_admin_url),
    )


def _commands_for(role: Role) -> list[BotCommand]:
    permissions = permissions_for(role)
    commands = [*USER_COMMANDS, BotCommand(command="settings", description="Abrir panel administrativo")]
    if permissions.view_stats:
        commands.extend(
            [
                BotCommand(command="stats", description="Ver estadisticas"),
                BotCommand(command="exportclients", description="Exportar clientes"),
                BotCommand(command="userinfo", description="Consultar un cliente"),
            ]
        )
    if permissions.broadcast:
        commands.append(BotCommand(command="broadcast", description="Crear una difusion"))
    if permissions.manage_catalog:
        commands.extend(
            [
                BotCommand(command="addmember", description="Generar enlaces de acceso"),
                BotCommand(command="listlinks", description="Listar enlaces generados"),
            ]
        )
    if permissions.support:
        commands.append(BotCommand(command="inbox", description="Abrir soporte"))
    return commands
