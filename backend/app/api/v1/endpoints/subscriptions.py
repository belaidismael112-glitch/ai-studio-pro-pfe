"""Subscription endpoints"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user_id
from app.models.user import User
from app.models.subscription import Subscription
from app.schemas.subscription import (
    SubscriptionPlan,
    SubscriptionResponse,
    SubscriptionCreateRequest,
    SubscriptionCheckoutResponse,
    SubscriptionCancelResponse,
    SubscriptionTier,
)
from app.services.stripe_service import stripe_service
from app.services.credit_service import credit_service

router = APIRouter()


@router.get("/plans", response_model=list[SubscriptionPlan])
async def get_subscription_plans():
    """Get available subscription plans"""
    
    plans = stripe_service.get_subscription_plans()
    return [SubscriptionPlan(**plan) for plan in plans]


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get user's current subscription"""
    
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user_id)
        .where(Subscription.status.in_(["active", "trialing"]))
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .limit(1)
    )
    subscription = result.scalars().first()
    
    if not subscription:
        # Return free tier
        return SubscriptionResponse(
            id=0,
            tier=SubscriptionTier.FREE,
            status="active",
            current_period_end=None,
            monthly_credits=0,
            amount=0,
            currency="eur",
        )
    
    return SubscriptionResponse.model_validate(subscription)


@router.post("/subscribe", response_model=SubscriptionCheckoutResponse)
async def create_subscription(
    request: SubscriptionCreateRequest,
    req: Request,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create subscription checkout session"""
    
    # Get plan details
    plans = stripe_service.get_subscription_plans()
    plan = next((p for p in plans if p["id"] == request.tier.value), None)
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription tier"
        )
    
    if not settings.STRIPE_SECRET_KEY or not plan.get("stripe_price_id"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Subscription checkout is not configured. Configure Stripe and the selected STRIPE_PRICE_* value."
        )
    
    # Get user email
    result = await db.execute(
        select(User.email).where(User.id == current_user_id)
    )
    user_email = result.scalar()
    
    # Build URLs
    frontend_base = settings.FRONTEND_PUBLIC_URL.rstrip("/") if settings.FRONTEND_PUBLIC_URL else str(req.base_url).rstrip("/")
    success_url = f"{frontend_base}/settings?subscription=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{frontend_base}/settings?subscription=cancel"
    
    # Create Stripe session
    stripe_result = await asyncio.to_thread(
        stripe_service.create_subscription_session,
        user_id=current_user_id,
        tier=request.tier.value,
        stripe_price_id=plan["stripe_price_id"],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
    )
    
    if not stripe_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=stripe_result.get("error", "Failed to create checkout session")
        )
    
    return SubscriptionCheckoutResponse(
        checkout_url=stripe_result["checkout_url"],
        session_id=stripe_result["session_id"],
    )


@router.post("/cancel", response_model=SubscriptionCancelResponse)
async def cancel_subscription(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Cancel current subscription"""
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found"
        )
    
    # Cancel in Stripe
    cancel_result = await asyncio.to_thread(
        stripe_service.cancel_subscription, user.stripe_subscription_id
    )
    
    if not cancel_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=cancel_result.get("error", "Failed to cancel subscription")
        )
    
    # Update user
    user.subscription_status = "canceled"
    
    canceled_at = cancel_result.get("canceled_at")
    if canceled_at is not None and not isinstance(canceled_at, datetime):
        try:
            canceled_at = datetime.fromtimestamp(int(canceled_at), tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OSError):
            canceled_at = None

    # Update subscription record
    await db.execute(
        update(Subscription)
        .where(Subscription.stripe_subscription_id == user.stripe_subscription_id)
        .values(status="canceled", canceled_at=canceled_at)
    )
    
    await db.flush()
    
    return SubscriptionCancelResponse(
        success=True,
        message="Subscription will be canceled at the end of the current period",
        current_period_end=user.subscription_expires_at,
    )
