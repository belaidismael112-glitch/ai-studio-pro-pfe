from __future__ import annotations

"""Subject extraction for V10 hybrid image-to-image.

Production rule: keep the uploaded subject's original pixels, but remove as much
background as possible before placing it in generated scenes/flyers. The module
uses rembg when installed and falls back to a conservative OpenCV/Pillow mask so
it remains safe on local Windows installs.
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps


def extract_subject(source_image_path: str, output_dir: str = "static/images") -> str:
    src = ImageOps.exif_transpose(Image.open(source_image_path)).convert("RGBA")
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / (Path(source_image_path).stem + "_v10_subject_cutout.png")

    cut = _try_rembg(src)
    if cut is None or _alpha_coverage(cut) < 0.02:
        cut = _conservative_edge_cutout(src)

    cut = _trim_transparent(cut)
    cut.save(out)
    return str(out)


def _try_rembg(src: Image.Image) -> Image.Image | None:
    try:
        from rembg import remove  # type: ignore

        result = remove(src)
        if isinstance(result, Image.Image):
            return result.convert("RGBA")
    except Exception:
        return None
    return None


def _conservative_edge_cutout(src: Image.Image) -> Image.Image:
    """Remove only background connected to image edges.

    This avoids destroying logos/products when rembg is unavailable. It works
    best for product photos with a mostly uniform studio/table background and is
    intentionally less aggressive than thresholding the whole image.
    """

    img = src.convert("RGBA")
    w, h = img.size
    if w < 8 or h < 8:
        return img

    px = img.load()
    samples: list[tuple[int, int, int]] = []
    step_x = max(1, w // 24)
    step_y = max(1, h // 24)
    for x in range(0, w, step_x):
        for y in (0, h - 1):
            r, g, b, _ = px[x, y]
            samples.append((r, g, b))
    for y in range(0, h, step_y):
        for x in (0, w - 1):
            r, g, b, _ = px[x, y]
            samples.append((r, g, b))

    if not samples:
        return img

    bg = tuple(sorted(c[i] for c in samples)[len(samples) // 2] for i in range(3))

    def close(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        if a < 10:
            return True
        dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
        lum = (r + g + b) / 3
        neutral = max(r, g, b) - min(r, g, b) < 52
        # Uniform bright/dark background or close-to-edge color only.
        return dist < 86 or (neutral and (lum > 214 or lum < 38) and dist < 140)

    from collections import deque

    seen: set[tuple[int, int]] = set()
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        q.append((x, 0))
        q.append((x, h - 1))
    for y in range(h):
        q.append((0, y))
        q.append((w - 1, y))

    alpha = Image.new("L", (w, h), 255)
    apx = alpha.load()
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or (x, y) in seen:
            continue
        seen.add((x, y))
        if close(x, y):
            apx[x, y] = 0
            q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    alpha = alpha.filter(ImageFilter.GaussianBlur(0.7))
    out = img.copy()
    out.putalpha(alpha)
    return out


def _trim_transparent(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return img
    # Preserve a small breathing margin.
    w, h = img.size
    pad = max(8, int(min(w, h) * 0.025))
    x1, y1, x2, y2 = bbox
    bbox = (max(0, x1 - pad), max(0, y1 - pad), min(w, x2 + pad), min(h, y2 + pad))
    return img.crop(bbox)


def _alpha_coverage(img: Image.Image) -> float:
    alpha = img.convert("RGBA").getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return 0.0
    hist = alpha.histogram()
    visible = sum(hist[16:])
    return visible / float(alpha.width * alpha.height)
