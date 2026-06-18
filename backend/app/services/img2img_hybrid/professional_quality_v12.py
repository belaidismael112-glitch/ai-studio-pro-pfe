from __future__ import annotations

"""V12 Prompt-First Commercial Quality helpers.

This module is intentionally pure-python and dependency-light.  It does not change
routes or workers; it builds professional creative briefs from user input, settings,
mode, detected subject and category.
"""

from dataclasses import dataclass, asdict
import re
from typing import Any

V12_MARKER = "AI_STUDIO_V12_PROMPT_FIRST_COMMERCIAL_ENGINE"
V12_VERSION = "v12-prompt-first-commercial-quality-engine"

STYLE_KEYWORDS = {
    "luxury": ["luxury", "premium", "high-end", "elegant", "fashion", "gold", "beige", "brown", "warm", "boutique"],
    "minimal": ["minimal", "clean", "simple", "white", "negative space", "modern"],
    "cinematic": ["cinematic", "dramatic", "moody", "film", "noir", "spotlight"],
    "studio": ["studio", "packshot", "product photography", "controlled lighting", "catalog"],
    "lifestyle": ["lifestyle", "home", "interior", "street", "outdoor", "scene", "environment"],
    "social": ["instagram", "social", "story", "post", "reel", "tiktok", "carousel"],
    "editorial": ["editorial", "magazine", "campaign", "cover", "poster", "flyer"],
    "futuristic": ["futuristic", "tech", "neon", "cyber", "modern launch"],
    "natural": ["natural", "organic", "earth", "eco", "macro", "scientific"],
}

CATEGORY_DEFAULTS = {
    "watch": {
        "label": "luxury wristwatch",
        "style": "luxury",
        "scene": "warm premium studio with refined beige-brown gradient, metallic highlights and elegant shadows",
        "headline": "PRECISION IN STYLE",
        "subheadline": "Premium timepiece campaign",
        "cta": "DISCOVER MORE",
    },
    "handbag": {
        "label": "premium handbag",
        "style": "luxury",
        "scene": "boutique fashion set with soft fabric, warm highlights and refined editorial spacing",
        "headline": "ELEGANT BY DESIGN",
        "subheadline": "A refined fashion statement",
        "cta": "EXPLORE",
    },
    "bottle": {
        "label": "bottle product",
        "style": "studio",
        "scene": "premium product studio with glossy surface, soft reflections and clean brand lighting",
        "headline": "PURE IMPRESSION",
        "subheadline": "Crafted for a premium moment",
        "cta": "SHOP THE COLLECTION",
    },
    "cosmetics": {
        "label": "beauty product",
        "style": "luxury",
        "scene": "beauty campaign set with cream tones, soft spotlight, glossy surface and elegant shadows",
        "headline": "RADIANT DETAILS",
        "subheadline": "Beauty campaign visual",
        "cta": "DISCOVER",
    },
    "tech": {
        "label": "technology product",
        "style": "futuristic",
        "scene": "clean futuristic product stage with geometric light, dark gradient and sharp reflections",
        "headline": "DESIGNED TO PERFORM",
        "subheadline": "Modern technology visual",
        "cta": "LEARN MORE",
    },
    "food": {
        "label": "food product",
        "style": "lifestyle",
        "scene": "appetizing commercial food scene with warm light, natural props and shallow depth of field",
        "headline": "FRESHLY SERVED",
        "subheadline": "Taste-focused commercial visual",
        "cta": "ORDER NOW",
    },
    "person": {
        "label": "person",
        "style": "studio",
        "scene": "professional portrait studio with clean background, soft key light and realistic skin tone",
        "headline": "PROFESSIONAL PORTRAIT",
        "subheadline": "Clean identity-safe visual",
        "cta": "",
    },
    "document": {
        "label": "document",
        "style": "minimal",
        "scene": "clean presentation layout with readable structure and neutral background",
        "headline": "CLEAR PRESENTATION",
        "subheadline": "Clean visual communication",
        "cta": "",
    },
    "generic_product": {
        "label": "uploaded product",
        "style": "studio",
        "scene": "premium commercial studio with clean background, controlled reflections and soft realistic shadows",
        "headline": "DESIGNED TO STAND OUT",
        "subheadline": "Premium commercial product visual",
        "cta": "DISCOVER MORE",
    },
}

@dataclass
class CreativeBrief:
    marker: str
    version: str
    mode: str
    category: str
    subject_label: str
    user_prompt_present: bool
    user_direction: str
    style_profile: str
    scene_direction: str
    commercial_goal: str
    composition: str
    text_policy: str
    headline: str
    subheadline: str
    cta: str
    quality_directives: str
    negative_directives: str
    size_intent: str
    reference_lock: str


def strip_markers(text: str, max_len: int = 700) -> str:
    t = re.sub(r"\[[A-Z0-9_]+:.*?\]", " ", str(text or ""), flags=re.I | re.S)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_len]


def marker_value(text: str, *names: str, max_len: int = 120) -> str:
    for name in names:
        m = re.search(rf"\[{re.escape(name)}:(.*?)\]", str(text or ""), flags=re.I | re.S)
        if m:
            v = re.sub(r"\s+", " ", m.group(1)).strip()
            if v:
                return v[:max_len]
    return ""


def category_defaults(category: str) -> dict[str, str]:
    c = (category or "generic_product").lower().replace(" ", "_")
    return dict(CATEGORY_DEFAULTS.get(c, CATEGORY_DEFAULTS["generic_product"]))


def infer_style(user_prompt: str, explicit_style: str | None, category: str, mode: str) -> str:
    text = f"{user_prompt or ''} {explicit_style or ''}".lower()
    scores: dict[str, int] = {}
    for style, words in STYLE_KEYWORDS.items():
        score = sum(1 for w in words if w in text)
        if score:
            scores[style] = score
    if scores:
        return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[0][0]
    if mode in {"flyer_poster", "social_post", "product_ad"}:
        return category_defaults(category)["style"]
    if mode in {"person_identity", "identity"}:
        return "studio"
    if mode in {"background_replace", "background_lifestyle"}:
        return "lifestyle"
    return category_defaults(category)["style"]


def size_intent(width: int | None, height: int | None) -> str:
    w, h = int(width or 0), int(height or 0)
    if not w or not h:
        return "balanced square commercial composition"
    ratio = w / max(1, h)
    if ratio < 0.82:
        return "portrait layout with vertical hierarchy, hero subject and clean headline/CTA spacing"
    if ratio > 1.25:
        return "landscape banner-like layout with wide hero composition and side-safe text areas"
    return "square layout with centered focal point, balanced breathing room and social-ready composition"


def mode_goal(mode: str, category: str) -> str:
    m = (mode or "auto").lower().replace("-", "_")
    if m == "product_ad":
        return "create a client-ready commercial product advertisement, not a generic template or mockup"
    if m == "flyer_poster":
        return "create a professional marketing flyer/poster with hierarchy, visual focus and campaign polish"
    if m == "social_post":
        return "create a platform-ready premium social post with strong crop, clear message and high-end finish"
    if m in {"background_replace", "background_lifestyle"}:
        return "create a realistic lifestyle/background transformation with natural integration and no typography"
    if m in {"person_identity", "identity"}:
        return "create an identity-safe professional portrait/editorial visual while preserving the person"
    if m == "creative_image":
        return "create a bold premium creative visual that respects the source and remains commercially polished"
    return "choose the best professional commercial direction for the uploaded reference"


def composition_for(mode: str, style: str, category: str, prompt: str) -> str:
    text = (prompt or "").lower()
    if "center" in text or "centre" in text:
        subject_pos = "hero subject centered with intentional premium spacing"
    elif "left" in text:
        subject_pos = "hero subject offset left with balanced copy space"
    elif "right" in text:
        subject_pos = "hero subject offset right with balanced copy space"
    else:
        subject_pos = "hero subject placed using the selected mode layout, never as a cheap pasted card"
    style_map = {
        "luxury": "warm refined light, elegant shadows, premium materials, gold/cream/brown accents when appropriate",
        "minimal": "clean negative space, very few elements, crisp edges and calm visual hierarchy",
        "cinematic": "dramatic directional light, contrast, atmosphere and depth",
        "studio": "controlled studio lighting, realistic contact shadows, reflections and product clarity",
        "lifestyle": "believable environment, natural props, coherent perspective and integrated lighting",
        "editorial": "magazine-grade composition, elegant type-safe areas and polished spacing",
        "futuristic": "modern geometry, clean gradients, sharp reflections and refined tech lighting",
        "natural": "macro detail, natural textures, authentic environment and realistic light",
    }
    return f"{subject_pos}; {style_map.get(style, style_map['studio'])}; avoid black bars, empty white boxes, placeholder cards and repeated templates"


def build_text_policy(mode: str, user_prompt: str, category: str) -> tuple[str, str, str, str]:
    d = category_defaults(category)
    headline = marker_value(user_prompt, "AI_STUDIO_HEADLINE", "HEADLINE")
    subheadline = marker_value(user_prompt, "AI_STUDIO_SUBHEADLINE", "SUBHEADLINE")
    cta = marker_value(user_prompt, "AI_STUDIO_CTA", "CTA")
    prompt_clean = strip_markers(user_prompt)
    has_prompt = bool(prompt_clean)
    mode = (mode or "").lower().replace("-", "_")
    if not headline and not has_prompt:
        headline = d["headline"] if mode in {"flyer_poster", "social_post"} else ""
    if not subheadline and not has_prompt:
        subheadline = d["subheadline"] if mode in {"flyer_poster", "social_post"} else ""
    if not cta and not has_prompt:
        cta = d["cta"] if mode in {"flyer_poster", "social_post"} else ""
    if mode == "product_ad":
        if headline or cta:
            policy = "use only concise optional ad copy requested by the user; keep product and scene dominant"
        else:
            policy = "no hardcoded headline or CTA; prioritize premium commercial photography without forced text"
    elif mode in {"flyer_poster", "social_post"}:
        policy = "if user provided copy, use it; if not, generate concise category-appropriate copy, never old generic defaults"
    else:
        policy = "no typography unless explicitly requested; no labels, no fake text, no placeholder copy"
        headline = headline if headline else ""
        subheadline = subheadline if subheadline else ""
        cta = cta if cta else ""
    return policy, headline.upper() if headline else "", subheadline, cta.upper() if cta else ""


def reference_lock(mode: str, category: str, strength: float | None) -> str:
    m = (mode or "").lower().replace("-", "_")
    try:
        s = float(strength) if strength is not None else None
    except Exception:
        s = None
    if m in {"person_identity", "identity"}:
        return "very strong identity lock: preserve same face geometry, age impression, skin tone, hair, eyes, nose and expression"
    if m in {"product_ad", "flyer_poster", "social_post", "background_replace", "background_lifestyle"}:
        base = "strong source lock: preserve product silhouette, proportions, materials, colors, logo/label if visible and key details"
        if s is not None and s >= 0.65:
            return base + "; allow stronger environment/style changes but do not redesign the subject"
        return base
    return "preserve recognizable source elements while allowing controlled creative styling"


def build_creative_brief(mode: str, category: str, subject_label: str, user_prompt: str, width: int | None, height: int | None, strength: float | None = None, explicit_style: str | None = None) -> CreativeBrief:
    mode_n = (mode or "auto").lower().replace("-", "_")
    category_n = (category or "generic_product").lower().replace(" ", "_")
    defaults = category_defaults(category_n)
    user_dir = strip_markers(user_prompt)
    style = infer_style(user_dir, explicit_style, category_n, mode_n)
    text_policy, headline, subheadline, cta = build_text_policy(mode_n, user_prompt, category_n)
    if user_dir:
        scene = f"follow the user's requested scene/style first: {user_dir}"
    else:
        scene = defaults["scene"]
    return CreativeBrief(
        marker=V12_MARKER,
        version=V12_VERSION,
        mode=mode_n,
        category=category_n,
        subject_label=subject_label or defaults["label"],
        user_prompt_present=bool(user_dir),
        user_direction=user_dir,
        style_profile=style,
        scene_direction=scene,
        commercial_goal=mode_goal(mode_n, category_n),
        composition=composition_for(mode_n, style, category_n, user_dir),
        text_policy=text_policy,
        headline=headline,
        subheadline=subheadline,
        cta=cta,
        quality_directives=(
            "client-ready commercial finish, intentional art direction, strong focal point, realistic lighting, coherent perspective, "
            "premium color harmony, polished spacing, clean edges, no placeholder panels, no repeated template look, no dead empty blocks"
        ),
        negative_directives=(
            "cheap template, generic black bars, empty white cards, placeholder blocks, fake text, unreadable typography, random letters, "
            "wrong product, changed logo, low-end mockup, clutter, flat lighting, poor crop, pasted subject, distorted anatomy/product"
        ),
        size_intent=size_intent(width, height),
        reference_lock=reference_lock(mode_n, category_n, strength),
    )


def final_prompt_from_brief(brief: CreativeBrief, selected_layout: str | None = None) -> str:
    layout = f" Selected layout/art direction: {selected_layout}." if selected_layout else ""
    text_part = f" Text policy: {brief.text_policy}."
    if brief.headline or brief.subheadline or brief.cta:
        bits = []
        if brief.headline: bits.append(f"headline '{brief.headline}'")
        if brief.subheadline: bits.append(f"subheadline '{brief.subheadline}'")
        if brief.cta: bits.append(f"CTA '{brief.cta}'")
        text_part += " Use copy only as needed: " + ", ".join(bits) + "."
    return (
        f"{brief.commercial_goal}. Subject: {brief.subject_label}. {brief.reference_lock}. "
        f"{brief.scene_direction}. Style profile: {brief.style_profile}. Composition: {brief.composition}. "
        f"Size intent: {brief.size_intent}.{layout}{text_part} Quality: {brief.quality_directives}."
    )


def brief_metadata(brief: CreativeBrief) -> dict[str, Any]:
    return asdict(brief)
