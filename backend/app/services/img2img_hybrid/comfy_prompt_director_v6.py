from __future__ import annotations

"""Comfy Prompt Director V6.

Goal:
- Ollama/vision is the prompt brain.
- ComfyUI is the visual generator for all 6 image-to-image modes.
- Backend only adds readable text overlay after Comfy for flyer/poster.

This module is intentionally defensive: if Ollama vision fails, it still returns
safe local routing from prompt/image hints instead of poisoning the route as
`document`.
"""

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any

try:
    from app.services.ollama_service import chat, parse_json_object, env_bool
except Exception:  # pragma: no cover - import fallback for isolated tests
    chat = None
    parse_json_object = lambda text: None  # type: ignore
    def env_bool(name: str, default: bool = False) -> bool:  # type: ignore
        return default


MODES = {
    "auto",
    "person_identity",
    "product_ad",
    "flyer_poster",
    "background_replace",
    "creative_image",
}


@dataclass
class VisualDecision:
    requested_mode: str
    resolved_mode: str
    subject_type: str
    category: str
    subject_label: str
    is_packshot: bool
    is_lifestyle: bool
    contains_person: bool = False
    contains_document: bool = False
    colors: list[str] = field(default_factory=list)
    mood: str = "premium commercial"
    confidence: float = 0.55
    reason: str = "local fallback"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComfyPromptPack:
    mode: str
    category: str
    positive_prompt: str
    negative_prompt: str
    workflow_name: str
    width: int
    height: int
    denoise: float
    steps: int
    cfg: float
    seed: int | None = None
    overlay_enabled: bool = False
    overlay_title: str = ""
    overlay_subtitle: str = ""
    overlay_cta: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:220] if text else fallback


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def _safe_mode(mode: str | None) -> str:
    m = (mode or "auto").strip().lower().replace("-", "_")
    if m == "person":
        m = "person_identity"
    if m == "creative_reference":
        m = "creative_image"
    return m if m in MODES else "auto"


def _local_decision(requested_mode: str, prompt: str, subject_type_hint: str | None = None) -> VisualDecision:
    text = f"{prompt or ''} {subject_type_hint or ''}".lower()
    mode = _safe_mode(requested_mode)

    # Commercial product heuristics.  Keep watch before handbag because leather
    # straps otherwise look like bags.
    if _contains_any(text, ("watch", "wrist", "dial", "strap", "bracelet", "clock")):
        category, label, lifestyle, packshot = "watch", "watch on wrist", True, False
    elif _contains_any(text, ("handbag", "purse", "bag", "tote", "leather carry")):
        category, label, lifestyle, packshot = "handbag", "handbag", False, True
    elif _contains_any(text, ("bottle", "perfume", "drink", "flacon", "jar")):
        category, label, lifestyle, packshot = "bottle", "bottle product", False, True
    elif _contains_any(text, ("cosmetic", "lipstick", "cream", "serum", "beauty", "makeup")):
        category, label, lifestyle, packshot = "cosmetics", "beauty product", False, True
    elif _contains_any(text, ("phone", "laptop", "headphone", "keyboard", "device", "tech")):
        category, label, lifestyle, packshot = "tech", "tech product", False, True
    elif _contains_any(text, ("food", "burger", "pizza", "menu", "restaurant", "dish", "coffee")):
        category, label, lifestyle, packshot = "food", "food item", True, False
    elif _contains_any(text, ("person", "portrait", "face", "outfit", "identity", "selfie")) or subject_type_hint == "person":
        category, label, lifestyle, packshot = "person", "person", True, False
    elif _contains_any(text, ("document", "screenshot", "paper", "pdf", "invoice")):
        category, label, lifestyle, packshot = "document", "document", False, False
    else:
        category, label, lifestyle, packshot = "generic_product", "uploaded subject", False, True

    if mode == "auto":
        if category == "person":
            mode = "person_identity"
        elif category == "document":
            mode = "creative_image"
        else:
            mode = "product_ad"

    # Flyer/poster is commercial by default; do not allow vague upstream
    # document hints to destroy product routing unless the prompt explicitly asks
    # for document/screenshot/paper.
    if mode == "flyer_poster" and category == "document" and not _contains_any(text, ("document", "pdf", "screenshot", "paper", "invoice")):
        category, label, lifestyle, packshot = "generic_product", "uploaded product", False, True

    return VisualDecision(
        requested_mode=requested_mode,
        resolved_mode=mode,
        subject_type="person" if category == "person" else ("document" if category == "document" else "product"),
        category=category,
        subject_label=label,
        is_packshot=packshot,
        is_lifestyle=lifestyle,
        contains_person=category == "person",
        contains_document=category == "document",
        colors=[],
        mood="premium commercial",
        confidence=0.50,
        reason="local keyword fallback",
        raw={"prompt_hint": prompt[:500], "subject_type_hint": subject_type_hint},
    )


async def analyze_reference_for_comfy(
    image_path: str,
    requested_mode: str,
    user_prompt: str,
    subject_type_hint: str | None = None,
) -> VisualDecision:
    """Return a stable routing decision. Ollama failure never becomes document by itself."""
    requested_mode = _safe_mode(requested_mode)
    fallback = _local_decision(requested_mode, user_prompt, subject_type_hint)

    if chat is None or not env_bool("OLLAMA_VISION_ENABLED", True):
        return fallback

    instruction = """
You are an image-to-image production director for ComfyUI.
Return ONLY compact JSON with these keys:
subject_type: one of product, person, document, object
category: one of watch, handbag, bottle, cosmetics, tech, food, person, document, generic_product
subject_label: short product/person label
is_packshot: boolean
is_lifestyle: boolean
contains_person: boolean
contains_document: boolean
colors: array of 1-5 color names
mood: short commercial mood
recommended_mode: one of auto, person_identity, product_ad, flyer_poster, background_replace, creative_image
confidence: number 0..1
reason: short reason
Rules:
- A watch on a wrist is category watch and is_lifestyle true.
- Leather strap does NOT mean handbag.
- Do not classify commercial product photos as document unless they are actually screenshots, PDFs, paper pages, or UI captures.
""".strip()
    try:
        result = await chat(
            [{"role": "user", "content": f"{instruction}\nUser requested mode: {requested_mode}\nUser prompt: {user_prompt or ''}"}],
            feature="image_understanding",
            json_mode=True,
            image_paths=[image_path],
            timeout_seconds=90.0,
        )
        parsed = parse_json_object(result.content) if result and result.ok else None
        if not isinstance(parsed, dict):
            return fallback

        category = _clean_text(parsed.get("category"), fallback.category).lower().replace(" ", "_")
        if category not in {"watch", "handbag", "bottle", "cosmetics", "tech", "food", "person", "document", "generic_product"}:
            category = fallback.category

        # Guard against the exact bug you hit: vision failure/document poison.
        if category == "document" and requested_mode in {"flyer_poster", "product_ad", "background_replace"}:
            if fallback.category != "document":
                category = fallback.category

        mode = _safe_mode(parsed.get("recommended_mode") or requested_mode)
        if requested_mode != "auto":
            mode = requested_mode
        elif mode == "auto":
            mode = fallback.resolved_mode

        return VisualDecision(
            requested_mode=requested_mode,
            resolved_mode=mode,
            subject_type="person" if category == "person" else ("document" if category == "document" else "product"),
            category=category,
            subject_label=_clean_text(parsed.get("subject_label"), fallback.subject_label),
            is_packshot=bool(parsed.get("is_packshot", fallback.is_packshot)),
            is_lifestyle=bool(parsed.get("is_lifestyle", fallback.is_lifestyle)),
            contains_person=bool(parsed.get("contains_person", category == "person")),
            contains_document=bool(parsed.get("contains_document", category == "document")),
            colors=[_clean_text(c) for c in (parsed.get("colors") or []) if _clean_text(c)][:5],
            mood=_clean_text(parsed.get("mood"), fallback.mood),
            confidence=float(parsed.get("confidence") or 0.72),
            reason=_clean_text(parsed.get("reason"), "ollama vision"),
            raw={"ollama": parsed, "fallback": fallback.__dict__},
        )
    except Exception as exc:
        fallback.raw["ollama_error"] = str(exc)[:500]
        return fallback


def _overlay_from_user_prompt(user_prompt: str) -> tuple[str, str, str]:
    prompt = user_prompt or ""
    # Support markers inserted by the frontend/back-end when available.
    def marker(name: str) -> str:
        m = re.search(rf"\[{re.escape(name)}:(.*?)\]", prompt, flags=re.I | re.S)
        return _clean_text(m.group(1), "") if m else ""
    title = marker("AI_STUDIO_HEADLINE") or "SUMMER PROMO"
    subtitle = marker("AI_STUDIO_SUBHEADLINE") or "Limited time only"
    cta = marker("AI_STUDIO_CTA") or "Order now"
    return title, subtitle, cta


def build_comfy_prompt_pack(
    decision: VisualDecision,
    user_prompt: str,
    negative_prompt: str | None,
    width: int | None,
    height: int | None,
    strength: float | None = None,
) -> ComfyPromptPack:
    mode = decision.resolved_mode
    w, h = int(width or 1024), int(height or 1024)
    if mode == "flyer_poster":
        w, h = 832, 1024
    elif mode in {"product_ad", "background_replace", "creative_image"}:
        w = min(max(w, 768), 1024)
        h = min(max(h, 768), 1024)
    elif mode == "person_identity":
        w, h = min(w, 1024), min(h, 1024)

    title, subtitle, cta = _overlay_from_user_prompt(user_prompt)
    subject = decision.subject_label or "uploaded reference"
    category = decision.category
    colors = ", ".join(decision.colors) if decision.colors else "matching product colors"

    shared_source_lock = (
        f"Use the uploaded reference image as the primary visual source. Preserve the exact {subject}: "
        "shape, proportions, material, color, logo/label details and identity. "
        "Do not create a different product. Do not duplicate the subject. "
    )

    if mode == "flyer_poster":
        positive = (
            f"{shared_source_lock} Create a real premium advertising flyer/poster visual for a {category} campaign. "
            "ComfyUI should design the visual composition, background, lighting, depth, premium commercial atmosphere, "
            "and clean poster structure. Leave clean empty negative space at the top for a headline and at the bottom for a CTA. "
            "Do NOT render letters, words, fake typography, random logos or unreadable text inside the image. "
            f"Style: {decision.mood}, professional campaign flyer, high-end studio lighting, elegant background, {colors}, "
            "sharp product focus, premium editorial composition, production quality. "
            f"User direction: {user_prompt or 'premium social media flyer'}."
        )
        workflow = "flyer_poster"
        overlay = True
        denoise = 0.46 if decision.is_lifestyle else 0.38
        steps, cfg = 8, 1.15
    elif mode == "product_ad":
        positive = (
            f"{shared_source_lock} Create a new commercial product advertisement scene, premium studio setup, "
            "refined background, realistic shadows, high-end ecommerce campaign, no readable text, no fake letters. "
            f"Category: {category}. Mood: {decision.mood}. User direction: {user_prompt}."
        )
        workflow, overlay, denoise, steps, cfg = "product_ad", False, 0.44, 8, 1.10
    elif mode == "background_replace":
        positive = (
            f"{shared_source_lock} Replace only the environment/background with the requested scene while preserving the main subject. "
            "Realistic integration, coherent lighting, clean background, no fake text. "
            f"User direction: {user_prompt}."
        )
        workflow, overlay, denoise, steps, cfg = "background_replace", False, 0.50, 8, 1.10
    elif mode == "person_identity":
        positive = (
            "Use the uploaded person as the identity reference. Preserve facial identity, facial structure, age, and expression. "
            "Create a new professional scene/outfit/styling only as requested. No distorted face, no extra people, no fake text. "
            f"User direction: {user_prompt}."
        )
        workflow, overlay, denoise, steps, cfg = "person_identity", False, 0.32, 8, 1.05
    elif mode == "creative_image":
        positive = (
            f"Use the uploaded image as visual reference material. Create a transformed creative composition with strong art direction, "
            "coherent scene, premium lighting, no fake text, no artifacts. "
            f"Preserve important recognizable elements from: {subject}. User direction: {user_prompt}."
        )
        workflow, overlay, denoise, steps, cfg = "creative_image", False, 0.58, 8, 1.20
    else:
        positive = f"{shared_source_lock} Create a polished reference-based image. User direction: {user_prompt}."
        workflow, overlay, denoise, steps, cfg = "auto", False, 0.42, 8, 1.10

    base_negative = (
        "blurry, low quality, jpeg artifacts, distorted product, changed identity, changed logo, wrong label, "
        "duplicate product, extra product, melted edges, broken geometry, fake typography, unreadable text, random letters, "
        "watermark, signature, cluttered layout, bad composition, amateur flyer, messy background"
    )
    if negative_prompt:
        base_negative = f"{base_negative}, {negative_prompt}"

    return ComfyPromptPack(
        mode=mode,
        category=category,
        positive_prompt=positive,
        negative_prompt=base_negative,
        workflow_name=workflow,
        width=w,
        height=h,
        denoise=float(strength) if strength and 0.15 <= float(strength) <= 0.85 else denoise,
        steps=steps,
        cfg=cfg,
        overlay_enabled=overlay,
        overlay_title=title,
        overlay_subtitle=subtitle,
        overlay_cta=cta,
        metadata={"decision": decision.__dict__, "director_version": "comfy-director-v6-all-modes"},
    )
