"""Autonomous Flyer Director for AI Studio Pro.

Goal:
- User can upload an image only.
- The backend understands the source category and creates useful marketing copy.
- The real flyer renderer receives structured copy/layout direction instead of generic text.
- Works for products, bags, bottles, food, insects/worms, pets/animals, posters and generic objects.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class FlyerCopy:
    subject_label: str
    category: str
    tone: str
    headline: str
    subheadline: str
    cta: str
    style_direction: str
    layout: str


_PRODUCT_WORDS = {
    "bag": "fashion accessory",
    "handbag": "fashion accessory",
    "purse": "fashion accessory",
    "shoe": "fashion",
    "sneaker": "fashion",
    "watch": "luxury accessory",
    "perfume": "beauty product",
    "bottle": "beverage product",
    "drink": "beverage product",
    "can": "beverage product",
    "cosmetic": "beauty product",
    "cream": "beauty product",
    "phone": "tech product",
    "laptop": "tech product",
}

_INSECT_WORDS = {"worm", "insect", "larva", "caterpillar", "bug", "beetle", "ant"}
_FOOD_WORDS = {"food", "burger", "pizza", "cake", "coffee", "restaurant", "meal", "sandwich"}
_PERSON_WORDS = {"person", "portrait", "face", "woman", "man", "girl", "boy"}
_PET_WORDS = {"dog", "cat", "pet", "animal", "bird", "horse"}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[\w\u0600-\u06FF]+", (text or "").lower()))


def infer_subject_label(subject_type: str | None, prompt: str | None, vision: dict[str, Any] | None = None) -> str:
    """Infer a short human subject label from prompt + vision metadata."""
    raw = " ".join([
        str(subject_type or ""),
        str(prompt or ""),
        str((vision or {}).get("subject") or ""),
        str((vision or {}).get("caption") or ""),
        str((vision or {}).get("summary") or ""),
    ]).lower()
    w = _words(raw)

    for key in ["handbag", "purse", "bag", "perfume", "bottle", "can", "watch", "shoe", "sneaker", "phone", "laptop"]:
        if key in w:
            return "handbag" if key in {"handbag", "purse", "bag"} else key
    if w & _INSECT_WORDS:
        if "worm" in w:
            return "worm"
        if "caterpillar" in w:
            return "caterpillar"
        return "insect"
    if w & _FOOD_WORDS:
        return "food"
    if w & _PET_WORDS:
        return "pet"
    if w & _PERSON_WORDS:
        return "portrait"
    if "product" in (subject_type or "").lower():
        return "product"
    return "featured subject"


def build_autonomous_flyer_copy(
    *,
    subject_type: str | None,
    prompt: str | None,
    headline: str | None = None,
    subheadline: str | None = None,
    cta: str | None = None,
    vision: dict[str, Any] | None = None,
) -> FlyerCopy:
    """Create production-safe flyer copy from image understanding and optional user text.

    User-provided copy always wins. When missing, this function writes useful,
    subject-aware marketing text instead of generic placeholders.
    """
    subject = infer_subject_label(subject_type, prompt, vision)
    stype = (subject_type or "").lower()
    pwords = _words(prompt or "")

    if subject in {"handbag", "purse", "bag"}:
        category = "fashion accessory"
        tone = "premium fashion"
        auto_headline = "ELEGANT EVERYDAY STYLE"
        auto_sub = "A refined black leather look with golden details."
        auto_cta = "SHOP THE LOOK"
        style = "luxury fashion campaign, warm neutral palette, elegant editorial spacing, premium retail poster"
        layout = "right hero product, left editorial copy card, strong CTA button, clean luxury negative space"
    elif subject in {"bottle", "can", "drink"} or "beverage" in stype:
        category = "beverage product"
        tone = "refreshing commercial"
        auto_headline = "REFRESH YOUR MOMENT"
        auto_sub = "A bold drink campaign with clean energy and crisp highlights."
        auto_cta = "DISCOVER MORE"
        style = "fresh beverage campaign, energetic lighting, premium studio/lifestyle background, clean commercial poster"
        layout = "single hero bottle, clear text zone, strong CTA, no duplicate beverage container"
    elif subject in {"perfume", "cosmetic", "cream"}:
        category = "beauty product"
        tone = "luxury beauty"
        auto_headline = "PURE LUXURY"
        auto_sub = "A premium beauty visual crafted for elegant campaigns."
        auto_cta = "EXPLORE NOW"
        style = "luxury beauty ad, soft gradients, refined reflections, clean premium poster"
        layout = "hero product with elegant side copy and CTA"
    elif subject in {"worm", "caterpillar", "insect"} or "insect" in stype or "animal" in stype:
        category = "nature / educational"
        tone = "macro discovery"
        auto_headline = "DISCOVER HIDDEN NATURE"
        auto_sub = "A close-up journey into the small worlds around us."
        auto_cta = "LEARN MORE"
        style = "macro nature poster, organic textures, educational campaign style, realistic natural environment"
        layout = "large living subject hero, readable educational text area, no product-ad styling"
    elif subject in {"food"} or pwords & _FOOD_WORDS:
        category = "food campaign"
        tone = "appetizing"
        auto_headline = "FRESH FLAVOR AWAITS"
        auto_sub = "A clean campaign visual designed to make every detail tempting."
        auto_cta = "ORDER NOW"
        style = "restaurant flyer, warm appetizing light, clean menu poster, inviting composition"
        layout = "food hero with menu-style copy zone and CTA"
    elif subject == "portrait" or "person" in stype:
        category = "personal campaign"
        tone = "editorial portrait"
        auto_headline = "NEW STORY. NEW LOOK."
        auto_sub = "A polished visual built around the uploaded portrait."
        auto_cta = "VIEW MORE"
        style = "editorial portrait poster, clean modern layout, respectful identity-preserving presentation"
        layout = "portrait hero with tasteful text zone"
    else:
        category = "creative campaign"
        tone = "modern promotional"
        auto_headline = "FEATURE HIGHLIGHT"
        auto_sub = "A polished campaign visual built from your uploaded image."
        auto_cta = "LEARN MORE"
        style = "modern promotional poster, clean design, strong hero subject, premium spacing"
        layout = "single hero subject with balanced copy panel and CTA"

    return FlyerCopy(
        subject_label=subject,
        category=category,
        tone=tone,
        headline=(headline or "").strip() or auto_headline,
        subheadline=(subheadline or "").strip() or auto_sub,
        cta=(cta or "").strip() or auto_cta,
        style_direction=style,
        layout=layout,
    )


def append_autonomous_flyer_marker(prompt: str, copy: FlyerCopy) -> str:
    marker = (
        f"\n\n[AUTONOMOUS_FLYER_DIRECTOR]"
        f"\nsubject_label={copy.subject_label}"
        f"\ncategory={copy.category}"
        f"\ntone={copy.tone}"
        f"\nheadline={copy.headline}"
        f"\nsubheadline={copy.subheadline}"
        f"\ncta={copy.cta}"
        f"\nstyle_direction={copy.style_direction}"
        f"\nlayout={copy.layout}"
        f"\n[/AUTONOMOUS_FLYER_DIRECTOR]"
    )
    return ((prompt or "").strip() + marker).strip()


def parse_autonomous_flyer_marker(prompt: str | None) -> dict[str, str]:
    text = prompt or ""
    m = re.search(r"\[AUTONOMOUS_FLYER_DIRECTOR\](.*?)\[/AUTONOMOUS_FLYER_DIRECTOR\]", text, re.S)
    if not m:
        return {}
    values: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip()
    return values
