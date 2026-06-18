from __future__ import annotations

from dataclasses import dataclass
from PIL import Image

from .utils import looks_like_packshot, open_source


@dataclass
class DesignDecision:
    category: str
    is_packshot: bool
    template: str
    confidence: float
    reason: str


def _visual_stats(img: Image.Image | None) -> dict:
    if img is None:
        return {"skin_ratio": 0.0, "edge_neutral": 0.0, "dark_ratio": 0.0, "bright_neutral_ratio": 0.0}
    small = img.convert("RGB").resize((128, 128), Image.LANCZOS)
    pix = list(small.getdata())
    total = max(1, len(pix))
    skin = 0
    dark = 0
    bright_neutral = 0
    for r, g, b in pix:
        avg = (r + g + b) / 3
        sat = max(r, g, b) - min(r, g, b)
        # broad skin / warm leather / wrist detector. Used only to avoid false packshot routing.
        if r > 80 and g > 42 and b < 185 and r >= g >= b * 0.72 and (r - b) > 28:
            skin += 1
        if avg < 78:
            dark += 1
        if avg > 178 and sat < 34:
            bright_neutral += 1
    edge = []
    for x in range(128):
        edge.append(small.getpixel((x, 0)))
        edge.append(small.getpixel((x, 127)))
    for y in range(128):
        edge.append(small.getpixel((0, y)))
        edge.append(small.getpixel((127, y)))
    neutral = 0
    for r, g, b in edge:
        avg = (r + g + b) / 3
        if avg > 178 and abs(r - g) < 28 and abs(g - b) < 28:
            neutral += 1
    return {
        "skin_ratio": skin / total,
        "edge_neutral": neutral / max(1, len(edge)),
        "dark_ratio": dark / total,
        "bright_neutral_ratio": bright_neutral / total,
    }


def _has_watch_words(text: str) -> bool:
    return any(k in text for k in ("watch", "wrist", "clock", "montre", "automatic", "timepiece", "horology"))


def _has_handbag_words(text: str) -> bool:
    # Do not let the generic word "leather" alone force handbag. Watches also have leather straps.
    return any(k in text for k in ("handbag", "purse", "sac", "bag", "tote", "shoulder bag", "crossbody"))


def decide_template(plan) -> DesignDecision:
    analysis = getattr(plan, "analysis", None)
    src = open_source(getattr(plan, "source_subject_path", None))
    subject = f"{getattr(analysis, 'subject_label', '')} {getattr(analysis, 'category', '')} {getattr(analysis, 'subject_type', '')}".lower()
    prompt = str(getattr(plan, 'metadata', {}).get('user_prompt', '') or '').lower()
    text = f"{subject} {prompt}"
    stats = _visual_stats(src)

    visual_packshot = looks_like_packshot(src)
    # Trust actual image geometry more than upstream analysis. The upstream vision route can fail
    # and label real photos as document/handbag. A warm wrist/lifestyle scene must NOT become a packshot.
    likely_lifestyle = stats["skin_ratio"] > 0.16 and stats["edge_neutral"] < 0.34
    pack = bool(visual_packshot and not likely_lifestyle)

    # Strong visual override for watches on wrist/lifestyle photos when Ollama vision fails.
    # The previous engine sent watch photos to handbag_packshot because analysis came back as document/handbag.
    if likely_lifestyle and (stats["skin_ratio"] > 0.20 or _has_watch_words(text)):
        return DesignDecision("watch", False, "watch_lifestyle", 0.88, "visual wrist/lifestyle override")

    if _has_watch_words(text):
        return DesignDecision("watch", pack, "watch_packshot" if pack else "watch_lifestyle", 0.92, "watch keywords or visual label")
    if _has_handbag_words(text):
        return DesignDecision("handbag", pack, "handbag_packshot" if pack else "fashion_lifestyle", 0.92, "handbag/fashion product")
    if any(k in text for k in ("cosmetic", "perfume", "cream", "serum", "makeup", "beauty")):
        return DesignDecision("cosmetics", pack, "cosmetics_packshot" if pack else "generic_editorial", 0.86, "beauty/cosmetic product")
    if any(k in text for k in ("bottle", "drink", "wine", "juice", "beverage")):
        return DesignDecision("bottle", pack, "bottle_packshot" if pack else "generic_editorial", 0.84, "bottle/beverage product")
    if any(k in text for k in ("food", "meal", "burger", "pizza", "coffee", "dessert")):
        return DesignDecision("food", pack, "food_editorial", 0.84, "food product")
    if any(k in text for k in ("phone", "laptop", "keyboard", "headphone", "camera", "tech")):
        return DesignDecision("tech", pack, "tech_packshot" if pack else "generic_editorial", 0.84, "tech product")

    # If the image is a lifestyle scene but no reliable category exists, prefer editorial photo layout.
    if likely_lifestyle:
        return DesignDecision("watch", False, "watch_lifestyle", 0.72, "lifestyle warm-scene safe default")

    return DesignDecision("general_product", pack, "generic_packshot" if pack else "generic_editorial", 0.70, "fallback category template")
