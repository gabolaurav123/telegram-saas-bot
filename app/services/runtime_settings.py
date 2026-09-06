from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.enums import LogAction
from app.models.setting import Setting
from app.models.user import User
from app.services.logs import log_event


RUNTIME_PREFIX = "runtime."
EDITABLE_SETTINGS = {
    "brand": ("public_brand_name", "Marca publica"),
    "support_url": ("support_url", "URL de soporte"),
    "faq_url": ("faq_url", "URL de FAQ"),
    "default_language": ("default_language", "Idioma predeterminado"),
    "stars_per_usd": ("telegram_stars_per_usd", "Stars por USD"),
    "currency_rates": ("currency_usd_rates", "Tasas de cambio a USD"),
}


async def load_runtime_settings(session: AsyncSession, settings: Settings) -> int:
    rows = (
        await session.scalars(select(Setting).where(Setting.key.like(f"{RUNTIME_PREFIX}%")))
    ).all()
    loaded = 0
    for row in rows:
        setting_key = row.key.removeprefix(RUNTIME_PREFIX)
        spec = EDITABLE_SETTINGS.get(setting_key)
        if spec is None or "value" not in row.value:
            continue
        try:
            parsed = parse_runtime_value(setting_key, row.value["value"], settings)
        except ValueError:
            continue
        setattr(settings, spec[0], parsed)
        loaded += 1
    return loaded


async def update_runtime_setting(
    session: AsyncSession,
    *,
    settings: Settings,
    key: str,
    raw_value: str,
    actor: User,
) -> Any:
    spec = EDITABLE_SETTINGS.get(key)
    if spec is None:
        raise ValueError("Configuracion no editable.")
    parsed = parse_runtime_value(key, raw_value, settings)
    persisted = serialize_runtime_value(parsed)
    db_key = f"{RUNTIME_PREFIX}{key}"
    row = await session.scalar(select(Setting).where(Setting.key == db_key))
    if row is None:
        row = Setting(key=db_key, value={"value": persisted}, description=spec[1])
        session.add(row)
    else:
        row.value = {"value": persisted}
    setattr(settings, spec[0], parsed)
    await log_event(
        session,
        LogAction.SETTING_UPDATED,
        f"Configuracion actualizada: {key}",
        actor_user_id=actor.id,
        details={"key": key, "value": persisted},
    )
    return parsed


def parse_runtime_value(key: str, raw_value: Any, settings: Settings) -> Any:
    text = str(raw_value).strip() if raw_value is not None and not isinstance(raw_value, dict) else raw_value
    if key == "brand":
        if not text or len(text) > 80:
            raise ValueError("La marca debe tener entre 1 y 80 caracteres.")
        return text
    if key in {"support_url", "faq_url"}:
        if text is None or not text or text == "-":
            return None
        if not str(text).startswith(("https://", "http://", "tg://")):
            raise ValueError("La URL debe comenzar con https://, http:// o tg://.")
        return str(text)
    if key == "default_language":
        language = str(text).lower().split("-")[0]
        if language not in settings.supported_languages:
            raise ValueError("Idioma no disponible en SUPPORTED_LANGUAGES.")
        return language
    if key == "stars_per_usd":
        try:
            value = Decimal(str(text).replace(",", "."))
        except InvalidOperation as exc:
            raise ValueError("Stars por USD debe ser un numero valido.") from exc
        if value <= 0 or value > 10000:
            raise ValueError("Stars por USD debe estar entre 0 y 10000.")
        return value
    if key == "currency_rates":
        if isinstance(text, dict):
            values = text
        else:
            stripped = str(text).strip()
            try:
                values = json.loads(stripped) if stripped.startswith("{") else dict(
                    item.strip().split("=", 1)
                    for item in stripped.split(",")
                    if item.strip()
                )
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValueError("Usa el formato USD=1,MXN=0.05926,BOB=0.145.") from exc
        try:
            rates = {str(code).upper().strip(): Decimal(str(rate)) for code, rate in values.items()}
        except (InvalidOperation, AttributeError) as exc:
            raise ValueError("Todas las tasas deben ser numeros validos.") from exc
        if not rates or any(not code or rate <= 0 for code, rate in rates.items()):
            raise ValueError("Las monedas y sus tasas deben ser validas y mayores que cero.")
        rates["USD"] = Decimal("1")
        return rates
    raise ValueError("Configuracion no editable.")


def serialize_runtime_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: str(item) if isinstance(item, Decimal) else item for key, item in value.items()}
    return value
