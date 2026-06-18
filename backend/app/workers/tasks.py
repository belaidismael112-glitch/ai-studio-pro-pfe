"""Celery tasks for async AI generation.

This moves heavy/polling work out of the request/response cycle.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import async_session
from app.models.generation import Generation
from app.services.ai_service import ai_service
from app.services.storage_service import storage_service
from app.services.credit_service import credit_service
from app.services.reference_modes import (
    should_use_source_lock_composite,
    strip_identity_board_marker,
    strip_reference_mode_marker,
    strip_reference_subject_type_marker,
)
from app.core.config import settings
from app.core import cache

# --- AI_STUDIO_V12_7_1_RUNTIME_HOOK_FIX2 ---
def _ai_studio_v1271_runtime_hook(ai_result, generation_obj=None, logger_obj=None):
    import os
    from pathlib import Path

    if not isinstance(ai_result, dict):
        return ai_result

    enabled = str(os.getenv("COMFY_DIRECTOR_V12_FINAL_SOURCE_LOCK_COMPOSITE", "true")).lower() in ("1", "true", "yes", "on")
    if not enabled or not ai_result.get("success"):
        return ai_result

    metadata = ai_result.setdefault("metadata", {})
    # AI_STUDIO_V13_WORKER_ACCEPT: V13 already produces the final source composite.
    if metadata.get("v13_commercial_engine") or str(ai_result.get("provider") or "").startswith("comfy-director-v13-"):
        return ai_result
    if metadata.get("v12_7_1_runtime_hook") or metadata.get("v12_7_source_lock_final_composite"):
        return ai_result

    mode = metadata.get("mode") or metadata.get("resolved_mode") or ai_result.get("source_lock_mode") or ""
    allowed_modes = {"flyer_poster", "product_ad", "background_replace", "auto_smart", "social_post"}
    if mode not in allowed_modes:
        return ai_result

    local_path = ai_result.get("local_path")
    if not local_path:
        return ai_result

    comfy_path = Path(str(local_path))
    if not comfy_path.exists():
        metadata["v12_7_1_runtime_hook_skipped"] = "comfy_path_missing"
        return ai_result

    source_path = None
    if generation_obj is not None:
        for attr in ("local_path", "input_path", "source_path", "image_path"):
            candidate = getattr(generation_obj, attr, None)
            if candidate and Path(str(candidate)).exists():
                source_path = str(candidate)
                break

    if not source_path:
        for candidate in (
            metadata.get("source_image_path"),
            metadata.get("input_path"),
            metadata.get("uploaded_image_path"),
        ):
            if candidate and Path(str(candidate)).exists():
                source_path = str(candidate)
                break

    if not source_path:
        metadata["v12_7_1_runtime_hook_skipped"] = "source_path_missing"
        if logger_obj:
            logger_obj.warning("V12_7_1_RUNTIME_HOOK_SKIPPED source_path_missing mode=%s local_path=%s", mode, local_path)
        return ai_result

    try:
        from app.services.img2img_hybrid.source_lock_composite_v12 import (
            V12_7_SOURCE_LOCK_FINAL_COMPOSITE_MARKER,
            apply_v12_7_source_lock_final_composite,
        )

        final_path, meta_patch = apply_v12_7_source_lock_final_composite(
            comfy_output_path=str(comfy_path),
            source_image_path=str(source_path),
            output_dir="static/images",
            mode=str(mode),
            metadata=metadata,
        )

        old_url = str(ai_result.get("url") or "")
        prefix = old_url.rsplit("/", 1)[0] + "/" if "/" in old_url else "http://127.0.0.1:8000/images/"

        ai_result["local_path"] = final_path
        ai_result["url"] = prefix + Path(final_path).name
        ai_result["provider"] = "comfy-director-v12-7-source-lock-final-composite"
        metadata.update(meta_patch)
        metadata["v12_7_1_runtime_hook"] = True
        metadata["v12_7_1_runtime_hook_marker"] = "AI_STUDIO_V12_7_1_RUNTIME_HOOK_FIX2"
        metadata["v12_7_marker"] = V12_7_SOURCE_LOCK_FINAL_COMPOSITE_MARKER
        if str(metadata.get("subject_type") or "") in ("", "document"):
            metadata["subject_type"] = "product"

        if logger_obj:
            logger_obj.info("V12_7_1_RUNTIME_HOOK_APPLIED mode=%s old=%s final=%s", mode, local_path, final_path)
        return ai_result

    except Exception as exc:
        metadata["v12_7_1_runtime_hook_error"] = str(exc)
        if logger_obj:
            logger_obj.exception("V12_7_1_RUNTIME_HOOK_FAILED keeping original result")
        return ai_result
# --- /AI_STUDIO_V12_7_1_RUNTIME_HOOK_FIX2 ---


logger = logging.getLogger(__name__)


async def _run_generation(gen: Generation) -> dict:
    """Execute generation via AIService and return result dict."""
    if gen.generation_type == "image":
        return await ai_service.generate_image(
            prompt=gen.prompt,
            negative_prompt=gen.negative_prompt,
            width=gen.width or 1024,
            height=gen.height or 1024,
            style=gen.style,
        )

    if gen.generation_type == "img2img":
        return await ai_service.generate_image_from_image(
            image_path=gen.local_path,
            prompt=gen.prompt,
            negative_prompt=gen.negative_prompt,
            strength=gen.strength or 0.22,
            width=gen.width or 1024,
            height=gen.height or 1024,
            style=gen.style,
        )

    if gen.generation_type in {"video", "img2vid"}:
        return {
            "success": False,
            "url": None,
            "error": "Video generation is disabled in this image-first production build. Use Image-to-Image instead.",
        }

    return {
        "success": False,
        "url": None,
        "error": f"Unsupported generation type: {gen.generation_type}",
    }



def _commercial_source_lock_required(prompt: str | None) -> bool:
    """Return True when a queued reference job must expose an exact-source composite.

    Product Ad always requires it. Flyer / Poster requires it only for a real
    product or document. Artistic flyers (worm, animal, generic object) must
    remain on the ComfyUI img2img path.
    """
    mode, clean = strip_reference_mode_marker(prompt or "")
    subject_type, _clean = strip_reference_subject_type_marker(clean)
    if str(mode or "").strip().lower() == "person_identity" and str(subject_type or "").strip().lower() not in {"person", "person_face", "person_full", "person_full_body"}:
        logger.warning("WORKER_PERSON_IDENTITY_SUBJECT_COERCED old_subject=%s new_subject=person_face", subject_type)
        subject_type = "person_face"
    required = should_use_source_lock_composite(mode, subject_type)
    logger.info("WORKER_SOURCE_LOCK_CHECK mode=%s subject=%s required=%s", mode, subject_type, required)
    return required




def _is_v11_shared_design_layer_result(ai_result: dict, expected_mode: str | None = None) -> bool:
    """Accept V11/V12 shared-design-layer outputs after the renderer has succeeded.

    V11/V12 Product Ad / Flyer / Social / Background / Identity / Creative outputs are not
    legacy ``source_lock`` files. They are Comfy final images validated by the
    V11 adapter metadata. The worker should accept them when the result is a
    real V11 no-fallback final asset with a selected layout.
    """
    try:
        provider = str(ai_result.get("provider") or "").lower()
        metadata = ai_result.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        local_path = str(ai_result.get("local_path") or metadata.get("final_local_path") or "")
        selected_layout = str(metadata.get("selected_layout") or "")
        mode = str(metadata.get("mode") or metadata.get("resolved_mode") or "").lower()
        fallback_used = bool(ai_result.get("fallback_used") or metadata.get("fallback_used"))

        if not (provider.startswith("comfy-director-v11-") or provider.startswith("comfy-director-v12-")):
            return False
        is_v11 = bool(metadata.get("v11_shared_design_layer"))
        is_v12 = bool(metadata.get("v12_prompt_first_commercial_engine") or metadata.get("v12_prompt_first") or metadata.get("v12_marker"))
        if not (is_v11 or is_v12):
            return False
        if fallback_used:
            return False
        if not selected_layout:
            return False
        if expected_mode and mode and mode != expected_mode:
            return False
        if not local_path:
            return False

        normalized = local_path.replace("\\", "/").lower()
        return (
            "/static/images/" in f"/{normalized}"
            or normalized.startswith("static/images/")
            or "generated_comfy_v6_" in normalized
            or "/v11_guides/" in normalized
            or "/v9_guides/" in normalized
        )
    except Exception:
        return False


# --- AI_STUDIO_V14_WORKER_ACCEPT_FINAL_COMPOSITE_FIX2 ---
def _ai_studio_v14_final_composite_result_is_valid(ai_result: dict) -> bool:
    try:
        if not isinstance(ai_result, dict):
            return False
        provider = str(ai_result.get("provider") or "").lower()
        metadata = ai_result.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        local_path = str(ai_result.get("local_path") or metadata.get("final_local_path") or "")
        stem = Path(local_path).stem.lower() if local_path else ""
        normalized = local_path.replace("\\", "/").lower()
        if _is_forbidden_person_identity_asset(local_path) or str(metadata.get("mode") or metadata.get("resolved_mode") or "").strip().lower() == "person_identity":
            return False

        provider_ok = (
            provider.startswith("comfy-director-v20-fixed-pro-poster-engine")
            or provider.startswith("comfy-director-v21-pro-comfy-poster-background")
            or provider.startswith("comfy-director-v22-center-product-pro-poster")
            or provider.startswith("comfy-director-v14-workflow-binding")
            or provider.startswith("comfy-director-v13-commercial-engine")
            or bool(metadata.get("v20_fixed_pro_poster_engine"))
            or bool(metadata.get("v22_center_product_pro_poster"))
            or bool(metadata.get("v14_workflow_binding"))
            or bool(metadata.get("v13_commercial_engine"))
        )
        final_file_ok = stem.startswith("generated_v13_commercial_") or "generated_v13_commercial_" in normalized
        composite_ok = bool(metadata.get("v13_final_composite")) and bool(metadata.get("v13_exact_source_composite"))
        source_ok = bool(
            metadata.get("v13_3_rembg_hard_fix")
            or metadata.get("v13_segmentation")
            or metadata.get("v13_cutout_path")
        )
        fallback_used = bool(ai_result.get("fallback_used") or metadata.get("fallback_used"))
        path_ok = bool(local_path) and (
            normalized.startswith("static/images/")
            or "/static/images/" in f"/{normalized}"
            or "generated_v13_commercial_" in normalized
        )
        return bool(provider_ok and final_file_ok and composite_ok and source_ok and path_ok and not fallback_used)
    except Exception:
        return False
# --- /AI_STUDIO_V14_WORKER_ACCEPT_FINAL_COMPOSITE_FIX2 ---

def _commercial_source_lock_result_is_valid(ai_result: dict) -> bool:
    """Validate production-safe commercial results.

    Legacy Product Ad / Flyer results used provider names containing
    ``source-lock`` and filenames containing ``_source_lock``.  V8 real flyer
    delivery intentionally bypasses ComfyUI backdrops and returns files named
    ``generated_real_flyer_*`` from provider
    ``real-flyer-engine-no-comfy-backdrop``.  That output is already a
    source-preserving composite, so the worker must accept it instead of
    refunding a successful result.
    """
    provider = str(ai_result.get("provider") or "").lower()
    local_path = str(ai_result.get("local_path") or "")
    stem = Path(local_path).stem.lower() if local_path else ""

    # AI_STUDIO_V14_WORKER_ACCEPT_FINAL_COMPOSITE_FIX2
    if _ai_studio_v14_final_composite_result_is_valid(ai_result):
        return True
    # AI_STUDIO_V13_WORKER_ACCEPT
    try:
        metadata = ai_result.get("metadata") or {}
        mode = str(metadata.get("mode") or metadata.get("resolved_mode") or "").strip().lower()
        commercial_provider = (
            provider.startswith("comfy-director-v13-")
            or provider.startswith("comfy-director-v20-")
            or provider.startswith("comfy-director-v21-")
            or provider.startswith("comfy-director-v22-")
            or provider.startswith("comfy-director-v23-")
            or provider.startswith("comfy-director-v24-")
            or provider.startswith("comfy-director-v25-")
        )
        if (
            commercial_provider
            and mode in {"product_ad", "flyer_poster", "background_replace", "social_post"}
            and stem.startswith("generated_v13_commercial_")
            and not _is_forbidden_person_identity_asset(local_path)
            and (bool(metadata.get("v13_commercial_engine")) or bool(metadata.get("v20_fixed_pro_poster_engine"))
            or bool(metadata.get("v22_center_product_pro_poster")) or bool(metadata.get("v25_universal_pro_poster_stage_integration")))
            and bool(metadata.get("v13_final_composite"))
            and not bool(metadata.get("fallback_used"))
        ):
            return True
    except Exception:
        pass

    # V11/V12 shared design layer outputs are final Comfy images, not legacy source_lock files.
    # Accept them here when metadata proves: no fallback, selected_layout present, final asset present.
    if _is_v11_shared_design_layer_result(ai_result):
        return True

    # V10_10_HARD_ACCEPT_ALL_V10_OUTPUTS
    # V10 hybrid engine already performs deterministic source-safe composition.
    # Accept V10 outputs even if filename/provider do not contain legacy source_lock tokens.
    try:
        _v10_provider = str(provider or "").lower()
        _v10_stem = str(stem or "").lower()
        if (
            "v10" in _v10_provider
            or _v10_stem.startswith("generated_v10_")
            or "hybrid-comfy-backdrop" in _v10_provider
            or "hybrid_flyer" in _v10_provider
            or "hybrid-flyer" in _v10_provider
        ):
            return True
    except Exception:
        pass


    # V10 Hybrid engine outputs are already source-safe for commercial modes.
    # Flyer uses deterministic final rendering, so it does not contain "source_lock"
    # in the filename. Product/background deterministic fallbacks use generated_v10_*.
    if provider.startswith("v10-") or "v10-hybrid" in provider or "deterministic_flyer" in provider:
        if stem.startswith(("generated_v10_flyer", "generated_v10_product", "generated_v10_background", "generated_v10_")):
            return True

    if "v10-hybrid-flyer-engine" in provider and stem.startswith("generated_v10_flyer"):
        return True

    if "real-flyer-engine" in provider and stem.startswith("generated_real_flyer_"):
        return True

    if "deterministic-premium-source-lock" in provider and ("source_lock" in stem or stem.startswith(("generated_real_flyer_", "generated_v10_"))):
        return True

    if "comfy-flux-source-lock-composite" in provider and "source_lock" in stem:
        return True

    return "source-lock" in provider and "source_lock" in stem


def _identity_board_required(prompt: str | None) -> bool:
    """Return True when queued Person / Identity work requested the safe board."""
    mode, clean = strip_reference_mode_marker(prompt or "")
    requested, _clean = strip_identity_board_marker(clean)
    return mode == "person_identity" and requested


def _identity_board_result_is_valid(ai_result: dict) -> bool:
    """Validate deterministic exact-source identity-board or V11 identity output."""
    if _is_v11_shared_design_layer_result(ai_result, expected_mode="person_identity"):
        return True
    provider = str(ai_result.get("provider") or "").lower()
    local_path = str(ai_result.get("local_path") or "")
    stem = Path(local_path).stem.lower() if local_path else ""
    return "identity-board-source-lock" in provider and "identity_board_source_lock" in stem


def _build_local_public_url(local_path: str, generation_type: str | None = None) -> str:
    """Build public URL for locally stored generated assets.

    Images generated by the flyer overlay live in /images.
    Videos generated by ComfyUI/LTXV live in /videos.
    """
    path = Path(local_path)
    filename = path.name
    backend_public_url = (
        getattr(settings, "BACKEND_PUBLIC_URL", None)
        or "http://localhost:8000"
    ).rstrip("/")

    suffix = path.suffix.lower()
    # Generation type wins over file extension. LTXV/SaveAnimatedWEBP returns
    # animated .webp files, and those must be served from /videos, not /images.
    if generation_type in {"video", "img2vid"}:
        return f"{backend_public_url}/videos/{filename}"
    if generation_type in {"image", "img2img"}:
        return f"{backend_public_url}/images/{filename}"
    if suffix in {".mp4", ".webm", ".gif", ".webp"}:
        return f"{backend_public_url}/videos/{filename}"
    return f"{backend_public_url}/images/{filename}"



# V10_14_FINAL_ONLY_DELIVERY_GUARD
def _is_intermediate_v10_asset(value: str | None) -> bool:
    """Return True for internal-only assets that must never be shown to users."""
    text = str(value or "").replace("\\", "/").lower()
    return any(token in text for token in (
        "v10_comfy_backdrop_",
        "aistudiopro_v10_backdrop_flyer",
        "source_lock_backdrop",
        "source-lock-backdrop",
        "commercial_backdrop",
        "backdrop_flyer",
        "person_identity_background",
        "v14_person_identity_background",
    )) and "generated_v10_flyer_" not in text


def _is_forbidden_person_identity_asset(value: str | None) -> bool:
    text = str(value or "").replace("\\", "/").lower()
    return any(token in text for token in (
        "generated_v13_commercial_person_identity",
        "v13_commercial_person_identity",
        "person_identity_background",
        "v14_person_identity_background",
    ))


def _looks_like_user_final_asset(value: str | None) -> bool:
    text = str(value or "").replace("\\", "/").lower()
    if _is_forbidden_person_identity_asset(text):
        return False
    return any(token in text for token in (
        "generated_v10_flyer_",
        "generated_v10_product",
        "generated_v10_background",
        "generated_real_flyer_",
        "source_lock",
        "identity_board_source_lock",
        "generated_comfy_v6_",
        "generated_v13_commercial_",
    ))


def _prompt_is_person_identity(prompt: str | None) -> bool:
    try:
        mode, clean = strip_reference_mode_marker(prompt or "")
        subject_type, _ = strip_reference_subject_type_marker(clean)
        st = str(subject_type or "").strip().lower()
        return str(mode or "").strip().lower() == "person_identity" or st in {"person", "person_face", "person_full", "person_full_body"}
    except Exception:
        return "person_identity" in str(prompt or "").lower()


def _person_identity_result_is_unsafe(prompt: str | None, ai_result: dict) -> bool:
    if not _prompt_is_person_identity(prompt):
        return False
    metadata = ai_result.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    provider = str(ai_result.get("provider") or "")
    values = [
        ai_result.get("local_path"),
        ai_result.get("url"),
        provider,
        metadata.get("mode"),
        metadata.get("resolved_mode"),
        metadata.get("v13_background_path"),
        metadata.get("v13_cutout_path"),
        metadata.get("final_local_path"),
    ]
    if any(_is_forbidden_person_identity_asset(v) for v in values):
        return True
    mode = str(metadata.get("mode") or metadata.get("resolved_mode") or "").strip().lower()
    if metadata.get("v13_commercial_engine") and mode == "person_identity":
        return True
    return False


def _find_recent_final_v10_asset(search_dir: Path, started_at: datetime | None = None) -> str | None:
    """Find the most recent user-facing V10 final image in a folder.

    Used only as a recovery guard if some code accidentally returns a ComfyUI
    backdrop path. The worker should store generated_v10_flyer_*.png, never the
    internal v10_comfy_backdrop_*.png.
    """
    try:
        if not search_dir.exists():
            return None
        candidates = []
        patterns = [
            "generated_v10_flyer_*.png",
            "generated_v10_product*.png",
            "generated_v10_background*.png",
            "generated_real_flyer_*.png",
        ]
        min_ts = started_at.timestamp() - 5 if started_at else 0
        for pattern in patterns:
            for path in search_dir.glob(pattern):
                try:
                    if path.stat().st_mtime >= min_ts:
                        candidates.append(path)
                except Exception:
                    continue
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return str(candidates[0])
    except Exception:
        return None


def _force_user_facing_ai_result(ai_result: dict, started_at: datetime | None = None) -> dict:
    """Normalize AI result so DB/frontend receive only the final composed asset.

    Internal-only ComfyUI background files are allowed for pipeline metadata,
    but they must not become Generation.result_url/local_path.
    """
    result = dict(ai_result or {})
    local_path = result.get("local_path")
    url = result.get("url")
    metadata = result.get("metadata") or {}

    # If the renderer provided explicit final path in metadata, prefer it.
    for key in ("final_local_path", "final_path", "user_facing_local_path", "composed_local_path"):
        candidate = metadata.get(key)
        if candidate and _looks_like_user_final_asset(candidate):
            result["local_path"] = candidate
            result["url"] = None
            result.setdefault("provider", result.get("provider") or "v10-final-only")
            return result

    for key in ("final_url", "final_result_url", "user_facing_url", "composed_url"):
        candidate = metadata.get(key)
        if candidate and _looks_like_user_final_asset(candidate):
            result["url"] = candidate
            result["local_path"] = None
            result.setdefault("provider", result.get("provider") or "v10-final-only")
            return result

    # If local path is internal backdrop, recover latest generated final from same folder.
    if _is_intermediate_v10_asset(local_path):
        search_dir = Path(str(local_path)).parent
        recovered = _find_recent_final_v10_asset(search_dir, started_at=started_at)
        if recovered:
            logger.warning("V10_FINAL_ONLY_GUARD recovered final asset %s from internal %s", recovered, local_path)
            result["local_path"] = recovered
            result["url"] = None
            return result

        logger.error("V10_FINAL_ONLY_GUARD blocked internal local_path=%s without final asset", local_path)
        return {
            **result,
            "success": False,
            "error": "Internal ComfyUI backdrop was produced but no final composed flyer was returned. Final-only guard blocked the intermediate asset.",
        }

    # If URL points to an internal backdrop, block it unless local final exists.
    if _is_intermediate_v10_asset(url):
        if local_path and _looks_like_user_final_asset(local_path):
            result["url"] = None
            return result
        logger.error("V10_FINAL_ONLY_GUARD blocked internal url=%s", url)
        return {
            **result,
            "success": False,
            "error": "Internal ComfyUI backdrop URL was returned instead of final composed image. Final-only guard blocked it.",
        }

    return result


async def process_generation_async(generation_id: int) -> None:
    """Process a generation using the current async event loop.

    FastAPI local/eager mode calls this directly so we do not call asyncio.run()
    inside an already-running event loop. The Celery task below wraps this for
    real worker mode.
    """
    async with async_session() as db:
        result = await db.execute(
            select(Generation).where(Generation.id == generation_id)
        )
        gen = result.scalar_one_or_none()

        if not gen:
            logger.warning("Generation %s not found", generation_id)
            return

        logger.info(
            "Processing generation id=%s type=%s AI_PROVIDER=%s COMFY_URL=%s",
            gen.id,
            gen.generation_type,
            getattr(settings, "AI_PROVIDER", None),
            getattr(settings, "COMFY_URL", None),
        )

        gen.status = "processing"
        gen.error_message = None
        await db.commit()

        start = datetime.utcnow()

        try:
            ai_result = await _run_generation(gen)
            ai_result = _force_user_facing_ai_result(ai_result, started_at=start)
            logger.info("AI result for generation %s after final-only guard: %s", gen.id, ai_result)
            ai_result = _ai_studio_v1271_runtime_hook(ai_result, locals().get("generation") or locals().get("gen") or locals().get("db_generation"), logger)
            logger.info("V12_7_1_RUNTIME_HOOK_APPLIED generation=%s provider=%s path=%s metadata_v1271=%s", locals().get("generation_id") or getattr(locals().get("generation", None), "id", None), ai_result.get("provider") if isinstance(ai_result, dict) else None, ai_result.get("local_path") if isinstance(ai_result, dict) else None, (ai_result.get("metadata") or {}).get("v12_7_1_runtime_hook") if isinstance(ai_result, dict) else None)

            # FINAL PRO FIX: A Neural Camera diagnostic board is not a final AI image.
            # If any stale UI/backend path still returns identity-board-source-lock,
            # fail/refund instead of exposing the report board as the delivery asset.
            if (
                str(ai_result.get("provider") or "").strip().lower() == "identity-board-source-lock"
                or bool(ai_result.get("identity_board"))
            ) and str(getattr(settings, "IDENTITY_REPORT_IMAGE_GENERATION_ENABLED", "false")).lower() not in {"1", "true", "yes", "on"}:
                gen.status = "failed"
                gen.error_message = "Neural Camera report board was produced instead of a final AI image. Final delivery guard blocked it. Leave report mode off and run final generation."
                await credit_service.add_credits(
                    db,
                    gen.user_id,
                    gen.credits_used or 0,
                    transaction_type="refund",
                    description=f"Refund for diagnostic report blocked as final image #{gen.id}",
                    generation_id=gen.id,
                )
                await db.commit()
                await cache.invalidate_admin_caches()
                return

            if not ai_result.get("success"):
                gen.status = "failed"
                gen.error_message = ai_result.get("error") or "Generation failed"

                await credit_service.add_credits(
                    db,
                    gen.user_id,
                    gen.credits_used or 0,
                    transaction_type="refund",
                    description=f"Refund for failed {gen.generation_type} generation #{gen.id}",
                    generation_id=gen.id,
                )
                await db.commit()
                await cache.invalidate_admin_caches()
                return

            # AI_STUDIO_V25_SAFE_PERSON_IDENTITY_ROUTE
            # Person / Identity must never expose a commercial/background/cutout
            # intermediate or a non-source fallback person. Fail safely and refund.
            if _person_identity_result_is_unsafe(gen.prompt, ai_result):
                gen.status = "failed"
                gen.error_message = (
                    "Person Identity safety guard blocked a commercial/background intermediate result. "
                    "Use Image-to-Image with a valid uploaded source image and the direct identity path; no random fallback person was exposed."
                )
                await credit_service.add_credits(
                    db,
                    gen.user_id,
                    gen.credits_used or 0,
                    transaction_type="refund",
                    description=f"Refund for unsafe person identity result #{gen.id}",
                    generation_id=gen.id,
                )
                await db.commit()
                await cache.invalidate_admin_caches()
                return

            # Production invariant: Product Ad and Flyer / Poster must expose
            # the exact-source composite, never the raw diffusion backdrop or a
            # full-frame img2img repaint. This keeps legacy worker behavior intact
            # while preventing mutated-label commercial results from being marked
            # completed.
            if _commercial_source_lock_required(gen.prompt) and not _commercial_source_lock_result_is_valid(ai_result):
                gen.status = "failed"
                gen.error_message = (
                    "Commercial source-lock invariant failed. The generated scene was not composited with the exact uploaded product. "
                    "No weak or repainted packaging result was exposed. Worker invariant rejected the output. Apply V10.2 worker accept patch and restart the backend/Celery worker."
                )
                await credit_service.add_credits(
                    db,
                    gen.user_id,
                    gen.credits_used or 0,
                    transaction_type="refund",
                    description=f"Refund for source-lock integrity failure #{gen.id}",
                    generation_id=gen.id,
                )
                await db.commit()
                await cache.invalidate_admin_caches()
                return

            # Person / Identity production-board requests must return the exact
            # source-locked board.  Never expose a generic img2img lookalike as
            # a completed production identity result.
            if _identity_board_required(gen.prompt) and not _identity_board_result_is_valid(ai_result):
                gen.status = "failed"
                gen.error_message = (
                    "Identity source-lock invariant failed. The safe production identity board was not returned. "
                    "No lookalike portrait was exposed. Worker invariant rejected the output. Apply V10.2 worker accept patch and restart the backend/Celery worker."
                )
                await credit_service.add_credits(
                    db,
                    gen.user_id,
                    gen.credits_used or 0,
                    transaction_type="refund",
                    description=f"Refund for identity source-lock integrity failure #{gen.id}",
                    generation_id=gen.id,
                )
                await db.commit()
                await cache.invalidate_admin_caches()
                return

            gen.model_used = (
                ai_result.get("provider")
                or ("replicate" if ai_result.get("prediction_id") else "runway")
            )

            result_url = None

            local_path = ai_result.get("local_path")
            if local_path:
                gen.local_path = local_path
                result_url = _build_local_public_url(local_path, gen.generation_type)

            elif ai_result.get("url"):
                remote_url = ai_result["url"]

                try:
                    stored = await storage_service.upload_from_url(
                        user_id=gen.user_id,
                        kind=gen.generation_type,
                        source_url=remote_url,
                        filename_hint=(
                            f"{gen.generation_type}."
                            f"{'png' if gen.generation_type in ['image', 'img2img'] else 'mp4'}"
                        ),
                    )
                    result_url = stored.signed_url if stored else remote_url
                except Exception as storage_error:
                    logger.warning(
                        "Storage upload failed for generation %s, fallback to direct URL: %s",
                        gen.id,
                        storage_error,
                    )
                    result_url = remote_url

            if not result_url:
                gen.status = "failed"
                gen.error_message = (
                    ai_result.get("error") or "No output returned from AI service"
                )

                await credit_service.add_credits(
                    db,
                    gen.user_id,
                    gen.credits_used or 0,
                    transaction_type="refund",
                    description=f"Refund for failed {gen.generation_type} generation #{gen.id}",
                    generation_id=gen.id,
                )
                await db.commit()
                await cache.invalidate_admin_caches()
                return

            gen.result_url = result_url
            gen.status = "completed"
            gen.error_message = None
            gen.completed_at = datetime.utcnow()
            gen.generation_time = (datetime.utcnow() - start).total_seconds()

            await db.commit()
            await cache.invalidate_admin_caches()

        except Exception as e:
            logger.error(
                "Failed processing generation %s: %s",
                generation_id,
                e,
                exc_info=True,
            )

            gen.status = "failed"
            gen.error_message = str(e)

            await credit_service.add_credits(
                db,
                gen.user_id,
                gen.credits_used or 0,
                transaction_type="refund",
                description=f"Refund for failed {gen.generation_type} generation #{gen.id}",
                generation_id=gen.id,
            )
            await db.commit()
            await cache.invalidate_admin_caches()


@celery_app.task(name="app.workers.process_generation")
def process_generation(generation_id: int) -> None:
    """Celery worker wrapper for generation processing."""
    asyncio.run(process_generation_async(generation_id))
