from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parse_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value.replace(",", ".").strip())
    except InvalidOperation as exc:
        raise ValueError("El precio no es valido") from exc
    if parsed <= 0:
        raise ValueError("El precio debe ser mayor a cero")
    return parsed.quantize(Decimal("0.01"))


def parse_positive_int(value: str, field_name: str = "valor") -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"El {field_name} debe ser un numero entero") from exc
    if parsed <= 0:
        raise ValueError(f"El {field_name} debe ser mayor a cero")
    return parsed


def parse_telegram_id(value: str) -> int:
    value = value.strip()
    if not value.lstrip("-").isdigit():
        raise ValueError("El Telegram ID debe ser numerico")
    return int(value)

