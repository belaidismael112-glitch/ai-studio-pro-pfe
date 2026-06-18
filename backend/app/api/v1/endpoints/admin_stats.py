"""Admin analytics endpoints"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.cache import make_key, get_json, set_json
from app.models.user import User
from app.models.generation import Generation
from app.models.payment import Payment
from app.models.support_ticket import SupportTicket

router = APIRouter()


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    key = make_key("admin_overview_v2", [])
    cached = await get_json(key)
    if cached:
        return cached

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    active_users = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar() or 0  # noqa: E712
    admin_users = (await db.execute(select(func.count(User.id)).where(User.is_admin == True))).scalar() or 0  # noqa: E712
    total_credits = (await db.execute(select(func.coalesce(func.sum(User.credits), 0)))).scalar() or 0

    total_generations = (await db.execute(select(func.count(Generation.id)))).scalar() or 0
    completed_generations = (await db.execute(select(func.count(Generation.id)).where(Generation.status == "completed"))).scalar() or 0
    failed_generations = (await db.execute(select(func.count(Generation.id)).where(Generation.status == "failed"))).scalar() or 0
    image_generations = (
        await db.execute(
            select(func.count(Generation.id)).where(Generation.generation_type.in_(["image", "img2img"]))
        )
    ).scalar() or 0
    video_generations = (
        await db.execute(
            select(func.count(Generation.id)).where(Generation.generation_type.in_(["video", "img2vid"]))
        )
    ).scalar() or 0

    total_revenue = (
        (await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0.0)).where(Payment.status == "succeeded")
        )).scalar()
        or 0.0
    )

    open_tickets = (
        await db.execute(
            select(func.count(SupportTicket.id)).where(
                SupportTicket.is_deleted == False,  # noqa: E712
                SupportTicket.status.in_(["open", "in_progress"]),
            )
        )
    ).scalar() or 0

    payload = {
        "total_users": int(total_users),
        "active_users": int(active_users),
        "admin_users": int(admin_users),
        "total_credits": int(total_credits),
        "total_generations": int(total_generations),
        "completed_generations": int(completed_generations),
        "failed_generations": int(failed_generations),
        "image_generations": int(image_generations),
        "video_generations": int(video_generations),
        "total_revenue": float(total_revenue),
        "open_tickets": int(open_tickets),
    }
    await set_json(key, payload, ttl_seconds=60)
    return payload


@router.get("/generations_per_day")
async def generations_per_day(days: int = 30, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    days = max(1, min(days, 365))
    key = make_key("admin_gpd", [days])
    cached = await get_json(key)
    if cached:
        return cached

    start = datetime.utcnow() - timedelta(days=days - 1)

    rows = (
        await db.execute(
            select(Generation.created_at)
            .where(Generation.created_at >= start)
            .order_by(Generation.created_at.asc())
        )
    ).scalars().all()

    counts: dict[str, int] = {}
    for value in rows:
        if not value:
            continue
        day = value.date().isoformat()
        counts[day] = counts.get(day, 0) + 1

    data = []
    for i in range(days):
        day = (start + timedelta(days=i)).date().isoformat()
        data.append({"day": day, "count": counts.get(day, 0)})

    payload = {"days": days, "data": data}
    await set_json(key, payload, ttl_seconds=60)
    return payload


@router.get("/revenue")
async def revenue(range: str = "month", db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    # range: day | week | month | all
    range = range.lower()
    if range not in {"day", "week", "month", "all"}:
        range = "month"

    key = make_key("admin_rev", [range])
    cached = await get_json(key)
    if cached:
        return cached

    now = datetime.utcnow()
    if range == "day":
        start = now - timedelta(days=1)
    elif range == "week":
        start = now - timedelta(days=7)
    elif range == "month":
        start = now - timedelta(days=30)
    else:
        start = None

    stmt = select(func.coalesce(func.sum(Payment.amount), 0.0)).where(Payment.status == "succeeded")
    if start is not None:
        stmt = stmt.where(Payment.created_at >= start)

    total = (await db.execute(stmt)).scalar() or 0.0
    payload = {"range": range, "total": float(total)}
    await set_json(key, payload, ttl_seconds=60)
    return payload


@router.get("/top_models")
async def top_models(days: int = 30, db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    days = max(1, min(days, 365))
    key = make_key("admin_top_models", [days])
    cached = await get_json(key)
    if cached:
        return cached

    start = datetime.utcnow() - timedelta(days=days)

    stmt = select(
        Generation.model_used,
        func.count(Generation.id).label("count"),
        func.avg(Generation.generation_time).label("avg_time"),
    ).where(
        Generation.created_at >= start,
        Generation.status == "completed",
    ).group_by(Generation.model_used).order_by(func.count(Generation.id).desc()).limit(10)

    rows = (await db.execute(stmt)).all()
    data = []
    for model_used, count, avg_time in rows:
        data.append({
            "model": model_used or "unknown",
            "count": int(count or 0),
            "avg_time": float(avg_time or 0.0),
        })

    payload = {"days": days, "data": data}
    await set_json(key, payload, ttl_seconds=60)
    return payload
