from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.enums import LogAction, ProofKind, ReceiptStatus
from app.models.payment_request import PaymentRequest
from app.models.receipt import PaymentReceipt
from app.services.logs import log_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReceiptAnalysis:
    sha256: str | None
    perceptual_hash: str | None
    status: ReceiptStatus
    warnings: list[str]
    duplicate_payment_request_id: int | None


async def analyze_and_store_receipt(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    request: PaymentRequest,
) -> PaymentReceipt:
    analysis = await analyze_receipt_file(
        bot=bot,
        session=session,
        settings=settings,
        proof_kind=request.proof_kind,
        file_id=request.proof_file_id,
        current_payment_request_id=request.id,
    )
    request.receipt_sha256 = analysis.sha256
    request.receipt_perceptual_hash = analysis.perceptual_hash
    request.receipt_warning_count = len(analysis.warnings)

    receipt = PaymentReceipt(
        payment_request_id=request.id,
        user_id=request.user_id,
        proof_kind=request.proof_kind,
        file_id=request.proof_file_id,
        file_unique_id=request.proof_file_unique_id,
        sha256=analysis.sha256,
        perceptual_hash=analysis.perceptual_hash,
        duplicate_of_payment_request_id=analysis.duplicate_payment_request_id,
        status=analysis.status,
        warning_text="\n".join(analysis.warnings) if analysis.warnings else None,
        warnings_json={"warnings": analysis.warnings},
    )
    session.add(receipt)
    if analysis.warnings:
        await log_event(
            session,
            LogAction.PAYMENT_RECEIPT_DUPLICATE,
            f"Advertencias antifraude en pago {request.id}",
            target_user_id=request.user_id,
            details={
                "payment_request_id": request.id,
                "status": analysis.status.value,
                "warnings": analysis.warnings,
                "duplicate_payment_request_id": analysis.duplicate_payment_request_id,
            },
        )
    return receipt


async def analyze_receipt_file(
    *,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    proof_kind: ProofKind | None,
    file_id: str | None,
    current_payment_request_id: int,
) -> ReceiptAnalysis:
    warnings: list[str] = []
    if not proof_kind or not file_id:
        return ReceiptAnalysis(None, None, ReceiptStatus.CLEAN, warnings, None)

    data = await _download_file_bytes(bot, file_id, max_mb=settings.receipt_max_download_mb)
    sha256 = hashlib.sha256(data).hexdigest()
    duplicate_request_id = await _find_exact_duplicate(
        session,
        sha256=sha256,
        current_payment_request_id=current_payment_request_id,
    )
    if duplicate_request_id:
        warnings.append(f"Este archivo exacto ya fue utilizado en el pago #{duplicate_request_id}.")

    perceptual_hash = _perceptual_hash(data) if proof_kind == ProofKind.PHOTO else None
    similar_request_id = None
    if perceptual_hash:
        similar_request_id = await _find_similar_image(
            session,
            perceptual_hash=perceptual_hash,
            current_payment_request_id=current_payment_request_id,
        )
        if similar_request_id and similar_request_id != duplicate_request_id:
            warnings.append(f"Imagen con alta similitud con el pago #{similar_request_id}.")

    status = ReceiptStatus.CLEAN
    if duplicate_request_id:
        status = ReceiptStatus.DUPLICATE
    elif similar_request_id:
        status = ReceiptStatus.SIMILAR
    return ReceiptAnalysis(sha256, perceptual_hash, status, warnings, duplicate_request_id or similar_request_id)


async def _download_file_bytes(bot: Bot, file_id: str, *, max_mb: int) -> bytes:
    tg_file = await bot.get_file(file_id)
    if tg_file.file_size and tg_file.file_size > max_mb * 1024 * 1024:
        raise ValueError(f"El comprobante supera el limite de {max_mb} MB.")
    buffer = io.BytesIO()
    try:
        await bot.download_file(tg_file.file_path, destination=buffer)
    except TelegramAPIError:
        logger.exception("Could not download receipt file %s", file_id)
        raise
    return buffer.getvalue()


async def _find_exact_duplicate(
    session: AsyncSession,
    *,
    sha256: str,
    current_payment_request_id: int,
) -> int | None:
    return await session.scalar(
        select(PaymentReceipt.payment_request_id)
        .where(
            PaymentReceipt.sha256 == sha256,
            PaymentReceipt.payment_request_id != current_payment_request_id,
        )
        .order_by(PaymentReceipt.created_at.asc())
        .limit(1)
    )


async def _find_similar_image(
    session: AsyncSession,
    *,
    perceptual_hash: str,
    current_payment_request_id: int,
) -> int | None:
    rows = await session.execute(
        select(PaymentReceipt.payment_request_id, PaymentReceipt.perceptual_hash)
        .where(
            PaymentReceipt.perceptual_hash.is_not(None),
            PaymentReceipt.payment_request_id != current_payment_request_id,
        )
        .limit(200)
    )
    for payment_request_id, existing_hash in rows:
        if existing_hash and _hamming_distance(perceptual_hash, existing_hash) <= 6:
            return int(payment_request_id)
    return None


def _perceptual_hash(data: bytes) -> str | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        image = Image.open(io.BytesIO(data)).convert("L").resize((8, 8))
    except Exception:
        return None
    pixels = list(image.getdata())
    average = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def _hamming_distance(left: str, right: str) -> int:
    return bin(int(left, 16) ^ int(right, 16)).count("1")
