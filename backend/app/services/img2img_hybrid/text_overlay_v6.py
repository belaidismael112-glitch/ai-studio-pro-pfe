from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from app.services.comfy_prompt_director_v6 import ComfyPromptPack


def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _fit(draw: ImageDraw.ImageDraw, text: str, font_path_bold: bool, max_width: int, start_size: int, min_size: int = 22):
    size = start_size
    while size >= min_size:
        f = _font(size, bold=font_path_bold)
        bbox = draw.textbbox((0, 0), text, font=f)
        if bbox[2] - bbox[0] <= max_width:
            return f
        size -= 2
    return _font(min_size, bold=font_path_bold)


def add_readable_flyer_overlay(image_path: str, pack: ComfyPromptPack, output_dir: str = "static/images") -> str:
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Top and bottom glass panels keep text readable without destroying Comfy's design.
    top_h = int(h * 0.18)
    bot_h = int(h * 0.15)
    d.rounded_rectangle((36, 36, w - 36, 36 + top_h), radius=32, fill=(8, 10, 14, 150))
    d.rounded_rectangle((48, h - bot_h - 46, w - 48, h - 46), radius=30, fill=(8, 10, 14, 165))

    title = (pack.overlay_title or "SUMMER PROMO").upper()
    subtitle = pack.overlay_subtitle or "Limited time only"
    cta = pack.overlay_cta or "Order now"

    title_font = _fit(d, title, True, w - 110, 58)
    sub_font = _fit(d, subtitle, False, w - 110, 30)
    cta_font = _fit(d, cta.upper(), True, w - 140, 36)

    d.text((58, 58), title, font=title_font, fill=(255, 255, 255, 255))
    d.text((60, 122), subtitle, font=sub_font, fill=(235, 222, 190, 255))
    d.text((70, h - bot_h - 12), cta.upper(), font=cta_font, fill=(255, 255, 255, 255))

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"generated_comfy_v6_flyer_final_{uuid4().hex}.png"
    composed.save(out, quality=96)
    return str(out)
