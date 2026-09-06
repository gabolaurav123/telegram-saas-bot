from __future__ import annotations

from decimal import Decimal
import unittest

from app.config.settings import Settings
from app.models.plan import Plan
from app.services.currency import plan_price_to_stars
from app.utils.i18n import normalize_language, t


class CurrencyStarsTests(unittest.TestCase):
    def test_mxn_plan_converts_to_usd_before_stars(self) -> None:
        settings = Settings(
            BOT_TOKEN="123:ABC",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            OWNER_ID=1,
            CURRENCY_USD_RATES="USD=1,MXN=0.058",
            TELEGRAM_STARS_PER_USD="100",
        )
        plan = Plan(name="VIP MXN", slug="vip-mxn", price=Decimal("200"), currency="MXN", duration_days=30)

        conversion = plan_price_to_stars(plan, settings)

        self.assertEqual(conversion.usd_amount, Decimal("11.60"))
        self.assertEqual(conversion.stars_amount, 1160)

    def test_missing_non_usd_rate_fails_safe(self) -> None:
        settings = Settings(
            BOT_TOKEN="123:ABC",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            OWNER_ID=1,
            CURRENCY_USD_RATES="USD=1",
            TELEGRAM_STARS_PER_USD="100",
        )
        plan = Plan(name="VIP MXN", slug="vip-mxn", price=Decimal("200"), currency="MXN", duration_days=30)

        with self.assertRaises(ValueError):
            plan_price_to_stars(plan, settings)

    def test_legacy_ratio_one_falls_back_to_safe_default(self) -> None:
        settings = Settings(
            BOT_TOKEN="123:ABC",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            OWNER_ID=1,
            CURRENCY_USD_RATES="USD=1,MXN=0.058",
            TELEGRAM_STARS_DEFAULT_RATIO="1",
        )
        plan = Plan(name="VIP USD", slug="vip-usd", price=Decimal("10"), currency="USD", duration_days=30)

        self.assertEqual(plan_price_to_stars(plan, settings).stars_amount, 1000)

    def test_plan_exact_stars_override_is_preserved(self) -> None:
        settings = Settings(
            BOT_TOKEN="123:ABC",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            OWNER_ID=1,
            CURRENCY_USD_RATES="USD=1,MXN=0.058",
            TELEGRAM_STARS_PER_USD="100",
        )
        plan = Plan(
            name="VIP MXN",
            slug="vip-mxn",
            price=Decimal("200"),
            currency="MXN",
            duration_days=30,
            metadata_json={"stars_amount": 999},
        )

        self.assertEqual(plan_price_to_stars(plan, settings).stars_amount, 999)


class I18NTests(unittest.TestCase):
    def test_normalize_and_translate_language(self) -> None:
        self.assertEqual(normalize_language("en-US", ["es", "en"]), "en")
        self.assertEqual(t("en", "btn.buy_membership"), "Buy membership")
        self.assertEqual(t("pt", "btn.renew_now"), "Renovar agora")


if __name__ == "__main__":
    unittest.main()
