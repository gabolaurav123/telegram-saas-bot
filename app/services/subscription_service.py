from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CRMStatus, LogAction, MembershipStatus
from app.models.membership import Membership
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.user import User
from app.services.crm import record_funnel_event, set_crm_status
from app.services.logs import log_event
from app.services.memberships import activate_membership, expire_membership
from app.utils.time import utc_now


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def activate(
        self,
        *,
        user: User,
        plan: Plan,
        payment_request: PaymentRequest,
        access_payload: dict | None = None,
    ) -> Membership:
        was_expired = bool(
            await self.session.scalar(
                select(Membership.id)
                .where(
                    Membership.user_id == user.id,
                    Membership.plan_id == plan.id,
                    Membership.status == MembershipStatus.EXPIRED,
                )
                .limit(1)
            )
        )
        membership = await activate_membership(
            self.session,
            user=user,
            plan=plan,
            payment_request=payment_request,
            access_payload=access_payload,
        )
        await set_crm_status(
            self.session,
            user=user,
            status=CRMStatus.RECOVERED if was_expired else CRMStatus.ACTIVE,
            reason="payment_approved",
            metadata={"payment_request_id": payment_request.id, "membership_id": membership.id},
        )
        await record_funnel_event(
            self.session,
            user=user,
            event_name="SUBSCRIPTION_RENEWED" if payment_request.metadata_json.get("request_kind") == "renewal" else "SUBSCRIPTION_ACTIVATED",
            plan_id=plan.id,
            payment_request_id=payment_request.id,
        )
        return membership

    async def extend(
        self,
        *,
        membership: Membership,
        new_expires_at,
        actor_user_id: int | None = None,
        reason: str = "manual_extend",
    ) -> Membership:
        old = membership.expires_at
        membership.expires_at = new_expires_at
        membership.status = MembershipStatus.ACTIVE
        await log_event(
            self.session,
            LogAction.MEMBERSHIP_EXTENDED,
            f"Membresia extendida: {membership.id}",
            actor_user_id=actor_user_id,
            target_user_id=membership.user_id,
            details={"old_expires_at": old.isoformat(), "new_expires_at": new_expires_at.isoformat(), "reason": reason},
        )
        return membership

    async def expire(self, *, membership: Membership) -> None:
        await expire_membership(self.session, membership)
        await set_crm_status(
            self.session,
            user=membership.user,
            status=CRMStatus.EXPIRED,
            reason="subscription_expired",
            metadata={"membership_id": membership.id},
        )
        await record_funnel_event(
            self.session,
            user=membership.user,
            event_name="SUBSCRIPTION_EXPIRED",
            plan_id=membership.plan_id,
            metadata={"membership_id": membership.id},
        )

    async def cancel(
        self,
        *,
        membership: Membership,
        actor_user_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        membership.status = MembershipStatus.CANCELLED
        membership.cancelled_at = utc_now()
        membership.revoke_reason = reason
        await log_event(
            self.session,
            LogAction.MEMBERSHIP_CANCELLED,
            f"Membresia cancelada: {membership.id}",
            actor_user_id=actor_user_id,
            target_user_id=membership.user_id,
            details={"membership_id": membership.id, "reason": reason},
        )

    async def suspend(
        self,
        *,
        membership: Membership,
        actor_user_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        membership.status = MembershipStatus.SUSPENDED
        membership.suspended_at = utc_now()
        membership.revoke_reason = reason
        await log_event(
            self.session,
            LogAction.MEMBERSHIP_SUSPENDED,
            f"Membresia suspendida: {membership.id}",
            actor_user_id=actor_user_id,
            target_user_id=membership.user_id,
            details={"membership_id": membership.id, "reason": reason},
        )

    async def restore(
        self,
        *,
        membership: Membership,
        actor_user_id: int | None = None,
    ) -> None:
        membership.status = MembershipStatus.ACTIVE
        membership.restored_at = utc_now()
        await log_event(
            self.session,
            LogAction.MEMBERSHIP_RESTORED,
            f"Membresia restaurada: {membership.id}",
            actor_user_id=actor_user_id,
            target_user_id=membership.user_id,
            details={"membership_id": membership.id},
        )
