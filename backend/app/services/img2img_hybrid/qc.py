from __future__ import annotations

from pathlib import Path

from PIL import Image

from .contracts import RenderPlan, RenderResult


def check_quality(plan: RenderPlan, result: RenderResult) -> dict:
    if not result.success:
        return {"ok": False, "reason": result.error or "render failed"}
    if not result.local_path or not Path(result.local_path).exists():
        return {"ok": False, "reason": "missing output file"}

    try:
        im = Image.open(result.local_path).convert("RGB")
        w, h = im.size
    except Exception:
        return {"ok": False, "reason": "output is not a readable image"}

    if w < 512 or h < 512:
        return {"ok": False, "reason": f"output too small: {w}x{h}"}

    if plan.mode == "flyer_poster" and h <= w:
        return {"ok": False, "reason": f"flyer must be portrait, got {w}x{h}"}

    # Reject blank / near-solid outputs.
    stat = _image_variance(im)
    if stat < 35.0:
        return {"ok": False, "reason": "output appears blank or near-solid"}

    if plan.mode == "flyer_poster":
        title = (plan.brief.title or "").strip()
        cta = (plan.brief.cta or "").strip()
        if not title or not cta:
            return {"ok": False, "reason": "missing title or CTA"}

    return {"ok": True, "reason": "production V10 quality pass", "size": [w, h], "variance": round(stat, 2)}


def _image_variance(im: Image.Image) -> float:
    small = im.resize((64, 64)).convert("L")
    pix = list(small.getdata())
    mean = sum(pix) / len(pix)
    return sum((p - mean) ** 2 for p in pix) / len(pix)
