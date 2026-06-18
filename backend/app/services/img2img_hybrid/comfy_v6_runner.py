from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import settings
from app.services.comfy_prompt_director_v6 import ComfyPromptPack


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value not in {None, ""}:
        return value
    setting = getattr(settings, name, None)
    if setting not in {None, ""}:
        return str(setting)
    return default


def _comfy_url() -> str:
    return _env("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _workflow_dir() -> Path:
    return _backend_root() / "comfy_workflows"


def _load_workflow(pack: ComfyPromptPack) -> dict[str, Any]:
    env_key = f"COMFY_WORKFLOW_{pack.workflow_name.upper()}"
    filename = _env(env_key, f"img2img_v6_{pack.workflow_name}.json")
    path = _workflow_dir() / filename
    if not path.exists():
        path = _workflow_dir() / "img2img_v6_universal_api.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing ComfyUI workflow template: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _replace(obj: Any, mapping: dict[str, Any]) -> Any:
    if isinstance(obj, dict):
        return {k: _replace(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace(v, mapping) for v in obj]
    if isinstance(obj, str):
        return mapping.get(obj, obj)
    return obj


async def _upload_image(client: httpx.AsyncClient, image_path: str) -> str:
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Source image not found: {image_path}")
    # ComfyUI /upload/image expects multipart form field 'image'.
    with p.open("rb") as f:
        files = {"image": (p.name, f, "application/octet-stream")}
        data = {"type": "input", "overwrite": "true"}
        resp = await client.post(f"{_comfy_url()}/upload/image", files=files, data=data, timeout=90.0)
        resp.raise_for_status()
    payload = resp.json() if resp.text else {}
    return str(payload.get("name") or p.name)


async def _queue_prompt(client: httpx.AsyncClient, workflow: dict[str, Any]) -> str:
    resp = await client.post(f"{_comfy_url()}/prompt", json={"prompt": workflow}, timeout=90.0)
    resp.raise_for_status()
    payload = resp.json()
    prompt_id = payload.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI returned no prompt_id: {payload}")
    return str(prompt_id)


async def _history(client: httpx.AsyncClient, prompt_id: str) -> dict[str, Any]:
    resp = await client.get(f"{_comfy_url()}/history/{prompt_id}", timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _find_output_image(hist: dict[str, Any], prompt_id: str) -> dict[str, str] | None:
    item = hist.get(prompt_id) if isinstance(hist, dict) else None
    if not isinstance(item, dict):
        return None
    outputs = item.get("outputs") or {}
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        images = node_output.get("images") or []
        if images:
            img = images[0]
            if isinstance(img, dict) and img.get("filename"):
                return {
                    "filename": str(img.get("filename")),
                    "subfolder": str(img.get("subfolder") or ""),
                    "type": str(img.get("type") or "output"),
                }
    return None


async def _download_output(client: httpx.AsyncClient, image_info: dict[str, str], output_dir: str, prefix: str) -> str:
    params = {
        "filename": image_info["filename"],
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    }
    resp = await client.get(f"{_comfy_url()}/view", params=params, timeout=90.0)
    resp.raise_for_status()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(image_info["filename"]).suffix or ".png"
    out = out_dir / f"{prefix}_{uuid4().hex}{ext}"
    out.write_bytes(resp.content)
    return str(out)


def _clean_text(value: str, limit: int = 80) -> str:
    value = str(value or "").replace("\n", " ").strip()
    value = " ".join(value.split())
    return value[:limit]


def _category_bullets(category: str) -> tuple[str, str, str]:
    c = (category or "product").lower()
    if any(x in c for x in ("handbag", "bag", "purse")):
        return ("PREMIUM FINISH", "GOLD DETAIL", "SOFT LEATHER")
    if any(x in c for x in ("watch", "timepiece")):
        return ("PRECISE STYLE", "PREMIUM DETAIL", "DAILY WEAR")
    if any(x in c for x in ("perfume", "cosmetic", "beauty")):
        return ("SIGNATURE SCENT", "ELEGANT FINISH", "LIMITED EDITION")
    if any(x in c for x in ("shoe", "sneaker")):
        return ("COMFORT FIT", "MODERN STYLE", "PREMIUM BUILD")
    return ("PREMIUM FINISH", "AUTHENTIC DETAIL", "LIMITED OFFER")


async def run_comfy_v6(source_image_path: str, pack: ComfyPromptPack, output_dir: str = "static/images") -> dict[str, Any]:
    timeout = httpx.Timeout(120.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        uploaded_name = await _upload_image(client, source_image_path)
        workflow = _load_workflow(pack)
        disable_comfy_text = _env("COMFY_DIRECTOR_V12_DISABLE_COMFY_TEXT", "true").strip().lower() in {"1", "true", "yes", "on"} or str(getattr(pack, "mode", "")).startswith("v13_")
        # AI_STUDIO_V13_NO_OLD_COMFY_TEXT_DEFAULTS
        mapping = {
            "__INPUT_IMAGE__": uploaded_name,
            "__POSITIVE_PROMPT__": pack.positive_prompt,
            "__NEGATIVE_PROMPT__": pack.negative_prompt,
            "__WIDTH__": int(pack.width),
            "__HEIGHT__": int(pack.height),
            "__STEPS__": int(pack.steps),
            "__CFG__": float(pack.cfg),
            "__DENOISE__": float(pack.denoise),
            "__SEED__": int(pack.seed or (abs(hash(pack.positive_prompt)) % 2147483647) or 1),
            "__CHECKPOINT__": _env("COMFY_IMAGE_CHECKPOINT", "sd_xl_base_1.0.safetensors"),
            "__SAVE_PREFIX__": f"AIStudio_V91_{pack.mode}",
            # AI_STUDIO_V14_PLACEHOLDER_BINDING: support exported Flux API workflows.
            "__PROMPT__": pack.positive_prompt,
            "__NEGATIVE_PROMPT__": pack.negative_prompt,
            "__CKPT__": _env("COMFY_IMAGE_CHECKPOINT", "flux1-schnell-fp8.safetensors"),
            "__CHECKPOINT__": _env("COMFY_IMAGE_CHECKPOINT", "flux1-schnell-fp8.safetensors"),
            "__FILENAME_PREFIX__": f"AIStudio_V14_{pack.mode}",
            "__SAMPLER__": _env("IMG2IMG_V14_SAMPLER", _env("COMFY_SAMPLER", "euler")),
            "__SCHEDULER__": _env("IMG2IMG_V14_SCHEDULER", _env("COMFY_SCHEDULER", "simple")),
            "__HEADLINE__": "" if disable_comfy_text else _clean_text(getattr(pack, "overlay_title", ""), 48),
            "__SUBHEADLINE__": "" if disable_comfy_text else _clean_text(getattr(pack, "overlay_subtitle", ""), 96),
            "__CTA__": "" if disable_comfy_text else _clean_text(getattr(pack, "overlay_cta", ""), 32),
            "__BULLET_1__": "" if disable_comfy_text else _clean_text(_category_bullets(getattr(pack, "category", "product"))[0], 36),
            "__BULLET_2__": "" if disable_comfy_text else _clean_text(_category_bullets(getattr(pack, "category", "product"))[1], 36),
            "__BULLET_3__": "" if disable_comfy_text else _clean_text(_category_bullets(getattr(pack, "category", "product"))[2], 36),
        }
        final_workflow = _replace(workflow, mapping)
        prompt_id = await _queue_prompt(client, final_workflow)

        max_wait = int(_env("COMFY_V6_MAX_WAIT_SECONDS", "1200"))
        for _ in range(max_wait):
            hist = await _history(client, prompt_id)
            # If ComfyUI marks execution failed, stop immediately with the real error instead of polling forever.
            item = hist.get(prompt_id) if isinstance(hist, dict) else None
            if isinstance(item, dict) and item.get("status", {}).get("status_str") == "error":
                return {"success": False, "error": f"ComfyUI execution error: {item.get('status')}", "prompt_id": prompt_id}
            info = _find_output_image(hist, prompt_id)
            if info:
                local_path = await _download_output(client, info, output_dir, f"generated_comfy_v6_{pack.mode}")
                return {"success": True, "local_path": local_path, "prompt_id": prompt_id, "comfy_image": info}
            await asyncio.sleep(1)
    return {"success": False, "error": f"ComfyUI timed out before producing an output image after {max_wait}s. Check Comfy terminal for progress/VRAM.", "prompt_id": prompt_id}
