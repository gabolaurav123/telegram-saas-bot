from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import ProofKind, ReceiptStatus
from app.models.types import enum_type

if TYPE_CHECKING:
    from app.models.payment_request import PaymentRequest
    from app.models.user import User


class PaymentReceipt(Base, TimestampMixin):
    __tablename__ = "payment_receipts"
    __table_args__ = (UniqueConstraint("payment_request_id", name="uq_payment_receipts_payment_request"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_request_id: Mapped[int] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    proof_kind: Mapped[ProofKind] = mapped_column(enum_type(ProofKind, "receipt_proof_kind"), nullable=False)
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_unique_id: Mapped[str | None] = mapped_column(String(255), index=True)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    duplicate_of_payment_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_requests.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[ReceiptStatus] = mapped_column(
        enum_type(ReceiptStatus, "receipt_status"),
        default=ReceiptStatus.CLEAN,
        server_default=ReceiptStatus.CLEAN.value,
        nullable=False,
        index=True,
    )
    warning_text: Mapped[str | None] = mapped_column(Text)
    warnings_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'"), nullable=False
    )

    payment_request: Mapped["PaymentRequest"] = relationship(
        foreign_keys=[payment_request_id],
        lazy="selectin",
    )
    duplicate_of_payment_request: Mapped["PaymentRequest | None"] = relationship(
        foreign_keys=[duplicate_of_payment_request_id],
        lazy="selectin",
    )
    user: Mapped["User"] = relationship(lazy="selectin")
