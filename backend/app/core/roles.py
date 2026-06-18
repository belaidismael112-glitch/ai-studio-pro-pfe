"""RBAC helpers.

We support a small set of roles while keeping backward compatibility with the
legacy `User.is_admin` boolean.

Roles (lowest → highest):
- USER
- PREMIUM
- ADMIN
- SUPERADMIN
"""

from __future__ import annotations

from enum import Enum
from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user
from app.models.user import User


class Role(str, Enum):
    USER = "USER"
    PREMIUM = "PREMIUM"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"


_ORDER = {
    Role.USER: 10,
    Role.PREMIUM: 20,
    Role.ADMIN: 90,
    Role.SUPERADMIN: 100,
}


def _effective_role(user: User) -> Role:
    """Map DB values to Role enum safely."""
    # Backward compatible: is_admin implies ADMIN.
    if getattr(user, "is_admin", False):
        return Role.ADMIN

    raw = (getattr(user, "role", None) or "USER").upper()
    try:
        return Role(raw)
    except Exception:
        return Role.USER


def require_role(min_role: Role):
    """Require user to have at least min_role."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        role = _effective_role(user)
        if _ORDER[role] < _ORDER[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _checker
