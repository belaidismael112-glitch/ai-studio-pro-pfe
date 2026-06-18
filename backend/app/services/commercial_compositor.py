from __future__ import annotations
from app.services.autonomous_flyer_director import parse_autonomous_flyer_marker
"""Production source-lock compositing for reference workflows.

The model should create the scene; it must not repaint packaging, logos or a
person's face when the user asked to preserve the source.  This module provides
an explicit subject-analysis layer:

1. analyse the uploaded reference;
2. remove the connected background with an OpenCV matte;
3. save a clean transparent subject asset;
4. resize it conservatively;
5. composite it over an AI-generated backdrop with restrained depth effects;
6. optionally add readable flyer copy.

The same extraction pipeline is shared by Product Ad, Flyer / Poster and the
source-lock variants of Background Replace and Creative Reference.
"""
from pathlib import Path
from uuid import uuid4
import os
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.core.config import settings


_ALLOWED_MODES = {"product_ad", "flyer_poster", "background_replace", "creative_image"}


def _clamp(value: int, low: int = 0, high: int = 255) -> int:
    return max(low, min(high, int(value)))


def _setting_or_env(name: str, default):
    env_value = os.getenv(name)
    if env_value not in {None, ""}:
        return env_value
    value = getattr(settings, name, None)
    if value not in {None, ""}:
        return value
    return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _setting_or_env(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(_setting_or_env(name, default))
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        return float(_setting_or_env(name, default))
    except Exception:
        return float(default)


def _font(size: int, *, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size=max(10, int(size)))
        except Exception:
            pass
    return ImageFont.load_default()


def _dominant_accent(img: Image.Image) -> tuple[int, int, int]:
    arr = np.asarray(img.convert("RGB").resize((96, 96)), dtype=np.float32)
    saturation = arr.max(axis=2) - arr.min(axis=2)
    brightness = arr.mean(axis=2)
    mask = (saturation > 42) & (brightness > 28) & (brightness < 236)
    mean = arr[mask].mean(axis=0) if np.count_nonzero(mask) >= 30 else arr.reshape(-1, 3).mean(axis=0)
    return tuple(_clamp(round(v)) for v in mean)


def _resize_for_analysis(rgb: np.ndarray, max_side: int = 720) -> tuple[np.ndarray, float]:
    h, w = rgb.shape[:2]
    scale = min(1.0, float(max_side) / max(1, max(h, w)))
    if scale >= 0.999:
        return rgb, 1.0
    return cv2.resize(rgb, (max(2, int(round(w * scale))), max(2, int(round(h * scale)))), interpolation=cv2.INTER_AREA), scale


def _border_pixels(rgb: np.ndarray, ratio: float = 0.035) -> np.ndarray:
    h, w = rgb.shape[:2]
    band = max(2, int(round(min(h, w) * ratio)))
    return np.concatenate(
        [
            rgb[:band, :, :].reshape(-1, 3),
            rgb[-band:, :, :].reshape(-1, 3),
            rgb[:, :band, :].reshape(-1, 3),
            rgb[:, -band:, :].reshape(-1, 3),
        ],
        axis=0,
    )


def _border_colour_centres(rgb: np.ndarray) -> np.ndarray:
    samples = _border_pixels(rgb)
    if len(samples) > 5000:
        step = max(1, len(samples) // 5000)
        samples = samples[::step]
    data = samples.astype(np.float32)
    if len(data) < 8:
        return np.median(data, axis=0, keepdims=True)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.3)
    try:
        _compactness, _labels, centres = cv2.kmeans(data, 4, None, criteria, 4, cv2.KMEANS_PP_CENTERS)
        return centres.astype(np.float32)
    except Exception:
        return np.median(data, axis=0, keepdims=True)


def _labels_touching_border(labels: np.ndarray) -> set[int]:
    border = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    return {int(value) for value in np.unique(border) if int(value) > 0}


def _connected_border_background(rgb: np.ndarray) -> np.ndarray:
    """Return a background mask connected to the image border.

    Multiple border-colour centres support white, grey, studio-gradient and
    shadowed packshots.  Only connected border regions are removed, so internal
    white logos and labels remain protected.
    """
    centres = _border_colour_centres(rgb)
    pixels = rgb.astype(np.float32)
    distances = np.sqrt(((pixels[:, :, None, :] - centres[None, None, :, :]) ** 2).sum(axis=3))
    min_distance = distances.min(axis=2)
    threshold = _env_float("REFERENCE_BORDER_COLOR_DISTANCE", 58.0)
    candidate = (min_distance <= threshold).astype(np.uint8)
    kernel = np.ones((3, 3), dtype=np.uint8)
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, kernel, iterations=1)
    count, labels = cv2.connectedComponents(candidate, connectivity=8)
    if count <= 1:
        return np.zeros(candidate.shape, dtype=np.uint8)
    touching = _labels_touching_border(labels)
    if not touching:
        return np.zeros(candidate.shape, dtype=np.uint8)
    bg = np.isin(labels, list(touching)).astype(np.uint8)
    return bg


def _largest_subject_components(mask: np.ndarray) -> np.ndarray:
    """Keep the principal subject plus nearby aligned pieces.

    Product packshots can contain disconnected but valid parts: bottle caps,
    watch straps, shoe laces and glass-neck highlights.  The previous logic kept
    only pieces whose centroids sat inside a narrow margin around the largest
    component, which could silently drop a cap.  Keep aligned components that
    are close to the principal silhouette while still discarding distant floor
    shadows and background islands.
    """
    mask_u8 = (mask > 0).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if count <= 1:
        return mask_u8

    areas = stats[1:, cv2.CC_STAT_AREA]
    largest_label = int(np.argmax(areas)) + 1
    largest_area = max(1, int(stats[largest_label, cv2.CC_STAT_AREA]))
    lx = int(stats[largest_label, cv2.CC_STAT_LEFT])
    ly = int(stats[largest_label, cv2.CC_STAT_TOP])
    lw = int(stats[largest_label, cv2.CC_STAT_WIDTH])
    lh = int(stats[largest_label, cv2.CC_STAT_HEIGHT])
    lright = lx + lw
    lbottom = ly + lh

    horizontal_margin = max(8, int(lw * 0.22))
    vertical_margin = max(10, int(lh * 0.26))
    min_piece_area = max(6, int(largest_area * 0.0012))
    keep = np.zeros(mask_u8.shape, dtype=np.uint8)

    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        right = x + w
        bottom = y + h

        horizontally_aligned = right >= lx - horizontal_margin and x <= lright + horizontal_margin
        vertically_close = bottom >= ly - vertical_margin and y <= lbottom + vertical_margin
        intersects_expanded_main = horizontally_aligned and vertically_close
        meaningful_piece = area >= min_piece_area

        if label == largest_label or (meaningful_piece and intersects_expanded_main):
            keep[labels == label] = 1

    # Connect tiny gaps between aligned product pieces without growing the mask
    # into distant shadows.  A narrow vertical close is useful for bottle caps
    # and transparent glass necks.
    bridge_h = max(3, min(17, int(round(lh * 0.035))))
    bridge = np.ones((bridge_h, 3), dtype=np.uint8)
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, bridge, iterations=1)
    return keep



def _fill_small_internal_holes(mask: np.ndarray) -> tuple[np.ndarray, float]:
    """Repair enclosed logo holes while preserving disconnected product pieces.

    Bright logo letters can resemble a white studio background.  Fill only
    small enclosed holes, but never collapse the subject back to its largest
    component: a cap, strap or lace can be a valid disconnected piece.
    """
    mask_u8 = (mask > 0).astype(np.uint8)
    total_subject_area = max(1, int(np.count_nonzero(mask_u8)))
    contours, hierarchy = cv2.findContours(mask_u8, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or hierarchy is None:
        return mask_u8, 0.0

    filled = mask_u8.copy()
    max_hole_ratio = _env_float("REFERENCE_MAX_INTERNAL_HOLE_FILL_RATIO", 0.18)
    filled_area = 0
    for index, contour in enumerate(contours):
        parent = int(hierarchy[0][index][3])
        if parent < 0:
            continue
        area = float(abs(cv2.contourArea(contour)))
        if area <= max(18.0, total_subject_area * max_hole_ratio):
            cv2.drawContours(filled, [contour], -1, 1, thickness=cv2.FILLED)
            filled_area += int(area)
    ratio = float(filled_area) / total_subject_area
    return filled, round(ratio, 4)



def _refine_subject_mask(mask: np.ndarray) -> tuple[np.ndarray, float]:
    """Keep the main silhouette, repair label holes and smooth only the edge."""
    kernel = np.ones((3, 3), dtype=np.uint8)
    refined = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=1)
    refined = _largest_subject_components(refined)
    refined, filled_ratio = _fill_small_internal_holes(refined)
    # A light close after hole repair removes single-pixel notches without
    # changing the product silhouette or repainting packaging details.
    refined = cv2.morphologyEx(refined, cv2.MORPH_CLOSE, kernel, iterations=1)
    return refined, filled_ratio


def _trim_transparent_margin(subject: Image.Image, padding_ratio: float = 0.018) -> Image.Image:
    rgba = subject.convert("RGBA")
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    ys, xs = np.where(alpha > 10)
    if len(xs) < 4:
        return rgba
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    pad_x = max(2, int((x2 - x1) * padding_ratio))
    pad_y = max(2, int((y2 - y1) * padding_ratio))
    return rgba.crop((max(0, x1 - pad_x), max(0, y1 - pad_y), min(rgba.width, x2 + pad_x), min(rgba.height, y2 + pad_y)))


def _enhance_subject_texture(subject: Image.Image) -> Image.Image:
    """Conservative packshot enhancement that never invents or repaints labels."""
    rgba = subject.convert("RGBA")
    rgb = rgba.convert("RGB")
    # Keep contrast changes restrained. Packaging integrity is more important
    # than aggressive sharpening, especially for text and logos.
    rgb = ImageEnhance.Contrast(rgb).enhance(_env_float("COMMERCIAL_SUBJECT_CONTRAST", 1.02))
    rgb = ImageEnhance.Sharpness(rgb).enhance(_env_float("COMMERCIAL_SUBJECT_SHARPNESS", 1.04))
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.35, percent=44, threshold=5))
    rgb.putalpha(rgba.getchannel("A"))
    return rgb


def _grabcut_subject_mask(rgb: np.ndarray, initial_foreground: np.ndarray | None = None) -> np.ndarray:
    h, w = rgb.shape[:2]
    if min(h, w) < 8:
        return np.ones((h, w), dtype=np.uint8)
    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    band = max(2, int(round(min(h, w) * 0.025)))
    mask[:band, :] = cv2.GC_BGD
    mask[-band:, :] = cv2.GC_BGD
    mask[:, :band] = cv2.GC_BGD
    mask[:, -band:] = cv2.GC_BGD
    if initial_foreground is not None:
        mask[initial_foreground > 0] = cv2.GC_PR_FGD
    else:
        x1, x2 = max(band, int(w * 0.12)), min(w - band, int(w * 0.88))
        y1, y2 = max(band, int(h * 0.08)), min(h - band, int(h * 0.92))
        mask[y1:y2, x1:x2] = cv2.GC_PR_FGD
    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(rgb, mask, None, bg_model, fg_model, 5, cv2.GC_INIT_WITH_MASK)
        return np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    except Exception:
        return (initial_foreground > 0).astype(np.uint8) if initial_foreground is not None else np.ones((h, w), dtype=np.uint8)


def _mask_confidence(mask: np.ndarray) -> float:
    h, w = mask.shape[:2]
    total = max(1, h * w)
    coverage = float(np.count_nonzero(mask)) / total
    border = np.concatenate([mask[0, :], mask[-1, :], mask[:, 0], mask[:, -1]])
    border_touch = float(np.count_nonzero(border)) / max(1, len(border))
    if coverage <= 0.004 or coverage >= 0.97:
        return 0.0
    score = 1.0
    if coverage < 0.015:
        score -= 0.35
    if coverage > 0.88:
        score -= 0.45
    if border_touch > 0.52:
        score -= min(0.55, (border_touch - 0.52) * 1.1)
    return round(max(0.0, min(1.0, score)), 4)



def _row_envelope_silhouette(mask: np.ndarray) -> np.ndarray:
    """Build a conservative silhouette envelope for transparent packshots.

    Clear glass regions can resemble the studio background.  Their outer shape
    still needs a small alpha floor so caps and necks do not look detached after
    compositing.  The envelope is intentionally conservative and only spans rows
    between detected product pixels.
    """
    binary = (mask > 0).astype(np.uint8)
    h, w = binary.shape[:2]
    rows = []
    for y in range(h):
        xs = np.where(binary[y] > 0)[0]
        if len(xs) >= 2:
            rows.append((y, int(xs.min()), int(xs.max())))
    if len(rows) < 4:
        return binary

    envelope = np.zeros_like(binary)
    known_y = np.array([item[0] for item in rows], dtype=np.float32)
    known_l = np.array([item[1] for item in rows], dtype=np.float32)
    known_r = np.array([item[2] for item in rows], dtype=np.float32)
    y_start, y_end = int(known_y.min()), int(known_y.max())
    query = np.arange(y_start, y_end + 1, dtype=np.float32)
    left = np.interp(query, known_y, known_l)
    right = np.interp(query, known_y, known_r)
    for offset, y in enumerate(range(y_start, y_end + 1)):
        x1 = max(0, int(round(left[offset])))
        x2 = min(w - 1, int(round(right[offset])))
        if x2 >= x1:
            envelope[y, x1 : x2 + 1] = 1
    envelope = cv2.morphologyEx(envelope, cv2.MORPH_CLOSE, np.ones((5, 3), dtype=np.uint8), iterations=1)
    return envelope


def _glass_safe_alpha(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Return a packaging-safe alpha matte for opaque and transparent products.

    Strong product pixels stay opaque.  Clear glass interiors receive a low
    alpha floor inside the detected silhouette, which preserves their outline
    without pasting the white studio background as an opaque rectangle.
    """
    binary = (mask > 0).astype(np.uint8)
    centres = _border_colour_centres(rgb)
    pixels = rgb.astype(np.float32)
    distances = np.sqrt(((pixels[:, :, None, :] - centres[None, None, :, :]) ** 2).sum(axis=3)).min(axis=2)
    low = _env_float("REFERENCE_ALPHA_DISTANCE_LOW", 10.0)
    high = max(low + 1.0, _env_float("REFERENCE_ALPHA_DISTANCE_HIGH", 62.0))
    colour_alpha = np.clip((distances - low) / (high - low), 0.0, 1.0) * 255.0

    silhouette = _row_envelope_silhouette(binary)
    floor = _env_int("REFERENCE_GLASS_ALPHA_FLOOR", 34)
    alpha = np.maximum(colour_alpha, silhouette.astype(np.float32) * float(floor))
    # Binary foreground includes labels, logos, caps and strong packaging edges.
    # Keep those exact source pixels opaque so branding never gets repainted.
    alpha = np.maximum(alpha, binary.astype(np.float32) * 246.0)

    boundary = cv2.morphologyEx(silhouette, cv2.MORPH_GRADIENT, np.ones((3, 3), dtype=np.uint8))
    alpha = np.maximum(alpha, boundary.astype(np.float32) * 150.0)
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), sigmaX=_env_float("REFERENCE_MASK_EDGE_BLUR", 0.72))
    return np.clip(alpha, 0, 255).astype(np.uint8)




def _generic_subject_alpha(mask: np.ndarray) -> np.ndarray:
    """Return a defringed alpha matte for animals and generic opaque objects.

    The commercial glass matte intentionally keeps a translucent silhouette for
    transparent packaging.  Applying it to every uploaded object can preserve a
    white studio fringe.  Generic objects instead get a conservative inward
    feather so the old background is not pasted over the requested scene.
    """
    binary = (mask > 0).astype(np.uint8)
    feather_px = max(0.55, _env_float("REFERENCE_GENERIC_EDGE_FEATHER_PX", 1.15))
    inside_distance = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    alpha = np.clip(inside_distance / feather_px, 0.0, 1.0) * 255.0
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), sigmaX=0.34)
    return np.clip(alpha, 0, 255).astype(np.uint8)


def _defringe_generic_rgb(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Replace contaminated boundary colours with the nearest interior colour."""
    binary = (mask > 0).astype(np.uint8)
    core = cv2.erode(binary, np.ones((3, 3), dtype=np.uint8), iterations=1)
    if not np.any(core):
        return rgb
    fringe = (binary > 0) & (core == 0)
    if not np.any(fringe):
        return rgb

    # OpenCV labels each zero pixel of the input. Zeros are the trusted interior
    # pixels here, so fringe pixels can borrow the nearest clean source colour.
    distance_input = np.where(core > 0, 0, 1).astype(np.uint8)
    _distance, labels = cv2.distanceTransformWithLabels(
        distance_input,
        cv2.DIST_L2,
        5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    coords = np.argwhere(distance_input == 0)
    if len(coords) == 0:
        return rgb
    indexes = np.clip(labels[fringe].astype(np.int64) - 1, 0, len(coords) - 1)
    nearest = coords[indexes]
    cleaned = rgb.copy()
    cleaned[fringe] = rgb[nearest[:, 0], nearest[:, 1]]
    return cleaned


def _extract_subject_asset(source: Image.Image, *, alpha_profile: str = "product") -> tuple[Image.Image, bool, float, dict[str, object]]:
    """Create a transparent, cropped subject asset with extraction metadata."""
    original = source.convert("RGBA")
    original_rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
    original_alpha = np.asarray(original.getchannel("A"), dtype=np.uint8)

    if np.percentile(original_alpha, 5) < 245:
        mask_full = (original_alpha > 12).astype(np.uint8)
        method = "embedded-alpha"
    else:
        small_rgb, scale = _resize_for_analysis(original_rgb)
        bg_small = _connected_border_background(small_rgb)
        fg_small = (1 - bg_small).astype(np.uint8)
        fg_small = _largest_subject_components(fg_small)
        confidence = _mask_confidence(fg_small)
        if confidence < 0.58:
            fg_small = _grabcut_subject_mask(small_rgb, fg_small)
            fg_small = _largest_subject_components(fg_small)
            method = "grabcut-refined"
        else:
            method = "border-connected"
        if scale < 0.999:
            mask_full = cv2.resize(fg_small, (original_rgb.shape[1], original_rgb.shape[0]), interpolation=cv2.INTER_CUBIC)
            mask_full = (mask_full > 0.40).astype(np.uint8)
        else:
            mask_full = fg_small

    mask_full, filled_hole_ratio = _refine_subject_mask(mask_full.astype(np.uint8))
    ys, xs = np.where(mask_full > 0)
    if len(xs) < max(80, int(source.width * source.height * 0.003)):
        return source.convert("RGBA"), False, 0.0, {"method": "failed", "confidence": 0.0, "border_touch": 1.0}

    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    coverage = float(np.count_nonzero(mask_full)) / max(1, source.width * source.height)
    border = np.concatenate([mask_full[0, :], mask_full[-1, :], mask_full[:, 0], mask_full[:, -1]])
    border_touch = float(np.count_nonzero(border)) / max(1, len(border))
    confidence = _mask_confidence(mask_full)

    profile = (alpha_profile or "product").strip().lower()
    if np.percentile(original_alpha, 5) < 245:
        alpha_np = original_alpha
        rgba_rgb = original_rgb
    elif profile == "generic":
        alpha_np = _generic_subject_alpha(mask_full)
        rgba_rgb = _defringe_generic_rgb(original_rgb, mask_full)
    else:
        alpha_np = _glass_safe_alpha(original_rgb, mask_full)
        rgba_rgb = original_rgb
    alpha = Image.fromarray(alpha_np, mode="L")
    rgba = Image.fromarray(rgba_rgb, mode="RGB").convert("RGBA")
    rgba.putalpha(alpha)
    pad_x = max(3, int((x2 - x1) * 0.025))
    pad_y = max(3, int((y2 - y1) * 0.018))
    crop_box = (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(source.width, x2 + pad_x),
        min(source.height, y2 + pad_y),
    )
    clean = confidence >= _env_float("REFERENCE_MIN_MASK_CONFIDENCE", 0.48)
    return rgba.crop(crop_box), clean, coverage, {
        "method": method,
        "confidence": round(confidence, 4),
        "border_touch": round(border_touch, 4),
        "filled_internal_hole_ratio": round(float(filled_hole_ratio), 4),
        "crop_box": crop_box,
    }


def _extract_subject_rgba(source: Image.Image, *, alpha_profile: str = "product") -> tuple[Image.Image, bool, float]:
    """Compatibility wrapper used by older tests and call sites."""
    subject, clean, coverage, _meta = _extract_subject_asset(source, alpha_profile=alpha_profile)
    return subject, clean, coverage


def prepare_reference_subject_asset(
    source_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    alpha_profile: str = "product",
) -> dict[str, object]:
    """Analyse, cut and persist the uploaded subject as a transparent PNG."""
    source = Image.open(source_path).convert("RGBA")
    subject, clean, coverage, meta = _extract_subject_asset(source, alpha_profile=alpha_profile)
    target_dir = Path(output_dir) if output_dir else Path("/tmp") / "ai_studio_pro" / "reference_subjects"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"subject_{uuid4().hex}.png"
    subject.save(target, format="PNG", optimize=True)
    return {
        "path": str(target),
        "clean_mask": bool(clean),
        "coverage": round(float(coverage), 4),
        "subject_width": int(subject.width),
        "subject_height": int(subject.height),
        **meta,
    }


def _subject_detail_score(subject: Image.Image) -> float:
    try:
        rgb = subject.convert("RGB")
        width = max(48, min(384, rgb.width))
        height = max(48, min(384, rgb.height))
        probe = rgb.resize((width, height), Image.Resampling.LANCZOS)
        arr = np.asarray(probe, dtype=np.float32).mean(axis=2)
        dx = np.abs(np.diff(arr, axis=1)).mean() if arr.shape[1] > 1 else 0.0
        dy = np.abs(np.diff(arr, axis=0)).mean() if arr.shape[0] > 1 else 0.0
        return round(float(dx + dy), 3)
    except Exception:
        return 0.0


def commercial_source_quality_report(
    source_path: str | Path,
    *,
    width: int,
    height: int,
    flyer: bool = False,
    alpha_profile: str = "product",
) -> dict[str, object]:
    """Assess whether a source can support a sharp source-locked composition."""
    try:
        prepared = prepare_reference_subject_asset(source_path, alpha_profile=alpha_profile)
        subject = Image.open(str(prepared["path"])).convert("RGBA")
        max_w = int(max(256, width) * (0.36 if flyer else 0.46))
        max_h = int(max(256, height) * 0.76)
        scale = min(max_w / max(1, subject.width), max_h / max(1, subject.height))
        detail_score = _subject_detail_score(subject)
        # Production integrity rules: tiny product crops must never be enlarged
        # into a client-facing result. A 64x190 crop can look sharp enough to a
        # naive edge metric while still lacking the packaging detail needed for
        # a real flyer. Keep a draft override for operators, but production stays
        # strict by default.
        min_h = _env_int("COMMERCIAL_MIN_SUBJECT_HEIGHT_PX", 420)
        min_w = _env_int("COMMERCIAL_MIN_SUBJECT_WIDTH_PX", 140)
        max_scale = _env_float("COMMERCIAL_MAX_SOURCE_UPSCALE", 2.10)
        min_detail = _env_float("COMMERCIAL_MIN_SOURCE_DETAIL", 0.55)
        hard_min_h = _env_int("COMMERCIAL_HARD_MIN_SUBJECT_HEIGHT_PX", 240)
        hard_min_w = _env_int("COMMERCIAL_HARD_MIN_SUBJECT_WIDTH_PX", 90)
        hard_max_scale = _env_float("COMMERCIAL_HARD_MAX_SOURCE_UPSCALE", 3.00)
        hard_min_detail = _env_float("COMMERCIAL_HARD_MIN_SOURCE_DETAIL", 0.34)
        allow_draft = _env_bool("COMMERCIAL_ALLOW_LOW_RES_DRAFT", False)

        failures: list[str] = []
        warnings: list[str] = []
        if not prepared.get("clean_mask"):
            failures.append("The product could not be isolated cleanly. Use a clearer photo or a simpler background.")
        if subject.height < hard_min_h or subject.width < hard_min_w:
            failures.append(
                f"The detected product crop is only {subject.width}x{subject.height}px; it is too small even for safe enhancement. "
                "Upload a higher-resolution product photo."
            )
        elif subject.height < min_h or subject.width < min_w:
            warnings.append(
                f"The detected product crop is {subject.width}x{subject.height}px; the app will apply conservative source enhancement before compositing."
            )
        if scale > hard_max_scale:
            failures.append(
                f"The product would need {scale:.2f}x enlargement, above the hard safety limit of {hard_max_scale:.2f}x. "
                "Upload a higher-resolution packshot to keep the label readable."
            )
        elif scale > max_scale:
            warnings.append(
                f"The product requires {scale:.2f}x enlargement; conservative enhancement will be applied and the original packaging pixels remain source-locked."
            )
        if detail_score < hard_min_detail:
            failures.append(
                f"The product detail score is {detail_score:.2f}, below the hard minimum of {hard_min_detail:.2f}; use a sharper source image."
            )
        elif detail_score < min_detail:
            warnings.append(
                f"The product detail score is {detail_score:.2f}; the app will enhance the extracted packshot without repainting the label."
            )

        allowed = not failures or allow_draft
        return {
            "allowed": allowed,
            "draft_override": bool(failures and allow_draft),
            "enhancement_required": bool(warnings),
            "warnings": warnings,
            "asset_path": str(prepared["path"]),
            "clean_mask": bool(prepared.get("clean_mask")),
            "mask_method": prepared.get("method"),
            "mask_confidence": prepared.get("confidence"),
            "coverage": prepared.get("coverage"),
            "subject_width": int(subject.width),
            "subject_height": int(subject.height),
            "required_upscale": round(float(scale), 3),
            "detail_score": detail_score,
            "message": " ".join(failures) if failures else (" ".join(warnings) if warnings else "Reference source quality is production-ready."),
        }
    except Exception as exc:
        return {
            "allowed": False,
            "draft_override": False,
            "clean_mask": False,
            "coverage": 0.0,
            "subject_width": 0,
            "subject_height": 0,
            "required_upscale": 0.0,
            "detail_score": 0.0,
            "message": f"Could not inspect the uploaded source: {exc}",
        }


def _resize_subject_for_commercial(subject: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Resize once, conservatively, so labels are not sharpened into artefacts.

    The previous multi-stage resize loop sharpened after every enlargement. On a
    small web thumbnail this created jagged logos and fake packaging details.
    Production now rejects unsafe enlargement before this function is reached
    and applies one restrained resample only.
    """
    target_w, target_h = max(1, int(target[0])), max(1, int(target[1]))
    current = subject.convert("RGBA")
    if current.size == (target_w, target_h):
        return _enhance_subject_texture(current)
    scale = max(target_w / max(1, current.width), target_h / max(1, current.height))
    resized = current.resize((target_w, target_h), Image.Resampling.LANCZOS)
    rgb = resized.convert("RGB")
    if scale <= 1.55:
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.42, percent=56, threshold=5))
    rgb.putalpha(resized.getchannel("A").filter(ImageFilter.GaussianBlur(radius=0.12)))
    return _enhance_subject_texture(rgb)

def _fit_ai_backdrop(generated: Image.Image, width: int, height: int) -> Image.Image:
    backdrop = ImageOps.fit(generated.convert("RGB"), (width, height), Image.Resampling.LANCZOS)
    return backdrop.filter(ImageFilter.UnsharpMask(radius=0.45, percent=106, threshold=4))


def _mix_colour(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, float(amount)))
    return tuple(_clamp(round((1.0 - t) * av + t * bv)) for av, bv in zip(a, b))


def _deterministic_premium_backdrop(source: Image.Image, *, mode: str, width: int, height: int) -> Image.Image:
    """Build a clean premium fallback scene with no hallucinated duplicate product.

    This is used only when AI backdrops fail the visual gate.  It deliberately
    avoids generating any packaging or logo while still providing a polished
    client-facing stage, lighting and depth.
    """
    accent = _dominant_accent(source)
    dark = _mix_colour(accent, (4, 8, 18), 0.78)
    mid = _mix_colour(accent, (20, 24, 42), 0.56)
    light = _mix_colour(accent, (245, 247, 252), 0.70)
    canvas = Image.new("RGB", (width, height), dark)
    draw = ImageDraw.Draw(canvas)

    # Vertical cinematic gradient.
    for y in range(height):
        t = y / max(1, height - 1)
        if t < 0.72:
            colour = _mix_colour(dark, mid, t / 0.72)
        else:
            colour = _mix_colour(mid, _mix_colour(light, accent, 0.12), (t - 0.72) / 0.28)
        draw.line((0, y, width, y), fill=colour)

    # Add soft architectural lighting and depth without drawing fake products.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    if mode == "flyer_poster":
        gd.ellipse((width * 0.50, -height * 0.12, width * 1.08, height * 0.84), fill=(*accent, 104))
        gd.rectangle((0, 0, int(width * 0.44), height), fill=(3, 8, 18, 66))
    elif mode == "creative_image":
        gd.ellipse((width * 0.16, -height * 0.18, width * 1.02, height * 0.88), fill=(*accent, 86))
        gd.ellipse((width * 0.46, height * 0.16, width * 0.98, height * 0.92), outline=(*light, 92), width=max(2, width // 180))
        gd.ellipse((width * 0.54, height * 0.24, width * 0.92, height * 0.84), outline=(*accent, 104), width=max(2, width // 220))
    elif mode == "background_replace":
        gd.ellipse((-width * 0.10, -height * 0.08, width * 0.70, height * 0.96), fill=(*light, 72))
        gd.ellipse((width * 0.38, -height * 0.10, width * 1.10, height * 0.92), fill=(*accent, 60))
    else:
        gd.ellipse((width * 0.22, -height * 0.18, width * 0.90, height * 0.82), fill=(*accent, 100))
        gd.ellipse((width * 0.44, height * 0.12, width * 0.96, height * 0.88), fill=(*light, 38))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(max(20, width // 24))))

    floor = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fd = ImageDraw.Draw(floor)
    floor_y = int(height * 0.74)
    fd.rectangle((0, floor_y, width, height), fill=(_mix_colour(dark, (255, 255, 255), 0.18) + (230,)))
    fd.line((0, floor_y, width, floor_y), fill=(255, 255, 255, 44), width=max(1, height // 360))
    fd.ellipse((int(width * 0.18), int(height * 0.68), int(width * 0.86), int(height * 1.05)), fill=(*accent, 38))
    canvas = Image.alpha_composite(canvas, floor.filter(ImageFilter.GaussianBlur(max(1, width // 520))))
    return canvas.convert("RGB")


def _add_premium_scene_effects(canvas: Image.Image, box: tuple[int, int, int, int], accent: tuple[int, int, int], *, mode: str) -> None:
    """Add restrained deterministic visual energy behind the exact source subject."""
    if mode == "background_replace" or not _env_bool("COMMERCIAL_ADD_DECORATIVE_GEOMETRY", False):
        return
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    subject_w = max(1, x2 - x1)
    subject_h = max(1, y2 - y1)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if mode in {"product_ad", "creative_image"}:
        for scale, alpha in [(1.42, 82), (1.78, 54), (2.12, 32)]:
            rx = int(subject_w * scale)
            ry = int(subject_h * scale * 0.58)
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(*accent, alpha), width=max(2, canvas.width // 360))
    # Stable pseudo-particles: deterministic positions based on index.
    for idx in range(18 if mode != "flyer_poster" else 10):
        dx = ((idx * 73) % max(80, subject_w * 4)) - subject_w * 2
        dy = ((idx * 47) % max(100, subject_h * 2)) - subject_h
        radius = 2 + (idx % 4)
        px = int(cx + dx)
        py = int(cy + dy * 0.62)
        if 0 <= px < canvas.width and 0 <= py < canvas.height:
            draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=(*accent, 80 - (idx % 3) * 14))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=0.8)))


def _hero_zone_box(
    width: int,
    height: int,
    *,
    mode: str,
    reserve_text_space: bool,
    placement_box: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Return the cleanup zone behind the preserved subject.

    Product, flyer and creative backdrops often hallucinate a second package
    that extends below or beside the true hero product.  Clean a broad vertical
    hero corridor for those modes, then redraw deterministic lighting, stage and
    particles.  Background Replace remains local so environmental detail stays
    intact.
    """
    if mode == "flyer_poster":
        # Keep the left information zone available; remove any fake product from
        # the full right-side poster corridor.
        x1 = int(width * (0.28 if reserve_text_space else 0.12))
        return x1, 0, width, height
    if mode == "creative_image":
        return int(width * 0.08), 0, width, height
    if mode == "product_ad":
        return int(width * 0.10), 0, int(width * 0.98), height

    if placement_box is not None:
        px1, py1, px2, py2 = placement_box
        subject_w = max(1, px2 - px1)
        subject_h = max(1, py2 - py1)
        margin_x = max(22, int(subject_w * 0.42))
        margin_y = max(18, int(subject_h * 0.16))
        return (
            max(0, px1 - margin_x),
            max(0, py1 - margin_y),
            min(width, px2 + margin_x),
            min(height, py2 + margin_y),
        )

    return int(width * 0.20), int(height * 0.06), int(width * 0.86), int(height * 0.94)


def _sanitize_ai_backdrop_for_source_lock(
    backdrop: Image.Image,
    *,
    mode: str,
    reserve_text_space: bool,
    placement_box: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    """Suppress hallucinated products without a rectangular matte artifact.

    A softly feathered rounded mask blends inpainted and blurred local colour.
    No opaque rectangle is pasted over the AI scene.
    """
    # V5 production-safe default: always sanitize the hero corridor for source-lock modes.
    # This prevents AI backdrops from keeping a hallucinated second product behind the real source.

    rgb = np.asarray(backdrop.convert("RGB"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    x1, y1, x2, y2 = _hero_zone_box(width, height, mode=mode, reserve_text_space=reserve_text_space, placement_box=placement_box)
    if x2 <= x1 or y2 <= y1:
        return backdrop.convert("RGB")

    mask = np.zeros((height, width), dtype=np.uint8)
    # Rounded rectangle removes duplicates beside the hero product; ellipse
    # softens the visual transition so no rectangular box remains visible.
    radius = max(12, min(x2 - x1, y2 - y1) // 5)
    cv2.rectangle(mask, (x1 + radius, y1), (x2 - radius, y2), 255, thickness=cv2.FILLED)
    cv2.rectangle(mask, (x1, y1 + radius), (x2, y2 - radius), 255, thickness=cv2.FILLED)
    cv2.circle(mask, (x1 + radius, y1 + radius), radius, 255, thickness=cv2.FILLED)
    cv2.circle(mask, (x2 - radius, y1 + radius), radius, 255, thickness=cv2.FILLED)
    cv2.circle(mask, (x1 + radius, y2 - radius), radius, 255, thickness=cv2.FILLED)
    cv2.circle(mask, (x2 - radius, y2 - radius), radius, 255, thickness=cv2.FILLED)

    inpaint_radius = max(3.0, _env_float("COMMERCIAL_HERO_ZONE_INPAINT_RADIUS", 7.0))
    try:
        inpainted = cv2.inpaint(rgb, mask, inpaint_radius, cv2.INPAINT_TELEA)
    except Exception:
        inpainted = rgb.copy()
    blurred = cv2.GaussianBlur(inpainted, (0, 0), sigmaX=max(10.0, min(width, height) / 52.0))
    rebuilt = cv2.addWeighted(inpainted, 0.66, blurred, 0.34, 0.0)
    feather = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(12.0, min(width, height) / 72.0)).astype(np.float32) / 255.0
    feather = np.clip(feather * 0.985, 0.0, 0.985)[:, :, None]
    blended = np.clip(rebuilt.astype(np.float32) * feather + rgb.astype(np.float32) * (1.0 - feather), 0, 255).astype(np.uint8)
    return Image.fromarray(blended, mode="RGB")


def source_lock_backdrop_duplicate_score(
    backdrop_path: str | Path,
    prepared_subject_path: str | Path,
) -> float:
    """Return a conservative duplicate-subject score for an AI backdrop.

    A commercial backdrop is supposed to contain an empty hero zone.  Some
    local checkpoints nevertheless hallucinate a bottle, can or package.  Once
    the exact source-locked asset is composited, that creates a clearly broken
    double-product output.  Detect a source-like silhouette before compositing
    by matching multi-scale subject edges against the empty AI scene.

    The score is intentionally conservative and is only a rejection signal;
    it never edits the source asset.  If detection fails, return 0.0 so the
    caller can still use its ordinary quality gate and deterministic fallback.
    """
    try:
        backdrop_file = Path(backdrop_path)
        subject_file = Path(prepared_subject_path)
        if not backdrop_file.is_file() or not subject_file.is_file():
            return 0.0
        backdrop = np.asarray(Image.open(backdrop_file).convert("RGB"), dtype=np.uint8)
        subject = Image.open(subject_file).convert("RGBA")
        alpha = np.asarray(subject.getchannel("A"), dtype=np.uint8)
        ys, xs = np.where(alpha > 20)
        if not len(xs) or not len(ys):
            return 0.0
        subject = subject.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
        alpha = np.asarray(subject.getchannel("A"), dtype=np.uint8)
        rgb = np.asarray(subject.convert("RGB"), dtype=np.uint8)
        subject_edges = cv2.Canny(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), 50, 150)
        subject_edges = cv2.bitwise_or(subject_edges, cv2.Canny(alpha, 20, 80))
        backdrop_edges = cv2.Canny(cv2.cvtColor(backdrop, cv2.COLOR_RGB2GRAY), 50, 150)
        if np.count_nonzero(subject_edges) < 8 or np.count_nonzero(backdrop_edges) < 8:
            return 0.0

        best = 0.0
        # Covers small and oversized hallucinated products while avoiding huge
        # expensive templates on modest local machines.
        for scale in np.linspace(0.16, 1.18, 18):
            tw = max(8, int(round(subject_edges.shape[1] * float(scale))))
            th = max(8, int(round(subject_edges.shape[0] * float(scale))))
            if tw >= backdrop_edges.shape[1] or th >= backdrop_edges.shape[0]:
                continue
            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            template = cv2.resize(subject_edges, (tw, th), interpolation=interpolation)
            if np.count_nonzero(template) < 8:
                continue
            score = float(cv2.matchTemplate(backdrop_edges, template, cv2.TM_CCOEFF_NORMED).max())
            best = max(best, score)
        return round(best, 4)
    except Exception:
        return 0.0


def source_lock_backdrop_is_safe(
    backdrop_path: str | Path,
    prepared_subject_path: str | Path,
) -> tuple[bool, float]:
    """Reject an AI backdrop when it already contains a source-like product."""
    score = source_lock_backdrop_duplicate_score(backdrop_path, prepared_subject_path)
    threshold = max(0.08, min(0.42, _env_float("COMMERCIAL_DUPLICATE_TEMPLATE_THRESHOLD", 0.095)))
    return score < threshold, score


def _add_subject_glow(canvas: Image.Image, box: tuple[int, int, int, int], accent: tuple[int, int, int]) -> None:
    if not _env_bool("COMMERCIAL_SUBJECT_GLOW_ENABLED", False):
        return
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    spread = max(16, int((x2 - x1) * 0.10))
    draw.rounded_rectangle((x1 - spread, y1 - spread, x2 + spread, y2 + spread), radius=max(16, spread), fill=(*accent, _env_int("COMMERCIAL_SUBJECT_GLOW_ALPHA", 14)))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=max(10, spread // 2))))



def _add_source_lock_podium(canvas: Image.Image, box: tuple[int, int, int, int], accent: tuple[int, int, int], *, mode: str) -> None:
    """Draw a restrained clean stage after backdrop sanitization."""
    if mode not in {"product_ad", "flyer_poster"} or not _env_bool("COMMERCIAL_DRAW_SOURCE_LOCK_PODIUM", False):
        return
    x1, _y1, x2, y2 = box
    width = max(1, x2 - x1)
    stage_w = max(int(canvas.width * 0.28), int(width * 1.72))
    cx = (x1 + x2) // 2
    top_y = min(canvas.height - 26, y2 + max(2, canvas.height // 120))
    stage_h = max(24, canvas.height // 22)
    left = max(10, cx - stage_w // 2)
    right = min(canvas.width - 10, cx + stage_w // 2)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((left, top_y - stage_h // 2, right, top_y + stage_h // 2), fill=(246, 248, 252, 225), outline=(255, 255, 255, 236), width=max(1, canvas.width // 620))
    draw.ellipse((left + 8, top_y + stage_h // 5, right - 8, top_y + stage_h), fill=(18, 24, 34, 92))
    glow_pad = max(8, stage_h // 2)
    draw.ellipse((left - glow_pad, top_y - stage_h, right + glow_pad, top_y + stage_h * 2), fill=(*accent, 18))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=1.1)))


def _add_floor_shadow(canvas: Image.Image, box: tuple[int, int, int, int]) -> None:
    x1, _y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    spread = max(12, (x2 - x1) // 5)
    shadow_h = max(10, canvas.height // 48)
    draw.ellipse((x1 - spread, y2 - shadow_h // 2, x2 + spread, y2 + shadow_h), fill=(0, 0, 0, _env_int("COMMERCIAL_SHADOW_ALPHA", 62)))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=max(7, canvas.width // 110))))


def _add_soft_reflection(canvas: Image.Image, subject: Image.Image, *, px: int, py: int, mode: str) -> None:
    # Reflection is useful for controlled studio packshots only.  It looks
    # artificial in outdoor Background Replace scenes and editorial Creative
    # Reference compositions, so keep it disabled there.
    if mode not in {"product_ad", "flyer_poster"}:
        return
    if not _env_bool("COMMERCIAL_ENABLE_REFLECTION", True):
        return
    reflection = subject.transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGBA")
    alpha = reflection.getchannel("A").filter(ImageFilter.GaussianBlur(radius=8)).point(lambda value: int(value * 0.065))
    reflection.putalpha(alpha)
    reflection = reflection.crop((0, 0, reflection.width, max(1, int(reflection.height * 0.10))))
    canvas.alpha_composite(reflection, (px, py + subject.height - 2))


def _subject_position(
    subject: Image.Image,
    *,
    width: int,
    height: int,
    flyer: bool,
    mode: str,
    reserve_text_space: bool = False,
) -> tuple[int, int]:
    # Raw flyer output is a centered hero image. Move the product right only
    # when a readable overlay is explicitly requested and needs left-side room.
    if flyer and reserve_text_space:
        anchor_x, floor_y = 0.73, 0.82
    elif mode == "background_replace":
        anchor_x, floor_y = 0.52, 0.80
    elif mode == "creative_image":
        anchor_x, floor_y = 0.58, 0.80
    else:
        anchor_x, floor_y = 0.53, 0.80
    px = int(width * anchor_x - subject.width / 2)
    py = int(height * floor_y - subject.height)
    return max(18, min(width - subject.width - 18, px)), max(14, min(height - subject.height - 20, py))


def _place_subject(
    canvas: Image.Image,
    source: Image.Image,
    *,
    flyer: bool,
    mode: str,
    require_clean_subject: bool,
    prepared_subject_path: str | Path | None = None,
    reserve_text_space: bool = False,
    sanitize_backdrop: bool = False,
    alpha_profile: str = "product",
) -> bool:
    if prepared_subject_path:
        subject = Image.open(prepared_subject_path).convert("RGBA")
        alpha = np.asarray(subject.getchannel("A"), dtype=np.uint8)
        # Never trust an opaque rectangular matte as a prepared product asset.
        # Re-extract from the original source so a grey/white box cannot be
        # pasted over the advertising backdrop.
        alpha_has_transparency = bool(alpha.size and int(alpha.min()) < 245 and int(alpha.max()) > 16)
        if alpha_has_transparency:
            clean_mask = True
        else:
            subject, clean_mask, _coverage = _extract_subject_rgba(source, alpha_profile=alpha_profile)
    else:
        subject, clean_mask, _coverage = _extract_subject_rgba(source, alpha_profile=alpha_profile)
    if require_clean_subject and not clean_mask:
        return False

    subject = _trim_transparent_margin(subject)
    subject = _enhance_subject_texture(subject)
    max_w = int(canvas.width * (0.36 if flyer and reserve_text_space else 0.43))
    max_h = int(canvas.height * (0.66 if flyer else 0.70))
    scale = min(max_w / max(1, subject.width), max_h / max(1, subject.height))
    scale = max(0.10, min(scale, _env_float("COMMERCIAL_MAX_SOURCE_UPSCALE", 2.10)))
    target = (max(1, int(subject.width * scale)), max(1, int(subject.height * scale)))
    if target != subject.size:
        subject = _resize_subject_for_commercial(subject, target)
    px, py = _subject_position(
        subject,
        width=canvas.width,
        height=canvas.height,
        flyer=flyer,
        mode=mode,
        reserve_text_space=reserve_text_space,
    )
    box = (px, py, px + subject.width, py + subject.height)

    if sanitize_backdrop:
        cleaned = _sanitize_ai_backdrop_for_source_lock(
            canvas.convert("RGB"),
            mode=mode,
            reserve_text_space=reserve_text_space,
            placement_box=box,
        )
        canvas.alpha_composite(cleaned.convert("RGBA"), (0, 0))

    # Keep the AI-generated scene visually dominant. The backend is allowed to
    # add only restrained physical integration, never a fake podium/template.
    _add_floor_shadow(canvas, box)
    canvas.alpha_composite(subject, (px, py))
    return True


def _clean_overlay_text(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value[:limit]


def _extract_structured_overlay_value(prompt: str, labels: tuple[str, ...]) -> str:
    raw = re.sub(r"\[AI_STUDIO_[^\]]+\]", "", prompt or "", flags=re.IGNORECASE)
    for label in labels:
        match = re.search(rf"(?:^|[.\n])\s*{re.escape(label)}\s*:\s*([^\n.]+)", raw, flags=re.IGNORECASE)
        if match:
            return _clean_overlay_text(match.group(1), 96)
    return ""


def _extract_display_copy(prompt: str) -> tuple[str, str, str]:
    """Return only user-provided copy. Never expose demo/system placeholder text."""
    raw = re.sub(r"\[AI_STUDIO_[^\]]+\]", "", prompt or "", flags=re.IGNORECASE)
    quoted = [item.strip() for item in re.findall(r'["“”]([^"“”]{2,96})["“”]', raw) if item.strip()]
    title = _extract_structured_overlay_value(raw, ("Headline idea", "Headline", "Title")) or (quoted[0] if quoted else "")
    subtitle = _extract_structured_overlay_value(raw, ("Secondary text idea", "Subheadline", "Subtitle")) or (quoted[1] if len(quoted) > 1 else "")
    cta = _extract_structured_overlay_value(raw, ("CTA or price note", "CTA", "Call to action")) or (quoted[-1] if len(quoted) > 2 else "")
    return title.upper()[:48], subtitle.upper()[:72], cta.upper()[:34]

def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        probe = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), probe, font=font)
        if box[2] - box[0] <= max_width or not current:
            current = probe
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_readable_flyer_overlay(canvas: Image.Image, prompt: str, accent: tuple[int, int, int]) -> None:
    title, subtitle, cta = _extract_display_copy(prompt)
    width, height = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    left = int(width * 0.055)
    panel_w = int(width * 0.42)
    top = int(height * 0.11)
    bottom = int(height * 0.78)
    draw.rounded_rectangle((left, top, left + panel_w, bottom), radius=max(20, width // 60), fill=(3, 8, 18, 174))
    canvas.alpha_composite(overlay)

    draw = ImageDraw.Draw(canvas)
    title_font = _font(max(30, width // 18), bold=True)
    subtitle_font = _font(max(15, width // 52), bold=True)
    body_font = _font(max(12, width // 72), bold=False)
    cta_font = _font(max(15, width // 58), bold=True)
    x = left + 24
    y = top + 34
    max_text_w = panel_w - 48
    for line in _wrap(draw, title, title_font, max_text_w)[:3]:
        draw.text((x, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += max(40, int(height * 0.085))
    y += 6
    for line in _wrap(draw, subtitle, subtitle_font, max_text_w)[:2]:
        draw.text((x, y), line, font=subtitle_font, fill=(*accent, 255))
        y += max(22, int(height * 0.044))
    y += 14
    draw.text((x, y), "SOURCE-LOCKED PRODUCT • SOCIAL READY", font=body_font, fill=(235, 240, 248, 228))
    btn_y = bottom - max(64, int(height * 0.11))
    btn_w = min(int(width * 0.23), panel_w - 48)
    btn_h = max(42, int(height * 0.074))
    draw.rounded_rectangle((x, btn_y, x + btn_w, btn_y + btn_h), radius=btn_h // 2, fill=(*accent, 255))
    cta_box = draw.textbbox((0, 0), cta, font=cta_font)
    tx = x + (btn_w - (cta_box[2] - cta_box[0])) / 2
    ty = btn_y + (btn_h - (cta_box[3] - cta_box[1])) / 2 - 2
    draw.text((tx, ty), cta, font=cta_font, fill=(255, 255, 255, 255))


def _extract_flyer_overlay_copy(prompt: str) -> tuple[str, str, list[str], str]:
    """Extract flyer copy from explicit user text only.

    V7 production rule: do not add default slogans over a product unless the
    user supplied usable copy. Default text on top of a packshot looks amateur
    and can cover labels. If the user gives too much text, structured fields or
    quoted text are distilled into title/subtitle/CTA.
    """
    raw = re.sub(r"\[AI_STUDIO_[^\]]+\]", "", prompt or "", flags=re.IGNORECASE)
    quoted = [item.strip() for item in re.findall(r'["“”]([^"“”]{2,96})["“”]', raw) if item.strip()]
    title = _extract_structured_overlay_value(raw, ("Headline idea", "Headline", "Title")) or (quoted[0] if quoted else "")
    subtitle = _extract_structured_overlay_value(raw, ("Secondary text idea", "Subheadline", "Subtitle")) or (quoted[1] if len(quoted) > 1 else "")
    cta = _extract_structured_overlay_value(raw, ("CTA or price note", "CTA", "Call to action")) or (quoted[-1] if len(quoted) > 2 else "")
    details: list[str] = []
    for label in ("Date", "Event date", "Time", "Location"):
        value = _extract_structured_overlay_value(raw, (label,))
        if value:
            details.append(value)
    if not details and len(quoted) > 3:
        details = quoted[2:-1]
    return title.upper()[:48], subtitle.upper()[:72], [item.upper()[:56] for item in details[:4]], cta.upper()[:34]

def _draw_modern_flyer_overlay(canvas: Image.Image, prompt: str, accent: tuple[int, int, int]) -> bool:
    """Draw readable user-provided flyer copy only.

    V7.3 production rule: never draw empty top/bottom bands. If the user did
    not provide headline, subtitle, details or CTA, leave the image clean.
    Text panels are side/bottom safe zones and must not cross the product.
    """
    title, subtitle, details, cta = _extract_flyer_overlay_copy(prompt)
    if not any([title, subtitle, details, cta]):
        return False

    width, height = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Use a readable side card + CTA pill instead of horizontal bands that cut
    # through the hero product. This keeps the preserved source clean.
    margin = max(22, width // 32)
    panel_w = min(int(width * 0.42), max(260, int(width * 0.34)))
    panel_h = max(int(height * 0.30), 190)
    panel_x = margin
    panel_y = max(margin, int(height * 0.08))
    radius = max(18, width // 70)
    draw.rounded_rectangle(
        (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
        radius=radius,
        fill=(2, 8, 16, 172),
        outline=(*accent, 130),
        width=max(1, width // 520),
    )
    canvas.alpha_composite(overlay)

    draw = ImageDraw.Draw(canvas)
    title_font = _font(max(28, width // 18), bold=True)
    subtitle_font = _font(max(15, width // 45), bold=True)
    detail_font = _font(max(14, width // 52), bold=False)
    cta_font = _font(max(15, width // 48), bold=True)

    def _wrap(text: str, font, max_width: int, max_lines: int = 3) -> list[str]:
        words = text.split()
        lines: list[str] = []
        cur = ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if draw.textbbox((0, 0), trial, font=font)[2] <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
                if len(lines) >= max_lines:
                    break
        if cur and len(lines) < max_lines:
            lines.append(cur)
        return lines[:max_lines]

    x = panel_x + max(18, panel_w // 12)
    y = panel_y + max(18, panel_h // 10)
    max_text_w = panel_w - 2 * max(18, panel_w // 12)

    for line in _wrap(title, title_font, max_text_w, 2):
        draw.text((x, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += max(34, int(width * 0.044))
    if subtitle:
        y += max(6, height // 130)
        for line in _wrap(subtitle, subtitle_font, max_text_w, 2):
            draw.text((x, y), line, font=subtitle_font, fill=(*accent, 255))
            y += max(22, int(width * 0.026))
    for item in details[:3]:
        y += max(5, height // 170)
        for line in _wrap(item, detail_font, max_text_w, 1):
            draw.text((x, y), line, font=detail_font, fill=(235, 240, 248, 238))
            y += max(20, int(width * 0.023))

    if cta:
        btn_h = max(42, int(height * 0.062))
        btn_w = min(max(210, int(panel_w * 0.62)), panel_w - 36)
        btn_x = panel_x + (panel_w - btn_w) // 2
        btn_y = min(height - btn_h - margin, panel_y + panel_h + max(18, height // 34))
        draw.rounded_rectangle((btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=btn_h // 2, fill=(*accent, 235))
        cta_box = draw.textbbox((0, 0), cta, font=cta_font)
        tx = btn_x + (btn_w - (cta_box[2] - cta_box[0])) / 2
        ty = btn_y + (btn_h - (cta_box[3] - cta_box[1])) / 2 - 2
        draw.text((tx, ty), cta, font=cta_font, fill=(255, 255, 255, 255))
    return True


def render_readable_flyer_overlay_only(
    generated_path: str | Path,
    *,
    prompt: str,
) -> str | None:
    """Add deterministic readable flyer copy without compositing the source again."""
    try:
        generated_file = Path(generated_path)
        if not generated_file.is_file():
            return None
        canvas = Image.open(generated_file).convert("RGBA")
        accent = _dominant_accent(canvas.convert("RGB"))
        if not _draw_modern_flyer_overlay(canvas, prompt, accent):
            return str(generated_file)
        out_path = generated_file.with_name(f"{generated_file.stem}_flyer_text_overlay.png")
        canvas.convert("RGB").save(out_path, format="PNG", quality=96)
        return str(out_path)
    except Exception:
        return None





def _extract_flyer_copy_with_defaults(prompt: str, accent_name: str = "") -> tuple[str, str, list[str], str]:
    """Return subject-aware flyer copy.

    Priority:
    1) V9 autonomous marker generated by the image understanding step.
    2) Structured user overlay copy if present.
    3) Subject keywords from the prompt created by vision director.
    4) Modern neutral campaign copy.

    Never return generic "AI STUDIO CAMPAIGN" style placeholder copy.
    """
    try:
        marker = parse_autonomous_flyer_marker(prompt)
    except Exception:
        marker = {}
    if marker:
        title = (marker.get("headline") or "").strip()
        subtitle = (marker.get("subheadline") or "").strip()
        cta = (marker.get("cta") or "").strip()
        subject = (marker.get("subject_label") or marker.get("category") or "").strip()
        details = []
        if subject:
            details.append(subject.upper()[:34])
        tone = (marker.get("tone") or "").strip()
        if tone:
            details.append(tone.upper()[:34])
        if title or subtitle or cta:
            return title or "DESIGNED TO STAND OUT", subtitle or "A polished campaign visual built from your image.", details or ["CAMPAIGN READY", "SOURCE PRESERVED"], cta or "DISCOVER MORE"

    title, subtitle, details, cta = _extract_flyer_overlay_copy(prompt)
    if any([title, subtitle, details, cta]):
        return title, subtitle, details or ["CAMPAIGN READY", "SOURCE PRESERVED"], cta or "DISCOVER MORE"

    lowered = (prompt or "").lower()
    if any(word in lowered for word in ("handbag", "purse", "leather bag", "fashion accessory", "bag")):
        return "ELEGANT EVERYDAY STYLE", "A refined black leather look with golden details.", ["PREMIUM FASHION", "SOURCE PRESERVED"], "SHOP THE LOOK"
    if any(word in lowered for word in ("drink", "soda", "cola", "bottle", "refresh", "beverage", "can")):
        return "REFRESH YOUR MOMENT", "A bold drink campaign with crisp commercial energy.", ["SINGLE HERO PRODUCT", "SOURCE PRESERVED"], "DISCOVER MORE"
    if any(word in lowered for word in ("perfume", "cosmetic", "cream", "beauty")):
        return "PURE LUXURY", "A premium beauty visual crafted for elegant campaigns.", ["LUXURY BEAUTY", "CAMPAIGN READY"], "EXPLORE NOW"
    if any(word in lowered for word in ("worm", "insect", "larva", "caterpillar", "bug", "animal", "pet")):
        return "DISCOVER HIDDEN NATURE", "A close-up journey into the small worlds around us.", ["MACRO DISCOVERY", "POSTER READY"], "LEARN MORE"
    if any(word in lowered for word in ("food", "burger", "pizza", "cake", "coffee", "restaurant", "meal")):
        return "FRESH FLAVOR AWAITS", "A clean campaign visual designed to make every detail tempting.", ["FOOD CAMPAIGN", "SOCIAL READY"], "ORDER NOW"
    if any(word in lowered for word in ("person", "portrait", "face", "woman", "man")):
        return "NEW STORY. NEW LOOK.", "A polished editorial visual built around the uploaded portrait.", ["EDITORIAL STYLE", "IDENTITY AWARE"], "VIEW MORE"
    return "DESIGNED TO STAND OUT", "A polished campaign visual built from your uploaded image.", ["CAMPAIGN READY", "SOURCE PRESERVED"], "DISCOVER MORE"


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font,
    *,
    max_width: int,
    fill: tuple[int, int, int, int],
    line_gap: int,
    max_lines: int,
) -> int:
    x, y = xy
    words = (text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        probe = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), probe, font=font)
        if box[2] - box[0] <= max_width or not current:
            current = probe
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    for line in lines[:max_lines]:
        draw.text((x, y), line, font=font, fill=fill)
        box = draw.textbbox((0, 0), line, font=font)
        y += max(1, box[3] - box[1]) + line_gap
    return y



def _render_real_flyer_design(
    source_path: str | Path,
    *,
    prompt: str,
    width: int,
    height: int,
    prepared_subject_path: str | Path | None = None,
    require_clean_subject: bool = False,
    alpha_profile: str = "product",
) -> str | None:
    """Create a finished flyer with exact source subject and real readable copy.

    V9.3 hardens the result:
    - no AI STUDIO placeholder text
    - bigger headline/CTA
    - clean editorial composition
    - exact uploaded subject preserved
    - prompt can be empty because defaults are inferred from the director prompt
    """
    try:
        source = Image.open(source_path).convert("RGB")
        width = max(768, int(width))
        height = max(768, int(height))
        accent = _dominant_accent(source)
        deep = _mix_colour(accent, (8, 11, 18), 0.82)
        soft = _mix_colour(accent, (246, 242, 235), 0.72)
        light = _mix_colour(accent, (255, 255, 255), 0.82)

        canvas = Image.new("RGBA", (width, height), (*soft, 255))
        draw = ImageDraw.Draw(canvas)

        # Premium background: dark editorial left panel + warm product stage.
        for y in range(height):
            t = y / max(1, height - 1)
            col = _mix_colour(light, _mix_colour(accent, (210, 198, 181), 0.55), t)
            draw.line((0, y, width, y), fill=(*col, 255))

        art = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ad = ImageDraw.Draw(art)
        left_w = int(width * 0.42)
        ad.rectangle((0, 0, left_w, height), fill=(*deep, 246))
        card = (int(width * 0.055), int(height * 0.085), int(width * 0.395), int(height * 0.705))
        ad.rounded_rectangle(card, radius=max(26, width // 38), fill=(255,255,255,238))
        ad.rectangle((0, int(height*0.87), width, height), fill=(0,0,0,118))
        # Product stage, smooth arcs behind subject.
        ad.ellipse((int(width*0.42), int(height*0.05), int(width*1.10), int(height*1.08)), fill=(*accent, 62))
        ad.ellipse((int(width*0.54), int(height*0.18), int(width*1.00), int(height*0.86)), outline=(255,255,255,92), width=max(3, width//190))
        ad.ellipse((int(width*0.61), int(height*0.33), int(width*0.96), int(height*0.79)), fill=(255,255,255,30))
        canvas = Image.alpha_composite(canvas, art)

        # Exact subject extraction.
        if prepared_subject_path and Path(prepared_subject_path).is_file():
            subject = Image.open(prepared_subject_path).convert("RGBA")
            clean_mask = True
        else:
            subject, clean_mask, _coverage = _extract_subject_rgba(source, alpha_profile=alpha_profile)
        if require_clean_subject and not clean_mask:
            return None
        subject = _trim_transparent_margin(subject)
        subject = _enhance_subject_texture(subject)

        # Make hero visibly large but do not crop.
        max_w = int(width * 0.43)
        max_h = int(height * 0.64)
        scale = min(max_w / max(1, subject.width), max_h / max(1, subject.height))
        scale = max(0.12, min(scale, _env_float("COMMERCIAL_MAX_SOURCE_UPSCALE", 2.20)))
        target = (max(1, int(subject.width * scale)), max(1, int(subject.height * scale)))
        if target != subject.size:
            subject = _resize_subject_for_commercial(subject, target)
        px = int(width * 0.735 - subject.width / 2)
        py = int(height * 0.77 - subject.height)
        px = max(left_w + int(width*0.045), min(width - subject.width - int(width*0.04), px))
        py = max(int(height*0.10), min(height - subject.height - int(height*0.11), py))
        box = (px, py, px + subject.width, py + subject.height)
        _add_floor_shadow(canvas, box)
        _add_soft_reflection(canvas, subject, px=px, py=py, mode="flyer_poster")
        canvas.alpha_composite(subject, (px, py))

        # Copy, driven by V9 marker or subject-aware defaults.
        title, subtitle, details, cta = _extract_flyer_copy_with_defaults(prompt)
        draw = ImageDraw.Draw(canvas)
        margin = int(width * 0.075)
        text_x = margin
        text_w = int(width * 0.275)
        y = int(height * 0.15)
        kicker_font = _font(max(16, width // 52), bold=True)
        title_font = _font(max(42, width // 16), bold=True)
        subtitle_font = _font(max(20, width // 40), bold=False)
        detail_font = _font(max(16, width // 55), bold=True)
        cta_font = _font(max(19, width // 45), bold=True)

        kicker = "NEW COLLECTION"
        low = (prompt or "").lower()
        if any(w in low for w in ("worm", "insect", "nature", "animal")):
            kicker = "NATURE POSTER"
        elif any(w in low for w in ("drink", "cola", "beverage", "bottle")):
            kicker = "BEVERAGE CAMPAIGN"
        elif any(w in low for w in ("handbag", "bag", "fashion")):
            kicker = "FASHION CAMPAIGN"

        # Kicker in accent, then dark readable title inside white card.
        draw.text((text_x, y), kicker, font=kicker_font, fill=(*accent, 255))
        y += max(34, height // 22)
        y = _draw_wrapped_text(draw, title, (text_x, y), title_font, max_width=text_w, fill=(*deep, 255), line_gap=max(6, height // 110), max_lines=3)
        y += max(12, height // 62)
        y = _draw_wrapped_text(draw, subtitle, (text_x, y), subtitle_font, max_width=text_w, fill=(78, 70, 62, 255), line_gap=max(5, height // 140), max_lines=3)
        y += max(26, height // 38)
        for item in details[:2]:
            bullet_r = max(5, width // 160)
            draw.ellipse((text_x, y + 7, text_x + bullet_r * 2, y + 7 + bullet_r * 2), fill=(*accent, 255))
            _draw_wrapped_text(draw, item, (text_x + bullet_r * 4, y), detail_font, max_width=text_w - bullet_r * 5, fill=(70, 62, 56, 245), line_gap=2, max_lines=1)
            y += max(32, height // 29)

        # CTA button: large and readable.
        btn_h = max(56, int(height * 0.074))
        btn_w = min(int(width * 0.285), int(width * 0.34))
        btn_x = int(width * 0.075)
        btn_y = int(height * 0.755)
        draw.rounded_rectangle((btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=btn_h // 2, fill=(*accent, 255))
        cta_box = draw.textbbox((0, 0), cta, font=cta_font)
        draw.text((btn_x + (btn_w - (cta_box[2] - cta_box[0])) / 2, btn_y + (btn_h - (cta_box[3] - cta_box[1])) / 2 - 2), cta, font=cta_font, fill=(255,255,255,255))

        # Clean footer, no broken glyphs.
        footer_font = _font(max(12, width // 78), bold=True)
        footer = "SOURCE PRESERVED  |  POSTER READY  |  CLIENT REVIEW EXPORT"
        fbox = draw.textbbox((0,0), footer, font=footer_font)
        draw.text(((width - (fbox[2]-fbox[0]))//2, height - max(46, height//18)), footer, font=footer_font, fill=(255,255,255,220))

        output_dir = Path(__file__).resolve().parents[2] / "static" / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"generated_real_flyer_{uuid4().hex}.png"
        canvas.convert("RGB").save(out_path, format="PNG", quality=98)
        return str(out_path)
    except Exception:
        return None


def render_reference_commercial_asset(
    generated_path: str | Path,
    source_path: str | Path,
    *,
    mode: str,
    prompt: str,
    width: int,
    height: int,
    include_text_overlay: bool = False,
    require_clean_subject: bool = False,
    use_ai_backdrop: bool = False,
    prepared_subject_path: str | Path | None = None,
    force_deterministic_backdrop: bool = False,
) -> str | None:
    """Composite a saved source subject over the generated backdrop."""
    resolved = (mode or "").strip().lower()
    if resolved not in _ALLOWED_MODES:
        return None

    if resolved == "flyer_poster" and _env_bool("FLYER_USE_REAL_DESIGN_ENGINE", True):
        return _render_real_flyer_design(
            source_path,
            prompt=prompt,
            width=width,
            height=height,
            prepared_subject_path=prepared_subject_path,
            require_clean_subject=require_clean_subject,
            alpha_profile="product",
        )

    try:
        generated_file = Path(generated_path) if str(generated_path or "").strip() else None
        generated = Image.open(generated_file).convert("RGB") if generated_file is not None and generated_file.is_file() else None
        source = Image.open(source_path).convert("RGB")
        width = max(256, int(width))
        height = max(256, int(height))
        accent = _dominant_accent(source)
        backdrop = (
            _deterministic_premium_backdrop(source, mode=resolved, width=width, height=height)
            if force_deterministic_backdrop or generated is None
            else _fit_ai_backdrop(generated, width, height)
        )
        flyer = resolved == "flyer_poster"
        reserve_text_space = bool(flyer and include_text_overlay)
        canvas = backdrop.convert("RGBA")

        if use_ai_backdrop or resolved in {"product_ad", "flyer_poster", "background_replace"}:
            if not _place_subject(
                canvas,
                source,
                flyer=flyer,
                mode=resolved,
                require_clean_subject=require_clean_subject,
                prepared_subject_path=prepared_subject_path,
                reserve_text_space=reserve_text_space,
                # V7.2: sanitize every source-lock AI backdrop, including Background Replace,
                # because a duplicate product is worse than a softly cleaned hero zone.
                sanitize_backdrop=bool(use_ai_backdrop),
                alpha_profile="product" if resolved in {"product_ad", "flyer_poster"} else "generic",
            ):
                return None
            if flyer and include_text_overlay:
                _draw_modern_flyer_overlay(canvas, prompt, accent)
        elif resolved == "creative_image":
            if not _place_subject(
                canvas,
                source,
                flyer=False,
                mode=resolved,
                require_clean_subject=require_clean_subject,
                prepared_subject_path=prepared_subject_path,
                reserve_text_space=reserve_text_space,
                # V7.2: sanitize every source-lock AI backdrop, including Background Replace,
                # because a duplicate product is worse than a softly cleaned hero zone.
                sanitize_backdrop=bool(use_ai_backdrop),
                alpha_profile="product" if resolved in {"product_ad", "flyer_poster"} else "generic",
            ):
                return None

        overlay_suffix = "_text" if flyer and include_text_overlay else ""
        if generated_file is not None and generated_file.is_file():
            out_path = generated_file.with_name(f"{generated_file.stem}_{resolved}_source_lock{overlay_suffix}.png")
        else:
            output_dir = Path(__file__).resolve().parents[2] / "static" / "images"
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"generated_deterministic_{resolved}_source_lock_{uuid4().hex}{overlay_suffix}.png"
        canvas.convert("RGB").save(out_path, format="PNG", quality=96)
        return str(out_path)
    except Exception:
        return None


def reference_finish_quality_score(path: str | Path) -> float:
    """Reject flat / empty output before exposing it as a successful result."""
    try:
        img = Image.open(path).convert("RGB").resize((192, 192), Image.Resampling.LANCZOS)
        arr = np.asarray(img, dtype=np.float32)
        gray = arr.mean(axis=2)
        contrast = min(float(gray.std()) / 64.0, 1.0)
        saturation = arr.max(axis=2) - arr.min(axis=2)
        saturation_score = min(float(saturation.mean()) / 96.0, 1.0)
        edge_x = np.abs(np.diff(gray, axis=1)).mean()
        edge_y = np.abs(np.diff(gray, axis=0)).mean()
        edge_score = min(float(edge_x + edge_y) / 42.0, 1.0)
        dynamic_range = min(float(np.percentile(gray, 95) - np.percentile(gray, 5)) / 160.0, 1.0)
        return round(contrast * 0.32 + saturation_score * 0.24 + edge_score * 0.22 + dynamic_range * 0.22, 4)
    except Exception:
        return 0.0
