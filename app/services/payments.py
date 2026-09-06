from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import LogAction, PaymentRequestStatus, ProofKind, UserStatus
from app.models.payment_method import PaymentMethod
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.services.logs import log_event
from app.utils.time import utc_now


def _payment_request_options(stmt: Select[tuple[PaymentRequest]]) -> Select[tuple[PaymentRequest]]:
    return stmt.options(
        selectinload(PaymentRequest.user),
        selectinload(PaymentRequest.plan).selectinload(Plan.channels),
        selectinload(PaymentRequest.plan).selectinload(Plan.groups),
        selectinload(PaymentRequest.payment_method),
    )


async def get_payment_request(session: AsyncSession, request_id: int) -> PaymentRequest | None:
    return await session.scalar(
        _payment_request_options(select(PaymentRequest)).where(PaymentRequest.id == request_id)
    )


async def get_payment_request_for_update(
    session: AsyncSession,
    request_id: int,
) -> PaymentRequest | None:
    """Lock a payment row so multiple replicas cannot review it concurrently."""

    return await session.scalar(
        _payment_request_options(select(PaymentRequest))
        .where(PaymentRequest.id == request_id)
        .with_for_update()
    )


async def create_payment_request(
    session: AsyncSession,
    *,
    user: User,
    plan: Plan,
    payment_method: PaymentMethod,
    proof_kind: ProofKind,
    proof_file_id: str,
    proof_file_unique_id: str | None,
    proof_message_id: int | None,
    metadata_json: dict | None = None,
) -> PaymentRequest:
    existing = await session.scalar(
        select(PaymentRequest.id).where(
            PaymentRequest.user_id == user.id,
            PaymentRequest.plan_id == plan.id,
            PaymentRequest.status.in_(
                [
                    PaymentRequestStatus.AWAITING_PROOF,
                    PaymentRequestStatus.PENDING,
                ]
            ),
        )
    )
    if existing:
        raise ValueError("Ya tienes una solicitud pendiente para este plan.")

    request = PaymentRequest(
        user_id=user.id,
        plan_id=plan.id,
        payment_method_id=payment_method.id,
        status=PaymentRequestStatus.PENDING,
        amount=plan.price,
        currency=plan.currency,
        proof_kind=proof_kind,
        proof_file_id=proof_file_id,
        proof_file_unique_id=proof_file_unique_id,
        proof_message_id=proof_message_id,
        metadata_json=metadata_json or {},
    )
    session.add(request)
    await session.flush()
    await log_event(
        session,
        LogAction.PAYMENT_CREATED,
        f"Solicitud de pago creada: {request.id}",
        target_user_id=user.id,
        details={
            "payment_request_id": request.id,
            "plan_id": plan.id,
            "payment_method_id": payment_method.id,
            "request_kind": request.metadata_json.get("request_kind"),
        },
    )
    if request.metadata_json.get("request_kind") == "renewal":
        await log_event(
            session,
            LogAction.MEMBERSHIP_RENEWAL_REQUESTED,
            f"Renovacion solicitada: pago {request.id}",
            target_user_id=user.id,
            details={
                "payment_request_id": request.id,
                "plan_id": plan.id,
                "renewal_membership_id": request.metadata_json.get("renewal_membership_id"),
            },
        )
    return request


async def list_pending_payment_requests(session: AsyncSession, limit: int = 20) -> list[PaymentRequest]:
    result = await session.scalars(
        _payment_request_options(select(PaymentRequest))
        .where(PaymentRequest.status == PaymentRequestStatus.PENDING)
        .order_by(PaymentRequest.submitted_at.desc())
        .limit(limit)
    )
    return list(result)


async def mark_payment_approved(
    session: AsyncSession,
    *,
    request: PaymentRequest,
    admin_user: User,
) -> None:
    if request.status != PaymentRequestStatus.PENDING:
        raise ValueError("Esta solicitud ya fue procesada.")
    request.status = PaymentRequestStatus.APPROVED
    request.reviewed_by_id = admin_user.id
    request.reviewed_at = utc_now()
    await log_event(
        session,
        LogAction.PAYMENT_APPROVED,
        f"Pago aprobado: {request.id}",
        actor_user_id=admin_user.id,
        target_user_id=request.user_id,
        details={"payment_request_id": request.id},
    )
    if request.metadata_json.get("request_kind") == "renewal":
        await log_event(
            session,
            LogAction.MEMBERSHIP_RENEWAL_APPROVED,
            f"Renovacion aprobada: pago {request.id}",
            actor_user_id=admin_user.id,
            target_user_id=request.user_id,
            details={
                "payment_request_id": request.id,
                "renewal_membership_id": request.metadata_json.get("renewal_membership_id"),
            },
        )


async def mark_payment_rejected(
    session: AsyncSession,
    *,
    request: PaymentRequest,
    admin_user: User,
    reason: str | None = None,
) -> None:
    if request.status != PaymentRequestStatus.PENDING:
        raise ValueError("Esta solicitud ya fue procesada.")
    request.status = PaymentRequestStatus.REJECTED
    request.reviewed_by_id = admin_user.id
    request.reviewed_at = utc_now()
    request.rejection_reason = reason or "Comprobante no aprobado."
    await log_event(
        session,
        LogAction.PAYMENT_REJECTED,
        f"Pago rechazado: {request.id}",
        actor_user_id=admin_user.id,
        target_user_id=request.user_id,
        details={"payment_request_id": request.id, "reason": request.rejection_reason},
    )
    if request.metadata_json.get("request_kind") == "renewal":
        await log_event(
            session,
            LogAction.MEMBERSHIP_RENEWAL_REJECTED,
            f"Renovacion rechazada: pago {request.id}",
            actor_user_id=admin_user.id,
            target_user_id=request.user_id,
            details={
                "payment_request_id": request.id,
                "renewal_membership_id": request.metadata_json.get("renewal_membership_id"),
                "reason": request.rejection_reason,
            },
        )


async def mark_payment_banned(
    session: AsyncSession,
    *,
    request: PaymentRequest,
    admin_user: User,
) -> None:
    request.status = PaymentRequestStatus.BANNED
    request.reviewed_by_id = admin_user.id
    request.reviewed_at = utc_now()
    request.user.status = UserStatus.BANNED
    request.user.banned_at = utc_now()
    await log_event(
        session,
        LogAction.USER_BANNED,
        f"Usuario baneado desde solicitud de pago: {request.id}",
        actor_user_id=admin_user.id,
        target_user_id=request.user_id,
        details={"payment_request_id": request.id},
    )
