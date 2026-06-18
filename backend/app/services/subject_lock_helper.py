"""Universal subject-lock analysis for production image/video generation.

This module produces subject-aware scores, crop regions and warnings for
people, products, objects, documents and general scenes. Weak person references
are blocked before identity-lock generation; product/object/flyer references
remain usable with auto-crop and review warnings.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math
import re

import numpy as np
from PIL import Image, ImageStat, ImageFilter

from app.core.production_rules import (
    FACE_MIN_COVERAGE_FOR_GENERATION,
    FACE_TARGET_COVERAGE_FOR_PREMIUM_IDENTITY,
    FACE_MIN_IDENTITY_RELIABILITY,
    FACE_MIN_GENERATION_CONFIDENCE,
)

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


# Hard-block only truly unusable person references. 14% remains the
# production target from production_rules; 8-14% is allowed with review/crop.
PERSON_FACE_HARD_MIN_COVERAGE = 8.0


_DOCUMENT_WORDS = {
    "document", "paper", "invoice", "facture", "receipt", "ticket", "contrat",
    "contract", "id", "passport", "poster", "flyer", "text", "texte", "ocr",
    "ورقة", "وثيقة", "فاتورة",
}
_CAR_WORDS = {"car", "voiture", "auto", "vehicle", "سيارة"}
_PET_WORDS = {"dog", "cat", "pet", "chien", "chat", "animal", "كلب", "قط"}
_PRODUCT_WORDS = {
    "product", "produit", "parfum", "perfume", "bottle", "phone", "shoe",
    "chaussure", "watch", "box", "logo", "brand", "منتج",
}
_PERSON_WORDS = {
    "person", "people", "human", "model", "portrait", "face", "man", "woman",
    "homme", "femme", "personne", "visage", "شخص", "انسان", "وجه",
}
_FULL_BODY_WORDS = {
    "fullbody", "full-body", "full_body", "body", "whole body", "head to toe",
    "plein pied", "corps entier", "جسم", "الجسم", "كامل",
}
_BACKGROUND_WORDS = {
    "background", "backdrop", "fond", "arriere plan", "arrière plan", "خلفية", "الخلفية",
}
_SMALL_OBJECT_WORDS = {"small", "tiny", "mini", "petit", "صغير", "بعيد"}


def _safe_float(value: Any, digits: int = 1) -> float | None:
    try:
        if value is None:
            return None
        if not math.isfinite(float(value)):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _score(value: float, low: float, high: float) -> int:
    if high <= low:
        return 0
    pct = (value - low) / (high - low)
    return int(max(0, min(100, round(pct * 100))))


def _hint_words(hint: str) -> set[str]:
    return set(re.findall(r"[\w\u0600-\u06FF]+", (hint or "").lower()))


def _contains_any(hint: str, words: set[str]) -> bool:
    text = (hint or "").lower().replace("-", "_")
    tokens = _hint_words(text)
    for word in words:
        w = word.lower()
        if " " in w:
            if w in text:
                return True
        elif w.replace("-", "_") in tokens or w in tokens:
            return True
    return False


def infer_subject_type(hint: str, real_face_analysis: dict[str, Any] | None, *, width: int, height: int) -> str:
    real = real_face_analysis or {}
    if real.get("face_detected") and int(real.get("face_count") or 0) >= 1:
        return "person_face"

    words = _hint_words(hint)
    if words & _DOCUMENT_WORDS:
        return "document"
    if words & _CAR_WORDS:
        return "car"
    if words & _PET_WORDS:
        return "pet"
    if words & _PRODUCT_WORDS:
        return "product"
    if _contains_any(hint, _FULL_BODY_WORDS) or _contains_any(hint, _PERSON_WORDS):
        # No face was detected, but the user intent says the subject is a person.
        # Treat this as a full-body/pose reference with warnings instead of a
        # product-like object. This prevents "full body" camera captures from
        # being routed like packshots.
        return "person_full_body"

    # Portrait-like frame without face still means a poster/full-body/person may
    # be possible, but without a face we keep it conservative unless the prompt
    # says person/full-body.
    aspect = width / max(1, height)
    if 0.68 <= aspect <= 0.78 and width * height > 600_000:
        return "document_or_poster"

    return "object_or_product"

def _image_stats(image_path: Path) -> dict[str, Any]:
    with Image.open(image_path) as pil:
        rgb = pil.convert("RGB")
        width, height = rgb.size
        small = rgb.resize((160, max(1, round(160 * height / max(1, width)))))
        stat = ImageStat.Stat(small)
        r, g, b = stat.mean
        std = sum(stat.stddev) / 3.0
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b

        gray = small.convert("L")
        # Simple entropy approximates texture/detail; useful if cv2 is absent.
        hist = gray.histogram()
        total = max(1, sum(hist))
        entropy = -sum((count / total) * math.log2(count / total) for count in hist if count)

        if cv2 is not None:
            full_rgb = np.array(rgb)
            full_gray = cv2.cvtColor(full_rgb, cv2.COLOR_RGB2GRAY)
            lap = float(cv2.Laplacian(full_gray, cv2.CV_64F).var())
            edges = cv2.Canny(full_gray, 60, 160)
            edge_density = float(np.count_nonzero(edges)) / max(1, width * height)
        else:
            lap = float(entropy * 40.0)
            edges = np.array(gray.filter(ImageFilter.FIND_EDGES))
            edge_density = float(np.count_nonzero(edges > 32)) / max(1, edges.size)

    return {
        "width": width,
        "height": height,
        "luminance": _safe_float(luminance, 1),
        "contrast": _safe_float(std, 1),
        "entropy": _safe_float(entropy, 2),
        "sharpness_laplacian": _safe_float(lap, 1),
        "edge_density": _safe_float(edge_density, 4),
    }



def _label_lighting(luminance: float | None) -> str:
    lum = float(luminance or 0)
    if lum < 55:
        return "too_dark"
    if lum < 82:
        return "low_light"
    if lum > 214:
        return "too_bright"
    if lum > 185:
        return "bright"
    return "balanced"


def _label_blur(sharpness: float | None) -> str:
    sharp = float(sharpness or 0)
    if sharp < 35:
        return "blurry"
    if sharp < 70:
        return "soft"
    if sharp < 140:
        return "acceptable"
    return "sharp"


def _coverage_status(coverage: float | None) -> str:
    cov = float(coverage or 0)
    if cov < 6:
        return "far_or_tiny"
    if cov < 14:
        return "small"
    if cov <= 86:
        return "usable"
    if cov <= 96:
        return "large_needs_background_separation_review"
    return "full_frame_or_weak_separation"


def _background_analysis(image_path: Path, bbox: dict[str, int] | None, stats: dict[str, Any]) -> dict[str, Any]:
    """Deterministic background quality/scene analysis.

    This is intentionally local and dependency-light. Semantic scene labels become
    stronger when the optional Ollama Vision merge runs; this local layer still
    detects clutter, brightness, contrast and subject separation for every user.
    """
    with Image.open(image_path) as pil:
        rgb = pil.convert("RGB")
        width, height = rgb.size
        arr = np.array(rgb.resize((180, max(1, round(180 * height / max(1, width))))))

    # Analyze border pixels as a proxy for background when no segmentation model
    # is available.
    h, w = arr.shape[:2]
    border = max(4, int(min(h, w) * 0.08))
    strips = [arr[:border, :, :], arr[-border:, :, :], arr[:, :border, :], arr[:, -border:, :]]
    pixels = np.concatenate([x.reshape(-1, 3) for x in strips], axis=0)
    bg_luminance = float(np.mean(0.2126 * pixels[:, 0] + 0.7152 * pixels[:, 1] + 0.0722 * pixels[:, 2]))
    bg_std = float(np.mean(np.std(pixels, axis=0)))

    edge_density = float(stats.get("edge_density") or 0)
    clutter_score = int(max(0, min(100, round((edge_density - 0.018) / 0.105 * 100))))
    clean_score = int(max(0, min(100, 100 - clutter_score)))
    lighting_label = _label_lighting(bg_luminance)

    if clean_score >= 72 and 70 <= bg_luminance <= 205:
        semantic_label = "clean_studio_or_simple_background"
    elif bg_luminance < 58:
        semantic_label = "dark_background"
    elif bg_luminance > 215:
        semantic_label = "bright_or_overexposed_background"
    elif clutter_score >= 62:
        semantic_label = "busy_or_cluttered_background"
    else:
        semantic_label = "natural_or_mixed_background"

    separation_score = 70
    if bbox:
        cov = _crop_coverage(bbox, int(stats["width"]), int(stats["height"]))
        if 12 <= cov <= 78:
            separation_score = 86
        elif cov < 8 or cov > 92:
            separation_score = 46
        else:
            separation_score = 66

    return {
        "local_background_label": semantic_label,
        "background_lighting_label": lighting_label,
        "background_cleanliness_score": clean_score,
        "background_clutter_score": clutter_score,
        "subject_background_separation_score": int(separation_score),
        "estimated_background_luminance": _safe_float(bg_luminance, 1),
        "estimated_background_contrast": _safe_float(bg_std, 1),
        "semantic_source": "local_border_edge_heuristic",
        "notes": [
            "Local background analysis measures cleanliness, exposure and subject separation.",
            "Optional Ollama Vision can add semantic labels such as studio, street, beach or indoor scene.",
        ],
    }


def _small_object_analysis(coverage: float | None, hint: str = "") -> dict[str, Any]:
    cov = float(coverage or 0)
    tiny = cov < 6 or _contains_any(hint, _SMALL_OBJECT_WORDS)
    small = 6 <= cov < 14
    if tiny:
        recommendation = "Retake closer or crop tightly; the object is too small for reliable source-lock."
        confidence = 78
    elif small:
        recommendation = "Usable with crop, but a closer reference will preserve details better."
        confidence = 64
    else:
        recommendation = "Object scale is usable for reference-driven generation."
        confidence = 40
    return {
        "is_small_object_risk": bool(tiny or small),
        "object_scale_label": "tiny" if tiny else "small" if small else "usable",
        "small_object_confidence": confidence,
        "recommendation": recommendation,
    }


def _full_body_analysis(real: dict[str, Any], stats: dict[str, Any], hint: str = "") -> dict[str, Any]:
    pos = real.get("face_position") or {}
    bbox = real.get("primary_face_bbox") or {}
    face_count = int(real.get("face_count") or 0)
    face_detected = bool(real.get("face_detected"))
    coverage = float(pos.get("coverage_percent") or 0)
    width = int(stats.get("width") or 1)
    height = int(stats.get("height") or 1)
    aspect = width / max(1, height)

    bbox_y = float(bbox.get("y") or 0)
    bbox_h = float(bbox.get("h") or 0)
    lower_space_ratio = (height - (bbox_y + bbox_h)) / max(1, height) if bbox else 0
    upper_face = bbox_y / max(1, height) < 0.42 if bbox else False
    prompt_says_full = _contains_any(hint, _FULL_BODY_WORDS)

    candidate_score = 0
    if face_detected and face_count == 1:
        candidate_score += 24
    if 0.45 <= aspect <= 0.85:
        candidate_score += 24
    if coverage <= 14:
        candidate_score += 16
    if lower_space_ratio >= 0.48 and upper_face:
        candidate_score += 24
    if prompt_says_full:
        candidate_score += 24
    candidate_score = int(min(100, candidate_score))

    if face_detected and coverage >= 22:
        label = "portrait_or_upper_body"
    elif candidate_score >= 70:
        label = "probable_full_body_or_pose_reference"
    elif candidate_score >= 45:
        label = "possible_full_body_needs_review"
    elif prompt_says_full:
        label = "requested_full_body_but_not_visually_confirmed"
    else:
        label = "not_full_body"

    return {
        "detected": candidate_score >= 55,
        "label": label,
        "confidence": candidate_score,
        "face_coverage_percent": _safe_float(coverage, 1),
        "lower_frame_space_ratio": _safe_float(lower_space_ratio, 2),
        "frame_aspect_ratio": _safe_float(aspect, 2),
        "prompt_requested_full_body": prompt_says_full,
        "recommendation": (
            "Use full-frame source and avoid face-only crop for pose/body preservation."
            if candidate_score >= 55
            else "For full-body generation, capture head-to-toe framing or provide a full-body reference."
        ),
    }


def _product_analysis(subject_type: str, hint: str, bbox: dict[str, int] | None, stats: dict[str, Any], scores: dict[str, int]) -> dict[str, Any]:
    hint_product = _contains_any(hint, _PRODUCT_WORDS)
    coverage = _crop_coverage(bbox, int(stats["width"]), int(stats["height"]))
    shape = int(scores.get("shape_clarity_score") or 0)
    color = int(scores.get("color_fidelity_readiness") or 0)
    edge_density = float(stats.get("edge_density") or 0)

    product_like_score = 0
    if subject_type == "product":
        product_like_score += 35
    if hint_product:
        product_like_score += 25
    if 8 <= coverage <= 78:
        product_like_score += 18
    if shape >= 55:
        product_like_score += 14
    elif shape >= 40:
        product_like_score += 8
    if color >= 55:
        product_like_score += 8

    # Clean packshot heuristic for DJI/studio captures without a typed prompt:
    # one clear centered object on a simple background is likely a product/object
    # reference and should be surfaced as product-capable, but still marked review.
    local_packshot = (
        subject_type in {"object_or_product", "unknown"}
        and bbox is not None
        and 6 <= coverage <= 62
        and shape >= 38
        and color >= 55
        and edge_density <= 0.035
    )
    if local_packshot:
        product_like_score += 28

    product_like_score = int(min(100, product_like_score))
    detected = subject_type == "product" or product_like_score >= 55
    if hint_product:
        source = "hint_plus_local_shape"
    elif local_packshot:
        source = "local_packshot_heuristic"
    else:
        source = "local_shape_heuristic"

    return {
        "detected": detected,
        "confidence": product_like_score,
        "source": source,
        "packshot_readiness": "good" if product_like_score >= 72 else "review" if product_like_score >= 45 else "weak",
        "recommendation": (
            "Use product/source-lock generation and preserve silhouette, material, colors and branding."
            if detected
            else "Add a product hint or use a cleaner product crop for reliable product-lock."
        ),
    }


def _quality_flags(stats: dict[str, Any]) -> dict[str, Any]:
    lum = float(stats.get("luminance") or 0)
    sharp = float(stats.get("sharpness_laplacian") or 0)
    lighting = _label_lighting(lum)
    blur = _label_blur(sharp)
    return {
        "dark_image_detected": lighting in {"too_dark", "low_light"},
        "lighting_label": lighting,
        "blurry_image_detected": blur in {"blurry", "soft"},
        "sharpness_label": blur,
        "luminance": stats.get("luminance"),
        "sharpness_laplacian": stats.get("sharpness_laplacian"),
        "contrast": stats.get("contrast"),
    }


def _capability_matrix(
    *,
    subject_type: str,
    real: dict[str, Any] | None,
    coverage: float | None,
    stats: dict[str, Any],
    product: dict[str, Any] | None,
    background: dict[str, Any],
    small_object: dict[str, Any],
    full_body: dict[str, Any] | None,
) -> dict[str, Any]:
    real = real or {}
    face_count = int(real.get("face_count") or 0)
    quality = _quality_flags(stats)
    cov_status = _coverage_status(coverage)
    product_detected = bool((product or {}).get("detected")) or subject_type in {"product", "car", "document", "document_or_poster"}
    return {
        "person": {"available": subject_type in {"person_face", "person_full_body"}, "confidence": 95 if subject_type == "person_face" else 62 if subject_type == "person_full_body" else 0},
        "face": {"available": bool(real.get("face_detected")), "confidence": 96 if real.get("face_detected") else 0, "face_count": face_count},
        "multi_person": {"available": face_count > 1, "confidence": 94 if face_count > 1 else 0, "face_count": face_count},
        "full_body": {"available": bool((full_body or {}).get("detected")), "confidence": int((full_body or {}).get("confidence") or 0), "label": (full_body or {}).get("label")},
        "product": {"available": product_detected, "confidence": int((product or {}).get("confidence") or (80 if product_detected else 0)), "source": (product or {}).get("source")},
        "small_object": {"available": bool(small_object.get("is_small_object_risk")), "confidence": int(small_object.get("small_object_confidence") or 0), "label": small_object.get("object_scale_label")},
        "background": {"available": True, "confidence": int(background.get("background_cleanliness_score") or 0), "label": background.get("local_background_label")},
        "dark_image": {"available": bool(quality["dark_image_detected"]), "confidence": 90 if quality["dark_image_detected"] else 20, "label": quality["lighting_label"]},
        "blurry_image": {"available": bool(quality["blurry_image_detected"]), "confidence": 90 if quality["blurry_image_detected"] else 20, "label": quality["sharpness_label"]},
        "far_subject": {"available": cov_status in {"far_or_tiny", "small"}, "confidence": 88 if cov_status == "far_or_tiny" else 65 if cov_status == "small" else 25, "coverage_percent": coverage, "label": cov_status},
    }


def _estimate_subject_bbox(image_path: Path) -> tuple[dict[str, int] | None, dict[str, Any]]:
    """Estimate primary non-face subject using edge/foreground geometry.

    This is not a segmentation model. It is a deterministic conservative fallback
    that gives a useful crop for products/objects when no specialized detector is
    available.
    """
    if cv2 is None:
        return None, {"method": "pil_fallback", "status": "opencv_unavailable"}

    with Image.open(image_path) as pil:
        rgb = np.array(pil.convert("RGB"))
        height, width = rgb.shape[:2]

    # First try a foreground/background delta. This catches clean DJI/studio
    # packshots and tiny objects that edge-contour area thresholds can miss.
    border = max(4, int(min(height, width) * 0.04))
    border_pixels = np.concatenate([
        rgb[:border, :, :].reshape(-1, 3),
        rgb[-border:, :, :].reshape(-1, 3),
        rgb[:, :border, :].reshape(-1, 3),
        rgb[:, -border:, :].reshape(-1, 3),
    ], axis=0)
    bg = np.median(border_pixels, axis=0)
    diff = np.linalg.norm(rgb.astype(np.float32) - bg.astype(np.float32), axis=2)
    mask = diff > 32.0
    if cv2 is not None:
        kernel_fg = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel_fg, iterations=1) > 0
        mask = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE, kernel_fg, iterations=1) > 0
    ys, xs = np.where(mask)
    if xs.size and ys.size:
        area_ratio = float(xs.size) / max(1, width * height)
        if 0.0008 <= area_ratio <= 0.92:
            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            box_w, box_h = max(1, x2 - x1 + 1), max(1, y2 - y1 + 1)
            pad_x = max(6, int(box_w * 0.08))
            pad_y = max(6, int(box_h * 0.08))
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(width, x2 + pad_x)
            y2 = min(height, y2 + pad_y)
            return {
                "x": int(x1),
                "y": int(y1),
                "w": int(max(1, x2 - x1)),
                "h": int(max(1, y2 - y1)),
            }, {
                "method": "foreground_background_delta",
                "status": "estimated",
                "foreground_area_ratio": _safe_float(area_ratio * 100, 2),
            }

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 48, 144)
    kernel = np.ones((9, 9), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[int, int, int, int, float]] = []
    img_area = max(1, width * height)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if area < img_area * 0.002:
            continue
        if area > img_area * 0.96:
            continue
        candidates.append((x, y, w, h, area / img_area))

    if not candidates:
        # central fallback crop to avoid using too much background for products
        margin_x = int(width * 0.12)
        margin_y = int(height * 0.12)
        return {
            "x": margin_x,
            "y": margin_y,
            "w": max(1, width - 2 * margin_x),
            "h": max(1, height - 2 * margin_y),
        }, {"method": "central_fallback", "status": "no_clear_contours"}

    # Merge meaningful contours around the center.
    candidates.sort(key=lambda item: item[4], reverse=True)
    selected = candidates[:6]
    x1 = min(x for x, y, w, h, a in selected)
    y1 = min(y for x, y, w, h, a in selected)
    x2 = max(x + w for x, y, w, h, a in selected)
    y2 = max(y + h for x, y, w, h, a in selected)

    pad_x = int((x2 - x1) * 0.08)
    pad_y = int((y2 - y1) * 0.08)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(width, x2 + pad_x)
    y2 = min(height, y2 + pad_y)

    return {
        "x": int(x1),
        "y": int(y1),
        "w": int(max(1, x2 - x1)),
        "h": int(max(1, y2 - y1)),
    }, {
        "method": "edge_contour_union",
        "status": "estimated",
        "candidate_count": len(candidates),
    }


def _crop_coverage(bbox: dict[str, int] | None, width: int, height: int) -> float:
    if not bbox:
        return 100.0
    return (bbox["w"] * bbox["h"]) / max(1, width * height) * 100.0


def _build_object_scores(stats: dict[str, Any], bbox: dict[str, int] | None) -> dict[str, int]:
    coverage = _crop_coverage(bbox, int(stats["width"]), int(stats["height"]))
    sharp = float(stats.get("sharpness_laplacian") or 0)
    contrast = float(stats.get("contrast") or 0)
    edge_density = float(stats.get("edge_density") or 0)

    sharp_score = _score(sharp, 35, 250)
    contrast_score = _score(contrast, 22, 72)
    edge_score = _score(edge_density, 0.015, 0.11)

    # Best subject crop coverage is not too tiny and not full-frame noisy background.
    if 18 <= coverage <= 78:
        coverage_score = 92
    elif 10 <= coverage < 18:
        coverage_score = 68
    elif 78 < coverage <= 92:
        coverage_score = 70
    else:
        coverage_score = 45

    shape_score = round((edge_score * 0.45) + (coverage_score * 0.35) + (sharp_score * 0.20))
    color_score = round((contrast_score * 0.55) + (sharp_score * 0.20) + 25)
    quality = round((shape_score * 0.40) + (color_score * 0.25) + (sharp_score * 0.25) + (coverage_score * 0.10))
    preservation = min(100, max(0, round((quality * 0.75) + (coverage_score * 0.25))))

    return {
        "reference_quality_score": int(max(0, min(100, quality))),
        "subject_preservation_score": int(max(0, min(100, preservation))),
        "shape_clarity_score": int(max(0, min(100, shape_score))),
        "color_fidelity_readiness": int(max(0, min(100, color_score))),
        "sharpness_score": int(max(0, min(100, sharp_score))),
        "crop_coverage_score": int(max(0, min(100, coverage_score))),
    }


def _face_coverage_readiness_score(coverage: float) -> int:
    # This score feeds the visible Subject Preservation / Reference Quality cards.
    # A crisp single-face reference at 18%+ is production-usable; 24%+ is only the
    # premium target for maximum likeness, not a hard block.
    if coverage >= FACE_TARGET_COVERAGE_FOR_PREMIUM_IDENTITY:
        return 100
    if coverage >= 20:
        return 98
    if coverage >= FACE_MIN_COVERAGE_FOR_GENERATION:
        return 96
    if coverage >= 12:
        return 84
    if coverage >= 8:
        return 62
    return 35


def _face_subject_analysis(real: dict[str, Any], stats: dict[str, Any], hint: str = "") -> dict[str, Any]:
    assessment_like = {
        "alignment_score": real.get("alignment_score"),
        "identity_reliability_score": real.get("identity_reliability_score"),
        "generation_confidence_score": real.get("generation_confidence_score"),
    }
    pos = real.get("face_position") or {}
    coverage = float(pos.get("coverage_percent") or 0.0)
    raw_identity = int(real.get("identity_reliability_score") or 0)
    raw_generation = int(real.get("generation_confidence_score") or 0)
    coverage_score = _face_coverage_readiness_score(coverage)
    identity = min(raw_identity, coverage_score)
    generation = min(raw_generation, coverage_score)
    face_count = int(real.get("face_count") or 0)
    landmark = bool(real.get("landmark_analysis"))

    # Practical production rule: hard-block only references that are genuinely
    # unsafe for identity/source-lock (no single primary face, face too tiny, or
    # extremely weak geometry). Missing FAN landmarks or sub-90 scores must stay
    # visible as warnings, not stop the whole Neural Camera workflow.
    basic_usable = (
        face_count == 1
        and coverage >= PERSON_FACE_HARD_MIN_COVERAGE
        and identity >= 50
        and generation >= 45
    )
    confident = (
        face_count == 1
        and coverage >= FACE_MIN_COVERAGE_FOR_GENERATION
        and identity >= FACE_MIN_IDENTITY_RELIABILITY
        and generation >= FACE_MIN_GENERATION_CONFIDENCE
    )
    hard_block = not basic_usable

    risks: list[str] = []
    recommendations: list[str] = []
    if face_count != 1:
        risks.append("Reference must contain exactly one primary person for identity lock.")
        recommendations.append("Retake or crop so only the target person is visible.")
    if coverage < PERSON_FACE_HARD_MIN_COVERAGE:
        risks.append("Face coverage is too small for reliable identity lock.")
        recommendations.append(f"Move closer or crop so the face covers at least {PERSON_FACE_HARD_MIN_COVERAGE:g}% of the frame before generating.")
    elif coverage < FACE_MIN_COVERAGE_FOR_GENERATION:
        risks.append("Face coverage is below the ideal production target; generation is allowed with review/crop.")
        recommendations.append(f"Optional: crop closer toward {FACE_MIN_COVERAGE_FOR_GENERATION:g}% coverage for stronger likeness, but this reference is usable.")
    elif coverage < FACE_TARGET_COVERAGE_FOR_PREMIUM_IDENTITY:
        recommendations.append(f"Optional: crop closer toward {FACE_TARGET_COVERAGE_FOR_PREMIUM_IDENTITY:g}% coverage for premium likeness, but this reference is generation-ready.")
    if identity < FACE_MIN_IDENTITY_RELIABILITY or generation < FACE_MIN_GENERATION_CONFIDENCE:
        risks.append("Identity/generation readiness is below the premium production threshold; generate with review instead of claiming final likeness.")
        recommendations.append("Use a sharper, closer, better-lit reference for premium likeness, or generate now with auto-crop and visual review.")
    if not landmark:
        risks.append("68-point landmark runtime is not active, so face geometry lock is weaker.")
        recommendations.append("Generation is still allowed with OpenCV/dlib geometry; enable/cache face-alignment model weights for premium production accuracy.")
    if not risks:
        recommendations.append("Reference is strong enough for strict identity-preserving generation.")

    full_body = _full_body_analysis(real, stats, hint)
    quality_flags = _quality_flags(stats)
    small_object = _small_object_analysis(coverage, hint)

    return {
        "subject_type": "person_face",
        "preservation_mode": "strict_person_identity",
        "primary_subject_detected": face_count >= 1,
        "subject_count": face_count,
        "primary_subject_bbox": real.get("primary_face_bbox"),
        "primary_subject_bbox_label": real.get("primary_face_bbox_label"),
        "primary_subject_coverage_percent": _safe_float(coverage, 1),
        "reference_quality_score": generation,
        "subject_preservation_score": identity,
        "raw_identity_reliability_score": raw_identity,
        "raw_generation_confidence_score": raw_generation,
        "coverage_readiness_score": coverage_score,
        "shape_clarity_score": int(real.get("alignment_score") or 0),
        "color_fidelity_readiness": 80 if (real.get("face_region_quality") or {}).get("lighting_label") == "balanced" else 62,
        "scores": assessment_like,
        "hard_block_generation": hard_block,
        "can_generate": basic_usable,
        "can_generate_confidently": confident,
        "warning_level": "low" if confident else "medium" if basic_usable else "high",
        "quality_flags": quality_flags,
        "full_body_analysis": full_body,
        "small_object_analysis": small_object,
        "risks": risks[:6],
        "recommendations": recommendations[:6],
        "prompt_en": (
            "Preserve the exact same person from the reference. Lock facial geometry, apparent gender presentation, skin tone, hair/facial-hair silhouette, jaw, nose and eye spacing. "
            "Do not redesign, beautify into another person, feminize, masculinize or change age impression."
        ),
        "prompt_fr": (
            "Préserver exactement la même personne de la référence. Verrouiller géométrie du visage, présentation de genre apparente, teint, cheveux/barbe, mâchoire, nez et écartement des yeux. "
            "Ne pas redessiner, ne pas embellir en changeant de personne, ne pas féminiser, masculiniser ou changer l'impression d'âge."
        ),
    }


def _generic_subject_analysis(image_path: Path, hint: str, subject_type: str) -> dict[str, Any]:
    stats = _image_stats(image_path)
    bbox, bbox_meta = _estimate_subject_bbox(image_path)
    scores = _build_object_scores(stats, bbox)
    coverage = _crop_coverage(bbox, int(stats["width"]), int(stats["height"]))
    quality = scores["reference_quality_score"]
    preservation = scores["subject_preservation_score"]

    is_document = subject_type in {"document", "document_or_poster"}
    # Product/object/flyer references must never be blocked by face-only or
    # conservative segmentation rules. Low scores are warnings only; the
    # generation endpoint will auto-crop/fallback and the worker will refund
    # credits if the provider actually fails.
    hard_block = False
    confident = quality >= 75 and preservation >= 75 and scores["shape_clarity_score"] >= 65 and 10 <= coverage <= 86

    risks: list[str] = []
    recommendations: list[str] = []
    if coverage < 6:
        risks.append("Primary subject appears too small or too hard to isolate.")
        recommendations.append("Retake closer or crop tightly around the subject.")
    if subject_type == "person_full_body":
        risks.append("Full-body/person intent was detected, but no confident face was found; identity lock is not guaranteed.")
        recommendations.append("For exact same-person output, capture a clearer face or provide a separate face reference. For pose/body only, full-frame generation is allowed with review.")
    if coverage > 96:
        risks.append("Subject/background separation is weak because the crop covers almost the full image.")
        recommendations.append("Use a cleaner background or crop around the main subject.")
    if scores["sharpness_score"] < 55:
        risks.append("Reference is not sharp enough for reliable detail preservation.")
        recommendations.append("Retake with better focus and more stable camera position.")
    if scores["shape_clarity_score"] < 35:
        risks.append("Subject edges/shape are not clear enough for strict matching.")
        recommendations.append("Use stronger lighting and a less cluttered background.")
    if is_document and scores["sharpness_score"] < 75:
        risks.append("Document/text may not remain readable if generated directly.")
        recommendations.append("Use document rectification/OCR mode before any generation.")
        # Advisory only: let the user generate, but preserve this risk text.

    if not risks:
        recommendations.append("Subject is clear enough for reference-driven generation. Keep crop as the main source.")

    prompt_en_map = {
        "product": "Preserve the exact product from the reference: same silhouette, proportions, material, color, label/branding if visible, cap/edges/details. Do not redesign or invent new branding.",
        "car": "Preserve the exact vehicle look from the reference: same body shape, color, proportions, lights, wheels and visible design details. Do not change model identity.",
        "pet": "Preserve the same animal from the reference: same body shape, fur color/pattern, face structure and markings. Do not morph into another animal.",
        "document": "Preserve the exact document layout and visible text. Do not rewrite, paraphrase, invent or remove text. Keep structure and readability.",
        "document_or_poster": "Preserve the exact layout, text and visual structure. Do not rewrite, invent or remove visible text.",
        "person_full_body": "Preserve the visible person/body pose reference from the image. Keep the same pose direction, body framing, clothing silhouette and camera perspective. If no face is confidently detected, do not claim exact identity; use it as pose/body reference.",
        "object_or_product": "Preserve the exact subject from the reference: same shape, proportions, color, texture, material and visible details. Do not redesign or invent a different object.",
    }
    prompt_fr_map = {
        "product": "Préserver exactement le produit de la référence : même silhouette, proportions, matière, couleur, étiquette/branding si visible, bouchon/bords/détails. Ne pas redessiner ni inventer une nouvelle marque.",
        "car": "Préserver exactement l'apparence du véhicule : même forme, couleur, proportions, feux, roues et détails visibles. Ne pas changer l'identité du modèle.",
        "pet": "Préserver le même animal : même forme, couleur/motif du pelage, structure du visage et marques visibles. Ne pas transformer en autre animal.",
        "document": "Préserver exactement la mise en page et le texte visible. Ne pas réécrire, paraphraser, inventer ou supprimer du texte. Garder structure et lisibilité.",
        "document_or_poster": "Préserver exactement la mise en page, le texte et la structure visuelle. Ne pas réécrire, inventer ou supprimer le texte visible.",
        "person_full_body": "Préserver la personne/pose visible dans l'image. Garder la même direction de pose, le cadrage du corps, la silhouette des vêtements et la perspective caméra. Si aucun visage n'est détecté avec confiance, ne pas promettre une identité exacte; utiliser comme référence pose/corps.",
        "object_or_product": "Préserver exactement le sujet de la référence : même forme, proportions, couleur, texture, matière et détails visibles. Ne pas redessiner ni inventer un autre objet.",
    }

    return {
        "subject_type": subject_type,
        "preservation_mode": "universal_subject_lock",
        "primary_subject_detected": bbox is not None,
        "subject_count": 1 if bbox else 0,
        "primary_subject_bbox": bbox,
        "primary_subject_bbox_label": f"x{bbox['x']} y{bbox['y']} w{bbox['w']} h{bbox['h']}" if bbox else None,
        "primary_subject_coverage_percent": _safe_float(coverage, 1),
        "bbox_detection": bbox_meta,
        "image_stats": stats,
        **scores,
        "hard_block_generation": False,
        "can_generate": True,
        "can_generate_confidently": confident,
        "warning_level": "medium" if not confident else "low",
        "risks": risks[:6],
        "recommendations": recommendations[:6],
        "prompt_en": prompt_en_map.get(subject_type, prompt_en_map["object_or_product"]),
        "prompt_fr": prompt_fr_map.get(subject_type, prompt_fr_map["object_or_product"]),
    }



def _finalize_subject_analysis(
    analysis: dict[str, Any],
    image_path: Path,
    hint: str,
    stats: dict[str, Any],
    real_face_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    subject_type = str(analysis.get("subject_type") or "unknown")
    bbox = analysis.get("primary_subject_bbox")
    coverage = analysis.get("primary_subject_coverage_percent")

    # Local production signals available for every image, even without semantic
    # vision models. These make the feature honest and useful offline.
    background = _background_analysis(image_path, bbox, stats)
    quality_flags = _quality_flags(stats)
    small_object = _small_object_analysis(float(coverage or 0), hint)

    scores_for_product = {
        "shape_clarity_score": int(analysis.get("shape_clarity_score") or 0),
        "color_fidelity_readiness": int(analysis.get("color_fidelity_readiness") or 0),
    }
    product = _product_analysis(subject_type, hint, bbox, stats, scores_for_product)

    full_body = analysis.get("full_body_analysis")
    if not full_body:
        full_body = _full_body_analysis(real_face_analysis or {}, stats, hint)
        if subject_type == "person_full_body":
            full_body["detected"] = True
            full_body["label"] = full_body.get("label") if full_body.get("confidence", 0) >= 45 else "requested_full_body_reference"
            full_body["confidence"] = max(int(full_body.get("confidence") or 0), 58)

    # Strengthen visible risks/recommendations with the requested pro checks.
    risks = list(analysis.get("risks") or [])
    recommendations = list(analysis.get("recommendations") or [])
    if quality_flags["dark_image_detected"]:
        risks.append(f"Image lighting is {quality_flags['lighting_label']}; generation may lose detail.")
        recommendations.append("Retake with more balanced light or select a brighter camera exposure.")
    if quality_flags["blurry_image_detected"]:
        risks.append(f"Image sharpness is {quality_flags['sharpness_label']}; subject details may drift.")
        recommendations.append("Retake with stable focus, lower motion blur and a cleaner lens.")
    if small_object["is_small_object_risk"]:
        risks.append("Primary subject/object appears small or far from the camera.")
        recommendations.append(small_object["recommendation"])
    if background["background_clutter_score"] >= 62:
        risks.append("Background is busy/cluttered and may compete with the subject.")
        recommendations.append("Use a cleaner background or select background replacement mode.")
    if full_body.get("detected") and subject_type == "person_face":
        recommendations.append("Full-body/pose cues are visible; prefer full-frame source over face-only crop for body/pose preservation.")

    analysis["image_stats"] = stats
    analysis["quality_flags"] = quality_flags
    analysis["background_analysis"] = background
    analysis["small_object_analysis"] = small_object
    analysis["product_analysis"] = product
    analysis["full_body_analysis"] = full_body
    analysis["capability_matrix"] = _capability_matrix(
        subject_type=subject_type,
        real=real_face_analysis or {},
        coverage=float(coverage or 0),
        stats=stats,
        product=product,
        background=background,
        small_object=small_object,
        full_body=full_body,
    )
    analysis["neural_camera_capabilities"] = [
        "person_detection_from_face_or_person_hint",
        "face_detection_count_bbox_pose_quality",
        "multi_face_detection",
        "subject_distance_and_coverage_check",
        "blur_detection_laplacian",
        "dark_low_light_detection_luminance",
        "product_detection_hint_plus_shape_heuristic",
        "small_object_distance_risk",
        "background_cleanliness_lighting_separation_analysis",
        "full_body_pose_reference_heuristic",
        "optional_ollama_vision_semantic_understanding_when_enabled",
    ]
    analysis["risks"] = list(dict.fromkeys(risks))[:8]
    analysis["recommendations"] = list(dict.fromkeys(recommendations))[:8]
    return analysis


def analyze_universal_subject(
    image_path: str | Path,
    hint: str = "",
    real_face_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(image_path)
    stats = _image_stats(path)
    subject_type = infer_subject_type(
        hint,
        real_face_analysis,
        width=int(stats["width"]),
        height=int(stats["height"]),
    )

    if subject_type == "person_face":
        return _finalize_subject_analysis(_face_subject_analysis(real_face_analysis or {}, stats, hint), path, hint, stats, real_face_analysis or {})

    return _finalize_subject_analysis(_generic_subject_analysis(path, hint, subject_type), path, hint, stats, real_face_analysis or {})
