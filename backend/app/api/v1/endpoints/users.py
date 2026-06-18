"""User endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, case, update, func

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.config import settings
from app.models.user import User
from app.services.identity_utils import normalize_email
from app.core import cache
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile"""
    
    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile"""
    
    # Check if email is already taken after stable lowercase normalization.
    normalized_email = normalize_email(user_update.email) if user_update.email else None
    if normalized_email:
        result = await db.execute(
            select(User).where(
                func.lower(User.email) == normalized_email,
                User.id != current_user_id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Build update data
    update_data = user_update.model_dump(exclude_unset=True)
    if normalized_email:
        update_data["email"] = normalized_email
    
    if update_data:
        await db.execute(
            update(User)
            .where(User.id == current_user_id)
            .values(**update_data)
        )
    
    # Get updated user
    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return UserResponse.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete current user account"""
    
    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Protect the last active admin from accidental self-deletion.
    is_admin = bool(user.is_admin) or (user.role or "").upper() in {"ADMIN", "SUPERADMIN"}
    if is_admin:
        active_admins = int((await db.execute(
            select(func.count(User.id)).where(
                User.is_active == True,  # noqa: E712
                (User.is_admin == True) | (User.role.in_(["ADMIN", "SUPERADMIN"])),  # noqa: E712
            )
        )).scalar() or 0)
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last active admin account",
            )

    # Soft-delete and anonymize PII while preserving referential integrity.
    user.is_active = False
    user.is_verified = False
    user.is_admin = False
    user.role = "USER"
    user.email = f"deleted_{user.id}@deleted.example.com"
    user.full_name = "Deleted User"
    await cache.delete_key(f"{settings.REFRESH_ALLOWLIST_PREFIX}:{user.id}")
    await cache.invalidate_admin_caches()
    await db.flush()
    
    return None


@router.get("/me/stats")
async def get_user_stats(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get user statistics"""
    
    from sqlalchemy import func
    from app.models.generation import Generation

    # SQLAlchemy 2.x fix: use sqlalchemy.case, not func.case.
    # Count img2img/img2vid with their media families so dashboard totals are correct.
    result = await db.execute(
        select(
            func.count(Generation.id).label("total"),
            func.coalesce(
                func.sum(case((Generation.generation_type.in_(["image", "img2img"]), 1), else_=0)),
                0,
            ).label("images"),
            func.coalesce(
                func.sum(case((Generation.generation_type.in_(["video", "img2vid"]), 1), else_=0)),
                0,
            ).label("videos"),
        )
        .where(Generation.user_id == current_user_id)
    )
    stats = result.one()

    return {
        "total_generations": int(stats.total or 0),
        "image_generations": int(stats.images or 0),
        "video_generations": int(stats.videos or 0),
    }
