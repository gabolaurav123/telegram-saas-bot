from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from urllib.parse import parse_qsl


@dataclass(frozen=True)
class WebAppUser:
    id: int
    username: str | None
    first_name: str | None
    last_name: str | None


def validate_webapp_init_data(init_data: str, bot_token: str) -> bool:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if not received_hash:
        return False
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, received_hash)


def parse_webapp_user(init_data: str, bot_token: str) -> WebAppUser:
    if not validate_webapp_init_data(init_data, bot_token):
        raise ValueError("Telegram WebApp initData invalido.")
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    raw_user = values.get("user")
    if not raw_user:
        raise ValueError("Telegram WebApp initData no contiene usuario.")
    payload = json.loads(raw_user)
    return WebAppUser(
        id=int(payload["id"]),
        username=payload.get("username"),
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
    )
