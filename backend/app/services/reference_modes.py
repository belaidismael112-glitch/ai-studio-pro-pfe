"""Reference-generation mode routing helpers.

The queue stores prompts, not mode metadata. Internal markers keep the resolved
mode and measured subject type attached to queued work without a database
migration. Markers are stripped before a provider receives the prompt.
"""
from __future__ import annotations

import base64
import json
import re

VALID_REFERENCE_MODES = {
    "auto",
    "person_identity",
    "product_ad",
    "flyer_poster",
    "background_replace",
    "creative_image",
    "text_only",
}

_REFERENCE_MODE_ALIASES = {
    "text_to_image": "text_only",
    "text_to_video": "text_only",
}

_MODE_MARKER_RE = re.compile(r"\s*\[AI_STUDIO_REFERENCE_MODE:([a-z_]+)\]\s*$", re.IGNORECASE)
_SUBJECT_TYPE_MARKER_RE = re.compile(r"\s*\[AI_STUDIO_SUBJECT_TYPE:([a-z_]+)\]\s*", re.IGNORECASE)
_FLYER_OVERLAY_MARKER_RE = re.compile(r"\s*\[AI_STUDIO_FLYER_OVERLAY:(true|false)\]\s*", re.IGNORECASE)
_IDENTITY_BOARD_MARKER_RE = re.compile(r"\s*\[AI_STUDIO_IDENTITY_BOARD:(true|false)\]\s*", re.IGNORECASE)
_VISION_PROMPT_PACK_MARKER_RE = re.compile(r"\s*\[AI_STUDIO_VISION_PROMPT_PACK:([A-Za-z0-9_-]+)\]\s*", re.IGNORECASE)

_FLYER_WORDS = {
    "flyer", "poster", "banner", "social post", "instagram", "facebook", "story",
    "headline", "price", "cta", "call to action", "promo", "promotion",
}
_BACKGROUND_WORDS = {
    "replace background", "change background", "new background", "background replace",
    "put this in", "place this in", "scene background", "remove background",
}
_CREATIVE_WORDS = {
    "creative", "cinematic", "stylized", "transform", "artistic", "editorial", "concept", "hero visual",
}
_COMMERCIAL_REQUEST_WORDS = {
    "ad", "advertising", "commercial", "campaign", "packshot", "catalog", "catalogue",
    "branding", "logo", "label", "hero shot", "hero image", "ecommerce", "e-commerce",
    "pub", "publicité", "publicite", "annonce", "produit",
}
_PRODUCT_TYPES = {"product", "object_or_product", "object", "car", "pet", "document", "document_or_poster"}
_EXACT_SOURCE_TYPES = {"product", "packshot", "document", "document_or_poster"}
_LIVING_TYPES = {"pet", "animal", "insect", "person", "person_face", "person_full", "person_full_body"}
_PERSON_TYPES = {"person", "person_face", "person_full", "person_full_body"}

_COMMERCIAL_BRIEF_DROP_WORDS = {
    "product", "products", "uploaded", "source", "packshot", "bottle", "can", "package", "packaging",
    "label", "logo", "brand", "watch", "shoe", "bag", "person", "face", "headline", "cta", "typography",
    "text", "letters", "poster", "flyer", "social", "media", "advertisement", "advertising",
}


def _contains_phrase(prompt: str, hint: str) -> bool:
    lowered = (prompt or "").strip().lower()
    needle = (hint or "").strip().lower()
    if not lowered or not needle:
        return False
    if " " in needle or "-" in needle:
        return needle in lowered
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered) is not None


def _prompt_has_any(prompt: str, hints: set[str]) -> bool:
    return any(_contains_phrase(prompt, hint) for hint in hints)


def normalize_reference_mode(mode: str | None) -> str:
    value = (mode or "auto").strip().lower()
    value = _REFERENCE_MODE_ALIASES.get(value, value)
    return value if value in VALID_REFERENCE_MODES else "auto"


def normalize_reference_subject_type(subject_type: str | None) -> str:
    value = re.sub(r"[^a-z_]+", "_", (subject_type or "unknown").strip().lower()).strip("_")
    return value or "unknown"


def is_commercial_reference_mode(mode: str | None) -> bool:
    return normalize_reference_mode(mode) in {"product_ad", "flyer_poster"}


def is_object_reference_type(subject_type: str | None) -> bool:
    return normalize_reference_subject_type(subject_type) in _PRODUCT_TYPES


def is_person_reference_type(subject_type: str | None) -> bool:
    return normalize_reference_subject_type(subject_type) in _PERSON_TYPES


def should_use_source_lock_composite(mode: str | None, subject_type: str | None) -> bool:
    """Use exact-source compositing only where it is genuinely required.

    - Product Ad: preserve the exact uploaded packshot over an AI-generated scene.
    - Flyer / Poster: preserve the exact source only for an explicitly classified
      product or document. Insects, animals and generic objects always stay on
      the full-frame ComfyUI img2img route.
    - Creative / Background Replace: always use ComfyUI img2img. Never paste a
      cutout onto a backend template.
    """
    resolved = normalize_reference_mode(mode)
    stype = normalize_reference_subject_type(subject_type)
    if resolved == "product_ad":
        # Branded products and packaging must never be repainted by img2img.
        # Even if the analyser is unsure, Product Ad is a source-lock delivery.
        return stype not in _LIVING_TYPES and stype not in _PERSON_TYPES
    if resolved == "flyer_poster":
        # V7 hybrid rule: living subjects can use true img2img flyer key-visuals;
        # branded products/documents/unknown packshots use exact-source layout so
        # logos, labels and bottle geometry are not hallucinated or corrupted.
        return stype not in _LIVING_TYPES and stype not in _PERSON_TYPES
    if resolved == "background_replace":
        # For product/object background replacement, preserve the exact source
        # subject and generate only the environment. Living subjects stay on
        # true img2img unless a dedicated mask workflow is installed.
        return stype not in _LIVING_TYPES and stype not in _PERSON_TYPES
    return False


def _sanitize_backdrop_brief(user_prompt: str) -> str:
    raw = re.sub(r"\[AI_STUDIO_[^\]]+\]", " ", user_prompt or "", flags=re.IGNORECASE)
    raw = re.sub(r"[\r\n]+", " ", raw)
    raw = re.sub(
        r"\b[A-Z][A-Za-z0-9'_-]{2,}\s+(?=(?:bottle|can|product|package|packaging)\b)",
        " ",
        raw,
    )
    tokens = re.findall(r"[A-Za-z0-9'-]+", raw)
    kept = [token for token in tokens if token.lower() not in _COMMERCIAL_BRIEF_DROP_WORDS]
    brief = " ".join(kept).strip()[:360]
    return brief or "premium commercial environment, coherent depth, realistic materials, controlled lighting"


def resolve_reference_mode(requested_mode: str | None, subject_type: str | None, prompt: str = "") -> str:
    """Resolve Auto Smart into one dedicated workflow.

    Production rule: living subjects are never auto-routed into product/flyer
    packshot compositing.  A worm, insect, pet or animal should become a true
    Creative Reference image unless the user clearly asks only to replace the
    background.  This prevents the rope/worm source-copy issue seen in local
    ComfyUI tests.
    """
    mode = normalize_reference_mode(requested_mode)
    if mode != "auto":
        return mode

    stype = normalize_reference_subject_type(subject_type)

    if stype in _PERSON_TYPES:
        return "person_identity"
    # V5: intent comes before subject fallback. A worm + flyer prompt is a worm flyer,
    # not Product Ad and not a generic Creative route.
    if _prompt_has_any(prompt, _FLYER_WORDS):
        return "flyer_poster"
    if _prompt_has_any(prompt, _BACKGROUND_WORDS):
        return "background_replace"
    if stype in _LIVING_TYPES:
        return "creative_image"
    if stype in _EXACT_SOURCE_TYPES:
        return "product_ad"
    if stype in {"object_or_product", "object", "car"}:
        if _prompt_has_any(prompt, _FLYER_WORDS):
            return "flyer_poster"
        if _prompt_has_any(prompt, _COMMERCIAL_REQUEST_WORDS):
            return "product_ad"
        return "creative_image"
    if _prompt_has_any(prompt, _FLYER_WORDS):
        return "flyer_poster"
    if _prompt_has_any(prompt, _CREATIVE_WORDS):
        return "creative_image"
    return "creative_image"


def attach_reference_mode_marker(prompt: str, mode: str | None) -> str:
    clean_prompt = strip_reference_mode_marker(prompt)[1].strip()
    resolved = normalize_reference_mode(mode)
    if resolved == "auto":
        resolved = "creative_image"
    return f"{clean_prompt}\n[AI_STUDIO_REFERENCE_MODE:{resolved}]".strip()


def strip_reference_mode_marker(prompt: str | None) -> tuple[str | None, str]:
    text = (prompt or "").strip()
    match = _MODE_MARKER_RE.search(text)
    if not match:
        return None, text
    mode = normalize_reference_mode(match.group(1))
    return mode, _MODE_MARKER_RE.sub("", text).strip()


def attach_reference_subject_type_marker(prompt: str, subject_type: str | None) -> str:
    clean_prompt = strip_reference_subject_type_marker(prompt)[1].strip()
    resolved = normalize_reference_subject_type(subject_type)
    return f"{clean_prompt}\n[AI_STUDIO_SUBJECT_TYPE:{resolved}]".strip()


def strip_reference_subject_type_marker(prompt: str | None) -> tuple[str | None, str]:
    text = (prompt or "").strip()
    match = _SUBJECT_TYPE_MARKER_RE.search(text)
    if not match:
        return None, text
    stype = normalize_reference_subject_type(match.group(1))
    return stype, _SUBJECT_TYPE_MARKER_RE.sub("", text).strip()


def attach_vision_prompt_pack_marker(prompt: str, pack: dict | None) -> str:
    clean_prompt = strip_vision_prompt_pack_marker(prompt)[1].strip()
    if not pack:
        return clean_prompt
    raw = json.dumps(pack, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{clean_prompt}\n[AI_STUDIO_VISION_PROMPT_PACK:{encoded}]".strip()


def strip_vision_prompt_pack_marker(prompt: str | None) -> tuple[dict | None, str]:
    text = (prompt or "").strip()
    match = _VISION_PROMPT_PACK_MARKER_RE.search(text)
    if not match:
        return None, text
    encoded = match.group(1)
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
        if not isinstance(payload, dict):
            payload = None
    except Exception:
        payload = None
    return payload, _VISION_PROMPT_PACK_MARKER_RE.sub("", text).strip()


def attach_flyer_overlay_marker(prompt: str, enabled: bool) -> str:
    clean_prompt = strip_flyer_overlay_marker(prompt)[1].strip()
    if not enabled:
        return clean_prompt
    return f"{clean_prompt}\n[AI_STUDIO_FLYER_OVERLAY:true]".strip()


def strip_flyer_overlay_marker(prompt: str | None) -> tuple[bool, str]:
    text = (prompt or "").strip()
    match = _FLYER_OVERLAY_MARKER_RE.search(text)
    if not match:
        return False, text
    enabled = match.group(1).lower() == "true"
    return enabled, _FLYER_OVERLAY_MARKER_RE.sub("", text).strip()


def attach_identity_board_marker(prompt: str, enabled: bool) -> str:
    clean_prompt = strip_identity_board_marker(prompt)[1].strip()
    value = "true" if enabled else "false"
    return f"{clean_prompt}\n[AI_STUDIO_IDENTITY_BOARD:{value}]".strip()


def strip_identity_board_marker(prompt: str | None) -> tuple[bool, str]:
    text = (prompt or "").strip()
    match = _IDENTITY_BOARD_MARKER_RE.search(text)
    if not match:
        return False, text
    enabled = match.group(1).lower() == "true"
    return enabled, _IDENTITY_BOARD_MARKER_RE.sub("", text).strip()


def should_apply_optional_flyer_overlay(mode: str | None, requested: bool) -> bool:
    return bool(requested) and normalize_reference_mode(mode) == "flyer_poster"


def effective_reference_strength(strength: float, mode: str | None, subject_type: str | None = None) -> float:
    value = max(0.1, min(float(strength), 0.9))
    resolved = normalize_reference_mode(mode)
    stype = normalize_reference_subject_type(subject_type)

    if resolved == "person_identity" or stype in _PERSON_TYPES:
        # Conservative envelope: generic FLUX img2img is not a FaceID adapter.
        # Keep identity stable and avoid gaze/eye drift while still allowing
        # gentle professional finishing.
        return max(0.12, min(value, 0.24))
    if resolved == "background_replace":
        return max(0.48, min(value, 0.70))
    if resolved == "product_ad":
        return max(0.54, min(value, 0.72))
    if resolved == "flyer_poster":
        return max(0.62, min(value, 0.80))
    if resolved == "creative_image":
        if stype in _LIVING_TYPES:
            return max(0.72, min(value, 0.88))
        return max(0.68, min(value, 0.86))
    return value


def source_lock_backdrop_prompt(mode: str | None, user_prompt: str = "") -> str:
    resolved = normalize_reference_mode(mode)
    brief = _sanitize_backdrop_brief(user_prompt)
    common = (
        "Do not render any product, bottle, can, jar, glass, beverage container, package, person, logo, brand name, letters, typography, or watermark. "
        "Leave a clean hero placement zone for the extracted source subject. "
    )
    if resolved == "flyer_poster":
        return (
            "Create a premium social-media flyer backdrop with polished commercial lighting, cinematic depth, tasteful visual energy, "
            "with intentional composition. Keep the right-center area ready for the hero subject and clean negative space on the left for headline and CTA. "
            f"{common}Creative direction: {brief}"
        ).strip()
    if resolved == "background_replace":
        return (
            "Create a realistic replacement environment with coherent perspective, natural light direction, contact-shadow space, and enough empty room "
            "for the extracted source subject. The environment must be visibly different from the original/plain source background and must contain no duplicate hero object. "
            f"{common}Environment direction: {brief}"
        ).strip()
    if resolved == "creative_image":
        return (
            "Create a premium editorial or cinematic backdrop with a bold but coherent art direction, layered depth, and a clear placement zone for the source subject. "
            f"{common}Creative direction: {brief}"
        ).strip()
    return (
        "Create a premium commercial advertising backdrop for a hero packshot with polished studio lighting, cinematic depth, tasteful splash or energy elements, "
        "subtle reflections, and a clean hero placement zone. Leave the center area ready for the hero subject. "
        f"{common}Creative direction: {brief}"
    ).strip()


def commercial_backdrop_prompt(mode: str | None, user_prompt: str = "") -> str:
    return source_lock_backdrop_prompt(mode, user_prompt)


def reference_mode_prompt_suffix(mode: str | None) -> str:
    resolved = normalize_reference_mode(mode)
    if resolved == "product_ad":
        return (
            "Create a premium product advertisement. Preserve the exact uploaded packaging, label, silhouette, colors and proportions. "
            "Use a polished commercial scene with coherent lighting, contact shadow and depth. Use one hero product only. Do not repaint the product, duplicate it or return a plain source copy."
        )
    if resolved == "flyer_poster":
        return (
            "Create a premium flyer/poster composition with one preserved uploaded hero subject, a real poster layout, readable negative space and clear campaign structure. "
            "Do not repaint the packaging, duplicate the hero subject or generate fake letters."
        )
    if resolved == "background_replace":
        return (
            "Replace the environment clearly while preserving the exact main subject. Keep coherent edges, perspective, scale and contact shadow. "
            "The output must look like a clearly new background/environment, not an isolated cutout, minor edit, cleaned source copy or plain background. "
            "Do not redesign the source subject."
        )
    if resolved == "creative_image":
        return (
            "Create a visibly transformed premium editorial or cinematic composition while keeping the main source subject readable and coherent. "
            "Place the subject inside a believable fully rendered scene with depth, contact shadow, lighting and surrounding context. "
            "Never return an isolated cutout, plain white background, or a minor edit/flat template."
        )
    if resolved == "person_identity":
        return (
            "Preserve the exact same person while generating a production-ready identity-safe portrait. "
            "Keep face geometry, gaze direction, eye alignment, mouth shape, jaw, nose, skin texture, hair and visible clothing consistent with the reference. "
            "Do not create a lookalike, side-gaze, cross-eyed face, beautified plastic skin or a different facial expression unless explicitly requested."
        )
    return ""
