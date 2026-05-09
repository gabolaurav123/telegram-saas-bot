from __future__ import annotations

import re
from decimal import Decimal
from html import escape
from string import Formatter


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def h(value: object) -> str:
    return escape(str(value), quote=True)


def money(amount: Decimal | int | float | str, currency: str) -> str:
    value = Decimal(str(amount))
    return f"{value:,.2f} {currency.upper()}"


def slugify(value: str) -> str:
    cleaned = _SLUG_RE.sub("-", value.lower()).strip("-")
    return cleaned or "plan"


def render_template(template: str, **data: object) -> str:
    safe_data = {key: "" if value is None else value for key, value in data.items()}
    allowed_fields = {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}
    missing = allowed_fields - set(safe_data)
    for key in missing:
        safe_data[key] = ""
    return template.format_map(_SafeFormatDict(safe_data))


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


DEFAULT_PAYMENT_TEMPLATE = (
    "Hola {username}\n\n"
    "Has seleccionado el plan {plan_name}.\n\n"
    "Monto: {price}\n"
    "Duracion: {duration} dias\n"
    "Metodo: {payment_method}\n\n"
    "{instructions}\n\n"
    "Luego envia una imagen o documento con tu comprobante."
)

