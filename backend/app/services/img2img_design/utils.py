from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

CANVAS_W = 832
CANVAS_H = 1024


def production_size(width: int | None, height: int | None) -> tuple[int, int]:
    return CANVAS_W, CANVAS_H


def open_source(path: str | None) -> Image.Image | None:
    if not path:
        return None
    try:
        return ImageOps.exif_transpose(Image.open(path).convert("RGB"))
    except Exception:
        return None


def font(size: int, bold: bool = False):
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def cover(img: Image.Image, w: int, h: int, focus: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    im = img.resize((nw, nh), Image.LANCZOS)
    fx, fy = focus
    left = int((nw - w) * max(0.0, min(1.0, fx)))
    top = int((nh - h) * max(0.0, min(1.0, fy)))
    left = max(0, min(left, nw - w))
    top = max(0, min(top, nh - h))
    return im.crop((left, top, left + w, top + h))


def contain(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    scale = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)


def gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    w, h = size
    a = Image.new("RGB", (1, 1), top).getpixel((0, 0))
    b = Image.new("RGB", (1, 1), bottom).getpixel((0, 0))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    px = out.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(a[0] * (1 - t) + b[0] * t)
        g = int(a[1] * (1 - t) + b[1] * t)
        bl = int(a[2] * (1 - t) + b[2] * t)
        for x in range(w):
            px[x, y] = (r, g, bl, 255)
    return out


def radial(size: tuple[int, int], center: tuple[float, float], inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> Image.Image:
    w, h = size
    cx, cy = center[0] * w, center[1] * h
    maxd = math.sqrt(max(cx, w - cx) ** 2 + max(cy, h - cy) ** 2)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = out.load()
    for y in range(h):
        for x in range(w):
            t = min(1.0, math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / maxd)
            px[x, y] = tuple(int(inner[i] * (1 - t) + outer[i] * t) for i in range(4))
    return out


def tint(img: Image.Image, color: tuple[int, int, int], alpha: int) -> Image.Image:
    out = img.convert("RGBA")
    out.alpha_composite(Image.new("RGBA", out.size, (*color, alpha)))
    return out


def looks_like_packshot(img: Image.Image | None) -> bool:
    if img is None:
        return False
    small = img.resize((96, 96)).convert("RGB")
    edge = []
    for x in range(96):
        edge.append(small.getpixel((x, 0)))
        edge.append(small.getpixel((x, 95)))
    for y in range(96):
        edge.append(small.getpixel((0, y)))
        edge.append(small.getpixel((95, y)))
    neutral = 0
    for r, g, b in edge:
        avg = (r + g + b) / 3
        if avg > 180 and abs(r - g) < 24 and abs(g - b) < 24:
            neutral += 1
    return neutral / max(1, len(edge)) > 0.45


def subject_bbox_by_difference(img: Image.Image, bg_threshold: int = 32) -> tuple[int, int, int, int] | None:
    # Simple packshot bbox: learn edge background color, then keep pixels that differ.
    rgb = img.convert("RGB")
    small = rgb.resize((min(600, rgb.width), int(rgb.height * min(600, rgb.width) / rgb.width))) if rgb.width > 600 else rgb
    w, h = small.size
    edge_pixels = []
    for x in range(w):
        edge_pixels.append(small.getpixel((x, 0)))
        edge_pixels.append(small.getpixel((x, h - 1)))
    for y in range(h):
        edge_pixels.append(small.getpixel((0, y)))
        edge_pixels.append(small.getpixel((w - 1, y)))
    bg = tuple(sorted([p[i] for p in edge_pixels])[len(edge_pixels)//2] for i in range(3))
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    pix = small.load()
    for y in range(h):
        for x in range(w):
            r, g, b = pix[x, y]
            dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
            sat = max(r, g, b) - min(r, g, b)
            avg = (r + g + b) / 3
            if dist > bg_threshold or sat > 40 or avg < 170:
                mp[x, y] = 255
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.0))
    bbox = mask.getbbox()
    if not bbox:
        return None
    cov = ((bbox[2]-bbox[0]) * (bbox[3]-bbox[1])) / float(w*h)
    if cov < 0.04 or cov > 0.88:
        return None
    # scale back
    sx = rgb.width / w
    sy = rgb.height / h
    return (int(bbox[0]*sx), int(bbox[1]*sy), int(bbox[2]*sx), int(bbox[3]*sy))


def simple_cutout(img: Image.Image) -> Image.Image | None:
    bbox = subject_bbox_by_difference(img)
    if not bbox:
        return None
    crop = img.convert("RGBA").crop(bbox)
    small = crop.resize((min(700, crop.width), int(crop.height * min(700, crop.width) / crop.width))) if crop.width > 700 else crop
    rgb = small.convert("RGB")
    w, h = rgb.size
    edge_pixels = []
    for x in range(w):
        edge_pixels.append(rgb.getpixel((x, 0)))
        edge_pixels.append(rgb.getpixel((x, h - 1)))
    for y in range(h):
        edge_pixels.append(rgb.getpixel((0, y)))
        edge_pixels.append(rgb.getpixel((w - 1, y)))
    bg = tuple(sorted([p[i] for p in edge_pixels])[len(edge_pixels)//2] for i in range(3))
    mask = Image.new("L", (w, h), 0)
    pix = rgb.load(); mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = pix[x, y]
            dist = abs(r-bg[0]) + abs(g-bg[1]) + abs(b-bg[2])
            sat = max(r,g,b)-min(r,g,b)
            avg = (r+g+b)/3
            if dist > 34 or sat > 38 or avg < 175:
                mp[x, y] = 255
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    bbox2 = mask.getbbox()
    if not bbox2:
        return None
    cut = small.copy().convert("RGBA")
    cut.putalpha(mask)
    return cut.crop(bbox2)


def paste_rounded_photo(canvas: Image.Image, img: Image.Image, box: tuple[int, int, int, int], radius: int = 28, border: int = 2, shadow: bool = True, focus: tuple[float, float] = (0.5, 0.5)) -> None:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    photo = cover(img, w, h, focus).convert("RGBA")
    photo = ImageEnhance.Contrast(photo).enhance(1.05)
    photo = ImageEnhance.Color(photo).enhance(1.03)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle([x1 + 14, y1 + 20, x2 + 14, y2 + 20], radius=radius, fill=(0, 0, 0, 90))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    if border:
        bd = Image.new("RGBA", (w + border*2, h + border*2), (255, 255, 255, 210))
        bm = Image.new("L", bd.size, 0)
        ImageDraw.Draw(bm).rounded_rectangle([0, 0, bd.width, bd.height], radius=radius+border, fill=255)
        canvas.paste(bd, (x1 - border, y1 - border), bm)
    canvas.paste(photo, (x1, y1), mask)


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str | None, x: int, y: int, max_width: int, fnt: ImageFont.ImageFont, fill, line_gap: int = 6, max_lines: int | None = None) -> int:
    words = (text or "").split()
    lines: list[str] = []
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if not line or draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            line = test
        else:
            lines.append(line)
            line = word
            if max_lines and len(lines) >= max_lines:
                break
    if line and (not max_lines or len(lines) < max_lines):
        lines.append(line)
    if max_lines:
        lines = lines[:max_lines]
    for i, ln in enumerate(lines):
        if max_lines and i == max_lines - 1:
            ln = ellipsize(draw, ln, fnt, max_width)
        draw.text((x, y), ln, font=fnt, fill=fill)
        y += getattr(fnt, "size", 18) + line_gap
    return y


def ellipsize(draw: ImageDraw.ImageDraw, text: str | None, fnt: ImageFont.ImageFont, max_width: int) -> str:
    text = text or ""
    if draw.textbbox((0, 0), text, font=fnt)[2] <= max_width:
        return text
    while text and draw.textbbox((0, 0), text + "...", font=fnt)[2] > max_width:
        text = text[:-1]
    return text + "..."


def center_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], fnt: ImageFont.ImageFont, fill) -> None:
    bb = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x1, y1, x2, y2 = box
    draw.text((x1 + (x2 - x1 - tw) // 2, y1 + (y2 - y1 - th) // 2 - 1), text, font=fnt, fill=fill)


def clean_badge(text: str | None, fallback: str = "NEW ARRIVAL") -> str:
    t = (text or "").strip()
    bad = {"NATURE SERIES", "FEATURE HIGHLIGHT", "NEW COLLECTION"}
    return fallback if not t or t.upper() in bad else t[:28]


def clean_title(text: str | None, fallback: str = "PREMIUM PRODUCT EDITORIAL") -> str:
    t = (text or "").strip()
    bad = {"DISCOVER HIDDEN NATURE", "DESIGNED TO STAND OUT", "CAMPAIGN READY VISUAL", "NEW CAMPAIGN"}
    return fallback if not t or t.upper() in bad else t[:72]


def clean_subtitle(text: str | None, fallback: str = "Premium styling with refined details and everyday luxury.") -> str:
    t = (text or "").strip()
    if not t or "hidden world" in t.lower() or "uploaded image" in t.lower():
        return fallback
    return t[:130]


def clean_cta(text: str | None, fallback: str = "SHOP NOW") -> str:
    t = (text or "").strip()
    return (t or fallback)[:28]


def clean_bullets(items: Iterable[str] | None, fallback: list[str] | None = None) -> list[str]:
    fallback = fallback or ["Premium finish", "Authentic detail", "Campaign ready"]
    out: list[str] = []
    for item in list(items or [])[:3]:
        item = (item or "").strip()
        if item and item.lower() not in {"source preserved", "campaign ready", "poster ready"}:
            out.append(item)
    for b in fallback:
        if len(out) >= 3:
            break
        if b not in out:
            out.append(b)
    return out[:3]


def save_canvas(canvas: Image.Image, output_dir: str, prefix: str = "generated_v10_design_engine") -> str:
    import uuid
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{prefix}_{uuid.uuid4().hex}.png"
    canvas.convert("RGB").save(out, quality=96, optimize=True)
    return str(out)
