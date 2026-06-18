from __future__ import annotations

"""V11 Shared Design Layer Engine for the 5 remaining img2img modes.

This engine keeps each mode isolated through small adapter files:
- modes/product_ad_adapter.py
- modes/social_post_adapter.py
- modes/background_lifestyle_adapter.py
- modes/identity_adapter.py
- modes/creative_image_adapter.py
- modes/auto_smart_router.py

It intentionally avoids putting all mode rules in one giant file so future fixes do not leak
from one mode into another.
"""

from dataclasses import dataclass
import os
import random
from pathlib import Path
from uuid import uuid4
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from app.services.img2img_hybrid.modes import V11_SHARED_DESIGN_LAYER_MARKER
from app.services.img2img_hybrid.modes import product_ad_adapter, social_post_adapter, background_lifestyle_adapter, identity_adapter, creative_image_adapter

MODE_VERSION = "v11-shared-design-layer-5-modes"
MODE_MARKER = V11_SHARED_DESIGN_LAYER_MARKER

MODE_TO_ADAPTER = {
    "product_ad": product_ad_adapter,
    "social_post": social_post_adapter,
    "background_replace": background_lifestyle_adapter,
    "background_lifestyle": background_lifestyle_adapter,
    "person_identity": identity_adapter,
    "identity": identity_adapter,
    "creative_image": creative_image_adapter,
}

@dataclass
class ModeDesign:
    mode: str
    selected_layout: str
    marker: str
    denoise: float
    steps: int
    cfg: float
    workflow_name: str
    positive_brief: str
    width: int
    height: int
    use_design_canvas: bool = True
    use_text_finalizer: bool = False
    sidecar_path: str = ""


def _env_bool(name: str, default: bool=True) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1","true","yes","on"}

def _env_int(name: str, default: int) -> int:
    try: return int(os.getenv(name, str(default)))
    except Exception: return default

def _env_float(name: str, default: float) -> float:
    try: return float(os.getenv(name, str(default)))
    except Exception: return default

def normalize_mode(mode: str) -> str:
    m = (mode or "auto").strip().lower().replace("-","_")
    if m in {"person", "identity"}: return "person_identity"
    if m in {"social", "social_media", "social_post"}: return "social_post"
    if m in {"background", "background_lifestyle", "lifestyle"}: return "background_replace"
    if m in {"creative", "creative_reference"}: return "creative_image"
    return m

def clean_user_direction(user_prompt: str, max_len: int=320) -> str:
    import re
    txt = re.sub(r"\[[A-Z0-9_]+:.*?\]", " ", str(user_prompt or ""), flags=re.I|re.S)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:max_len]

def extract_text(user_prompt: str) -> tuple[str,str,str]:
    import re
    def marker(name: str) -> str:
        m = re.search(rf"\[{re.escape(name)}:(.*?)\]", user_prompt or "", flags=re.I|re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip()[:80] if m else ""
    title = marker("AI_STUDIO_HEADLINE") or marker("HEADLINE") or "TIMELESS STYLE"
    subtitle = marker("AI_STUDIO_SUBHEADLINE") or marker("SUBHEADLINE") or "Premium design for everyday elegance"
    cta = marker("AI_STUDIO_CTA") or marker("CTA") or "SHOP NOW"
    return title.upper(), subtitle, cta.upper()

def select_mode_design(mode: str, decision: Any, user_prompt: str, width: int, height: int) -> ModeDesign:
    mode = normalize_mode(mode)
    adapter = MODE_TO_ADAPTER.get(mode, creative_image_adapter)
    category = getattr(decision, "category", "generic_product")
    subject = getattr(decision, "subject_label", "uploaded subject")
    mood = getattr(decision, "mood", "premium commercial")
    title, subtitle, cta = extract_text(user_prompt)
    rng = random.Random(f"{uuid4()}::{mode}::{category}::{user_prompt[:80]}")

    force_var = f"COMFY_DIRECTOR_V11_{mode.upper()}_FORCE_LAYOUT"
    forced = os.getenv(force_var, "").strip().lower().replace("-","_")
    if forced and forced in getattr(adapter, "LAYOUTS", []):
        selected_layout = forced
    else:
        selected_layout = adapter.choose_layout(category, user_prompt, rng)

    default_w, default_h = width or 768, height or 768
    if mode == "social_post":
        default_w = _env_int("COMFY_DIRECTOR_V11_SOCIAL_WIDTH", 768)
        default_h = _env_int("COMFY_DIRECTOR_V11_SOCIAL_HEIGHT", 768)
        workflow_name = os.getenv("COMFY_DIRECTOR_V11_SOCIAL_WORKFLOW", "flyer_poster")
        use_text = True
    elif mode == "product_ad":
        default_w = _env_int("COMFY_DIRECTOR_V11_PRODUCT_WIDTH", 768)
        default_h = _env_int("COMFY_DIRECTOR_V11_PRODUCT_HEIGHT", 768)
        workflow_name = os.getenv("COMFY_DIRECTOR_V11_PRODUCT_WORKFLOW", "product_ad")
        use_text = False
    elif mode == "background_replace":
        default_w = _env_int("COMFY_DIRECTOR_V11_BACKGROUND_WIDTH", min(max(width or 768, 512), 768))
        default_h = _env_int("COMFY_DIRECTOR_V11_BACKGROUND_HEIGHT", min(max(height or 768, 512), 768))
        workflow_name = os.getenv("COMFY_DIRECTOR_V11_BACKGROUND_WORKFLOW", "background_replace")
        use_text = False
    elif mode == "person_identity":
        default_w = _env_int("COMFY_DIRECTOR_V11_IDENTITY_WIDTH", min(max(width or 768, 512), 768))
        default_h = _env_int("COMFY_DIRECTOR_V11_IDENTITY_HEIGHT", min(max(height or 768, 512), 768))
        workflow_name = os.getenv("COMFY_DIRECTOR_V11_IDENTITY_WORKFLOW", "person_identity")
        use_text = False
    else:
        default_w = _env_int("COMFY_DIRECTOR_V11_CREATIVE_WIDTH", min(max(width or 768, 512), 768))
        default_h = _env_int("COMFY_DIRECTOR_V11_CREATIVE_HEIGHT", min(max(height or 768, 512), 768))
        workflow_name = os.getenv("COMFY_DIRECTOR_V11_CREATIVE_WORKFLOW", "creative_image")
        use_text = False

    brief = adapter.brief(subject, category, mood, clean_user_direction(user_prompt), title, subtitle, cta)
    denoise = _env_float(f"COMFY_DIRECTOR_V11_{mode.upper()}_DENOISE", getattr(adapter, "DEFAULT_DENOISE", 0.45))
    steps = _env_int(f"COMFY_DIRECTOR_V11_{mode.upper()}_STEPS", getattr(adapter, "DEFAULT_STEPS", 4))
    cfg = _env_float(f"COMFY_DIRECTOR_V11_{mode.upper()}_CFG", getattr(adapter, "DEFAULT_CFG", 1.0))

    return ModeDesign(mode=mode, selected_layout=selected_layout, marker=getattr(adapter, "MODE_MARKER", MODE_MARKER), denoise=denoise, steps=steps, cfg=cfg, workflow_name=workflow_name, positive_brief=brief, width=default_w, height=default_h, use_text_finalizer=use_text)


def _fit(im: Image.Image, max_w: int, max_h: int) -> Image.Image:
    im = im.convert("RGBA")
    im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return im

def _shadow(size, blur=24, opacity=110):
    mask = Image.new("L", size, 255).filter(ImageFilter.GaussianBlur(blur))
    mask = mask.point(lambda p: min(opacity, p))
    sh = Image.new("RGBA", size, (0,0,0,0)); sh.putalpha(mask); return sh

def _paste_subject(canvas: Image.Image, source: Image.Image, box: tuple[int,int,int,int]):
    x1,y1,x2,y2 = box; max_w=max(8,x2-x1); max_h=max(8,y2-y1)
    subj = _fit(source, max_w, max_h)
    px=x1+(max_w-subj.width)//2; py=y1+(max_h-subj.height)//2
    canvas.alpha_composite(_shadow(subj.size), (px+12, py+16))
    canvas.alpha_composite(subj, (px,py))

def _grad(w,h,top,bottom):
    img=Image.new("RGBA",(w,h),(0,0,0,255)); pix=img.load()
    for y in range(h):
        t=y/max(1,h-1); col=tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))+(255,)
        for x in range(w): pix[x,y]=col
    return img

def _card(d, box, fill, outline=None, radius=28):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)

def _layout_boxes(mode: str, layout: str, w: int, h: int):
    # returns subject_box, text_boxes
    if mode == "product_ad":
        return {
            "product_hero_center": ((int(w*.16), int(h*.20), int(w*.84), int(h*.78)), [(int(w*.12), int(h*.08), int(w*.88), int(h*.18)), (int(w*.28), int(h*.82), int(w*.72), int(h*.91))]),
            "premium_packshot_shadow": ((int(w*.22), int(h*.16), int(w*.78), int(h*.76)), [(int(w*.10), int(h*.78), int(w*.90), int(h*.91))]),
            "split_product_offer": ((int(w*.48), int(h*.18), int(w*.92), int(h*.80)), [(int(w*.08), int(h*.16), int(w*.42), int(h*.42)), (int(w*.10), int(h*.62), int(w*.42), int(h*.78))]),
            "floating_product_stage": ((int(w*.18), int(h*.22), int(w*.82), int(h*.72)), [(int(w*.12), int(h*.08), int(w*.70), int(h*.18)), (int(w*.56), int(h*.76), int(w*.90), int(h*.88))]),
            "dark_luxury_ad": ((int(w*.26), int(h*.18), int(w*.86), int(h*.76)), [(int(w*.08), int(h*.12), int(w*.46), int(h*.34)), (int(w*.10), int(h*.78), int(w*.48), int(h*.88))]),
            "minimal_ecommerce_ad": ((int(w*.18), int(h*.18), int(w*.82), int(h*.74)), [(int(w*.18), int(h*.78), int(w*.82), int(h*.90))]),
        }.get(layout)
    if mode == "social_post":
        return {
            "square_center_card": ((int(w*.18), int(h*.24), int(w*.82), int(h*.78)), [(int(w*.10), int(h*.08), int(w*.90), int(h*.19)), (int(w*.28), int(h*.82), int(w*.72), int(h*.92))]),
            "bold_caption_top": ((int(w*.22), int(h*.34), int(w*.84), int(h*.88)), [(int(w*.07), int(h*.07), int(w*.93), int(h*.28))]),
            "story_vertical_hero": ((int(w*.20), int(h*.30), int(w*.84), int(h*.82)), [(int(w*.08), int(h*.08), int(w*.82), int(h*.22)), (int(w*.10), int(h*.84), int(w*.58), int(h*.94))]),
            "carousel_cover": ((int(w*.42), int(h*.22), int(w*.90), int(h*.78)), [(int(w*.08), int(h*.12), int(w*.38), int(h*.36)), (int(w*.08), int(h*.58), int(w*.38), int(h*.74))]),
            "minimal_brand_post": ((int(w*.22), int(h*.25), int(w*.78), int(h*.75)), [(int(w*.18), int(h*.08), int(w*.82), int(h*.18)), (int(w*.22), int(h*.80), int(w*.78), int(h*.90))]),
            "promo_badge_layout": ((int(w*.18), int(h*.28), int(w*.82), int(h*.82)), [(int(w*.08), int(h*.08), int(w*.70), int(h*.22)), (int(w*.62), int(h*.14), int(w*.90), int(h*.32))]),
        }.get(layout)
    if mode == "background_replace":
        return None, []
    if mode == "person_identity":
        return ((int(w*.22), int(h*.12), int(w*.78), int(h*.82)), [(int(w*.10), int(h*.82), int(w*.90), int(h*.94))])
    return ((int(w*.18), int(h*.18), int(w*.82), int(h*.80)), [(int(w*.10), int(h*.08), int(w*.90), int(h*.18))])

def create_design_layer_canvas(source_image_path: str, design: ModeDesign, output_dir: str="static/images") -> str:
    mode, layout, w, h = design.mode, design.selected_layout, int(design.width), int(design.height)
    out_dir = Path(output_dir) / "v11_guides"; out_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_image_path).convert("RGBA")
    if mode == "background_replace":
        # For background replacement, use original subject image as main signal but provide scene-colored guide.
        bg = _grad(w,h,(235,231,222),(166,153,135))
        d = ImageDraw.Draw(bg)
        # scene hints only, no text/cards
        for i in range(8):
            x=int(w*(i/8)); d.rectangle((x, int(h*.72), x+int(w*.12), h), fill=(80+i*12,75+i*10,68+i*8,120))
        _paste_subject(bg, source, (int(w*.16), int(h*.16), int(w*.84), int(h*.84)))
    else:
        dark = layout in {"dark_luxury_ad", "bold_caption_top", "story_vertical_hero", "professional_headshot", "editorial_portrait", "cinematic_reference"}
        bg = _grad(w,h,(18,18,19) if dark else (243,236,224), (58,50,43) if dark else (210,195,174))
        d = ImageDraw.Draw(bg)
        gold=(219,158,45,230); cream=(248,242,232,230); ink=(18,18,18,230); soft=(255,255,255,200)
        # layout-specific decorative panels
        if "diagonal" in layout or layout in {"split_product_offer", "carousel_cover"}:
            d.polygon([(0,0),(int(w*.55),0),(int(w*.34),h),(0,h)], fill=(28,27,26,235) if not dark else (236,228,212,225))
        if "circle" in layout or "spotlight" in layout:
            d.ellipse((int(w*.10), int(h*.12), int(w*.90), int(h*.86)), outline=gold, width=6)
        if "grid" in layout or "carousel" in layout:
            for x in (int(w*.33), int(w*.66)): d.line((x,0,x,h), fill=(255,255,255,55), width=2)
            for y in (int(h*.33), int(h*.66)): d.line((0,y,w,y), fill=(255,255,255,55), width=2)
        subj_box, text_boxes = _layout_boxes(mode, layout, w, h)
        if subj_box:
            _card(d, (subj_box[0]-18, subj_box[1]-18, subj_box[2]+18, subj_box[3]+18), (255,255,255,50) if dark else (30,28,25,35), outline=(255,255,255,65), radius=34)
            _paste_subject(bg, source, subj_box)
        for i, box in enumerate(text_boxes or []):
            fill = (255,255,255,210) if dark else (25,24,22,210)
            if mode in {"product_ad", "social_post"}:
                _card(d, box, fill, outline=gold if i==0 else None, radius=22)
            elif mode == "person_identity":
                _card(d, box, (255,255,255,190), outline=None, radius=20)
        # accents
        d.line((int(w*.08), int(h*.08), int(w*.28), int(h*.08)), fill=gold, width=5)
        d.line((int(w*.72), int(h*.92), int(w*.92), int(h*.92)), fill=gold, width=5)
    filename = f"v11_{mode}_{layout}_guide_{uuid4().hex}.png"
    out_path = out_dir / filename
    bg.save(out_path)
    sidecar = out_path.with_suffix('.txt')
    sidecar.write_text(f"marker={MODE_MARKER}\nmode={mode}\nselected_layout={layout}\nrenderer_version={MODE_VERSION}\nworkflow_name={design.workflow_name}\n", encoding="utf-8")
    design.sidecar_path = str(sidecar)
    return str(out_path)

def read_design_sidecar(path: str) -> dict[str,str]:
    try:
        p = str(path or "")
        if not p.lower().endswith(".png"):
            return {}
        side = p[:-4] + ".txt"
        data = {}
        for line in open(side, "r", encoding="utf-8", errors="ignore").read().splitlines():
            if "=" in line:
                k,v=line.split("=",1); data[k.strip()]=v.strip()
        return data
    except Exception:
        return {}
