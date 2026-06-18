from __future__ import annotations

"""Real V10 ComfyUI adapter + source-lock compositor.

ComfyUI creates only a clean commercial scene/background. The uploaded subject is
then composited on top from `source_subject_path`, so products, logos and people
are not hallucinated or duplicated by the model.
"""

import asyncio
import os
import random
from pathlib import Path
from urllib.parse import urlencode

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .contracts import RenderPlan, RenderResult
from .utils import backend_public_image_url, ensure_output_dir, unique_name


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


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
    return max(512, min(1536, (int(value or 1024) // 64) * 64))


async def render_with_comfy(plan: RenderPlan) -> RenderResult:
    backdrop_path = await generate_comfy_scene(plan)
    if not backdrop_path:
        return RenderResult(False, error="Comfy scene generation failed", renderer_used="comfy", provider="v10-comfy-source-lock")
    return composite_source_locked(plan, backdrop_path)


async def generate_comfy_scene(plan: RenderPlan) -> str | None:
    if not _env_bool("IMG2IMG_V10_USE_COMFY", True):
        return None

    comfy = os.getenv("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
    ckpt = os.getenv("COMFY_IMAGE_CHECKPOINT", "flux1-schnell-fp8.safetensors")
    w = _round64(plan.final_width)
    h = _round64(plan.final_height)
    steps = max(8, min(_env_int("COMFY_REFERENCE_TRANSFORM_STEPS", 18), 32))
    cfg = max(1.0, min(_env_float("COMFY_REFERENCE_TRANSFORM_CFG", 2.0), 5.0))
    sampler = os.getenv("COMFY_IMAGE_SAMPLER", "euler")
    scheduler = os.getenv("COMFY_IMAGE_SCHEDULER", "simple")
    seed = random.randint(1, 2**63 - 1)
    prompt = build_comfy_prompt(plan)
    negative = build_negative_prompt(plan)
    prefix = f"AIStudioPro_V10_{plan.mode}"

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
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
    }

    try:
        timeout = httpx.Timeout(float(os.getenv("COMFY_V10_BACKDROP_TIMEOUT", "240")), connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(f"{comfy}/prompt", json={"prompt": workflow})
            res.raise_for_status()
            prompt_id = res.json().get("prompt_id")
            if not prompt_id:
                return None
            info = await _poll_history_for_image(client, comfy, str(prompt_id), filename_prefix=prefix)
            if not info:
                return None
            query = urlencode({"filename": info.get("filename"), "subfolder": info.get("subfolder", ""), "type": info.get("type", "output")})
            view = await client.get(f"{comfy}/view?{query}")
            view.raise_for_status()
            out_dir = ensure_output_dir(plan.output_dir)
            out = out_dir / f"v10_comfy_scene_{plan.mode}_{prompt_id}.png"
            out.write_bytes(view.content)
            return str(out)
    except Exception as exc:
        print(f"V10_COMFY_SCENE_EXCEPTION {type(exc).__name__}: {exc}")
        return None


def build_comfy_prompt(plan: RenderPlan) -> str:
    a = plan.analysis
    b = plan.brief
    category = (a.category or "general_product").lower()
    user_prompt = str(plan.metadata.get("user_prompt") or "").strip()
    common = (
        "production-quality commercial background, high-end advertising photography, clean composition, "
        "professional lighting, realistic shadows, premium color harmony, empty hero space for uploaded subject, "
        "no text, no letters, no logo, no watermark, no duplicated product"
    )
    if plan.mode == "background_replace":
        base = f"new background only for a preserved foreground subject, {b.scene_description}, {b.style_direction}"
    elif plan.mode == "product_ad":
        base = f"premium product advertising scene for a {a.subject_label}, studio set, plinth, depth, editorial campaign"
    elif plan.mode == "person_identity":
        base = "editorial portrait background, clean studio environment, flattering light, no extra faces, no body duplication"
    elif plan.mode == "creative_image":
        base = f"creative campaign scene inspired by {a.subject_label}, cinematic environment, polished art direction"
    else:
        base = f"commercial scene for {a.subject_label}"

    if category in {"fashion", "general_product"}:
        flavor = "luxury beige black gold fashion set, satin curves, premium shadows, editorial retail campaign"
    elif category == "beverage":
        flavor = "bold beverage campaign set, crisp condensation mood, red black white energy, clean reflective surface"
    elif category == "food":
        flavor = "warm appetizing restaurant campaign scene, clean table surface, soft highlights"
    elif category == "sports":
        flavor = "dynamic sports graphic scene, orange black energy, motion-light background, event poster atmosphere"
    elif category == "nature":
        flavor = "macro nature editorial background, organic texture, soft natural light, educational poster atmosphere"
    else:
        flavor = "modern premium studio scene, soft gradients, clean depth"
    return ", ".join(x for x in [base, flavor, b.style_direction, user_prompt, common] if x)


def build_negative_prompt(plan: RenderPlan) -> str:
    return ", ".join(
        [
            "text, typography, letters, words, watermark, logo, brand name",
            "duplicate subject, duplicate product, extra object, extra person, hallucinated foreground product",
            "warped label, changed logo, distorted face, distorted hands, bad anatomy",
            "low quality, blurry, noisy, cluttered, messy layout, jpeg artifacts",
            plan.brief.negative_prompt or "",
        ]
    )


def composite_source_locked(plan: RenderPlan, backdrop_path: str) -> RenderResult:
    W, H = int(plan.final_width or 1024), int(plan.final_height or 1024)
    bg = ImageOps.exif_transpose(Image.open(backdrop_path).convert("RGB"))
    bg = _cover(bg, W, H).convert("RGBA")
    bg = _soften_hero_zone(bg, plan.mode)

    if plan.mode == "background_replace":
        box = (int(W * 0.08), int(H * 0.08), int(W * 0.92), int(H * 0.92))
    elif plan.mode == "person_identity":
        box = (int(W * 0.10), int(H * 0.06), int(W * 0.90), int(H * 0.94))
    else:
        box = (int(W * 0.18), int(H * 0.15), int(W * 0.82), int(H * 0.78))

    _paste_subject(bg, plan.source_subject_path, box, shadow=True)

    # Product ad/creative get subtle brand-safe copy only when not background replace.
    if plan.mode in {"product_ad", "creative_image"}:
        draw = ImageDraw.Draw(bg)
        _draw_product_caption(draw, plan, W, H)

    out = ensure_output_dir(plan.output_dir) / unique_name(f"generated_v10_{plan.mode}_comfy_locked")
    bg.convert("RGB").save(out, quality=96)
    return RenderResult(
        True,
        str(out),
        backend_public_image_url(str(out)),
        renderer_used="comfy_source_locked_composite",
        provider="v10-production-comfy-source-lock",
        metadata={"backdrop_path": backdrop_path, "source_subject_path": plan.source_subject_path},
    )


def _draw_product_caption(draw: ImageDraw.ImageDraw, plan: RenderPlan, W: int, H: int) -> None:
    from .flyer_renderer import _draw_wrapped, _font

    title = (plan.brief.title or "PREMIUM CAMPAIGN").upper()
    subtitle = plan.brief.subtitle or "Source-preserved commercial visual."
    x = int(W * 0.07)
    y = int(H * 0.07)
    maxw = int(W * 0.38)
    draw.rounded_rectangle([x - 22, y - 18, x + maxw + 22, y + int(H * 0.18)], radius=24, fill=(0, 0, 0, 115))
    _draw_wrapped(draw, title, x, y, maxw, _font(max(26, W // 24), True), "#ffffff", max_lines=2)
    _draw_wrapped(draw, subtitle, x, y + int(H * 0.105), maxw, _font(max(14, W // 58), False), "#e5e7eb", max_lines=2)


def _paste_subject(canvas: Image.Image, subject_path: str | None, box: tuple[int, int, int, int], shadow: bool = True) -> None:
    if not subject_path:
        return
    try:
        subject = ImageOps.exif_transpose(Image.open(subject_path).convert("RGBA"))
    except Exception:
        return
    x1, y1, x2, y2 = box
    bw, bh = max(10, x2 - x1), max(10, y2 - y1)
    subject.thumbnail((bw, bh), Image.LANCZOS)
    px = x1 + (bw - subject.width) // 2
    py = y1 + (bh - subject.height) // 2
    if shadow:
        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sd.ellipse([px + int(subject.width * 0.08), py + subject.height - 18, px + int(subject.width * 0.92), py + subject.height + 30], fill=(0, 0, 0, 105))
        canvas.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(max(10, canvas.width // 70))))
    canvas.alpha_composite(subject, (px, py))


def _soften_hero_zone(bg: Image.Image, mode: str) -> Image.Image:
    if mode not in {"product_ad", "creative_image", "background_replace"}:
        return bg
    W, H = bg.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([int(W * 0.12), int(H * 0.12), int(W * 0.88), int(H * 0.84)], radius=max(30, W // 24), fill=(255, 255, 255, 22))
    od.ellipse([int(W * 0.20), int(H * 0.70), int(W * 0.80), int(H * 0.88)], fill=(0, 0, 0, 45))
    bg.alpha_composite(overlay)
    return bg


def _cover(img: Image.Image, W: int, H: int) -> Image.Image:
    img = img.convert("RGB")
    scale = max(W / img.width, H / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))


async def _poll_history_for_image(client: httpx.AsyncClient, comfy: str, prompt_id: str, filename_prefix: str | None = None) -> dict | None:
    for _ in range(_env_int("COMFY_V10_BACKDROP_POLL_COUNT", 240)):
        await asyncio.sleep(1)
        for url in (f"{comfy}/history/{prompt_id}", f"{comfy}/history"):
            try:
                res = await client.get(url)
                if res.status_code != 200:
                    continue
                found = _find_image_info_recursive(res.json(), filename_prefix=filename_prefix)
                if found:
                    return found
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
    elif isinstance(obj, list):
        for value in obj:
            found = _find_image_info_recursive(value, filename_prefix)
            if found:
                return found
    return None
