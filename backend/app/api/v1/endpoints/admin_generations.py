"""Admin generation moderation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core import cache
from app.core.deps import require_admin
from app.models.generation import Generation
from app.models.credit_transaction import CreditTransaction
from app.models.user import User

router = APIRouter()


def _row_to_dict(gen: Generation, user: User | None) -> dict:
    return {
        "id": gen.id,
        "user_id": gen.user_id,
        "user_email": user.email if user else None,
        "user_name": user.full_name if user else None,
        "generation_type": gen.generation_type,
        "prompt": gen.prompt,
        "negative_prompt": gen.negative_prompt,
        "status": gen.status,
        "width": gen.width,
        "height": gen.height,
        "duration": gen.duration,
        "style": gen.style,
        "credits_used": gen.credits_used,
        "result_url": gen.result_url,
        "thumbnail_url": gen.thumbnail_url,
        "error_message": gen.error_message,
        "model_used": gen.model_used,
        "generation_time": gen.generation_time,
        "created_at": gen.created_at,
        "completed_at": gen.completed_at,
    }


@router.get("/generations")
async def list_admin_generations(
    q: str | None = None,
    type: str | None = None,
    status_filter: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 24,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """List all generations for admin moderation.

    Query params:
    - q: search prompt/user email/name
    - type: image/video/img2img/img2vid
    - status: queued/processing/completed/failed
    """
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 24), 100))
    effective_status = status_filter or status

    stmt = select(Generation, User).join(User, User.id == Generation.user_id, isouter=True)
    count_stmt = select(func.count(Generation.id)).select_from(Generation).join(User, User.id == Generation.user_id, isouter=True)

    filters = []
    if type:
        if type == "image":
            filters.append(Generation.generation_type.in_(["image", "img2img"]))
        elif type == "video":
            filters.append(Generation.generation_type.in_(["video", "img2vid"]))
        else:
            filters.append(Generation.generation_type == type)

    if effective_status:
        filters.append(Generation.status == effective_status)

    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Generation.prompt.ilike(pattern),
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
            )
        )

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    total = int((await db.execute(count_stmt)).scalar() or 0)
    rows = (
        await db.execute(
            stmt.order_by(Generation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return {
        "items": [_row_to_dict(gen, user) for gen, user in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/generations/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_generation(
    generation_id: int,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    result = await db.execute(select(Generation).where(Generation.id == generation_id))
    generation = result.scalar_one_or_none()
    if not generation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")

    await db.execute(
        update(CreditTransaction)
        .where(CreditTransaction.generation_id == generation.id)
        .values(generation_id=None)
    )
    await db.delete(generation)
    await db.flush()
    await cache.invalidate_admin_caches()
    return None
