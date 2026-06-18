from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.core.database import async_session
from app.core.config import settings
from app.core import cache
from app.core.deps import require_role
from app.core.roles import Role
from app.core.security import get_password_hash
from app.models.user import User
from app.models.credit_transaction import CreditTransaction
from app.services.identity_utils import normalize_email
from app.schemas.admin_users import (
    AdminUserOut,
    AdminUserResetPassword,
    AdminUserRoleUpdate,
    AdminUserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin - Users"], dependencies=[Depends(require_role(Role.ADMIN))])


def _is_admin_account(user: User) -> bool:
    return bool(user.is_admin) or (user.role or "").upper() in {"ADMIN", "SUPERADMIN"}


async def _active_admin_count(db) -> int:
    return int((await db.execute(
        select(func.count(User.id)).where(
            User.is_active == True,  # noqa: E712
            (User.is_admin == True) | (User.role.in_(["ADMIN", "SUPERADMIN"])),  # noqa: E712
        )
    )).scalar() or 0)


async def _protect_admin_lockout(db, *, target: User, actor: User, removes_admin_access: bool) -> None:
    """Prevent accidental self-lockout and removal of the last active admin."""

    if not removes_admin_access or not target.is_active or not _is_admin_account(target):
        return
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot remove your own active admin access")
    if await _active_admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last active admin")


@router.get("", response_model=dict)
async def list_users(
    q: Optional[str] = Query(None, description="Search by email/full name"),
    is_active: Optional[bool] = None,
    role: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    offset = (page - 1) * page_size

    async with async_session() as db:
        stmt = select(User)

        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where((User.email.ilike(like)) | (User.full_name.ilike(like)))

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        if role:
            stmt = stmt.where(User.role == role)

        # Count and paginate inside the database. Loading every user into Python
        # becomes slow and memory-heavy once a production database grows.
        total = int((await db.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )).scalar() or 0)
        items = (await db.execute(
            stmt.order_by(User.created_at.desc(), User.id.desc()).offset(offset).limit(page_size)
        )).scalars().all()

        return {
            "items": [AdminUserOut.model_validate(u) for u in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.get("/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: int):
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return AdminUserOut.model_validate(user)


@router.patch("/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    admin_user: User = Depends(require_role(Role.ADMIN)),
):
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        data = payload.model_dump(exclude_unset=True)
        if data.get("email"):
            data["email"] = normalize_email(data["email"])
            duplicate = (
                await db.execute(
                    select(User).where(func.lower(User.email) == data["email"], User.id != user_id)
                )
            ).scalar_one_or_none()
            if duplicate:
                raise HTTPException(status_code=400, detail="Email already registered")

        removes_admin_access = (
            ("is_admin" in data and data["is_admin"] is False)
            or ("is_active" in data and data["is_active"] is False)
        )
        await _protect_admin_lockout(
            db, target=user, actor=admin_user, removes_admin_access=removes_admin_access
        )

        old_credits = int(user.credits or 0)
        new_credits = data.pop("credits", None)

        for k, v in data.items():
            setattr(user, k, v)

        if new_credits is not None:
            new_credits = int(new_credits)
            difference = new_credits - old_credits
            user.credits = new_credits
            if difference:
                db.add(CreditTransaction(
                    user_id=user.id,
                    amount=difference,
                    transaction_type="admin_adjustment",
                    description=f"Admin credit adjustment by user #{admin_user.id}",
                    balance_after=new_credits,
                ))

        # Keep the legacy is_admin flag and RBAC role synchronized. The admin UI
        # patches is_admin directly; older code silently ignored that field and
        # displayed a false Saved notice.
        if "is_admin" in data:
            if bool(data["is_admin"]):
                user.role = "ADMIN"
            elif (user.role or "").upper() in {"ADMIN", "SUPERADMIN"}:
                user.role = "USER"

        await db.commit()
        await cache.invalidate_admin_caches()
        await db.refresh(user)
        return AdminUserOut.model_validate(user)


@router.patch("/{user_id}/role", response_model=AdminUserOut)
async def update_role(
    user_id: int,
    payload: AdminUserRoleUpdate,
    admin_user: User = Depends(require_role(Role.ADMIN)),
):
    role = (payload.role or "").upper().strip()
    if role not in {"USER", "ADMIN"}:
        raise HTTPException(status_code=400, detail="Invalid role. Use USER or ADMIN")

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await _protect_admin_lockout(
            db, target=user, actor=admin_user, removes_admin_access=role != "ADMIN"
        )
        user.role = role
        user.is_admin = role == "ADMIN"
        await db.commit()
        await cache.invalidate_admin_caches()
        await db.refresh(user)
        return AdminUserOut.model_validate(user)


@router.post("/{user_id}/reset-password", response_model=dict)
async def reset_password(user_id: int, payload: AdminUserResetPassword):
    if not payload.new_password or len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.hashed_password = get_password_hash(payload.new_password)
        user.auth_token_version = int(user.auth_token_version or 0) + 1
        await db.commit()
        await cache.delete_key(f"{settings.REFRESH_ALLOWLIST_PREFIX}:{user.id}")
        return {"ok": True}


@router.delete("/{user_id}", response_model=dict)
async def soft_delete_user(
    user_id: int,
    admin_user: User = Depends(require_role(Role.ADMIN)),
):
    """Soft delete: deactivate and anonymize while protecting active admins."""

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.id == admin_user.id:
            raise HTTPException(status_code=400, detail="You cannot delete your own admin account")
        if _is_admin_account(user) and await _active_admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last active admin")

        user.is_active = False
        user.is_verified = False
        # keep uniqueness
        user.email = f"deleted_{user.id}@deleted.example.com"
        user.full_name = "Deleted User"
        user.is_admin = False
        user.role = "USER"

        await db.commit()
        await cache.delete_key(f"{settings.REFRESH_ALLOWLIST_PREFIX}:{user.id}")
        await cache.invalidate_admin_caches()
        return {"ok": True}
