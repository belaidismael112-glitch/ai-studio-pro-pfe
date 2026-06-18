from __future__ import annotations

"""V10.3 Final Design Layer Engine for Flyer/Poster.

This is the final layout layer cleanup (V10.3.1 lower-left empty block cleanup):
- Force one of a few truly different layout families.
- Write selected_layout sidecar metadata so backend logs can prove the route.
- Generate visual-only canvas guides with no readable text and no old left-panel/right-card default.
- Keep product recognizable while letting ComfyUI render a real campaign poster.
"""

import os
import random
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFilter, ImageFont

V10_CREATIVE_DIRECTOR_RANDOMIZER_MARKER = "AI_STUDIO_V10_3_FINAL_DESIGN_LAYER_ENGINE"
V10_3_FINAL_DESIGN_LAYER_MARKER = "AI_STUDIO_V10_3_FINAL_DESIGN_LAYER_ENGINE"
V10_2_REAL_LAYOUT_BREAKER_MARKER = "AI_STUDIO_V10_2_REAL_LAYOUT_BREAKER"
V9_3_LAYOUT_POLISH_MARKER = "AI_STUDIO_V9_3_LAYOUT_POLISH_NO_EXTRA_BARS"

FORCED_LAYOUTS = (
    "full_bleed_dark",
    "center_hero",
    "diagonal_split",
    "magazine_grid",
    "circular_spotlight",
    "bottom_campaign",
)


def _env_bool(name: str, default: bool = True) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _env_choice(name: str) -> str:
    v = str(os.getenv(name, "")).strip().lower().replace("-", "_")
    return v if v in FORCED_LAYOUTS else ""


def _fit_contain(im: Image.Image, max_w: int, max_h: int) -> Image.Image:
    im = im.convert("RGBA")
    im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return im


def _soft_shadow(mask: Image.Image, blur: int = 28, opacity: int = 120) -> Image.Image:
    shadow = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    alpha = mask.convert("L").filter(ImageFilter.GaussianBlur(blur))
    alpha = alpha.point(lambda p: min(opacity, p))
    shadow.putalpha(alpha)
    return shadow


def _paste_product(canvas: Image.Image, product: Image.Image, box: tuple[int, int, int, int], *, shadow_opacity: int = 90) -> None:
    x1, y1, x2, y2 = box
    max_w, max_h = max(8, x2 - x1), max(8, y2 - y1)
    prod = _fit_contain(product, max_w, max_h)
    px = x1 + (max_w - prod.width) // 2
    py = y1 + (max_h - prod.height) // 2
    mask = Image.new("L", prod.size, 255)
    shadow = _soft_shadow(mask, blur=22, opacity=shadow_opacity)
    canvas.alpha_composite(shadow, (px + 14, py + 18))
    canvas.alpha_composite(prod, (px, py))


def _choose_layout(category: str, user_hint: str) -> str:
    forced = _env_choice("COMFY_DIRECTOR_V10_3_FORCE_LAYOUT")
    if forced:
        return forced
    if not _env_bool("COMFY_DIRECTOR_V10_LAYOUT_RANDOM", True):
        return "center_hero"

    hint = (user_hint or "").lower()
    category = (category or "generic_product").lower()
    weighted: list[str] = []

    # Hard rule: old luxury_split/soft_gallery/poster_wall are not allowed in V10.3.
    if any(w in hint for w in ("dark", "black", "cinematic", "noir", "metal", "watch", "montre")):
        weighted += ["full_bleed_dark", "circular_spotlight", "diagonal_split"] * 5
    if any(w in hint for w in ("minimal", "clean", "beige", "soft", "boutique", "elegant")):
        weighted += ["center_hero", "bottom_campaign", "magazine_grid"] * 5
    if any(w in hint for w in ("bold", "fashion", "magazine", "social", "sale", "promo", "dynamic")):
        weighted += ["diagonal_split", "magazine_grid", "bottom_campaign"] * 5

    if category == "watch":
        weighted += ["full_bleed_dark", "circular_spotlight", "center_hero", "diagonal_split"] * 4
    elif category == "handbag":
        weighted += ["center_hero", "diagonal_split", "magazine_grid", "bottom_campaign", "circular_spotlight"] * 4
    else:
        weighted += list(FORCED_LAYOUTS) * 3

    weighted += list(FORCED_LAYOUTS)
    return random.choice(weighted)


def _bg_gradient(w: int, h: int, top: tuple[int,int,int], bottom: tuple[int,int,int]) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0,0,0,255))
    px = img.load()
    for y in range(h):
        t = y / max(1, h-1)
        col = tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3)) + (255,)
        for x in range(w):
            px[x, y] = col
    return img


def _card(draw: ImageDraw.ImageDraw, box: tuple[int,int,int,int], fill: tuple[int,int,int,int], radius: int = 26, outline=None):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)


def _draw_layout_base(bg: Image.Image, layout: str) -> tuple[tuple[int,int,int,int], list[tuple[int,int,int,int]], dict[str,str]]:
    w, h = bg.size
    d = ImageDraw.Draw(bg)
    gold = (216, 154, 43, 255)
    cream = (239, 231, 217, 242)
    dark = (18, 18, 17, 248)
    paper = (248, 242, 232, 238)
    transparent_paper = (248, 242, 232, 70)
    text_zones: list[tuple[int,int,int,int]] = []

    if layout == "full_bleed_dark":
        bg.alpha_composite(_bg_gradient(w, h, (11,11,11), (42,34,27)))
        d.ellipse((int(w*.08), int(h*.13), int(w*.92), int(h*.92)), fill=(255,255,255,28))
        d.ellipse((int(w*.18), int(h*.23), int(w*.82), int(h*.80)), outline=(gold[0],gold[1],gold[2],130), width=4)
        d.rectangle((0, int(h*.76), w, h), fill=(10,10,10,175))
        d.line((int(w*.08), int(h*.10), int(w*.72), int(h*.03)), fill=gold, width=5)
        product_box = (int(w*.20), int(h*.25), int(w*.80), int(h*.70))
        text_zones = [(int(w*.07), int(h*.06), int(w*.62), int(h*.21)), (int(w*.07), int(h*.78), int(w*.58), int(h*.93))]
    elif layout == "center_hero":
        bg.alpha_composite(_bg_gradient(w, h, (238,228,213), (218,205,188)))
        d.rectangle((0, 0, w, int(h*.18)), fill=(18,18,17,235))
        d.rounded_rectangle((int(w*.10), int(h*.21), int(w*.90), int(h*.68)), radius=42, fill=(255,255,255,70))
        d.ellipse((int(w*.62), int(h*.04), int(w*1.12), int(h*.36)), outline=(gold[0],gold[1],gold[2],145), width=4)
        d.rectangle((0, int(h*.72), w, h), fill=(26,25,23,238))
        product_box = (int(w*.23), int(h*.26), int(w*.77), int(h*.64))
        text_zones = [(int(w*.08), int(h*.05), int(w*.70), int(h*.16)), (int(w*.08), int(h*.76), int(w*.92), int(h*.93))]
    elif layout == "diagonal_split":
        bg.alpha_composite(_bg_gradient(w, h, (234,223,205), (31,29,27)))
        d.polygon([(0,0),(int(w*.58),0),(int(w*.26),h),(0,h)], fill=(18,18,17,250))
        d.polygon([(int(w*.58),0),(w,0),(w,h),(int(w*.26),h)], fill=(235,223,205,238))
        d.line((int(w*.15), int(h*.08), int(w*.92), int(h*.33)), fill=gold, width=6)
        d.line((int(w*.08), int(h*.92), int(w*.85), int(h*.72)), fill=(gold[0],gold[1],gold[2],160), width=3)
        product_box = (int(w*.43), int(h*.27), int(w*.92), int(h*.77))
        text_zones = [(int(w*.07), int(h*.10), int(w*.47), int(h*.37))]  # V10.3.1: removed empty lower-left white block
    elif layout == "magazine_grid":
        bg.alpha_composite(_bg_gradient(w, h, (226,216,202), (242,235,224)))
        d.rectangle((0, 0, w, h), fill=(234,226,214,255))
        d.rectangle((0, 0, w, int(h*.23)), fill=(248,242,232,244))
        d.rectangle((int(w*.65), int(h*.23), w, h), fill=(22,22,21,244))
        for x in [int(w*.18), int(w*.36), int(w*.54), int(w*.72), int(w*.90)]:
            d.line((x, int(h*.04), x, int(h*.96)), fill=(255,255,255,48), width=1)
        d.rectangle((int(w*.05), int(h*.26), int(w*.60), int(h*.80)), fill=(255,255,255,64))
        product_box = (int(w*.09), int(h*.29), int(w*.58), int(h*.76))
        text_zones = [(int(w*.08), int(h*.05), int(w*.92), int(h*.19)), (int(w*.68), int(h*.30), int(w*.95), int(h*.82))]
    elif layout == "circular_spotlight":
        bg.alpha_composite(_bg_gradient(w, h, (24,23,21), (61,50,39)))
        d.ellipse((int(w*.09), int(h*.12), int(w*.91), int(h*.87)), fill=(239,231,217,230))
        d.ellipse((int(w*.18), int(h*.21), int(w*.82), int(h*.77)), outline=(gold[0],gold[1],gold[2],150), width=5)
        d.ellipse((int(w*.03), int(h*.04), int(w*.98), int(h*.96)), outline=(gold[0],gold[1],gold[2],95), width=2)
        product_box = (int(w*.28), int(h*.31), int(w*.72), int(h*.68))
        text_zones = [(int(w*.07), int(h*.06), int(w*.58), int(h*.22)), (int(w*.08), int(h*.76), int(w*.92), int(h*.92))]
    else:  # bottom_campaign
        bg.alpha_composite(_bg_gradient(w, h, (241,233,220), (214,199,180)))
        d.rectangle((0, 0, int(w*.18), h), fill=(18,18,17,244))
        d.rectangle((0, int(h*.66), w, h), fill=(22,21,20,246))
        d.ellipse((int(w*.54), int(h*.03), int(w*1.06), int(h*.42)), outline=(gold[0],gold[1],gold[2],140), width=4)
        d.line((int(w*.24), int(h*.65), int(w*.94), int(h*.65)), fill=gold, width=4)
        product_box = (int(w*.25), int(h*.14), int(w*.85), int(h*.59))
        text_zones = [(int(w*.23), int(h*.07), int(w*.68), int(h*.20)), (int(w*.10), int(h*.72), int(w*.90), int(h*.92))]

    # Draw very light non-text zone guides only, to avoid old template lock.
    for z in text_zones:
        _card(d, z, (255,255,255,42), radius=18, outline=(255,255,255,55))
    return product_box, text_zones, {"selected_layout": layout}


def create_v9_poster_canvas(source_image_path: str, pack, output_dir: str = "static/images") -> str:
    w, h = int(getattr(pack, "width", 640) or 640), int(getattr(pack, "height", 768) or 768)
    out_dir = Path(output_dir) / "v9_guides"
    out_dir.mkdir(parents=True, exist_ok=True)

    src = Image.open(source_image_path).convert("RGBA")
    category = str(getattr(pack, "category", "generic_product") or "generic_product")
    user_hint = str(getattr(pack, "positive_prompt", "") or "")
    layout = _choose_layout(category, user_hint)

    bg = Image.new("RGBA", (w, h), (238, 229, 216, 255))
    product_box, text_zones, meta = _draw_layout_base(bg, layout)
    d = ImageDraw.Draw(bg)

    # Product support shape differs per layout, never the old fixed right card.
    if layout in {"full_bleed_dark", "circular_spotlight"}:
        d.ellipse((product_box[0]-22, product_box[1]-22, product_box[2]+22, product_box[3]+24), fill=(255,255,255,30))
    elif layout == "diagonal_split":
        d.polygon([(product_box[0]-18, product_box[1]+12), (product_box[2]+10, product_box[1]-6), (product_box[2]+18, product_box[3]-8), (product_box[0]-8, product_box[3]+20)], fill=(255,255,255,74))
    else:
        d.rounded_rectangle((product_box[0]-14, product_box[1]-12, product_box[2]+14, product_box[3]+14), radius=30, fill=(255,255,255,62))

    _paste_product(bg, src, product_box, shadow_opacity=95)

    out = out_dir / f"v10_3_{layout}_poster_canvas_{uuid4().hex}.png"
    sidecar = out.with_suffix(".txt")
    try:
        sidecar.write_text(
            f"selected_layout={layout}\nvariant={layout}\ncategory={category}\nmarker={V10_3_FINAL_DESIGN_LAYER_MARKER}\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    bg.convert("RGB").save(out, quality=95)
    return str(out)
