
from __future__ import annotations

"""AI Studio V13 - 6 Modes Commercial Engine."""

import os
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

from app.services.img2img_hybrid.contracts import Img2ImgRequest, RenderResult
from app.services.img2img_hybrid.utils import backend_public_image_url

V13_MARKER = "AI_STUDIO_V13_6_MODES_COMMERCIAL_ENGINE"
V13_PROVIDER = "comfy-director-v13-commercial-engine"
V14_PROVIDER = "comfy-director-v14-workflow-binding"
V13_1_MARKER = "AI_STUDIO_V13_1_SEGMENTATION_AND_BACKGROUND_CLEANUP"
V13_2_MARKER = "AI_STUDIO_V13_2_COLOR_SUBJECT_MASK_FIX"
V13_3_MARKER = "AI_STUDIO_V13_3_REMBG_HARD_CLEAN_COMMERCIAL"
V13_4_MARKER = "AI_STUDIO_V13_4_FINAL_POLISH_NO_DEFAULT_TEXT"
V14_MARKER = "AI_STUDIO_V14_WORKFLOW_BINDING_PRO_COMFY"
V14_1_MARKER = "AI_STUDIO_V14_1_FINAL_COMPOSITE_POLISH"
V14_2_MARKER = "AI_STUDIO_V14_2_RECTANGLE_MATTE_KILLER"
V14_3_MARKER = "AI_STUDIO_V14_3_CONTENT_MASK_MATTE_KILLER"
V14_4_MARKER = "AI_STUDIO_V14_4_BORDER_ONLY_MATTE_KILLER"
V14_5_MARKER = "AI_STUDIO_V14_5_ALL_IN_ONE_PRODUCT_STABILIZER"
V15_MARKER = "AI_STUDIO_V15_GLASS_AWARE_FINAL_REPAIR"
V16_MARKER = "AI_STUDIO_V16_STAGE_ANCHOR_SAFE_GLASS"
V17_MARKER = "AI_STUDIO_V17_LOGICAL_PRODUCT_SCALE_STAGE_FIT"
V18_MARKER = "AI_STUDIO_V18_AI_COPYWRITER_POSTER_LAYOUT"
V19_MARKER = "AI_STUDIO_V19_PRO_POSTER_COMPOSITION_LOCK"
V19_1_MARKER = "AI_STUDIO_V19_1_SYNTAX_REPAIR_NO_FALLBACK"


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except Exception:
        return int(default)


def _normalize_mode(mode: str | None) -> str:
    m = str(mode or "auto").strip().lower().replace("-", "_")
    aliases = {
        "auto_smart": "auto",
        "person": "person_identity",
        "identity": "person_identity",
        "creative": "creative_image",
        "background": "background_replace",
        "bg_replace": "background_replace",
        "poster": "flyer_poster",
        "flyer": "flyer_poster",
    }
    return aliases.get(m, m)


def _resolve_mode(mode: str | None, subject_type: str | None, prompt: str) -> str:
    m = _normalize_mode(mode)
    if m in {"product_ad", "flyer_poster", "background_replace", "person_identity", "creative_image", "social_post"}:
        return m
    p = (prompt or "").lower()
    st = (subject_type or "").lower()
    if any(x in st for x in ("person", "face", "human")) or any(x in p for x in ("person", "portrait", "face", "identity")):
        return "person_identity"
    if any(x in p for x in ("background", "fond", "environment", "scene", "replace")):
        return "background_replace"
    if any(x in p for x in ("flyer", "poster", "banner", "promo", "cta", "price", "affiche")):
        return "flyer_poster"
    if any(x in p for x in ("creative", "fantasy", "surreal", "artistic", "cinematic concept")):
        return "creative_image"
    return "product_ad"


def _text_disabled(prompt: str) -> bool:
    p = (prompt or "").lower()
    return any(x in p for x in (
        "no text", "without text", "no typography", "without typography", "no cta", "no headline",
        "sans texte", "pas de texte", "بلا كتابة", "no letters",
    ))


def _extract_copy(prompt: str) -> tuple[str, str, str]:
    """Extract ONLY explicit user copy.

    V13.4 deliberately does not invent generic text. Text is rendered only when
    the prompt contains quoted copy or explicit fields such as Headline: ...
    """
    text = " ".join(str(prompt or "").split())
    quoted = re.findall(r'["“”\']([^"“”\']{2,80})["“”\']', text)
    if quoted:
        headline = quoted[0][:42]
        sub = quoted[1][:72] if len(quoted) > 1 else ""
        cta = quoted[2][:26] if len(quoted) > 2 else ""
        return headline, sub, cta

    def field(names: str, limit: int) -> str:
        m = re.search(rf"(?:{names})\s*[:=]\s*([^.;\n\r|]{{2,{limit}}})", text, flags=re.I)
        if not m:
            return ""
        value = m.group(1).strip()
        value = re.sub(r"\[[^\]]+\]", "", value).strip()
        banned = ("clean space", "headline", "price", "cta", "poster", "flyer", "composition", "background")
        if any(b in value.lower() for b in banned):
            return ""
        return value[:limit]

    headline = field("headline|title|titre", 42)
    sub = field("subheadline|subtitle|sous[- ]?titre", 72)
    cta = field("cta|call[- ]?to[- ]?action|price|prix", 26)
    return headline, sub, cta


def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            if c and Path(c).exists():
                return ImageFont.truetype(c, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int, bold: bool = False, min_size: int = 18):
    while size >= min_size:
        f = _font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=f)
        if bbox[2] - bbox[0] <= max_width:
            return f
        size -= 2
    return _font(min_size, bold=bold)


def _copywriter_fallback(mode: str, prompt: str, subject: Image.Image | None = None) -> tuple[str, str, str, str]:
    """V18 lightweight AI copywriter.

    Uses explicit UI/user copy when available. If fields are empty, it creates
    short commercial copy from product geometry and prompt intent. It does not
    ask Comfy to draw letters because Flux text is usually unreadable; the AI
    decides the copy/layout, while backend renders clean typography.
    """
    headline, sub, cta = _extract_copy(prompt)
    if headline:
        return "Featured", headline, sub, cta or "Discover More"

    p = (prompt or "").lower()
    wide = tall = False
    if subject is not None and subject.width and subject.height:
        wide = subject.width >= subject.height * 1.25
        tall = subject.height >= subject.width * 1.45

    if any(x in p for x in ("drink", "beverage", "soda", "cola", "refresh", "bottle")) or tall:
        return "Campaign Highlight", "Refresh Your Moment", "A polished product story built for modern campaigns.", "Discover More"
    if wide:
        return "Premium Feature", "Made to Stand Out", "Clean visual impact with a refined commercial presentation.", "Shop Now"
    if any(x in p for x in ("limited", "offer", "promo", "sale")):
        return "Limited Campaign", "Premium Offer", "A clean commercial visual ready for your next promotion.", "Get It Now"
    return "Featured Product", "Elevate the Everyday", "A refined product presentation designed for premium visibility.", "Discover More"


def _draw_text_block(img: Image.Image, mode: str, prompt: str, subject_bbox: tuple[int, int, int, int] | None = None, subject: Image.Image | None = None) -> dict[str, Any]:
    if mode not in {"flyer_poster", "social_post"} or _text_disabled(prompt):
        return {"v18_text_rendered": False, "v18_text_reason": "mode_or_disabled"}

    eyebrow, headline, sub, cta = _copywriter_fallback(mode, prompt, subject)
    if not headline:
        return {"v18_text_rendered": False, "v18_text_reason": "no_copy"}

    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    tall_canvas = h >= w * 1.1

    # Integrated design panel: not a cheap sticker. It is a soft layout layer
    # with gradient/lines/shadows, respecting product bbox.
    if subject_bbox:
        sx1, sy1, sx2, sy2 = subject_bbox
    else:
        sx1, sy1, sx2, sy2 = int(w*0.55), int(h*0.25), int(w*0.90), int(h*0.78)

    # Choose side with more safe space. Usually left for product-right layout.
    left_space = sx1
    right_space = w - sx2
    use_left = left_space >= right_space
    pad = int(w * (0.070 if mode == "flyer_poster" else 0.065))
    panel_w = int(w * (0.56 if (mode == "flyer_poster" and tall_canvas) else (0.50 if tall_canvas else 0.46)))
    if use_left:
        x1 = pad
    else:
        x1 = max(pad, w - pad - panel_w)
    x2 = min(w - pad, x1 + panel_w)
    y1 = int(h * (0.115 if mode == "flyer_poster" and tall_canvas else (0.10 if tall_canvas else 0.13)))

    # Keep text away from the product if bbox overlaps.
    if subject_bbox and not (x2 < sx1 or x1 > sx2):
        if use_left:
            x2 = max(pad + int(w*0.34), sx1 - int(w*0.045))
        else:
            x1 = min(w - pad - int(w*0.34), sx2 + int(w*0.045))
        panel_w = max(int(w*0.34), x2 - x1)

    max_w = max(120, int(x2 - x1 - 34))
    if mode == "flyer_poster" and " " in headline and len(headline) > 20:
        parts = headline.split()
        mid = max(1, len(parts)//2)
        headline_draw = " ".join(parts[:mid]) + "\n" + " ".join(parts[mid:])
    else:
        headline_draw = headline
    title_font = _fit_text(draw, headline.replace("\n", " "), int(h * (0.070 if tall_canvas else 0.064)), max_w, bold=True, min_size=28)
    eyebrow_font = _fit_text(draw, eyebrow.upper(), int(h * 0.017), max_w, bold=True, min_size=13)
    sub_font = _fit_text(draw, sub, int(h * 0.024), max_w, bold=False, min_size=16) if sub else None
    cta_font = _fit_text(draw, cta.upper(), int(h * 0.021), int(max_w*0.72), bold=True, min_size=15) if cta else None

    # Estimate panel height.
    title_bbox = draw.multiline_textbbox((0, 0), headline_draw, font=title_font, spacing=4)
    sub_h = int(h * 0.052) if sub else 0
    cta_h = int(h * 0.052) if cta else 0
    panel_h = int(h * 0.045) + (title_bbox[3]-title_bbox[1]) + sub_h + cta_h + int(h*0.040)
    y2 = min(int(h*0.72), y1 + panel_h)

    # Background wash/gradient card.
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay, "RGBA")
    shadow = (int(x1-12), int(y1-12), int(x2+18), int(y2+18))
    od.rounded_rectangle(shadow, radius=36, fill=(70, 45, 24, 36))
    od.rounded_rectangle((x1-14, y1-14, x2+14, y2+14), radius=34, fill=(255, 245, 226, 118))
    od.rounded_rectangle((x1-14, y1-14, x2+14, y2+14), radius=34, outline=(255, 255, 255, 100), width=2)
    # Design accent line.
    accent_y = y1 + int(h*0.028)
    od.rounded_rectangle((x1, accent_y, x1 + int(panel_w*0.35), accent_y + 3), radius=2, fill=(170, 88, 36, 170))
    img.alpha_composite(overlay)

    tx = x1 + 12
    ty = y1 + int(h*0.018)
    draw.text((tx, ty), eyebrow.upper(), font=eyebrow_font, fill=(122, 70, 33, 228))
    ty += int(h * 0.038)
    draw.multiline_text((tx, ty), headline_draw, font=title_font, fill=(34, 27, 21, 248), spacing=4)
    ty += (title_bbox[3] - title_bbox[1]) + int(h * 0.020)
    if sub and sub_font:
        # Simple wrap into max two lines.
        words = sub.split()
        lines = []
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if draw.textbbox((0, 0), test, font=sub_font)[2] <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
            if len(lines) >= 2:
                break
        if cur and len(lines) < 2:
            lines.append(cur)
        for line in lines[:2]:
            draw.text((tx, ty), line, font=sub_font, fill=(49, 40, 32, 212))
            ty += int(h * 0.030)
        ty += int(h * 0.012)

    if cta and cta_font:
        cta_text = cta.upper()[:32]
        bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        bw = min(max_w, bbox[2] - bbox[0] + 44)
        bh = bbox[3] - bbox[1] + 24
        draw.rounded_rectangle((tx, ty, tx + bw, ty + bh), radius=18, fill=(35, 29, 24, 230))
        draw.text((tx + 22, ty + 10), cta_text, fill=(255, 246, 230, 255), font=cta_font)

    return {
        "v18_text_rendered": True,
        "v18_ai_copywriter": True,
        "v18_headline": headline,
        "v18_subheadline": sub,
        "v18_cta": cta,
        "v18_layout": "integrated_poster_panel",
    }


def _make_gradient_background(width: int, height: int, mode: str, prompt: str, out_dir: str) -> str:
    """V13.4 clean commercial studio background.

    No props, no circle frame, no hard rings, no text placeholders.
    """
    out = Path(out_dir) / f"v13_4_clean_commercial_background_{uuid4().hex}.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (width, height), (242, 222, 191))
    px = img.load()
    for y in range(height):
        yy = y / max(1, height - 1)
        for x in range(width):
            xx = x / max(1, width - 1)
            r = int(250 - 34 * yy + 7 * xx)
            g = int(232 - 38 * yy + 5 * xx)
            b = int(199 - 49 * yy + 2 * xx)
            px[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Diffuse softbox; blurred until it becomes lighting, not a visible circle.
    draw.ellipse((int(width*0.02), -int(height*0.30), int(width*0.98), int(height*0.48)), fill=(255, 247, 224, 82))

    # Floor/cove.
    floor_y = int(height * 0.69)
    draw.rectangle((0, floor_y, width, height), fill=(221, 186, 136, 32))

    # Low premium pedestal.
    ped_y = int(height * 0.735)
    ped_h = int(height * 0.085)
    ped_x1 = int(width * 0.18)
    ped_x2 = int(width * 0.82)
    draw.ellipse((ped_x1, ped_y - int(ped_h*0.40), ped_x2, ped_y + int(ped_h*0.42)), fill=(255, 239, 209, 158))
    draw.rectangle((ped_x1, ped_y, ped_x2, ped_y + ped_h), fill=(229, 193, 145, 120))
    draw.ellipse((ped_x1, ped_y + int(ped_h*0.52), ped_x2, ped_y + int(ped_h*1.15)), fill=(158, 108, 60, 36))

    # Subject contact shadow zone only.
    draw.ellipse((int(width*0.24), int(height*0.565), int(width*0.76), int(height*0.665)), fill=(80, 48, 28, 22))

    canvas = canvas.filter(ImageFilter.GaussianBlur(max(22, int(min(width, height) * 0.035))))
    img = Image.alpha_composite(img.convert("RGBA"), canvas).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.025)
    img = ImageEnhance.Color(img).enhance(1.025)
    img.save(out, quality=96)
    return str(out)


def _create_background_guide(width: int, height: int, out_dir: str) -> str:
    out = Path(out_dir) / f"v13_background_guide_{uuid4().hex}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), (235, 226, 211))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse((int(width*0.55), -int(height*0.18), int(width*1.15), int(height*0.35)), fill=(255, 252, 242, 95))
    draw.ellipse((-int(width*0.20), int(height*0.66), int(width*0.50), int(height*1.14)), fill=(180, 150, 110, 40))
    img = img.filter(ImageFilter.GaussianBlur(8))
    img.save(out, quality=95)
    return str(out)



def _sanitize_background_hint(prompt: str) -> str:
    """Keep only style/background intent from the user prompt.

    Do not pass source/product preservation instructions into the background-only generator,
    otherwise Comfy may create extra props, fake products, or poster templates.
    """
    raw = " ".join(str(prompt or "").split())
    if not raw:
        return ""
    blocked = (
        "uploaded", "reference image", "source", "preserve", "exact silhouette",
        "product shape", "subject source", "do not redesign", "invent a different object",
        "primary product", "label/branding", "key details", "source lock",
    )
    useful = (
        "background", "lighting", "light", "shadow", "studio", "luxury", "beige",
        "warm", "clean", "commercial", "advertising", "premium", "minimal", "scene",
        "environment", "soft", "elegant", "natural", "realistic",
    )
    keep: list[str] = []
    for part in re.split(r"[.\n\r;|]+", raw):
        s = part.strip()
        low = s.lower()
        if len(s) < 4:
            continue
        if any(b in low for b in blocked):
            continue
        if any(u in low for u in useful):
            keep.append(s)
    hint = ". ".join(keep)
    if not hint:
        if any(x in raw.lower() for x in ("beige", "luxury", "warm", "commercial", "studio")):
            hint = "warm beige luxury commercial studio background with soft shadows"
        else:
            hint = "clean premium commercial studio background"
    return hint[:360]

def _bg_prompt(mode: str, prompt: str) -> str:
    hint = _sanitize_background_hint(prompt)
    shared = (
        "high-end commercial advertising background only, empty central hero space for compositing the uploaded product later, "
        "premium studio lighting, cinematic soft shadows, editorial catalog quality, clean perspective, polished depth, "
        "warm beige and soft gold tones, no product, no duplicate subject, no person, no text, no logo, no typography, no watermark"
    )
    if mode == "product_ad":
        return (
            shared + ", seamless luxury ecommerce product studio, single clean rounded podium, clean hero product zone, "
            "minimal premium catalog packshot backdrop, subtle wall gradient, realistic soft ground shadow area, "
            "no side props, no plants, no vases, no jars, no decorative objects, no ceiling spotlight grid, no heavy theatre room, "
            "no arches, no shelves, no clutter, no extra product. Style hint: " + hint
        )
    if mode == "flyer_poster":
        return (
            shared + ", premium vertical commercial poster background, luxury beige studio set, large clean left copy zone, "
            "right-side hero product stage/podium area, refined architectural framing, soft warm spotlighting, editorial advertising layout, "
            "minimal clean negative space, no written text in the generated background, no tiny placeholders, no busy ceiling rig, "
            "no black spotlight clutter, no furniture, no chair, no cabinets, no props clutter. Style hint: " + hint
        )
    if mode == "background_replace":
        return (
            "premium realistic environment background only, empty subject space, coherent perspective, natural commercial lighting, "
            "no subject, no text, no props clutter. Style hint: " + hint
        )
    if mode == "person_identity":
        return (
            "premium portrait studio backdrop only, elegant professional lighting, clean background, no person, no face, no text. "
            "Style hint: " + hint
        )
    if mode == "creative_image":
        return (
            "creative cinematic commercial backdrop only, high-end art direction, empty space for final composite, no source subject, no text. "
            "Style hint: " + hint
        )
    if mode == "social_post":
        return (
            shared + ", square social media ad background, bold clean visual hierarchy, empty safe space for product and optional backend text, "
            "no written text in generated background. Style hint: " + hint
        )
    return shared + ". Style hint: " + hint


def _bg_negative(mode: str, user_negative: str) -> str:
    neg = (
        "product, object, subject, person, insect, animal, duplicate product, second product, extra prop, props, "
        "vase, jar, bottle, pot, plant, decorative object, side object, flowers, leaves, wheat, branch, "
        "ceiling spotlight grid, black ceiling lights, busy ceiling rig, overhead clutter, theatre stage, heavy room box, chairs, furniture, cabinets, side props, arches, shelves, window frame, "
        "text, letters, typography, words, logo, watermark, label, headline, CTA, "
        "hard circle, circular frame, ring, line art, banner, poster frame, white rectangle, crop box, source rectangle, "
        "cheap template, clutter, messy composition, low quality, blurry, deformed subject"
    )
    if user_negative:
        neg += ", " + user_negative
    return neg


def _v14_workflow_name(mode: str) -> str:
    mapping = {
        "product_ad": "flux_product_backdrop",
        "flyer_poster": "flux_flyer_backdrop",
        "background_replace": "flux_background_replace",
        "person_identity": "flux_identity_img2img",
        "creative_image": "flux_creative_reference",
        "social_post": "flux_commercial_background",
    }
    return mapping.get(mode, "flux_commercial_background")


def _v14_steps() -> int:
    # Hard cap for RTX 3060 / flux schnell. This prevents old duplicate .env values from forcing 8.
    return max(1, min(4, _env_int("IMG2IMG_V14_BG_STEPS", _env_int("IMG2IMG_V13_BG_STEPS", 4))))


def _v14_cfg() -> float:
    return max(0.8, min(1.4, _env_float("IMG2IMG_V14_BG_CFG", _env_float("IMG2IMG_V13_BG_CFG", 1.0))))


def _v14_denoise() -> float:
    return max(0.55, min(0.90, _env_float("IMG2IMG_V14_BG_DENOISE", _env_float("IMG2IMG_V13_BG_DENOISE", 0.72))))


async def _generate_ai_background(mode: str, prompt: str, negative_prompt: str, width: int, height: int, style: str | None, output_dir: str) -> tuple[str, dict[str, Any]]:
    guide = _create_background_guide(width, height, output_dir)

    if _env_bool("IMG2IMG_V14_USE_BOUND_WORKFLOW", True) is False:
        return _make_gradient_background(width, height, mode, prompt, output_dir), {
            "v13_background_ai": False,
            "v14_background_ai": False,
            "v14_background_reason": "bound_workflow_disabled",
            "v13_background_guide": guide,
        }

    try:
        from app.services.img2img_hybrid.comfy_v6_runner import run_comfy_v6

        workflow_name = _v14_workflow_name(mode)
        pack = SimpleNamespace(
            mode=f"v14_{mode}_background",
            workflow_name=workflow_name,
            width=int(width),
            height=int(height),
            positive_prompt=_bg_prompt(mode, prompt),
            negative_prompt=_bg_negative(mode, negative_prompt),
            steps=_v14_steps(),
            cfg=_v14_cfg(),
            denoise=_v14_denoise(),
            seed=None,
            overlay_title="",
            overlay_subtitle="",
            overlay_cta="",
            category="background",
        )
        comfy = await run_comfy_v6(guide, pack, output_dir=output_dir)
        if comfy.get("success") and comfy.get("local_path"):
            return str(comfy["local_path"]), {
                "v13_background_ai": True,
                "v14_background_ai": True,
                "v14_bound_workflow": workflow_name,
                "v14_workflow_file_expected": f"COMFY_WORKFLOW_{workflow_name.upper()}",
                "v13_background_comfy": comfy,
                "v13_background_guide": guide,
            }

        if _env_bool("IMG2IMG_V14_REQUIRE_COMFY_BACKGROUND", True):
            raise RuntimeError(str(comfy.get("error") or "V14 bound Comfy background failed"))

        return _make_gradient_background(width, height, mode, prompt, output_dir), {
            "v13_background_ai": False,
            "v14_background_ai": False,
            "v14_background_error": str(comfy.get("error")),
            "v13_background_guide": guide,
        }
    except Exception as exc:
        if _env_bool("IMG2IMG_V14_REQUIRE_COMFY_BACKGROUND", True):
            raise
        return _make_gradient_background(width, height, mode, prompt, output_dir), {
            "v13_background_ai": False,
            "v14_background_ai": False,
            "v14_background_error": str(exc),
            "v13_background_guide": guide,
        }




def _v14_3_content_mask_matte_killer(im: Image.Image) -> Image.Image:
    """Remove source rectangles without destroying internal product details.

    V14.4 changes the matte killer from global content erasing to border-only
    erasing. It can remove full screenshot/crop rectangles, but it only removes
    matte pixels connected to the crop border. Internal glass windows, labels,
    reflections, transparent product details, and enclosed highlights are kept.
    """
    im = im.convert("RGBA")
    w, h = im.size
    if w < 8 or h < 8:
        return im
    alpha = im.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return im

    bbox_coverage = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1, w * h)

    border = Image.new("L", (w, h), 0)
    bd = ImageDraw.Draw(border)
    bw = max(2, min(w, h) // 36)
    bd.rectangle((0, 0, w - 1, bw), fill=255)
    bd.rectangle((0, h - 1 - bw, w - 1, h - 1), fill=255)
    bd.rectangle((0, 0, bw, h - 1), fill=255)
    bd.rectangle((w - 1 - bw, 0, w - 1, h - 1), fill=255)
    border_alpha = ImageStat.Stat(Image.composite(alpha, Image.new("L", (w, h), 0), border)).mean[0] / 255.0

    # Normal rembg cutout: do nothing.
    if bbox_coverage < 0.88 and border_alpha < 0.12:
        return im

    try:
        import numpy as np
        from collections import deque

        arr = np.asarray(im).astype(np.int16)
        r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        chroma = mx - mn
        luma = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.int16)
        sat = np.where(mx > 0, chroma / np.maximum(mx, 1), 0.0)

        gx = np.zeros_like(luma)
        gy = np.zeros_like(luma)
        gx[:, 1:] = np.abs(luma[:, 1:] - luma[:, :-1])
        gy[1:, :] = np.abs(luma[1:, :] - luma[:-1, :])
        edge = np.maximum(gx, gy)

        # Evidence of real product pixels. This intentionally preserves dark
        # glass, saturated branding, metallic caps, edges and transparent-bottle
        # contours. It is not product-specific.
        product_evidence = (
            (a > 18)
            & (
                (chroma > 26)
                | (sat > 0.16)
                | (edge > 10)
                | ((luma < 150) & (edge > 3))
                | (luma < 78)
            )
        )

        evidence = Image.fromarray((product_evidence.astype(np.uint8) * 255), "L")
        evidence = evidence.filter(ImageFilter.MedianFilter(3))

        # Dilate enough to close product contours, especially glass bottles and
        # thin edge highlights, so flood-fill cannot enter enclosed interiors.
        dilate = max(11, (min(w, h) // 18) | 1)
        if dilate % 2 == 0:
            dilate += 1
        keep = evidence.filter(ImageFilter.MaxFilter(dilate))
        keep = keep.filter(ImageFilter.MaxFilter(max(7, (dilate // 2) | 1)))
        keep = keep.filter(ImageFilter.GaussianBlur(max(0.8, min(w, h) * 0.0035)))
        keep = keep.point(lambda p: 255 if p > 10 else 0)

        keep_arr = np.asarray(keep) > 0
        alpha_arr = np.asarray(alpha) > 16

        # Only background-like pixels outside the keep region are candidates.
        # Crucial: we only erase candidates reachable from the crop border.
        candidate = alpha_arr & (~keep_arr)
        if not candidate.any():
            return im

        remove = np.zeros((h, w), dtype=bool)
        q: deque[tuple[int, int]] = deque()

        # Seed flood with candidate pixels on all borders.
        for x0 in range(w):
            if candidate[0, x0]:
                remove[0, x0] = True
                q.append((x0, 0))
            if candidate[h - 1, x0]:
                remove[h - 1, x0] = True
                q.append((x0, h - 1))
        for y0 in range(h):
            if candidate[y0, 0]:
                remove[y0, 0] = True
                q.append((0, y0))
            if candidate[y0, w - 1]:
                remove[y0, w - 1] = True
                q.append((w - 1, y0))

        while q:
            x0, y0 = q.popleft()
            nx = x0 + 1
            if nx < w and candidate[y0, nx] and not remove[y0, nx]:
                remove[y0, nx] = True
                q.append((nx, y0))
            nx = x0 - 1
            if nx >= 0 and candidate[y0, nx] and not remove[y0, nx]:
                remove[y0, nx] = True
                q.append((nx, y0))
            ny = y0 + 1
            if ny < h and candidate[ny, x0] and not remove[ny, x0]:
                remove[ny, x0] = True
                q.append((x0, ny))
            ny = y0 - 1
            if ny >= 0 and candidate[ny, x0] and not remove[ny, x0]:
                remove[ny, x0] = True
                q.append((x0, ny))

        removed_ratio = float(remove.sum()) / max(1, w * h)
        if removed_ratio < 0.002:
            return im

        new_alpha = np.asarray(alpha).copy()
        new_alpha[remove] = 0

        # Fail safe: do not destroy most alpha.
        old_sum = max(1, int(np.asarray(alpha).sum()))
        new_sum = int(new_alpha.sum())
        if new_sum < old_sum * 0.35:
            return im

        out = im.copy()
        out.putalpha(Image.fromarray(new_alpha.astype("uint8"), "L"))
        bbox2 = out.getchannel("A").getbbox()
        return out.crop(bbox2) if bbox2 else im
    except Exception:
        return im


def _v14_1_clean_cutout_alpha(cut: Image.Image) -> Image.Image:
    """Final anti-halo cleanup for source-locked product cutouts.

    V14.2 adds a rectangle/matte killer for screenshots and product photos that
    keep a semi-transparent beige/gray source patch under the object. The logic
    is universal: it removes low-information neutral translucent pixels while
    preserving saturated, dark, branded, glass, and product-detail pixels.
    """
    im = cut.convert("RGBA")
    px = im.load()
    w, h = im.size

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            mx, mn = max(r, g, b), min(r, g, b)
            chroma = mx - mn
            luma = int(0.299 * r + 0.587 * g + 0.114 * b)
            sat = 0.0 if mx == 0 else chroma / float(mx)

            # Fully remove almost transparent pixels.
            if a < 42:
                px[x, y] = (r, g, b, 0)
                continue

            # V14.2: kill screenshot/source matte leaks: pale/neutral or weakly
            # colored translucent regions. This removes the visible rectangular
            # patch under bottles/products without keying on a specific object.
            neutralish = sat < 0.20 or chroma < 28
            pale_matte = 115 < luma < 248 and neutralish
            if a < 220 and pale_matte:
                px[x, y] = (r, g, b, 0)
                continue
            if a < 175 and sat < 0.28 and luma > 95:
                px[x, y] = (r, g, b, 0)
                continue

            # Keep colored/dark product details but harden alpha to avoid glow.
            if a < 210:
                if sat >= 0.20 or chroma >= 32 or luma < 105:
                    na = max(0, min(255, int((a - 42) * 255 / 168)))
                    px[x, y] = (r, g, b, na)
                else:
                    px[x, y] = (r, g, b, 0)
            elif a > 235:
                px[x, y] = (r, g, b, 255)

    alpha = im.getchannel("A")
    alpha = alpha.filter(ImageFilter.MedianFilter(3))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.16))
    alpha = alpha.point(lambda p: 0 if p < 34 else 255 if p > 214 else int((p - 34) * 255 / 180))
    im.putalpha(alpha)
    im = _v14_3_content_mask_matte_killer(im)

    # Final trim after matte removal. This removes empty transparent canvas/pad
    # that could otherwise still influence placement and shadows.
    bbox = im.getchannel("A").getbbox()
    if bbox:
        im = im.crop(bbox)
    return im


def _v14_1_subject_finish(subject: Image.Image) -> Image.Image:
    subject = _v14_1_clean_cutout_alpha(subject)
    # Very light clarity only; keep original product pixels recognizable.
    rgb = subject.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.025)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.06)
    out = rgb.convert("RGBA")
    out.putalpha(subject.getchannel("A"))
    return out


def _v14_1_contact_shadow(size: tuple[int, int], opacity: int = 54) -> Image.Image:
    sw, sh = size
    cw = max(24, int(sw * 0.78))
    ch = max(10, int(sh * 0.16))
    pad = max(24, int(max(sw, sh) * 0.10))
    shadow = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow, "RGBA")
    draw.ellipse((pad, pad, pad + cw, pad + ch), fill=(48, 30, 16, opacity))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(12, int(ch * 0.75))))
    return shadow


def _v14_1_background_focus(bg: Image.Image, mode: str) -> Image.Image:
    """Subtle foreground polish without destroying the Comfy design."""
    if mode not in {"product_ad", "flyer_poster", "social_post"}:
        return bg
    w, h = bg.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    # A soft central warm glow makes the subject read as the hero and hides minor busy artifacts.
    draw.ellipse((int(w * 0.10), int(h * 0.18), int(w * 0.90), int(h * 0.82)), fill=(255, 238, 198, 32))
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(22, int(min(w, h) * 0.035))))
    return Image.alpha_composite(bg, overlay)

def _postprocess_alpha_cutout(cut: Image.Image) -> Image.Image:
    cut = cut.convert("RGBA")
    alpha = cut.getchannel("A")
    alpha = alpha.filter(ImageFilter.MedianFilter(3))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.25))
    alpha = alpha.point(lambda p: 0 if p < 24 else min(255, int(p * 1.14)))
    cut.putalpha(alpha)
    return _v14_1_clean_cutout_alpha(cut)


def _remove_background_rembg(image: Image.Image) -> Image.Image | None:
    if not _env_bool("IMG2IMG_V13_USE_REMBG", True):
        return None
    try:
        from rembg import remove, new_session  # type: ignore
        import io

        model_name = os.getenv("IMG2IMG_V13_REMBG_MODEL", "u2netp").strip() or "u2netp"
        buf = io.BytesIO()
        image.convert("RGBA").save(buf, format="PNG")

        try:
            session = new_session(model_name)
            out = remove(buf.getvalue(), session=session)
        except TypeError:
            out = remove(buf.getvalue())
        except Exception:
            out = remove(buf.getvalue())

        cut = Image.open(io.BytesIO(out)).convert("RGBA")
        return _postprocess_alpha_cutout(cut)
    except Exception:
        return None


def _edge_bg(r: int, g: int, b: int, seed: tuple[int, int, int]) -> bool:
    sr, sg, sb = seed
    mx, mn = max(r, g, b), min(r, g, b)
    very_light = r > 224 and g > 224 and b > 224
    low_chroma_light = (mx - mn) < 46 and (r + g + b) / 3 > 168
    close = abs(r - sr) + abs(g - sg) + abs(b - sb) < 132
    return very_light or (low_chroma_light and close)


def _rgb_stats(r: int, g: int, b: int) -> tuple[int, int, float]:
    mx, mn = max(r, g, b), min(r, g, b)
    chroma = mx - mn
    luma = int(0.299 * r + 0.587 * g + 0.114 * b)
    sat = 0.0 if mx == 0 else chroma / float(mx)
    return chroma, luma, sat



def _color_subject_cutout(image: Image.Image) -> Image.Image | None:
    """Color/contrast subject mask for white-background product photos.

    This is intentionally conservative. It is used only when a meaningful colored/dark
    subject exists; otherwise callers fall back to edge flood / rembg.
    """
    try:
        import numpy as np  # type: ignore
    except Exception:
        return None

    im = image.convert("RGBA")
    alpha = im.getchannel("A")
    if alpha.getbbox() and min(alpha.getextrema()) < 255:
        return im

    arr = np.asarray(im.convert("RGB")).astype("int16")
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    chroma = mx - mn
    luma = (0.299 * r + 0.587 * g + 0.114 * b)
    sat = chroma / np.maximum(mx, 1)

    h, w = r.shape
    border = np.concatenate([
        arr[: max(2, h // 80), :, :].reshape(-1, 3),
        arr[-max(2, h // 80):, :, :].reshape(-1, 3),
        arr[:, : max(2, w // 80), :].reshape(-1, 3),
        arr[:, -max(2, w // 80):, :].reshape(-1, 3),
    ], axis=0)
    bg = np.median(border, axis=0)
    dist_bg = np.abs(arr - bg).sum(axis=2)

    # Main colorful-product rule: keeps orange, red, blue, green, product labels, etc.
    colorful = (sat > 0.095) & (chroma > 16) & (luma < 252)

    # Dark/detail rule: keeps dark logos/legs/details but avoids soft neutral shadows.
    dark_detail = (luma < 150) & (dist_bg > 110)

    # Warm product rule: helps pale beige/gold products on white background.
    warm_product = (r > 120) & (g > 65) & (b < 185) & (sat > 0.055) & (dist_bg > 58) & (luma < 245)

    # Shadow/white rejection.
    neutral_shadow = (luma > 122) & (chroma < 28) & (sat < 0.13)
    near_white = (luma > 218) & (chroma < 42)

    mask = (colorful | dark_detail | warm_product) & (~neutral_shadow) & (~near_white)

    # If too little subject was found, do not use this strategy.
    raw_pixels = int(mask.sum())
    if raw_pixels < max(120, int(w * h * 0.0018)):
        return None

    mask_img = Image.fromarray((mask * 255).astype("uint8"))
    # Connect body sections while preserving thin legs/antennae.
    mask_img = (
        mask_img
        .filter(ImageFilter.MaxFilter(5))
        .filter(ImageFilter.MinFilter(3))
        .filter(ImageFilter.GaussianBlur(0.85))
        .point(lambda p: 255 if p > 18 else 0)
    )

    bbox = mask_img.getbbox()
    if not bbox:
        return None
    bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    coverage = bbox_area / max(1, w * h)
    # Avoid selecting a huge frame. For product cutouts, useful subject bbox should not be most of the source.
    if coverage > 0.72:
        return None

    # Remove isolated noise outside the subject's broad horizontal band.
    # This helps avoid small compression speckles from white backgrounds.
    out = im.copy()
    a = mask_img.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.45))
    a = a.point(lambda p: 0 if p < 22 else min(255, int(p * 1.20)))
    out.putalpha(a)
    return out


def _edge_flood_cutout(image: Image.Image) -> Image.Image:
    from collections import deque
    im = image.convert("RGBA")
    # Respect already transparent user uploads.
    alpha = im.getchannel("A")
    if alpha.getbbox() and min(alpha.getextrema()) < 255:
        return im

    w, h = im.size
    px = im.load()
    samples = [
        px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1],
        px[w // 2, 0], px[w // 2, h - 1], px[0, h // 2], px[w - 1, h // 2],
    ]
    seed = tuple(int(sum(c[i] for c in samples) / len(samples)) for i in range(3))

    visited = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        idx = y * w + x
        if visited[idx]:
            return
        r, g, b, a = px[x, y]
        if a == 0 or _edge_bg(r, g, b, seed):
            visited[idx] = 1
            q.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)

    while q:
        x, y = q.popleft()
        r, g, b, a = px[x, y]
        if a:
            px[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                idx = ny * w + nx
                if not visited[idx]:
                    rr, gg, bb, aa = px[nx, ny]
                    if aa == 0 or _edge_bg(rr, gg, bb, seed):
                        visited[idx] = 1
                        q.append((nx, ny))

    # Second pass: remove source-photo shadows left inside the flood mask.
    # This is the main V13.1 fix for white-background product shots.
    px = im.load()
    kept_color = 0
    removed_shadow = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            chroma, luma, sat = _rgb_stats(r, g, b)
            # Product pixels usually have color/chroma or dark detail.
            product_like = (chroma >= 24 and sat >= 0.10) or (luma < 142 and chroma >= 8)
            shadow_like = (luma > 118 and chroma < 26 and sat < 0.14)
            near_white = luma > 214 and chroma < 36
            if shadow_like or near_white:
                px[x, y] = (r, g, b, 0)
                removed_shadow += 1
            elif product_like:
                kept_color += 1

    # If the image is mostly grayscale product and the cleanup was too aggressive, keep the flood result behavior.
    if kept_color < max(80, int(w * h * 0.002)):
        # Return before cleanup would be ideal, but for grayscale products keep all non-white dark pixels.
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    chroma, luma, sat = _rgb_stats(r, g, b)
                    if luma < 130 and chroma >= 4:
                        px[x, y] = (r, g, b, 255)

    alpha = im.getchannel("A")
    # Clean small translucent leftovers and feather only the edge.
    alpha = alpha.filter(ImageFilter.MedianFilter(3))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.35))
    alpha = alpha.point(lambda p: 0 if p < 28 else min(255, int(p * 1.18)))
    im.putalpha(alpha)
    return im


def _trim_alpha(image: Image.Image, pad: int = 8) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return image
    x1, y1, x2, y2 = bbox
    return image.crop((max(0, x1 - pad), max(0, y1 - pad), min(image.width, x2 + pad), min(image.height, y2 + pad)))


def _coverage_before_trim(image: Image.Image) -> float:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return 0.0
    return ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1, image.width * image.height)


def _isolate_subject(source_path: str, output_dir: str) -> tuple[str, dict[str, Any]]:
    src = Image.open(source_path).convert("RGBA")

    method = "rembg_u2netp_v13_3"
    cut = _remove_background_rembg(src)

    if cut is None:
        if _env_bool("IMG2IMG_V13_REMBG_REQUIRED", True):
            raise RuntimeError(
                "V13.3 requires rembg/onnxruntime for clean commercial cutouts. "
                "Run INSTALL_V13_3_REMBG_HARD_FIX.bat first."
            )
        color_candidate = _color_subject_cutout(src)
        if color_candidate is not None:
            method = "color_subject_mask_v13_2_fallback"
            cut = color_candidate
        else:
            method = "edge_flood_shadow_clean_v13_1_fallback"
            cut = _edge_flood_cutout(src)

    source_bbox = cut.getchannel("A").getbbox()
    if not source_bbox:
        raise RuntimeError("V13.3 subject cutout failed: empty alpha mask")

    source_coverage = ((source_bbox[2] - source_bbox[0]) * (source_bbox[3] - source_bbox[1])) / max(1, src.width * src.height)

    if method.startswith("rembg") and source_coverage > 0.78:
        if _env_bool("IMG2IMG_V13_REMBG_REQUIRED", True):
            raise RuntimeError(f"V13.3 rembg cutout rejected: source coverage too high ({source_coverage:.3f})")
        color_candidate = _color_subject_cutout(src)
        if color_candidate is not None:
            method = "color_subject_mask_v13_2_fallback_after_rembg_reject"
            cut = color_candidate
            source_bbox = cut.getchannel("A").getbbox()
            source_coverage = ((source_bbox[2] - source_bbox[0]) * (source_bbox[3] - source_bbox[1])) / max(1, src.width * src.height)

    pre_trim_coverage = float(source_coverage)
    cut = _trim_alpha(cut, pad=6)
    cut = _v14_1_clean_cutout_alpha(cut)
    cut = _trim_alpha(cut, pad=4)

    out = Path(output_dir) / f"v14_1_clean_subject_cutout_{uuid4().hex}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cut.save(out)

    bbox = cut.getchannel("A").getbbox()
    internal_coverage = 0.0
    if bbox:
        internal_coverage = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / max(1, cut.width * cut.height)

    return str(out), {
        "v13_segmentation": True,
        "v13_1_segmentation_cleanup": True,
        "v13_2_color_subject_mask": method.startswith("color_subject_mask_v13_2"),
        "v13_3_rembg_hard_fix": method.startswith("rembg"),
        "v13_1_marker": V13_1_MARKER,
        "v13_2_marker": V13_2_MARKER,
        "v13_3_marker": V13_3_MARKER,
        "v14_1_marker": V14_1_MARKER,
        "v14_2_marker": V14_2_MARKER,
        "v14_3_marker": V14_3_MARKER,
        "v14_4_marker": V14_4_MARKER,
        "v14_5_marker": V14_5_MARKER,
        "v14_1_cutout_alpha_cleanup": True,
        "v14_3_content_mask_matte_killer": True,
        "v14_4_border_only_matte_killer": True,
        "v14_5_all_in_one_product_stabilizer": True,
        "v14_2_rectangle_matte_killer": True,
        "v13_segmentation_method": method,
        "v13_cutout_bbox": bbox,
        "v13_cutout_coverage": round(float(pre_trim_coverage), 4),
        "v13_cutout_source_coverage": round(float(pre_trim_coverage), 4),
        "v13_cutout_internal_coverage": round(float(internal_coverage), 4),
    }


def _fit_contain(im: Image.Image, max_w: int, max_h: int) -> Image.Image:
    out = im.convert("RGBA")
    out.thumbnail((max(16, max_w), max(16, max_h)), Image.Resampling.LANCZOS)
    return out


def _subject_position(mode: str, subject: Image.Image, w: int, h: int, has_text: bool) -> tuple[int, int, int, int]:
    wide = subject.width >= subject.height * 1.25
    tall = subject.height >= subject.width * 1.45
    if mode == "person_identity":
        max_w, max_h, cy = int(w*0.68), int(h*0.82), int(h*0.54)
    elif mode == "background_replace":
        max_w, max_h, cy = int(w*0.78), int(h*0.78), int(h*0.55)
    elif mode == "flyer_poster":
        # V19 pro poster lock: real campaign composition.
        # Text has a large left design panel; product becomes a large right hero
        # grounded on a stage, similar to a commercial campaign poster.
        if has_text:
            if wide:
                max_w, max_h, cx, cy = int(w * 0.66), int(h * 0.30), int(w * 0.66), int(h * 0.61)
            elif tall:
                max_w, max_h, cx, cy = int(w * 0.43), int(h * 0.63), int(w * 0.70), int(h * 0.61)
            else:
                max_w, max_h, cx, cy = int(w * 0.50), int(h * 0.56), int(w * 0.68), int(h * 0.60)
            return max_w, max_h, cx, cy
        max_w = int(w * (0.74 if wide else 0.56))
        max_h = int(h * (0.32 if wide else 0.56))
        cy = int(h * 0.55)
    elif mode == "social_post":
        if has_text:
            max_w, max_h, cx, cy = int(w*0.58), int(h*0.46), int(w*0.64), int(h*0.61)
            return max_w, max_h, cx, cy
        max_w, max_h, cy = int(w*0.72), int(h*0.58), int(h*0.58)
    elif mode == "product_ad":
        # V17 logical product scale:
        # A product ad must look natural to the eye. The product should sit on
        # the stage/podium with breathing room, not touch the ceiling or dominate
        # the whole canvas. Universal rules based on aspect ratio, not product name.
        if wide:
            max_w, max_h, cy = int(w * 0.66), int(h * 0.26), int(h * 0.56)
        elif tall:
            max_w, max_h, cy = int(w * 0.38), int(h * 0.56), int(h * 0.52)
        else:
            max_w, max_h, cy = int(w * 0.50), int(h * 0.52), int(h * 0.54)
    else:
        max_w = int(w * (0.76 if wide else 0.58))
        max_h = int(h * (0.36 if wide else 0.62))
        cy = int(h * 0.55)
    return max_w, max_h, (w//2), cy


def _shadow(subject: Image.Image, blur: int = 24, opacity: int = 82) -> Image.Image:
    alpha = subject.getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda p: min(opacity, p))
    out = Image.new("RGBA", subject.size, (0,0,0,0))
    out.putalpha(alpha)
    return out



def _v15_glass_aware_subject_repair(subject: Image.Image, bg: Image.Image, x: int, y: int, mode: str) -> tuple[Image.Image, dict[str, Any]]:
    """Repair matte leaks inside transparent/glass products after final placement.

    This is not Coca-specific. It only targets weak, low-detail, neutral pixels
    inside the subject that look like old crop/background matte. It preserves:
    - dark product material
    - saturated labels/branding
    - sharp edges/text/reflections
    - metallic or colored details

    It uses the final background crop under the product, so glass/matte leak pixels
    blend into the actual scene instead of becoming hard-cut holes.
    """
    subject = subject.convert("RGBA")
    bg = bg.convert("RGBA")
    sw, sh = subject.size
    bw, bh = bg.size
    if sw < 8 or sh < 8:
        return subject, {"v15_glass_repair_applied": False, "v15_glass_repair_reason": "too_small"}

    try:
        import numpy as np

        s = np.asarray(subject).copy()
        a = s[:, :, 3].astype(np.int16)
        rgb = s[:, :, :3].astype(np.int16)

        # Build matching background crop at subject position.
        crop = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        src_left = max(0, x)
        src_top = max(0, y)
        src_right = min(bw, x + sw)
        src_bottom = min(bh, y + sh)
        if src_right <= src_left or src_bottom <= src_top:
            return subject, {"v15_glass_repair_applied": False, "v15_glass_repair_reason": "off_canvas"}
        crop_part = bg.crop((src_left, src_top, src_right, src_bottom))
        crop.alpha_composite(crop_part, (src_left - x, src_top - y))
        bgrgb = np.asarray(crop.convert("RGBA"))[:, :, :3].astype(np.int16)

        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        chroma = mx - mn
        luma = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.int16)
        sat = np.where(mx > 0, chroma / np.maximum(mx, 1), 0.0)

        gx = np.zeros_like(luma)
        gy = np.zeros_like(luma)
        gx[:, 1:] = np.abs(luma[:, 1:] - luma[:, :-1])
        gy[1:, :] = np.abs(luma[1:, :] - luma[:-1, :])
        edge = np.maximum(gx, gy)

        br, bgc, bb = bgrgb[:, :, 0], bgrgb[:, :, 1], bgrgb[:, :, 2]
        diff_bg = (np.abs(r - br) + np.abs(g - bgc) + np.abs(b - bb)) / 3.0

        alpha_mask = a > 24
        coverage = float(alpha_mask.mean())
        tall = sh >= sw * 1.20
        wide = sw >= sh * 1.25

        # Only run aggressively when there is a likely matte leak:
        # high alpha coverage/crop-like subject, or tall glass-like product.
        likely_leak = coverage > 0.58 or tall or mode == "product_ad"
        if not likely_leak:
            return subject, {"v15_glass_repair_applied": False, "v15_glass_repair_reason": "no_leak_signal", "v15_subject_alpha_coverage": coverage}

        # Matte-like pixels: neutral/pale/low-detail old background inside source.
        # Preserve white labels with text/edges by excluding stronger edge zones.
        matte_like = (
            alpha_mask
            & (luma > 108)
            & (luma < 252)
            & (sat < 0.18)
            & (chroma < 34)
            & (edge < 7)
        )

        # Also remove near-background weak matte patches even if a bit colored.
        near_bg_weak = (
            alpha_mask
            & (diff_bg < 42)
            & (sat < 0.22)
            & (edge < 6)
            & (luma > 95)
        )

        candidate = matte_like | near_bg_weak

        # Do not touch likely labels/details/edges/reflections.
        protect = (
            (sat > 0.24)
            | (chroma > 46)
            | (luma < 88)
            | (edge > 12)
        )
        candidate &= ~protect

        # Avoid changing too much of the product.
        ratio = float(candidate.sum()) / max(1, int(alpha_mask.sum()))
        if ratio < 0.004:
            return subject, {"v15_glass_repair_applied": False, "v15_glass_repair_reason": "low_candidate", "v15_candidate_ratio": ratio}

        max_ratio = 0.22 if tall else 0.14
        if ratio > max_ratio:
            # Conservative fallback: only near-background weak pixels.
            candidate = near_bg_weak & ~protect
            ratio = float(candidate.sum()) / max(1, int(alpha_mask.sum()))
            if ratio > max_ratio or ratio < 0.004:
                return subject, {"v15_glass_repair_applied": False, "v15_glass_repair_reason": "unsafe_candidate_ratio", "v15_candidate_ratio": ratio}

        # Blend candidate pixels into the actual final background. Use partial
        # transparency-like blend instead of alpha holes so glass still looks natural.
        blend = 0.88
        repaired = rgb.astype(np.float32)
        repaired[candidate] = repaired[candidate] * (1.0 - blend) + bgrgb.astype(np.float32)[candidate] * blend
        s[:, :, :3] = np.clip(repaired, 0, 255).astype("uint8")

        # Slight alpha relaxation on repaired matte leak, but never fully erase;
        # this prevents hard cutouts and keeps bottle transparency plausible.
        new_a = a.copy()
        new_a[candidate] = np.minimum(new_a[candidate], 120)
        s[:, :, 3] = np.clip(new_a, 0, 255).astype("uint8")

        out = Image.fromarray(s.astype("uint8"), "RGBA")
        return out, {
            "v15_glass_repair_applied": True,
            "v15_glass_repair_pixels": int(candidate.sum()),
            "v15_glass_repair_ratio": float(ratio),
            "v15_subject_alpha_coverage": coverage,
            "v15_glass_repair_mode": "background_blend_matte_leak",
        }
    except Exception as exc:
        return subject, {"v15_glass_repair_applied": False, "v15_glass_repair_error": str(exc)}



def _v16_anchor_subject_on_stage(subject: Image.Image, bg: Image.Image, mode: str, x: int, y: int) -> tuple[int, int, dict[str, Any]]:
    """Anchor product ads on the podium/table instead of letting them float or sink.

    Universal heuristic: for product ads we place the subject by bottom anchor,
    not only by center. Tall bottles/jars are reduced slightly and placed on the
    hero stage area. This avoids floor placement in front of the podium.
    """
    if mode != "product_ad":
        return x, y, {"v16_stage_anchor_applied": False, "v16_stage_anchor_reason": "mode_skip"}

    w, h = bg.size
    wide = subject.width >= subject.height * 1.25
    tall = subject.height >= subject.width * 1.45

    # V17: visually logical stage fit.
    # Tall bottles/boxes: bottom around the podium top/front blend, not on the
    # floor plane. Wide objects: slightly higher/lighter. Compact products:
    # classic catalog stage position.
    if tall:
        target_bottom = int(h * 0.78)
    elif wide:
        target_bottom = int(h * 0.72)
    else:
        target_bottom = int(h * 0.76)

    new_x = max(0, min(w - subject.width, x))
    new_y = max(0, min(h - subject.height, target_bottom - subject.height))
    return new_x, new_y, {
        "v16_stage_anchor_applied": True,
        "v16_stage_anchor_bottom": int(target_bottom),
        "v16_stage_anchor_subject_bottom": int(new_y + subject.height),
        "v16_stage_anchor_kind": "bottom_lock",
    }


def _v16_safe_transparency_repair(subject: Image.Image, bg: Image.Image, x: int, y: int, mode: str) -> tuple[Image.Image, dict[str, Any]]:
    """Safe matte repair for transparent/glass products.

    Fixes only small pale/neutral matte leaks that match the background, while
    preserving label text, liquid, reflections, edges and dark material.
    This is intentionally much safer than the broad V15 repair.
    """
    subject = subject.convert("RGBA")
    bg = bg.convert("RGBA")
    sw, sh = subject.size
    bw, bh = bg.size
    if mode != "product_ad":
        return subject, {"v16_safe_glass_repair_applied": False, "v16_safe_glass_repair_reason": "mode_skip"}
    if sw < 8 or sh < 8:
        return subject, {"v16_safe_glass_repair_applied": False, "v16_safe_glass_repair_reason": "too_small"}

    try:
        import numpy as np

        s = np.asarray(subject).copy()
        a = s[:, :, 3].astype(np.int16)
        rgb = s[:, :, :3].astype(np.int16)

        crop = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        src_left = max(0, x)
        src_top = max(0, y)
        src_right = min(bw, x + sw)
        src_bottom = min(bh, y + sh)
        if src_right <= src_left or src_bottom <= src_top:
            return subject, {"v16_safe_glass_repair_applied": False, "v16_safe_glass_repair_reason": "off_canvas"}
        crop_part = bg.crop((src_left, src_top, src_right, src_bottom))
        crop.alpha_composite(crop_part, (src_left - x, src_top - y))
        bg_rgb = np.asarray(crop)[:, :, :3].astype(np.int16)

        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        chroma = mx - mn
        luma = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.int16)
        sat = np.where(mx > 0, chroma / np.maximum(mx, 1), 0.0)

        gx = np.zeros_like(luma)
        gy = np.zeros_like(luma)
        gx[:, 1:] = np.abs(luma[:, 1:] - luma[:, :-1])
        gy[1:, :] = np.abs(luma[1:, :] - luma[:-1, :])
        edge = np.maximum(gx, gy)

        br, bgc, bb = bg_rgb[:, :, 0], bg_rgb[:, :, 1], bg_rgb[:, :, 2]
        diff_bg = (np.abs(r - br) + np.abs(g - bgc) + np.abs(b - bb)) / 3.0

        alpha_mask = a > 24
        tall = sh >= sw * 1.20

        # Very conservative leak candidate: pale neutral patch, low texture,
        # visually close to the background. This targets the beige rectangle in
        # transparent bottle necks without erasing the bottle itself.
        candidate = (
            alpha_mask
            & (luma > 145)
            & (luma < 248)
            & (sat < 0.12)
            & (chroma < 22)
            & (edge < 5)
            & (diff_bg < 30)
        )

        # Preserve details: brand label, dark liquid, edge highlights, cap,
        # reflections, text and any structured product evidence.
        protect = (
            (sat > 0.16)
            | (chroma > 30)
            | (edge > 8)
            | (luma < 118)
        )
        candidate &= ~protect

        candidate_ratio = float(candidate.sum()) / max(1, int(alpha_mask.sum()))
        max_ratio = 0.035 if tall else 0.025
        if candidate_ratio < 0.0005:
            return subject, {
                "v16_safe_glass_repair_applied": False,
                "v16_safe_glass_repair_reason": "low_candidate",
                "v16_safe_glass_candidate_ratio": float(candidate_ratio),
            }
        if candidate_ratio > max_ratio:
            return subject, {
                "v16_safe_glass_repair_applied": False,
                "v16_safe_glass_repair_reason": "unsafe_candidate_ratio",
                "v16_safe_glass_candidate_ratio": float(candidate_ratio),
            }

        repaired = rgb.astype(np.float32)
        blend = 0.94
        repaired[candidate] = repaired[candidate] * (1.0 - blend) + bg_rgb.astype(np.float32)[candidate] * blend
        s[:, :, :3] = np.clip(repaired, 0, 255).astype('uint8')

        new_a = a.copy()
        new_a[candidate] = np.minimum(new_a[candidate], 132)
        s[:, :, 3] = np.clip(new_a, 0, 255).astype('uint8')

        out = Image.fromarray(s.astype('uint8'), 'RGBA')
        return out, {
            "v16_safe_glass_repair_applied": True,
            "v16_safe_glass_repair_pixels": int(candidate.sum()),
            "v16_safe_glass_candidate_ratio": float(candidate_ratio),
            "v16_safe_glass_mode": "pale_bg_matte_only",
        }
    except Exception as exc:
        return subject, {"v16_safe_glass_repair_applied": False, "v16_safe_glass_repair_error": str(exc)}



def _v19_anchor_flyer_product_on_stage(subject: Image.Image, bg: Image.Image, mode: str, has_text: bool, x: int, y: int) -> tuple[int, int, dict[str, Any]]:
    """Ground flyer/poster hero product on the stage/podium.

    Product ads already use V16 anchor. Flyer/poster needs a different poster
    anchor: product should be large, right-side, and visually standing on the
    campaign set, not floating in the middle of the image.
    """
    if mode not in {"flyer_poster", "social_post"} or not has_text:
        return x, y, {"v19_flyer_stage_anchor_applied": False, "v19_flyer_stage_anchor_reason": "mode_skip"}
    w, h = bg.size
    wide = subject.width >= subject.height * 1.25
    tall = subject.height >= subject.width * 1.45
    if mode == "social_post":
        target_bottom = int(h * (0.84 if tall else 0.80))
    else:
        target_bottom = int(h * (0.86 if tall else (0.80 if wide else 0.84)))
    nx = max(0, min(w - subject.width, x))
    ny = max(0, min(h - subject.height, target_bottom - subject.height))
    return nx, ny, {
        "v19_flyer_stage_anchor_applied": True,
        "v19_flyer_stage_anchor_bottom": int(target_bottom),
        "v19_flyer_stage_anchor_subject_bottom": int(ny + subject.height),
    }


def _compose_final(background_path: str, cutout_path: str, mode: str, prompt: str, output_dir: str) -> tuple[str, dict[str, Any]]:
    bg = Image.open(background_path).convert("RGBA")
    bg = _v14_1_background_focus(bg, mode)
    w,h = bg.size
    subject = Image.open(cutout_path).convert("RGBA")
    subject = _v14_1_subject_finish(subject)
    headline_for_text, _, _ = _extract_copy(prompt)
    has_text = mode in {"flyer_poster", "social_post"} and not _text_disabled(prompt)
    max_w, max_h, cx, cy = _subject_position(mode, subject, w, h, has_text)
    subject = _fit_contain(subject, max_w, max_h)
    x = max(0, min(w-subject.width, cx - subject.width//2))
    y = max(0, min(h-subject.height, cy - subject.height//2))

    # V19: poster/flyer product grounding and hero scale.
    x, y, v19_flyer_anchor_meta = _v19_anchor_flyer_product_on_stage(subject, bg, mode, has_text, x, y)

    # V16: product ads use bottom anchoring so the product sits on the podium,
    # not on the floor plane or floating in front of the stage.
    x, y, v16_anchor_meta = _v16_anchor_subject_on_stage(subject, bg, mode, x, y)

    # V16: safer transparency repair. Only tiny pale background-like leaks are
    # blended; internal bottle details are preserved.
    subject, v16_repair_meta = _v16_safe_transparency_repair(subject, bg, x, y, mode)

    # Contact shadow only: avoids the old gray silhouette/glow behind the product.
    contact = _v14_1_contact_shadow((subject.width, subject.height), opacity=44 if mode == "product_ad" else 38)
    sx = int(x + subject.width * 0.50 - contact.width * 0.50)
    sy = int(y + subject.height * (0.90 if subject.width > subject.height else 0.95))
    sx = max(-contact.width//2, min(w-contact.width//2, sx))
    sy = max(0, min(h-contact.height, sy))
    bg.alpha_composite(contact, (sx, sy))

    bg.alpha_composite(subject, (x,y))
    img = ImageEnhance.Contrast(bg.convert("RGB")).enhance(1.04)
    img = ImageEnhance.Color(img).enhance(1.03).convert("RGBA")
    text_meta = _draw_text_block(img, mode, prompt, (x, y, x + subject.width, y + subject.height), subject)
    out = Path(output_dir) / f"generated_v13_commercial_{mode}_{uuid4().hex}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=96)
    return str(out), {
        "v13_final_composite": True,
        "v14_1_marker": V14_1_MARKER,
        "v14_2_marker": V14_2_MARKER,
        "v14_3_marker": V14_3_MARKER,
        "v14_4_marker": V14_4_MARKER,
        "v14_5_marker": V14_5_MARKER,
        "v15_marker": V15_MARKER,
        "v16_marker": V16_MARKER,
        "v17_marker": V17_MARKER,
        "v18_marker": V18_MARKER,
        "v19_marker": V19_MARKER,
        "v19_1_marker": V19_1_MARKER,
        "v19_1_syntax_repair_no_fallback": True,
        "v18_ai_copywriter_poster_layout": True,
        "v19_pro_poster_composition_lock": True,
        **v19_flyer_anchor_meta,
        "v17_logical_product_scale_stage_fit": True,
        "v15_glass_aware_final_repair": True,
        "v16_stage_anchor_safe_glass": True,
        **v16_anchor_meta,
        **v16_repair_meta,
        "v14_1_final_composite_polish": True,
        "v14_3_content_mask_matte_killer": True,
        "v14_4_border_only_matte_killer": True,
        "v14_5_all_in_one_product_stabilizer": True,
        "v14_2_rectangle_matte_killer": True,
        "v14_1_contact_shadow": True,
        "v14_1_silhouette_shadow_removed": True,
        **text_meta,
        "v13_subject_bbox_final": [int(x), int(y), int(x+subject.width), int(y+subject.height)],
        "v13_background_path": str(background_path),
        "v13_cutout_path": str(cutout_path),
        "v13_text_rendered": bool(text_meta.get("v18_text_rendered")),
        "v18_text_reason": text_meta.get("v18_text_reason"),
    }


def _qc_output(path: str) -> dict[str, Any]:
    try:
        im = Image.open(path).convert("RGB")
        stat = ImageStat.Stat(im)
        var = sum(stat.var) / 3.0
        return {"ok": bool(var > 40), "variance": round(float(var), 2), "size": list(im.size)}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


async def generate_v13_commercial(req: Img2ImgRequest) -> RenderResult:
    mode = _resolve_mode(req.mode, req.subject_type, req.prompt or "")
    if mode not in {"product_ad", "flyer_poster", "background_replace", "person_identity", "creative_image", "social_post"}:
        mode = "product_ad"
    out_dir = req.output_dir or "static/images"
    width = int(req.width or 1024)
    height = int(req.height or 1024)
    if mode == "social_post":
        width = height = min(max(min(width, height), 768), 1024)
    try:
        cutout_path, seg_meta = _isolate_subject(req.source_image_path, out_dir)
        bg_path, bg_meta = await _generate_ai_background(mode, req.prompt or "", req.negative_prompt or "", width, height, req.style, out_dir)
        final_path, comp_meta = _compose_final(bg_path, cutout_path, mode, req.prompt or "", out_dir)
        qc = _qc_output(final_path)
        metadata: dict[str, Any] = {
            "renderer_version": "v19-1-pro-poster-composition-lock-syntax-repair",
            "v13_marker": V13_MARKER,
            "v13_1_marker": V13_1_MARKER,
            "v13_2_marker": V13_2_MARKER,
            "v13_3_marker": V13_3_MARKER,
            "v13_4_marker": V13_4_MARKER,
            "v14_marker": V14_MARKER,
            "v14_1_marker": V14_1_MARKER,
            "v13_commercial_engine": True,
            "v14_workflow_binding": True,
            "v13_background_only": True,
            "v13_exact_source_composite": True,
            "mode": mode,
            "resolved_mode": mode,
            "category": "commercial_subject",
            "subject_type": "product" if mode in {"product_ad", "flyer_poster", "background_replace", "social_post"} else (req.subject_type or "subject"),
            "selected_layout": "v13_clean_commercial_composite",
            "fallback_used": False,
            "overlay_enabled": mode in {"flyer_poster", "social_post"} and not _text_disabled(req.prompt or ""),
            "comfy_text": False,
            "source_image_path": req.source_image_path,
            "prompt_pack": {
                "positive_prompt": _bg_prompt(mode, req.prompt or ""),
                "negative_prompt": _bg_negative(mode, req.negative_prompt or ""),
                "steps": _v14_steps(),
                "cfg": _v14_cfg(),
                "denoise": _v14_denoise(),
                "workflow_name": _v14_workflow_name(mode),
            },
            "qc": qc,
            "v12_7_1_runtime_hook": True,
            "v12_7_1_runtime_hook_skipped": "v13_already_final",
        }
        metadata.update(seg_meta)
        metadata.update(bg_meta)
        metadata.update(comp_meta)
        return RenderResult(
            success=True,
            local_path=final_path,
            public_url=backend_public_image_url(final_path),
            renderer_used="v14_workflow_binding_pro_comfy",
            provider=f"{V14_PROVIDER}-{mode}-no-fallback",
            metadata=metadata,
        )
    except Exception as exc:
        return RenderResult(
            success=False,
            error=f"V13 commercial engine failed: {exc}",
            provider="comfy-director-v13-commercial-engine-exception",
            metadata={
                "renderer_version": "v19-1-pro-poster-composition-lock-syntax-repair",
                "v13_marker": V13_MARKER,
                "v13_commercial_engine": True,
                "mode": mode,
                "source_image_path": req.source_image_path,
            },
        )
