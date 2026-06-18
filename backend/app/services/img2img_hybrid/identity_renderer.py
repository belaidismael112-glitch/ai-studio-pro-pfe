from __future__ import annotations
from .contracts import RenderPlan, RenderResult
from .comfy_renderer import render_with_comfy
from .fallback import deterministic_identity_fallback


async def render_identity(plan: RenderPlan) -> RenderResult:
    plan.brief.negative_prompt = (plan.brief.negative_prompt + ", different person, changed face, face distortion").strip(", ")
    result = await render_with_comfy(plan)
    if result.success:
        return result
    fallback = deterministic_identity_fallback(plan)
    fallback.metadata["comfy_error"] = result.error
    return fallback
