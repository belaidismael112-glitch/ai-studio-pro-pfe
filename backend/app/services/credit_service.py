"""Credit service - manages user credits

Key improvements:
- Atomic credit updates (prevents race conditions under concurrent requests)
- Optional generation_id support for refunds/bonuses tied to a generation
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.user import User
from app.models.credit_transaction import CreditTransaction

logger = logging.getLogger(__name__)


class CreditService:
    """Service for managing user credits"""

    # Credit packages
    CREDIT_PACKAGES = {
        "starter": {
            "id": "starter",
            "name": "Starter Pack",
            "credits": 500,
            "price": 9.99,
            "description": "Perfect for beginners",
        },
        "pro": {
            "id": "pro",
            "name": "Pro Pack",
            "credits": 2000,
            "price": 29.99,
            "description": "Best value for professionals",
        },
        "enterprise": {
            "id": "enterprise",
            "name": "Enterprise Pack",
            "credits": 10000,
            "price": 99.99,
            "description": "For high-volume users",
        },
    }

    @staticmethod
    async def get_balance(db: AsyncSession, user_id: int) -> int:
        """Get user's credit balance"""
        result = await db.execute(select(User.credits).where(User.id == user_id))
        return int(result.scalar() or 0)

    @staticmethod
    async def add_credits(
        db: AsyncSession,
        user_id: int,
        amount: int,
        transaction_type: str,
        description: Optional[str] = None,
        payment_intent_id: Optional[str] = None,
        generation_id: Optional[int] = None,
    ) -> CreditTransaction:
        """Add credits to user account (atomic)."""

        if amount <= 0:
            raise ValueError("amount must be positive")

        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(credits=User.credits + amount)
            .returning(User.credits)
        )
        res = await db.execute(stmt)
        new_balance = res.scalar_one_or_none()

        if new_balance is None:
            raise ValueError(f"User {user_id} not found")

        transaction = CreditTransaction(
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            payment_intent_id=payment_intent_id,
            generation_id=generation_id,
            balance_after=int(new_balance),
        )

        db.add(transaction)
        await db.flush()

        logger.info("Added %s credits to user %s. New balance: %s", amount, user_id, new_balance)
        return transaction

    @staticmethod
    async def deduct_credits(
        db: AsyncSession,
        user_id: int,
        amount: int,
        description: Optional[str] = None,
        generation_id: Optional[int] = None,
    ) -> Optional[CreditTransaction]:
        """Deduct credits from user account (atomic).

        Returns None if insufficient balance.
        """

        if amount <= 0:
            raise ValueError("amount must be positive")

        stmt = (
            update(User)
            .where(User.id == user_id, User.credits >= amount)
            .values(credits=User.credits - amount)
            .returning(User.credits)
        )
        res = await db.execute(stmt)
        new_balance = res.scalar_one_or_none()

        if new_balance is None:
            current = await CreditService.get_balance(db, user_id)
            if current < amount:
                logger.warning("User %s has insufficient credits: %s < %s", user_id, current, amount)
                return None
            raise ValueError(f"User {user_id} not found")

        transaction = CreditTransaction(
            user_id=user_id,
            amount=-amount,
            transaction_type="usage",
            description=description,
            generation_id=generation_id,
            balance_after=int(new_balance),
        )

        db.add(transaction)
        await db.flush()

        logger.info("Deducted %s credits from user %s. New balance: %s", amount, user_id, new_balance)
        return transaction

    @staticmethod
    async def has_sufficient_credits(db: AsyncSession, user_id: int, required: int) -> bool:
        """Check if user has sufficient credits"""
        balance = await CreditService.get_balance(db, user_id)
        return balance >= required

    @staticmethod
    async def get_transaction_history(
        db: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CreditTransaction]:
        """Get user's credit transaction history"""
        result = await db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    def get_credit_packages() -> list[dict]:
        """Get available credit packages"""
        return list(CreditService.CREDIT_PACKAGES.values())

    @staticmethod
    def get_credit_package(package_id: str) -> Optional[dict]:
        """Get a specific credit package"""
        return CreditService.CREDIT_PACKAGES.get(package_id)


# Singleton instance
credit_service = CreditService()
