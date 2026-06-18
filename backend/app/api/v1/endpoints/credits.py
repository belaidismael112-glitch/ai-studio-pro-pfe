"""Credit endpoints"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.config import settings
from app.models.user import User
from app.schemas.credit import (
    CreditBalanceResponse,
    CreditTransactionResponse,
    CreditPackage,
    CreditPurchaseRequest,
    CreditPurchaseResponse,
)
from app.services.credit_service import credit_service
from app.services.stripe_service import stripe_service

router = APIRouter()

LOCAL_PURCHASE_SESSION_PREFIX = "local-credit-"


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get user's credit balance"""
    
    result = await db.execute(
        select(User.credits, User.subscription_tier).where(User.id == current_user_id)
    )
    user_data = result.one()
    
    return CreditBalanceResponse(
        credits=user_data.credits,
        subscription_tier=user_data.subscription_tier,
    )


@router.get("/packages", response_model=list[CreditPackage])
async def get_credit_packages():
    """Get available credit packages"""
    
    packages = credit_service.get_credit_packages()
    return [CreditPackage(**pkg) for pkg in packages]


async def _create_credit_checkout_response(
    package_id: str,
    req: Request,
    current_user_id: int,
    db: AsyncSession,
) -> CreditPurchaseResponse:
    """Shared Stripe/local checkout creator used by all credit checkout aliases."""

    package_id = str(package_id or "").strip().lower()
    package = credit_service.get_credit_package(package_id)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID. Use starter, pro, or enterprise.",
        )

    # Real Stripe mode only. Never add credits from a package selection or a local
    # development purchase fallback. Credits must be credited by the Stripe webhook
    # after a completed Checkout Session. This prevents accidental balance inflation
    # when a frontend calls /purchase while the user is only selecting a pack.
    stripe_secret = str(getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    stripe_configured = bool(stripe_secret) and not stripe_secret.startswith("sk_test_HOT_") and "SECRET_KEY_MTA3EK" not in stripe_secret

    if not stripe_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Stripe Checkout is not configured. Add a real STRIPE_SECRET_KEY=sk_test_... "
                "to backend .env, save it, restart the backend, then try again. "
                "Local credit purchase is disabled for safety."
            ),
        )

    frontend_base = settings.FRONTEND_PUBLIC_URL.rstrip("/") if settings.FRONTEND_PUBLIC_URL else str(req.base_url).rstrip("/")
    success_url = f"{frontend_base}/credits?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{frontend_base}/credits?checkout=cancel"

    stripe_result = await asyncio.to_thread(
        stripe_service.create_credit_purchase_session,
        user_id=current_user_id,
        package_id=package_id,
        credits=package["credits"],
        amount=package["price"],
        success_url=success_url,
        cancel_url=cancel_url,
    )

    if not stripe_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=stripe_result.get("error", "Failed to create checkout session"),
        )

    checkout_url = str(stripe_result.get("checkout_url") or "").strip()
    if not checkout_url.startswith("https://checkout.stripe.com/"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe session was created without a valid hosted checkout URL.",
        )

    return CreditPurchaseResponse(
        checkout_url=checkout_url,
        session_id=stripe_result["session_id"],
    )


def _package_id_from_compat_payload(payload: dict | None) -> str:
    payload = payload or {}
    value = (
        payload.get("package_id")
        or payload.get("packageId")
        or payload.get("pack_id")
        or payload.get("packId")
        or payload.get("pack")
        or payload.get("id")
    )
    return str(value or "").strip().lower()


@router.post("/purchase", response_model=CreditPurchaseResponse)
async def purchase_credits(
    request: CreditPurchaseRequest,
    req: Request,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create checkout session for credit purchase."""

    return await _create_credit_checkout_response(
        request.package_id, req, current_user_id, db
    )


@router.post("/checkout", response_model=CreditPurchaseResponse)
async def checkout_credits_compat(
    req: Request,
    payload: dict | None = Body(default=None),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Compatibility alias for older frontends calling /credits/checkout."""

    package_id = _package_id_from_compat_payload(payload)
    if not package_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing package_id. Send {'package_id': 'starter'|'pro'|'enterprise'}.",
        )
    return await _create_credit_checkout_response(package_id, req, current_user_id, db)


@router.get("/checkout")
async def checkout_get_help():
    """Helpful response for accidental direct browser opens of /credits/checkout."""

    return {
        "detail": "Credit checkout must be started from the app with an authenticated POST request.",
        "method": "POST",
        "endpoint": "/api/v1/credits/purchase",
        "compat_endpoint": "/api/v1/credits/checkout",
        "body": {"package_id": "pro"},
    }


@router.get("/history", response_model=list[CreditTransactionResponse])
async def get_credit_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get credit transaction history"""
    
    transactions = await credit_service.get_transaction_history(
        db, current_user_id, limit, offset
    )
    
    return [CreditTransactionResponse.model_validate(t) for t in transactions]
