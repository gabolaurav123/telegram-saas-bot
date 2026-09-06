from __future__ import annotations

import secrets
from dataclasses import dataclass
from urllib.parse import parse_qs

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import CRMStateHistory, CRMTag, FunnelEvent, UserNote, UserTag
from app.models.enums import CRMStatus, LogAction
from app.models.growth import Referral
from app.models.user import User
from app.services.logs import log_event
from app.utils.time import utc_now


@dataclass(frozen=True)
class StartAttribution:
    raw: str | None
    source: str | None
    campaign: str | None
    referral: str | None


def parse_start_attribution(raw: str | None) -> StartAttribution:
    if not raw:
        return StartAttribution(None, None, None, None)
    value = raw.strip()
    normalized = value.replace("__", "&").replace("--", "&")
    parsed = parse_qs(normalized, keep_blank_values=False)
    source = _first(parsed, "source") or _first(parsed, "src")
    campaign = _first(parsed, "campaign") or _first(parsed, "camp")
    referral = _first(parsed, "referral") or _first(parsed, "ref") or _first(parsed, "r")
    if not any([source, campaign, referral]):
        if value.startswith("ref_"):
            referral = value[4:]
        elif value.startswith("src_"):
            source = value[4:]
        else:
            referral = value
    return StartAttribution(value, source, campaign, referral)


async def ensure_referral_code(session: AsyncSession, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    while True:
        code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
        exists = await session.scalar(select(User.id).where(User.referral_code == code))
        if not exists:
            user.referral_code = code
            return code


async def apply_start_attribution(
    session: AsyncSession,
    *,
    user: User,
    raw_parameter: str | None,
    is_first_start: bool,
) -> StartAttribution:
    now = utc_now()
    user.chat_id = user.telegram_id
    user.last_start_at = now
    user.last_contacted_at = now
    if user.first_started_at is None:
        user.first_started_at = now
    await ensure_referral_code(session, user)
    attribution = parse_start_attribution(raw_parameter)
    if attribution.raw:
        user.start_parameter = attribution.raw
    if attribution.source and not user.source:
        user.source = attribution.source[:120]
    if attribution.campaign and not user.campaign:
        user.campaign = attribution.campaign[:120]
    await set_crm_status(
        session,
        user=user,
        status=CRMStatus.LEAD if is_first_start else user.crm_status,
        reason="/start",
        metadata={"start_parameter": attribution.raw},
    )
    await record_funnel_event(
        session,
        user=user,
        event_name="START",
        source=attribution.source or user.source,
        campaign=attribution.campaign or user.campaign,
        metadata={"first_start": is_first_start, "referral": attribution.referral},
    )
    if attribution.referral:
        await _link_referral(session, user=user, referral_code=attribution.referral)
    return attribution


async def set_crm_status(
    session: AsyncSession,
    *,
    user: User,
    status: CRMStatus,
    reason: str | None = None,
    actor_user_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    current = user.crm_status
    if current == status:
        return
    user.crm_status = status
    user.is_vip = status == CRMStatus.VIP or user.is_vip
    if status == CRMStatus.BLOCKED:
        user.blocked_at = utc_now()
    history = CRMStateHistory(
        user_id=user.id,
        from_status=current,
        to_status=status,
        reason=reason,
        actor_user_id=actor_user_id,
        changed_at=utc_now(),
        metadata_json=metadata or {},
    )
    session.add(history)
    await log_event(
        session,
        LogAction.USER_CRM_STATUS_CHANGED,
        f"CRM {user.telegram_id}: {current.value if current else '-'} -> {status.value}",
        actor_user_id=actor_user_id,
        target_user_id=user.id,
        details={"from": current.value if current else None, "to": status.value, "reason": reason},
    )


async def record_funnel_event(
    session: AsyncSession,
    *,
    user: User | None,
    event_name: str,
    source: str | None = None,
    campaign: str | None = None,
    plan_id: int | None = None,
    payment_request_id: int | None = None,
    metadata: dict | None = None,
) -> FunnelEvent:
    event = FunnelEvent(
        user_id=user.id if user else None,
        event_name=event_name,
        source=source or (user.source if user else None),
        campaign=campaign or (user.campaign if user else None),
        plan_id=plan_id,
        payment_request_id=payment_request_id,
        occurred_at=utc_now(),
        metadata_json=metadata or {},
    )
    session.add(event)
    await log_event(
        session,
        LogAction.FUNNEL_EVENT,
        f"Funnel event: {event_name}",
        target_user_id=user.id if user else None,
        details={"event": event_name, "plan_id": plan_id, "payment_request_id": payment_request_id},
    )
    return event


async def add_user_note(
    session: AsyncSession,
    *,
    user: User,
    author: User | None,
    note: str,
) -> UserNote:
    record = UserNote(user_id=user.id, author_user_id=author.id if author else None, note=note.strip())
    session.add(record)
    return record


async def add_user_tag(
    session: AsyncSession,
    *,
    user: User,
    tag_name: str,
    actor: User | None = None,
) -> CRMTag:
    normalized = tag_name.strip().lower()
    if not normalized:
        raise ValueError("Etiqueta vacia.")
    tag = await session.scalar(select(CRMTag).where(CRMTag.name == normalized))
    if tag is None:
        tag = CRMTag(name=normalized)
        session.add(tag)
        await session.flush()
    existing = await session.scalar(
        select(UserTag.id).where(UserTag.user_id == user.id, UserTag.tag_id == tag.id)
    )
    if not existing:
        session.add(UserTag(user_id=user.id, tag_id=tag.id, added_by_user_id=actor.id if actor else None))
    return tag


async def _link_referral(session: AsyncSession, *, user: User, referral_code: str) -> None:
    referrer = await session.scalar(select(User).where(User.referral_code == referral_code))
    if referrer is None or referrer.id == user.id or user.referred_by_user_id:
        return
    user.referred_by_user_id = referrer.id
    exists = await session.scalar(
        select(Referral.id).where(
            Referral.referrer_user_id == referrer.id,
            Referral.referred_user_id == user.id,
        )
    )
    if exists:
        return
    session.add(Referral(referrer_user_id=referrer.id, referred_user_id=user.id))
    await log_event(
        session,
        LogAction.REFERRAL_CREATED,
        f"Referral registrado: {referrer.telegram_id} -> {user.telegram_id}",
        actor_user_id=referrer.id,
        target_user_id=user.id,
    )


def _first(values: dict[str, list[str]], key: str) -> str | None:
    current = values.get(key)
    if not current:
        return None
    return current[0] or None
