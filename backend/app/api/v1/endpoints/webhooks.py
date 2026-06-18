"""Stripe webhook endpoints with transactional idempotency.

Production rules:
- Stripe signature verification is mandatory.
- One Stripe event is reserved once through ``WebhookEvent``.
- One payment/invoice credits the wallet at most once through ``Payment``.
- Subscription Checkout activates the plan, while the paid invoice grants the
  monthly credits. This avoids the initial subscription invoice double-credit.
- Stripe unix timestamps are converted before writing DateTime columns.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.config import settings
from app.core.database import get_db
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User
from app.models.webhook_event import WebhookEvent
from app.services.credit_service import credit_service
from app.services.stripe_service import stripe_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _utc_datetime(value: Any) -> datetime | None:
    """Convert a Stripe unix timestamp to a naive UTC datetime for SQLAlchemy."""

    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    try:
        return datetime.fromtimestamp(int(value), UTC).replace(tzinfo=None)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _positive_int(value: Any) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    return resolved if resolved > 0 else None


def _subscription_price_id(subscription: Any) -> str | None:
    items = _value(subscription, "items")
    data = _value(items, "data", []) or []
    if not data:
        return None
    price = _value(data[0], "price")
    price_id = _value(price, "id")
    return str(price_id) if price_id else None


async def _reserve_webhook_event(db: AsyncSession, event_id: str, event_type: str) -> bool:
    """Reserve one Stripe event. False means it was already processed."""

    exists = await db.scalar(select(WebhookEvent.id).where(WebhookEvent.event_id == event_id))
    if exists:
        return False
    try:
        async with db.begin_nested():
            db.add(WebhookEvent(provider="stripe", event_id=event_id, event_type=event_type))
            await db.flush()
        return True
    except IntegrityError:
        return False


async def _record_payment_once(
    db: AsyncSession,
    *,
    user_id: int,
    provider_payment_id: str | None,
    payment_type: str,
    amount_minor: Any,
    currency: str | None,
) -> bool:
    """Write one payment ledger row. False means the Stripe payment was seen before."""

    if not provider_payment_id:
        raise HTTPException(status_code=400, detail="Stripe payment identifier is missing")
    payment_id = str(provider_payment_id)
    exists = await db.scalar(select(Payment.id).where(Payment.provider_payment_id == payment_id))
    if exists:
        return False
    try:
        amount = float(amount_minor or 0) / 100.0
    except (TypeError, ValueError):
        amount = 0.0
    try:
        async with db.begin_nested():
            db.add(
                Payment(
                    user_id=user_id,
                    provider="stripe",
                    provider_payment_id=payment_id,
                    payment_type=payment_type,
                    status="succeeded",
                    amount=amount,
                    currency=str(currency or "eur"),
                )
            )
            await db.flush()
        return True
    except IntegrityError:
        return False


async def _retrieve_subscription(stripe_subscription_id: str) -> Any:
    import stripe as stripe_lib

    return await asyncio.to_thread(stripe_lib.Subscription.retrieve, stripe_subscription_id)


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle signed Stripe webhooks without duplicate wallet mutations."""

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    event = stripe_service.construct_webhook_event(payload, sig_header)
    if not event:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    try:
        event_id = str(event["id"])
        event_type = str(event["type"])
        data = event["data"]["object"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Malformed Stripe event")

    if not await _reserve_webhook_event(db, event_id, event_type):
        logger.info("Ignoring duplicate Stripe event %s", event_id)
        return {"status": "success", "duplicate": True}

    logger.info("Received Stripe webhook: %s", event_type)
    try:
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(data, db)
        elif event_type == "invoice.payment_succeeded":
            await _handle_invoice_paid(data, db)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(data, db)
        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(data, db)
        await cache.invalidate_admin_caches()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error processing webhook %s: %s", event_type, exc)
        raise HTTPException(status_code=500, detail="Error processing webhook") from exc


async def _handle_checkout_completed(data: dict, db: AsyncSession) -> None:
    """Handle Stripe Checkout. Subscriptions are activated but not credited here."""

    metadata = data.get("metadata") or {}
    user_id = _positive_int(metadata.get("user_id"))
    purchase_type = str(metadata.get("type") or "")
    if not user_id:
        raise HTTPException(status_code=400, detail="Checkout metadata user_id is invalid")
    if not await db.scalar(select(User.id).where(User.id == user_id)):
        raise HTTPException(status_code=400, detail="Checkout user was not found")

    if purchase_type == "credit_purchase":
        package_id = str(metadata.get("package_id") or "")
        package = credit_service.get_credit_package(package_id)
        if not package:
            raise HTTPException(status_code=400, detail="Checkout credit package is invalid")
        inserted = await _record_payment_once(
            db,
            user_id=user_id,
            provider_payment_id=data.get("payment_intent") or data.get("id"),
            payment_type="credit_purchase",
            amount_minor=data.get("amount_total"),
            currency=data.get("currency"),
        )
        if inserted:
            await credit_service.add_credits(
                db,
                user_id,
                int(package["credits"]),
                transaction_type="purchase",
                description=f"Credit purchase: {package_id}",
                payment_intent_id=str(data.get("payment_intent") or data.get("id") or ""),
            )
            logger.info("Added %s credits to user %s", package["credits"], user_id)
        return

    if purchase_type != "subscription":
        raise HTTPException(status_code=400, detail="Checkout metadata type is invalid")

    tier = str(metadata.get("tier") or "")
    stripe_subscription_id = str(data.get("subscription") or "")
    if not stripe_subscription_id:
        raise HTTPException(status_code=400, detail="Stripe subscription identifier is missing")
    plan = next((p for p in stripe_service.get_subscription_plans() if p["id"] == tier), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Checkout subscription tier is invalid")

    stripe_sub = await _retrieve_subscription(stripe_subscription_id)
    period_start = _utc_datetime(_value(stripe_sub, "current_period_start"))
    period_end = _utc_datetime(_value(stripe_sub, "current_period_end"))
    stripe_customer_id = data.get("customer")

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            subscription_tier=tier,
            subscription_status=str(_value(stripe_sub, "status", "active") or "active"),
            subscription_expires_at=period_end,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )
    )

    existing = await db.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
    )
    values = dict(
        user_id=user_id,
        tier=tier,
        status=str(_value(stripe_sub, "status", "active") or "active"),
        stripe_subscription_id=stripe_subscription_id,
        stripe_price_id=_subscription_price_id(stripe_sub),
        current_period_start=period_start,
        current_period_end=period_end,
        amount=plan.get("price"),
        monthly_credits=int(plan.get("credits_per_month", 0) or 0),
    )
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
    else:
        db.add(Subscription(**values))

    # The initial and recurring invoice events are the single source of truth
    # for monthly wallet credits and subscription revenue.
    logger.info("Activated %s subscription for user %s", tier, user_id)


async def _handle_invoice_paid(data: dict, db: AsyncSession) -> None:
    """Handle one paid subscription invoice exactly once."""

    stripe_subscription_id = str(data.get("subscription") or "")
    invoice_id = str(data.get("id") or "")
    if not stripe_subscription_id or not invoice_id:
        return

    user = await db.scalar(select(User).where(User.stripe_subscription_id == stripe_subscription_id))
    if not user:
        # Invoice delivery can race checkout completion. Recover the user mapping
        # from metadata copied onto the Stripe subscription.
        stripe_sub = await _retrieve_subscription(stripe_subscription_id)
        metadata = _value(stripe_sub, "metadata", {}) or {}
        recovered_user_id = _positive_int(_value(metadata, "user_id"))
        if recovered_user_id:
            user = await db.scalar(select(User).where(User.id == recovered_user_id))
            if user:
                user.stripe_subscription_id = stripe_subscription_id
                user.stripe_customer_id = data.get("customer") or user.stripe_customer_id
    if not user:
        logger.warning("Invoice %s has no matching application user", invoice_id)
        return

    inserted = await _record_payment_once(
        db,
        user_id=user.id,
        provider_payment_id=invoice_id,
        payment_type="subscription_invoice",
        amount_minor=data.get("amount_paid"),
        currency=data.get("currency"),
    )
    if not inserted:
        return

    plan = next((p for p in stripe_service.get_subscription_plans() if p["id"] == user.subscription_tier), None)
    credits = int((plan or {}).get("credits_per_month", 0) or 0)
    if credits > 0:
        await credit_service.add_credits(
            db,
            user.id,
            credits,
            transaction_type="subscription",
            description=f"Monthly credits for {user.subscription_tier} subscription (invoice {invoice_id})",
            payment_intent_id=invoice_id,
        )
        logger.info("Added monthly credits (%s) for user %s", credits, user.id)


async def _handle_subscription_deleted(data: dict, db: AsyncSession) -> None:
    stripe_subscription_id = str(data.get("id") or "")
    if not stripe_subscription_id:
        return
    await db.execute(
        update(User)
        .where(User.stripe_subscription_id == stripe_subscription_id)
        .values(subscription_tier="free", subscription_status="inactive", stripe_subscription_id=None)
    )
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == stripe_subscription_id)
        .values(status="expired")
    )
    logger.info("Subscription %s expired", stripe_subscription_id)


async def _handle_subscription_updated(data: dict, db: AsyncSession) -> None:
    stripe_subscription_id = str(data.get("id") or "")
    if not stripe_subscription_id:
        return
    subscription_status = str(data.get("status") or "inactive")
    period_end = _utc_datetime(data.get("current_period_end"))
    await db.execute(
        update(User)
        .where(User.stripe_subscription_id == stripe_subscription_id)
        .values(subscription_status=subscription_status, subscription_expires_at=period_end)
    )
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == stripe_subscription_id)
        .values(status=subscription_status, current_period_end=period_end)
    )
