"""Generation endpoints.

Image generation is executed asynchronously via Celery to keep the API responsive. Legacy video routes are retained only to return a clear disabled response.
"""

from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update
from typing import Optional
import logging
import os
import uuid
import re
from PIL import Image

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.config import settings
from app.core import cache
from app.models.generation import Generation
from app.models.credit_transaction import CreditTransaction
from app.schemas.generation import (
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResponse,
    GenerationListResponse,
)
from app.services.credit_service import credit_service
from app.services.prompt_tools import validate_prompt, enhance_prompt
from app.core.rate_limit import limiter
from app.services.generation_guard import evaluate_prompt_subject_lock_gate
from app.services.reference_crop import create_subject_reference_crop
from app.services.visual_understanding_service import analyze_reference_with_vision
from app.services.commercial_compositor import commercial_source_quality_report
from app.services.reference_prompt_policy import append_gate_form_metadata, validate_reference_prompt_actionable
from app.services.reference_modes import (
    attach_flyer_overlay_marker,
    attach_identity_board_marker,
    attach_reference_mode_marker,
    attach_reference_subject_type_marker,
    attach_vision_prompt_pack_marker,
    effective_reference_strength,
    resolve_reference_mode,
    normalize_reference_mode,
    should_use_source_lock_composite,
)

router = APIRouter()
logger = logging.getLogger(__name__)

VIDEO_FEATURE_DISABLED_DETAIL = "Video generation is disabled in this production build. Use Image-to-Image instead."


def _raise_video_disabled() -> None:
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=VIDEO_FEATURE_DISABLED_DETAIL)



def _normalized_generation_mode(mode: str | None) -> str:
    normalized = normalize_reference_mode(mode)
    allowed = {
        "auto",
        "person_identity",
        "product_ad",
        "flyer_poster",
        "background_replace",
        "creative_image",
        "text_only",
    }
    if normalized not in allowed:
        raise HTTPException(status_code=422, detail="Invalid generation_mode")
    return normalized


def _strict_mode_enabled() -> bool:
    return str(getattr(settings, "COMFY_STRICT_WORKFLOW_MODE", True)).lower() in {"1", "true", "yes", "on"}


def _round8(value: int) -> int:
    return max(8, (int(value) // 8) * 8)


def _image_effective_dimensions(requested_width: int, requested_height: int) -> tuple[int, int]:
    """Return the real dimensions that ComfyUI will receive.

    Production rule: if the UI exposes a size, the backend must apply that exact
    size to the ComfyUI EmptyLatentImage node (rounded to multiples of 64 for
    ComfyUI stability). We no longer silently replace UI values with 640x896.
    """
    return _round8(requested_width), _round8(requested_height)


def _parse_image_size(value: str | None, *, default: tuple[int, int] = (1280, 720)) -> tuple[int, int]:
    """Parse a strict WIDTHxHEIGHT form value and reject resource-exhaustion sizes."""

    if not value:
        return default
    match = re.fullmatch(r"(\d{2,4})x(\d{2,4})", value.strip().lower())
    if not match:
        raise HTTPException(status_code=422, detail="Invalid size format. Expected like 1280x720")
    width, height = int(match.group(1)), int(match.group(2))
    if not (256 <= width <= 2048 and 256 <= height <= 2048):
        raise HTTPException(status_code=422, detail="Image dimensions must be between 256 and 2048 pixels")
    return width, height


def _video_effective_parameters(requested_width: int, requested_height: int, requested_duration: int) -> tuple[int, int, int]:
    """Return the real width/height/duration requested by the UI.

    The ComfyUI worker converts duration to a valid LTXV frame count. The DB keeps
    the same duration shown in the UI, so History/Preview metadata never lies.
    """
    return _round8(requested_width), _round8(requested_height), int(requested_duration)


async def _enqueue_generation(generation_id: int) -> None:
    """Queue or run a generation safely.

    Local mode uses CELERY_TASK_ALWAYS_EAGER=true and usually has no Redis/Celery
    worker. Calling the Celery task eagerly from an async FastAPI endpoint would
    call asyncio.run() inside the running event loop. Instead, local mode awaits
    the async processor directly. Real queue mode still uses Celery .delay().
    """
    from app.workers.tasks import process_generation, process_generation_async

    if settings.CELERY_TASK_ALWAYS_EAGER:
        await process_generation_async(generation_id)
        return

    try:
        process_generation.delay(generation_id)
    except Exception as exc:
        # In strict production mode a missing worker/broker must fail fast.
        # Running a potentially long GPU job inline would block the HTTP worker
        # and hide an infrastructure outage. Local development keeps the
        # convenient inline fallback when Redis is not required.
        if settings.REQUIRE_REDIS:
            raise RuntimeError("Generation queue is unavailable") from exc
        logger.warning(
            "Celery queue unavailable; processing generation %s inline in local mode: %s",
            generation_id,
            exc,
            exc_info=True,
        )
        await process_generation_async(generation_id)


async def _enqueue_or_refund(db: AsyncSession, generation: Generation) -> None:
    """Dispatch a committed job or mark it failed and refund its wallet debit."""

    try:
        await _enqueue_generation(generation.id)
        # Queued/completed jobs change overview and model-comparison counts.
        await cache.invalidate_admin_caches()
    except Exception as exc:
        await db.refresh(generation)
        if generation.status not in {"completed", "failed"}:
            generation.status = "failed"
            generation.error_message = "Generation queue is unavailable. Credits were refunded."
            if int(generation.credits_used or 0) > 0:
                await credit_service.add_credits(
                    db,
                    generation.user_id,
                    int(generation.credits_used or 0),
                    transaction_type="refund",
                    description=f"Refund for queue failure on {generation.generation_type} generation #{generation.id}",
                    generation_id=generation.id,
                )
            await db.commit()
            await cache.invalidate_admin_caches()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation queue is unavailable. Credits were refunded; retry after Redis/Celery is healthy.",
        ) from exc


def _validate_or_422(prompt: str) -> None:
    """Validate prompt and raise HTTP 422 on errors."""
    try:
        validate_prompt(prompt)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _validate_reference_prompt_or_422(prompt: str, *, mode: str) -> None:
    """Require an actionable description when a reference image is used."""
    _validate_or_422(prompt)
    try:
        validate_reference_prompt_actionable(prompt, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _is_person_identity_reference(mode: str | None, subject_type: str | None) -> bool:
    return (mode or "").strip().lower() == "person_identity" or (subject_type or "").strip().lower() in {
        "person", "person_face", "person_full", "person_full_body"
    }


def _coerce_person_identity_subject(mode: str | None, subject_type: str | None) -> str:
    """Dedicated Person / Identity must stay in the person safety path.

    Optional semantic vision can be noisy on close-up webcam/DJI frames.  If the
    user selected person_identity, never pass pet/product/object to the worker;
    that disables the identity-specific prompt and negative prompt.
    """
    stype = (subject_type or "unknown").strip().lower()
    if (mode or "").strip().lower() != "person_identity":
        return stype
    if stype in {"person_full", "person_full_body"}:
        return "person_full_body"
    return "person_face"


def _prompt_requires_reference_image(prompt: str) -> bool:
    lowered = (prompt or "").strip().lower()
    if not lowered:
        return False
    markers = [
        "uploaded reference image",
        "uploaded image as the primary",
        "use the uploaded as the primary",
        "same person from the reference",
        "preserve the exact same person",
        "primary identity source",
        "source-lock",
        "subject-lock",
    ]
    return any(marker in lowered for marker in markers)


def _raise_reference_required_for_text2img(endpoint_required: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error_code": "REFERENCE_REQUIRED_FOR_THIS_PROMPT",
            "message": "This prompt requires a reference image. Use the reference-based endpoint instead of the text-only endpoint.",
            "required_action": "retry_with_reference_image",
            "details": {
                "endpoint_required": endpoint_required,
            },
        },
    )


def _enforce_source_lock_prompt_gate(prompt: str, *, subject_lock: bool = False) -> None:
    gate = evaluate_prompt_subject_lock_gate(prompt, subject_lock=subject_lock)
    if not gate.allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=gate.as_http_detail())


def _append_gate_form_metadata(
    prompt: str,
    *,
    subject_type: str | None = None,
    gate_status: str | None = None,
    reference_quality_score: float | None = None,
    subject_preservation_score: float | None = None,
    subject_coverage_percent: float | None = None,
    identity_reliability_score: float | None = None,
    generation_confidence_score: float | None = None,
) -> str:
    """Compatibility wrapper around the lightweight multipart metadata helper."""
    return append_gate_form_metadata(
        prompt,
        subject_type=subject_type,
        gate_status=gate_status,
        reference_quality_score=reference_quality_score,
        subject_preservation_score=subject_preservation_score,
        subject_coverage_percent=subject_coverage_percent,
        identity_reliability_score=identity_reliability_score,
        generation_confidence_score=generation_confidence_score,
    )


def _source_reference_mode(mode: str | None, subject_lock: bool) -> bool:
    normalized = _normalized_generation_mode(mode)
    return bool(subject_lock) or normalized in {
        "auto",
        "person_identity",
        "product_ad",
        "flyer_poster",
        "background_replace",
        "creative_image",
    }


def _reference_mode_prompt(prompt: str, *, mode: str, subject_type: str, width: int, height: int) -> str:
    """Convert a user prompt into a source-locked production prompt.

    Important: this text goes to ComfyUI. It must not contain stale "gate"
    status text that could be parsed as a future blocker.
    """
    clean_prompt = (prompt or "").strip()
    mode = (mode or "auto").strip().lower()
    subject_type = (subject_type or "unknown").strip().lower()

    if subject_type == "person_face" or mode == "person_identity":
        prefix = (
            "Use the uploaded reference image as the primary identity source. "
            "Preserve the exact same person, face geometry, apparent gender presentation, skin tone, hair/facial-hair silhouette, jaw, nose, mouth, eye spacing and gaze direction. "
            "Keep visible shoulders, clothing, camera perspective and believable lighting. Do not create side-gaze, crossed eyes, a different expression, a lookalike, or beauty-filter plastic skin unless explicitly requested. "
        )
    elif mode == "background_replace":
        prefix = (
            "Use the uploaded reference image as the primary subject source. "
            "Preserve the exact subject/object, its edges, proportions, colors, texture and visible details. Replace only the background and scene context. "
        )
    elif mode in {"product_ad", "flyer_poster"}:
        prefix = (
            "Use the uploaded reference image as the primary product/subject source. "
            "Preserve the exact silhouette, proportions, material, colors, label/branding if visible, and key details. "
            "Do not redesign the product or invent a different object. Create a clean commercial advertising composition. "
        )
    elif subject_type in {"document", "document_or_poster"}:
        prefix = (
            "Use the uploaded reference image as the layout source. Preserve the document/poster structure and visible text as much as possible. "
        )
    else:
        prefix = (
            "Use the uploaded reference image as the primary visual source. Preserve the main subject, proportions, colors, material and visible details. "
        )

    suffix = f"Output {width}x{height}, landscape, balanced lighting, neutral color temperature, medium contrast, production-ready quality."
    return f"{prefix}{clean_prompt}. {suffix}".strip()


def _reference_negative_prompt(mode: str, subject_type: str, negative_prompt: str | None) -> str:
    base = (negative_prompt or "").strip()
    common = "blurry, low quality, distorted, artifacts, watermark, bad text, duplicate subject, wrong proportions"
    if subject_type == "person_face" or (mode or "").lower() == "person_identity":
        extra = "different person, identity drift, changed gender, changed age, warped eyes, asymmetric mouth, plastic skin, deformed face"
    else:
        extra = "different product, redesigned object, changed logo, wrong label, melted edges, broken geometry, unreadable branding"
    return ", ".join(part for part in [base, extra, common] if part)


async def _analyze_source_reference(input_path: str, prompt: str, mode: str) -> dict:
    """Run production image understanding with Ollama Vision + safe fallback."""
    try:
        return await analyze_reference_with_vision(input_path, prompt, mode)
    except Exception as exc:  # pragma: no cover - best-effort analyzer
        logger.warning("Vision reference analysis failed: %s", exc, exc_info=True)
        return {
            "subject_type": "unknown",
            "resolved_generation_mode": "creative_image",
            "primary_subject_detected": True,
            "primary_subject_bbox": None,
            "primary_subject_coverage_percent": 50,
            "reference_quality_score": 70,
            "subject_preservation_score": 70,
            "hard_block_generation": False,
            "can_generate": True,
            "risks": ["Reference analyzer fallback was used."],
            "recommendations": ["Check the generated output before client delivery."],
            "vision_understanding": {
                "enabled": False,
                "used": False,
                "provider": None,
                "raw": None,
                "error": str(exc)[:500],
            },
        }

def _raise_reference_block(subject_analysis: dict, *, mode: str) -> None:
    risks = subject_analysis.get("risks") or []
    recommendations = subject_analysis.get("recommendations") or []
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error_code": "REFERENCE_NOT_READY_FOR_SOURCE_LOCK",
            "message": "Generation blocked because the uploaded reference is not production-ready for this mode.",
            "required_action": "retake_or_crop_closer",
            "details": {
                "generation_mode": mode,
                "subject_type": subject_analysis.get("subject_type"),
                "coverage": subject_analysis.get("primary_subject_coverage_percent"),
                "reference_quality_score": subject_analysis.get("reference_quality_score"),
                "subject_preservation_score": subject_analysis.get("subject_preservation_score"),
                "risks": risks,
                "recommendations": recommendations,
            },
        },
    )


async def _save_upload_to_tmp(upload: UploadFile) -> str:
    """Persist an uploaded file to a local temp path.

    The Celery worker reads this path to send the input image to the provider.
    """
    tmp_dir = os.path.join("/tmp", "ai_studio_pro", "uploads")
    os.makedirs(tmp_dir, exist_ok=True)

    # Validate the declared MIME and the actual image bytes. A forged MIME must
    # never reach face analysis or ComfyUI.
    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in settings.ALLOWED_IMAGE_MIME:
        raise HTTPException(status_code=415, detail="Unsupported image type")

    data = await upload.read()
    max_bytes = int(settings.MAX_UPLOAD_MB) * 1024 * 1024
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded image is empty")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_UPLOAD_MB}MB)")

    # Keep provider uploads deterministic and avoid trusting a user-controlled
    # filename extension. Pillow verifies file structure before persistence.
    from io import BytesIO
    try:
        probe = Image.open(BytesIO(data))
        width, height = int(probe.width), int(probe.height)
        if (
            width <= 0
            or height <= 0
            or width > int(settings.MAX_IMAGE_DIMENSION)
            or height > int(settings.MAX_IMAGE_DIMENSION)
            or width * height > int(settings.MAX_IMAGE_PIXELS)
        ):
            raise HTTPException(status_code=422, detail="Uploaded image dimensions are too large")
        probe.verify()
        fmt = (probe.format or "PNG").upper()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid image") from exc

    extensions = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
    ext = extensions.get(fmt)
    if not ext:
        raise HTTPException(status_code=415, detail="Unsupported image encoding")
    filename = f"{uuid.uuid4().hex}{ext}"
    out_path = os.path.join(tmp_dir, filename)
    with open(out_path, "wb") as f:
        f.write(data)
    return out_path


@router.post("/images", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def generate_image(
    request: Request,
    payload: ImageGenerationRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate an image from text prompt"""

    _validate_or_422(payload.prompt)
    if _prompt_requires_reference_image(payload.prompt):
        _raise_reference_required_for_text2img("/api/v1/generations/image/img2img")
    _enforce_source_lock_prompt_gate(payload.prompt, subject_lock=False)
    # Store raw user prompt. The AI service applies the correct image prompt engine
    # at execution time. Pre-enhancing here breaks flyer text extraction.
    effective_prompt = payload.prompt
    effective_negative = payload.negative_prompt or ""

    # Check credits
    has_credits = await credit_service.has_sufficient_credits(
        db, current_user_id, settings.CREDIT_COST_IMAGE
    )
    
    
    if not has_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription."
        )
    
    # Create generation record with the real ComfyUI dimensions.
    effective_width, effective_height = _image_effective_dimensions(payload.width, payload.height)

    generation = Generation(
        user_id=current_user_id,
        generation_type="image",
        prompt=effective_prompt,
        negative_prompt=effective_negative,
        width=effective_width,
        height=effective_height,
        style=payload.style if payload.style else None,
        status="queued",
        credits_used=settings.CREDIT_COST_IMAGE,
        model_used=payload.model_id or "sdxl",
    )
    
    db.add(generation)
    await db.flush()
    
    # Deduct credits atomically. The earlier balance check is user-friendly,
    # but this check is the real protection against concurrent double-spend.
    tx = await credit_service.deduct_credits(
        db,
        current_user_id,
        settings.CREDIT_COST_IMAGE,
        description=f"Image generation #{generation.id}",
        generation_id=generation.id,
    )
    if tx is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription.",
        )
    
    # IMPORTANT: commit before enqueueing to avoid Celery reading a non-committed row
    await db.commit()
    await db.refresh(generation)

    # Enqueue background job
    await _enqueue_or_refund(db, generation)
    await db.refresh(generation)
    
    return GenerationResponse.model_validate(generation)


async def _generate_image_img2img_internal(
    request: Request,
    image: UploadFile,
    prompt: str,
    negative_prompt: str,
    strength: float,
    style: Optional[str],
    size: Optional[str],
    model_id: Optional[str],
    subject_lock: bool,
    gate_status: Optional[str],
    reference_quality_score: Optional[float],
    subject_preservation_score: Optional[float],
    subject_coverage_percent: Optional[float],
    subject_type: Optional[str],
    generation_mode: Optional[str],
    auto_crop: bool,
    apply_template_overlay: bool,
    identity_board: bool,
    current_user_id: int,
    db: AsyncSession,
    *,
    forced_mode: Optional[str] = None,
):
    """Shared implementation for generic and dedicated img2img endpoints."""

    mode = _normalized_generation_mode(forced_mode or generation_mode)
    _validate_reference_prompt_or_422(prompt, mode=mode)

    if strength < 0.1 or strength > 0.9:
        raise HTTPException(status_code=422, detail="strength must be between 0.1 and 0.9")

    width, height = _parse_image_size(size)
    width, height = _image_effective_dimensions(width, height)

    # Category design engine contract: Flyer / Poster is a portrait delivery asset.
    # Do not let the legacy UI 768x768 preset leak into the database, prompt pack,
    # source quality checks, or worker metadata. RTX 3060 6GB safe target.
    if mode == "flyer_poster":
        width, height = 832, 1024

    input_path = await _save_upload_to_tmp(image)
    source_locked = _source_reference_mode(mode, subject_lock=True if mode != "text_only" else subject_lock)
    subject_analysis: dict = {}
    prepared_input_path = input_path

    if source_locked:
        subject_analysis = await _analyze_source_reference(input_path, prompt, mode)
        server_subject_type = subject_analysis.get("subject_type") or subject_type or "unknown"
        effective_mode = str(subject_analysis.get("resolved_generation_mode") or resolve_reference_mode(mode, str(server_subject_type), prompt))
        # Dedicated routes force their own mode, except Auto Smart: Auto is a
        # classifier route and must keep the resolved mode returned by vision/
        # reference policy.  The old behavior forced "auto" back into the queue,
        # which weakened the prompt and could return a near-copy.
        if forced_mode and _normalized_generation_mode(forced_mode) != "auto":
            effective_mode = _normalized_generation_mode(forced_mode)

        # Final safety normalization after dedicated-route forcing.  This avoids
        # mode=person_identity subject=pet/product logs and keeps identity
        # generation in the correct prompt/guard path.
        server_subject_type = _coerce_person_identity_subject(effective_mode, str(server_subject_type))
        subject_analysis["subject_type"] = server_subject_type

        # If Auto Smart resolves to flyer_poster, force the same portrait contract too.
        if effective_mode == "flyer_poster":
            width, height = 832, 1024

        source_lock_required = should_use_source_lock_composite(effective_mode, str(server_subject_type))
        logger.info(
            "IMG2IMG_ROUTE endpoint_mode=%s requested=%s resolved=%s subject=%s source_lock=%s vision_used=%s",
            forced_mode or "generic",
            generation_mode,
            effective_mode,
            server_subject_type,
            source_lock_required,
            bool((subject_analysis.get("vision_understanding") or {}).get("used")),
        )
        server_gate_status = "allowed" if not subject_analysis.get("hard_block_generation") else "blocked"

        gate_prompt = _append_gate_form_metadata(
            prompt,
            subject_type=server_subject_type,
            gate_status=server_gate_status,
            reference_quality_score=subject_analysis.get("reference_quality_score", reference_quality_score),
            subject_preservation_score=subject_analysis.get("subject_preservation_score", subject_preservation_score),
            subject_coverage_percent=subject_analysis.get("primary_subject_coverage_percent", subject_coverage_percent),
            identity_reliability_score=subject_analysis.get("raw_identity_reliability_score"),
            generation_confidence_score=subject_analysis.get("raw_generation_confidence_score"),
        )
        server_gate = evaluate_prompt_subject_lock_gate(gate_prompt, subject_lock=True)
        if _is_person_identity_reference(effective_mode, str(server_subject_type)) and (
            subject_analysis.get("hard_block_generation") or not server_gate.allowed
        ):
            _raise_reference_block(subject_analysis, mode=effective_mode)

        full_frame_modes = {"product_ad", "flyer_poster", "background_replace", "creative_image"}
        keep_full_source = effective_mode in full_frame_modes or should_use_source_lock_composite(effective_mode, str(server_subject_type))
        should_auto_crop = bool(auto_crop and not keep_full_source and _is_person_identity_reference(effective_mode, str(server_subject_type)))
        logger.info(
            "IMG2IMG_PREP mode=%s subject=%s auto_crop_requested=%s keep_full_source=%s should_auto_crop=%s input=%s",
            effective_mode,
            server_subject_type,
            bool(auto_crop),
            keep_full_source,
            should_auto_crop,
            input_path,
        )
        if should_auto_crop:
            crop_path = create_subject_reference_crop(
                input_path,
                subject_analysis.get("primary_subject_bbox"),
                subject_type=str(server_subject_type),
                target_width=width,
                target_height=height,
            )
            if crop_path:
                prepared_input_path = crop_path

        prompt_for_queue = _reference_mode_prompt(
            prompt,
            mode=effective_mode,
            subject_type=str(server_subject_type),
            width=width,
            height=height,
        )
        prompt_for_queue = attach_vision_prompt_pack_marker(
            prompt_for_queue,
            subject_analysis.get("production_prompt_pack"),
        )
        logger.info(
            "VISION_PROMPT_PACK mode=%s subject=%s has_pack=%s",
            effective_mode,
            server_subject_type,
            bool(subject_analysis.get("production_prompt_pack")),
        )
        # Flyer / Poster should look like a flyer by default.  The overlay is
        # deterministic/readable, so we enable it for this mode even when the UI
        # toggle was left off.  Other modes remain untouched.
        prompt_for_queue = attach_flyer_overlay_marker(
            prompt_for_queue,
            enabled=bool(effective_mode == "flyer_poster"),
        )
        # FINAL PRO FIX: the report checkbox must not turn the final generation
        # into a diagnostic board. Neural Camera analysis is displayed in the UI;
        # the image-to-image endpoint must queue the final AI output only.
        if bool(identity_board and effective_mode == "person_identity"):
            logger.info("IDENTITY_REPORT_OPTION_RECEIVED_BUT_NOT_QUEUED_AS_FINAL_BOARD mode=%s subject=%s", effective_mode, server_subject_type)
        prompt_for_queue = attach_identity_board_marker(
            prompt_for_queue,
            enabled=False,
        )
        prompt_for_queue = attach_reference_subject_type_marker(prompt_for_queue, str(server_subject_type))
        effective_prompt = attach_reference_mode_marker(prompt_for_queue, effective_mode)
        effective_negative = _reference_negative_prompt(effective_mode, str(server_subject_type), negative_prompt)
        strength = effective_reference_strength(float(strength), effective_mode, str(server_subject_type))

        exact_source_commercial_mode = bool(
            effective_mode == "product_ad"
            or (
                effective_mode == "flyer_poster"
                and should_use_source_lock_composite(effective_mode, str(server_subject_type))
            )
        )
        logger.info(
            "IMG2IMG_COMMERCIAL_GATE mode=%s subject=%s exact_source=%s",
            effective_mode,
            server_subject_type,
            exact_source_commercial_mode,
        )
        if exact_source_commercial_mode:
            source_report = commercial_source_quality_report(
                input_path,
                width=width,
                height=height,
                flyer=effective_mode == "flyer_poster",
            )
            if not source_report.get("allowed"):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Commercial source image is not production-ready. "
                        f"{source_report.get('message') or 'Upload a sharper, larger product packshot.'}"
                    ),
                )
    else:
        _enforce_source_lock_prompt_gate(prompt, subject_lock=False)
        effective_prompt = prompt
        effective_negative = (negative_prompt or "").strip()

    cost = int(round(settings.CREDIT_COST_IMAGE * 1.2))

    has_credits = await credit_service.has_sufficient_credits(db, current_user_id, cost)
    if not has_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription.",
        )

    generation = Generation(
        user_id=current_user_id,
        generation_type="img2img",
        prompt=effective_prompt,
        negative_prompt=effective_negative,
        width=width,
        height=height,
        style=style,
        strength=strength,
        local_path=prepared_input_path,
        status="queued",
        credits_used=cost,
        model_used=model_id or "sdxl",
    )

    db.add(generation)
    await db.flush()

    tx = await credit_service.deduct_credits(
        db,
        current_user_id,
        cost,
        description=f"Image-to-image generation #{generation.id}",
        generation_id=generation.id,
    )
    if tx is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription.",
        )

    await db.commit()
    await db.refresh(generation)
    await _enqueue_or_refund(db, generation)
    await db.refresh(generation)

    return GenerationResponse.model_validate(generation)


@router.post("/image/img2img", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def generate_image_img2img(
    request: Request,
    image: UploadFile = File(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    strength: float = Form(0.22),
    style: Optional[str] = Form(None),
    size: Optional[str] = Form(None),
    model_id: Optional[str] = Form(None),
    subject_lock: bool = Form(False),
    gate_status: Optional[str] = Form(None),
    reference_quality_score: Optional[float] = Form(None),
    subject_preservation_score: Optional[float] = Form(None),
    subject_coverage_percent: Optional[float] = Form(None),
    subject_type: Optional[str] = Form(None),
    generation_mode: Optional[str] = Form("auto"),
    auto_crop: bool = Form(False),
    apply_template_overlay: bool = Form(False),
    identity_board: bool = Form(False),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generic Image → Image endpoint kept for backward compatibility."""
    return await _generate_image_img2img_internal(
        request=request,
        image=image,
        prompt=prompt,
        negative_prompt=negative_prompt,
        strength=strength,
        style=style,
        size=size,
        model_id=model_id,
        subject_lock=subject_lock,
        gate_status=gate_status,
        reference_quality_score=reference_quality_score,
        subject_preservation_score=subject_preservation_score,
        subject_coverage_percent=subject_coverage_percent,
        subject_type=subject_type,
        generation_mode=generation_mode,
        auto_crop=auto_crop,
        apply_template_overlay=apply_template_overlay,
        identity_board=identity_board,
        current_user_id=current_user_id,
        db=db,
        forced_mode=None,
    )




@router.post("/videos", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def generate_video(
    request: Request,
    payload: VideoGenerationRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Legacy video endpoint kept for compatibility but disabled in this image-first build."""

    _raise_video_disabled()

    _validate_or_422(payload.prompt)
    if _prompt_requires_reference_image(payload.prompt):
        _raise_reference_required_for_text2img("/api/v1/generations/video/img2vid")
    _enforce_source_lock_prompt_gate(payload.prompt, subject_lock=False)
    # Store raw user prompt. The AI service applies the video prompt engine at execution time.
    effective_prompt = payload.prompt
    effective_negative = payload.negative_prompt or ""

    # Credits rule: 4 seconds = CREDIT_COST_VIDEO; longer/shorter clips scale proportionally.
    video_cost = max(1, int(round(settings.CREDIT_COST_VIDEO * (int(payload.duration) / 4.0))))

    # Check credits
    has_credits = await credit_service.has_sufficient_credits(
        db, current_user_id, video_cost
    )
    
    if not has_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription."
        )
    
    # Create generation record with the real ComfyUI/LTXV parameters.
    effective_width, effective_height, effective_duration = _video_effective_parameters(
        payload.width, payload.height, payload.duration
    )

    generation = Generation(
        user_id=current_user_id,
        generation_type="video",
        prompt=effective_prompt,
        negative_prompt=effective_negative,
        width=effective_width,
        height=effective_height,
        duration=effective_duration,
        status="queued",
        credits_used=video_cost,
        model_used=payload.model_id or "runway-gen3",
    )
    
    db.add(generation)
    await db.flush()
    
    # Deduct credits atomically. The earlier balance check is user-friendly,
    # but this check is the real protection against concurrent double-spend.
    tx = await credit_service.deduct_credits(
        db,
        current_user_id,
        video_cost,
        description=f"Video generation #{generation.id}",
        generation_id=generation.id,
    )
    if tx is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription.",
        )
    
    await db.commit()
    await db.refresh(generation)
    # Enqueue background job
    await _enqueue_or_refund(db, generation)
    await db.refresh(generation)
    
    return GenerationResponse.model_validate(generation)


@router.post("/video/img2vid", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def generate_video_img2vid(
    request: Request,
    image: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    motion_strength: int = Form(50),
    duration: int = Form(4),
    resolution: str = Form("1024x576"),
    model_id: Optional[str] = Form(None),
    subject_lock: bool = Form(False),
    gate_status: Optional[str] = Form(None),
    reference_quality_score: Optional[float] = Form(None),
    subject_preservation_score: Optional[float] = Form(None),
    subject_coverage_percent: Optional[float] = Form(None),
    subject_type: Optional[str] = Form(None),
    generation_mode: Optional[str] = Form("auto"),
    auto_crop: bool = Form(False),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Image → Video generation (multipart/form-data)."""

    _raise_video_disabled()

    effective_prompt = ""
    if prompt:
        _validate_or_422(prompt)
        # Keep raw prompt for ComfyUI-match mode.  Enhancing img2vid prompts
        # was a hidden mismatch vs manual ComfyUI tests.
        if _strict_mode_enabled() and str(getattr(settings, "AI_PROVIDER", "")).lower() == "comfy":
            effective_prompt = prompt
        else:
            enh = enhance_prompt(prompt)
            effective_prompt = enh.prompt

    if motion_strength < 0 or motion_strength > 100:
        raise HTTPException(status_code=422, detail="motion_strength must be between 0 and 100")
    if duration < 2 or duration > 16:
        raise HTTPException(status_code=422, detail="duration must be between 2 and 16 seconds")

    # Keep the disabled legacy route future-safe: use the same strict parser as
    # image generation so malformed or resource-exhaustion dimensions never
    # become accepted silently if video support is enabled again later.
    width, height = _parse_image_size(resolution, default=(1024, 576))
    width, height, duration = _video_effective_parameters(width, height, duration)

    # Credits rule: same base as text-to-video, +20% for image conditioning.
    cost = max(1, int(round(settings.CREDIT_COST_VIDEO * (duration / 4.0) * 1.2)))

    has_credits = await credit_service.has_sufficient_credits(db, current_user_id, cost)
    if not has_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription.",
        )

    input_path = await _save_upload_to_tmp(image)
    mode = _normalized_generation_mode(generation_mode)
    if prompt:
        _validate_reference_prompt_or_422(prompt, mode=mode)

    prepared_input_path = input_path
    if _source_reference_mode(mode, subject_lock=True if mode != "text_only" else subject_lock):
        subject_analysis = await _analyze_source_reference(input_path, effective_prompt or prompt or "", mode)
        server_subject_type = subject_analysis.get("subject_type") or subject_type or "unknown"
        effective_mode = str(subject_analysis.get("resolved_generation_mode") or resolve_reference_mode(mode, str(server_subject_type), effective_prompt or prompt or ""))
        server_gate_status = "allowed" if not subject_analysis.get("hard_block_generation") else "blocked"
        gate_prompt = _append_gate_form_metadata(
            effective_prompt or prompt or "",
            subject_type=server_subject_type,
            gate_status=server_gate_status,
            reference_quality_score=subject_analysis.get("reference_quality_score", reference_quality_score),
            subject_preservation_score=subject_analysis.get("subject_preservation_score", subject_preservation_score),
            subject_coverage_percent=subject_analysis.get("primary_subject_coverage_percent", subject_coverage_percent),
            identity_reliability_score=subject_analysis.get("raw_identity_reliability_score"),
            generation_confidence_score=subject_analysis.get("raw_generation_confidence_score"),
        )
        # Apply the same strict person identity gate to image-to-video. Product
        # and object references keep their warning-only behavior.
        server_gate = evaluate_prompt_subject_lock_gate(gate_prompt, subject_lock=True)
        if _is_person_identity_reference(effective_mode, str(server_subject_type)) and (
            subject_analysis.get("hard_block_generation") or not server_gate.allowed
        ):
            _raise_reference_block(subject_analysis, mode=effective_mode)
        # Product ads and flyers need the full packshot and surrounding margins.
        # A tight detector crop made cans/bottles unnaturally narrow and starved
        # the creative workflow of composition space. Keep the original upload
        # for those commercial modes even when the UI sends auto_crop=true.
        # Preserve the complete source frame for every non-identity image mode.
        # The old object auto-crop could lock onto a small textured region (for
        # example a fish eye or scorpion claw) and upscale that crop to the whole
        # output canvas. Only person identity references may use auto-crop.
        full_frame_modes = {"product_ad", "flyer_poster", "background_replace", "creative_image"}
        keep_full_source = effective_mode in full_frame_modes or should_use_source_lock_composite(effective_mode, str(server_subject_type))
        should_auto_crop = bool(auto_crop and not keep_full_source and _is_person_identity_reference(effective_mode, str(server_subject_type)))
        logger.info(
            "IMG2IMG_PREP mode=%s subject=%s auto_crop_requested=%s keep_full_source=%s should_auto_crop=%s input=%s",
            effective_mode,
            server_subject_type,
            bool(auto_crop),
            keep_full_source,
            should_auto_crop,
            input_path,
        )
        if should_auto_crop:
            crop_path = create_subject_reference_crop(
                input_path,
                subject_analysis.get("primary_subject_bbox"),
                subject_type=str(server_subject_type),
                target_width=width,
                target_height=height,
            )
            if crop_path:
                prepared_input_path = crop_path
        effective_prompt = attach_reference_mode_marker(
            _reference_mode_prompt(
                effective_prompt or prompt or "",
                mode=effective_mode,
                subject_type=str(server_subject_type),
                width=width,
                height=height,
            ),
            effective_mode,
        )

    generation = Generation(
        user_id=current_user_id,
        generation_type="img2vid",
        prompt=effective_prompt,
        negative_prompt=None,
        width=width,
        height=height,
        duration=duration,
        motion_strength=motion_strength,
        local_path=prepared_input_path,
        status="queued",
        credits_used=cost,
        model_used=model_id or "runway-gen3",
    )

    db.add(generation)
    await db.flush()

    tx = await credit_service.deduct_credits(
        db,
        current_user_id,
        cost,
        description=f"Image-to-video generation #{generation.id}",
        generation_id=generation.id,
    )
    if tx is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Please purchase more credits or upgrade your subscription.",
        )

    await db.commit()
    await db.refresh(generation)
    await _enqueue_or_refund(db, generation)
    await db.refresh(generation)

    return GenerationResponse.model_validate(generation)


@router.get("/", response_model=GenerationListResponse)
async def list_generations(
    generation_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List user's generations"""
    
    # Build query
    query = select(Generation).where(Generation.user_id == current_user_id)
    
    if generation_type:
        if generation_type == "image":
            query = query.where(Generation.generation_type.in_(["image", "img2img"]))
        elif generation_type == "video":
            query = query.where(Generation.generation_type.in_(["video", "img2vid"]))
        else:
            query = query.where(Generation.generation_type == generation_type)
    
    if status:
        query = query.where(Generation.status == status)
    
        
    
    # Get total count (respect filters)
    from sqlalchemy import func
    count_query = select(func.count(Generation.id)).select_from(Generation).where(Generation.user_id == current_user_id)
    if generation_type:
        if generation_type == "image":
            count_query = count_query.where(Generation.generation_type.in_(["image", "img2img"]))
        elif generation_type == "video":
            count_query = count_query.where(Generation.generation_type.in_(["video", "img2vid"]))
        else:
            count_query = count_query.where(Generation.generation_type == generation_type)
    if status:
        count_query = count_query.where(Generation.status == status)
    count_result = await db.execute(count_query)
    total = int(count_result.scalar() or 0)
    
    # Get paginated results
    query = query.order_by(desc(Generation.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    generations = result.scalars().all()
    
    return GenerationListResponse(
        items=[GenerationResponse.model_validate(g) for g in generations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{generation_id}", response_model=GenerationResponse)
async def get_generation(
    generation_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific generation"""
    
    result = await db.execute(
        select(Generation)
        .where(Generation.id == generation_id)
        .where(Generation.user_id == current_user_id)
    )
    generation = result.scalar_one_or_none()
    
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found"
        )
    
    return GenerationResponse.model_validate(generation)


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generation(
    generation_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a generation"""
    
    result = await db.execute(
        select(Generation)
        .where(Generation.id == generation_id)
        .where(Generation.user_id == current_user_id)
    )
    generation = result.scalar_one_or_none()
    
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found"
        )
    
    # Preserve the immutable wallet ledger while detaching the deleted media row.
    # PostgreSQL otherwise rejects the delete because credit_transactions keeps
    # a foreign key to the generation.
    await db.execute(
        update(CreditTransaction)
        .where(CreditTransaction.generation_id == generation.id)
        .values(generation_id=None)
    )
    await db.delete(generation)
    await db.flush()
    await cache.invalidate_admin_caches()
    
    return None

# Image-to-Image 6-mode separated files.
# Loaded here deliberately so the main app/api/v1/router.py does not need to be replaced.
# This keeps the patch focused and protects Operator, Credits, Assistant, Admin and other API routes.
from app.api.v1.endpoints.img2img_modes import router as img2img_modes_router  # noqa: E402
router.include_router(img2img_modes_router)
