"""Authenticated runtime status for image-first ComfyUI deployments.

The endpoint intentionally exposes no secrets.  It verifies the configured
ComfyUI URL, local workflow assets and the selected image checkpoint so the UI
can show an honest production-readiness state.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends

from app.core.config import settings
import os
from app.core.security import get_current_user_id
from app.services.ollama_service import runtime_status as ollama_runtime_status

router = APIRouter()

_REQUIRED_WORKFLOWS = {
    "text_to_image": "AIStudio_Image_FLUX_BASE_Correct_ComfyUI.json",
    "person_identity": "AIStudio_Image_FLUX_IDENTITY_IMG2IMG.json",
    "product_ad": "AIStudio_Image_FLUX_PRODUCT_BACKDROP.json",
    "flyer_poster": "AIStudio_Image_FLUX_FLYER_BACKDROP.json",
    "background_replace": "AIStudio_Image_FLUX_BACKGROUND_REPLACE.json",
    "creative_reference": "AIStudio_Image_FLUX_CREATIVE_REFERENCE.json",
}


def _safe_url(raw: str) -> str:
    """Return URL without credentials, query string or fragments."""
    try:
        parts = urlsplit(raw)
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path.rstrip("/"), "", ""))
    except Exception:
        return "configured"


def _workflow_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "comfy_workflows"


def _workflow_status() -> dict[str, dict[str, object]]:
    root = _workflow_dir()
    result: dict[str, dict[str, object]] = {}
    for key, filename in _REQUIRED_WORKFLOWS.items():
        path = root / filename
        result[key] = {
            "filename": filename,
            "present": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
    return result




def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


async def _assistant_runtime_status() -> dict[str, object]:
    ollama = await ollama_runtime_status(timeout_seconds=3.0)
    piper_enabled = _env_bool("PIPER_ENABLED", False)
    piper_exe = os.getenv("PIPER_EXE", "").strip()
    piper_voice_en = os.getenv("PIPER_VOICE_EN", "").strip()
    piper_voice_fr = os.getenv("PIPER_VOICE_FR", "").strip()
    return {
        "output_languages": ["en", "fr"],
        "accepted_input_styles": ["en", "fr", "tunisian_arabizi", "tunisian_arabic_script"],
        "unsupported_language_policy": "accept_input_answer_in_selected_ui_language",
        "tunisian_arabizi_supported": True,
        "chat": {
            **ollama.as_dict(),
            "fallback_enabled": True,
            "fallback_policy": "explicit_local_fallback_when_ollama_is_optional",
        },
        "speech": {
            "audio_output_languages": ["en", "fr"],
            "arabic_voice_enabled": False,
            "arabic_voice_policy": "disabled",
            "server_tts_enabled": piper_enabled,
            "piper_configured": bool(piper_enabled and piper_exe and piper_voice_en and piper_voice_fr),
            "browser_tts_fallback": True,
            "voice_en_configured": bool(piper_voice_en),
            "voice_fr_configured": bool(piper_voice_fr),
        },
    }

def _extract_checkpoint_names(payload: object) -> list[str]:
    """Best-effort parse of ComfyUI CheckpointLoaderSimple object_info."""
    try:
        if not isinstance(payload, dict):
            return []
        node = payload.get("CheckpointLoaderSimple", payload)
        required = node.get("input", {}).get("required", {})
        values = required.get("ckpt_name", [])
        if isinstance(values, list) and values:
            options = values[0]
            if isinstance(options, list):
                return [str(item) for item in options]
    except Exception:
        return []
    return []


@router.get("/runtime/status")
async def runtime_status(current_user_id: int = Depends(get_current_user_id)):
    del current_user_id  # authentication only; response is non-secret

    provider = str(settings.AI_PROVIDER).lower()
    comfy_url = str(settings.COMFY_URL).rstrip("/")
    workflows = _workflow_status()
    workflow_assets_ready = all(bool(item["present"]) for item in workflows.values())

    connected = False
    checkpoint_available: bool | None = None
    checkpoint_names: list[str] = []
    error: str | None = None

    if provider == "comfy":
        try:
            timeout = httpx.Timeout(4.0, connect=2.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{comfy_url}/system_stats")
                response.raise_for_status()
                connected = True
                try:
                    info = await client.get(f"{comfy_url}/object_info/CheckpointLoaderSimple")
                    info.raise_for_status()
                    checkpoint_names = _extract_checkpoint_names(info.json())
                except Exception:
                    checkpoint_names = []
        except Exception as exc:
            error = f"ComfyUI is not reachable: {exc}"
    else:
        error = f"AI_PROVIDER is '{provider}', expected 'comfy' for this image-first build."

    checkpoint = str(settings.COMFY_IMAGE_CHECKPOINT)
    if connected and checkpoint_names:
        checkpoint_available = checkpoint in checkpoint_names
    elif connected:
        checkpoint_available = None

    assistant = await _assistant_runtime_status()

    warnings: list[str] = []
    if provider != "comfy":
        warnings.append("Set AI_PROVIDER=comfy in backend/.env.")
    if not connected:
        warnings.append("Start ComfyUI and verify COMFY_URL from the backend runtime.")
    if not workflow_assets_ready:
        warnings.append("One or more required image workflow files are missing.")
    if checkpoint_available is False:
        warnings.append(f"Checkpoint '{checkpoint}' was not reported by ComfyUI.")
    elif connected and checkpoint_available is None:
        warnings.append("ComfyUI checkpoint verification is incomplete because object_info did not expose checkpoint names.")
    if not bool(settings.COMFY_STRICT_WORKFLOW_MODE):
        warnings.append("Enable COMFY_STRICT_WORKFLOW_MODE=true for predictable local results.")
    if assistant["chat"]["enabled"] and not assistant["chat"]["connected"]:
        warnings.append("Ollama is enabled but unreachable. Start the Ollama container or update OLLAMA_BASE_URL.")
    if assistant["chat"]["enabled"] and assistant["chat"]["connected"] and not assistant["chat"]["fast_model_ready"]:
        warnings.append(f"Ollama fast model '{assistant['chat']['fast_model']}' is not installed.")
    if assistant["chat"]["enabled"] and assistant["chat"]["connected"] and not assistant["chat"]["advanced_model_ready"]:
        warnings.append(f"Ollama advanced model '{assistant['chat']['advanced_model']}' is not installed.")
    if assistant["speech"]["server_tts_enabled"] and not assistant["speech"]["piper_configured"]:
        warnings.append("PIPER_ENABLED is true but Piper executable or voices are not fully configured.")

    ready = (
        provider == "comfy"
        and connected
        and workflow_assets_ready
        and checkpoint_available is True
        and bool(settings.COMFY_STRICT_WORKFLOW_MODE)
        and (not bool(assistant["chat"]["required"]) or bool(assistant["chat"]["ready"]))
    )

    return {
        "build_mode": "image_first",
        "video_generation_enabled": False,
        "production_ready": ready,
        "provider": provider,
        "comfyui": {
            "url": _safe_url(comfy_url),
            "connected": connected,
            "error": error,
            "image_checkpoint": checkpoint,
            "checkpoint_available": checkpoint_available,
            "strict_workflow_mode": bool(settings.COMFY_STRICT_WORKFLOW_MODE),
            "prompt_engine_enabled": bool(settings.COMFY_USE_PROMPT_ENGINE),
            "random_seed": bool(settings.COMFY_RANDOM_SEED),
            "steps": int(settings.COMFY_IMAGE_STEPS),
            "cfg": float(settings.COMFY_IMAGE_CFG),
            "sampler": str(settings.COMFY_IMAGE_SAMPLER),
            "scheduler": str(settings.COMFY_IMAGE_SCHEDULER),
            "timeout_seconds": int(settings.COMFY_IMAGE_TIMEOUT_SECONDS),
        },
        "assistant": assistant,
        "reference_modes": {
            "identity_production": {
                "board_default": _env_bool("IDENTITY_PRODUCTION_BOARD_DEFAULT", True),
                "strategy": "exact_source_identity_board_without_generic_face_repaint",
                "optional_identity_adapter_required_for_new_pose_or_outfit": True,
            },
            "commercial_source_lock": {
                "deterministic_fallback_enabled": _env_bool("COMMERCIAL_ENABLE_DETERMINISTIC_FALLBACK", True),
                "experimental_ai_backdrops_for_safe_modes": _env_bool("COMMERCIAL_ALLOW_AI_BACKDROP_FOR_SAFE_MODES", False),
                "safe_delivery_modes": ["product_ad", "flyer_poster", "creative_image"],
                "background_replace_preserves_environment_without_hero_zone_blur": True,
            },
        },
        "queue": {
            "task_always_eager": bool(settings.CELERY_TASK_ALWAYS_EAGER),
            "redis_configured": bool(settings.REDIS_URL),
        },
        "workflows": workflows,
        "warnings": warnings,
    }
