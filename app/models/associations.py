from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table

from app.database.base import Base


plan_channels = Table(
    "plan_channels",
    Base.metadata,
    Column("plan_id", ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True),
    Column("channel_id", ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
)


plan_groups = Table(
    "plan_groups",
    Base.metadata,
    Column("plan_id", ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)


plan_payment_methods = Table(
    "plan_payment_methods",
    Base.metadata,
    Column("plan_id", ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "payment_method_id",
        ForeignKey("payment_methods.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
