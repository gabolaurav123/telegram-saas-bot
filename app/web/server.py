from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiohttp import web
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.keyboards.user import payment_methods_keyboard, renewal_payment_methods_keyboard
from app.models.enums import MembershipStatus, PaymentRequestStatus, Role
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.services.admins import get_role, permissions_for
from app.services.currency import plan_price_to_stars
from app.services.locks import payment_lock
from app.services.memberships import get_active_memberships
from app.services.notifications import send_access_links, send_payment_rejected
from app.services.payment_service import PaymentService
from app.services.payment_methods import list_payment_methods
from app.services.payments import (
    get_payment_request,
    get_payment_request_for_update,
    list_pending_payment_requests,
)
from app.services.plans import get_plan, list_plans, toggle_plan_payment_method
from app.services.runtime_settings import update_runtime_setting
from app.services.stats import get_overview
from app.services.support import forward_webapp_text_to_admins
from app.services.users import get_user_by_telegram_id, set_preferred_language
from app.utils.i18n import LANGUAGE_LABELS, t
from app.utils.telegram_webapp import parse_webapp_user
from app.utils.text import h, money
from app.utils.time import human_datetime, remaining_days


logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).with_name("static")

BOT_KEY: web.AppKey[Bot] = web.AppKey("bot", Bot)
SETTINGS_KEY: web.AppKey[Settings] = web.AppKey("settings", Settings)
SESSION_FACTORY_KEY: web.AppKey[async_sessionmaker[AsyncSession]] = web.AppKey(
    "session_factory",
    async_sessionmaker,
)
BOT_USERNAME_KEY: web.AppKey[str] = web.AppKey("bot_username", str)


@dataclass(frozen=True)
class WebServer:
    runner: web.AppRunner
    host: str
    port: int

    async def stop(self) -> None:
        await self.runner.cleanup()


@web.middleware
async def error_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
    except web.HTTPException:
        raise
    except ValueError as exc:
        response = web.json_response({"ok": False, "error": str(exc)}, status=400)
    except PermissionError as exc:
        response = web.json_response({"ok": False, "error": str(exc)}, status=403)
    except Exception:
        logger.exception("Unhandled Mini App request error | path=%s", request.path)
        response = web.json_response(
            {"ok": False, "error": "No se pudo completar la operacion."},
            status=500,
        )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://telegram.org; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
        "connect-src 'self'; frame-src blob:; object-src 'none'; "
        "frame-ancestors https://web.telegram.org https://*.telegram.org"
    )
    return response


async def start_web_server(
    *,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    bot_username: str,
) -> WebServer:
    application = create_web_application(
        bot=bot,
        settings=settings,
        session_factory=session_factory,
        bot_username=bot_username,
    )
    runner = web.AppRunner(application, access_log=logger)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.web_host, port=settings.port)
    await site.start()
    logger.info("Mini App HTTP server started | host=%s port=%s", settings.web_host, settings.port)
    return WebServer(runner=runner, host=settings.web_host, port=settings.port)


def create_web_application(
    *,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    bot_username: str,
) -> web.Application:
    application = web.Application(
        middlewares=[error_middleware],
        client_max_size=settings.receipt_max_download_mb * 1024 * 1024,
    )
    application[BOT_KEY] = bot
    application[SETTINGS_KEY] = settings
    application[SESSION_FACTORY_KEY] = session_factory
    application[BOT_USERNAME_KEY] = bot_username
    application.router.add_get("/", root_redirect)
    application.router.add_get("/health", health)
    application.router.add_get("/miniapp", client_page)
    application.router.add_get("/admin", admin_page)
    application.router.add_get("/api/client/dashboard", client_dashboard)
    application.router.add_post("/api/client/language", client_language)
    application.router.add_post("/api/client/support", client_support)
    application.router.add_post("/api/client/plans/{plan_id:\\d+}/buy", client_buy_plan)
    application.router.add_post(
        "/api/client/memberships/{membership_id:\\d+}/renew",
        client_renew_membership,
    )
    application.router.add_get("/api/admin/dashboard", admin_dashboard)
    application.router.add_post(
        "/api/admin/payments/{request_id:\\d+}/approve",
        admin_approve_payment,
    )
    application.router.add_get(
        "/api/admin/payments/{request_id:\\d+}/proof",
        admin_payment_proof,
    )
    application.router.add_post(
        "/api/admin/payments/{request_id:\\d+}/reject",
        admin_reject_payment,
    )
    application.router.add_post(
        "/api/admin/plans/{plan_id:\\d+}/methods/{method_id:\\d+}/toggle",
        admin_toggle_plan_method,
    )
    application.router.add_post("/api/admin/settings/{key}", admin_update_setting)
    application.router.add_static("/assets", STATIC_DIR, append_version=True)
    return application


async def root_redirect(_: web.Request) -> web.Response:
    raise web.HTTPFound("/miniapp")


async def health(request: web.Request) -> web.Response:
    async with request.app[SESSION_FACTORY_KEY]() as session:
        await session.scalar(text("select 1"))
    return web.json_response(
        {
            "ok": True,
            "service": "telegram-memberships-saas",
            "database": "ok",
            "telegram": "ok",
            "bot": f"@{request.app[BOT_USERNAME_KEY]}",
        }
    )


async def client_page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "client.html")


async def admin_page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "admin.html")


async def client_dashboard(request: web.Request) -> web.Response:
    async with request.app[SESSION_FACTORY_KEY]() as session:
        user = await _authenticated_user(request, session)
        settings = request.app[SETTINGS_KEY]
        plans = await list_plans(session, only_active=True)
        memberships = await get_active_memberships(session, user.id)
        return web.json_response(
            {
                "ok": True,
                "brand": settings.public_brand_name,
                "botUsername": request.app[BOT_USERNAME_KEY],
                "user": _user_payload(user),
                "languages": [
                    {"code": code, "label": LANGUAGE_LABELS.get(code, code.upper())}
                    for code in settings.supported_languages
                ],
                "plans": [_plan_payload(plan, settings) for plan in plans],
                "memberships": [_membership_payload(item, settings) for item in memberships],
            }
        )


async def client_language(request: web.Request) -> web.Response:
    payload = await request.json()
    async with request.app[SESSION_FACTORY_KEY]() as session:
        user = await _authenticated_user(request, session)
        settings = request.app[SETTINGS_KEY]
        language = str(payload.get("language", "")).lower().strip()
        if language not in settings.supported_languages:
            raise ValueError("Idioma no disponible.")
        await set_preferred_language(
            session,
            user=user,
            language=language,
            supported_languages=settings.supported_languages,
        )
        await session.commit()
    return web.json_response({"ok": True, "language": language})


async def client_support(request: web.Request) -> web.Response:
    payload = await request.json()
    body = str(payload.get("message", "")).strip()
    if len(body) < 2 or len(body) > 3000:
        raise ValueError("El mensaje debe tener entre 2 y 3000 caracteres.")
    async with request.app[SESSION_FACTORY_KEY]() as session:
        user = await _authenticated_user(request, session)
        sent = await forward_webapp_text_to_admins(
            bot=request.app[BOT_KEY],
            session=session,
            settings=request.app[SETTINGS_KEY],
            user=user,
            text=body,
        )
        await session.commit()
    if not sent:
        raise ValueError("No hay administradores disponibles en este momento.")
    return web.json_response({"ok": True, "sent": sent})


async def client_buy_plan(request: web.Request) -> web.Response:
    async with request.app[SESSION_FACTORY_KEY]() as session:
        user = await _authenticated_user(request, session)
        plan = await get_plan(session, int(request.match_info["plan_id"]))
        if plan is None or not plan.is_active:
            raise ValueError("Plan no disponible.")
        methods = [method for method in plan.payment_methods if method.is_active]
        if not methods:
            raise ValueError("El plan no tiene metodos de pago activos.")
        await request.app[BOT_KEY].send_message(
            user.telegram_id,
            f"<b>{h(plan.name)}</b>\n\n"
            f"Precio: <b>{money(plan.price, plan.currency)}</b>\n"
            f"Duracion: <b>{plan.duration_days} dias</b>\n\n"
            f"{t(user.preferred_language, 'plan.select_payment', plan=h(plan.name))}",
            reply_markup=payment_methods_keyboard(plan.id, methods, user.preferred_language),
        )
    return web.json_response({"ok": True, "message": "Opciones enviadas al chat."})


async def client_renew_membership(request: web.Request) -> web.Response:
    async with request.app[SESSION_FACTORY_KEY]() as session:
        user = await _authenticated_user(request, session)
        membership = await session.scalar(
            select(Membership)
            .options(selectinload(Membership.plan).selectinload(Plan.payment_methods))
            .where(
                Membership.id == int(request.match_info["membership_id"]),
                Membership.user_id == user.id,
            )
        )
        if membership is None:
            raise ValueError("Membresia no encontrada.")
        methods = [method for method in membership.plan.payment_methods if method.is_active]
        if not methods:
            raise ValueError("El plan no tiene metodos de pago activos.")
        await request.app[BOT_KEY].send_message(
            user.telegram_id,
            t(user.preferred_language, "renew.title", plan=h(membership.plan.name))
            + "\n\n"
            + t(user.preferred_language, "renew.select_payment"),
            reply_markup=renewal_payment_methods_keyboard(
                membership_id=membership.id,
                plan_id=membership.plan.id,
                methods=methods,
                language=user.preferred_language,
            ),
        )
    return web.json_response({"ok": True, "message": "Renovacion enviada al chat."})


async def admin_dashboard(request: web.Request) -> web.Response:
    async with request.app[SESSION_FACTORY_KEY]() as session:
        user, role = await _authenticated_admin(request, session, permission="view_stats")
        settings = request.app[SETTINGS_KEY]
        stats = await get_overview(session, settings)
        pending = await list_pending_payment_requests(session, limit=30)
        plans = await list_plans(session)
        payment_methods = await list_payment_methods(session)
        return web.json_response(
            {
                "ok": True,
                "brand": settings.public_brand_name,
                "botUsername": request.app[BOT_USERNAME_KEY],
                "user": _user_payload(user),
                "role": role.value,
                "permissions": permissions_for(role).__dict__,
                "stats": {key: _json_value(value) for key, value in stats.items()},
                "pending": [_payment_payload(item, settings) for item in pending],
                "plans": [
                    _plan_payload(
                        plan,
                        settings,
                        include_inactive=True,
                        all_methods=payment_methods,
                    )
                    for plan in plans
                ],
                "settings": {
                    "brand": settings.public_brand_name,
                    "support_url": settings.support_url or "",
                    "faq_url": settings.faq_url or "",
                    "default_language": settings.default_language,
                    "stars_per_usd": str(settings.effective_stars_per_usd),
                    "currency_rates": ",".join(
                        f"{code}={rate}" for code, rate in sorted(settings.currency_usd_rates.items())
                    ),
                    "scheduler": settings.scheduler_enabled,
                },
            }
        )


async def admin_approve_payment(request: web.Request) -> web.Response:
    request_id = int(request.match_info["request_id"])
    async with payment_lock(request_id):
        async with request.app[SESSION_FACTORY_KEY]() as session:
            admin_user, _ = await _authenticated_admin(request, session, permission="review_payments")
            payment = await get_payment_request_for_update(session, request_id)
            if payment is None:
                raise ValueError("Solicitud no encontrada.")
            membership, links = await PaymentService(session).approve_manual_payment(
                bot=request.app[BOT_KEY],
                settings=request.app[SETTINGS_KEY],
                request=payment,
                admin_user=admin_user,
            )
            await session.commit()
            try:
                await send_access_links(
                    bot=request.app[BOT_KEY],
                    user_telegram_id=payment.user.telegram_id,
                    membership=membership,
                    links=links,
                    settings=request.app[SETTINGS_KEY],
                )
            except TelegramAPIError:
                logger.exception("Payment %s approved but access message failed", request_id)
    return web.json_response({"ok": True, "status": "APPROVED"})


async def admin_payment_proof(request: web.Request) -> web.Response:
    async with request.app[SESSION_FACTORY_KEY]() as session:
        await _authenticated_admin(request, session, permission="review_payments")
        payment = await get_payment_request(session, int(request.match_info["request_id"]))
        if payment is None or not payment.proof_file_id:
            raise web.HTTPNotFound(text="Comprobante no encontrado.")
        telegram_file = await request.app[BOT_KEY].get_file(payment.proof_file_id)
        if not telegram_file.file_path:
            raise web.HTTPNotFound(text="Archivo no disponible.")
        downloaded = await request.app[BOT_KEY].download_file(telegram_file.file_path)
        content = downloaded.read()
        filename = Path(telegram_file.file_path).name or f"comprobante-{payment.id}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return web.Response(
            body=content,
            content_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )


async def admin_reject_payment(request: web.Request) -> web.Response:
    request_id = int(request.match_info["request_id"])
    payload = await request.json()
    reason = str(payload.get("reason", "")).strip() or "Comprobante no aprobado."
    async with payment_lock(request_id):
        async with request.app[SESSION_FACTORY_KEY]() as session:
            admin_user, _ = await _authenticated_admin(request, session, permission="review_payments")
            payment = await get_payment_request_for_update(session, request_id)
            if payment is None:
                raise ValueError("Solicitud no encontrada.")
            await PaymentService(session).reject_payment(
                request=payment,
                admin_user=admin_user,
                reason=reason,
            )
            await session.commit()
            try:
                await send_payment_rejected(
                    bot=request.app[BOT_KEY],
                    user_telegram_id=payment.user.telegram_id,
                    reason=reason,
                )
            except TelegramAPIError:
                logger.exception("Payment %s rejected but user notification failed", request_id)
    return web.json_response({"ok": True, "status": "REJECTED"})


async def admin_toggle_plan_method(request: web.Request) -> web.Response:
    async with request.app[SESSION_FACTORY_KEY]() as session:
        admin_user, _ = await _authenticated_admin(request, session, permission="manage_catalog")
        plan = await get_plan(session, int(request.match_info["plan_id"]))
        if plan is None:
            raise ValueError("Plan no encontrado.")
        method_id = int(request.match_info["method_id"])
        enabled = not any(method.id == method_id for method in plan.payment_methods)
        plan = await toggle_plan_payment_method(
            session,
            plan_id=plan.id,
            payment_method_id=method_id,
            actor=admin_user,
        )
        await session.commit()
    return web.json_response({"ok": True, "enabled": any(item.id == method_id for item in plan.payment_methods)})


async def admin_update_setting(request: web.Request) -> web.Response:
    payload = await request.json()
    async with request.app[SESSION_FACTORY_KEY]() as session:
        admin_user, role = await _authenticated_admin(request, session)
        if role != Role.OWNER:
            raise PermissionError("Solo OWNER puede editar configuraciones globales.")
        value = await update_runtime_setting(
            session,
            settings=request.app[SETTINGS_KEY],
            key=request.match_info["key"],
            raw_value=str(payload.get("value", "")),
            actor=admin_user,
        )
        await session.commit()
    return web.json_response({"ok": True, "value": _json_value(value)})


async def _authenticated_user(request: web.Request, session: AsyncSession) -> User:
    settings = request.app[SETTINGS_KEY]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        raise PermissionError("Abre esta Mini App desde Telegram.")
    webapp_user = parse_webapp_user(
        init_data,
        settings.bot_token,
        max_age_seconds=settings.telegram_webapp_max_age_seconds,
    )
    user = await get_user_by_telegram_id(session, webapp_user.id)
    if user is None:
        raise PermissionError("Primero inicia el bot con /start.")
    return user


async def _authenticated_admin(
    request: web.Request,
    session: AsyncSession,
    *,
    permission: str | None = None,
) -> tuple[User, Role]:
    user = await _authenticated_user(request, session)
    role = await get_role(session, user.telegram_id, request.app[SETTINGS_KEY])
    if role is None:
        raise PermissionError("No tienes acceso al panel administrativo.")
    if permission and not getattr(permissions_for(role), permission):
        raise PermissionError("Tu rol no permite esta operacion.")
    return user, role


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.telegram_id,
        "name": user.display_name,
        "username": user.username,
        "language": user.preferred_language,
    }


def _plan_payload(
    plan: Plan,
    settings: Settings,
    *,
    include_inactive: bool = False,
    all_methods: list | None = None,
) -> dict[str, Any]:
    try:
        conversion = plan_price_to_stars(plan, settings)
        stars: dict[str, Any] | None = {
            "amount": conversion.stars_amount,
            "usd": str(conversion.usd_amount),
            "starsPerUsd": str(conversion.stars_per_usd),
        }
    except ValueError:
        stars = None
    payload = {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description or "",
        "price": str(plan.price),
        "currency": plan.currency,
        "durationDays": plan.duration_days,
        "active": plan.is_active,
        "stars": stars,
        "accessCount": len(plan.channels) + len(plan.groups),
        "methods": [
            {
                "id": method.id,
                "name": method.name,
                "provider": method.provider.value,
                "active": method.is_active,
                "enabledForPlan": any(linked.id == method.id for linked in plan.payment_methods),
            }
            for method in (all_methods if all_methods is not None else plan.payment_methods)
        ],
    }
    if include_inactive:
        payload["statusLabel"] = "Activo" if plan.is_active else "Inactivo"
    return payload


def _membership_payload(membership: Membership, settings: Settings) -> dict[str, Any]:
    return {
        "id": membership.id,
        "plan": membership.plan.name,
        "status": membership.status.value,
        "expiresAt": membership.expires_at.isoformat(),
        "expiresLabel": human_datetime(membership.expires_at, settings.app_timezone),
        "daysLeft": remaining_days(membership.expires_at),
    }


def _payment_payload(payment: PaymentRequest, settings: Settings) -> dict[str, Any]:
    return {
        "id": payment.id,
        "user": payment.user.display_name,
        "telegramId": payment.user.telegram_id,
        "plan": payment.plan.name,
        "method": payment.payment_method.name,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "submittedAt": payment.submitted_at.isoformat(),
        "submittedLabel": human_datetime(payment.submitted_at, settings.app_timezone),
        "kind": "Renovacion" if payment.metadata_json.get("request_kind") == "renewal" else "Compra",
        "hasProof": bool(payment.proof_file_id),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [[_json_value(item) for item in row] if isinstance(row, tuple) else _json_value(row) for row in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value
