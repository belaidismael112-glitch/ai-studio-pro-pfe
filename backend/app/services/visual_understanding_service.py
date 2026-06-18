from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.face_alignment_helper import analyze_face_reference
from app.services.ollama_service import env_bool, json_chat
from app.services.subject_lock_helper import analyze_universal_subject
from app.services.vision_prompt_director import build_prompt_pack

logger = logging.getLogger(__name__)

_ALLOWED_MODES = {"auto", "person_identity", "product_ad", "flyer_poster", "background_replace", "creative_image", "text_only"}
_BACKGROUND_HINTS = {
    "replace background", "change background", "new background", "background replace",
    "remove background", "put this in", "place this in", "scene background",
    "badel el fond", "بدل الخلفية", "change le fond", "changer le fond",
}
_FLYER_HINTS = {
    "flyer", "poster", "banner", "social post", "instagram", "facebook", "story",
    "headline", "price", "cta", "call to action", "promo", "promotion",
    "affiche", "visuel", "pub",
}
_COMMERCIAL_HINTS = {
    "product ad", "commercial", "advertising", "ad", "campaign", "packshot",
    "branding", "branded", "label", "logo", "catalog", "hero shot", "hero image", "hero visual",
    "annonce", "publicité", "publicite", "produit", "pub", "catalogue",
    "ecommerce", "e-commerce",
}


def _normalize_mode(value: str | None) -> str:
    mode = (value or "auto").strip().lower()
    return mode if mode in _ALLOWED_MODES else "auto"


def _contains_hint(prompt: str, hint: str) -> bool:
    lowered = (prompt or "").strip().lower()
    needle = (hint or "").strip().lower()
    if not lowered or not needle:
        return False
    if " " in needle or "-" in needle:
        return needle in lowered
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered) is not None


def _prompt_has_any(prompt: str, hints: set[str]) -> bool:
    return any(_contains_hint(prompt, hint) for hint in hints)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _map_vision_subject_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"person", "human", "face", "portrait", "person_face", "woman", "man", "child"}:
        return "person_face"
    if raw in {"document", "poster", "flyer", "paper", "receipt", "invoice", "id card", "passport"}:
        return "document_or_poster"
    if raw in {"product", "packshot", "package", "packaging", "bottle", "can", "cup", "shoe", "perfume", "phone", "watch"}:
        return "product"
    if raw in {"car", "vehicle", "automobile"}:
        return "car"
    if raw in {"animal", "pet", "dog", "cat"}:
        return "pet"
    if raw in {"insect", "worm", "larva", "mealworm"}:
        return "insect"
    if raw in {"object", "generic_object", "tool", "food", "plant", "scene"}:
        return "object_or_product"
    return "unknown"


def _living_subject_override(input_path: str, vision_payload: dict[str, Any] | None) -> str | None:
    """Protect artistic flyer routing from product-biased fallback classification.

    Flyer / Poster is a presentation mode, not a product detector.  A living
    reference must never become an exact-source packshot just because the user
    selected Flyer / Poster.
    """
    payload = vision_payload or {}
    text = " ".join(
        [
            Path(input_path).name,
            str(payload.get("subject_type") or ""),
            str(payload.get("primary_subject") or ""),
            str(payload.get("subject") or ""),
            str(payload.get("visual_summary") or ""),
            str(payload.get("reason") or ""),
        ]
    ).lower()
    if re.search(r"(?<![a-z0-9])(worm|mealworm|larva|tenebrio|insect|scorpion|beetle|spider|ant|bee|butterfly|moth)(?![a-z0-9])", text):
        return "insect"
    if re.search(r"(?<![a-z0-9])(animal|fish|dog|cat|bird|horse|rabbit|pet|reptile|snake|lizard)(?![a-z0-9])", text):
        return "pet"
    if _parse_bool(payload.get("is_living_subject")):
        return "pet"
    return None


def _merge_subject_type(
    input_path: str,
    base_type: str,
    vision_payload: dict[str, Any] | None,
    *,
    requested_mode: str | None = None,
) -> str:
    """Merge deterministic CV and optional vision subject labels.

    Person / Identity is a user-selected identity route.  It must never be
    downgraded to pet/product/object because an optional vision model returned a
    noisy semantic label.  The old behavior could log
    `mode=person_identity subject=pet`, which disabled the person prompt/guard
    path and produced weak face results.
    """
    mode = _normalize_mode(requested_mode)
    base = str(base_type or "unknown").strip().lower()
    payload = vision_payload or {}

    if mode == "person_identity":
        if base in {"person", "person_face", "person_full", "person_full_body"}:
            return "person_full_body" if base in {"person_full", "person_full_body"} else "person_face"
        mapped = _map_vision_subject_type(payload.get("subject_type"))
        if mapped in {"person_face", "person_full_body"}:
            return mapped
        if _parse_bool(payload.get("person_present")) or _parse_bool(payload.get("face_visible")):
            return "person_face"
        # Dedicated Person / Identity requests should still keep the person
        # safety envelope. If no confident face is found, the generation guard
        # can warn/block based on coverage, but the worker must not treat the
        # reference as a pet/product.
        return "person_face"

    living_override = _living_subject_override(input_path, vision_payload)
    if living_override:
        return living_override
    mapped = _map_vision_subject_type(payload.get("subject_type"))
    if mapped != "unknown":
        return mapped
    return base_type or "unknown"


def _is_living_subject_type(subject_type: str | None, vision_payload: dict[str, Any] | None = None) -> bool:
    stype = str(subject_type or "").strip().lower()
    if stype in {"insect", "pet", "animal", "person", "person_face", "person_full"}:
        return True
    if _parse_bool((vision_payload or {}).get("is_living_subject")):
        return True
    text = " ".join(
        str((vision_payload or {}).get(key) or "")
        for key in ("subject_type", "primary_subject", "subject", "visual_summary", "reason")
    ).lower()
    return bool(re.search(r"(?<![a-z0-9])(worm|mealworm|larva|insect|animal|pet|dog|cat|bird|fish|reptile)(?![a-z0-9])", text))


def _is_packshot_like(subject_type: str | None, vision_payload: dict[str, Any] | None = None) -> bool:
    stype = str(subject_type or "").strip().lower()
    if _is_living_subject_type(stype, vision_payload):
        return False
    if stype in {"product", "packshot", "document", "document_or_poster"}:
        return True
    return _parse_bool((vision_payload or {}).get("is_packshot_product"))


def _resolve_mode(requested_mode: str, subject_type: str, prompt: str, vision_payload: dict[str, Any] | None) -> str:
    mode = _normalize_mode(requested_mode)
    living_subject = _is_living_subject_type(subject_type, vision_payload)
    packshot_like = _is_packshot_like(subject_type, vision_payload)

    if mode != "auto":
        if mode == "product_ad" and not packshot_like:
            if _prompt_has_any(prompt, _BACKGROUND_HINTS):
                return "background_replace"
            # Prevent worms, pets, people and generic objects from being pasted
            # into deterministic product-ad templates. They remain on the real
            # img2img creative route unless a later vision pass proves packshot.
            return "creative_image"
        if mode == "flyer_poster" and living_subject:
            # Flyer is valid for living subjects, but not as exact-source
            # product/document compositing. The renderer will use img2img.
            return "flyer_poster"
        return mode

    if subject_type == "person_face":
        return "person_identity"
    # V5: user intent is mode-safe. Living subjects can be flyers, but they must
    # stay out of product/document source-lock compositing later.
    if _prompt_has_any(prompt, _FLYER_HINTS):
        return "flyer_poster"
    if _prompt_has_any(prompt, _BACKGROUND_HINTS):
        return "background_replace"
    if living_subject:
        return "creative_image"

    vision = vision_payload or {}
    explicit_recommendation = _normalize_mode(vision.get("recommended_mode"))
    if explicit_recommendation in {"person_identity", "product_ad", "flyer_poster", "background_replace", "creative_image"}:
        if explicit_recommendation == "product_ad":
            is_packshot = _parse_bool(vision.get("is_packshot_product"))
            if not living_subject and (is_packshot or packshot_like):
                return "product_ad"
            return "creative_image"
        if explicit_recommendation == "flyer_poster":
            return "flyer_poster"
        return explicit_recommendation

    if packshot_like:
        return "product_ad"
    if subject_type in {"car", "object_or_product", "object"}:
        if _prompt_has_any(prompt, _COMMERCIAL_HINTS):
            return "product_ad"
        return "creative_image"
    if subject_type in {"pet", "insect", "animal"} or living_subject:
        return "creative_image"
    return "creative_image"


async def analyze_reference_with_vision(input_path: str, prompt: str, mode: str) -> dict[str, Any]:
    """Production-safe image understanding for img2img."""
    normalized_mode = _normalize_mode(mode)
    real_analysis: dict[str, Any] = {}
    # Product Ad may bias the deterministic fallback toward manufactured packshots.
    # Flyer / Poster must stay classification-neutral: a flyer can feature a worm,
    # animal or creative object and must not silently become a product composite.
    commercial_product_mode = normalized_mode == "product_ad"

    if not commercial_product_mode:
        try:
            real_analysis = analyze_face_reference(input_path, hint=prompt).dict().get("real_face_analysis") or {}
        except Exception:
            real_analysis = {}

    try:
        if commercial_product_mode:
            hint = f"{normalized_mode} manufactured product packshot merchandise {prompt}"
        elif normalized_mode == "flyer_poster":
            hint = f"{normalized_mode} creative flyer visual poster subject classification-neutral {prompt}"
        else:
            hint = f"{normalized_mode} {prompt}"
        base_analysis = analyze_universal_subject(input_path, hint, real_analysis)
    except Exception:
        base_analysis = {
            "subject_type": "unknown",
            "primary_subject_detected": True,
            "primary_subject_bbox": None,
            "primary_subject_coverage_percent": 50,
            "reference_quality_score": 70,
            "subject_preservation_score": 70,
            "hard_block_generation": False,
            "can_generate": True,
            "risks": ["Reference analyzer fallback was used."],
            "recommendations": ["Check the generated output before client delivery."],
        }

    use_vision = env_bool("OLLAMA_VISION_ENABLED", True)
    vision_payload: dict[str, Any] | None = None
    vision_error: str | None = None

    if use_vision and Path(input_path).exists():
        system = (
            "You are the image understanding and routing engine for an image-to-image commercial platform. "
            "Look at the uploaded image itself, not only the text prompt. "
            "Return JSON only with keys: subject_type, primary_subject, is_packshot_product, "
            "is_living_subject, scene_type, needs_subject_preservation, recommended_mode, "
            "background_policy, composite_policy, confidence, reason, visual_summary, scene_direction, "
            "composition_notes, lighting_notes, img2img_prompt, background_prompt, negative_prompt. "
            "subject_type must be one of: person, product, packshot, object, animal, insect, document, poster, car, scene. "
            "recommended_mode must be one of: person_identity, product_ad, flyer_poster, background_replace, creative_image. "
            "Classify the uploaded source independently from the requested mode. Flyer / Poster is a presentation mode and MUST NOT turn a living subject into a product. "
            "A worm, mealworm, larva, insect, scorpion, fish, animal or pet remains a living subject even when the requested mode is flyer_poster. "
            "Set is_packshot_product=false for every living subject. Only manufactured merchandise, branded packaging or a real document may be treated as an exact-source flyer asset. "
            "If the image is an insect, animal, simple object or non-packshot cutout, do NOT recommend product_ad unless the prompt clearly asks for an ad/commercial packshot. "
            "If the prompt asks to replace or change the background, prefer background_replace. "
            "If the uploaded image is a real branded bottle/can/cup/product packshot, product_ad is acceptable. "
            "The prompt fields must describe a premium professional result. Avoid generic podiums, generic geometric stages, plain backgrounds and template-like visuals. "
            "For product_ad or flyer_poster, background_prompt must describe an EMPTY art-directed environment for later compositing of the exact source subject. "
            "For creative_image or background_replace, img2img_prompt must describe a complete integrated scene and preserve the complete subject."
        )
        user = (
            f"Requested mode: {normalized_mode}\n"
            f"User prompt: {prompt}\n"
            "Classify the image and choose the safest generation mode for a production-ready result."
        )
        try:
            payload, result = await json_chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                mode="advanced",
                feature="image_understanding",
                timeout_seconds=float(getattr(settings, "OLLAMA_VISION_TIMEOUT_SECONDS", 120) or 120),
                image_paths=[input_path],
            )
            if payload:
                vision_payload = payload
            elif result.error:
                vision_error = result.error
        except Exception as exc:
            vision_error = str(exc)[:500]

    merged_type = _merge_subject_type(input_path, str(base_analysis.get("subject_type") or "unknown"), vision_payload, requested_mode=normalized_mode)
    resolved_mode = _resolve_mode(normalized_mode, merged_type, prompt, vision_payload)
    logger.info(
        "VISION_ROUTE requested=%s base_subject=%s vision_subject=%s merged_subject=%s living=%s packshot=%s resolved=%s vision_used=%s",
        normalized_mode,
        base_analysis.get("subject_type"),
        (vision_payload or {}).get("subject_type"),
        merged_type,
        (vision_payload or {}).get("is_living_subject"),
        (vision_payload or {}).get("is_packshot_product"),
        resolved_mode,
        bool(vision_payload),
    )
    production_prompt_pack = build_prompt_pack(
        vision_payload=vision_payload,
        user_prompt=prompt,
        resolved_mode=resolved_mode,
        subject_type=merged_type,
    )

    analysis = dict(base_analysis)
    analysis["subject_type"] = merged_type
    analysis["resolved_generation_mode"] = resolved_mode
    analysis["production_prompt_pack"] = production_prompt_pack
    analysis["vision_understanding"] = {
        "enabled": use_vision,
        "used": bool(vision_payload),
        "provider": "ollama_vision" if vision_payload else None,
        "raw": vision_payload,
        "error": vision_error,
    }
    return analysis
