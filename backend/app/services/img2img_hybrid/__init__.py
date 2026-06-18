from __future__ import annotations

import os

from app.services.comfy_prompt_director_v6 import analyze_reference_for_comfy, build_comfy_prompt_pack
from app.services.img2img_hybrid.comfy_v6_runner import run_comfy_v6
from app.services.img2img_hybrid.contracts import Img2ImgRequest, RenderResult
from app.services.img2img_hybrid.qc_v6 import qc_comfy_v6
from app.services.img2img_hybrid.text_overlay_v6 import add_readable_flyer_overlay
from app.services.img2img_hybrid.poster_canvas_v9 import create_v9_poster_canvas, V10_CREATIVE_DIRECTOR_RANDOMIZER_MARKER
from app.services.img2img_hybrid.design_layer_engine import (
    MODE_MARKER as V11_SHARED_DESIGN_LAYER_MARKER,
    MODE_VERSION as V11_SHARED_DESIGN_LAYER_VERSION,
    create_design_layer_canvas,
    read_design_sidecar,
)
from app.services.img2img_hybrid.utils import backend_public_image_url


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return _env_bool("IMG2IMG_COMFY_DIRECTOR_V6_ENABLED", True)


def _strict() -> bool:
    return _env_bool("IMG2IMG_COMFY_DIRECTOR_V6_STRICT", True)


def _v7_full_flyer() -> bool:
    return _env_bool("COMFY_DIRECTOR_V7_FULL_FLYER", True)


def _v9_poster_canvas() -> bool:
    return _env_bool("COMFY_DIRECTOR_V9_POSTER_CANVAS", True)


def _v11_shared_layer() -> bool:
    return _env_bool("COMFY_DIRECTOR_V11_SHARED_DESIGN_LAYER", True)


def _read_v10_layout_sidecar(path: str) -> dict[str, str]:
    try:
        p = str(path or "")
        if not p.lower().endswith(".png"):
            return {}
        side = p[:-4] + ".txt"
        data: dict[str, str] = {}
        for line in open(side, "r", encoding="utf-8", errors="ignore").read().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
        return data
    except Exception:
        return {}


def _provider_for_mode(mode: str, category: str, shared: bool) -> tuple[str, str, str]:
    if shared and mode != "flyer_poster":
        name = mode.replace("_", "-")
        return (
            f"comfy-director-v11-{name}-{category}-no-fallback",
            V11_SHARED_DESIGN_LAYER_VERSION,
            "comfy_director_v11_shared_design_layer",
        )
    if mode == "flyer_poster":
        return (
            f"comfy-director-v10-3-final-design-layer-{category}-no-fallback" if _v9_poster_canvas() else f"comfy-director-v8-pro-flyer-{category}-no-fallback",
            "comfy-director-v10-3-final-design-layer-engine" if _v9_poster_canvas() else "comfy-director-v8-pro-flyer-director",
            "comfy_director_v10_3_final_design_layer" if _v9_poster_canvas() else "comfy_director_v8_pro_flyer",
        )
    return (f"comfy-director-v6-{mode}-{category}-no-fallback", "comfy-director-v6-all-modes", "comfy_director_v6_all_modes")


async def generate_img2img(req: Img2ImgRequest) -> RenderResult:
    if not _enabled():
        return RenderResult(False, error="IMG2IMG_COMFY_DIRECTOR_V6_ENABLED=false", provider="comfy-director-v7-disabled")

    decision = await analyze_reference_for_comfy(
        req.source_image_path,
        requested_mode=req.mode,
        user_prompt=req.prompt or "",
        subject_type_hint=req.subject_type,
    )
    pack = build_comfy_prompt_pack(
        decision,
        user_prompt=req.prompt or "",
        negative_prompt=req.negative_prompt or "",
        width=req.width,
        height=req.height,
        strength=req.strength,
    )

    if pack.mode in {"flyer_poster", "social_post"} and _v7_full_flyer():
        pack.overlay_enabled = False

    try:
        comfy_source_path = req.source_image_path
        shared_v11_active = bool(_v11_shared_layer() and pack.mode != "flyer_poster")
        if pack.mode == "flyer_poster" and _v9_poster_canvas():
            comfy_source_path = create_v9_poster_canvas(req.source_image_path, pack, output_dir=req.output_dir or "static/images")
        elif shared_v11_active:
            design = getattr(pack, "metadata", {}).get("v11_design") if hasattr(pack, "metadata") else None
            if design:
                comfy_source_path = create_design_layer_canvas(req.source_image_path, design, output_dir=req.output_dir or "static/images")

        comfy = await run_comfy_v6(comfy_source_path, pack, output_dir=req.output_dir or "static/images")
        if not comfy.get("success"):
            return RenderResult(
                False,
                error=str(comfy.get("error") or "ComfyUI failed"),
                provider="comfy-director-v11-comfy-failed" if shared_v11_active else "comfy-director-v7-comfy-failed",
                metadata={"decision": decision.__dict__, "prompt_pack": pack.__dict__, "comfy": comfy},
            )

        local_path = str(comfy["local_path"])
        if pack.overlay_enabled:
            local_path = add_readable_flyer_overlay(local_path, pack, output_dir=req.output_dir or "static/images")

        qc = qc_comfy_v6(local_path, decision, pack)
        if not qc.get("ok") and _strict():
            return RenderResult(
                False,
                local_path=local_path,
                error=str(qc.get("reason")),
                provider="comfy-director-v11-qc-reject" if shared_v11_active else "comfy-director-v7-qc-reject",
                metadata={"qc": qc, "decision": decision.__dict__, "prompt_pack": pack.__dict__, "comfy": comfy},
            )

        if shared_v11_active:
            layout_meta = read_design_sidecar(str(comfy_source_path))
        else:
            layout_meta = _read_v10_layout_sidecar(str(comfy_source_path)) if pack.mode == "flyer_poster" else {}
        selected_layout = layout_meta.get("selected_layout") or layout_meta.get("variant") or getattr(getattr(pack, "metadata", {}).get("v11_design", None), "selected_layout", "")
        provider, renderer_version, renderer_used = _provider_for_mode(pack.mode, decision.category, shared_v11_active)

        return RenderResult(
            success=True,
            local_path=local_path,
            public_url=backend_public_image_url(local_path),
            renderer_used=renderer_used,
            provider=provider,
            metadata={
                "renderer_version": renderer_version,
                "v11_shared_design_layer": bool(shared_v11_active),
                "v11_marker": V11_SHARED_DESIGN_LAYER_MARKER if shared_v11_active else "",
                "mode": pack.mode,
                "selected_layout": selected_layout,
                "comfy_source_path": str(comfy_source_path),
                "v11_layout_sidecar": (str(comfy_source_path)[:-4] + ".txt") if (shared_v11_active and str(comfy_source_path).lower().endswith(".png")) else "",
                "v9_poster_canvas": bool(pack.mode == "flyer_poster" and _v9_poster_canvas()),
                "v9_1_comfy_text_finalizer": bool(pack.mode == "flyer_poster" and _v9_poster_canvas()),
                "v10_creative_randomizer": bool(pack.mode == "flyer_poster" and _v9_poster_canvas()),
                "v10_1_strong_random": bool(pack.mode == "flyer_poster" and _v9_poster_canvas()),
                "v10_2_real_layout_breaker": bool(pack.mode == "flyer_poster" and _v9_poster_canvas()),
                "v10_3_final_design_layer": bool(pack.mode == "flyer_poster" and _v9_poster_canvas()),
                "v10_marker": V10_CREATIVE_DIRECTOR_RANDOMIZER_MARKER if (pack.mode == "flyer_poster" and _v9_poster_canvas()) else "",
                "category": decision.category,
                "subject_type": decision.subject_type,
                "workflow_name": pack.workflow_name,
                "final_size": [pack.width, pack.height],
                "overlay_enabled": bool(pack.overlay_enabled),
                "comfy_text": bool(pack.mode in {"flyer_poster", "social_post"} and _v7_full_flyer()),
                "fallback_used": False,
                "auto_smart_requested": bool((req.mode or "").lower().replace("-", "_") == "auto"),
                "resolved_mode": pack.mode,
                "qc": qc,
                "decision": decision.__dict__,
                "prompt_pack": {
                    "positive_prompt": pack.positive_prompt,
                    "negative_prompt": pack.negative_prompt,
                    "steps": pack.steps,
                    "cfg": pack.cfg,
                    "denoise": pack.denoise,
                    "workflow_name": pack.workflow_name,
                },
                "comfy": comfy,
            },
        )
    except Exception as exc:
        return RenderResult(
            False,
            error=f"Comfy Director V11 exception: {exc}",
            provider="comfy-director-v11-exception",
            metadata={"decision": decision.__dict__, "prompt_pack": pack.__dict__},
        )
