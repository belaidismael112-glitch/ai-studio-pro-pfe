"""Credit schemas"""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class TransactionType(str, Enum):
    PURCHASE = "purchase"
    USAGE = "usage"
    BONUS = "bonus"
    REFUND = "refund"
    SUBSCRIPTION = "subscription"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class CreditPackage(BaseModel):
    id: str
    name: str
    credits: int
    price: float
    currency: str = "eur"
    description: Optional[str] = None


class CreditTransactionResponse(BaseModel):
    id: int
    amount: int
    transaction_type: TransactionType
    description: Optional[str]
    balance_after: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CreditBalanceResponse(BaseModel):
    credits: int
    subscription_tier: str
    monthly_credits_remaining: Optional[int] = None


class CreditPurchaseRequest(BaseModel):
    package_id: str


class CreditPurchaseResponse(BaseModel):
    checkout_url: str
    session_id: str
