from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum


EnumT = TypeVar("EnumT", bound=StrEnum)


def enum_type(enum_cls: type[EnumT], name: str, length: int = 32) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda enum: [item.value for item in enum],
    )

