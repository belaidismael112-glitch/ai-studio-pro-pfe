"""Vision-to-prompt orchestration for reference image generation.

The visual model must not directly generate the final asset. It produces a
compact production brief that is consumed by the correct ComfyUI path:
- commercial backdrop + exact-source compositing for Product Ad / Flyer;
- full-frame img2img for Creative Reference / Background Replace;
- identity-safe handling for Person / Identity.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Any


@dataclass
class VisionPromptPack:
    mode: str
    subject_type: str
    primary_subject: str
    visual_summary: str
    comfy_prompt: str
    background_prompt: str
    negative_prompt: str
    composition_notes: str
    lighting_notes: str
    text_overlay_title: str = ""
    text_overlay_subtitle: str = ""
    text_overlay_cta: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _clean(value: Any, *, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _quoted_text(user_prompt: str) -> tuple[str, str, str]:
    items = [item.strip() for item in re.findall(r'["“”]([^"“”]{2,80})["“”]', user_prompt or "") if item.strip()]
    title = items[0] if items else ""
    subtitle = items[1] if len(items) > 1 else ""
    cta = items[2] if len(items) > 2 else ""
    return title[:64], subtitle[:96], cta[:48]


def _flyer_visual_direction(user_prompt: str) -> str:
    """Remove display copy from a flyer brief before sending it to ComfyUI.

    Text is rendered deterministically after generation.  The image model sees
    only art direction, subject styling and environment notes so it does not
    hallucinate letters, dates or duplicate headline blocks.
    """
    raw = user_prompt or ""
    # Strip quoted display copy such as title, date and CTA.
    raw = re.sub(r'["“”][^"“”]{1,120}["“”]', ' ', raw)
    kept: list[str] = []
    skipping_typography = False
    for original_line in raw.splitlines():
        line = re.sub(r'\s+', ' ', original_line).strip(' -	')
        lowered = line.lower()
        if not line:
            continue
        if lowered.startswith('typography layout'):
            skipping_typography = True
            continue
        if skipping_typography:
            # Resume when we reach visual/design directions or output format.
            if lowered.startswith(('use modern ', 'background:', 'format:', 'style:', 'design ')):
                skipping_typography = False
            else:
                continue
        if lowered.startswith((
            'title:', 'subtitle:', 'headline:', 'subheadline:', 'event date:',
            'date:', 'time:', 'location:', 'bottom cta:', 'cta:', 'price:',
        )):
            continue
        # Remove leftover text-layout instructions while keeping visual style.
        if any(token in lowered for token in (
            'make the title highly readable', 'empty space around the text',
            'modern editorial typography', 'strong hierarchy', 'balanced spacing',
            'clean alignment', 'print-ready', 'readable typography', 'misspelled words',
        )):
            continue
        kept.append(line)
    result = re.sub(r'\s+', ' ', ' '.join(kept)).strip()
    return result[:1100]


def _commercial_backdrop_direction(user_prompt: str) -> str:
    """Keep only environment, mood and lighting notes for empty backdrops."""
    raw = user_prompt or ""
    raw = re.sub(r'["“”][^"“”]{1,120}["“”]', ' ', raw)
    kept: list[str] = []
    for original_line in raw.splitlines():
        line = re.sub(r"\s+", " ", original_line).strip(" -\t")
        lowered = line.lower()
        if not line:
            continue
        if lowered.startswith((
            "background:", "environment:", "scene:", "mood:", "lighting:",
            "color palette:", "colours:", "colors:", "art direction:", "style:",
        )):
            kept.append(line)
    result = re.sub(r"\s+", " ", " ".join(kept)).strip()
    return result[:700]


def _is_exact_source_flyer(subject_type: str) -> bool:
    return (subject_type or '').strip().lower() in {'product', 'document', 'document_or_poster'}


def _default_scene(subject_type: str) -> str:
    stype = (subject_type or "unknown").strip().lower()
    if stype in {"insect", "pet", "animal"}:
        return "a believable macro natural environment with realistic scale cues, detailed surface texture, depth and contact shadow"
    if stype in {"product", "object_or_product", "object", "car"}:
        return "a polished commercial environment with coherent depth, realistic reflections and a clean hero composition"
    if stype in {"document", "document_or_poster"}:
        return "a clean editorial layout with readable hierarchy and controlled negative space"
    return "a cinematic editorial environment with coherent lighting, depth and realistic context"


def _generic_negative() -> str:
    return (
        "duplicate subject, duplicate product, fake packaging, fake logo, changed label, unreadable brand, warped geometry, "
        "isolated cutout on plain background, white background, grey background, pasted subject, template-like stage, "
        "cheap podium, hard geometric spotlight, halo, border artifact, blurry, low quality, watermark, fake text"
    )


def _default_flyer_copy(stype: str) -> tuple[str, str, str]:
    if (stype or "").lower() in {"product", "packshot", "document", "document_or_poster"}:
        return "PRODUCT SPOTLIGHT", "PREMIUM CAMPAIGN VISUAL", "DISCOVER MORE"
    return "FEATURE HIGHLIGHT", "CREATIVE PROMOTIONAL VISUAL", "LEARN MORE"


def _user_intent_sentence(user_prompt: str, *, limit: int = 420) -> str:
    text = _clean(user_prompt, limit=limit)
    if not text:
        return "Use the uploaded image as the visual source and create a professional production-ready result."
    return text


def build_prompt_pack(
    *,
    vision_payload: dict[str, Any] | None,
    user_prompt: str,
    resolved_mode: str,
    subject_type: str,
) -> dict[str, str]:
    """Return a concise V6 mode-specific prompt pack.

    V6 policy: the AI understands the uploaded image first, then sends a useful,
    compact prompt to ComfyUI.  It does not bury the user request under long
    template text.  User text remains the primary creative direction.
    """
    payload = vision_payload or {}
    mode = (resolved_mode or "creative_image").strip().lower()
    stype = (subject_type or "unknown").strip().lower()
    primary = _clean(payload.get("primary_subject") or payload.get("subject") or stype, limit=120)
    summary = _clean(payload.get("visual_summary") or payload.get("reason") or primary, limit=260)
    composition = _clean(payload.get("composition_notes"), limit=220)
    lighting = _clean(payload.get("lighting_notes"), limit=180)
    scene = _clean(payload.get("scene_direction") or payload.get("background_policy"), limit=260) or _default_scene(stype)
    user = _user_intent_sentence(user_prompt)
    negative = _clean(payload.get("negative_prompt"), limit=500)
    negative = f"{negative}, {_generic_negative()}" if negative else _generic_negative()

    title, subtitle, cta = _quoted_text(user_prompt)
    # V7: do not invent default overlay text. Use only explicit user copy;
    # otherwise deliver a clean no-text campaign visual.

    if mode == "product_ad":
        # Product Ad can still use exact-source compositing later, so the
        # backdrop prompt is explicitly empty of products.  The final prompt is
        # concise and keeps the user's instruction central.
        background_prompt = (
            "Create a realistic premium advertising background only: clean set, lighting, depth, shadows and reflections. "
            "Do not draw any product, bottle, can, package, logo, text or extra hero object. Leave one empty hero zone. "
            f"User direction: {user}. Scene: {scene}."
        )
        comfy_prompt = (
            f"One hero {primary}. Preserve the uploaded product identity and label. "
            f"Create a realistic premium product advertisement. User direction: {user}. "
            f"Image understanding: {summary}. {composition} {lighting}"
        )
    elif mode == "flyer_poster":
        # V6: Flyer is a finished poster img2img, not source-lock empty backdrop.
        background_prompt = ""
        comfy_prompt = (
            f"Create a finished realistic marketing flyer/poster using the uploaded image as the source. "
            f"The main subject is {primary}; keep it recognizable and use exactly one hero subject. "
            f"Build a real poster layout with clean negative space for headline, subheadline and CTA. "
            f"Do not invent a second product/object and do not render fake unreadable text. "
            f"User direction: {user}. Image understanding: {summary}. Scene/style: {scene}."
        )
    elif mode == "background_replace":
        background_prompt = ""
        comfy_prompt = (
            f"Replace only the background around the uploaded {primary}. Preserve the subject exactly: silhouette, label/logo, colors, proportions and texture. "
            f"Create a clearly different realistic environment with matching light, grounding and contact shadow. "
            f"Do not add another hero object and do not keep the original plain background. User direction: {user}. Scene: {scene}."
        )
    elif mode == "person_identity":
        background_prompt = ""
        comfy_prompt = (
            f"Preserve the same uploaded person and facial identity exactly. Apply only the requested scene/styling change. "
            f"User direction: {user}. Keep natural age, skin texture, facial geometry and realistic light."
        )
    else:
        background_prompt = ""
        comfy_prompt = (
            f"Create a professional creative image from the uploaded source. Main subject: {primary}. "
            f"Keep the subject recognizable but make a genuinely new integrated scene with depth, grounding and coherent lighting. "
            f"User direction: {user}. Image understanding: {summary}. Scene/style: {scene}."
        )

    pack = VisionPromptPack(
        mode=mode,
        subject_type=stype,
        primary_subject=primary,
        visual_summary=summary,
        comfy_prompt=_clean(comfy_prompt, limit=1200),
        background_prompt=_clean(background_prompt, limit=900),
        negative_prompt=_clean(negative, limit=1200),
        composition_notes=composition,
        lighting_notes=lighting,
        text_overlay_title=title,
        text_overlay_subtitle=subtitle,
        text_overlay_cta=cta,
    )
    return pack.as_dict()
