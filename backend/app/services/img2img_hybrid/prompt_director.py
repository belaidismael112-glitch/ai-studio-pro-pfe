from __future__ import annotations

from .contracts import CreativeBrief, ImageAnalysis
from .presets import PRESETS


def build_creative_brief(mode: str, analysis: ImageAnalysis, user_prompt: str = "") -> CreativeBrief:
    category = analysis.category or "general_product"
    preset = PRESETS.get(category, PRESETS.get("fashion") if category == "general_product" else PRESETS["general"])

    if mode == "auto":
        mode = analysis.suggested_mode

    if mode == "flyer_poster":
        return CreativeBrief(
            mode="flyer_poster",
            title=_title_for(analysis, preset),
            subtitle=_subtitle_for(analysis),
            cta=_cta_for(analysis, preset),
            badge=_badge_for(analysis),
            bullets=_bullets_for(analysis),
            scene_description=f"Professional production-ready flyer/poster for {analysis.subject_label}",
            style_direction=_style_for(analysis),
            layout_type=_layout_for(analysis, preset),
            palette=_palette_for(analysis, preset),
            negative_prompt="generic AI studio text, unreadable text, duplicate product, distorted subject, messy layout",
        )

    if mode == "product_ad":
        return CreativeBrief(
            mode="product_ad",
            title=_title_for(analysis, preset),
            subtitle=_subtitle_for(analysis),
            cta=_cta_for(analysis, preset),
            badge=_badge_for(analysis),
            bullets=_bullets_for(analysis),
            scene_description=f"Premium commercial ad scene for {analysis.subject_label}",
            style_direction=f"single hero product, professional lighting, clean background, {analysis.mood}",
            layout_type="single_product_ad",
            palette=_palette_for(analysis, preset),
            negative_prompt="duplicate product, repainted label, fake text, warped packaging",
        )

    if mode == "background_replace":
        return CreativeBrief(
            mode="background_replace",
            title="",
            subtitle="",
            cta="",
            scene_description=f"Replace only the background with a clean {analysis.mood} scene",
            style_direction="preserve subject exactly, new environment only",
            layout_type="subject_preserved_background",
            palette=_palette_for(analysis, preset),
            negative_prompt="changed subject, duplicate object, distorted product, repainted packaging",
        )

    if mode == "person_identity":
        return CreativeBrief(
            mode="person_identity",
            title="",
            subtitle="",
            cta="",
            scene_description="Identity-preserving portrait transformation",
            style_direction="same face and identity, new styling or background",
            layout_type="identity_preserved",
            palette=_palette_for(analysis, preset),
            negative_prompt="different face, changed identity, distorted anatomy",
        )

    return CreativeBrief(
        mode="creative_image",
        title=_title_for(analysis, preset),
        subtitle=_subtitle_for(analysis),
        cta=_cta_for(analysis, preset),
        badge=_badge_for(analysis),
        bullets=_bullets_for(analysis),
        scene_description=f"Creative transformation inspired by {analysis.subject_label}",
        style_direction=f"{analysis.mood} artistic campaign",
        layout_type="creative_reference",
        palette=_palette_for(analysis, preset),
        negative_prompt="low quality, messy composition, unreadable text",
    )


def _palette_for(analysis: ImageAnalysis, preset: dict) -> list[str]:
    if analysis.category in {"fashion", "general_product"}:
        return ["#0f1720", "#f4ead7", "#b08855", "#ffffff", "#111111"]
    return preset.get("palette", ["#111827", "#e5e7eb", "#ffffff"])


def _title_for(analysis: ImageAnalysis, preset: dict) -> str:
    if analysis.category in {"fashion", "general_product"}:
        return "PREMIUM PRODUCT EDITORIAL"
    if analysis.category == "beverage":
        return "REFRESH YOUR MOMENT"
    if analysis.category == "sports":
        return "MARATHON"
    if analysis.category == "nature":
        return "DISCOVER HIDDEN NATURE"
    if analysis.category == "food":
        return "FRESH FLAVOR AWAITS"
    return preset.get("headline_examples", ["FEATURE HIGHLIGHT"])[0]


def _subtitle_for(analysis: ImageAnalysis) -> str:
    if analysis.category in {"fashion", "general_product"}:
        return "Premium styling with refined details and everyday luxury."
    if analysis.category == "beverage":
        return "A bold visual made to feel fresh, crisp and memorable."
    if analysis.category == "nature":
        return "A close-up story from the hidden world around us."
    if analysis.category == "sports":
        return "Running for a good cause with energy, movement and purpose."
    if analysis.category == "food":
        return "A clean campaign visual designed to make every detail tempting."
    return "A polished campaign visual built from your uploaded image."


def _badge_for(analysis: ImageAnalysis) -> str:
    if analysis.category in {"fashion", "general_product"}:
        return "NEW ARRIVAL"
    if analysis.category == "beverage":
        return "LIMITED CAMPAIGN"
    if analysis.category == "sports":
        return "ANNUAL EVENT"
    if analysis.category == "nature":
        return "NATURE SERIES"
    if analysis.category == "food":
        return "TODAY SPECIAL"
    return "NEW CAMPAIGN"


def _cta_for(analysis: ImageAnalysis, preset: dict) -> str:
    if analysis.category in {"fashion", "general_product"}:
        return "SHOP THE LOOK"
    if analysis.category == "sports":
        return "REGISTER NOW"
    if analysis.category == "food":
        return "ORDER NOW"
    return preset.get("cta", "DISCOVER MORE")


def _bullets_for(analysis: ImageAnalysis) -> list[str]:
    if analysis.category in {"fashion", "general_product"}:
        return ["Premium finish", "Authentic detail", "Campaign ready"]
    if analysis.category == "beverage":
        return ["Bold taste", "Fresh energy", "Serve chilled"]
    if analysis.category == "sports":
        return ["Date schedule", "Event details", "Registration info"]
    if analysis.category == "nature":
        return ["Macro detail", "Natural habitat", "Educational visual"]
    if analysis.category == "food":
        return ["Fresh ingredients", "Special offer", "Fast order"]
    return ["Clean design", "Source preserved", "Ready to share"]


def _layout_for(analysis: ImageAnalysis, preset: dict) -> str:
    if analysis.category == "sports":
        return "event_poster"
    if analysis.category == "nature":
        return "macro_educational"
    if analysis.category in {"fashion", "beverage", "food", "general_product"}:
        return "premium_product_flyer"
    return preset.get("layout", "balanced_modern")


def _style_for(analysis: ImageAnalysis) -> str:
    if analysis.category in {"fashion", "general_product"}:
        return "luxury fashion campaign, premium editorial spacing, black gold beige palette"
    if analysis.category == "beverage":
        return "fresh beverage campaign, crisp highlights, bold commercial design"
    if analysis.category == "sports":
        return "high-energy sports event poster, orange black white shapes, bold typography"
    if analysis.category == "nature":
        return "macro educational nature poster with organic textures and clear readable copy"
    if analysis.category == "food":
        return "appetizing food campaign with warm colors and clear CTA"
    return f"{analysis.mood} modern promotional campaign"
