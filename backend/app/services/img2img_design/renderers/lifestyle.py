from __future__ import annotations

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from ..copy import build_copy
from ..utils import cover, font, paste_rounded_photo, radial, tint, draw_wrapped
from .common import draw_button, draw_text_stack


def render_lifestyle(plan, src: Image.Image, decision, w: int, h: int) -> Image.Image:
    copy = build_copy(plan, decision.category)
    if decision.template == "watch_lifestyle":
        return _watch_lifestyle(src, copy, w, h)
    return _editorial_photo(src, copy, decision.category, w, h)


def _footer(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    txt = 'SOURCE PRESERVED  •  CATEGORY ENGINE V4  •  3060 SAFE'
    f = font(8, True)
    bb = draw.textbbox((0, 0), txt, font=f)
    draw.text(((w - (bb[2] - bb[0])) // 2, h - 26), txt, font=f, fill=(255, 255, 255, 150))
    draw.rounded_rectangle([18, 18, w - 18, h - 18], radius=30, outline=(255, 255, 255, 55), width=1)


def _watch_lifestyle(src: Image.Image, copy, w: int, h: int) -> Image.Image:
    # Lifestyle watch should stay a premium photo editorial, not a handbag/product packshot.
    bg = cover(src, w, h, focus=(0.50, 0.50)).filter(ImageFilter.GaussianBlur(26)).convert("RGBA")
    bg = ImageEnhance.Color(bg).enhance(0.72)
    bg = ImageEnhance.Contrast(bg).enhance(0.92)
    canvas = tint(bg, (18, 13, 10), 154)
    draw = ImageDraw.Draw(canvas)

    canvas.alpha_composite(radial((w, h), (0.70, 0.45), (232, 181, 130, 86), (0, 0, 0, 0)))

    # Clean reading gradient, no huge empty cream panel.
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(0, 330):
        sd.line([(0, y), (w, y)], fill=(0, 0, 0, int(175 * (1 - y / 330))))
    for y in range(730, h):
        sd.line([(0, y), (w, y)], fill=(0, 0, 0, int(60 + 125 * ((y - 730) / max(1, h - 730)))))
    canvas.alpha_composite(shade)

    # Big hero photo. For watch-on-wrist the product is already in-scene, so do NOT cut out.
    paste_rounded_photo(canvas, src, (54, 286, w - 54, 760), radius=30, border=2, shadow=True, focus=(0.50, 0.50))

    draw.text((58, 66), copy.badge, font=font(14, True), fill="#e0aa6d")
    # Title can be up to two lines. Avoid the handbag copy if routing is correct.
    title_f = font(38, True)
    ty = 112
    for line in _fit_lines(draw, copy.title, title_f, w - 116, 2):
        draw.text((58, ty), line, font=title_f, fill="#fff7ef")
        ty += 43
    draw_wrapped(draw, copy.subtitle, 58, ty + 12, w - 116, font(15, False), fill="#eadbcc", line_gap=5, max_lines=2)

    chip_y = 796
    chip_x = 58
    for b in copy.bullets[:3]:
        bb = draw.textbbox((0, 0), b, font=font(11, True))
        chip_w = min(235, bb[2] - bb[0] + 34)
        draw.rounded_rectangle([chip_x, chip_y, chip_x + chip_w, chip_y + 34], radius=17, fill=(255, 247, 239, 228), outline=(255, 255, 255, 110))
        draw.ellipse([chip_x + 12, chip_y + 12, chip_x + 20, chip_y + 20], fill="#d9a56c")
        draw.text((chip_x + 28, chip_y + 10), b, font=font(11, True), fill="#2a1d18")
        chip_x += chip_w + 10
        if chip_x > w - 190:
            break

    draw_button(draw, (58, h - 148, 58 + 226, h - 90), copy.cta, fill="#bd7a4f")
    _footer(draw, w, h)
    return canvas


def _editorial_photo(src: Image.Image, copy, category: str, w: int, h: int) -> Image.Image:
    bg = cover(src, w, h).filter(ImageFilter.GaussianBlur(24)).convert("RGBA")
    bg = ImageEnhance.Color(bg).enhance(0.65)
    canvas = tint(bg, (18, 15, 14), 150)
    draw = ImageDraw.Draw(canvas)
    paste_rounded_photo(canvas, src, (54, 190, w - 54, 712), radius=34, border=2, shadow=True)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([42, 54, w - 42, 178], radius=28, fill=(0, 0, 0, 125))
    od.rounded_rectangle([42, 740, w - 42, 930], radius=28, fill=(0, 0, 0, 135))
    canvas.alpha_composite(overlay)
    draw.text((72, 82), copy.badge, font=font(14, True), fill="#d9a56c")
    draw_text_stack(draw, copy, 72, 114, w - 144, dark=True, title_size=30)
    draw_button(draw, (72, h - 145, 72 + 226, h - 89), copy.cta, fill="#bd7a4f")
    _footer(draw, w, h)
    return canvas


def _fit_lines(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int, max_lines: int = 2):
    words = (text or '').split()
    lines = []
    line = ''
    for word in words:
        test = (line + ' ' + word).strip()
        if not line or draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
            if len(lines) >= max_lines - 1:
                break
    if line and len(lines) < max_lines:
        lines.append(line)
    return lines[:max_lines]
