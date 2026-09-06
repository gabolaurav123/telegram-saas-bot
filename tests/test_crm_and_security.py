from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from urllib.parse import quote

from app.models.enums import Role
from app.services.admins import permissions_for
from app.services.crm import parse_start_attribution
from app.utils.telegram_webapp import parse_webapp_user, validate_webapp_init_data


class CRMAttributionTests(unittest.TestCase):
    def test_parse_key_value_start_parameter(self) -> None:
        attribution = parse_start_attribution("source=adscamp&campaign=vip&referral=ABC123")

        self.assertEqual(attribution.source, "adscamp")
        self.assertEqual(attribution.campaign, "vip")
        self.assertEqual(attribution.referral, "ABC123")

    def test_parse_referral_shortcut(self) -> None:
        attribution = parse_start_attribution("ref_ABC123")

        self.assertEqual(attribution.referral, "ABC123")


class RolePermissionTests(unittest.TestCase):
    def test_payments_role_can_review_but_not_manage_admins(self) -> None:
        permissions = permissions_for(Role.PAYMENTS)

        self.assertTrue(permissions.review_payments)
        self.assertFalse(permissions.manage_admins)


class TelegramWebAppTests(unittest.TestCase):
    def test_validate_and_parse_init_data(self) -> None:
        token = "123:ABC"
        user = {"id": 42, "first_name": "Gabriel", "username": "gabriel"}
        values = {
            "auth_date": "1790000000",
            "query_id": "AAH-test",
            "user": json.dumps(user, separators=(",", ":")),
        }
        data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        payload_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        init_data = "&".join(f"{key}={quote(value)}" for key, value in values.items()) + f"&hash={payload_hash}"

        self.assertTrue(validate_webapp_init_data(init_data, token))
        parsed = parse_webapp_user(init_data, token)
        self.assertEqual(parsed.id, 42)
        self.assertEqual(parsed.username, "gabriel")


if __name__ == "__main__":
    unittest.main()
