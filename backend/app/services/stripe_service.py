"""Stripe service - handles payments and subscriptions"""

import logging
from typing import Optional
import stripe as stripe_lib

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Stripe
stripe_lib.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for Stripe payments and subscriptions"""
    
    # Subscription plans
    SUBSCRIPTION_PLANS = {
        "starter": {
            "id": "starter",
            "tier": "starter",
            "name": "Starter",
            "price": 9.99,
            "credits_per_month": 500,
            "features": [
                "500 credits per month",
                "Standard generation speed",
                "Email support",
                "Save generation history",
            ],
        },
        "pro": {
            "id": "pro",
            "tier": "pro",
            "name": "Pro",
            "price": 29.99,
            "credits_per_month": 2000,
            "features": [
                "2000 credits per month",
                "Priority generation speed",
                "Priority support",
                "Unlimited history",
                "API access",
            ],
        },
        "enterprise": {
            "id": "enterprise",
            "tier": "enterprise",
            "name": "Enterprise",
            "price": 99.99,
            "credits_per_month": 10000,
            "features": [
                "10000 credits per month",
                "Fastest generation speed",
                "Dedicated support",
                "Unlimited history",
                "Full API access",
                "Custom models",
            ],
        },
    }
    
    @staticmethod
    def create_credit_purchase_session(
        user_id: int,
        package_id: str,
        credits: int,
        amount: float,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """Create Stripe checkout session for credit purchase"""
        
        try:
            session = stripe_lib.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"AI Studio Pro - {credits} Credits",
                            "description": f"Purchase {credits} credits for AI generation",
                        },
                        "unit_amount": int(amount * 100),  # Convert to cents
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user_id),
                    "package_id": package_id,
                    "credits": str(credits),
                    "type": "credit_purchase",
                },
            )
            
            return {
                "success": True,
                "session_id": session.id,
                "checkout_url": session.url,
            }
        
        except stripe_lib.error.StripeError as e:
            logger.error(f"Stripe error creating credit session: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def create_subscription_session(
        user_id: int,
        tier: str,
        stripe_price_id: str,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
    ) -> dict:
        """Create Stripe checkout session for subscription"""
        
        try:
            # Create or retrieve customer
            customer = None
            if customer_email:
                customers = stripe_lib.Customer.list(email=customer_email, limit=1)
                if customers.data:
                    customer = customers.data[0]
                else:
                    customer = stripe_lib.Customer.create(email=customer_email)
            
            session_params = {
                "payment_method_types": ["card"],
                "line_items": [{
                    "price": stripe_price_id,
                    "quantity": 1,
                }],
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "user_id": str(user_id),
                    "tier": tier,
                    "type": "subscription",
                },
                # Copy identity metadata onto the subscription itself so a paid
                # invoice that races Checkout completion can still recover the
                # correct application user without granting duplicate credits.
                "subscription_data": {
                    "metadata": {
                        "user_id": str(user_id),
                        "tier": tier,
                        "type": "subscription",
                    }
                },
            }
            
            if customer:
                session_params["customer"] = customer.id
            
            session = stripe_lib.checkout.Session.create(**session_params)
            
            return {
                "success": True,
                "session_id": session.id,
                "checkout_url": session.url,
            }
        
        except stripe_lib.error.StripeError as e:
            logger.error(f"Stripe error creating subscription session: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> Optional[dict]:
        """Construct and verify Stripe webhook event"""
        
        try:
            event = stripe_lib.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            return None
        except stripe_lib.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            return None
    
    @staticmethod
    def cancel_subscription(stripe_subscription_id: str) -> dict:
        """Cancel a Stripe subscription"""
        
        try:
            subscription = stripe_lib.Subscription.delete(stripe_subscription_id)
            return {
                "success": True,
                "status": subscription.status,
                "canceled_at": subscription.canceled_at,
            }
        except stripe_lib.error.StripeError as e:
            logger.error(f"Stripe error canceling subscription: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_subscription_plans() -> list[dict]:
        """Get available subscription plans"""
        plans = []
        for plan_id, plan in StripeService.SUBSCRIPTION_PLANS.items():
            plan_copy = plan.copy()
            # Add Stripe price ID from settings
            if plan_id == "starter":
                plan_copy["stripe_price_id"] = settings.STRIPE_PRICE_STARTER
            elif plan_id == "pro":
                plan_copy["stripe_price_id"] = settings.STRIPE_PRICE_PRO
            elif plan_id == "enterprise":
                plan_copy["stripe_price_id"] = settings.STRIPE_PRICE_ENTERPRISE
            plans.append(plan_copy)
        return plans


# Singleton instance
stripe_service = StripeService()
