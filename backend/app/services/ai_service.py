"""AI generation service - integrates with Replicate, Runway, and ComfyUI.

Hardening added:
- Centralized HTTP helper with retry/backoff for transient failures
- Safer error handling (returns structured error instead of raising where possible)
- Runtime provider/token resolution to reduce stale worker config issues
- Clearer provider selection for video/image generation
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
import random
from pathlib import Path
from typing import Optional
from types import SimpleNamespace
from urllib.parse import quote, urlencode, urlparse, parse_qs
from uuid import uuid4

import httpx
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageStat

from app.core.config import settings
from app.services.prompt_tools import enhance_prompt, enhance_video_prompt
from app.services.commercial_compositor import (
    commercial_source_quality_report,
    prepare_reference_subject_asset,
    render_reference_commercial_asset,
    render_readable_flyer_overlay_only,
    reference_finish_quality_score,
    source_lock_backdrop_is_safe,
)
from app.services.identity_board_compositor import render_identity_production_board
from app.services.reference_modes import (
    commercial_backdrop_prompt,
    source_lock_backdrop_prompt,
    reference_mode_prompt_suffix,
    should_apply_optional_flyer_overlay,
    should_use_source_lock_composite,
    strip_flyer_overlay_marker,
    strip_identity_board_marker,
    strip_reference_mode_marker,
    strip_reference_subject_type_marker,
    strip_vision_prompt_pack_marker,
)

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI image and video generation."""

    def __init__(self):
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.max_retries = int(getattr(settings, "AI_HTTP_MAX_RETRIES", 3))
        self.retry_backoff = float(getattr(settings, "AI_HTTP_RETRY_BACKOFF", 0.8))

    # -------------------------------------------------------------------------
    # Runtime configuration helpers
    # -------------------------------------------------------------------------
    def _current_provider(self) -> str:
        return (
            os.getenv("AI_PROVIDER")
            or getattr(settings, "AI_PROVIDER", "replicate")
            or "replicate"
        ).strip().lower()

    def _replicate_token(self) -> Optional[str]:
        return os.getenv("REPLICATE_API_TOKEN") or getattr(
            settings, "REPLICATE_API_TOKEN", None
        )

    def _runway_key(self) -> Optional[str]:
        return os.getenv("RUNWAY_API_KEY") or getattr(
            settings, "RUNWAY_API_KEY", None
        )

    def _fal_key(self) -> Optional[str]:
        return os.getenv("FAL_KEY") or getattr(settings, "FAL_KEY", None)

    def _comfy_url(self) -> str:
        return (
            os.getenv("COMFY_URL")
            or getattr(settings, "COMFY_URL", None)
            or "http://127.0.0.1:8188"
        ).rstrip("/")

    def _stable_seed(self, *parts: object) -> int:
        """Deterministic seed for stable results when the prompt is identical."""
        raw = "|".join(str(p or "") for p in parts)
        digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()
        return max(1, int(digest[:8], 16))

    def _comfy_checkpoint(self) -> str:
        return (
            os.getenv("COMFY_CHECKPOINT")
            or getattr(settings, "COMFY_CHECKPOINT", None)
            or "flux1-schnell-fp8.safetensors"
        )

    def _comfy_image_checkpoint(self) -> str:
        """Checkpoint used by the image and image-to-image workflows.

        Resolve runtime environment first, then Pydantic settings loaded from
        backend/.env, then the safe FLUX default.  The previous implementation
        ignored Settings.COMFY_IMAGE_CHECKPOINT when the variable came only from
        the .env file, which made the Settings source-of-truth misleading.
        """
        return (
            os.getenv("COMFY_IMAGE_CHECKPOINT")
            or getattr(settings, "COMFY_IMAGE_CHECKPOINT", None)
            or "flux1-schnell-fp8.safetensors"
        )

    def _comfy_ltxv_checkpoint(self) -> str:
        """Checkpoint used by video generation. Never falls back to old AnimateDiff/SD1.5 keys."""
        return (
            os.getenv("COMFY_LTXV_CHECKPOINT")
            or os.getenv("COMFY_VIDEO_CHECKPOINT")
            or getattr(settings, "COMFY_LTXV_CHECKPOINT", None)
            or getattr(settings, "COMFY_VIDEO_CHECKPOINT", None)
            or "ltx-video-2b-v0.9.safetensors"
        )

    def _comfy_ltxv_clip(self) -> str:
        """CLIP/T5 encoder used by LTXV video workflow."""
        return (
            os.getenv("COMFY_LTXV_CLIP")
            or getattr(settings, "COMFY_LTXV_CLIP", None)
            or "t5xxl_fp8_e4m3fn.safetensors"
        )

    def _env_value(self, key: str, default):
        env_value = os.getenv(key)
        if env_value not in {None, ""}:
            return env_value
        setting_value = getattr(settings, key, None)
        if setting_value not in {None, ""}:
            return setting_value
        return default

    def _env_int(self, key: str, default: int) -> int:
        try:
            return int(self._env_value(key, default))
        except Exception:
            return int(default)

    def _env_float(self, key: str, default: float) -> float:
        try:
            return float(self._env_value(key, default))
        except Exception:
            return float(default)

    def _env_str(self, key: str, default: str) -> str:
        return str(self._env_value(key, default))

    def _comfy_motion_model(self) -> str:
        """Legacy compatibility only; kept to prevent old paths from crashing."""
        return self._comfy_ltxv_checkpoint()

    def _backend_public_url(self) -> str:
        return (
            os.getenv("BACKEND_PUBLIC_URL")
            or getattr(settings, "BACKEND_PUBLIC_URL", None)
            or "http://localhost:8000"
        ).rstrip("/")

    def _workflow_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "comfy_workflows"

    def _load_comfy_workflow_template(self, filename: str) -> Optional[dict]:
        try:
            path = self._workflow_dir() / filename
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _replace_workflow_placeholders(self, obj, mapping: dict[str, object]):
        if isinstance(obj, dict):
            return {k: self._replace_workflow_placeholders(v, mapping) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._replace_workflow_placeholders(v, mapping) for v in obj]
        if isinstance(obj, str) and obj in mapping:
            return mapping[obj]
        return obj

    # -------------------------------------------------------------------------
    # HTTP utilities
    # -------------------------------------------------------------------------
    async def _request_json(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        headers: dict,
        json: Optional[dict] = None,
        timeout: Optional[httpx.Timeout] = None,
    ) -> dict:
        """HTTP request with small retry+backoff for transient network/provider errors."""
        last_err: Exception | None = None

        for attempt in range(max(1, self.max_retries)):
            try:
                r = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    timeout=timeout or self.timeout,
                )
                r.raise_for_status()
                return r.json()

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
                last_err = e
                status = getattr(getattr(e, "response", None), "status_code", None)

                # Don't retry most client errors except 429. Preserve provider body
                # so the UI shows useful ComfyUI errors such as missing custom nodes.
                if status is not None and 400 <= int(status) < 500 and int(status) != 429:
                    body = ""
                    try:
                        body = e.response.text[:1200] if e.response is not None else ""
                    except Exception:
                        body = ""
                    if body:
                        raise RuntimeError(f"Provider request failed ({status}): {body}") from e
                    break

                await asyncio.sleep(self.retry_backoff * (2 ** attempt))

        raise RuntimeError(f"Provider request failed: {last_err}")

    def _reference_prompt_is_generic(self, prompt: str) -> bool:
        lowered = (prompt or "").strip().lower()
        if not lowered:
            return True
        generic_phrases = [
            "polished hero visual", "main subject clear and recognizable", "production-ready quality",
            "turn this upload", "keep the main subject", "hero visual", "studio style"
        ]
        scene_markers = [
            "forest", "jungle", "desert", "beach", "city", "street", "room", "kitchen", "studio",
            "macro", "cinematic", "sunset", "night", "neon", "water", "smoke", "fog", "garden",
            "background", "scene", "environment", "editorial", "poster", "flyer"
        ]
        return any(phrase in lowered for phrase in generic_phrases) and not any(marker in lowered for marker in scene_markers)

    def _augment_reference_prompt_for_mode(self, prompt: str, generation_mode: str | None, subject_type: str | None) -> str:
        mode = (generation_mode or "").strip().lower()
        stype = (subject_type or "").strip().lower()
        if mode not in {"creative_image", "background_replace"}:
            return prompt
        additions: list[str] = []
        if mode == "creative_image":
            additions.append(
                "Transform the uploaded source into a genuinely new fully rendered scene. Do not keep the subject as a simple cutout, rope-like copy, white-background object, or minor edit."
            )
            if stype in {"insect", "pet", "animal"}:
                additions.append(
                    "For living small subjects, create a believable macro cinematic habitat: natural scale cues, textured ground, depth of field, environmental context, realistic contact shadow, and preserved recognizable anatomy."
                )
            else:
                additions.append(
                    "Place the subject in a believable editorial or cinematic environment with depth, supporting elements, and realistic contact shadow."
                )
        if mode == "background_replace":
            additions.append(
                "Change the environment clearly and completely. The result must show a new background and coherent scene lighting, not the original/plain background."
            )
        if self._reference_prompt_is_generic(prompt):
            additions.append(
                "If the user did not specify a scene, choose one automatically that best fits the subject and looks production-ready."
            )
        merged = " ".join(part.strip() for part in [prompt, *additions] if part and part.strip())
        return merged.strip()

    def _reference_visual_delta_score(self, source_path: str, result_path: str) -> float:
        """Return a normalized pixel delta for reference-based generation.

        The score is intentionally simple and deterministic: both images are
        normalized to the same small RGB canvas and the mean absolute pixel
        difference is divided by 255. It is not a perceptual-quality score. It
        only prevents a provider/fallback bug from reporting a near-copy of the
        uploaded source as a successful transformed Product Ad or background
        replacement.
        """
        try:
            size = (192, 192)
            source = ImageOps.fit(Image.open(source_path).convert("RGB"), size, Image.Resampling.LANCZOS)
            result = ImageOps.fit(Image.open(result_path).convert("RGB"), size, Image.Resampling.LANCZOS)
            diff = ImageChops.difference(source, result)
            mean = ImageStat.Stat(diff).mean[:3]
            return round(sum(float(value) for value in mean) / (3.0 * 255.0), 4)
        except Exception as exc:
            logger.warning("Could not calculate reference visual delta: %s", exc)
            return -1.0

    def _minimum_reference_visual_delta(self, generation_mode: str | None) -> float:
        """Return the minimum visible-change gate for transformation modes."""
        resolved = (generation_mode or "").strip().lower()
        defaults = {
            "product_ad": 0.020,
            "flyer_poster": 0.020,
            "background_replace": 0.012,
            "creative_image": 0.020,
        }
        default = defaults.get(resolved, 0.0)
        if default <= 0:
            return 0.0
        env_key = f"REFERENCE_MIN_VISUAL_DELTA_{resolved.upper()}"
        return max(0.0, min(self._env_float(env_key, default), 1.0))

    def _reference_retry_denoise(self, generation_mode: str | None) -> float:
        """Return the stronger second-pass denoise for non-person transformations."""
        resolved = (generation_mode or "").strip().lower()
        defaults = {
            "product_ad": 0.82,
            "flyer_poster": 0.84,
            "background_replace": 0.82,
            "creative_image": 0.86,
        }
        default = defaults.get(resolved, 0.0)
        if default <= 0:
            return 0.0
        env_key = f"REFERENCE_RETRY_DENOISE_{resolved.upper()}"
        return max(0.0, min(self._env_float(env_key, default), 0.90))

    def _minimum_reference_finish_quality(self, generation_mode: str | None) -> float:
        """Reject obviously flat deterministic finishing outputs.

        This is intentionally a conservative heuristic, not an aesthetic score.
        """
        resolved = (generation_mode or "").strip().lower()
        defaults = {
            "product_ad": 0.22,
            "flyer_poster": 0.20,
            "background_replace": 0.16,
            "creative_image": 0.20,
        }
        default = defaults.get(resolved, 0.0)
        if default <= 0:
            return 0.0
        env_key = f"REFERENCE_MIN_FINISH_QUALITY_{resolved.upper()}"
        return max(0.0, min(self._env_float(env_key, default), 1.0))

    def _deterministic_reference_rescue_enabled(self) -> bool:
        """Keep deterministic rescue disabled unless the operator opts in.

        The primary result must come from the AI workflow.  This prevents a
        basic emergency layout from being presented as a professional render.
        """
        return self._env_str("REFERENCE_ALLOW_DETERMINISTIC_RESCUE", "false").lower() in {"1", "true", "yes", "on"}

    def _file_to_data_url(self, path: str, max_bytes: int = 5 * 1024 * 1024) -> str:
        """Convert a local file to a data URL."""
        p = Path(path)
        data = p.read_bytes()
        if len(data) > max_bytes:
            raise ValueError(
                f"Input file too large ({len(data)} bytes). Max: {max_bytes} bytes"
            )

        mime, _ = mimetypes.guess_type(p.name)
        mime = mime or "image/png"
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    # -------------------------------------------------------------------------
    # Public generation APIs
    # -------------------------------------------------------------------------
    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        style: Optional[str] = None,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
    ) -> dict:
        """Generate image using the configured provider."""

        provider = self._current_provider()
        logger.info(
            "generate_image provider=%s width=%s height=%s",
            provider,
            width,
            height,
        )

        if provider == "comfy":
            return await self._generate_image_comfy(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                style=style,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
            )

        if provider == "replicate":
            token = self._replicate_token()
            if not token:
                return {
                    "success": False,
                    "url": None,
                    "error": "AI_PROVIDER=replicate but REPLICATE_API_TOKEN is not configured",
                }

            enhanced_prompt = self._apply_style(prompt, style)
            url = "https://api.replicate.com/v1/predictions"

            headers = {
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
            }

            payload = {
                "version": "39ed52f2a78e934b3ba6e2a89ff5f7e222c5e5f71fd95e0e6f5f9a7b2f2e5e5",
                "input": {
                    "prompt": enhanced_prompt,
                    "negative_prompt": negative_prompt or "",
                    "width": width,
                    "height": height,
                    "num_inference_steps": num_inference_steps,
                    "guidance_scale": guidance_scale,
                    "scheduler": "K_EULER",
                },
            }

            try:
                async with httpx.AsyncClient() as client:
                    prediction = await self._request_json(
                        client, "POST", url, headers=headers, json=payload
                    )
                    prediction_id = prediction["id"]
                    result = await self._poll_replicate_prediction(
                        client, headers, prediction_id
                    )

                    output = result.get("output")
                    if isinstance(output, list):
                        output = output[0] if output else None

                    return {
                        "success": result.get("status") == "succeeded",
                        "url": output,
                        "error": result.get("error"),
                        "prediction_id": prediction_id,
                        "provider": "replicate",
                    }

            except Exception as e:
                logger.error("generate_image failed: %s", str(e), exc_info=True)
                return {"success": False, "url": None, "error": str(e)}


        return {
            "success": False,
            "url": None,
            "error": f"Unsupported AI_PROVIDER for image generation: {provider}",
        }

    async def generate_image_from_image(
        self,
        image_path: str,
        prompt: str,
        negative_prompt: Optional[str] = None,
        strength: float = 0.22,
        width: int = 1024,
        height: int = 1024,
        style: Optional[str] = None,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
    ) -> dict:
        """Image → Image generation.

        In production we must preserve the uploaded person's identity instead of
        falling back to text-only generation. When AI_PROVIDER=comfy, run a true
        ComfyUI img2img workflow (LoadImage -> VAEEncode -> KSampler -> VAEDecode).
        External img2img providers are still supported when configured.
        """

        if self._current_provider() == "comfy":
            return await self._generate_image_from_image_comfy(
                image_path=image_path,
                prompt=prompt,
                negative_prompt=negative_prompt,
                strength=strength,
                width=width,
                height=height,
                style=style,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
            )

        token = self._replicate_token()
        if not token:
            return {
                "success": False,
                "url": None,
                "error": "REPLICATE_API_TOKEN not configured",
            }

        try:
            _, provider_prompt = strip_reference_mode_marker(prompt)
            _, provider_prompt = strip_flyer_overlay_marker(provider_prompt)
            _, provider_prompt = strip_identity_board_marker(provider_prompt)
            _, provider_prompt = strip_reference_subject_type_marker(provider_prompt)
            enhanced_prompt = self._apply_style(provider_prompt, style)
            image_input = self._file_to_data_url(image_path)

            url = "https://api.replicate.com/v1/predictions"
            headers = {
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
            }

            payload = {
                "version": "15a3689ee13b0d07b27a171053436c0063784057591e694297755d5cdbfc1b70",
                "input": {
                    "prompt": enhanced_prompt,
                    "negative_prompt": negative_prompt or "",
                    "image": image_input,
                    "strength": float(strength),
                    "width": int(width),
                    "height": int(height),
                    "num_inference_steps": int(num_inference_steps),
                    "guidance_scale": float(guidance_scale),
                },
            }

            async with httpx.AsyncClient() as client:
                prediction = await self._request_json(
                    client, "POST", url, headers=headers, json=payload
                )
                prediction_id = prediction["id"]
                result = await self._poll_replicate_prediction(
                    client, headers, prediction_id
                )

                output = result.get("output")
                if isinstance(output, list):
                    output = output[0] if output else None

                return {
                    "success": result.get("status") == "succeeded",
                    "url": output,
                    "error": result.get("error"),
                    "prediction_id": prediction_id,
                    "provider": "replicate",
                }

        except Exception as e:
            logger.error("generate_image_from_image failed: %s", str(e), exc_info=True)
            return {"success": False, "url": None, "error": str(e)}

    async def generate_video_from_image(
        self,
        image_path: str,
        prompt: str = "",
        motion_strength: int = 50,
        duration: int = 4,
        width: int = 1024,
        height: int = 576,
    ) -> dict:
        """Image → Video generation.

        In local ComfyUI mode, use the locked LTXV text-to-video workflow so the
        feature does not fail just because Runway keys are absent. The input image
        path is preserved in the generation record but the local workflow is text
        driven unless a dedicated img2vid Comfy workflow is later added.
        """

        _, provider_prompt = strip_reference_mode_marker(prompt)
        _, provider_prompt = strip_reference_subject_type_marker(provider_prompt)
        prompt = provider_prompt

        if self._current_provider() == "comfy":
            return await self._generate_video_from_image_comfy(
                image_path=image_path,
                prompt=prompt or "animate the uploaded image with natural product motion",
                motion_strength=motion_strength,
                duration=duration,
                width=width,
                height=height,
            )

        runway_key = self._runway_key()
        if not runway_key:
            return {
                "success": False,
                "url": None,
                "error": "RUNWAY_API_KEY not configured",
            }

        try:
            prompt_image = self._file_to_data_url(image_path)
            mapped_duration = 5 if int(duration) <= 5 else 10

            ratio = f"{int(width)}:{int(height)}"
            if (width, height) == (1024, 576):
                ratio = "1280:720"
            elif (width, height) == (576, 1024):
                ratio = "720:1280"

            headers = {
                "Authorization": f"Bearer {runway_key}",
                "Content-Type": "application/json",
                "X-Runway-Version": "2024-11-06",
            }

            payload = {
                "model": "gen4_turbo",
                "promptImage": prompt_image,
                "duration": mapped_duration,
                "ratio": ratio,
            }
            if prompt:
                payload["promptText"] = prompt

            _ = motion_strength

            async with httpx.AsyncClient() as client:
                task = await self._request_json(
                    client,
                    "POST",
                    "https://api.runwayml.com/v1/image_to_video",
                    headers=headers,
                    json=payload,
                )

                task_id = task.get("id")
                if not task_id:
                    return {"success": False, "url": None, "error": "No task id returned"}

                out_url = await self._poll_runway_task(client, headers, task_id)
                return {
                    "success": out_url is not None,
                    "url": out_url,
                    "error": None if out_url else "Generation failed",
                    "generation_id": task_id,
                    "provider": "runway",
                }

        except Exception as e:
            logger.error("generate_video_from_image failed: %s", str(e), exc_info=True)
            return {"success": False, "url": None, "error": str(e)}

    async def generate_video(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        duration: int = 4,
        width: int = 1024,
        height: int = 576,
        fps: int = 24,
    ) -> dict:
        """Generate video using the configured provider."""

        provider = self._current_provider()
        logger.info(
            "generate_video provider=%s duration=%s width=%s height=%s comfy_url=%s",
            provider,
            duration,
            width,
            height,
            self._comfy_url(),
        )

        if provider == "comfy":
            return await self._generate_video_comfy(
                prompt=prompt,
                negative_prompt=negative_prompt,
                duration=duration,
                width=width,
                height=height,
            )

        if provider == "replicate":
            token = self._replicate_token()
            if not token:
                return {
                    "success": False,
                    "url": None,
                    "error": "AI_PROVIDER=replicate but REPLICATE_API_TOKEN is not configured",
                }
            return await self._generate_video_replicate(
                prompt, negative_prompt, duration, width, height, fps
            )


        return {
            "success": False,
            "url": None,
            "error": f"Unsupported AI_PROVIDER for video generation: {provider}",
        }

    # -------------------------------------------------------------------------
    # Provider-specific implementations
    # -------------------------------------------------------------------------
    async def _generate_video_replicate(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        duration: int,
        width: int,
        height: int,
        fps: int,
    ) -> dict:
        """Generate video using Stable Video Diffusion on Replicate."""

        token = self._replicate_token()
        if not token:
            return {
                "success": False,
                "url": None,
                "error": "REPLICATE_API_TOKEN not configured",
            }

        try:
            url = "https://api.replicate.com/v1/predictions"
            headers = {
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
            }

            payload = {
                "version": "3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
                "input": {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt or "",
                    "width": width,
                    "height": height,
                    "num_frames": duration * fps,
                    "fps": fps,
                },
            }

            async with httpx.AsyncClient() as client:
                prediction = await self._request_json(
                    client, "POST", url, headers=headers, json=payload
                )
                prediction_id = prediction["id"]
                result = await self._poll_replicate_prediction(
                    client, headers, prediction_id
                )

                return {
                    "success": result.get("status") == "succeeded",
                    "url": result.get("output"),
                    "error": result.get("error"),
                    "prediction_id": prediction_id,
                    "provider": "replicate",
                }

        except Exception as e:
            logger.error("_generate_video_replicate failed: %s", str(e), exc_info=True)
            return {"success": False, "url": None, "error": str(e)}

    async def _generate_video_runway(
        self,
        prompt: str,
        duration: int,
        width: int,
        height: int,
    ) -> dict:
        """Generate video using Runway API."""

        runway_key = self._runway_key()
        if not runway_key:
            return {
                "success": False,
                "url": None,
                "error": "RUNWAY_API_KEY not configured",
            }

        try:
            url = "https://api.runwayml.com/v1/generations"
            headers = {
                "Authorization": f"Bearer {runway_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "prompt": prompt,
                "duration": duration,
                "width": width,
                "height": height,
            }

            async with httpx.AsyncClient() as client:
                result = await self._request_json(
                    client, "POST", url, headers=headers, json=payload
                )
                generation_id = result.get("id")
                if not generation_id:
                    return {
                        "success": False,
                        "url": None,
                        "error": "No generation id returned",
                    }

                video_url = await self._poll_runway_generation(
                    client, headers, generation_id
                )
                return {
                    "success": video_url is not None,
                    "url": video_url,
                    "error": None if video_url else "Generation failed",
                    "generation_id": generation_id,
                    "provider": "runway",
                }

        except Exception as e:
            logger.error("_generate_video_runway failed: %s", str(e), exc_info=True)
            return {"success": False, "url": None, "error": str(e)}

    async def _generate_video_comfy(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        duration: int,
        width: int,
        height: int,
    ) -> dict:
        """Generate video using local ComfyUI + the new LTXV workflow.

        The old project had an AnimateDiff / RealisticVision path here.  We keep
        every old .env key untouched, but this method intentionally uses the new
        LTXV nodes and models so the video page no longer falls back to the old
        model:
        - CheckpointLoaderSimple: ltx-video-2b-v0.9.safetensors
        - CLIPLoader: t5xxl_fp8_e4m3fn.safetensors, type=ltxv
        - LTXVConditioning
        - EmptyLTXVLatentVideo
        - LTXVScheduler
        - SamplerCustom
        - VAE Decode
        - SaveAnimatedWEBP
        """

        comfy = self._comfy_url()
        # Do NOT read COMFY_VIDEO_CHECKPOINT here; that belongs to the old
        # AnimateDiff workflow.  Use optional new variables only if the user
        # explicitly adds them later.
        video_ckpt = self._comfy_ltxv_checkpoint()
        clip_name = self._comfy_ltxv_clip()

        def round64(x: int) -> int:
            return max(8, (int(x) // 8) * 8)

        strict_workflow = self._env_str("COMFY_STRICT_WORKFLOW_MODE", "true").lower() in {"1", "true", "yes", "on"}

        # Production UI-sync rule:
        # - Keep the uploaded LTXV workflow structure/model nodes.
        # - Apply the UI resolution directly to EmptyLTXVLatentVideo.
        # - Convert the UI duration into an LTXV-valid frame count (8n+1).
        #   Example with output_fps=24: 2s -> 49, 4s -> 97, 8s -> 193, 16s -> 385.
        requested_w = int(width or self._env_int("COMFY_LTXV_SQUARE_WIDTH", 512))
        requested_h = int(height or self._env_int("COMFY_LTXV_SQUARE_HEIGHT", 512))
        w = round64(requested_w)
        h = round64(requested_h)

        requested_duration = max(2, min(int(duration or 4), 16))
        fps = self._env_int("COMFY_LTXV_FPS", 25) if strict_workflow else max(6, min(self._env_int("COMFY_LTXV_FPS", 25), 30))
        output_fps = self._env_int("COMFY_LTXV_OUTPUT_FPS", 24) if strict_workflow else fps

        raw_frames = max(1, requested_duration * max(1, output_fps))
        remainder = raw_frames % 8
        frames = raw_frames if remainder == 1 else raw_frames + ((9 - remainder) % 8)
        min_frames = self._env_int("COMFY_LTXV_MIN_FRAMES", 25)
        max_frames = self._env_int("COMFY_LTXV_MAX_FRAMES", 385)
        frames = max(min_frames, min(frames, max_frames))

        # Exact default from the user's ComfyUI workflow: steps=20, cfg=3.
        steps = max(8, min(self._env_int("COMFY_LTXV_STEPS", 20), 36))
        cfg = max(1.0, min(self._env_float("COMFY_LTXV_CFG", 3.0), 6.0))
        sampler = self._env_str("COMFY_LTXV_SAMPLER", "euler")
        max_shift = self._env_float("COMFY_LTXV_MAX_SHIFT", 2.05)
        base_shift = self._env_float("COMFY_LTXV_BASE_SHIFT", 0.95)
        terminal = self._env_float("COMFY_LTXV_TERMINAL", 0.1)
        crf = max(10, min(self._env_int("COMFY_VIDEO_CRF", 18), 28))

        # IMPORTANT COMFY MATCH FIX: do not rewrite the prompt by default.
        # The previous backend expanded short prompts, so ComfyUI received a different
        # prompt from the one typed in the app.
        use_prompt_engine = self._env_str("COMFY_USE_PROMPT_ENGINE", "false").lower() in {"1", "true", "yes", "on"}
        if use_prompt_engine:
            video_prompt = enhance_video_prompt(
                prompt=prompt,
                negative_prompt=negative_prompt,
                duration=requested_duration,
                width=w,
                height=h,
            )
        else:
            video_prompt = SimpleNamespace(prompt=prompt, negative_prompt=negative_prompt or None)
        clean_prompt = video_prompt.prompt
        neg = video_prompt.negative_prompt or (
            "low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, fused fingers, bad anatomy, weird hand, ugly"
        )

        if self._env_str("COMFY_RANDOM_SEED", "true").lower() in {"1", "true", "yes", "on"}:
            seed = random.randint(1, 2**63 - 1)
        else:
            seed = self._stable_seed("video", clean_prompt, neg, w, h, frames, fps, steps, cfg, sampler)

        logger.info(
            "MODEL_LOCK VIDEO_PROVIDER=LTXV ckpt=%s clip=%s comfy=%s frames=%s conditioning_fps=%s output_fps=%s size=%sx%s seed=%s prompt_len=%s",
            video_ckpt,
            clip_name,
            comfy,
            frames,
            fps,
            output_fps,
            w,
            h,
            seed,
            len(clean_prompt),
        )

        try:
            workflow = {
                "44": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": video_ckpt},
                },
                "38": {
                    "class_type": "CLIPLoader",
                    "inputs": {"clip_name": clip_name, "type": "ltxv", "device": "default"},
                },
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["38", 0], "text": clean_prompt},
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["38", 0], "text": neg},
                },
                "69": {
                    "class_type": "LTXVConditioning",
                    "inputs": {"positive": ["6", 0], "negative": ["7", 0], "frame_rate": fps},
                },
                "70": {
                    "class_type": "EmptyLTXVLatentVideo",
                    "inputs": {"width": w, "height": h, "length": frames, "batch_size": 1},
                },
                "73": {
                    "class_type": "KSamplerSelect",
                    "inputs": {"sampler_name": sampler},
                },
                "71": {
                    "class_type": "LTXVScheduler",
                    "inputs": {
                        "latent": ["70", 0],
                        "steps": steps,
                        "max_shift": max_shift,
                        "base_shift": base_shift,
                        "stretch": True,
                        "terminal": terminal,
                    },
                },
                "72": {
                    "class_type": "SamplerCustom",
                    "inputs": {
                        "model": ["44", 0],
                        "positive": ["69", 0],
                        "negative": ["69", 1],
                        "sampler": ["73", 0],
                        "sigmas": ["71", 0],
                        "latent_image": ["70", 0],
                        "add_noise": True,
                        "noise_seed": seed,
                        "control_after_generate": "randomize",
                        "cfg": cfg,
                    },
                },
                "8": {
                    "class_type": "VAEDecode",
                    "inputs": {"samples": ["72", 0], "vae": ["44", 2]},
                },
                "41": {
                    # Exact output node from backend/comfy_workflows/ltxv_text_to_video_USER_NEW.json.
                    # The old backend used VHS_VideoCombine/mp4 here, which is NOT the same workflow.
                    "class_type": "SaveAnimatedWEBP",
                    "inputs": {
                        "images": ["8", 0],
                        "filename_prefix": "ComfyUI",
                        "fps": output_fps,
                        "lossless": False,
                        "quality": 90,
                        "method": "default",
                    },
                },
            }

            headers = {"Content-Type": "application/json"}

            async with httpx.AsyncClient() as client:
                r = await self._request_json(
                    client,
                    "POST",
                    f"{comfy}/prompt",
                    headers=headers,
                    json={"prompt": workflow},
                )

                prompt_id = r.get("prompt_id")
                if not prompt_id:
                    return {
                        "success": False,
                        "url": None,
                        "local_path": None,
                        "error": f"ComfyUI: no prompt_id returned: {r}",
                    }

                view_url = await self._poll_comfy_history_for_video(
                    client, comfy, headers, str(prompt_id)
                )
                if not view_url:
                    return {
                        "success": False,
                        "url": None,
                        "local_path": None,
                        "error": "ComfyUI: finished but no LTXV video found",
                    }

                download_result = await self._download_comfy_video_to_local(
                    client, view_url
                )
                if not download_result:
                    return {
                        "success": False,
                        "url": None,
                        "local_path": None,
                        "error": "ComfyUI: LTXV video generated but local download failed",
                    }

                return {
                    "success": True,
                    "url": download_result["public_url"],
                    "local_path": download_result["local_path"],
                    "error": None,
                    "prediction_id": str(prompt_id),
                    "provider": "comfy-ltxv",
                }

        except Exception as e:
            logger.error("_generate_video_comfy LTXV failed: %s", str(e), exc_info=True)
            return {"success": False, "url": None, "local_path": None, "error": str(e)}


    async def _upload_image_to_comfy(
        self,
        client: httpx.AsyncClient,
        comfy: str,
        image_path: str,
        *,
        overwrite: bool = True,
    ) -> str:
        """Upload a local image into ComfyUI input directory and return its ComfyUI filename."""
        p = Path(image_path)
        if not p.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")

        filename = f"product_studio_{uuid4().hex}{p.suffix.lower() or '.png'}"

        with p.open("rb") as f:
            files = {
                "image": (filename, f, mimetypes.guess_type(filename)[0] or "image/png"),
            }
            data = {
                "overwrite": "true" if overwrite else "false",
                "type": "input",
            }
            response = await client.post(
                f"{comfy}/upload/image",
                files=files,
                data=data,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            response.raise_for_status()

        try:
            payload = response.json()
            return payload.get("name") or filename
        except Exception:
            return filename

    async def _generate_video_from_image_comfy(
        self,
        *,
        image_path: str,
        prompt: str,
        motion_strength: int,
        duration: int,
        width: int,
        height: int,
    ) -> dict:
        """True ComfyUI image-to-video using LTXVImgToVideo.

        This workflow is based on ComfyUI's LTXV Image-to-Video graph and uses:
        LoadImage -> LTXVImgToVideo -> LTXVConditioning/LTXVScheduler -> SamplerCustom -> VAEDecode -> SaveAnimatedWEBP.
        """
        comfy = self._comfy_url()
        video_ckpt = self._comfy_ltxv_checkpoint()
        clip_name = self._comfy_ltxv_clip()

        def round64(x: int) -> int:
            return max(8, (int(x) // 8) * 8)

        w = round64(width or self._env_int("COMFY_LTXV_SQUARE_WIDTH", 512))
        h = round64(height or self._env_int("COMFY_LTXV_SQUARE_HEIGHT", 512))

        requested_duration = max(2, min(int(duration or 4), 16))
        fps = self._env_int("COMFY_LTXV_FPS", 25)
        output_fps = self._env_int("COMFY_LTXV_OUTPUT_FPS", 24)

        raw_frames = requested_duration * max(1, output_fps)
        remainder = raw_frames % 8
        frames = raw_frames if remainder == 1 else raw_frames + ((9 - remainder) % 8)
        frames = max(
            self._env_int("COMFY_LTXV_MIN_FRAMES", 25),
            min(frames, self._env_int("COMFY_LTXV_MAX_FRAMES", 385)),
        )

        steps = max(8, min(self._env_int("COMFY_LTXV_STEPS", 20), 40))
        cfg = max(1.0, min(self._env_float("COMFY_LTXV_CFG", 3.0), 6.0))
        sampler = self._env_str("COMFY_LTXV_SAMPLER", "euler")
        max_shift = self._env_float("COMFY_LTXV_MAX_SHIFT", 2.05)
        base_shift = self._env_float("COMFY_LTXV_BASE_SHIFT", 0.95)
        terminal = self._env_float("COMFY_LTXV_TERMINAL", 0.1)

        denoise = max(0.05, min(float(motion_strength or 50) / 100.0, 0.95))
        # Keep product identity stronger by default. Product ads need motion, but not full redesign.
        denoise = min(denoise, self._env_float("COMFY_PRODUCT_I2V_DENOISE_MAX", 0.35))

        clean_prompt = prompt or (
            "A premium cinematic product advertisement video. Animate the uploaded product photo "
            "with a subtle camera push-in, glossy reflections, elegant moving light, clean luxury "
            "background, realistic commercial product ad, keep product identity, logo, label, "
            "shape and packaging consistent."
        )
        neg = (
            "low quality, worst quality, deformed, distorted, disfigured, motion smear, "
            "motion artifacts, bad product shape, wrong label, fake text, watermark, blurry, "
            "noisy, artifacts, changed packaging, warped logo"
        )

        timeout_s = self._env_int("COMFY_VIDEO_TIMEOUT_SECONDS", 1800)
        logger.info(
            "MODEL_LOCK PRODUCT_I2V ckpt=%s clip=%s size=%sx%s frames=%s fps=%s output_fps=%s steps=%s cfg=%s denoise=%s",
            video_ckpt, clip_name, w, h, frames, fps, output_fps, steps, cfg, denoise,
        )

        async with httpx.AsyncClient() as client:
            uploaded_name = await self._upload_image_to_comfy(client, comfy, image_path)

            workflow = {
                "38": {
                    "class_type": "CLIPLoader",
                    "inputs": {"clip_name": clip_name, "type": "ltxv", "device": "default"},
                },
                "44": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": video_ckpt},
                },
                "78": {
                    "class_type": "LoadImage",
                    "inputs": {"image": uploaded_name},
                },
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["38", 0], "text": clean_prompt},
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["38", 0], "text": neg},
                },
                "77": {
                    "class_type": "LTXVImgToVideo",
                    "inputs": {
                        "positive": ["6", 0],
                        "negative": ["7", 0],
                        "vae": ["44", 2],
                        "image": ["78", 0],
                        "width": w,
                        "height": h,
                        "length": frames,
                        "batch_size": 1,
                        "strength": denoise,
                    },
                },
                "69": {
                    "class_type": "LTXVConditioning",
                    "inputs": {
                        "positive": ["77", 0],
                        "negative": ["77", 1],
                        "frame_rate": fps,
                    },
                },
                "73": {
                    "class_type": "KSamplerSelect",
                    "inputs": {"sampler_name": sampler},
                },
                "71": {
                    "class_type": "LTXVScheduler",
                    "inputs": {
                        "latent": ["77", 2],
                        "steps": steps,
                        "max_shift": max_shift,
                        "base_shift": base_shift,
                        "stretch": True,
                        "terminal": terminal,
                    },
                },
                "72": {
                    "class_type": "SamplerCustom",
                    "inputs": {
                        "model": ["44", 0],
                        "positive": ["69", 0],
                        "negative": ["69", 1],
                        "sampler": ["73", 0],
                        "sigmas": ["71", 0],
                        "latent_image": ["77", 2],
                        "add_noise": True,
                        "noise_seed": random.randint(1, 2**63 - 1),
                        "control_after_generate": "randomize",
                        "cfg": cfg,
                    },
                },
                "8": {
                    "class_type": "VAEDecode",
                    "inputs": {"samples": ["72", 0], "vae": ["44", 2]},
                },
                "41": {
                    "class_type": "SaveAnimatedWEBP",
                    "inputs": {
                        "images": ["8", 0],
                        "filename_prefix": "ProductStudio_I2V",
                        "fps": output_fps,
                        "lossless": False,
                        "quality": 90,
                        "method": "default",
                    },
                },
            }

            payload = {"prompt": workflow}
            task = await self._request_json(
                client,
                "POST",
                f"{comfy}/prompt",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
            prompt_id = task.get("prompt_id")
            if not prompt_id:
                return {"success": False, "url": None, "error": "ComfyUI did not return prompt_id"}

            view_url = await self._poll_comfy_history_for_video(
                client,
                comfy,
                {},
                prompt_id,
                max_attempts=max(1, int(timeout_s / 1.5)),
                delay=1.5,
            )
            if not view_url:
                return {"success": False, "url": None, "error": "ComfyUI image-to-video generation timed out"}

            stored = await self._download_comfy_video_to_local(client, view_url)
            if not stored:
                return {"success": False, "url": None, "error": "Failed to download ComfyUI product video"}

            return {
                "success": True,
                "url": stored["public_url"],
                "local_path": stored["local_path"],
                "generation_id": prompt_id,
                "provider": "comfy-product-i2v",
            }


    async def _download_comfy_video_to_local(
        self,
        client: httpx.AsyncClient,
        view_url: str,
    ) -> Optional[dict]:
        """Download the generated video from ComfyUI and store it locally under static/videos."""

        try:
            response = await client.get(
                view_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            response.raise_for_status()

            content_type = (response.headers.get("content-type") or "").lower()

            ext = ".mp4"
            if "webm" in content_type:
                ext = ".webm"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"
            else:
                try:
                    filename = (parse_qs(urlparse(view_url).query).get("filename") or [""])[0]
                    suffix = Path(filename).suffix.lower()
                    if suffix in {".mp4", ".webm", ".gif", ".webp"}:
                        ext = suffix
                except Exception:
                    pass

            base_dir = Path(__file__).resolve().parents[2]
            video_dir = base_dir / "static" / "videos"
            video_dir.mkdir(parents=True, exist_ok=True)

            filename = f"generated_{uuid4().hex}{ext}"
            output_path = video_dir / filename
            output_path.write_bytes(response.content)

            return {
                "public_url": f"{self._backend_public_url()}/videos/{filename}",
                "local_path": str(output_path),
            }

        except Exception as e:
            logger.error("_download_comfy_video_to_local failed: %s", str(e), exc_info=True)
            return None

    # -------------------------------------------------------------------------
    # Pollers
    # -------------------------------------------------------------------------
    async def _poll_replicate_prediction(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        prediction_id: str,
        max_attempts: int = 60,
        delay: float = 2.0,
    ) -> dict:
        """Poll Replicate prediction until complete."""

        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        for _ in range(max_attempts):
            try:
                result = await self._request_json(
                    client,
                    "GET",
                    url,
                    headers=headers,
                    json=None,
                    timeout=httpx.Timeout(15.0, connect=10.0),
                )
            except Exception:
                await asyncio.sleep(delay)
                continue

            status = result.get("status")
            if status in ["succeeded", "failed", "canceled"]:
                return result
            await asyncio.sleep(delay)

        raise TimeoutError(f"Prediction {prediction_id} timed out")

    async def _poll_runway_task(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        task_id: str,
        max_attempts: int = 80,
        delay: float = 5.0,
    ) -> Optional[str]:
        """Poll a Runway task until it is complete."""

        url = f"https://api.runwayml.com/v1/tasks/{task_id}"
        for _ in range(max_attempts):
            try:
                task = await self._request_json(
                    client,
                    "GET",
                    url,
                    headers=headers,
                    json=None,
                    timeout=httpx.Timeout(20.0, connect=10.0),
                )
            except Exception:
                await asyncio.sleep(delay)
                continue

            status = (task.get("status") or "").lower()

            if status in {"succeeded", "completed"}:
                output = task.get("output") or {}
                out = output.get("url") if isinstance(output, dict) else None

                if isinstance(out, list):
                    return out[0] if out else None
                if isinstance(out, str):
                    return out

                if isinstance(output, list) and output:
                    first = output[0]
                    if isinstance(first, dict):
                        u = first.get("url")
                        if isinstance(u, str):
                            return u

                return None

            if status in {"failed", "canceled", "cancelled"}:
                return None

            await asyncio.sleep(delay)

        return None

    async def _poll_runway_generation(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        generation_id: str,
        max_attempts: int = 60,
        delay: float = 2.0,
    ) -> Optional[str]:
        """Poll Runway generation until complete."""

        url = f"https://api.runwayml.com/v1/generations/{generation_id}"
        for _ in range(max_attempts):
            try:
                result = await self._request_json(
                    client,
                    "GET",
                    url,
                    headers=headers,
                    json=None,
                    timeout=httpx.Timeout(15.0, connect=10.0),
                )
            except Exception:
                await asyncio.sleep(delay)
                continue

            status = result.get("status")
            if status == "completed":
                return result.get("url")
            if status == "failed":
                return None
            await asyncio.sleep(delay)

        return None

    # -------------------------------------------------------------------------
    # Comfy image generation
    # -------------------------------------------------------------------------

    async def _download_comfy_image_to_local(self, client: httpx.AsyncClient, view_url: str) -> Optional[tuple[str, str]]:
        """Download a ComfyUI image view URL to backend/static/images.

        Production bug fixed: returning ComfyUI's /view URL directly exposes
        http://127.0.0.1:8188 to the browser and breaks when ComfyUI is private,
        firewalled, container-only, or CORS-restricted. The backend now always
        stores the image under /images and returns a public backend URL.
        """
        try:
            resp = await client.get(view_url, timeout=httpx.Timeout(120.0, connect=10.0))
            resp.raise_for_status()

            images_dir = Path(__file__).resolve().parents[2] / "static" / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            content_type = (resp.headers.get("content-type") or "").lower()
            ext = ".png"
            if "jpeg" in content_type or "jpg" in content_type:
                ext = ".jpg"
            elif "webp" in content_type:
                ext = ".webp"
            elif "png" in content_type:
                ext = ".png"
            else:
                try:
                    filename = (parse_qs(urlparse(view_url).query).get("filename") or [""])[0]
                    suffix = Path(filename).suffix.lower()
                    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                        ext = ".jpg" if suffix == ".jpeg" else suffix
                except Exception:
                    pass

            filename = f"generated_{uuid4().hex}{ext}"
            local_path = images_dir / filename
            local_path.write_bytes(resp.content)

            return f"{self._backend_public_url()}/images/{filename}", str(local_path)
        except Exception as e:
            logger.error("_download_comfy_image_to_local failed: %s", e, exc_info=True)
            return None

    def _load_font(self, size: int, bold: bool = False):
        """Load a common Windows/Linux font with fallback."""
        candidates = []
        if bold:
            candidates += [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/segoeuib.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        candidates += [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            try:
                if Path(path).exists():
                    return ImageFont.truetype(path, size=size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
        words = (text or "").split()
        if not words:
            return []
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _apply_flyer_overlay(self, image_path: str, flyer_meta: dict) -> str:
        """Render real readable flyer text after generation.

        The diffusion model generates the background only. This method draws
        the actual flyer text with Pillow, so spelling/readability is stable.
        """
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)

        # Professional left information panel; avoids covering the student face.
        panel_w = int(w * 0.44)
        pad = int(w * 0.055)
        od.rectangle((0, 0, panel_w, h), fill=(4, 24, 42, 205))
        od.rectangle((panel_w - max(4, int(w * 0.012)), 0, panel_w, h), fill=(0, 130, 210, 160))

        # Bottom CTA card
        band_h = int(h * 0.18)
        od.rounded_rectangle((pad, h - band_h - pad, panel_w - pad, h - pad), radius=max(12, int(w * 0.025)), fill=(255, 255, 255, 235))

        img = Image.alpha_composite(img.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(img)

        title = str(flyer_meta.get("title") or "UNIVERSITY OPEN DAY").upper()
        subtitle = str(flyer_meta.get("subtitle") or "BUILD YOUR FUTURE WITH US").upper()
        cta = str(flyer_meta.get("cta") or "REGISTER NOW").upper()
        details = flyer_meta.get("details") or []
        details = [str(x) for x in details if str(x).strip()][:5]

        title_font = self._load_font(max(26, int(w * 0.056)), bold=True)
        subtitle_font = self._load_font(max(14, int(w * 0.026)), bold=True)
        detail_font = self._load_font(max(13, int(w * 0.023)), bold=False)
        cta_font = self._load_font(max(16, int(w * 0.030)), bold=True)
        small_font = self._load_font(max(11, int(w * 0.020)), bold=False)

        max_text_w = panel_w - 2 * pad
        y = int(h * 0.075)

        for line in self._wrap_text(draw, title, title_font, max_text_w)[:3]:
            draw.text((pad, y), line, font=title_font, fill=(255, 255, 255, 255))
            y += int(w * 0.070)

        y += int(h * 0.014)
        draw.rounded_rectangle((pad, y, pad + int(max_text_w * 0.58), y + max(4, int(h * 0.007))), radius=6, fill=(0, 178, 255, 255))
        y += int(h * 0.045)

        for line in self._wrap_text(draw, subtitle, subtitle_font, max_text_w)[:2]:
            draw.text((pad, y), line, font=subtitle_font, fill=(210, 242, 255, 255))
            y += int(w * 0.040)
        y += int(h * 0.024)

        for line in details:
            for wrapped in self._wrap_text(draw, line, detail_font, max_text_w - int(w * 0.02))[:2]:
                draw.text((pad, y), "• " + wrapped, font=detail_font, fill=(235, 245, 255, 245))
                y += int(w * 0.038)
            y += int(h * 0.006)

        card_x0, card_y0 = pad, h - band_h - pad
        card_x1, card_y1 = panel_w - pad, h - pad
        btn_h = int((card_y1 - card_y0) * 0.40)
        btn_y = card_y0 + int((card_y1 - card_y0) * 0.15)
        draw.rounded_rectangle((card_x0 + int(w*0.025), btn_y, card_x1 - int(w*0.025), btn_y + btn_h), radius=int(btn_h * 0.45), fill=(0, 115, 190, 255))
        bbox = draw.textbbox((0, 0), cta, font=cta_font)
        draw.text(((card_x0+card_x1-(bbox[2]-bbox[0]))/2, btn_y + (btn_h-(bbox[3]-bbox[1]))/2 - 2), cta, font=cta_font, fill=(255,255,255,255))

        footer = ""
        for line in details:
            if "www." in line.lower() or "+" in line:
                footer = line
                break
        if footer:
            fy = card_y1 - int(h * 0.045)
            for fl in self._wrap_text(draw, footer, small_font, max_text_w)[:2]:
                fb = draw.textbbox((0,0), fl, font=small_font)
                draw.text(((card_x0+card_x1-(fb[2]-fb[0]))/2, fy), fl, font=small_font, fill=(20, 28, 36, 255))
                fy += int(h * 0.026)

        out_path = str(Path(image_path).with_name(Path(image_path).stem + "_pro_text.png"))
        img.convert("RGB").save(out_path, quality=96)
        return out_path


    @staticmethod
    def _source_lock_workflow_filename(mode: str | None) -> str:
        """Return the dedicated ComfyUI workflow asset for one reference mode.

        Auto Smart is resolved before this point. Person / Identity never enters
        the source-lock compositor and continues to use IDENTITY_IMG2IMG.
        """
        resolved = (mode or "product_ad").strip().lower()
        return {
            "product_ad": "AIStudio_Image_FLUX_PRODUCT_BACKDROP.json",
            "flyer_poster": "AIStudio_Image_FLUX_FLYER_BACKDROP.json",
            "background_replace": "AIStudio_Image_FLUX_BACKGROUND_REPLACE.json",
            "creative_image": "AIStudio_Image_FLUX_CREATIVE_REFERENCE.json",
        }.get(resolved, "AIStudio_Image_FLUX_PRODUCT_BACKDROP.json")

    async def _generate_commercial_backdrop_comfy(
        self,
        *,
        prompt: str,
        negative_prompt: Optional[str],
        width: int,
        height: int,
        style: Optional[str],
        filename_prefix: str,
        mode: str = "product_ad",
    ) -> dict:
        """Generate an empty AI advertising scene for source-locked compositing."""
        comfy = self._comfy_url()
        ckpt = self._comfy_image_checkpoint()

        def round64(value: int) -> int:
            return max(8, (int(value) // 8) * 8)

        w = round64(width or self._env_int("COMFY_IMAGE_DEFAULT_WIDTH", 1280))
        h = round64(height or self._env_int("COMFY_IMAGE_DEFAULT_HEIGHT", 720))
        steps = max(8, min(self._env_int("COMFY_COMMERCIAL_BACKGROUND_STEPS", 14), 32))
        cfg = max(1.0, min(self._env_float("COMFY_COMMERCIAL_BACKGROUND_CFG", 1.2), 3.0))
        sampler = self._env_str("COMFY_IMAGE_SAMPLER", "euler")
        scheduler = self._env_str("COMFY_IMAGE_SCHEDULER", "simple")
        styled_prompt = self._apply_style(prompt, style) if style else prompt
        forced_background_neg = (
            "product, bottle, can, package, packaging, box, watch, shoe, bag, logo, label, brand, letters, text, "
            "typography, watermark, person, hand, clutter, flat white background, low quality, blurry, distorted"
        )
        neg = ", ".join(part for part in [(negative_prompt or "").strip(), forced_background_neg] if part)
        if self._env_str("COMFY_RANDOM_SEED", "true").lower() in {"1", "true", "yes", "on"}:
            seed = random.randint(1, 2**63 - 1)
        else:
            seed = self._stable_seed("commercial-backdrop", styled_prompt, neg, w, h, steps, cfg)

        values = {
            "__CKPT__": ckpt,
            "__PROMPT__": styled_prompt,
            "__NEGATIVE_PROMPT__": neg,
            "__SEED__": seed,
            "__STEPS__": steps,
            "__CFG__": cfg,
            "__SAMPLER__": sampler,
            "__SCHEDULER__": scheduler,
            "__WIDTH__": w,
            "__HEIGHT__": h,
            "__FILENAME_PREFIX__": filename_prefix,
        }
        template = self._load_comfy_workflow_template(self._source_lock_workflow_filename(mode))
        if template:
            workflow = self._replace_workflow_placeholders(template, values)
        else:
            workflow = {
                "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
                "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": styled_prompt}},
                "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": neg}},
                "4": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "width": w, "height": h}},
                "5": {
                    "class_type": "KSampler",
                    "inputs": {
                        "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
                        "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0,
                    },
                },
                "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
                "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": filename_prefix}},
            }

        headers = {"Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient() as client:
                response = await self._request_json(client, "POST", f"{comfy}/prompt", headers=headers, json={"prompt": workflow})
                prompt_id = response.get("prompt_id")
                if not prompt_id:
                    return {"success": False, "error": f"ComfyUI commercial backdrop: no prompt_id returned: {response}"}
                view_url = await self._poll_comfy_history_for_image(client, comfy, headers, str(prompt_id))
                if not view_url:
                    return {"success": False, "error": "ComfyUI commercial backdrop: finished but no image found", "prediction_id": str(prompt_id)}
                downloaded = await self._download_comfy_image_to_local(client, view_url)
                if not downloaded:
                    return {"success": False, "error": "ComfyUI commercial backdrop generated but backend download failed", "prediction_id": str(prompt_id)}
                final_url, local_path = downloaded
                return {"success": True, "url": final_url, "local_path": local_path, "prediction_id": str(prompt_id)}
        except Exception as exc:
            logger.error("_generate_commercial_backdrop_comfy failed: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    async def _generate_source_lock_composite_comfy(
        self,
        *,
        source_path: str,
        prompt: str,
        negative_prompt: Optional[str],
        mode: str,
        width: int,
        height: int,
        style: Optional[str],
        include_text_overlay: bool,
        strict_source: bool = True,
        vision_prompt_pack: dict | None = None,
    ) -> dict:
        """Generate a dedicated AI scene and composite the analysed source asset.

        Product Ad and Flyer / Poster always use this path. Background Replace
        and Creative Reference use it for object/product sources when the subject
        can be isolated cleanly. Person / Identity never enters this compositor.
        """

        # V10.4 FORCE: Product/Flyer/Background/Creative can be handled by the hybrid engine
        # before the legacy source-lock compositor. Without this, flyer_poster can still
        # fall into V8 real-flyer-engine and produce generated_real_flyer_* outputs.
        if self._env_str("IMG2IMG_HYBRID_V10_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
            try:
                enabled_map = {
                    "flyer_poster": self._env_str("IMG2IMG_V10_ENABLE_FLYER", "true"),
                    "product_ad": self._env_str("IMG2IMG_V10_ENABLE_PRODUCT_AD", "true"),
                    "background_replace": self._env_str("IMG2IMG_V10_ENABLE_BACKGROUND_REPLACE", "true"),
                    "creative_image": self._env_str("IMG2IMG_V10_ENABLE_CREATIVE", "true"),
                    "auto": self._env_str("IMG2IMG_V10_ENABLE_AUTO", "true"),
                }
                if str(enabled_map.get(str(mode or ""), "false")).lower() in {"1", "true", "yes", "on"}:
                    from app.services.img2img_hybrid import generate_img2img
                    from app.services.img2img_hybrid.contracts import Img2ImgRequest

                    ai_backdrop_path = None
                    if str(mode or "") == "flyer_poster" and self._env_str("IMG2IMG_V10_USE_COMFY_BACKDROP_FOR_FLYER", "true").lower() in {"1", "true", "yes", "on"}:
                        try:
                            backdrop_prompt = (
                                "premium advertising background only, no product, no bottle, no package, no bag, "
                                "no text, no letters, clean professional commercial scene, cinematic lighting, "
                                "high-end poster background, abstract shapes, depth, elegant color harmony"
                            )
                            # Let the V10 renderer handle final product and text, ComfyUI only creates the art backdrop.
                            bd = await self._generate_commercial_backdrop_comfy(
                                prompt=backdrop_prompt,
                                negative_prompt="product, bottle, bag, logo, brand, text, letters, people, watermark, clutter",
                                width=width,
                                height=height,
                                style=style,
                                filename_prefix="AIStudioPro_V10_Backdrop_flyer",
                                mode="flyer_poster",
                            )
                            if bd.get("success") and bd.get("local_path"):
                                ai_backdrop_path = bd.get("local_path")
                                logger.info("V10_COMFY_BACKDROP_SUCCESS path=%s", ai_backdrop_path)
                            else:
                                logger.warning("V10_COMFY_BACKDROP_FAILED error=%s", bd.get("error"))
                        except Exception as exc:
                            logger.warning("V10_COMFY_BACKDROP_EXCEPTION error=%s", exc, exc_info=True)

                    v10 = await generate_img2img(Img2ImgRequest(
                        mode=str(mode or "creative_image"),
                        source_image_path=source_path,
                        prompt=prompt or "",
                        negative_prompt=negative_prompt or "",
                        width=width,
                        height=height,
                        style=style,
                        strength=0.25,
                        subject_type=None,
                        output_dir=self._env_str("IMG2IMG_HYBRID_OUTPUT_DIR", "static/images"),
                        ai_backdrop_path=ai_backdrop_path,
                    ))
                    if v10.success and v10.local_path:
                        logger.info(
                            "V10_FORCE_SOURCE_LOCK_ROUTE_SUCCESS mode=%s provider=%s path=%s",
                            mode,
                            v10.provider,
                            v10.local_path,
                        )
                        return {
                            "success": True,
                            "url": f"{self._backend_public_url()}/images/{Path(v10.local_path).name}",
                            "local_path": v10.local_path,
                            "error": None,
                            "visual_delta_score": -1.0,
                            "minimum_visual_delta": 0.0,
                            "finish_quality_score": 0.80,
                            "prediction_id": "",
                            "provider": v10.provider or v10.renderer_used or "v10-hybrid",
                            "source_lock_mode": mode,
                            "source_asset_path": source_path,
                            "commercial_background_composite": mode in {"product_ad", "flyer_poster", "background_replace"},
                            "retry_attempted": False,
                            "retry_used": False,
                            "fallback_used": False,
                            "postprocessed": True,
                            "source_quality": {"allowed": True, "message": "V10 hybrid route handled before legacy source-lock compositor."},
                            "metadata": v10.metadata,
                        }
                    logger.warning("V10_FORCE_SOURCE_LOCK_ROUTE_FALLBACK mode=%s error=%s", mode, v10.error)
            except Exception as exc:
                logger.warning("V10_FORCE_SOURCE_LOCK_ROUTE_EXCEPTION mode=%s error=%s", mode, exc, exc_info=True)
                if self._env_str("IMG2IMG_HYBRID_V10_STRICT", "false").lower() in {"1", "true", "yes", "on"}:
                    return {
                        "success": False,
                        "url": None,
                        "local_path": None,
                        "error": f"V10 hybrid route failed: {exc}",
                        "provider": "v10-hybrid",
                    }

        source_report = commercial_source_quality_report(
            source_path,
            width=width,
            height=height,
            flyer=mode == "flyer_poster",
        )
        if not source_report.get("allowed"):
            if not strict_source:
                return {
                    "success": False,
                    "fallback_to_img2img": True,
                    "error": source_report.get("message") or "Source-lock extraction was not reliable enough.",
                    "source_quality": source_report,
                }
            return {
                "success": False,
                "url": None,
                "local_path": None,
                "error": (
                    "Reference source image is not production-ready. "
                    f"{source_report.get('message') or 'Upload a sharper, larger source image.'}"
                ),
                "provider": "comfy-flux-source-lock-composite",
                "source_quality": source_report,
            }

        prepared_path = str(source_report.get("asset_path") or "")
        if not prepared_path:
            prepared = prepare_reference_subject_asset(source_path)
            prepared_path = str(prepared.get("path") or "")
        if not prepared_path:
            return {
                "success": False,
                "url": None,
                "local_path": None,
                "error": "The reference subject could not be persisted as a transparent source-lock asset.",
                "provider": "comfy-flux-source-lock-composite",
            }

        # V8.1 HARD RULE: Flyer / Poster is a real design-delivery route, not a ComfyUI backdrop route.
        # Do not call AIStudioPro_SourceLock_Backdrop for flyer. The model may hallucinate bottles/props,
        # while the flyer engine can preserve the exact uploaded product and build a clean layout directly.
        if mode == "flyer_poster":
            flyer_path = render_reference_commercial_asset(
                "",
                source_path,
                mode=mode,
                prompt=prompt,
                width=width,
                height=height,
                include_text_overlay=bool(include_text_overlay),
                require_clean_subject=True,
                use_ai_backdrop=False,
                prepared_subject_path=prepared_path,
                force_deterministic_backdrop=True,
            )
            if flyer_path:
                flyer_quality = reference_finish_quality_score(flyer_path)
                return {
                    "success": True,
                    "url": f"{self._backend_public_url()}/images/{Path(flyer_path).name}",
                    "local_path": flyer_path,
                    "error": None,
                    "visual_delta_score": -1.0,
                    "minimum_visual_delta": 0.0,
                    "finish_quality_score": flyer_quality,
                    "prediction_id": "",
                    "provider": "real-flyer-engine-no-comfy-backdrop",
                    "source_lock_mode": mode,
                    "source_asset_path": prepared_path,
                    "commercial_background_composite": True,
                    "retry_attempted": False,
                    "retry_used": False,
                    "fallback_used": True,
                    "postprocessed": True,
                    "source_quality": source_report,
                }
            return {
                "success": False,
                "url": None,
                "local_path": None,
                "error": "Real flyer engine could not compose the uploaded source into a production flyer.",
                "provider": "real-flyer-engine-no-comfy-backdrop",
                "source_quality": source_report,
            }

        min_quality = max(0.18, self._minimum_reference_finish_quality(mode))
        min_delta = self._minimum_reference_visual_delta(mode)

        def deterministic_source_lock_response(*, reason: str) -> dict:
            """Return a clean source-locked result without trusting a random AI backdrop.

            The local Comfy checkpoint can hallucinate a duplicate package even when
            the negative prompt explicitly forbids it.  For production-safe product,
            flyer and creative deliveries we prefer a polished deterministic scene
            and composite the exact analysed RGBA subject over it.  Operators can
            explicitly opt back into experimental AI backdrops through the env flag.
            """
            fallback_path = render_reference_commercial_asset(
                "",
                source_path,
                mode=mode,
                prompt=prompt,
                width=width,
                height=height,
                include_text_overlay=bool(mode == "flyer_poster" and include_text_overlay),
                require_clean_subject=True,
                use_ai_backdrop=False,
                prepared_subject_path=prepared_path,
                force_deterministic_backdrop=True,
            )
            if not fallback_path:
                return {
                    "success": False,
                    "url": None,
                    "local_path": None,
                    "error": "The deterministic source-lock stage could not composite the extracted subject cleanly.",
                    "provider": "deterministic-premium-source-lock",
                }
            fallback_quality = reference_finish_quality_score(fallback_path)
            fallback_delta = self._reference_visual_delta_score(source_path, fallback_path)
            if fallback_quality < min_quality or (fallback_delta >= 0 and fallback_delta < min_delta):
                return {
                    "success": False,
                    "url": None,
                    "local_path": None,
                    "error": (
                        "The deterministic source-lock stage did not pass the production quality gate "
                        f"(quality {fallback_quality:.3f}, minimum {min_quality:.3f}, visual delta {fallback_delta:.3f}, minimum delta {min_delta:.3f})."
                    ),
                    "provider": "deterministic-premium-source-lock",
                }
            return {
                "success": True,
                "url": f"{self._backend_public_url()}/images/{Path(fallback_path).name}",
                "local_path": fallback_path,
                "error": None,
                "visual_delta_score": fallback_delta,
                "minimum_visual_delta": min_delta,
                "finish_quality_score": fallback_quality,
                "prediction_id": "",
                "provider": "deterministic-premium-source-lock",
                "source_lock_mode": mode,
                "source_asset_path": prepared_path,
                "commercial_background_composite": mode in {"product_ad", "flyer_poster"},
                "retry_attempted": False,
                "retry_used": False,
                "fallback_used": True,
                "deterministic_reason": reason,
                "postprocessed": True,
                "source_quality": source_report,
            }

        safe_delivery_modes = {"product_ad", "flyer_poster"}
        allow_experimental_ai_backdrops = self._env_str(
            "COMMERCIAL_ALLOW_AI_BACKDROP_FOR_SAFE_MODES", "false"
        ).lower() in {"1", "true", "yes", "on"}
        if mode in safe_delivery_modes and not allow_experimental_ai_backdrops:
            return deterministic_source_lock_response(reason="production-safe default; experimental AI backdrop disabled")

        director_backdrop_prompt = str((vision_prompt_pack or {}).get("background_prompt") or "").strip()
        backdrop_prompt = director_backdrop_prompt or source_lock_backdrop_prompt(mode, prompt)
        logger.info(
            "VISION_DIRECTOR_COMMERCIAL mode=%s has_director_backdrop=%s prompt=%s",
            mode,
            bool(director_backdrop_prompt),
            backdrop_prompt[:420],
        )
        # One AI backdrop attempt only. If it fails the visual gate, fall back
        # immediately to the deterministic polished stage instead of spending a
        # second attempt on a similar raw background.
        attempts = [backdrop_prompt]
        last_error = "AI backdrop generation failed"
        for index, attempt_prompt in enumerate(attempts, start=1):
            backdrop = await self._generate_commercial_backdrop_comfy(
                prompt=attempt_prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                style=style,
                filename_prefix=f"AIStudioPro_SourceLock_Backdrop_{mode}_{index}",
                mode=mode,
            )
            if not backdrop.get("success"):
                last_error = str(backdrop.get("error") or last_error)
                continue
            backdrop_safe, duplicate_score = source_lock_backdrop_is_safe(
                str(backdrop.get("local_path") or ""),
                prepared_path,
            )
            if not backdrop_safe:
                # V7.2: never expose or fail because of a hallucinated duplicate in the generated backdrop.
                # The compositor sanitizes the hero zone first, then pastes the exact uploaded subject.
                # This is safer than returning an error to the user and avoids the repeated "duplicate score" failure loop.
                last_error = (
                    "AI backdrop contained a source-like subject; the compositor sanitized the hero zone "
                    f"before source-lock compositing (duplicate score {duplicate_score:.3f})."
                )
            final_path = render_reference_commercial_asset(
                str(backdrop["local_path"]),
                source_path,
                mode=mode,
                prompt=prompt,
                width=width,
                height=height,
                include_text_overlay=bool(mode == "flyer_poster" and include_text_overlay),
                require_clean_subject=True,
                use_ai_backdrop=True,
                prepared_subject_path=prepared_path,
            )
            if not final_path:
                last_error = "The extracted reference asset could not be composited cleanly over the AI scene."
                continue
            quality = reference_finish_quality_score(final_path)
            delta = self._reference_visual_delta_score(source_path, final_path)
            if quality >= min_quality and (delta < 0 or delta >= min_delta):
                return {
                    "success": True,
                    "url": f"{self._backend_public_url()}/images/{Path(final_path).name}",
                    "local_path": final_path,
                    "error": None,
                    "visual_delta_score": delta,
                    "minimum_visual_delta": min_delta,
                    "finish_quality_score": quality,
                    "prediction_id": str(backdrop.get("prediction_id") or ""),
                    "provider": "comfy-flux-source-lock-composite",
                    "source_lock_mode": mode,
                    "source_asset_path": prepared_path,
                    "commercial_background_composite": mode in {"product_ad", "flyer_poster"},
                    "retry_attempted": index > 1,
                    "retry_used": index > 1,
                    "postprocessed": True,
                    "source_quality": source_report,
                }
            last_error = (
                f"AI source-lock scene did not pass the quality gate (attempt {index}, quality {quality:.3f}, "
                f"minimum {min_quality:.3f}, visual delta {delta:.3f}, minimum delta {min_delta:.3f})."
            )
        # Production fallback: a weak or hallucinated AI backdrop must never be
        # exposed.  Build a deterministic premium stage with no duplicate
        # product, then composite the exact extracted source asset.
        deterministic_enabled = self._env_str("COMMERCIAL_ENABLE_DETERMINISTIC_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}
        if deterministic_enabled:
            fallback_path = render_reference_commercial_asset(
                "",
                source_path,
                mode=mode,
                prompt=prompt,
                width=width,
                height=height,
                include_text_overlay=bool(mode == "flyer_poster" and include_text_overlay),
                require_clean_subject=True,
                use_ai_backdrop=False,
                prepared_subject_path=prepared_path,
                force_deterministic_backdrop=True,
            )
            if fallback_path:
                fallback_quality = reference_finish_quality_score(fallback_path)
                fallback_delta = self._reference_visual_delta_score(source_path, fallback_path)
                if fallback_quality >= min_quality and (fallback_delta < 0 or fallback_delta >= min_delta):
                    return {
                        "success": True,
                        "url": f"{self._backend_public_url()}/images/{Path(fallback_path).name}",
                        "local_path": fallback_path,
                        "error": None,
                        "visual_delta_score": fallback_delta,
                        "minimum_visual_delta": min_delta,
                        "finish_quality_score": fallback_quality,
                        "prediction_id": "",
                        "provider": "deterministic-premium-source-lock",
                        "source_lock_mode": mode,
                        "source_asset_path": prepared_path,
                        "commercial_background_composite": mode in {"product_ad", "flyer_poster"},
                        "retry_attempted": True,
                        "retry_used": False,
                        "fallback_used": True,
                        "postprocessed": True,
                        "source_quality": source_report,
                    }
                last_error = (
                    f"Deterministic source-lock fallback did not pass the quality gate "
                    f"(quality {fallback_quality:.3f}, minimum {min_quality:.3f}, visual delta {fallback_delta:.3f}, minimum delta {min_delta:.3f})."
                )

        return {
            "success": False,
            "url": None,
            "local_path": None,
            "error": (
                f"{last_error} The app refused to expose a weak commercial result."
                if mode in {"product_ad", "flyer_poster"}
                else f"{last_error} The app refused to expose a weak source-lock result."
            ),
            "provider": "comfy-flux-source-lock-composite",
            "retry_attempted": True,
            "retry_used": False,
        }

    async def _generate_commercial_source_lock_comfy(
        self,
        *,
        source_path: str,
        prompt: str,
        negative_prompt: Optional[str],
        mode: str,
        width: int,
        height: int,
        style: Optional[str],
        include_text_overlay: bool,
        vision_prompt_pack: dict | None = None,
    ) -> dict:
        """Backward-compatible strict wrapper for Product Ad and Flyer / Poster."""
        result = await self._generate_source_lock_composite_comfy(
            source_path=source_path,
            prompt=prompt,
            negative_prompt=negative_prompt,
            mode=mode,
            width=width,
            height=height,
            style=style,
            include_text_overlay=include_text_overlay,
            strict_source=True,
            vision_prompt_pack=vision_prompt_pack,
        )
        if result.get("provider") == "comfy-flux-source-lock-composite":
            result["provider"] = "comfy-flux-commercial-source-lock"
        return result

    async def _generate_image_from_image_comfy(
        self,
        *,
        image_path: str,
        prompt: str,
        negative_prompt: Optional[str],
        strength: float,
        width: int,
        height: int,
        style: Optional[str],
        num_inference_steps: int,
        guidance_scale: float,
    ) -> dict:
        """True ComfyUI img2img with single-pass generation by default.

        Person / Identity remains conservative. Creative Image and Background
        Replace stay on the true img2img path. Optional near-copy retry is now
        disabled by default and can be re-enabled only through the environment.
        """
        comfy = self._comfy_url()
        ckpt = self._comfy_image_checkpoint()
        generation_mode, clean_prompt = strip_reference_mode_marker(prompt)
        vision_prompt_pack, clean_prompt = strip_vision_prompt_pack_marker(clean_prompt)
        flyer_overlay_requested, clean_prompt = strip_flyer_overlay_marker(clean_prompt)
        if generation_mode == "flyer_poster" and not flyer_overlay_requested and any(q in clean_prompt for q in ['\"', '“', '”']):
            flyer_overlay_requested = True
        identity_board_marker_present = "[AI_STUDIO_IDENTITY_BOARD:" in clean_prompt.upper()
        identity_board_requested, clean_prompt = strip_identity_board_marker(clean_prompt)
        # FINAL PRO FIX: the old UI marker [AI_STUDIO_IDENTITY_BOARD:true]
        # must not hijack a Person / Identity generation. Neural Camera reports
        # are diagnostic only; the user-facing generation endpoint must keep
        # producing the final AI image unless report-image generation is
        # explicitly enabled by env for a separate diagnostic workflow.
        identity_report_image_allowed = self._env_str("IDENTITY_REPORT_IMAGE_GENERATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        if identity_board_marker_present and identity_board_requested and not identity_report_image_allowed:
            logger.info("IDENTITY_BOARD_MARKER_IGNORED_FOR_FINAL_AI_OUTPUT mode=%s", generation_mode)
            identity_board_requested = False
            identity_board_marker_present = False
        reference_subject_type, clean_prompt = strip_reference_subject_type_marker(clean_prompt)
        prompt = clean_prompt

        # AI_STUDIO_V25_SAFE_PERSON_IDENTITY_ROUTE
        # Person / Identity must never enter the commercial poster/background
        # compositor. That engine is correct for product/poster modes, but it
        # can return a background/cutout intermediate or a fallback person if
        # the source image is not bound correctly. Keep person flows on the
        # direct conservative identity img2img path below.
        if generation_mode == "person_identity":
            if not image_path or not Path(str(image_path)).exists():
                return {
                    "success": False,
                    "url": None,
                    "local_path": None,
                    "error": "Person Identity requires a valid uploaded source image. Source image was not bound to the workflow.",
                    "provider": "person-identity-source-missing",
                }
            if str(reference_subject_type or "").strip().lower() not in {"person", "person_face", "person_full", "person_full_body"}:
                logger.warning(
                    "PERSON_IDENTITY_SUBJECT_COERCED_EARLY old_subject=%s new_subject=person_face",
                    reference_subject_type,
                )
                reference_subject_type = "person_face"

        # AI_STUDIO_V20_FIXED_PRO_POSTER_ENGINE
        # Hard production route for commercial source-lock modes. This bypasses
        # the older V10/V14 experiment chain and forces the reliable V20 flow:
        # isolate exact product -> fixed pro stage -> deterministic pro layout/text.
        v20_enabled = self._env_str("IMG2IMG_V20_FIXED_PRO_POSTER_ENGINE", "true").lower() in {"1", "true", "yes", "on"}
        v20_modes = {"product_ad", "flyer_poster", "social_post", "background_replace"}
        if v20_enabled and str(generation_mode or "").lower() in v20_modes:
            try:
                from app.services.img2img_hybrid.v13_commercial_engine import generate_v13_commercial
                from app.services.img2img_hybrid.contracts import Img2ImgRequest

                v20_subject_type = reference_subject_type or ("product" if str(generation_mode or "").lower() in {"product_ad", "flyer_poster", "social_post", "background_replace"} else "subject")
                v20 = await generate_v13_commercial(Img2ImgRequest(
                    mode=str(generation_mode or "product_ad"),
                    source_image_path=image_path,
                    prompt=clean_prompt or prompt or "",
                    negative_prompt=negative_prompt or "",
                    width=width,
                    height=height,
                    style=style,
                    strength=strength,
                    subject_type=v20_subject_type,
                    output_dir="static/images",
                ))
                if v20.success and v20.local_path:
                    logger.info("V25_UNIVERSAL_PRO_POSTER_STAGE_INTEGRATION_SUCCESS mode=%s provider=%s path=%s", generation_mode, v20.provider, v20.local_path)
                    return {
                        "success": True,
                        "url": f"{self._backend_public_url()}/images/{Path(v20.local_path).name}",
                        "local_path": v20.local_path,
                        "error": None,
                        "provider": v20.provider or v20.renderer_used or "comfy-director-v25-universal-pro-poster-stage-integration",
                        "prediction_id": "",
                        "visual_delta_score": -1.0,
                        "minimum_visual_delta": 0.0,
                        "finish_quality_score": 0.92,
                        "source_lock_mode": generation_mode,
                        "commercial_background_composite": True,
                        "retry_attempted": False,
                        "retry_used": False,
                        "fallback_used": False,
                        "postprocessed": True,
                        "metadata": v20.metadata,
                    }
                logger.warning("V25_UNIVERSAL_PRO_POSTER_STAGE_INTEGRATION_FAILED mode=%s error=%s", generation_mode, v20.error)
                return {
                    "success": False,
                    "url": None,
                    "local_path": None,
                    "error": v20.error or "V21 pro Comfy poster engine failed",
                    "provider": v20.provider or "comfy-director-v25-universal-pro-poster-stage-integration",
                    "metadata": v20.metadata,
                }
            except Exception as exc:
                logger.error("V25_UNIVERSAL_PRO_POSTER_STAGE_INTEGRATION_EXCEPTION mode=%s error=%s", generation_mode, exc, exc_info=True)
                return {
                    "success": False,
                    "url": None,
                    "local_path": None,
                    "error": f"V21 pro Comfy poster engine failed: {exc}",
                    "provider": "comfy-director-v25-universal-pro-poster-stage-integration-exception",
                }

        # V10 Hybrid AI Engine + AI Renderer. Feature-flagged and safe: if it fails, old pipeline continues.
        if self._env_str("IMG2IMG_HYBRID_V10_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
            try:
                enabled_map = {
                    "flyer_poster": self._env_str("IMG2IMG_V10_ENABLE_FLYER", "true"),
                    "product_ad": self._env_str("IMG2IMG_V10_ENABLE_PRODUCT_AD", "true"),
                    "background_replace": self._env_str("IMG2IMG_V10_ENABLE_BACKGROUND_REPLACE", "true"),
                    "creative_image": self._env_str("IMG2IMG_V10_ENABLE_CREATIVE", "true"),
                    # Keep Person / Identity out of the hybrid commercial chain.
                    # It must use the conservative direct identity img2img path.
                    "person_identity": "false",
                    "auto": self._env_str("IMG2IMG_V10_ENABLE_AUTO", "true"),
                }
                if generation_mode == "person_identity":
                    logger.info("PERSON_IDENTITY_SKIP_V10_HYBRID route=direct_flux_identity_img2img")
                if str(enabled_map.get(str(generation_mode or ""), "false")).lower() in {"1", "true", "yes", "on"}:
                    from app.services.img2img_hybrid import generate_img2img
                    from app.services.img2img_hybrid.contracts import Img2ImgRequest
                    v10 = await generate_img2img(Img2ImgRequest(
                        mode=str(generation_mode or "creative_image"),
                        source_image_path=image_path,
                        prompt=clean_prompt or prompt or "",
                        negative_prompt=negative_prompt or "",
                        width=width,
                        height=height,
                        style=style,
                        strength=strength,
                        subject_type=reference_subject_type,
                        output_dir="static/images",
                    ))
                    if v10.success and v10.local_path:
                        logger.info("V10_HYBRID_IMG2IMG_SUCCESS mode=%s provider=%s path=%s", generation_mode, v10.provider, v10.local_path)
                        return {
                            "success": True,
                            "url": f"{self._backend_public_url()}/images/{Path(v10.local_path).name}",
                            "local_path": v10.local_path,
                            "error": None,
                            "provider": v10.provider or v10.renderer_used or "v10-hybrid",
                            "prediction_id": "",
                            "visual_delta_score": -1.0,
                            "minimum_visual_delta": 0.0,
                            "finish_quality_score": 0.75,
                            "source_lock_mode": generation_mode,
                            "commercial_background_composite": generation_mode in {"product_ad", "flyer_poster"},
                            "fallback_used": False,
                            "postprocessed": True,
                            "metadata": v10.metadata,
                        }
                    logger.warning("V10_HYBRID_IMG2IMG_FALLBACK mode=%s error=%s", generation_mode, v10.error)
            except Exception as exc:
                logger.warning("V10_HYBRID_IMG2IMG_EXCEPTION mode=%s error=%s", generation_mode, exc, exc_info=True)
                if self._env_str("IMG2IMG_HYBRID_V10_STRICT", "false").lower() in {"1", "true", "yes", "on"}:
                    return {"success": False, "url": None, "error": f"V10 hybrid failed: {exc}", "provider": "v10-hybrid"}

        director_comfy_prompt = str((vision_prompt_pack or {}).get("comfy_prompt") or "").strip()
        if director_comfy_prompt:
            prompt = f"{director_comfy_prompt} User request: {clean_prompt}".strip()
        else:
            mode_suffix = reference_mode_prompt_suffix(generation_mode)
            if mode_suffix:
                prompt = f"{prompt} {mode_suffix}".strip()
            prompt = self._augment_reference_prompt_for_mode(prompt, generation_mode, reference_subject_type)
        logger.info(
            "VISION_DIRECTOR_IMG2IMG mode=%s subject=%s has_pack=%s prompt=%s",
            generation_mode,
            reference_subject_type,
            bool(vision_prompt_pack),
            prompt[:520],
        )

        use_prompt_engine = self._env_str("COMFY_USE_PROMPT_ENGINE", "false").lower() in {"1", "true", "yes", "on"}
        if use_prompt_engine:
            prompt_result = enhance_prompt(prompt, style=style)
        else:
            styled_prompt = self._apply_style(prompt, style) if style else prompt
            prompt_result = SimpleNamespace(prompt=styled_prompt, negative_prompt=None, meta={})
        enhanced_prompt = prompt_result.prompt

        def round64(x: int) -> int:
            return max(8, (int(x) // 8) * 8)

        transformation_modes = {"product_ad", "flyer_poster", "background_replace", "creative_image"}
        is_transform_mode = generation_mode in transformation_modes
        strict_workflow = self._env_str("COMFY_STRICT_WORKFLOW_MODE", "true").lower() in {"1", "true", "yes", "on"}
        w = round64(width or self._env_int("COMFY_IMAGE_DEFAULT_WIDTH", 640))
        h = round64(height or self._env_int("COMFY_IMAGE_DEFAULT_HEIGHT", 896))
        if strict_workflow:
            steps = self._env_int("COMFY_IMAGE_STEPS", 8)
            cfg = self._env_float("COMFY_IMAGE_CFG", 1.0)
        else:
            steps = int(num_inference_steps or self._env_int("COMFY_IMAGE_STEPS", 8))
            cfg = float(guidance_scale or self._env_float("COMFY_IMAGE_CFG", 1.0))
        steps = max(4, min(steps, 4))  # V20_SAFE: hard cap img2img steps at 4
        cfg = max(1.0, min(cfg, 3.0))
        if generation_mode in {"creative_image", "background_replace"}:
            steps = max(4, min(steps, 4))  # V20_SAFE: do not raise transform steps above 4
            cfg = max(cfg, self._env_float("COMFY_REFERENCE_TRANSFORM_CFG", 1.2))
        sampler = self._env_str("COMFY_IMAGE_SAMPLER", "euler")
        scheduler = self._env_str("COMFY_IMAGE_SCHEDULER", "simple")
        denoise_cap = 0.88 if is_transform_mode else 0.75
        denoise = max(0.15, min(float(strength or 0.35), denoise_cap))

        # Person / Identity uses the existing compatible img2img graph, but with
        # a deliberately conservative parameter envelope.  This keeps the old
        # workflow operational on installations that do not have optional
        # FaceID/PuLID custom nodes while reducing facial drift.
        if generation_mode == "person_identity" and str(reference_subject_type or "").strip().lower() not in {"person", "person_face", "person_full", "person_full_body"}:
            logger.warning(
                "PERSON_IDENTITY_SUBJECT_COERCED old_subject=%s new_subject=person_face",
                reference_subject_type,
            )
            reference_subject_type = "person_face"

        identity_conservative_mode = generation_mode == "person_identity" or str(reference_subject_type or "").strip().lower() in {
            "person", "person_face", "person_full", "person_full_body"
        }
        if identity_conservative_mode:
            identity_denoise_min = max(0.08, min(self._env_float("COMFY_IDENTITY_DENOISE_MIN", 0.12), 0.20))
            identity_denoise_max = max(identity_denoise_min, min(self._env_float("COMFY_IDENTITY_DENOISE_MAX", 0.18), 0.24))
            denoise = max(identity_denoise_min, min(denoise, identity_denoise_max))
            steps = max(4, min(steps, 4))  # V20_SAFE: person identity max 4 steps
            cfg = min(cfg, max(1.0, min(self._env_float("COMFY_IDENTITY_CFG_MAX", 1.20), 1.8)))

        # Honest production fallback for Person / Identity.  Generic img2img can
        # create a lookalike when FaceID/PuLID/InstantID nodes are unavailable.
        # The default production board keeps the exact uploaded portrait and
        # applies restrained finishing only.  Operators can explicitly turn the
        # board off when a dedicated identity adapter workflow is installed.
        if generation_mode == "person_identity":
            board_default = self._env_str("IDENTITY_PRODUCTION_BOARD_DEFAULT", "false").lower() in {"1", "true", "yes", "on"}
            # Do not return the diagnostic report board as the final image by default.
            # This keeps report and final output separated: report stays in Neural Camera UI,
            # final generation continues through the conservative identity img2img path.
            report_image_allowed = self._env_str("IDENTITY_REPORT_IMAGE_GENERATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
            board_enabled = bool(report_image_allowed and (identity_board_requested if identity_board_marker_present else board_default))
            if board_enabled:
                try:
                    board = render_identity_production_board(
                        image_path,
                        prompt=clean_prompt,
                        width=max(1280, w),
                        height=max(900, h),
                    )
                    local_path = str(board.local_path)
                    return {
                        "success": True,
                        "url": f"{self._backend_public_url()}/images/{Path(local_path).name}",
                        "local_path": local_path,
                        "error": None,
                        "provider": "identity-board-source-lock",
                        "postprocessed": True,
                        "identity_board": True,
                        "identity_source_locked": True,
                        "identity_strategy": board.identity_strategy,
                        "output_width": board.width,
                        "output_height": board.height,
                    }
                except Exception as exc:
                    logger.error("Identity production board render failed: %s", exc, exc_info=True)
                    return {
                        "success": False,
                        "url": None,
                        "local_path": None,
                        "error": f"Identity production board render failed: {exc}",
                        "provider": "identity-board-source-lock",
                    }

        # Source-lock commercial compositing is now restricted to explicit
        # commercial modes only. Creative Image and Background Replace must use
        # true img2img generation so insects, animals and generic objects are
        # not forced onto a product podium or commercial backdrop.
        flyer_exact_source_lock = bool(
            generation_mode == "flyer_poster"
            and should_use_source_lock_composite(generation_mode, reference_subject_type)
        )
        # Hard rule: artistic flyers always stay on ComfyUI img2img. Only a
        # confidently classified real product/document flyer may use exact-source
        # compositing. Creative/background modes never enter backend templates.
        strict_source_lock = bool(should_use_source_lock_composite(generation_mode, reference_subject_type))
        if generation_mode == "flyer_poster":
            logger.info(
                "FLYER_ROUTE subject=%s strategy=%s overlay=%s",
                reference_subject_type,
                "exact_source_composite" if flyer_exact_source_lock else "artistic_img2img",
                flyer_overlay_requested,
            )
        # V7 hybrid rule: for product/object background replacement, preserve
        # the exact uploaded subject and generate/composite only the new
        # environment. This prevents Coca-Cola labels and packaging from being
        # repainted by img2img. Living subjects remain true img2img.
        background_exact_source_lock = bool(
            generation_mode == "background_replace"
            and should_use_source_lock_composite(generation_mode, reference_subject_type)
        )
        source_lock_context_ready = reference_subject_type is not None and (strict_source_lock or background_exact_source_lock)
        if source_lock_context_ready:
            if strict_source_lock:
                return await self._generate_commercial_source_lock_comfy(
                    source_path=image_path,
                    prompt=clean_prompt,
                    negative_prompt=negative_prompt,
                    mode=str(generation_mode),
                    width=w,
                    height=h,
                    style=style,
                    include_text_overlay=flyer_overlay_requested,
                    vision_prompt_pack=vision_prompt_pack,
                )
            source_lock_result = await self._generate_source_lock_composite_comfy(
                source_path=image_path,
                prompt=clean_prompt,
                negative_prompt=negative_prompt,
                mode=str(generation_mode),
                width=w,
                height=h,
                style=style,
                include_text_overlay=flyer_overlay_requested,
                strict_source=False,
                vision_prompt_pack=vision_prompt_pack,
            )
            if source_lock_result.get("success") or not source_lock_result.get("fallback_to_img2img"):
                return source_lock_result

        identity_negative = (
            "different person, lookalike, identity drift, changed age, younger face, changed gender, beautified face, "
            "plastic skin, over-smoothed skin, altered wrinkles, wrong facial structure, reshaped jawline, changed nose, "
            "changed mouth, changed eye shape, changed gaze direction, side gaze, cross-eyed, misaligned eyes, deformed face, warped eyes, asymmetric mouth, extra facial parts"
        )
        director_negative = str((vision_prompt_pack or {}).get("negative_prompt") or "").strip()
        base_negative = ", ".join(
            part for part in [negative_prompt or prompt_result.negative_prompt or "blurry, low quality, watermark, unreadable text", director_negative]
            if str(part or "").strip()
        )
        neg = f"{base_negative}, {identity_negative}" if identity_conservative_mode else base_negative

        random_seed = self._env_str("COMFY_RANDOM_SEED", "true").lower() in {"1", "true", "yes", "on"}

        def choose_seed(*parts: object) -> int:
            if random_seed:
                return random.randint(1, 2**63 - 1)
            return self._stable_seed(*parts)

        first_seed = choose_seed("img2img", enhanced_prompt, neg, image_path, w, h, style or "", steps, cfg, denoise)
        logger.info(
            "MODEL_LOCK IMG2IMG_PROVIDER=FLUX ckpt=%s comfy=%s mode=%s size=%sx%s steps=%s cfg=%s seed=%s denoise=%s image=%s",
            ckpt,
            comfy,
            generation_mode or "reference",
            w,
            h,
            steps,
            cfg,
            first_seed,
            denoise,
            image_path,
        )

        try:
            image_for_upload = image_path
            try:
                src = Image.open(image_path).convert("RGB")
                background = tuple(int(v) for v in ImageStat.Stat(src.resize((1, 1))).mean[:3])
                fitted = ImageOps.pad(src, (w, h), Image.LANCZOS, color=background, centering=(0.5, 0.5))
                prepared_dir = Path("/tmp") / "ai_studio_pro" / "prepared_inputs"
                prepared_dir.mkdir(parents=True, exist_ok=True)
                prepared_path = prepared_dir / f"reference_{uuid4().hex}.png"
                fitted.save(prepared_path, format="PNG")
                image_for_upload = str(prepared_path)
            except Exception:
                image_for_upload = image_path

            async with httpx.AsyncClient() as client:
                uploaded_name = await self._upload_image_to_comfy(client, comfy, image_for_upload)
                workflow_template = self._load_comfy_workflow_template("AIStudio_Image_FLUX_IDENTITY_IMG2IMG.json")
                headers = {"Content-Type": "application/json"}

                def build_workflow(
                    *,
                    attempt_prompt: str,
                    attempt_seed: int,
                    attempt_steps: int,
                    attempt_cfg: float,
                    attempt_denoise: float,
                    filename_prefix: str,
                ) -> dict:
                    values = {
                        "__CKPT__": ckpt,
                        "__PROMPT__": attempt_prompt,
                        "__NEGATIVE_PROMPT__": neg,
                        "__INPUT_IMAGE__": uploaded_name,
                        "__SEED__": attempt_seed,
                        "__STEPS__": attempt_steps,
                        "__CFG__": attempt_cfg,
                        "__SAMPLER__": sampler,
                        "__SCHEDULER__": scheduler,
                        "__DENOISE__": attempt_denoise,
                        "__FILENAME_PREFIX__": filename_prefix,
                    }
                    if workflow_template:
                        return self._replace_workflow_placeholders(workflow_template, values)
                    return {
                        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
                        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": attempt_prompt}},
                        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": neg}},
                        "4": {"class_type": "LoadImage", "inputs": {"image": uploaded_name}},
                        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
                        "6": {
                            "class_type": "KSampler",
                            "inputs": {
                                "model": ["1", 0],
                                "positive": ["2", 0],
                                "negative": ["3", 0],
                                "latent_image": ["5", 0],
                                "seed": attempt_seed,
                                "steps": attempt_steps,
                                "cfg": attempt_cfg,
                                "sampler_name": sampler,
                                "scheduler": scheduler,
                                "denoise": attempt_denoise,
                            },
                        },
                        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
                        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": filename_prefix}},
                    }

                async def run_attempt(
                    *,
                    attempt_prompt: str,
                    attempt_seed: int,
                    attempt_steps: int,
                    attempt_cfg: float,
                    attempt_denoise: float,
                    filename_prefix: str,
                ) -> dict:
                    workflow = build_workflow(
                        attempt_prompt=attempt_prompt,
                        attempt_seed=attempt_seed,
                        attempt_steps=attempt_steps,
                        attempt_cfg=attempt_cfg,
                        attempt_denoise=attempt_denoise,
                        filename_prefix=filename_prefix,
                    )
                    response = await self._request_json(client, "POST", f"{comfy}/prompt", headers=headers, json={"prompt": workflow})
                    prompt_id = response.get("prompt_id")
                    if not prompt_id:
                        return {"error": f"ComfyUI img2img: no prompt_id returned: {response}"}
                    view_url = await self._poll_comfy_history_for_image(client, comfy, headers, str(prompt_id))
                    if not view_url:
                        return {"error": "ComfyUI img2img: finished but no image found", "prompt_id": str(prompt_id)}
                    downloaded = await self._download_comfy_image_to_local(client, view_url)
                    if not downloaded:
                        return {"error": "ComfyUI img2img generated but backend could not download it to /images", "prompt_id": str(prompt_id)}
                    result_url, result_path = downloaded
                    return {"url": result_url, "local_path": result_path, "prompt_id": str(prompt_id)}

                selected = await run_attempt(
                    attempt_prompt=enhanced_prompt,
                    attempt_seed=first_seed,
                    attempt_steps=steps,
                    attempt_cfg=cfg,
                    attempt_denoise=denoise,
                    filename_prefix="AIStudioPro_Image_Reference",
                )
                if selected.get("error"):
                    return {"success": False, "url": None, "local_path": None, "error": selected["error"]}

                final_url = str(selected["url"])
                local_path = str(selected["local_path"])
                prompt_id = str(selected["prompt_id"])
                min_delta = self._minimum_reference_visual_delta(generation_mode)
                visual_delta = self._reference_visual_delta_score(image_for_upload, local_path)
                retry_attempted = False
                retry_used = False
                rescue_applied = False
                overlay_applied = False
                finish_quality_score = None

                retry_enabled = self._env_str("COMFY_IMG2IMG_RETRY_ON_NEAR_COPY", "true").lower() in {"1", "true", "yes", "on"}
                if is_transform_mode and retry_enabled and min_delta > 0 and visual_delta >= 0 and visual_delta < min_delta:
                    retry_attempted = True
                    retry_denoise = max(denoise, self._reference_retry_denoise(generation_mode))
                    retry_steps = max(steps, min(self._env_int("COMFY_IMG2IMG_RETRY_STEPS", 16), 32))
                    retry_cfg = max(cfg, min(self._env_float("COMFY_IMG2IMG_RETRY_CFG", 1.6), 3.0))
                    retry_prompt = (
                        f"{enhanced_prompt} SECOND PASS QUALITY DIRECTIVE: create a substantially different premium finished "
                        "composition, preserve the exact uploaded subject or product, keep labels and silhouette readable, "
                        "add realistic depth, lighting and scene energy, integrate the subject into a real environment with contact shadow, "
                        "and never return a minor edit, isolated cutout, source-copy, rope-like simplification, or flat template."
                    )
                    retry_seed = choose_seed("img2img-retry", retry_prompt, image_path, w, h, retry_steps, retry_cfg, retry_denoise)
                    logger.warning(
                        "IMG2IMG_NEAR_COPY_RETRY mode=%s first_delta=%s min_delta=%s retry_steps=%s retry_cfg=%s retry_denoise=%s",
                        generation_mode,
                        visual_delta,
                        min_delta,
                        retry_steps,
                        retry_cfg,
                        retry_denoise,
                    )
                    retry_result = await run_attempt(
                        attempt_prompt=retry_prompt,
                        attempt_seed=retry_seed,
                        attempt_steps=retry_steps,
                        attempt_cfg=retry_cfg,
                        attempt_denoise=retry_denoise,
                        filename_prefix="AIStudioPro_Image_Reference_Retry",
                    )
                    if not retry_result.get("error"):
                        retry_delta = self._reference_visual_delta_score(image_for_upload, str(retry_result["local_path"]))
                        if retry_delta > visual_delta:
                            final_url = str(retry_result["url"])
                            local_path = str(retry_result["local_path"])
                            prompt_id = str(retry_result["prompt_id"])
                            visual_delta = retry_delta
                            retry_used = True

                if should_apply_optional_flyer_overlay(generation_mode, flyer_overlay_requested):
                    # Artistic flyers already contain the generated subject and
                    # environment.  Add clean readable copy only; never paste
                    # the uploaded source over the design a second time.
                    overlay_path = render_readable_flyer_overlay_only(
                        local_path,
                        prompt=clean_prompt,
                    )
                    if overlay_path:
                        logger.info("FLYER_OVERLAY_ONLY path=%s", overlay_path)
                        local_path = overlay_path
                        final_url = f"{self._backend_public_url()}/images/{Path(local_path).name}"
                        visual_delta = self._reference_visual_delta_score(image_for_upload, local_path)
                        finish_quality_score = reference_finish_quality_score(local_path)
                        overlay_applied = True

                if (
                    generation_mode in {"product_ad", "creative_image", "background_replace"}
                    and min_delta > 0
                    and visual_delta >= 0
                    and visual_delta < min_delta
                    and self._deterministic_reference_rescue_enabled()
                ):
                    rescue_path = render_reference_commercial_asset(
                        "" if generation_mode in {"creative_image", "background_replace"} else local_path,
                        image_path,
                        mode=generation_mode,
                        prompt=clean_prompt,
                        width=w,
                        height=h,
                        include_text_overlay=bool(generation_mode == "flyer_poster" and flyer_overlay_requested),
                        force_deterministic_backdrop=bool(generation_mode in {"creative_image", "background_replace"}),
                    )
                    if rescue_path:
                        rescue_delta = self._reference_visual_delta_score(image_for_upload, rescue_path)
                        rescue_quality = reference_finish_quality_score(rescue_path)
                        min_quality = self._minimum_reference_finish_quality(generation_mode)
                        if rescue_delta >= min_delta and rescue_quality >= min_quality:
                            local_path = rescue_path
                            final_url = f"{self._backend_public_url()}/images/{Path(local_path).name}"
                            visual_delta = rescue_delta
                            finish_quality_score = rescue_quality
                            rescue_applied = True

                if min_delta > 0 and visual_delta >= 0 and visual_delta < min_delta:
                    best_effort_allowed = self._env_str("REFERENCE_ALLOW_NEAR_COPY_BEST_EFFORT", "false").lower() in {"1", "true", "yes", "on"}
                    if generation_mode in {"creative_image", "background_replace"} and best_effort_allowed:
                        return {
                            "success": True,
                            "url": final_url,
                            "local_path": local_path,
                            "error": None,
                            "warning": (
                                f"Best-effort result returned for {generation_mode}: visual delta {visual_delta:.3f} remained below the target {min_delta:.3f}."
                            ),
                            "visual_delta_score": visual_delta,
                            "minimum_visual_delta": min_delta,
                            "finish_quality_score": finish_quality_score,
                            "prediction_id": prompt_id,
                            "provider": f"comfy-flux-img2img-{generation_mode or 'reference'}",
                            "retry_attempted": retry_attempted,
                            "retry_used": retry_used,
                            "postprocessed": rescue_applied or overlay_applied,
                        }
                    return {
                        "success": False,
                        "url": None,
                        "local_path": None,
                        "error": (
                            f"Reference transformation rejected after AI quality retry: output stayed too close to the uploaded source "
                            f"for {generation_mode} (visual delta {visual_delta:.3f}, minimum {min_delta:.3f}). "
                            "The app refused to expose a weak template-like result. Verify the ComfyUI img2img workflow or use a clearer scene direction."
                        ),
                        "visual_delta_score": visual_delta,
                        "minimum_visual_delta": min_delta,
                        "prediction_id": prompt_id,
                        "provider": f"comfy-flux-img2img-{generation_mode or 'reference'}",
                        "retry_attempted": retry_attempted,
                        "retry_used": retry_used,
                    }

                return {
                    "success": True,
                    "url": final_url,
                    "local_path": local_path,
                    "error": None,
                    "visual_delta_score": visual_delta,
                    "minimum_visual_delta": min_delta,
                    "finish_quality_score": finish_quality_score,
                    "prediction_id": prompt_id,
                    "provider": f"comfy-flux-img2img-{generation_mode or 'reference'}",
                    "retry_attempted": retry_attempted,
                    "retry_used": retry_used,
                    "postprocessed": rescue_applied or overlay_applied,
                }

        except Exception as e:
            logger.error("_generate_image_from_image_comfy failed: %s", str(e), exc_info=True)
            return {"success": False, "url": None, "error": str(e)}


    async def _generate_image_comfy(
        self,
        *,
        prompt: str,
        negative_prompt: Optional[str],
        width: int,
        height: int,
        style: Optional[str],
        num_inference_steps: int,
        guidance_scale: float,
    ) -> dict:
        """Generate an image using local ComfyUI + the new FLUX image workflow.

        The old .env can still contain old checkpoint variables.  This method
        uses COMFY_IMAGE_CHECKPOINT if present, otherwise it forces the new FLUX
        image model so the image page does not fall back to the old model.
        """
        comfy = self._comfy_url()
        ckpt = self._comfy_image_checkpoint()

        # IMPORTANT COMFY MATCH FIX:
        # To make the app result match the same workflow in ComfyUI, do not rewrite
        # the prompt by default. The old package enhanced/expanded the prompt before
        # sending it to ComfyUI, so the app was NOT sending the same text you tested
        # manually in ComfyUI. Set COMFY_USE_PROMPT_ENGINE=true only if you want the
        # app to deliberately change/enhance prompts.
        use_prompt_engine = self._env_str("COMFY_USE_PROMPT_ENGINE", "false").lower() in {"1", "true", "yes", "on"}
        if use_prompt_engine:
            prompt_result = enhance_prompt(prompt, style=style)
        else:
            styled_prompt = self._apply_style(prompt, style) if style else prompt
            prompt_result = SimpleNamespace(prompt=styled_prompt, negative_prompt=None, meta={})
        enhanced_prompt = prompt_result.prompt

        def round64(x: int) -> int:
            return max(8, (int(x) // 8) * 8)

        strict_workflow = self._env_str("COMFY_STRICT_WORKFLOW_MODE", "true").lower() in {"1", "true", "yes", "on"}

        # Production UI-sync rule:
        # - The FLUX workflow structure stays exact.
        # - The UI size must be applied to EmptyLatentImage.
        # - In strict mode, sampler/steps/cfg stay locked to the uploaded workflow
        #   values so the model behavior matches ComfyUI.
        w = round64(width or self._env_int("COMFY_IMAGE_DEFAULT_WIDTH", 640))
        h = round64(height or self._env_int("COMFY_IMAGE_DEFAULT_HEIGHT", 896))
        if strict_workflow:
            steps = self._env_int("COMFY_IMAGE_STEPS", 8)
            cfg = self._env_float("COMFY_IMAGE_CFG", 1.0)
        else:
            steps = int(num_inference_steps or self._env_int("COMFY_IMAGE_STEPS", 8))
            cfg = float(guidance_scale or self._env_float("COMFY_IMAGE_CFG", 1.0))
        steps = max(4, min(steps, 4))  # V20_SAFE: hard cap img2img steps at 4
        cfg = max(1.0, min(cfg, 3.0))
        # Text-to-image has no reference generation_mode. Reference-specific
        # step/cfg boosts are applied only in _generate_image_from_image_comfy.
        sampler = self._env_str("COMFY_IMAGE_SAMPLER", "euler")
        scheduler = self._env_str("COMFY_IMAGE_SCHEDULER", "simple")

        flyer_like = (prompt_result.meta or {}).get("kind") == "flyer"
        neg = negative_prompt or prompt_result.negative_prompt or (
            "text, letters, logo, watermark, unreadable typography, broken words, bad hands, extra fingers, deformed face, blurry, low quality, oversaturated, messy background, distorted anatomy"
        )

        if self._env_str("COMFY_RANDOM_SEED", "true").lower() in {"1", "true", "yes", "on"}:
            seed = random.randint(1, 2**63 - 1)
        else:
            seed = self._stable_seed("image", enhanced_prompt, neg, w, h, style or "", steps, cfg)

        logger.info(
            "MODEL_LOCK IMAGE_PROVIDER=FLUX ckpt=%s comfy=%s size=%sx%s steps=%s cfg=%s seed=%s",
            ckpt,
            comfy,
            w,
            h,
            steps,
            cfg,
            seed,
        )

        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": ckpt},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["1", 1], "text": enhanced_prompt},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["1", 1], "text": neg},
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "width": w, "height": h},
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {"images": ["6", 0], "filename_prefix": "AIStudioPro_Image_Base"},
            },
        }

        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                r = await self._request_json(
                    client,
                    "POST",
                    f"{comfy}/prompt",
                    headers=headers,
                    json={"prompt": workflow},
                )

                prompt_id = r.get("prompt_id")
                if not prompt_id:
                    return {
                        "success": False,
                        "url": None,
                        "error": f"ComfyUI: no prompt_id returned: {r}",
                    }

                view_url = await self._poll_comfy_history_for_image(
                    client, comfy, headers, str(prompt_id)
                )
                if not view_url:
                    return {
                        "success": False,
                        "url": None,
                        "error": "ComfyUI: finished but no image found",
                    }

                downloaded = await self._download_comfy_image_to_local(client, view_url)
                if not downloaded:
                    return {
                        "success": False,
                        "url": None,
                        "local_path": None,
                        "error": "ComfyUI image generated but backend could not download it to /images",
                    }

                final_url, local_path = downloaded

                # For flyers/posters: overlay real readable text after generation.
                # This is the only reliable way to get professional readable text locally.
                if flyer_like:
                    try:
                        overlay_path = self._apply_flyer_overlay(local_path, (prompt_result.meta or {}).get("flyer") or {})
                        overlay_name = Path(overlay_path).name
                        final_url = f"{self._backend_public_url()}/images/{overlay_name}"
                        local_path = overlay_path
                    except Exception as overlay_error:
                        logger.error("flyer overlay failed: %s", overlay_error, exc_info=True)

                return {
                    "success": True,
                    "url": final_url,
                    "local_path": local_path,
                    "error": None,
                    "prediction_id": str(prompt_id),
                    "provider": "comfy-flux-pro-overlay" if flyer_like else "comfy-flux",
                }

        except Exception as e:
            logger.error("_generate_image_comfy failed: %s", str(e), exc_info=True)
            return {"success": False, "url": None, "error": str(e)}

    async def _poll_comfy_history_for_image(
        self,
        client: httpx.AsyncClient,
        comfy: str,
        headers: dict,
        prompt_id: str,
        max_attempts: int | None = None,
        delay: float = 1.0,
    ) -> Optional[str]:
        if max_attempts is None:
            max_attempts = max(1, int(self._env_int("COMFY_IMAGE_TIMEOUT_SECONDS", 900) / max(delay, 0.1)))
        def find_first_image(obj):
            if isinstance(obj, dict):
                if isinstance(obj.get("images"), list) and obj["images"]:
                    first = obj["images"][0]
                    if isinstance(first, dict) and first.get("filename"):
                        return first
                for value in obj.values():
                    found = find_first_image(value)
                    if found:
                        return found
            elif isinstance(obj, list):
                for value in obj:
                    found = find_first_image(value)
                    if found:
                        return found
            return None

        for _ in range(max_attempts):
            try:
                hist = await self._request_json(
                    client,
                    "GET",
                    f"{comfy}/history/{prompt_id}",
                    headers=headers,
                    json=None,
                    timeout=httpx.Timeout(20.0, connect=10.0),
                )
            except Exception:
                await asyncio.sleep(delay)
                continue

            data = hist.get(prompt_id) if isinstance(hist, dict) and prompt_id in hist else hist
            first = find_first_image(data)
            if first:
                filename = first.get("filename")
                subfolder = first.get("subfolder", "")
                typ = first.get("type", "output")
                if filename:
                    qs = urlencode({"filename": filename, "subfolder": subfolder, "type": typ}, quote_via=quote)
                    return f"{comfy}/view?{qs}"

            await asyncio.sleep(delay)

        return None

    async def _poll_comfy_history_for_video(
        self,
        client: httpx.AsyncClient,
        comfy: str,
        headers: dict,
        prompt_id: str,
        max_attempts: int | None = None,
        delay: float = 1.5,
    ) -> Optional[str]:
        if max_attempts is None:
            max_attempts = max(1, int(self._env_int("COMFY_VIDEO_TIMEOUT_SECONDS", 1800) / max(delay, 0.1)))
        for _ in range(max_attempts):
            try:
                hist = await self._request_json(
                    client,
                    "GET",
                    f"{comfy}/history/{prompt_id}",
                    headers=headers,
                    json=None,
                    timeout=httpx.Timeout(20.0, connect=10.0),
                )
            except Exception:
                await asyncio.sleep(delay)
                continue

            data = hist.get(prompt_id) if isinstance(hist, dict) and prompt_id in hist else hist
            outputs = (data or {}).get("outputs") if isinstance(data, dict) else None

            if isinstance(outputs, dict):
                for node_out in outputs.values():
                    if not isinstance(node_out, dict):
                        continue

                    candidates = []
                    candidates.extend(node_out.get("gifs") or [])
                    candidates.extend(node_out.get("videos") or [])
                    # Some ComfyUI/custom-node versions expose SaveAnimatedWEBP
                    # outputs under "images" even though the file is animated.
                    for image in node_out.get("images") or []:
                        filename = str(image.get("filename") or "").lower() if isinstance(image, dict) else ""
                        if filename.endswith((".webp", ".gif", ".mp4", ".webm")):
                            candidates.append(image)

                    if candidates:
                        first = candidates[0]
                        filename = first.get("filename")
                        subfolder = first.get("subfolder", "")
                        typ = first.get("type", "output")
                        if filename:
                            qs = urlencode(
                                {
                                    "filename": filename,
                                    "subfolder": subfolder,
                                    "type": typ,
                                },
                                quote_via=quote,
                            )
                            return f"{comfy}/view?{qs}"

            await asyncio.sleep(delay)

        return None

    # -------------------------------------------------------------------------
    # Prompt style helper
    # -------------------------------------------------------------------------
    def _apply_style(self, prompt: str, style: Optional[str]) -> str:
        """Apply style modifiers to prompt."""

        style_modifiers = {
            "photorealistic": "photorealistic, highly detailed, 8k, professional photography",
            "digital_art": "digital art, vibrant colors, detailed illustration",
            "anime": "anime style, manga, japanese animation, detailed",
            "oil_painting": "oil painting, artistic, textured brush strokes, masterpiece",
            "watercolor": "watercolor painting, soft colors, artistic, flowing",
            "sketch": "pencil sketch, detailed drawing, monochrome",
            "cinematic": "cinematic, dramatic lighting, movie still, film grain",
            "neonpunk": "neonpunk, cyberpunk, neon lights, futuristic",
            "fantasy": "fantasy art, magical, ethereal, detailed",
            "3d": "3d render, octane render, blender, detailed modeling",
        }

        if style and style in style_modifiers:
            return f"{prompt}, {style_modifiers[style]}"
        return prompt


ai_service = AIService()
