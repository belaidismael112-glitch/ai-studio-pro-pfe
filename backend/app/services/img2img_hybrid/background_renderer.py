from __future__ import annotations
from .contracts import RenderPlan, RenderResult
from .comfy_renderer import render_with_comfy
from .fallback import deterministic_background_fallback


async def render_background_replace(plan: RenderPlan) -> RenderResult:
    result = await render_with_comfy(plan)
    if result.success:
        return result
    fallback = deterministic_background_fallback(plan)
    fallback.metadata["comfy_error"] = result.error
    return fallback
