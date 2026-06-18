from __future__ import annotations

"""High-quality deterministic fallbacks for V10.

These are not placeholders. They provide a production-safe source-locked output
when ComfyUI is unavailable: clean scene, preserved subject, correct aspect,
readable copy, no fake generated logos/text.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .contracts import RenderPlan, RenderResult
from .utils import backend_public_image_url, ensure_output_dir, unique_name


def deterministic_product_fallback(plan: RenderPlan) -> RenderResult:
    if plan.mode == "background_replace":
        return deterministic_background_fallback(plan)
    if plan.mode == "person_identity":
        return deterministic_identity_fallback(plan)

    W, H = int(plan.final_width or 1024), int(plan.final_height or 1024)
    palette = plan.brief.palette or ["#111827", "#e5e7eb", "#ffffff"]
    dark = palette[0]
    mid = palette[1] if len(palette) > 1 else "#2a2a2a"
    accent = palette[2] if len(palette) > 2 else "#ffffff"

    canvas = Image.new("RGBA", (W, H), dark)
    draw = ImageDraw.Draw(canvas)
    _premium_background(draw, W, H, dark, mid, accent, plan.analysis.category)
    _paste(canvas, plan.source_subject_path, (int(W * 0.18), int(H * 0.16), int(W * 0.82), int(H * 0.78)), strong_shadow=True)

    if plan.mode in {"product_ad", "creative_image"}:
        _caption(canvas, plan)

    out = ensure_output_dir(plan.output_dir) / unique_name(f"generated_v10_{plan.mode}_fallback")
    canvas.convert("RGB").save(out, quality=96)
    return RenderResult(
        True,
        str(out),
        backend_public_image_url(str(out)),
        "deterministic_source_locked_composite",
        "v10-production-deterministic-fallback",
        metadata={"mode": plan.mode, "fallback": True},
    )


def deterministic_background_fallback(plan: RenderPlan) -> RenderResult:
    W, H = int(plan.final_width or 1024), int(plan.final_height or 1024)
    canvas = Image.new("RGBA", (W, H), "#111827")
    draw = ImageDraw.Draw(canvas)
    _premium_background(draw, W, H, "#111827", "#d6c2a2", "#ffffff", plan.analysis.category)
    _paste(canvas, plan.source_subject_path, (int(W * 0.08), int(H * 0.08), int(W * 0.92), int(H * 0.92)), strong_shadow=True)
    out = ensure_output_dir(plan.output_dir) / unique_name("generated_v10_background_fallback")
    canvas.convert("RGB").save(out, quality=96)
    return RenderResult(True, str(out), backend_public_image_url(str(out)), "deterministic_background_replace", "v10-production-fallback", metadata={"mode": plan.mode, "fallback": True})


def deterministic_identity_fallback(plan: RenderPlan) -> RenderResult:
    W, H = int(plan.final_width or 1024), int(plan.final_height or 1024)
    canvas = Image.new("RGBA", (W, H), "#111827")
    draw = ImageDraw.Draw(canvas)
    _premium_background(draw, W, H, "#111827", "#334155", "#f8fafc", "portrait")
    _paste(canvas, plan.source_subject_path, (int(W * 0.10), int(H * 0.06), int(W * 0.90), int(H * 0.94)), strong_shadow=False)
    out = ensure_output_dir(plan.output_dir) / unique_name("generated_v10_identity_fallback")
    canvas.convert("RGB").save(out, quality=96)
    return RenderResult(True, str(out), backend_public_image_url(str(out)), "deterministic_identity_preserve", "v10-production-fallback", metadata={"mode": plan.mode, "fallback": True})


def _premium_background(draw: ImageDraw.ImageDraw, W: int, H: int, dark: str, mid: str, accent: str, category: str | None) -> None:
    category = (category or "").lower()
    draw.rectangle([0, 0, W, H], fill=dark)
    if category == "beverage":
        draw.rectangle([int(W * 0.55), 0, W, H], fill="#b91c1c")
        draw.ellipse([int(W * 0.48), -80, W + int(W * 0.25), int(H * 0.70)], fill="#ef4444")
        draw.ellipse([int(W * 0.58), int(H * 0.18), W + int(W * 0.06), int(H * 0.76)], outline="#ffffff", width=max(2, W // 260))
    else:
        draw.polygon([(int(W * 0.45), 0), (W, 0), (W, H), (int(W * 0.55), H)], fill=mid)
        draw.ellipse([int(W * 0.52), int(H * 0.08), W + int(W * 0.18), int(H * 0.88)], fill=accent)
        draw.ellipse([int(W * 0.60), int(H * 0.20), W + int(W * 0.06), int(H * 0.75)], outline="#ffffff", width=max(2, W // 260))
    draw.rounded_rectangle([int(W * 0.12), int(H * 0.12), int(W * 0.88), int(H * 0.84)], radius=max(24, W // 30), outline=(255, 255, 255, 42), width=max(1, W // 420))


def _caption(canvas: Image.Image, plan: RenderPlan) -> None:
    from .flyer_renderer import _draw_wrapped, _font

    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)
    x, y = int(W * 0.06), int(H * 0.06)
    maxw = int(W * 0.40)
    title = (plan.brief.title or "PREMIUM CAMPAIGN").upper()
    subtitle = plan.brief.subtitle or "Commercial source-preserved visual."
    draw.rounded_rectangle([x - 18, y - 16, x + maxw + 18, y + int(H * 0.16)], radius=22, fill=(0, 0, 0, 125))
    _draw_wrapped(draw, title, x, y, maxw, _font(max(24, W // 25), True), "#ffffff", max_lines=2)
    _draw_wrapped(draw, subtitle, x, y + int(H * 0.10), maxw, _font(max(14, W // 60)), "#e5e7eb", max_lines=2)


def _paste(canvas: Image.Image, path: str | None, box: tuple[int, int, int, int], strong_shadow: bool = True) -> None:
    if not path:
        return
    try:
        im = ImageOps.exif_transpose(Image.open(path).convert("RGBA"))
    except Exception:
        return
    x1, y1, x2, y2 = box
    im.thumbnail((x2 - x1, y2 - y1), Image.LANCZOS)
    px = x1 + (x2 - x1 - im.width) // 2
    py = y1 + (y2 - y1 - im.height) // 2
    if strong_shadow:
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse([px + 20, py + im.height - 18, px + im.width - 20, py + im.height + 32], fill=(0, 0, 0, 115))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(10, canvas.width // 70))))
    canvas.alpha_composite(im, (px, py))
