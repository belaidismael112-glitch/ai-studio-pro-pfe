"""Dependency helpers (auth, admin, roles)"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User


async def get_current_user(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Backward-compatible admin check."""
    if getattr(user, "is_admin", False) or (getattr(user, "role", "").upper() in {"ADMIN", "SUPERADMIN"}):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def require_role(*allowed_roles: str):
    """
    Role-based dependency.
    Example:
        admin_user: User = Depends(require_role("ADMIN", "SUPERADMIN"))
    """
    allowed = {r.upper() for r in allowed_roles}

    async def _checker(user: User = Depends(get_current_user)) -> User:
        user_role = (getattr(user, "role", "") or "").upper()

        if getattr(user, "is_admin", False):
            return user

        if user_role in allowed:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return _checker