"""Model catalog + comparison endpoints.

Usage statistics are normalized to stable pipeline ids. Generation.model_used may
contain a provider name (for example ``comfy``) after the worker finishes, while
queued rows may contain a checkpoint/model alias. The comparison page must not
silently show zeroes because those runtime values differ.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from app.core.database import get_db
from app.core.cache import make_key, get_json, set_json
from app.models.generation import Generation

router = APIRouter()

MODEL_CATALOG = [
    {
        "id": "text2img",
        "name": "Text-to-Image",
        "type": "image",
        "strengths": ["Local ComfyUI generation", "Commercial visuals", "Prompt-driven composition"],
        "weaknesses": ["Requires ComfyUI model files", "Depends on local GPU"],
        "recommended_for": ["Image generation", "Campaign visuals", "Creative visuals"],
    },
    {
        "id": "img2img",
        "name": "Image-to-Image Reference Studio",
        "type": "image",
        "strengths": ["Preserves the uploaded subject", "Identity, product, flyer and background modes", "Reference-aware transformations"],
        "weaknesses": ["Input image quality matters", "Mode and prompt choice affect results"],
        "recommended_for": ["Reference-based edits", "Identity lock", "Product ads", "Background replacement"],
    },
]


def normalize_pipeline_id(model_used: str | None, generation_type: str | None) -> str:
    """Map DB/runtime aliases to one stable comparison pipeline id."""

    gen_type = (generation_type or "").strip().lower()
    model = (model_used or "").strip().lower()

    if gen_type == "img2img" or "img2img" in model or "reference" in model:
        return "img2img"
    if gen_type == "image" or any(marker in model for marker in ("comfy", "flux", "sdxl", "replicate", "stability")):
        return "text2img"
    return "unknown"


@router.get("/models")
async def list_models():
    return {"models": MODEL_CATALOG}


@router.get("/models/compare")
async def compare_models(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Compare real image pipelines using Generation history."""

    days = max(1, min(days, 365))
    key = make_key("models_compare_v2", [days])
    cached = await get_json(key)
    if cached:
        return cached

    start = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(
            Generation.model_used,
            Generation.generation_type,
            func.count(Generation.id).label("count"),
            func.avg(Generation.generation_time).label("avg_time"),
            func.sum(case((Generation.status == "completed", 1), else_=0)).label("completed"),
            func.sum(case((Generation.status == "failed", 1), else_=0)).label("failed"),
        )
        .where(Generation.created_at >= start)
        .where(Generation.generation_type.in_(["image", "img2img"]))
        .group_by(Generation.model_used, Generation.generation_type)
    )

    rows = (await db.execute(stmt)).all()
    stats = {
        item["id"]: {"total": 0, "avg_time": 0.0, "success_rate": 0.0, "completed": 0, "failed": 0}
        for item in MODEL_CATALOG
    }
    stats["unknown"] = {"total": 0, "avg_time": 0.0, "success_rate": 0.0, "completed": 0, "failed": 0}
    weighted_time_total: dict[str, float] = {key: 0.0 for key in stats}

    for model_used, generation_type, count, avg_time, completed, failed in rows:
        pipeline_id = normalize_pipeline_id(model_used, generation_type)
        total = int(count or 0)
        target = stats.setdefault(
            pipeline_id,
            {"total": 0, "avg_time": 0.0, "success_rate": 0.0, "completed": 0, "failed": 0},
        )
        target["total"] += total
        target["completed"] += int(completed or 0)
        target["failed"] += int(failed or 0)
        weighted_time_total[pipeline_id] = weighted_time_total.get(pipeline_id, 0.0) + float(avg_time or 0.0) * total

    for pipeline_id, values in stats.items():
        total = int(values["total"] or 0)
        values["avg_time"] = weighted_time_total.get(pipeline_id, 0.0) / total if total else 0.0
        values["success_rate"] = float(values["completed"] / total) if total else 0.0

    payload = {"days": days, "catalog": MODEL_CATALOG, "stats": stats}
    await set_json(key, payload, ttl_seconds=120)
    return payload
