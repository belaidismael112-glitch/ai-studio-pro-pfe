"""Vision helper route - English/French with real local face analysis and editable generation settings."""
from pathlib import Path
from typing import Literal, Any
import re
import uuid

from PIL import Image

from fastapi import APIRouter, UploadFile, File, Form, Depends, Request, HTTPException
from pydantic import BaseModel

from app.services.face_alignment_helper import analyze_face_reference
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.services.subject_lock_helper import analyze_universal_subject
from app.services.ollama_service import env_bool, json_chat

router = APIRouter(prefix="/assistant/vision", tags=["assistant-vision"])
CODE_VERSION = "vision-pro-semantic-camera-analysis-2026-06-16"

ALLOWED_SIZES = {"1280x720", "1920x1080", "1536x1024", "1024x1024", "1024x1536", "720x1280"}
ALLOWED_ORIENTATIONS = {"landscape", "portrait", "square/near-square"}
ALLOWED_LIGHTING = {"balanced", "studio soft", "cinematic", "low-key / dark", "bright / high-key"}
ALLOWED_TEMPERATURES = {"neutral", "warm", "cool"}
ALLOWED_CONTRASTS = {"medium contrast", "soft contrast", "strong contrast"}


class MagicLensSuggestion(BaseModel):
    action: Literal["generate_image", "make_prompt"]
    title: str
    prompt: str
    description: str | None = None
    negative_prompt: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    workflow_stage: Literal["identity_expression_board", "pose_style_direction", "subject_lock_prompt"] | None = None
    generation_mode: Literal["person_identity", "auto"] | None = None
    strength: float | None = None
    layout: str | None = None


class PersonaWorkflowStage(BaseModel):
    order: int
    key: Literal["identity_expression_board", "pose_style_direction"]
    title: str
    description: str
    output_intent: str
    prompt: str
    width: int
    height: int
    generation_mode: Literal["person_identity"] = "person_identity"
    strength: float
    requires_identity_review: bool = True


class PersonaWorkflow(BaseModel):
    enabled: bool
    status: Literal["ready", "blocked"]
    title: str
    summary: str
    identity_source: str
    stages: list[PersonaWorkflowStage]
    delivery_note: str


class MagicLensAnalyzeResult(BaseModel):
    success: bool
    provider: str
    image_url: str | None = None
    description: str
    detected_language: str
    suggestions: list[MagicLensSuggestion]
    error: str | None = None
    face_profile: dict[str, Any] | None = None
    face_prompt: str | None = None
    persona_workflow: PersonaWorkflow | None = None
    code_version: str = CODE_VERSION


def backend_root():
    return Path(__file__).resolve().parents[3]


def lang_of(v, text=""):
    v = (v or "auto").lower()
    if v in {"en", "fr"}:
        return v
    return "fr" if any(w in (text or "").lower() for w in ["bonjour", "francais", "français", "image", "visage", "analyse"]) else "en"


def clean_choice(value: str | None, allowed: set[str], fallback: str) -> str:
    candidate = (value or "").strip().lower()
    return candidate if candidate in allowed else fallback


def parse_size(size: str | None) -> tuple[int | None, int | None]:
    if not size:
        return None, None
    match = re.fullmatch(r"(\d{3,4})x(\d{3,4})", size.strip().lower())
    if not match:
        return None, None
    width = int(match.group(1))
    height = int(match.group(2))
    return width, height


def _num_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None



def _bool_from_payload(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_int_score(value: Any, fallback: int = 0) -> int:
    try:
        return int(max(0, min(100, round(float(value)))))
    except Exception:
        return fallback


def _map_semantic_subject(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if raw in {"person", "human", "face", "portrait", "man", "woman", "person_face"}:
        return "person_face"
    if raw in {"full_body", "person_full_body", "body", "pose", "model"}:
        return "person_full_body"
    if raw in {"product", "packshot", "bottle", "perfume", "phone", "shoe", "watch", "packaging"}:
        return "product"
    if raw in {"background", "scene", "landscape", "street", "studio", "room", "beach", "indoor", "outdoor"}:
        return "scene"
    if raw in {"small_object", "object", "generic_object", "tool", "food", "plant"}:
        return "object_or_product"
    if raw in {"document", "paper", "poster", "flyer", "receipt", "invoice"}:
        return "document_or_poster"
    if raw in {"car", "vehicle"}:
        return "car"
    if raw in {"pet", "animal", "dog", "cat"}:
        return "pet"
    return None


async def analyze_optional_semantic_vision(image_path: Path, hint: str) -> dict[str, Any]:
    """Optional high-level semantic detector for Neural Camera Analysis.

    Local CV always runs first. When Ollama Vision is installed, this adds the
    missing semantic layer: product vs person vs full-body vs background/scene.
    It never blocks generation and never becomes a hard dependency.
    """
    if not env_bool("OLLAMA_VISION_ENABLED", True):
        return {"used": False, "provider": "ollama_disabled"}
    system = (
        "You are the semantic vision layer for a professional AI camera analysis tool. "
        "Analyze the actual uploaded image and return JSON only. Do not write markdown. "
        "Return keys: subject_type, primary_subject, person_present, face_visible, full_body_visible, "
        "product_present, small_object_present, multiple_people, background_type, scene_type, "
        "lighting_issue, blur_issue, far_subject_issue, background_clutter, confidence, reason, "
        "generation_strategy, prompt_focus. "
        "subject_type must be one of: person_face, person_full_body, product, small_object, background_scene, document_or_poster, car, pet, object_or_product. "
        "Use full_body_visible=true only when the body/pose is visibly important, not for a close-up face. "
        "Use product_present=true for manufactured products, packaging, bottles, watches, phones, shoes or branded objects. "
        "Use background_type for simple labels such as studio, street, room, outdoor, beach, dark, clean, cluttered."
    )
    user = (
        f"User/context hint: {hint or 'none'}\n"
        "Classify the image for image-to-image generation routing and subject preservation."
    )
    try:
        payload, result = await json_chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            mode="advanced",
            feature="image_understanding",
            timeout_seconds=45,
            image_paths=[str(image_path)],
        )
        if not payload:
            return {"used": False, "provider": result.provider, "error": result.error or "empty vision response"}
        payload["used"] = True
        payload["provider"] = result.provider
        return payload
    except Exception as exc:
        return {"used": False, "provider": "ollama_vision", "error": str(exc)[:500]}


def merge_semantic_vision(subject: dict[str, Any], semantic: dict[str, Any]) -> dict[str, Any]:
    merged = dict(subject or {})
    merged["semantic_vision"] = semantic
    if not semantic.get("used"):
        return merged

    semantic_type = _map_semantic_subject(semantic.get("subject_type"))
    current = str(merged.get("subject_type") or "unknown")
    face_proven = current == "person_face" and bool(merged.get("primary_subject_detected"))

    # Never downgrade a real face detector. Upgrade weak/generic categories when
    # semantic vision provides a clearer label.
    if semantic_type and not face_proven and current in {"unknown", "object_or_product", "document_or_poster", "scene"}:
        if semantic_type == "person_face" and not _bool_from_payload(semantic.get("face_visible")):
            semantic_type = "person_full_body" if _bool_from_payload(semantic.get("person_present")) else current
        merged["subject_type"] = semantic_type
        merged["semantic_subject_type"] = semantic_type

    background = dict(merged.get("background_analysis") or {})
    background.update({
        "semantic_label": semantic.get("background_type") or semantic.get("scene_type"),
        "semantic_scene_type": semantic.get("scene_type"),
        "semantic_background_clutter": semantic.get("background_clutter"),
        "semantic_source": "ollama_vision_plus_local_cv",
    })
    merged["background_analysis"] = background

    product = dict(merged.get("product_analysis") or {})
    if _bool_from_payload(semantic.get("product_present")) or _map_semantic_subject(semantic.get("subject_type")) == "product":
        product.update({
            "detected": True,
            "confidence": max(int(product.get("confidence") or 0), _safe_int_score(semantic.get("confidence"), 74)),
            "source": "ollama_vision_semantic",
            "primary_subject": semantic.get("primary_subject"),
        })
    merged["product_analysis"] = product

    full_body = dict(merged.get("full_body_analysis") or {})
    if _bool_from_payload(semantic.get("full_body_visible")):
        full_body.update({
            "detected": True,
            "confidence": max(int(full_body.get("confidence") or 0), _safe_int_score(semantic.get("confidence"), 72)),
            "label": "semantic_full_body_visible",
            "source": "ollama_vision_semantic",
            "recommendation": "Use full-frame source for body/pose preservation; do not crop to face only.",
        })
    merged["full_body_analysis"] = full_body

    small_object = dict(merged.get("small_object_analysis") or {})
    if _bool_from_payload(semantic.get("small_object_present")) or _bool_from_payload(semantic.get("far_subject_issue")):
        small_object.update({
            "is_small_object_risk": True,
            "object_scale_label": "small_or_far_semantic",
            "small_object_confidence": max(int(small_object.get("small_object_confidence") or 0), _safe_int_score(semantic.get("confidence"), 70)),
            "recommendation": "Move closer or crop the subject before final generation.",
        })
    merged["small_object_analysis"] = small_object

    caps = dict(merged.get("capability_matrix") or {})
    if _bool_from_payload(semantic.get("person_present")):
        caps["person"] = {"available": True, "confidence": _safe_int_score(semantic.get("confidence"), 74), "source": "ollama_vision_semantic"}
    if _bool_from_payload(semantic.get("product_present")):
        caps["product"] = {"available": True, "confidence": _safe_int_score(semantic.get("confidence"), 74), "source": "ollama_vision_semantic"}
    if _bool_from_payload(semantic.get("multiple_people")):
        caps["multi_person"] = {"available": True, "confidence": _safe_int_score(semantic.get("confidence"), 80), "source": "ollama_vision_semantic"}
    if _bool_from_payload(semantic.get("full_body_visible")):
        caps["full_body"] = {"available": True, "confidence": _safe_int_score(semantic.get("confidence"), 72), "label": "semantic_full_body_visible"}
    caps["background"] = {"available": True, "confidence": _safe_int_score(semantic.get("confidence"), int(background.get("background_cleanliness_score") or 60)), "label": background.get("semantic_label") or background.get("local_background_label")}
    merged["capability_matrix"] = caps

    risks = list(merged.get("risks") or [])
    recommendations = list(merged.get("recommendations") or [])
    if _bool_from_payload(semantic.get("lighting_issue")):
        risks.append("Semantic vision also detected a lighting issue.")
    if _bool_from_payload(semantic.get("blur_issue")):
        risks.append("Semantic vision also detected blur/soft focus.")
    if _bool_from_payload(semantic.get("far_subject_issue")):
        risks.append("Semantic vision detected that the subject is far/small in the frame.")
    if semantic.get("generation_strategy"):
        recommendations.append(f"Vision strategy: {semantic.get('generation_strategy')}")
    if semantic.get("prompt_focus"):
        merged["semantic_prompt_focus"] = str(semantic.get("prompt_focus"))[:700]
    merged["risks"] = list(dict.fromkeys(risks))[:8]
    merged["recommendations"] = list(dict.fromkeys(recommendations))[:8]
    return merged

def subject_lock_strength(subject: dict[str, Any]) -> float:
    """Conservative img2img strength tuned for real camera/DJI references."""
    subject_type = str(subject.get("subject_type") or "").lower()
    coverage = _num_or_none(subject.get("primary_subject_coverage_percent")) or 0.0
    quality = _num_or_none(subject.get("reference_quality_score")) or 0.0
    preservation = _num_or_none(subject.get("subject_preservation_score")) or 0.0

    if subject_type == "person_face":
        if coverage >= 18 and quality >= 70 and preservation >= 70:
            return 0.14
        if coverage >= 14 and quality >= 55 and preservation >= 55:
            return 0.18
        return 0.20
    if subject_type in {"product", "car", "pet", "object_or_product"}:
        return 0.18
    if subject_type in {"document", "document_or_poster"}:
        return 0.12
    return 0.20


def create_primary_face_crop(image_path: Path, bbox: dict[str, Any] | None) -> Path | None:
    if not bbox:
        return None
    try:
        x = int(bbox.get("x", 0))
        y = int(bbox.get("y", 0))
        w = int(bbox.get("w", 0))
        h = int(bbox.get("h", 0))
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        iw, ih = rgb.size
        pad_x = int(w * 0.35)
        pad_y = int(h * 0.45)
        left = max(0, x - pad_x)
        top = max(0, y - pad_y)
        right = min(iw, x + w + pad_x)
        bottom = min(ih, y + h + pad_y)
        if right <= left or bottom <= top:
            return None
        crop = rgb.crop((left, top, right, bottom))
        crop_name = f"{image_path.stem}_facecrop.jpg"
        crop_path = image_path.with_name(crop_name)
        crop.save(crop_path, format="JPEG", quality=95)
        return crop_path


def create_bbox_crop(image_path: Path, bbox: dict[str, Any] | None, *, suffix: str) -> Path | None:
    if not bbox:
        return None
    try:
        x = int(bbox.get("x", 0))
        y = int(bbox.get("y", 0))
        w = int(bbox.get("w", 0))
        h = int(bbox.get("h", 0))
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        iw, ih = rgb.size
        pad_x = int(w * 0.12)
        pad_y = int(h * 0.12)
        left = max(0, x - pad_x)
        top = max(0, y - pad_y)
        right = min(iw, x + w + pad_x)
        bottom = min(ih, y + h + pad_y)
        if right <= left or bottom <= top:
            return None
        crop = rgb.crop((left, top, right, bottom))
        crop_path = image_path.with_name(f"{image_path.stem}_{suffix}.jpg")
        crop.save(crop_path, format="JPEG", quality=95)
        return crop_path


def build_universal_subject_prompt(
    face_profile: dict[str, Any],
    *,
    lang: str,
    settings: dict[str, str],
    base_hint: str,
) -> str:
    """Build the generation prompt only. Keep analysis/report details out of the model prompt."""
    subject = face_profile.get("subject_analysis") or {}
    subject_type = subject.get("subject_type") or "unknown"
    size = settings["size"]
    orientation = settings["orientation"]
    lighting = settings["lighting"]
    temperature = settings["temperature"]
    contrast = settings["contrast"]
    subject_prompt = subject.get("prompt_fr" if lang == "fr" else "prompt_en") or ""
    quality = subject.get("reference_quality_score")
    preservation = subject.get("subject_preservation_score")
    coverage = subject.get("primary_subject_coverage_percent")
    gate = "blocked" if subject.get("hard_block_generation") else "allowed" if subject.get("can_generate") else "review"
    real = face_profile.get("real_face_analysis") or {}
    raw_identity = real.get("identity_reliability_score")
    raw_generation = real.get("generation_confidence_score")

    metadata = (
        f"Subject type {subject_type}; coverage {coverage}%; reference quality {quality}/100; "
        f"subject preservation {preservation}/100; identity reliability {raw_identity}/100; "
        f"generation confidence {raw_generation}/100; generation_gate {gate}."
    )

    if subject_type == "person_face":
        if lang == "fr":
            return (
                "Utilise l'image importée comme source d'identité principale. "
                f"{subject_prompt} "
                "Préserver le même corps visible, les épaules, les vêtements, la perspective caméra, la lumière et l'arrière-plan cohérents. "
                "Si la source vient d'une caméra/DJI propre, utiliser le cadre original comme référence principale au lieu d'inventer un nouveau corps ou décor. "
                f"Sortie {size}, orientation {orientation}, lumière {lighting}, température {temperature}, contraste {contrast}. "
                "Do not render analysis labels, scores, UI text, captions or watermarks. "
                f"Contexte utilisateur: {base_hint}."
            )
        return (
            "Use the uploaded image as the primary identity source. "
            f"{subject_prompt} "
            "Preserve the visible body, shoulders, clothing, camera perspective, lighting and coherent background. "
            "When the source is a clean camera/DJI capture, use the original full frame as the main reference instead of inventing a new body or scene. "
            f"Output {size}, orientation {orientation}, lighting {lighting}, {temperature} temperature, {contrast}. "
            "Do not render analysis labels, scores, UI text, captions or watermarks. "
            f"User context: {base_hint}."
        )

    if lang == "fr":
        return (
            "Utilise l'image importée comme référence principale du sujet. "
            f"{subject_prompt} "
            f"Sortie {size}, orientation {orientation}; lumière {lighting}, température {temperature}, contraste {contrast}. "
            "Même sujet, mêmes proportions, mêmes couleurs/matières, pas de redesign, pas d'invention de détails majeurs. "
            "Ne pas rendre de labels d'analyse, scores, texte UI, légendes ou filigranes. "
            f"Contexte utilisateur: {base_hint}."
        )

    return (
        "Use the uploaded image as the primary subject reference. "
        f"{subject_prompt} "
        f"Output {size}, orientation {orientation}; lighting {lighting}, {temperature} color temperature, {contrast}. "
        "Same subject, same proportions, same colors/materials, no redesign, no major invented details. "
        "Do not render analysis labels, scores, UI text, captions or watermarks. "
        f"User context: {base_hint}."
    )



def build_persona_workflow(
    face_profile: dict[str, Any],
    *,
    lang: str,
    base_prompt: str,
) -> PersonaWorkflow | None:
    """Prepare the honest two-stage person workflow requested by the user.

    Stage 1 generates a same-person expression board. Stage 2 proposes full-body
    pose and wardrobe directions. Stage 2 is deliberately described as a style
    proposal: a face-only upload cannot prove exact body reconstruction.
    """
    subject = face_profile.get("subject_analysis") or {}
    if subject.get("subject_type") != "person_face":
        return None

    blocked = bool(subject.get("hard_block_generation")) or subject.get("can_generate") is False
    if lang == "fr":
        stage1_title = "Étape 1 · Planche personnage avec expressions"
        stage1_desc = "Génère une planche 4×3 de la même personne avec plusieurs expressions, en gardant l'identité du visage verrouillée."
        stage1_intent = "Planche identité + expressions de la même personne"
        stage2_title = "Étape 2 · Suggestions poses et tenues plein pied"
        stage2_desc = "Après validation de l'identité, propose six directions plein pied avec poses et styles vestimentaires. Ce sont des directions créatives à revoir, pas une reconstruction corporelle mesurée."
        stage2_intent = "Planche de directions plein pied, poses et tenues"
        summary = "À partir d'un visage, construire d'abord une personnalité visuelle cohérente, puis proposer des directions de poses et de styles."
        delivery = "Toujours vérifier visuellement l'identité après chaque génération avant une livraison client."
    else:
        stage1_title = "Step 1 · Same-person expression character sheet"
        stage1_desc = "Generate a clean 4×3 board of the same person with multiple expressions while keeping the facial identity locked."
        stage1_intent = "Same-person identity and expression character sheet"
        stage2_title = "Step 2 · Full-body pose and wardrobe directions"
        stage2_desc = "After identity review, propose six full-body pose and outfit directions. These are creative directions to review, not a measured reconstruction of the person's body."
        stage2_intent = "Full-body pose, posture and wardrobe direction board"
        summary = "Build a coherent visual persona from the face first, then expand it into pose and styling directions."
        delivery = "Always review likeness visually after each generation before client delivery."

    stage1_prompt = (
        f"{base_prompt} Create a clean professional 4x3 identity character sheet of the exact same person from the uploaded face reference. "
        "Show twelve distinct expressions: neutral, soft smile, broad smile, confident, surprised, curious, concerned, serious, focused, skeptical, thoughtful, and energetic. "
        "Use consistent hair, facial hair, face geometry, skin tone, apparent age and camera style in every panel. "
        "Head-and-shoulders framing, clean studio background, even lighting. Do not add captions, UI labels, score text, watermark, duplicated faces or drifting identity."
    )
    stage2_prompt = (
        f"{base_prompt} Create a clean professional six-panel full-body persona direction board using the same face identity from the uploaded reference. "
        "Propose six believable directions: casual standing, professional blazer, confident arms crossed, relaxed hands in pockets, side profile presentation, and modern smart-casual pose. "
        "Keep the same face identity, apparent age, hair and facial-hair silhouette across panels. Use a clean neutral studio background. "
        "Treat body, outfits and poses as styling proposals for review; do not claim measured body reconstruction. No captions, no UI labels, no watermark, no distorted anatomy."
    )

    stages = [
        PersonaWorkflowStage(order=1, key="identity_expression_board", title=stage1_title, description=stage1_desc, output_intent=stage1_intent, prompt=stage1_prompt, width=1536, height=1536, strength=0.30),
        PersonaWorkflowStage(order=2, key="pose_style_direction", title=stage2_title, description=stage2_desc, output_intent=stage2_intent, prompt=stage2_prompt, width=1536, height=1024, strength=0.35),
    ]
    return PersonaWorkflow(
        enabled=not blocked,
        status="blocked" if blocked else "ready",
        title="Neural Camera Persona Workflow",
        summary=summary,
        identity_source="uploaded_face_reference",
        stages=stages,
        delivery_note=delivery,
    )

def build_generation_gate_summary(face_profile: dict[str, Any], *, lang: str) -> str:
    subject = face_profile.get("subject_analysis") or {}
    real = face_profile.get("real_face_analysis") or {}
    assessment = face_profile.get("production_assessment") or {}
    pos = real.get("face_position") or {}
    coverage = subject.get("primary_subject_coverage_percent", pos.get("coverage_percent"))
    quality = subject.get("reference_quality_score", assessment.get("generation_confidence_score"))
    preservation = subject.get("subject_preservation_score", assessment.get("identity_reliability_score"))
    subject_type = subject.get("subject_type") or "unknown"
    gate = "blocked" if subject.get("hard_block_generation") else "allowed_with_review" if (subject.get("risks") or assessment.get("warning_level") in {"medium", "high"}) else "allowed"
    if lang == "fr":
        return f"Sujet {subject_type}. Gate {gate}. Couverture {coverage}% · préservation {preservation}/100 · qualité {quality}/100."
    return f"Subject {subject_type}. Gate {gate}. Coverage {coverage}% · preservation {preservation}/100 · quality {quality}/100."


def build_action_warning(face_profile: dict[str, Any], *, lang: str) -> str:
    subject = face_profile.get("subject_analysis") or {}
    assessment = face_profile.get("production_assessment") or {}
    recommendations = assessment.get("recommendations") or subject.get("recommendations") or []
    first = recommendations[0] if recommendations else (
        "Reference is ready for identity-preserving generation." if lang == "en" else "La référence est prête pour une génération avec identité verrouillée."
    )
    if subject.get("hard_block_generation"):
        if lang == "fr":
            return f"Référence bloquée pour identity-lock: recadre ou reprends la photo avant génération. {first}"
        return f"Reference blocked for identity lock: crop closer or retake before generating. {first}"
    if lang == "fr":
        return f"Référence utilisable: génération autorisée avec auto-crop et revue du résultat. {first}"
    return f"Reference usable: generation is allowed with auto-crop and result review. {first}"


def apply_user_alignment_settings(
    face_profile: dict[str, Any],
    *,
    size: str,
    orientation: str,
    lighting: str,
    temperature: str,
    contrast: str,
) -> dict[str, Any]:
    """Make the visible face-alignment panel reflect user choices, not hidden defaults."""
    original_size = face_profile.get("image_size")
    if original_size and original_size != size:
        face_profile["source_image_size"] = original_size

    face_profile["image_size"] = size
    face_profile["output_size"] = size
    face_profile["orientation"] = orientation
    face_profile["lighting"] = lighting
    face_profile["color_temperature"] = temperature
    face_profile["contrast"] = contrast
    face_profile["user_selected_settings"] = {
        "size": size,
        "orientation": orientation,
        "lighting": lighting,
        "temperature": temperature,
        "contrast": contrast,
    }
    return face_profile


def build_user_aligned_prompt(face_profile: dict[str, Any], *, lang: str, settings: dict[str, str]) -> str:
    """Build a concise identity-lock prompt from face analysis plus user-selected controls."""
    framing = face_profile.get("framing") or "reference composition"
    size = settings["size"]
    orientation = settings["orientation"]
    lighting = settings["lighting"]
    temperature = settings["temperature"]
    contrast = settings["contrast"]
    detected_en = face_profile.get("detected_face_prompt_en") or "Use the visible face geometry as the identity reference."
    detected_fr = face_profile.get("detected_face_prompt_fr") or "Utilise la géométrie visible du visage comme référence d'identité."
    real = face_profile.get("real_face_analysis") or {}
    identity_score = real.get("identity_reliability_score")
    generation_score = real.get("generation_confidence_score")

    if lang == "fr":
        return (
            "Utilise l'image importée comme référence principale d'identité et de pose. "
            f"{detected_fr} "
            f"Cadrage {framing}. Sortie {size}, orientation {orientation}. "
            f"Lumière {lighting}, température {temperature}, contraste {contrast}. "
            f"Fiabilité identité {identity_score}/100, confiance génération {generation_score}/100. "
            "Préserver la même personne: proportions du visage, mâchoire, nez, yeux, teint, cheveux ou barbe si visibles. "
            "Préserver exactement la présentation de genre visible dans la référence; si la référence paraît masculine, garder des traits masculins, et si elle paraît féminine, garder des traits féminins. "
            "Ne pas embellir en changeant d'identité, ne pas féminiser ni masculiniser, ne pas inventer une autre personne. "
            "Rendu réaliste, naturel, anatomie stable, détails propres, arrière-plan cohérent."
        )

    return (
        "Use the uploaded reference image as the primary identity and pose reference. "
        f"{detected_en} "
        f"Framing {framing}. Output {size}, orientation {orientation}. "
        f"Lighting {lighting}, {temperature} color temperature, {contrast}. "
        f"Identity reliability {identity_score}/100, generation confidence {generation_score}/100. "
        "Preserve the same person: facial proportions, jaw, nose, eye spacing, skin tone, hair or facial-hair silhouette if visible. "
        "Preserve the apparent gender presentation exactly as seen in the reference; if the source appears male, keep masculine traits, and if the source appears female, keep feminine traits. "
        "Do not beautify into a different person, do not feminize or masculinize the subject, and do not invent a different identity. "
        "Realistic natural output, stable anatomy, clean details, coherent background."
    )


def summarize_real_analysis(real: dict[str, Any], *, lang: str) -> str:
    if not real.get("face_detected"):
        return (
            "aucun visage détecté avec confiance; utilise une photo plus claire/frontale"
            if lang == "fr"
            else "no confident face detected; use a clearer/front-facing photo"
        )
    pos = real.get("face_position") or {}
    pose = real.get("pose_estimate") or {}
    quality = real.get("face_region_quality") or {}
    if lang == "fr":
        return (
            f"{real.get('face_count', 1)} visage(s), couverture {pos.get('coverage_percent')}%, "
            f"décalage x {pos.get('center_offset_x_percent')}% / y {pos.get('center_offset_y_percent')}%, "
            f"pose {pose.get('yaw_label')}, ligne des yeux {pose.get('eye_line')}, roll {pose.get('roll_degrees')}°, "
            f"lumière {quality.get('lighting_label')}, netteté {quality.get('sharpness_label')}, "
            f"score {real.get('alignment_score')}/100"
        )
    return (
        f"{real.get('face_count', 1)} face(s), coverage {pos.get('coverage_percent')}%, "
        f"offset x {pos.get('center_offset_x_percent')}% / y {pos.get('center_offset_y_percent')}%, "
        f"pose {pose.get('yaw_label')}, eye-line {pose.get('eye_line')}, roll {pose.get('roll_degrees')}°, "
        f"lighting {quality.get('lighting_label')}, sharpness {quality.get('sharpness_label')}, "
        f"alignment {real.get('alignment_score')}/100, identity {real.get('identity_reliability_score')}/100, generation {real.get('generation_confidence_score')}/100"
    )


@router.get("/health")
async def vision_health():
    return {
        "ok": True,
        "service": "vision_face_alignment_user_settings_readable",
        "code_version": CODE_VERSION,
        "languages": ["en", "fr"],
        "features": [
            "neural_camera_analysis",
            "real_local_face_detection",
            "vendored_face_alignment_master_source",
            "optional_68_point_fan_landmarks_from_face_alignment_master",
            "face_box_eye_pose_lighting_sharpness_analysis",
            "face_alignment_prompt",
            "user_selected_size_orientation_lighting_temperature_contrast",
            "prompt_generation",
            "two_stage_persona_workflow",
            "same_person_expression_board_prompt",
            "full_body_pose_style_direction_prompt",
            "product_object_background_small_object_analysis",
            "full_body_reference_heuristics",
            "dark_blur_far_subject_detection",
            "optional_ollama_vision_semantic_layer",
        ],
    }


@router.post("/analyze", response_model=MagicLensAnalyzeResult)
@limiter.limit("15/minute")
async def analyze_magic_lens_image(
    request: Request,
    image: UploadFile = File(...),
    hint: str = Form(""),
    lang: str = Form("auto"),
    alignment_size: str = Form("1280x720"),
    alignment_orientation: str = Form("landscape"),
    alignment_lighting: str = Form("balanced"),
    alignment_temperature: str = Form("neutral"),
    alignment_contrast: str = Form("medium contrast"),
    current_user_id: int = Depends(get_current_user_id),
):
    _ = current_user_id
    final_lang = lang_of(lang, hint)
    upload_dir = backend_root() / "static" / "magic_lens"
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(image.filename or "image.jpg").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    name = f"magic_lens_{uuid.uuid4().hex}{suffix}"
    path = upload_dir / name
    if image.content_type and image.content_type not in settings.ALLOWED_IMAGE_MIME:
        raise HTTPException(status_code=415, detail="Unsupported image type. Use PNG, JPEG or WEBP.")
    content = await image.read()
    max_bytes = int(settings.MAX_UPLOAD_MB) * 1024 * 1024
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded image is empty.")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_UPLOAD_MB}MB)")
    path.write_bytes(content)
    try:
        with Image.open(path) as probe:
            probe.verify()
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid image.")
    image_url = f"/magic_lens/{name}"

    selected_settings = {
        "size": clean_choice(alignment_size, ALLOWED_SIZES, "1280x720"),
        "orientation": clean_choice(alignment_orientation, ALLOWED_ORIENTATIONS, "landscape"),
        "lighting": clean_choice(alignment_lighting, ALLOWED_LIGHTING, "balanced"),
        "temperature": clean_choice(alignment_temperature, ALLOWED_TEMPERATURES, "neutral"),
        "contrast": clean_choice(alignment_contrast, ALLOWED_CONTRASTS, "medium contrast"),
    }

    negative = (
        "low quality, blurry, noisy, artifacts, watermark, distorted anatomy, bad face alignment, "
        "warped eyes, asymmetric mouth, extra facial parts, plastic skin, unreadable text, bad composition"
    )
    base_hint = (hint or "the uploaded reference image").strip()

    try:
        profile = analyze_face_reference(path, base_hint)
        face_profile = profile.dict()
    except Exception as exc:
        face_profile = {"error": str(exc)}

    face_profile = apply_user_alignment_settings(face_profile, **selected_settings)
    real_analysis = face_profile.get("real_face_analysis") or {}

    crop_path = create_primary_face_crop(path, real_analysis.get("primary_face_bbox"))
    if crop_path:
        face_profile["primary_face_crop_url"] = f"/magic_lens/{crop_path.name}"

    subject_analysis = analyze_universal_subject(path, base_hint, real_analysis)
    semantic_vision = await analyze_optional_semantic_vision(path, base_hint)
    subject_analysis = merge_semantic_vision(subject_analysis, semantic_vision)
    subject_crop_path = create_bbox_crop(path, subject_analysis.get("primary_subject_bbox"), suffix="subjectcrop")
    if subject_crop_path:
        subject_analysis["primary_subject_crop_url"] = f"/magic_lens/{subject_crop_path.name}"
        face_profile["primary_subject_crop_url"] = f"/magic_lens/{subject_crop_path.name}"

    face_profile["subject_analysis"] = subject_analysis
    subject_cov = _num_or_none(subject_analysis.get("primary_subject_coverage_percent")) or 0.0
    subject_quality = _num_or_none(subject_analysis.get("reference_quality_score")) or 0.0
    subject_preservation = _num_or_none(subject_analysis.get("subject_preservation_score")) or 0.0
    prefer_full_frame_person = (
        subject_analysis.get("subject_type") == "person_face"
        and (subject_cov >= 14 or (subject_quality >= 60 and subject_preservation >= 60))
    )
    face_profile["source_recommendation"] = {
        "default": "full_frame" if prefer_full_frame_person else "subject_crop",
        "reason": "Use the DJI/camera full frame for person identity when it is usable; use crop for tiny faces or product/object isolation.",
        "recommended_strength": subject_lock_strength(subject_analysis),
    }
    assessment = face_profile.get("production_assessment") or {}
    subject_risks = subject_analysis.get("risks") or []
    subject_recommendations = subject_analysis.get("recommendations") or []
    subject_blocked = bool(subject_analysis.get("hard_block_generation"))
    subject_is_person = subject_analysis.get("subject_type") == "person_face"

    if subject_is_person and subject_blocked:
        assessment.update({
            "readiness": "retake_or_crop_closer",
            "headline": "Retake or crop closer before identity-lock generation",
            "can_generate": False,
            "hard_block_generation": True,
            "warning_level": "high",
        })
    elif subject_risks or assessment.get("warning_level") in {"medium", "high"}:
        assessment.update({
            "readiness": assessment.get("readiness") or "usable_with_auto_crop_review",
            "headline": assessment.get("headline") or "Usable with auto-crop and result review",
            "can_generate": True,
            "hard_block_generation": False,
            "warning_level": "medium",
        })

    assessment["risks"] = list(dict.fromkeys([*subject_risks, *(assessment.get("risks") or [])]))[:6]
    assessment["recommendations"] = list(dict.fromkeys([*subject_recommendations, *(assessment.get("recommendations") or [])]))[:6]
    face_profile["production_assessment"] = assessment

    face_profile["generation_gate"] = {
        "allowed": not subject_blocked,
        "status": "blocked" if subject_blocked else "allowed_with_review" if subject_risks else "allowed",
        "subject_type": subject_analysis.get("subject_type"),
        "reference_quality_score": subject_analysis.get("reference_quality_score"),
        "subject_preservation_score": subject_analysis.get("subject_preservation_score"),
        "subject_coverage_percent": subject_analysis.get("primary_subject_coverage_percent"),
        "required_action": "retake_or_crop_closer" if subject_blocked else "auto_crop_or_review" if subject_risks else "none",
    }
    face_prompt = build_universal_subject_prompt(face_profile, lang=final_lang, settings=selected_settings, base_hint=base_hint)
    width, height = parse_size(selected_settings["size"])
    face_profile["generation_gate_summary_en"] = build_generation_gate_summary(face_profile, lang="en")
    face_profile["generation_gate_summary_fr"] = build_generation_gate_summary(face_profile, lang="fr")
    face_profile["generation_warning_en"] = build_action_warning(face_profile, lang="en")
    face_profile["generation_warning_fr"] = build_action_warning(face_profile, lang="fr")
    persona_workflow = build_persona_workflow(face_profile, lang=final_lang, base_prompt=face_prompt)

    if final_lang == "fr":
        real = face_profile.get("real_face_analysis") or {}
        real_summary = face_profile.get("readable_summary_fr") or summarize_real_analysis(real, lang="fr")
        assessment = face_profile.get("production_assessment") or {}
        risks = assessment.get("risks") or []
        recommendations = assessment.get("recommendations") or []
        risk_text = "\n".join([f"- {item}" for item in risks[:3]]) or "- Aucun risque majeur détecté"
        reco_text = "\n".join([f"- {item}" for item in recommendations[:3]]) or "- Aucune action requise"
        subject = face_profile.get("subject_analysis") or {}
        subject_summary = f"Type sujet: {subject.get('subject_type')} · qualité {subject.get('reference_quality_score')}/100 · préservation {subject.get('subject_preservation_score')}/100 · gate {'bloqué' if subject.get('hard_block_generation') else 'autorisé/revue'}"
        desc = (
            "Image reçue. Analyse locale terminée avec un format de restitution production.\n\n"
            f"Résumé exécutif : {real_summary}\n"
            f"{subject_summary}\n\n"
            f"Risques principaux :\n{risk_text}\n\n"
            f"Actions recommandées :\n{reco_text}\n\n"
            "Le prompt détaillé reste séparé plus bas pour garder le panneau lisible et professionnel."
        )
        prompt = face_prompt
        suggestions = []
        if persona_workflow and persona_workflow.enabled:
            suggestions.extend([
                MagicLensSuggestion(action="generate_image", title=stage.title, description=stage.description, prompt=stage.prompt, negative_prompt=negative, width=stage.width, height=stage.height, workflow_stage=stage.key, generation_mode=stage.generation_mode, strength=stage.strength, layout=stage.output_intent)
                for stage in persona_workflow.stages
            ])
        elif not subject.get("hard_block_generation") and subject.get("can_generate"):
            suggestions.append(MagicLensSuggestion(action="generate_image", title="Générer image subject-lock", prompt=prompt, negative_prompt=negative, width=width, height=height, workflow_stage="subject_lock_prompt", generation_mode="auto", strength=subject_lock_strength(subject)))
        suggestions.append(MagicLensSuggestion(action="make_prompt", title="Rapport / prompt subject-lock", prompt=prompt, negative_prompt=negative, workflow_stage="subject_lock_prompt"))
    else:
        real = face_profile.get("real_face_analysis") or {}
        real_summary = face_profile.get("readable_summary_en") or summarize_real_analysis(real, lang="en")
        assessment = face_profile.get("production_assessment") or {}
        risks = assessment.get("risks") or []
        recommendations = assessment.get("recommendations") or []
        risk_text = "\n".join([f"- {item}" for item in risks[:3]]) or "- No major risk flags detected"
        reco_text = "\n".join([f"- {item}" for item in recommendations[:3]]) or "- No corrective action needed"
        subject = face_profile.get("subject_analysis") or {}
        subject_summary = f"Subject type: {subject.get('subject_type')} · quality {subject.get('reference_quality_score')}/100 · preservation {subject.get('subject_preservation_score')}/100 · gate {'blocked' if subject.get('hard_block_generation') else 'allowed'}"
        desc = (
            "Image received. Local subject analysis completed in a production-style report.\n\n"
            f"Executive summary: {real_summary}\n"
            f"{subject_summary}\n\n"
            f"Primary risks:\n{risk_text}\n\n"
            f"Recommended actions:\n{reco_text}\n\n"
            "The detailed prompt is kept separately below so the panel stays readable and professional."
        )
        prompt = face_prompt
        suggestions = []
        if persona_workflow and persona_workflow.enabled:
            suggestions.extend([
                MagicLensSuggestion(action="generate_image", title=stage.title, description=stage.description, prompt=stage.prompt, negative_prompt=negative, width=stage.width, height=stage.height, workflow_stage=stage.key, generation_mode=stage.generation_mode, strength=stage.strength, layout=stage.output_intent)
                for stage in persona_workflow.stages
            ])
        elif not subject.get("hard_block_generation") and subject.get("can_generate"):
            suggestions.append(MagicLensSuggestion(action="generate_image", title="Generate subject-locked image", prompt=prompt, negative_prompt=negative, width=width, height=height, workflow_stage="subject_lock_prompt", generation_mode="auto", strength=subject_lock_strength(subject)))
        suggestions.append(MagicLensSuggestion(action="make_prompt", title="Subject-lock report / prompt", prompt=prompt, negative_prompt=negative, workflow_stage="subject_lock_prompt"))

    return MagicLensAnalyzeResult(
        success=True,
        provider="local_real_face_analyzer",
        image_url=image_url,
        description=desc,
        detected_language=final_lang,
        suggestions=suggestions,
        face_profile=face_profile,
        face_prompt=face_prompt,
        persona_workflow=persona_workflow,
    )
