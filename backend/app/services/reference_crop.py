"""Reference-image auto crop helpers for production source-locked generation.

The goal is not to replace a real segmentation model. It prepares a stronger
reference frame for ComfyUI when the subject is present but too wide/small in the
original camera capture. This prevents the old failure where a valid 15-19%
face/product reference was blocked instead of being cropped and used.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageOps


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _expand_to_aspect(
    cx: float,
    cy: float,
    box_w: float,
    box_h: float,
    *,
    target_aspect: float,
    image_w: int,
    image_h: int,
) -> tuple[int, int, int, int]:
    """Build a crop rectangle with the desired aspect ratio and clipped bounds."""
    crop_w = max(1.0, float(box_w))
    crop_h = max(1.0, float(box_h))

    if crop_w / crop_h < target_aspect:
        crop_w = crop_h * target_aspect
    else:
        crop_h = crop_w / target_aspect

    crop_w = min(crop_w, float(image_w))
    crop_h = min(crop_h, float(image_h))

    left = cx - crop_w / 2.0
    top = cy - crop_h / 2.0
    right = left + crop_w
    bottom = top + crop_h

    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > image_w:
        left -= right - image_w
        right = image_w
    if bottom > image_h:
        top -= bottom - image_h
        bottom = image_h

    left = _clamp(round(left), 0, image_w - 1)
    top = _clamp(round(top), 0, image_h - 1)
    right = _clamp(round(right), left + 1, image_w)
    bottom = _clamp(round(bottom), top + 1, image_h)
    return left, top, right, bottom


def create_subject_reference_crop(
    image_path: str | Path,
    bbox: dict[str, Any] | None,
    *,
    subject_type: str = "object_or_product",
    target_width: int = 1280,
    target_height: int = 720,
) -> str | None:
    """Create a 16:9 production crop around the detected subject.

    Person crops intentionally keep shoulders/body context. Product crops keep a
    smaller margin for cleaner advertising cut-outs. The returned image is saved
    next to the original temp upload and can be sent directly to ComfyUI.
    """
    if not bbox:
        return None

    try:
        x = float(bbox.get("x", 0))
        y = float(bbox.get("y", 0))
        w = float(bbox.get("w", 0))
        h = float(bbox.get("h", 0))
    except Exception:
        return None

    if w <= 0 or h <= 0:
        return None

    src_path = Path(image_path)
    with Image.open(src_path) as img:
        rgb = img.convert("RGB")
        image_w, image_h = rgb.size

        cx = x + w / 2.0
        cy = y + h / 2.0
        stype = (subject_type or "").lower()

        # Defense in depth: auto-crop is identity-only. Generic objects,
        # animals, insects, products and creative references must keep the full
        # source composition. Edge-based object boxes can be unstable on
        # textured images and may zoom into a small detail.
        if stype not in {"person", "person_face", "person_full"}:
            return None

        if stype == "person_face":
            # Keep head + shoulders and move center slightly downward so the crop
            # has body context instead of only forehead/face.
            expanded_w = w * 3.10
            expanded_h = h * 3.00
            cy = cy + h * 0.42
        elif stype in {"document", "document_or_poster"}:
            expanded_w = w * 1.18
            expanded_h = h * 1.18
        else:
            expanded_w = w * 1.58
            expanded_h = h * 1.58

        rect = _expand_to_aspect(
            cx,
            cy,
            expanded_w,
            expanded_h,
            target_aspect=target_width / max(1, target_height),
            image_w=image_w,
            image_h=image_h,
        )

        crop = rgb.crop(rect)
        fitted = ImageOps.fit(crop, (target_width, target_height), Image.LANCZOS, centering=(0.5, 0.5))
        out_path = src_path.with_name(f"{src_path.stem}_autocrop_{uuid4().hex}.png")
        fitted.save(out_path, format="PNG")
        return str(out_path)
