from __future__ import annotations

from .analyzer import decide_template
from .qc import design_qc
from .renderers.lifestyle import render_lifestyle
from .renderers.packshot import render_packshot
from .utils import open_source, production_size, save_canvas
from app.services.img2img_hybrid.contracts import RenderPlan, RenderResult
from app.services.img2img_hybrid.utils import backend_public_image_url


def render_category_flyer(plan: RenderPlan, output_dir: str) -> RenderResult:
    w, h = production_size(plan.final_width, plan.final_height)
    plan.final_width, plan.final_height = w, h
    src = open_source(plan.source_subject_path)
    if src is None:
        return RenderResult(False, error="Cannot open source image for design engine", provider="category-design-engine")
    decision = decide_template(plan)
    canvas = render_packshot(plan, src, decision, w, h) if decision.is_packshot else render_lifestyle(plan, src, decision, w, h)
    out = save_canvas(canvas, output_dir, prefix="generated_v10_category_flyer")
    qc = design_qc(out, (w, h))
    if not qc.get("ok"):
        return RenderResult(False, local_path=out, error=qc.get("reason"), provider="category-design-engine-qc-reject", metadata={"qc": qc})
    provider = f"category-design-engine-v4-{decision.template}-3060-no-fallback"
    return RenderResult(
        success=True,
        local_path=out,
        public_url=backend_public_image_url(out),
        renderer_used="category_based_design_engine",
        provider=provider,
        metadata={
            "renderer_version": "category-design-engine-v4-clean-packshot",
            "layout": decision.template,
            "category": decision.category,
            "decision_confidence": decision.confidence,
            "decision_reason": decision.reason,
            "is_packshot": decision.is_packshot,
            "final_size": [w, h],
            "fallback_used": False,
            "ai_backdrop_path": None,
            "final_local_path": out,
            "user_facing_local_path": out,
            "qc": qc,
        },
    )
