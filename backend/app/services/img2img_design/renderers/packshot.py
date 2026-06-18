from __future__ import annotations

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from ..copy import build_copy
from ..utils import contain, cover, font, gradient
from .common import draw_button


def render_packshot(plan, src: Image.Image, decision, w: int, h: int) -> Image.Image:
    copy = build_copy(plan, decision.category)
    return _clean_luxury_packshot(src, copy, decision, w, h)


def _hex(rgb: str):
    rgb = rgb.lstrip('#')
    return tuple(int(rgb[i:i+2], 16) for i in (0, 2, 4))


def _edge_median_color(img: Image.Image) -> tuple[int, int, int]:
    small = img.convert('RGB').resize((128, 128), Image.LANCZOS)
    pts = []
    for x in range(128):
        pts.append(small.getpixel((x, 0)))
        pts.append(small.getpixel((x, 127)))
    for y in range(128):
        pts.append(small.getpixel((0, y)))
        pts.append(small.getpixel((127, y)))
    return tuple(sorted(p[i] for p in pts)[len(pts)//2] for i in range(3))


def _is_bright_neutral(r: int, g: int, b: int) -> bool:
    avg = (r + g + b) / 3
    sat = max(r, g, b) - min(r, g, b)
    return avg > 178 and sat < 32


def _clean_packshot_cutout(src: Image.Image) -> Image.Image | None:
    """Deterministic low-VRAM packshot cutout.

    Designed for ecommerce-style product photos on light/grey backgrounds.
    It intentionally removes bright neutral pixels aggressively to avoid the
    white/grey speckle artifacts that made the previous flyer look unpolished.
    """
    rgb = ImageOps.exif_transpose(src).convert('RGB')
    max_side = 1200
    scale = min(1.0, max_side / max(rgb.width, rgb.height))
    work = rgb.resize((max(1, int(rgb.width * scale)), max(1, int(rgb.height * scale))), Image.LANCZOS) if scale < 1 else rgb.copy()
    bg = _edge_median_color(work)
    w, h = work.size
    mask = Image.new('L', (w, h), 0)
    pix = work.load(); mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = pix[x, y]
            avg = (r + g + b) / 3
            sat = max(r, g, b) - min(r, g, b)
            diff = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
            # Keep dark product, metallic color, and real detail. Remove neutral bright/grey background.
            keep = avg < 188 or sat > 38 or diff > 92
            if _is_bright_neutral(r, g, b) and diff < 120:
                keep = False
            # Avoid preserving soft grey paper/shadow regions as product.
            if avg > 198 and sat < 26:
                keep = False
            if keep:
                mp[x, y] = 255
    # Close chain/handle details, then smooth edge without expanding background speckles.
    mask = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(0.8))
    bbox = mask.getbbox()
    if not bbox:
        return None
    x1, y1, x2, y2 = bbox
    coverage = ((x2 - x1) * (y2 - y1)) / float(w * h)
    if coverage < 0.03 or coverage > 0.72:
        return None
    cut = work.convert('RGBA')
    cut.putalpha(mask)
    cut = cut.crop(bbox)
    return cut


def _palette(category: str):
    if category == 'tech':
        return dict(bg_a='#081018', bg_b='#141f2c', paper='#eaf7ff', accent='#65cfff', text='#fffefe', muted='#cdd9e5')
    if category == 'cosmetics':
        return dict(bg_a='#180f12', bg_b='#352125', paper='#f2d7d3', accent='#df9a91', text='#fff7f2', muted='#e5c6bf')
    if category in {'bottle', 'food'}:
        return dict(bg_a='#170f0b', bg_b='#342014', paper='#f1d6ab', accent='#d89450', text='#fff7ef', muted='#ead0ba')
    return dict(bg_a='#100d0b', bg_b='#2d2119', paper='#ead8bb', accent='#d09056', text='#fff8ef', muted='#e6d4c4')


def _clean_luxury_packshot(src: Image.Image, copy, decision, w: int, h: int) -> Image.Image:
    p = _palette(decision.category)
    canvas = gradient((w, h), p['bg_b'], p['bg_a'])
    draw = ImageDraw.Draw(canvas)

    # One clean editorial stage. No diagonal shards, no rough texture, no white card.
    stage = [int(w * 0.42), int(h * 0.07), int(w * 0.96), int(h * 0.88)]
    shadow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([stage[0] + 16, stage[1] + 22, stage[2] + 16, stage[3] + 22], radius=44, fill=(0, 0, 0, 95))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))
    draw.rounded_rectangle(stage, radius=48, fill=(*_hex(p['paper']), 255))

    # Subtle editorial rings fully inside stage, not crossing the product edge aggressively.
    ring = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    for expand, alpha in [(0, 82), (38, 46)]:
        rd.ellipse([int(w * 0.58) - expand, int(h * 0.08) - expand, int(w * 1.02) + expand, int(h * 0.58) + expand], outline=(255, 255, 255, alpha), width=2)
    canvas.alpha_composite(ring)

    # Soft tabletop base inside the stage.
    base = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(base)
    bd.rectangle([stage[0], int(h * 0.70), stage[2], stage[3]], fill=(*_hex('#d6bd95'), 72))
    canvas.alpha_composite(base.filter(ImageFilter.GaussianBlur(1)))

    cut = _clean_packshot_cutout(src)
    if cut is not None:
        _place_clean_cutout(canvas, cut, w, h, decision.category)
    else:
        _place_clean_photo(canvas, src, w, h)

    _draw_left_copy(draw, copy, w, h, p)
    _draw_footer(draw, w, h)
    return canvas


def _place_clean_cutout(canvas: Image.Image, cut: Image.Image, w: int, h: int, category: str) -> None:
    if category == 'bottle':
        max_w, max_h = int(w * 0.35), int(h * 0.68)
    elif category == 'tech':
        max_w, max_h = int(w * 0.50), int(h * 0.46)
    else:
        max_w, max_h = int(w * 0.50), int(h * 0.52)
    prod = contain(cut, max_w, max_h).convert('RGBA')
    prod = ImageEnhance.Contrast(prod).enhance(1.06)
    prod = ImageEnhance.Sharpness(prod).enhance(1.08)
    x = int(w * 0.69 - prod.width / 2)
    y = int(h * 0.52 - prod.height / 2)

    # Soft realistic contact shadow only, no heavy black oval.
    sh = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    base_y = y + prod.height - 12
    sd.ellipse([x + int(prod.width * 0.06), base_y, x + int(prod.width * 0.96), base_y + int(h * 0.055)], fill=(0, 0, 0, 118))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
    canvas.alpha_composite(prod, (x, y))


def _place_clean_photo(canvas: Image.Image, src: Image.Image, w: int, h: int) -> None:
    # Safe fallback: large clean crop, but with no inner border/card look.
    photo = cover(src.convert('RGB'), int(w * 0.48), int(h * 0.52)).convert('RGBA')
    x = int(w * 0.47)
    y = int(h * 0.22)
    mask = Image.new('L', photo.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, photo.width, photo.height], radius=26, fill=255)
    sh = Image.new('RGBA', canvas.size, (0,0,0,0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([x+14, y+18, x+photo.width+14, y+photo.height+18], radius=28, fill=(0,0,0,82))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
    canvas.paste(photo, (x, y), mask)


def _draw_left_copy(draw: ImageDraw.ImageDraw, copy, w: int, h: int, p: dict) -> None:
    x = 56
    y = 78
    max_width = int(w * 0.34)
    draw.text((x, y), copy.badge, font=font(13, True), fill=p['accent'])
    y += 58
    title_font = font(45, True)
    for line in _fit_lines(draw, copy.title, title_font, max_width, 3):
        draw.text((x, y), line, font=title_font, fill=p['text'])
        y += 50
    y += 18
    body_font = font(15, False)
    for line in _fit_lines(draw, copy.subtitle, body_font, max_width, 4):
        draw.text((x, y), line, font=body_font, fill=p['muted'])
        y += 24
    y += 34
    for b in copy.bullets[:3]:
        draw.rounded_rectangle([x, y + 7, x + 11, y + 18], radius=4, fill=p['accent'])
        draw.text((x + 29, y), b, font=font(13, True), fill=p['text'])
        y += 34
    draw_button(draw, (56, h - 156, 56 + 232, h - 96), copy.cta, fill=p['accent'])


def _fit_lines(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int, max_lines: int = 3):
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


def _draw_footer(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    txt = 'SOURCE PRESERVED  •  CATEGORY ENGINE V3  •  3060 SAFE'
    f = font(8, True)
    bb = draw.textbbox((0, 0), txt, font=f)
    draw.text(((w - (bb[2] - bb[0])) // 2, h - 26), txt, font=f, fill=(255, 255, 255, 150))
    draw.rounded_rectangle([18, 18, w - 18, h - 18], radius=30, outline=(255, 255, 255, 55), width=1)
