from __future__ import annotations

from app.services.img2img_design import render_category_flyer
from .contracts import RenderPlan, RenderResult


def render_flyer(plan: RenderPlan, output_dir: str) -> RenderResult:
    """Category-based design-engine flyer entrypoint.

    This intentionally replaces the old single-template flyer renderer. The
    engine chooses a category-specific template (handbag packshot, watch
    lifestyle, cosmetics, bottle, food, tech, generic) and never returns the
    old fallback poster as a successful result.
    """
    return render_category_flyer(plan, output_dir)
