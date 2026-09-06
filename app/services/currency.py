from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.config.settings import Settings
from app.models.plan import Plan


@dataclass(frozen=True)
class USDConversion:
    source_amount: Decimal
    source_currency: str
    usd_amount: Decimal
    rate_to_usd: Decimal
    rate_source: str


@dataclass(frozen=True)
class StarsConversion:
    source_amount: Decimal
    source_currency: str
    usd_amount: Decimal
    rate_to_usd: Decimal
    stars_per_usd: Decimal
    stars_amount: int
    rate_source: str


def plan_price_to_usd(plan: Plan, settings: Settings) -> USDConversion:
    metadata = plan.metadata_json or {}
    source_amount = Decimal(str(plan.price))
    source_currency = (plan.currency or settings.default_currency).upper().strip()

    configured_usd = _metadata_decimal(metadata, "price_usd")
    if configured_usd is not None:
        return USDConversion(
            source_amount=source_amount,
            source_currency=source_currency,
            usd_amount=configured_usd,
            rate_to_usd=(configured_usd / source_amount) if source_amount else Decimal("0"),
            rate_source="plan.metadata_json.price_usd",
        )

    configured_rate = _metadata_decimal(metadata, "usd_rate")
    if configured_rate is not None:
        return USDConversion(
            source_amount=source_amount,
            source_currency=source_currency,
            usd_amount=_money_quantize(source_amount * configured_rate),
            rate_to_usd=configured_rate,
            rate_source="plan.metadata_json.usd_rate",
        )

    if source_currency == "USD":
        return USDConversion(
            source_amount=source_amount,
            source_currency=source_currency,
            usd_amount=_money_quantize(source_amount),
            rate_to_usd=Decimal("1"),
            rate_source="USD",
        )

    rate = settings.currency_usd_rates.get(source_currency)
    if rate is None:
        raise ValueError(
            f"No hay tasa USD configurada para {source_currency}. "
            "Define CURRENCY_USD_RATES en Seenode o usd_rate en metadata_json del plan."
        )
    if rate <= 0:
        raise ValueError(f"La tasa USD para {source_currency} debe ser mayor que cero.")

    return USDConversion(
        source_amount=source_amount,
        source_currency=source_currency,
        usd_amount=_money_quantize(source_amount * rate),
        rate_to_usd=rate,
        rate_source="settings.currency_usd_rates",
    )


def plan_price_to_stars(plan: Plan, settings: Settings) -> StarsConversion:
    exact_stars = _metadata_decimal(plan.metadata_json or {}, "stars_amount")
    usd = plan_price_to_usd(plan, settings)
    stars_per_usd = settings.effective_stars_per_usd
    if exact_stars is not None:
        amount = max(1, int(exact_stars.to_integral_value(rounding=ROUND_HALF_UP)))
    else:
        amount = max(1, int((usd.usd_amount * stars_per_usd).to_integral_value(rounding=ROUND_HALF_UP)))
    return StarsConversion(
        source_amount=usd.source_amount,
        source_currency=usd.source_currency,
        usd_amount=usd.usd_amount,
        rate_to_usd=usd.rate_to_usd,
        stars_per_usd=stars_per_usd,
        stars_amount=amount,
        rate_source=usd.rate_source,
    )


def _metadata_decimal(metadata: dict[str, Any], key: str) -> Decimal | None:
    value = metadata.get(key)
    if value in (None, ""):
        return None
    parsed = Decimal(str(value))
    if parsed <= 0:
        raise ValueError(f"{key} debe ser mayor que cero.")
    return parsed


def _money_quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
