from __future__ import annotations
from .contracts import RenderPlan, RenderResult
from .comfy_renderer import render_with_comfy
from .fallback import deterministic_product_fallback


async def render_creative(plan: RenderPlan) -> RenderResult:
    result = await render_with_comfy(plan)
    if result.success:
        return result
    fallback = deterministic_product_fallback(plan)
    fallback.metadata["comfy_error"] = result.error
    return fallback
