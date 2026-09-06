from __future__ import annotations

import secrets
from decimal import Decimal

from aiogram import Bot
from aiogram.types import LabeledPrice, SuccessfulPayment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.models.enums import CRMStatus, LogAction, MembershipStatus, PaymentProvider, PaymentRequestStatus, ProofKind
from app.models.membership import Membership
from app.models.payment_integration import ExternalPaymentSession
from app.models.payment_integration import TelegramStarsPayment
from app.models.payment_method import PaymentMethod
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.services.antifraud import analyze_and_store_receipt
from app.services.channels import create_invite_links_for_plan
from app.services.crm import record_funnel_event, set_crm_status
from app.services.logs import log_event
from app.services.payments import create_payment_request, mark_payment_approved, mark_payment_rejected
from app.services.subscription_service import SubscriptionService
from app.utils.time import utc_now


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_manual_payment(
        self,
        *,
        bot: Bot,
        settings: Settings,
        user: User,
        plan: Plan,
        payment_method: PaymentMethod,
        proof_kind: ProofKind,
        proof_file_id: str,
        proof_file_unique_id: str | None,
        proof_message_id: int | None,
        metadata_json: dict | None = None,
    ) -> PaymentRequest:
        request = await create_payment_request(
            self.session,
            user=user,
            plan=plan,
            payment_method=payment_method,
            proof_kind=proof_kind,
            proof_file_id=proof_file_id,
            proof_file_unique_id=proof_file_unique_id,
            proof_message_id=proof_message_id,
            metadata_json=metadata_json,
        )
        await set_crm_status(self.session, user=user, status=CRMStatus.RECEIPT_SUBMITTED, reason="receipt_submitted")
        await record_funnel_event(
            self.session,
            user=user,
            event_name="RECEIPT_SUBMITTED",
            plan_id=plan.id,
            payment_request_id=request.id,
        )
        await analyze_and_store_receipt(bot=bot, session=self.session, settings=settings, request=request)
        return request

    async def approve_manual_payment(
        self,
        *,
        bot: Bot,
        settings: Settings,
        request: PaymentRequest,
        admin_user: User,
    ) -> tuple[Membership, list[tuple[str, str]]]:
        await mark_payment_approved(self.session, request=request, admin_user=admin_user)
        await record_funnel_event(
            self.session,
            user=request.user,
            event_name="PAYMENT_APPROVED",
            plan_id=request.plan_id,
            payment_request_id=request.id,
        )
        return await self.fulfill_approved_payment(
            bot=bot,
            settings=settings,
            request=request,
            approved_by=admin_user,
        )

    async def fulfill_approved_payment(
        self,
        *,
        bot: Bot,
        settings: Settings,
        request: PaymentRequest,
        approved_by: User | None,
    ) -> tuple[Membership, list[tuple[str, str]]]:
        existing_membership = await self.session.scalar(
            select(Membership).where(Membership.payment_request_id == request.id)
        )
        if existing_membership:
            return existing_membership, []
        subscription_service = SubscriptionService(self.session)
        membership = await subscription_service.activate(
            user=request.user,
            plan=request.plan,
            payment_request=request,
            access_payload={
                "approved_by": approved_by.telegram_id if approved_by else None,
                "request_kind": request.metadata_json.get("request_kind", "purchase"),
                "renewal_membership_id": request.metadata_json.get("renewal_membership_id"),
            },
        )
        membership.plan = request.plan
        links = await create_invite_links_for_plan(
            bot=bot,
            session=self.session,
            plan=request.plan,
            user=request.user,
            membership=membership,
            payment_request=request,
            approved_by=approved_by,
            settings=settings,
        )
        membership.access_payload = {
            **(membership.access_payload or {}),
            "links_created": len(links),
        }
        return membership, links

    async def reject_payment(
        self,
        *,
        request: PaymentRequest,
        admin_user: User,
        reason: str | None = None,
    ) -> None:
        await mark_payment_rejected(self.session, request=request, admin_user=admin_user, reason=reason)
        await set_crm_status(
            self.session,
            user=request.user,
            status=CRMStatus.INTERESTED,
            reason="payment_rejected",
            actor_user_id=admin_user.id,
            metadata={"payment_request_id": request.id},
        )
        await record_funnel_event(
            self.session,
            user=request.user,
            event_name="PAYMENT_REJECTED",
            plan_id=request.plan_id,
            payment_request_id=request.id,
        )

    async def create_stars_invoice(
        self,
        *,
        settings: Settings,
        user: User,
        plan: Plan,
        payment_method: PaymentMethod,
        subscription_period: int | None = None,
        metadata_json: dict | None = None,
    ) -> tuple[PaymentRequest, TelegramStarsPayment, list[LabeledPrice]]:
        if not settings.telegram_stars_enabled:
            raise ValueError("Telegram Stars esta desactivado.")
        if payment_method.provider != PaymentProvider.TELEGRAM_STARS:
            raise ValueError("El metodo seleccionado no es Telegram Stars.")
        amount_stars = _stars_amount(plan, settings)
        payload = f"stars:{plan.id}:{user.id}:{secrets.token_urlsafe(16)}"[:128]
        request = PaymentRequest(
            user_id=user.id,
            plan_id=plan.id,
            payment_method_id=payment_method.id,
            status=PaymentRequestStatus.INVOICE_CREATED,
            amount=Decimal(amount_stars),
            currency="XTR",
            invoice_payload=payload,
            metadata_json={
                "provider": PaymentProvider.TELEGRAM_STARS.value,
                "subscription_period": subscription_period,
                **(metadata_json or {}),
            },
        )
        self.session.add(request)
        await self.session.flush()
        stars_payment = TelegramStarsPayment(
            user_id=user.id,
            plan_id=plan.id,
            payment_request_id=request.id,
            invoice_payload=payload,
            amount_stars=amount_stars,
            subscription_period=subscription_period,
        )
        self.session.add(stars_payment)
        await set_crm_status(self.session, user=user, status=CRMStatus.PAYMENT_PENDING, reason="stars_invoice")
        await record_funnel_event(
            self.session,
            user=user,
            event_name="PAYMENT_STARTED",
            plan_id=plan.id,
            payment_request_id=request.id,
            metadata={"provider": PaymentProvider.TELEGRAM_STARS.value},
        )
        await log_event(
            self.session,
            LogAction.TELEGRAM_STARS_INVOICE_CREATED,
            f"Invoice Stars creado: pago {request.id}",
            target_user_id=user.id,
            details={"payment_request_id": request.id, "payload": payload, "amount_stars": amount_stars},
        )
        return request, stars_payment, [LabeledPrice(label=plan.name[:32], amount=amount_stars)]

    async def create_external_payment_session(
        self,
        *,
        settings: Settings,
        user: User,
        plan: Plan,
        payment_method: PaymentMethod,
        provider: str,
        provider_session_id: str,
        checkout_url: str,
    ) -> tuple[PaymentRequest, ExternalPaymentSession]:
        if not settings.external_payments_enabled:
            raise ValueError("Pagos externos desactivados.")
        request = PaymentRequest(
            user_id=user.id,
            plan_id=plan.id,
            payment_method_id=payment_method.id,
            status=PaymentRequestStatus.INVOICE_CREATED,
            amount=plan.price,
            currency=plan.currency,
            reference=provider_session_id,
            provider_payment_id=provider_session_id,
            metadata_json={"provider": provider},
        )
        self.session.add(request)
        await self.session.flush()
        external_session = ExternalPaymentSession(
            user_id=user.id,
            plan_id=plan.id,
            payment_request_id=request.id,
            provider=provider,
            provider_session_id=provider_session_id,
            checkout_url=checkout_url,
            amount=plan.price,
            currency=plan.currency,
        )
        self.session.add(external_session)
        await set_crm_status(self.session, user=user, status=CRMStatus.PAYMENT_PENDING, reason="external_payment")
        await record_funnel_event(
            self.session,
            user=user,
            event_name="EXTERNAL_PAYMENT_STARTED",
            plan_id=plan.id,
            payment_request_id=request.id,
            metadata={"provider": provider},
        )
        return request, external_session

    async def approve_pre_checkout(self, *, payload: str) -> bool:
        record = await self.session.scalar(
            select(TelegramStarsPayment).where(TelegramStarsPayment.invoice_payload == payload)
        )
        return record is not None and record.status not in {"PAID", "REFUNDED"}

    async def process_successful_stars_payment(
        self,
        *,
        successful_payment: SuccessfulPayment,
    ) -> PaymentRequest | None:
        payload = successful_payment.invoice_payload
        stars_payment = await self.session.scalar(
            select(TelegramStarsPayment)
            .options(selectinload(TelegramStarsPayment.payment_request).selectinload(PaymentRequest.user))
            .where(TelegramStarsPayment.invoice_payload == payload)
        )
        if stars_payment is None:
            return None
        request = await self.session.scalar(
            select(PaymentRequest)
            .options(
                selectinload(PaymentRequest.user),
                selectinload(PaymentRequest.plan).selectinload(Plan.channels),
                selectinload(PaymentRequest.plan).selectinload(Plan.groups),
                selectinload(PaymentRequest.payment_method),
            )
            .where(PaymentRequest.id == stars_payment.payment_request_id)
        )
        if request is None:
            return None
        if request.status == PaymentRequestStatus.APPROVED:
            return request

        stars_payment.status = "PAID"
        stars_payment.telegram_payment_charge_id = successful_payment.telegram_payment_charge_id
        stars_payment.provider_payment_charge_id = successful_payment.provider_payment_charge_id
        stars_payment.paid_at = utc_now()
        request.status = PaymentRequestStatus.APPROVED
        request.telegram_payment_charge_id = successful_payment.telegram_payment_charge_id
        request.provider_payment_id = successful_payment.provider_payment_charge_id
        request.reviewed_at = utc_now()
        await log_event(
            self.session,
            LogAction.TELEGRAM_STARS_PAYMENT_CONFIRMED,
            f"Pago Stars confirmado: {request.id}",
            target_user_id=request.user_id,
            details={
                "payment_request_id": request.id,
                "telegram_payment_charge_id": successful_payment.telegram_payment_charge_id,
            },
        )
        await record_funnel_event(
            self.session,
            user=request.user,
            event_name="PAYMENT_APPROVED",
            plan_id=request.plan_id,
            payment_request_id=request.id,
            metadata={"provider": PaymentProvider.TELEGRAM_STARS.value},
        )
        return request

    async def refund_stars_payment(
        self,
        *,
        telegram_payment_charge_id: str,
        actor_user_id: int | None = None,
    ) -> PaymentRequest | None:
        stars_payment = await self.session.scalar(
            select(TelegramStarsPayment).where(
                TelegramStarsPayment.telegram_payment_charge_id == telegram_payment_charge_id
            )
        )
        if stars_payment is None:
            return None
        request = await self.session.get(PaymentRequest, stars_payment.payment_request_id)
        stars_payment.status = "REFUNDED"
        stars_payment.refunded_at = utc_now()
        if request:
            request.status = PaymentRequestStatus.REFUNDED
            request.reviewed_at = utc_now()
            membership = await self.session.scalar(
                select(Membership).where(Membership.payment_request_id == request.id)
            )
            if membership:
                membership.status = MembershipStatus.REFUNDED
                membership.refunded_at = utc_now()
            await log_event(
                self.session,
                LogAction.TELEGRAM_STARS_PAYMENT_REFUNDED,
                f"Pago Stars reembolsado: {request.id}",
                actor_user_id=actor_user_id,
                target_user_id=request.user_id,
                details={"telegram_payment_charge_id": telegram_payment_charge_id},
            )
        return request


def _stars_amount(plan: Plan, settings: Settings) -> int:
    configured = (plan.metadata_json or {}).get("stars_amount")
    if configured:
        return max(1, int(configured))
    return max(1, int(round(float(plan.price) * settings.telegram_stars_default_ratio)))
