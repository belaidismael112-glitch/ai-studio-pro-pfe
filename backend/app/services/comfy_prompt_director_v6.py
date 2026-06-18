from __future__ import annotations

"""Comfy Prompt Director V11 Shared Design Layer.

Keeps V10.3 Flyer/Poster stable and adds isolated mode adapters for the 5 remaining modes.
"""

from dataclasses import dataclass, field
import json
import os
import re
from typing import Any

try:
    from app.services.ollama_service import chat, parse_json_object, env_bool
except Exception:  # pragma: no cover
    chat = None
    parse_json_object = lambda text: None  # type: ignore
    def env_bool(name: str, default: bool = False) -> bool:  # type: ignore
        return default

try:
    from app.services.img2img_hybrid.design_layer_engine import select_mode_design, normalize_mode
    from app.services.img2img_hybrid.modes.auto_smart_router import route as auto_route
except Exception:  # pragma: no cover
    select_mode_design = None  # type: ignore
    normalize_mode = lambda m: (m or "auto")  # type: ignore
    auto_route = None  # type: ignore

MODES = {"auto", "person_identity", "product_ad", "flyer_poster", "background_replace", "creative_image", "social_post"}

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

def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}

def _env_int(name: str, default: int) -> int:
    try: return int(os.getenv(name, str(default)))
    except Exception: return default

def _env_float(name: str, default: float) -> float:
    try: return float(os.getenv(name, str(default)))
    except Exception: return default

def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:260] if text else fallback

def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(w in t for w in words)

def _safe_mode(mode: str | None) -> str:
    m = normalize_mode((mode or "auto").strip().lower().replace("-", "_"))
    return m if m in MODES else "auto"

def _classify_from_text(text: str) -> tuple[str, str, bool, bool]:
    if _contains_any(text, ("watch", "wrist", "dial", "strap", "bracelet", "clock", "montre", "charlie")):
        return "watch", "luxury wristwatch", True, False
    if _contains_any(text, ("handbag", "purse", "bag", "tote", "leather carry", "sac")):
        return "handbag", "premium handbag", False, True
    if _contains_any(text, ("bottle", "perfume", "drink", "flacon", "jar")):
        return "bottle", "bottle product", False, True
    if _contains_any(text, ("cosmetic", "lipstick", "cream", "serum", "beauty", "makeup")):
        return "cosmetics", "beauty product", False, True
    if _contains_any(text, ("phone", "laptop", "headphone", "keyboard", "device", "tech")):
        return "tech", "tech product", False, True
    if _contains_any(text, ("food", "burger", "pizza", "menu", "restaurant", "dish", "coffee")):
        return "food", "food item", True, False
    if _contains_any(text, ("person", "portrait", "face", "outfit", "identity", "selfie", "headshot")):
        return "person", "person", True, False
    if _contains_any(text, ("document flyer", "pdf", "screenshot", "invoice", "paper page", "ui screenshot")):
        return "document", "document", False, False
    return "generic_product", "uploaded product", False, True

def _local_decision(requested_mode: str, prompt: str, subject_type_hint: str | None = None) -> VisualDecision:
    text = (prompt or "").lower()
    requested = _safe_mode(requested_mode)
    category, label, lifestyle, packshot = _classify_from_text(text)
    if subject_type_hint == "person" and category == "generic_product":
        category, label, lifestyle, packshot = "person", "person", True, False
    if requested == "auto" and auto_route is not None:
        resolved, reason = auto_route("auto", "person" if category == "person" else ("document" if category == "document" else "product"), category, prompt, category == "person")
    elif requested == "auto":
        resolved, reason = ("person_identity" if category == "person" else "product_ad"), "local auto"
    else:
        resolved, reason = requested, "explicit mode"
    if resolved == "flyer_poster" and category == "document" and not _contains_any(text, ("pdf", "screenshot", "invoice", "paper page")):
        category, label, lifestyle, packshot = "generic_product", "uploaded product", False, True
    return VisualDecision(
        requested_mode=requested_mode,
        resolved_mode=resolved,
        subject_type="person" if category == "person" else ("document" if category == "document" else "product"),
        category=category,
        subject_label=label,
        is_packshot=packshot,
        is_lifestyle=lifestyle,
        contains_person=category == "person",
        contains_document=category == "document",
        mood="premium commercial",
        confidence=0.55,
        reason=reason,
        raw={"prompt_hint": prompt[:500], "subject_type_hint": subject_type_hint},
    )

async def analyze_reference_for_comfy(image_path: str, requested_mode: str, user_prompt: str, subject_type_hint: str | None = None) -> VisualDecision:
    requested_mode = _safe_mode(requested_mode)
    fallback = _local_decision(requested_mode, user_prompt, subject_type_hint)
    if chat is None or not env_bool("OLLAMA_VISION_ENABLED", True):
        return fallback
    instruction = """
You are an image-to-image production director for ComfyUI.
Return ONLY compact JSON with keys:
subject_type, category, subject_label, is_packshot, is_lifestyle, contains_person, contains_document, colors, mood, recommended_mode, confidence, reason.
Modes: auto, person_identity, product_ad, flyer_poster, background_replace, creative_image, social_post.
Categories: watch, handbag, bottle, cosmetics, tech, food, person, document, generic_product.
Rules: commercial product photos are product, not document. A watch strap is not handbag. If social/instagram/story intent, recommend social_post. If background/environment intent, recommend background_replace. If person/portrait/headshot, recommend person_identity.
""".strip()
    try:
        result = await chat([
            {"role": "user", "content": f"{instruction}\nUser requested mode: {requested_mode}\nUser prompt: {user_prompt or ''}"}
        ], feature="image_understanding", json_mode=True, image_paths=[image_path], timeout_seconds=90.0)
        parsed = parse_json_object(result.content) if result and result.ok else None
        if not isinstance(parsed, dict):
            return fallback
        category = _clean_text(parsed.get("category"), fallback.category).lower().replace(" ", "_")
        if category not in {"watch", "handbag", "bottle", "cosmetics", "tech", "food", "person", "document", "generic_product"}:
            category = fallback.category
        if category == "document" and requested_mode in {"flyer_poster", "product_ad", "background_replace", "social_post"}:
            category = fallback.category if fallback.category != "document" else "generic_product"
        if requested_mode == "auto" and auto_route is not None:
            mode, route_reason = auto_route("auto", "person" if category == "person" else ("document" if category == "document" else "product"), category, user_prompt, bool(parsed.get("contains_person", category == "person")))
        elif requested_mode != "auto":
            mode, route_reason = requested_mode, "explicit mode"
        else:
            mode, route_reason = _safe_mode(parsed.get("recommended_mode") or fallback.resolved_mode), "ollama mode"
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
            reason=route_reason + "; " + _clean_text(parsed.get("reason"), "ollama vision"),
            raw={"ollama": parsed, "fallback": fallback.__dict__},
        )
    except Exception as exc:
        fallback.raw["ollama_error"] = str(exc)[:500]
        return fallback

def _extract_frontend_text(user_prompt: str) -> tuple[str, str, str]:
    def marker(name: str) -> str:
        m = re.search(rf"\[{re.escape(name)}:(.*?)\]", user_prompt or "", flags=re.I | re.S)
        return _clean_text(m.group(1), "") if m else ""
    return (marker("AI_STUDIO_HEADLINE") or marker("HEADLINE") or "TIMELESS STYLE").upper(), marker("AI_STUDIO_SUBHEADLINE") or marker("SUBHEADLINE") or "Premium design for everyday elegance", (marker("AI_STUDIO_CTA") or marker("CTA") or "SHOP NOW").upper()

def _strip_markers(user_prompt: str, limit: int=360) -> str:
    text = re.sub(r"\[[A-Z0-9_]+:.*?\]", " ", str(user_prompt or ""), flags=re.I | re.S)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]

def _category_flyer_brief(category: str, subject: str, colors: str, title: str, subtitle: str, cta: str) -> str:
    c = (category or "generic_product").lower()
    if c == "handbag":
        return "Luxury handbag campaign poster with premium editorial composition, warm accents, soft shadow, and product integrated into the design."
    if c == "watch":
        return "Premium watch campaign poster, dark luxury lighting, sharp hero watch, clean typography zones, CTA badge."
    if c in {"bottle", "cosmetics"}:
        return "Premium beauty/product campaign poster, glossy surface, spotlight, cream and gold palette, clean type hierarchy."
    if c == "tech":
        return "Premium tech launch poster, dark futuristic gradient, geometric panels, clean product hero, modern typography."
    return "Premium commercial social media poster with designed background panels, hero product, soft shadow, clean type hierarchy and CTA."

def build_comfy_prompt_pack(decision: VisualDecision, user_prompt: str, negative_prompt: str | None, width: int | None, height: int | None, strength: float | None = None) -> ComfyPromptPack:
    mode = _safe_mode(decision.resolved_mode)
    w, h = int(width or 1024), int(height or 1024)
    title, subtitle, cta = _extract_frontend_text(user_prompt)
    subject = decision.subject_label or "uploaded reference"
    category = decision.category
    shared_source_lock = f"Use the uploaded image as reference. Preserve the recognizable {subject}: silhouette, material, color, logo/label if visible. Do not invent a different subject. "
    metadata: dict[str, Any] = {"decision": decision.__dict__, "director_version": "v11-shared-design-layer-5-modes"}

    if mode == "flyer_poster":
        flyer_w = _env_int("COMFY_DIRECTOR_V6_FLYER_WIDTH", 640)
        flyer_h = _env_int("COMFY_DIRECTOR_V6_FLYER_HEIGHT", 768)
        w, h = flyer_w, flyer_h
        style_brief = _category_flyer_brief(category, subject, "", title, subtitle, cta)
        positive = (
            f"{shared_source_lock} Premium {category} advertising poster. Follow the V10.3 selected layout guide exactly. "
            "Do not reuse the old left black panel/right product card template. "
            f"{style_brief} User direction: {_strip_markers(user_prompt)}. Readable final text: headline '{title}', subheadline '{subtitle}', CTA '{cta}'. Portrait poster {w}x{h}."
        )
        workflow, overlay = "flyer_poster", False
        denoise = _env_float("COMFY_DIRECTOR_V10_3_FLYER_DENOISE", 0.58)
        steps = _env_int("COMFY_DIRECTOR_V10_3_FLYER_STEPS", 4)
        cfg = _env_float("COMFY_DIRECTOR_V10_3_CFG", 1.0)
    else:
        if select_mode_design is not None:
            design = select_mode_design(mode, decision, user_prompt, w, h)
            mode = design.mode
            w, h = design.width, design.height
            workflow = design.workflow_name
            denoise, steps, cfg = design.denoise, design.steps, design.cfg
            overlay = False
            positive = f"{shared_source_lock} {design.positive_brief} Follow the selected V11 design guide: {design.selected_layout}."
            metadata["v11_design"] = design
        else:
            workflow, overlay, denoise, steps, cfg = mode, False, 0.45, 4, 1.0
            positive = f"{shared_source_lock} Create a polished {mode} result. User direction: {_strip_markers(user_prompt)}."

    base_negative = "blurry, low quality, jpeg artifacts, distorted subject, changed identity, changed logo, wrong label, duplicate subject, melted edges, broken geometry, fake typography, unreadable text, random letters, watermark, signature, cluttered layout, bad composition"
    if mode == "background_replace":
        base_negative += ", text, typography, CTA, poster, flyer, cards, product redesign"
    if mode == "person_identity":
        base_negative += ", changed face, different person, altered age, distorted eyes, distorted mouth, extra face"
    if negative_prompt:
        base_negative = f"{base_negative}, {negative_prompt}"
    denoise_value = _env_float(f"COMFY_DIRECTOR_V6_{mode.upper()}_DENOISE", denoise)
    if os.getenv("COMFY_DIRECTOR_V6_USE_UI_STRENGTH", "false").lower() in {"1", "true", "yes", "on"}:
        try:
            if strength and 0.15 <= float(strength) <= 0.85:
                denoise_value = float(strength)
        except Exception:
            pass
    return ComfyPromptPack(mode=mode, category=category, positive_prompt=positive, negative_prompt=base_negative, workflow_name=workflow, width=w, height=h, denoise=denoise_value, steps=steps, cfg=cfg, overlay_enabled=overlay, overlay_title=title, overlay_subtitle=subtitle, overlay_cta=cta, metadata=metadata)
