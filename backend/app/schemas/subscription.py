"""Subscription schemas"""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionPlan(BaseModel):
    id: str
    name: str
    tier: SubscriptionTier
    price: float
    currency: str = "eur"
    interval: str = "month"
    credits_per_month: int
    features: list[str]
    description: Optional[str] = None
    stripe_price_id: Optional[str] = None


class SubscriptionResponse(BaseModel):
    id: int
    tier: SubscriptionTier
    status: str
    current_period_end: Optional[datetime]
    monthly_credits: int
    amount: Optional[float]
    currency: str
    
    model_config = ConfigDict(from_attributes=True)


class SubscriptionCreateRequest(BaseModel):
    tier: SubscriptionTier


class SubscriptionCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SubscriptionCancelResponse(BaseModel):
    success: bool
    message: str
    current_period_end: Optional[datetime] = None
