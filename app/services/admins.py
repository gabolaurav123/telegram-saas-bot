from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.models.admin import Admin
from app.models.enums import LogAction, Role
from app.models.user import User
from app.services.logs import log_event
from app.services.users import get_user_by_telegram_id


ROLE_LEVEL = {
    Role.READ_ONLY: 0,
    Role.SUPPORT: 1,
    Role.SALES: 1,
    Role.PAYMENTS: 1,
    Role.MODERATOR: 1,
    Role.SUPERVISOR: 2,
    Role.ADMIN: 2,
    Role.OWNER: 3,
}


@dataclass(frozen=True)
class Permission:
    manage_admins: bool = False
    manage_settings: bool = False
    manage_catalog: bool = False
    review_payments: bool = False
    view_stats: bool = False
    support: bool = False
    broadcast: bool = False
    direct_message: bool = False


ROLE_PERMISSIONS = {
    Role.OWNER: Permission(
        manage_admins=True,
        manage_settings=True,
        manage_catalog=True,
        review_payments=True,
        view_stats=True,
        support=True,
        broadcast=True,
        direct_message=True,
    ),
    Role.SUPERVISOR: Permission(
        manage_catalog=True,
        review_payments=True,
        view_stats=True,
        support=True,
        broadcast=True,
        direct_message=True,
    ),
    Role.ADMIN: Permission(
        manage_catalog=True,
        review_payments=True,
        view_stats=True,
        support=True,
        broadcast=True,
        direct_message=True,
    ),
    Role.PAYMENTS: Permission(
        review_payments=True,
        view_stats=True,
    ),
    Role.SUPPORT: Permission(support=True, direct_message=True),
    Role.SALES: Permission(view_stats=True, broadcast=True, direct_message=True),
    Role.MODERATOR: Permission(support=True),
    Role.READ_ONLY: Permission(view_stats=True),
}


async def get_admin_by_telegram_id(session: AsyncSession, telegram_id: int) -> Admin | None:
    return await session.scalar(
        select(Admin)
        .options(selectinload(Admin.user))
        .where(Admin.telegram_id == telegram_id, Admin.is_active.is_(True))
    )


async def get_role(session: AsyncSession, telegram_id: int, settings: Settings) -> Role | None:
    if telegram_id in settings.owner_ids:
        return Role.OWNER
    admin = await get_admin_by_telegram_id(session, telegram_id)
    return admin.role if admin else None


async def has_role(
    session: AsyncSession,
    telegram_id: int,
    settings: Settings,
    minimum_role: Role,
) -> bool:
    role = await get_role(session, telegram_id, settings)
    if role is None:
        return False
    return ROLE_LEVEL.get(role, -1) >= ROLE_LEVEL.get(minimum_role, 99)


async def require_role(
    session: AsyncSession,
    telegram_id: int,
    settings: Settings,
    minimum_role: Role,
) -> Role:
    role = await get_role(session, telegram_id, settings)
    if role is None or ROLE_LEVEL.get(role, -1) < ROLE_LEVEL.get(minimum_role, 99):
        raise PermissionError("No tienes permisos para realizar esta accion.")
    return role


def permissions_for(role: Role) -> Permission:
    return ROLE_PERMISSIONS.get(role, Permission())


async def require_permission(
    session: AsyncSession,
    telegram_id: int,
    settings: Settings,
    permission: str,
) -> Role:
    role = await get_role(session, telegram_id, settings)
    if role is None:
        raise PermissionError("No tienes permisos para realizar esta accion.")
    if not getattr(permissions_for(role), permission, False):
        raise PermissionError("No tienes permisos para realizar esta accion.")
    return role


async def list_admins(session: AsyncSession) -> list[Admin]:
    result = await session.scalars(
        select(Admin)
        .options(selectinload(Admin.user))
        .where(Admin.is_active.is_(True))
        .order_by(Admin.role, Admin.created_at)
    )
    return list(result)


async def add_admin(
    session: AsyncSession,
    *,
    telegram_id: int,
    role: Role,
    actor: User | None,
    settings: Settings,
) -> Admin:
    if role == Role.OWNER and (actor is None or actor.telegram_id not in settings.owner_ids):
        raise PermissionError("Solo un OWNER por entorno puede crear otro OWNER.")

    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        raise ValueError("Ese usuario aun no existe. Debe ejecutar /start antes.")

    admin = await session.scalar(select(Admin).where(Admin.telegram_id == telegram_id))
    if admin is None:
        admin = Admin(
            user_id=user.id,
            telegram_id=user.telegram_id,
            role=role,
            is_active=True,
            added_by_id=actor.id if actor else None,
        )
        session.add(admin)
    else:
        admin.user_id = user.id
        admin.role = role
        admin.is_active = True
        admin.deactivated_at = None
        admin.added_by_id = actor.id if actor else admin.added_by_id

    await log_event(
        session,
        LogAction.ADMIN_CREATED,
        f"Admin {telegram_id} asignado como {role.value}",
        actor_user_id=actor.id if actor else None,
        target_user_id=user.id,
        details={"telegram_id": telegram_id, "role": role.value},
    )
    return admin


async def remove_admin(
    session: AsyncSession,
    *,
    telegram_id: int,
    actor: User | None,
    settings: Settings,
) -> None:
    if telegram_id in settings.owner_ids:
        raise PermissionError("No se puede eliminar un OWNER definido por entorno.")
    admin = await session.scalar(select(Admin).where(Admin.telegram_id == telegram_id))
    if admin is None or not admin.is_active:
        raise ValueError("Administrador no encontrado.")
    admin.is_active = False
    await log_event(
        session,
        LogAction.ADMIN_REMOVED,
        f"Admin {telegram_id} desactivado",
        actor_user_id=actor.id if actor else None,
        target_user_id=admin.user_id,
        details={"telegram_id": telegram_id},
    )
