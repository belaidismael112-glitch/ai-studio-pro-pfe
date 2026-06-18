from __future__ import annotations

"""AI Studio V12.7 Source-Lock Final Composite.

Composites the exact uploaded source subject over the Comfy output after generation.
This prevents the final delivery image from exposing a repainted/deformed product.
"""

from collections import deque
from pathlib import Path
from uuid import uuid4
from typing import Any

from PIL import Image, ImageFilter


V12_7_SOURCE_LOCK_FINAL_COMPOSITE_MARKER = "AI_STUDIO_V12_7_SOURCE_LOCK_FINAL_COMPOSITE"


def _is_edge_background(r: int, g: int, b: int, seed: tuple[int, int, int]) -> bool:
    sr, sg, sb = seed
    maxc = max(r, g, b)
    minc = min(r, g, b)
    very_white = r > 232 and g > 232 and b > 232
    bright_neutral = r > 184 and g > 184 and b > 184 and (maxc - minc) < 54
    close_to_seed = abs(r - sr) + abs(g - sg) + abs(b - sb) < 92
    return very_white or (bright_neutral and close_to_seed)


def _edge_flood_cutout(image: Image.Image) -> Image.Image:
    im = image.convert("RGBA")
    w, h = im.size
    px = im.load()

    samples = [
        px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1],
        px[w // 2, 0], px[w // 2, h - 1], px[0, h // 2], px[w - 1, h // 2],
    ]
    seed = tuple(int(sum(c[i] for c in samples) / len(samples)) for i in range(3))

    visited = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    def maybe_push(x: int, y: int) -> None:
        idx = y * w + x
        if visited[idx]:
            return
        r, g, b, a = px[x, y]
        if a == 0 or _is_edge_background(r, g, b, seed):
            visited[idx] = 1
            q.append((x, y))

    for x in range(w):
        maybe_push(x, 0)
        maybe_push(x, h - 1)
    for y in range(h):
        maybe_push(0, y)
        maybe_push(w - 1, y)

    while q:
        x, y = q.popleft()
        r, g, b, a = px[x, y]
        if a:
            px[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                idx = ny * w + nx
                if not visited[idx]:
                    rr, gg, bb, aa = px[nx, ny]
                    if aa == 0 or _is_edge_background(rr, gg, bb, seed):
                        visited[idx] = 1
                        q.append((nx, ny))

    alpha = im.getchannel("A").filter(ImageFilter.GaussianBlur(0.35))
    alpha = alpha.point(lambda p: 0 if p < 12 else min(255, int(p * 1.10)))
    im.putalpha(alpha)
    return im


def _trim_alpha(image: Image.Image, pad: int = 8) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return image
    x1, y1, x2, y2 = bbox
    return image.crop((max(0, x1 - pad), max(0, y1 - pad), min(image.width, x2 + pad), min(image.height, y2 + pad)))


def _fit_contain(image: Image.Image, max_w: int, max_h: int) -> Image.Image:
    im = image.convert("RGBA")
    im.thumbnail((max(16, max_w), max(16, max_h)), Image.Resampling.LANCZOS)
    return im


def _shadow(subject: Image.Image, blur: int = 24, opacity: int = 80) -> Image.Image:
    alpha = subject.getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda p: min(opacity, p))
    out = Image.new("RGBA", subject.size, (0, 0, 0, 0))
    out.putalpha(alpha)
    return out


def apply_v12_7_source_lock_final_composite(
    comfy_output_path: str,
    source_image_path: str,
    output_dir: str = "static/images",
    mode: str = "flyer_poster",
    metadata: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    base_path = Path(comfy_output_path)
    src_path = Path(source_image_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = Image.open(base_path).convert("RGBA")
    source = Image.open(src_path).convert("RGBA")

    subject = _trim_alpha(_edge_flood_cutout(source), pad=8)

    w, h = base.size
    # Preserve source scale better for product ads/posters.
    if subject.width >= subject.height:
        max_w = int(w * 0.76)
        max_h = int(h * 0.30)
        y_center = int(h * 0.43)
    else:
        max_w = int(w * 0.50)
        max_h = int(h * 0.62)
        y_center = int(h * 0.48)

    subject = _fit_contain(subject, max_w, max_h)
    x = (w - subject.width) // 2
    y = y_center - subject.height // 2

    x = max(0, min(x, w - subject.width))
    y = max(0, min(y, h - subject.height))

    base.alpha_composite(_shadow(subject), (x + 10, y + 18))
    base.alpha_composite(subject, (x, y))

    out = out_dir / f"generated_v12_7_source_lock_composite_{uuid4().hex}.png"
    base.convert("RGB").save(out, quality=95)

    meta_patch = {
        "v12_7_source_lock_final_composite": True,
        "v12_7_marker": V12_7_SOURCE_LOCK_FINAL_COMPOSITE_MARKER,
        "v12_7_composite_source": str(src_path),
        "v12_7_composite_base": str(base_path),
        "v12_7_composite_subject_bbox": [x, y, x + subject.width, y + subject.height],
        "local_path": str(out),
    }
    return str(out), meta_patch
