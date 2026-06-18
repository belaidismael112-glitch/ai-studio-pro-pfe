from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path
from urllib.parse import urlencode

import httpx


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _round64(value: int) -> int:
    return max(512, (int(value) // 64) * 64)


async def generate_v10_comfy_backdrop(*, analysis, brief, width: int, height: int, output_dir: str) -> str | None:
    """Generate an abstract backdrop only.

    V10.13 rule:
    ComfyUI must NOT be trusted to preserve/no-preserve product. It is used only
    as a texture/abstract backdrop source. The final renderer sanitizes the hero
    zone before the uploaded subject is pasted.
    """

    if not _env_bool("IMG2IMG_V10_USE_COMFY_BACKDROP_FOR_FLYER", True):
        return None

    comfy = os.getenv("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
    ckpt = os.getenv("COMFY_IMAGE_CHECKPOINT", "flux1-schnell-fp8.safetensors")
    w = _round64(width or 1024)
    h = _round64(height or 1024)
    steps = max(6, min(_env_int("COMFY_COMMERCIAL_BACKGROUND_STEPS", 10), 24))
    cfg = max(1.0, min(_env_float("COMFY_COMMERCIAL_BACKGROUND_CFG", 1.0), 3.0))
    sampler = os.getenv("COMFY_IMAGE_SAMPLER", "euler")
    scheduler = os.getenv("COMFY_IMAGE_SCHEDULER", "simple")
    seed = random.randint(1, 2**63 - 1)

    category = (getattr(analysis, "category", "") or "").lower()

    if category == "beverage":
        prompt = (
            "abstract commercial poster background only, pure graphic design, red black white gradients, "
            "liquid-inspired curves but no bottle, no can, no product, no label, no logo, no words, "
            "empty premium advertising backdrop, shapes only, studio light, clean hero space"
        )
    elif category in {"fashion", "general_product"}:
        prompt = (
            "abstract luxury fashion poster background only, pure graphic design, beige black gold gradients, "
            "silky curves, editorial light, premium empty advertising backdrop, no handbag, no purse, no bag, "
            "no product, no object, no logo, no text, no letters, shapes only, clean hero space"
        )
    elif category == "sports":
        prompt = (
            "abstract sports event poster background only, orange black graphic shapes, motion energy, "
            "no athlete, no person, no product, no text, no logo, empty backdrop"
        )
    else:
        prompt = (
            "abstract premium marketing poster background only, graphic shapes, soft gradients, clean studio lighting, "
            "no product, no object, no people, no text, no logo, empty hero space"
        )

    negative = (
        "handbag, purse, bag, bottle, can, product, package, box, object, item, logo, label, brand, "
        "letters, typography, text, words, watermark, people, person, hand, face, model, clutter, "
        "foreground object, centered object, duplicate subject, low quality, blurry, distorted"
    )

    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": negative}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "width": w, "height": h}},
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
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "AIStudioPro_V10_Backdrop_flyer"}},
    }

    try:
        timeout = httpx.Timeout(float(os.getenv("COMFY_V10_BACKDROP_TIMEOUT", "220")), connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(f"{comfy}/prompt", json={"prompt": workflow})
            res.raise_for_status()
            prompt_id = res.json().get("prompt_id")
            if not prompt_id:
                print("V10_CORE_COMFY_BACKDROP_FAILED no prompt_id")
                return None

            image_info = await _poll_history_for_image(client, comfy, str(prompt_id))
            if not image_info:
                print(f"V10_CORE_COMFY_BACKDROP_FAILED no image prompt_id={prompt_id}")
                return None

            query = urlencode({
                "filename": image_info.get("filename"),
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "output"),
            })
            view = await client.get(f"{comfy}/view?{query}")
            view.raise_for_status()

            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"v10_comfy_backdrop_{prompt_id}.png"
            out.write_bytes(view.content)
            print(f"V10_CORE_COMFY_BACKDROP_SUCCESS path={out} source={image_info}")
            return str(out)
    except Exception as exc:
        print(f"V10_CORE_COMFY_BACKDROP_EXCEPTION {type(exc).__name__}: {exc}")
        return None


async def _poll_history_for_image(client: httpx.AsyncClient, comfy: str, prompt_id: str) -> dict | None:
    for _ in range(_env_int("COMFY_V10_BACKDROP_POLL_COUNT", 240)):
        await asyncio.sleep(1)

        for url in (f"{comfy}/history/{prompt_id}", f"{comfy}/history"):
            try:
                res = await client.get(url)
                if res.status_code != 200:
                    continue
                data = res.json()
                image = _find_image_info_recursive(data, filename_prefix="AIStudioPro_V10_Backdrop_flyer")
                if image:
                    return image
                image = _find_image_info_recursive(data)
                if image and str(image.get("filename", "")).startswith("AIStudioPro_V10_Backdrop_flyer"):
                    return image
            except Exception:
                pass

    return None


def _find_image_info_recursive(obj, filename_prefix: str | None = None) -> dict | None:
    if isinstance(obj, dict):
        if "filename" in obj:
            filename = str(obj.get("filename") or "")
            if filename and (not filename_prefix or filename.startswith(filename_prefix)):
                return {"filename": filename, "subfolder": obj.get("subfolder", ""), "type": obj.get("type", "output")}

        images = obj.get("images")
        if isinstance(images, list):
            for img in images:
                found = _find_image_info_recursive(img, filename_prefix)
                if found:
                    return found

        for value in obj.values():
            found = _find_image_info_recursive(value, filename_prefix)
            if found:
                return found

    if isinstance(obj, list):
        for value in obj:
            found = _find_image_info_recursive(value, filename_prefix)
            if found:
                return found

    return None
