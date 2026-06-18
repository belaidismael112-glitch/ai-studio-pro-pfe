from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from ..utils import center_text, draw_wrapped, font


def draw_footer(draw: ImageDraw.ImageDraw, w: int, h: int, text: str = "SOURCE PRESERVED  •  CATEGORY DESIGN ENGINE  •  3060 SAFE"):
    f = font(8, True)
    bb = draw.textbbox((0, 0), text, font=f)
    draw.text(((w - (bb[2] - bb[0])) // 2, h - 28), text, font=f, fill=(255, 255, 255, 185))


def draw_button(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fill="#c47b4f", text_fill="#ffffff"):
    f = font(14, True)
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1 + 7, y1 + 9, x2 + 7, y2 + 9], radius=(y2-y1)//2, fill=(0, 0, 0, 80))
    draw.rounded_rectangle(box, radius=(y2-y1)//2, fill=fill)
    center_text(draw, text, box, f, text_fill)


def draw_text_stack(draw: ImageDraw.ImageDraw, copy, x: int, y: int, width: int, dark: bool = True, title_size: int = 42):
    accent = "#d9a56c" if dark else "#9a623e"
    primary = "#fff7ef" if dark else "#121826"
    secondary = "#e6d6c8" if dark else "#263241"
    draw.text((x, y), copy.badge, font=font(14, True), fill=accent)
    y += 48
    y = draw_wrapped(draw, copy.title, x, y, width, font(title_size, True), fill=primary, line_gap=7, max_lines=3)
    y += 18
    y = draw_wrapped(draw, copy.subtitle, x, y, width, font(15, False), fill=secondary, line_gap=6, max_lines=4)
    y += 28
    for b in copy.bullets[:3]:
        draw.ellipse([x, y + 5, x + 12, y + 17], fill=accent)
        draw.text((x + 28, y), b, font=font(13, True), fill=primary)
        y += 32
    return y


def soft_shadow(canvas: Image.Image, box: tuple[int, int, int, int], radius: int = 32, alpha: int = 95, blur: int = 22):
    x1, y1, x2, y2 = box
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([x1 + 14, y1 + 20, x2 + 14, y2 + 20], radius=radius, fill=(0, 0, 0, alpha))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
