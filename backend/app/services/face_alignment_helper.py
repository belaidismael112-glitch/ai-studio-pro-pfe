"""Professional local face-analysis helper for Smart Agent Neural Camera Analysis.

The helper does NOT identify a person. It extracts face geometry, framing,
lighting, sharpness and prompt-safe pose cues from the uploaded reference image.
It is designed to work offline with OpenCV/Pillow; optional detectors are used
only when available.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import math
import os
import sys

import numpy as np

from app.core.production_rules import (
    FACE_MIN_COVERAGE_FOR_GENERATION,
    FACE_TARGET_COVERAGE_FOR_PREMIUM_IDENTITY,
    FACE_MIN_IDENTITY_RELIABILITY,
    FACE_MIN_GENERATION_CONFIDENCE,
)
from PIL import Image, ImageStat

try:  # OpenCV is optional at import-time but required for real face detection.
    import cv2  # type: ignore
except Exception:  # pragma: no cover - production fallback
    cv2 = None  # type: ignore

try:  # Optional extra detector; no model files required for HOG face detection.
    import dlib  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    dlib = None  # type: ignore


_FACE_ALIGNMENT_MODEL_CACHE: dict[str, Any] = {}


def _backend_dir() -> Path:
    """Return the backend directory from this helper path."""
    return Path(__file__).resolve().parents[2]


def _face_alignment_vendor_path() -> Path:
    return _backend_dir() / "vendor" / "face_alignment_source"


def _read_backend_env_file() -> dict[str, str]:
    """Read backend/.env directly for optional face-alignment runtime flags.

    Some launchers load Pydantic settings from .env without exporting values to
    os.environ. The face-alignment runtime needs these values before model load,
    so we read backend/.env as a fallback.
    """
    env_path = _backend_dir() / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    try:
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    except Exception:
        return values

    return values


def _env_flag(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None and str(value).strip() != "":
        return str(value).strip()

    return _read_backend_env_file().get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    fallback = "1" if default else ""
    return _env_flag(name, fallback).lower() in {"1", "true", "yes", "on"}


def _face_alignment_dependency_status() -> dict[str, Any]:
    vendor = _face_alignment_vendor_path()
    package_dir = vendor / "face_alignment"
    status: dict[str, Any] = {
        "vendor_present": package_dir.exists(),
        "vendor_path": str(vendor),
        "source": "uploaded face-alignment-master",
    }
    if not package_dir.exists():
        status.update({"active": False, "status": "vendor_missing"})
        return status
    try:
        if str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        import face_alignment as fa  # type: ignore
        status.update(
            {
                "import_ok": True,
                "version": getattr(fa, "__version__", "unknown"),
                "active": True,
                "status": "available",
            }
        )
    except Exception as exc:  # pragma: no cover - depends on optional torch stack
        status.update(
            {
                "import_ok": False,
                "active": False,
                "status": "dependency_missing",
                "error": str(exc),
                "install_hint": "Install backend/requirements.txt dependencies or backend/vendor/face_alignment_source/requirements.txt.",
            }
        )
    return status


def _get_face_alignment_model() -> tuple[Any | None, dict[str, Any]]:
    """Load the vendored face-alignment-master FAN model when dependencies/weights exist.

    This is optional and cached. If PyTorch or model weights are not installed/cached, the
    app still falls back to OpenCV/dlib and returns an explicit engine status instead of
    pretending that 68-point FAN landmarks were used.
    """
    status = _face_alignment_dependency_status()
    if not status.get("active"):
        return None, status
    if _env_bool("AI_STUDIO_DISABLE_FACE_ALIGNMENT_MASTER"):
        status.update({"active": False, "status": "disabled_by_env"})
        return None, status

    device = _env_flag("AI_STUDIO_FACE_ALIGNMENT_DEVICE", "cpu") or "cpu"
    detector = _env_flag("AI_STUDIO_FACE_ALIGNMENT_DETECTOR", "sfd") or "sfd"
    cache_key = f"{device}:{detector}:2d"
    if cache_key in _FACE_ALIGNMENT_MODEL_CACHE:
        status.update({"status": "active_cached", "device": device, "detector": detector})
        return _FACE_ALIGNMENT_MODEL_CACHE[cache_key], status

    allow_download = _env_bool("AI_STUDIO_ALLOW_FACE_ALIGNMENT_DOWNLOAD")
    try:  # pragma: no cover - may require model weights/network/cache in runtime
        if str(_face_alignment_vendor_path()) not in sys.path:
            sys.path.insert(0, str(_face_alignment_vendor_path()))
        import torch  # type: ignore
        import face_alignment as fa  # type: ignore

        checkpoints_dir = Path(torch.hub.get_dir()) / "checkpoints"
        required_weights = ["2DFAN4-11f355bf06.pth.tar"]
        if detector == "sfd":
            required_weights.append("s3fd-619a316812.pth")
        missing_weights = [name for name in required_weights if not (checkpoints_dir / name).exists()]
        if missing_weights and allow_download:
            status.update(
                {
                    "status": "downloading_model_weights",
                    "device": device,
                    "detector": detector,
                    "missing_weights": missing_weights,
                    "weights_dir": str(checkpoints_dir),
                }
            )
        if missing_weights and not allow_download:
            status.update(
                {
                    "active": False,
                    "status": "model_weights_missing",
                    "device": device,
                    "detector": detector,
                    "missing_weights": missing_weights,
                    "weights_dir": str(checkpoints_dir),
                    "install_hint": "Pre-cache face-alignment-master FAN/detector weights or set AI_STUDIO_ALLOW_FACE_ALIGNMENT_DOWNLOAD=1 on a machine with internet.",
                }
            )
            return None, status

        model = fa.FaceAlignment(
            fa.LandmarksType.TWO_D,
            device=device,
            face_detector=detector,
            flip_input=False,
            compile=False,
        )
        _FACE_ALIGNMENT_MODEL_CACHE[cache_key] = model
        status.update({"status": "active", "device": device, "detector": detector})
        return model, status
    except Exception as exc:
        status.update(
            {
                "active": False,
                "status": "model_unavailable",
                "device": device,
                "detector": detector,
                "error": str(exc),
                "install_hint": "Make sure torch/scipy/scikit-image/numba/tqdm are installed and FAN detector/model weights are available/cached.",
            }
        )
        return None, status


def _points_center(points: np.ndarray) -> tuple[float, float]:
    return float(points[:, 0].mean()), float(points[:, 1].mean())


def _label_yaw_from_landmarks(landmarks: np.ndarray) -> str:
    # 68-point FAN landmarks: eye centers and nose tip provide a robust prompt-safe yaw cue.
    left_eye = landmarks[36:42]
    right_eye = landmarks[42:48]
    nose_tip = landmarks[30]
    lx, ly = _points_center(left_eye)
    rx, ry = _points_center(right_eye)
    eye_mid_x = (lx + rx) / 2.0
    half_eye_distance = max(1.0, abs(rx - lx) / 2.0)
    nose_offset = (float(nose_tip[0]) - eye_mid_x) / half_eye_distance
    if nose_offset > 0.18:
        return "slight turn toward image left"
    if nose_offset < -0.18:
        return "slight turn toward image right"
    return "front-facing / balanced"


def _landmark_bbox(landmarks: np.ndarray) -> dict[str, int]:
    x1, y1 = landmarks[:, 0].min(), landmarks[:, 1].min()
    x2, y2 = landmarks[:, 0].max(), landmarks[:, 1].max()
    return {"x": int(round(x1)), "y": int(round(y1)), "w": int(round(x2 - x1)), "h": int(round(y2 - y1))}


def _analyze_fan_landmarks(image_path: Path, rgb: np.ndarray, main_box: tuple[int, int, int, int] | None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    model, status = _get_face_alignment_model()
    if model is None:
        return None, status
    try:  # pragma: no cover - runtime model inference
        detected_faces = None
        if main_box:
            x, y, w, h = main_box
            detected_faces = [np.array([x, y, x + w, y + h])]
        landmarks_list = model.get_landmarks_from_image(rgb, detected_faces=detected_faces)
        if not landmarks_list:
            status.update({"active": False, "status": "no_landmarks"})
            return None, status
        landmarks = np.asarray(landmarks_list[0], dtype=np.float32)
        if landmarks.shape[0] < 68:
            status.update({"active": False, "status": "insufficient_landmarks", "landmark_count": int(landmarks.shape[0])})
            return None, status

        left_eye = landmarks[36:42]
        right_eye = landmarks[42:48]
        mouth_outer = landmarks[48:60]
        jaw = landmarks[0:17]
        nose_tip = landmarks[30]
        lx, ly = _points_center(left_eye)
        rx, ry = _points_center(right_eye)
        dx, dy = rx - lx, ry - ly
        roll = math.degrees(math.atan2(dy, dx)) if abs(dx) > 1 else 0.0
        eye_distance = math.sqrt(dx * dx + dy * dy)
        mb = _landmark_bbox(mouth_outer)
        lb = _landmark_bbox(landmarks)
        face_width = max(1, lb["w"])
        eye_distance_pct = eye_distance / face_width * 100.0
        mouth_width_pct = mb["w"] / face_width * 100.0
        yaw_label = _label_yaw_from_landmarks(landmarks)
        eye_line = "level" if abs(roll) <= 3.5 else ("tilted clockwise" if roll > 0 else "tilted counter-clockwise")

        status.update(
            {
                "active": True,
                "status": "landmarks_active",
                "landmark_count": int(landmarks.shape[0]),
                "used_for_pose": True,
            }
        )
        return (
            {
                "landmark_count": int(landmarks.shape[0]),
                "landmark_bbox": lb,
                "jaw_bbox": _landmark_bbox(jaw),
                "left_eye_center": {"x": _safe_float(lx, 1), "y": _safe_float(ly, 1)},
                "right_eye_center": {"x": _safe_float(rx, 1), "y": _safe_float(ry, 1)},
                "nose_tip": {"x": _safe_float(float(nose_tip[0]), 1), "y": _safe_float(float(nose_tip[1]), 1)},
                "mouth_bbox": mb,
                "roll_degrees": _safe_float(roll, 1),
                "eye_line": eye_line,
                "yaw_label": yaw_label,
                "eye_distance_percent_of_landmark_face_width": _safe_float(eye_distance_pct, 1),
                "mouth_width_percent_of_landmark_face_width": _safe_float(mouth_width_pct, 1),
                "prompt_features": [
                    "68-point face-alignment-master FAN landmarks available",
                    f"FAN yaw cue: {yaw_label}",
                    f"FAN eye-line: {eye_line}, roll {round(roll, 1)} degrees",
                    f"FAN mouth width {round(mouth_width_pct, 1)}% of landmark face width",
                ],
            },
            status,
        )
    except Exception as exc:
        status.update({"active": False, "status": "landmark_runtime_error", "error": str(exc)})
        return None, status


@dataclass
class FaceAlignmentProfile:
    image_size: str
    orientation: str
    framing: str
    lighting: str
    color_temperature: str
    contrast: str
    sharpness_note: str
    likely_subject_region: str
    alignment_notes: list[str]
    prompt_details_en: str
    prompt_details_fr: str
    real_face_analysis: dict[str, Any]
    production_assessment: dict[str, Any]
    readable_summary_en: str
    readable_summary_fr: str
    detected_face_prompt_en: str
    detected_face_prompt_fr: str

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _label_orientation(w: int, h: int) -> str:
    if w > h * 1.18:
        return "landscape"
    if h > w * 1.18:
        return "portrait"
    return "square/near-square"


def _brightness_label(mean: float) -> str:
    if mean < 70:
        return "low-key / dark"
    if mean > 185:
        return "bright / high-key"
    return "balanced"


def _temperature_label(r: float, b: float) -> str:
    if r > b + 12:
        return "warm"
    if b > r + 12:
        return "cool"
    return "neutral"


def _contrast_label(std: float) -> str:
    if std < 35:
        return "soft contrast"
    if std > 72:
        return "strong contrast"
    return "medium contrast"


def _sharpness_label(lap_var: float) -> str:
    if lap_var < 55:
        return "soft / slightly blurry"
    if lap_var > 240:
        return "crisp"
    return "usable"


def _safe_float(value: float | int | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _load_cascade(name: str):
    if cv2 is None:
        return None
    try:
        path = str(Path(cv2.data.haarcascades) / name)  # type: ignore[attr-defined]
        cascade = cv2.CascadeClassifier(path)
        return cascade if not cascade.empty() else None
    except Exception:
        return None


def _bbox_clip(box: tuple[int, int, int, int], w: int, h: int) -> tuple[int, int, int, int]:
    x, y, bw, bh = [int(v) for v in box]
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    bw = max(1, min(bw, w - x))
    bh = max(1, min(bh, h - y))
    return x, y, bw, bh


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def _center_distance_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy = ax + aw / 2.0, ay + ah / 2.0
    bcx, bcy = bx + bw / 2.0, by + bh / 2.0
    dist = math.sqrt((acx - bcx) ** 2 + (acy - bcy) ** 2)
    scale = max(1.0, max(aw, ah, bw, bh))
    return dist / scale


def _looks_like_duplicate_face(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    # OpenCV cascades can return the same face from default + alt2/profile with
    # shifted boxes. IoU alone misses these cases, so also compare centers and
    # relative size. This prevents one real person being counted as two faces.
    iou = _iou(a, b)
    center_ratio = _center_distance_ratio(a, b)
    area_a = max(1, a[2] * a[3])
    area_b = max(1, b[2] * b[3])
    area_ratio = min(area_a, area_b) / max(area_a, area_b)
    return iou >= 0.22 or (center_ratio <= 0.42 and area_ratio >= 0.45)


def _merge_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: item[2] * item[3], reverse=True):
        if all(not _looks_like_duplicate_face(box, current) for current in merged):
            merged.append(box)
    return merged


def _detect_faces(gray: np.ndarray, rgb: np.ndarray) -> tuple[list[tuple[int, int, int, int]], str]:
    h, w = gray.shape[:2]
    boxes: list[tuple[int, int, int, int]] = []
    used: list[str] = []

    if cv2 is not None:
        min_side = max(32, int(min(w, h) * 0.12))
        cascades = [
            ("opencv-frontal-default", _load_cascade("haarcascade_frontalface_default.xml")),
            ("opencv-frontal-alt2", _load_cascade("haarcascade_frontalface_alt2.xml")),
            ("opencv-profile", _load_cascade("haarcascade_profileface.xml")),
        ]
        eq = cv2.equalizeHist(gray)
        for label, cascade in cascades:
            if cascade is None:
                continue
            try:
                found = cascade.detectMultiScale(eq, scaleFactor=1.08, minNeighbors=5, minSize=(min_side, min_side))
                for x, y, bw, bh in found:
                    boxes.append(_bbox_clip((int(x), int(y), int(bw), int(bh)), w, h))
                if len(found):
                    used.append(label)
            except Exception:
                continue

    if dlib is not None:
        try:
            detector = dlib.get_frontal_face_detector()
            # Upsample small webcam images once for better recall.
            rects = detector(rgb, 1 if min(w, h) < 900 else 0)
            for rect in rects:
                x, y = int(rect.left()), int(rect.top())
                bw, bh = int(rect.right() - rect.left()), int(rect.bottom() - rect.top())
                if bw > 0 and bh > 0:
                    boxes.append(_bbox_clip((x, y, bw, bh), w, h))
            if len(rects):
                used.append("dlib-hog")
        except Exception:
            pass

    return _merge_boxes(boxes), " + ".join(used) if used else "not detected"


def _detect_eyes(gray: np.ndarray, face_box: tuple[int, int, int, int]) -> list[dict[str, Any]]:
    if cv2 is None:
        return []
    x, y, w, h = face_box
    roi_y1 = y + int(h * 0.12)
    roi_y2 = y + int(h * 0.62)
    roi = gray[roi_y1:roi_y2, x : x + w]
    if roi.size == 0:
        return []

    candidates: list[tuple[int, int, int, int]] = []
    min_eye = max(10, int(w * 0.10))
    for cascade_name in ["haarcascade_eye_tree_eyeglasses.xml", "haarcascade_eye.xml"]:
        cascade = _load_cascade(cascade_name)
        if cascade is None:
            continue
        try:
            found = cascade.detectMultiScale(roi, scaleFactor=1.08, minNeighbors=4, minSize=(min_eye, min_eye))
            for ex, ey, ew, eh in found:
                # Filter out oversized detections and convert to image coords.
                if ew > w * 0.45 or eh > h * 0.35:
                    continue
                candidates.append((x + int(ex), roi_y1 + int(ey), int(ew), int(eh)))
        except Exception:
            continue

    candidates = _merge_boxes(candidates)
    if not candidates:
        return []

    # Keep the best detection on the left and right side of the face.
    cx = x + w / 2.0
    left = [b for b in candidates if b[0] + b[2] / 2.0 < cx]
    right = [b for b in candidates if b[0] + b[2] / 2.0 >= cx]
    selected: list[tuple[int, int, int, int]] = []
    if left:
        selected.append(max(left, key=lambda b: b[2] * b[3]))
    if right:
        selected.append(max(right, key=lambda b: b[2] * b[3]))
    if len(selected) < 2:
        selected = sorted(candidates, key=lambda b: b[2] * b[3], reverse=True)[:2]
    selected = sorted(selected, key=lambda b: b[0])

    eyes: list[dict[str, Any]] = []
    for ex, ey, ew, eh in selected[:2]:
        eyes.append(
            {
                "bbox": {"x": ex, "y": ey, "w": ew, "h": eh},
                "center": {"x": _safe_float(ex + ew / 2.0, 1), "y": _safe_float(ey + eh / 2.0, 1)},
                "size_percent_of_face": _safe_float((ew * eh) / max(1, w * h) * 100.0, 2),
            }
        )
    return eyes


def _detect_mouth(gray: np.ndarray, face_box: tuple[int, int, int, int]) -> dict[str, Any]:
    if cv2 is None:
        return {"detected": False, "label": "estimated lower-face mouth area"}
    x, y, w, h = face_box
    roi_y1 = y + int(h * 0.54)
    roi = gray[roi_y1 : y + h, x : x + w]
    cascade = _load_cascade("haarcascade_smile.xml")
    if roi.size == 0 or cascade is None:
        return {"detected": False, "label": "estimated lower-face mouth area"}
    try:
        found = cascade.detectMultiScale(roi, scaleFactor=1.12, minNeighbors=12, minSize=(max(18, int(w * 0.22)), max(8, int(h * 0.05))))
    except Exception:
        found = []
    if len(found) == 0:
        return {
            "detected": False,
            "label": "mouth not confidently detected; use natural closed/neutral mouth unless prompt says otherwise",
            "estimated_center": {"x": _safe_float(x + w / 2.0, 1), "y": _safe_float(y + h * 0.72, 1)},
        }
    mx, my, mw, mh = max(found, key=lambda b: int(b[2]) * int(b[3]))
    bbox = {"x": int(x + mx), "y": int(roi_y1 + my), "w": int(mw), "h": int(mh)}
    return {"detected": True, "label": "smile/mouth region detected", "bbox": bbox}


def _region_stats(rgb: np.ndarray, gray: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, Any]:
    x, y, w, h = box
    crop_rgb = rgb[y : y + h, x : x + w]
    crop_gray = gray[y : y + h, x : x + w]
    if crop_rgb.size == 0:
        return {}
    mean = crop_rgb.reshape(-1, 3).mean(axis=0)
    std = crop_rgb.reshape(-1, 3).std(axis=0).mean()
    luminance = 0.2126 * mean[0] + 0.7152 * mean[1] + 0.0722 * mean[2]
    lap = float(cv2.Laplacian(crop_gray, cv2.CV_64F).var()) if cv2 is not None and crop_gray.size else 0.0
    return {
        "luminance": _safe_float(luminance, 1),
        "lighting_label": _brightness_label(float(luminance)),
        "temperature_label": _temperature_label(float(mean[0]), float(mean[2])),
        "contrast_label": _contrast_label(float(std)),
        "sharpness_laplacian": _safe_float(lap, 1),
        "sharpness_label": _sharpness_label(lap),
    }


def _pose_from_face(face_box: tuple[int, int, int, int], eyes: list[dict[str, Any]]) -> dict[str, Any]:
    x, y, w, h = face_box
    pose: dict[str, Any] = {
        "yaw_label": "near-front / not enough landmarks for exact yaw",
        "pitch_label": "neutral / approximate",
        "roll_degrees": None,
        "eye_line": "not enough eye landmarks",
    }
    if len(eyes) >= 2:
        left, right = eyes[0], eyes[1]
        lx, ly = float(left["center"]["x"]), float(left["center"]["y"])
        rx, ry = float(right["center"]["x"]), float(right["center"]["y"])
        dx, dy = rx - lx, ry - ly
        roll = math.degrees(math.atan2(dy, dx)) if abs(dx) > 1 else 0.0
        eye_mid_x = (lx + rx) / 2.0
        eye_mid_y = (ly + ry) / 2.0
        eye_mid_offset = (eye_mid_x - (x + w / 2.0)) / max(1, w)
        eye_y_ratio = (eye_mid_y - y) / max(1, h)
        if eye_mid_offset > 0.08:
            yaw_label = "slight turn toward image left"
        elif eye_mid_offset < -0.08:
            yaw_label = "slight turn toward image right"
        else:
            yaw_label = "front-facing / balanced"
        if eye_y_ratio < 0.31:
            pitch_label = "chin slightly down or camera slightly above"
        elif eye_y_ratio > 0.45:
            pitch_label = "chin slightly up or camera slightly below"
        else:
            pitch_label = "neutral"
        pose.update(
            {
                "yaw_label": yaw_label,
                "pitch_label": pitch_label,
                "roll_degrees": _safe_float(roll, 1),
                "eye_line": "level" if abs(roll) <= 4 else ("tilted clockwise" if roll > 0 else "tilted counter-clockwise"),
                "eye_distance_percent_of_face_width": _safe_float(abs(dx) / max(1, w) * 100.0, 1),
                "eye_midpoint_offset_x_percent": _safe_float(eye_mid_offset * 100.0, 1),
                "eye_midpoint_y_percent_of_face": _safe_float(eye_y_ratio * 100.0, 1),
            }
        )
    return pose


def _framing_from_coverage(coverage: float, center_x: float, center_y: float, face_detected: bool, image_orientation: str) -> str:
    if not face_detected:
        return "reference image; no face detected confidently"
    if coverage > 38:
        base = "tight face close-up"
    elif coverage > 18:
        base = "head-and-shoulders portrait"
    elif coverage > 7:
        base = "upper-body / medium portrait"
    else:
        base = "wide scene with smaller face"
    horizontal = "centered" if abs(center_x) < 8 else ("left-weighted" if center_x < 0 else "right-weighted")
    vertical = "mid frame" if abs(center_y) < 10 else ("upper frame" if center_y < 0 else "lower frame")
    return f"{base}, {horizontal}, {vertical}, {image_orientation} frame"


def _score_alignment(face_detected: bool, eyes: list[dict[str, Any]], roll: float | None, center_offset: float, sharpness: float) -> int:
    score = 30 if face_detected else 5
    if face_detected:
        score += 20
    if len(eyes) >= 2:
        score += 20
        if roll is not None:
            score += max(0, int(15 - min(15, abs(roll) * 2)))
    if center_offset < 12:
        score += 10
    elif center_offset < 24:
        score += 5
    if sharpness > 180:
        score += 10
    elif sharpness > 60:
        score += 5
    return max(0, min(100, score))


def _score_identity_reliability(
    *,
    face_count: int,
    coverage: float,
    center_distance: float,
    eyes_count: int,
    mouth_detected: bool,
    sharpness_label: str | None,
    landmark_active: bool,
) -> int:
    """Estimate how reliable the reference is for preserving the same visible person.

    This is not a biometric identity match score. It is a production readiness score
    for image-to-image identity preservation.
    """
    score = 100
    if face_count == 0:
        return 0
    if face_count > 1:
        score -= 28
    if coverage < 8:
        score -= 32
    elif coverage < 14:
        score -= 18
    elif coverage < 18:
        score -= 8
    if center_distance > 22:
        score -= 12
    elif center_distance > 12:
        score -= 6
    if eyes_count < 2:
        score -= 18
    if not mouth_detected:
        score -= 8
    if sharpness_label not in {"usable", "crisp"}:
        score -= 14
    if not landmark_active:
        score -= 18
    return max(0, min(100, int(score)))


def _score_generation_confidence(alignment_score: int, identity_reliability_score: int, face_count: int) -> int:
    """Conservative generation confidence.

    The final generation can still drift, so this deliberately uses the lower
    of alignment and identity reliability instead of claiming success from landmarks alone.
    """
    confidence = min(int(alignment_score), int(identity_reliability_score))
    if face_count > 1:
        confidence -= 12
    return max(0, min(100, confidence))


def _ambiguity_label(face_count: int) -> str:
    if face_count <= 0:
        return "no_face"
    if face_count == 1:
        return "low"
    if face_count == 2:
        return "medium"
    return "high"


def _format_bbox(box: tuple[int, int, int, int] | None) -> str | None:
    if not box:
        return None
    x, y, w, h = box
    return f"x{x} y{y} w{w} h{h}"


def _build_real_face_analysis(image_path: Path) -> dict[str, Any]:
    with Image.open(image_path) as pil:
        rgb_pil = pil.convert("RGB")
        w, h = rgb_pil.size
        rgb = np.array(rgb_pil)

    if cv2 is None:
        stat = ImageStat.Stat(rgb_pil.resize((128, 128)))
        r, g, b = stat.mean
        return {
            "face_detected": False,
            "face_count": 0,
            "detector": "opencv unavailable",
            "image_width": w,
            "image_height": h,
            "professional_notes": ["Install opencv-python-headless for baseline local face geometry analysis."],
            "face_alignment_master": _face_alignment_dependency_status(),
            "global_lighting_label": _brightness_label(0.2126 * r + 0.7152 * g + 0.0722 * b),
            "global_temperature_label": _temperature_label(r, b),
        }

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    global_lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    boxes, detector_label = _detect_faces(gray, rgb)
    face_detected = bool(boxes)
    main_box = max(boxes, key=lambda b: b[2] * b[3]) if boxes else None

    global_stat = ImageStat.Stat(rgb_pil.resize((128, 128)))
    r, g, b = global_stat.mean
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    global_std = sum(global_stat.stddev) / 3.0

    analysis: dict[str, Any] = {
        "face_detected": face_detected,
        "face_count": len(boxes),
        "detector": detector_label,
        "image_width": w,
        "image_height": h,
        "global_lighting_label": _brightness_label(luminance),
        "global_temperature_label": _temperature_label(r, b),
        "global_contrast_label": _contrast_label(global_std),
        "global_sharpness_laplacian": _safe_float(global_lap, 1),
        "global_sharpness_label": _sharpness_label(global_lap),
    }

    if not main_box:
        analysis.update(
            {
                "face_position": {"label": "no confident face box"},
                "pose_estimate": {"label": "not available"},
                "eye_analysis": {"detected_count": 0, "label": "not available"},
                "mouth_analysis": {"detected": False, "label": "not available"},
                "alignment_score": 10,
                "face_alignment_master": _face_alignment_dependency_status(),
                "features_for_prompt": [
                    "no confident face detector hit; keep prompt conservative",
                    "use uploaded image as composition and pose reference only",
                ],
                "professional_notes": [
                    "No face was confidently detected. Use a clearer front-facing crop or stronger lighting for exact face alignment.",
                ],
            }
        )
        return analysis

    x, y, fw, fh = main_box
    face_area_percent = (fw * fh) / max(1, w * h) * 100.0
    face_center_x = x + fw / 2.0
    face_center_y = y + fh / 2.0
    offset_x_percent = (face_center_x - w / 2.0) / max(1, w) * 100.0
    offset_y_percent = (face_center_y - h / 2.0) / max(1, h) * 100.0
    center_distance = math.sqrt(offset_x_percent**2 + offset_y_percent**2)

    eyes = _detect_eyes(gray, main_box)
    mouth = _detect_mouth(gray, main_box)
    pose = _pose_from_face(main_box, eyes)
    face_stats = _region_stats(rgb, gray, main_box)

    fan_landmarks, fan_status = _analyze_fan_landmarks(image_path, rgb, main_box)
    if fan_landmarks:
        pose.update(
            {
                "yaw_label": fan_landmarks.get("yaw_label") or pose.get("yaw_label"),
                "roll_degrees": fan_landmarks.get("roll_degrees"),
                "eye_line": fan_landmarks.get("eye_line") or pose.get("eye_line"),
                "eye_distance_percent_of_face_width": fan_landmarks.get("eye_distance_percent_of_landmark_face_width"),
                "landmark_source": "face-alignment-master FAN 68-point landmarks",
            }
        )
        eyes = [
            {"center": fan_landmarks.get("left_eye_center"), "source": "face-alignment-master"},
            {"center": fan_landmarks.get("right_eye_center"), "source": "face-alignment-master"},
        ]
        mouth = {
            "detected": True,
            "label": "mouth region located with face-alignment-master 68-point landmarks",
            "bbox": fan_landmarks.get("mouth_bbox"),
        }

    roll = pose.get("roll_degrees")
    alignment_score = _score_alignment(
        face_detected=True,
        eyes=eyes,
        roll=float(roll) if roll is not None else None,
        center_offset=center_distance,
        sharpness=float(face_stats.get("sharpness_laplacian") or 0),
    )
    if fan_landmarks:
        alignment_score = min(100, alignment_score + 15)

    face_count = len(boxes)
    identity_reliability_score = _score_identity_reliability(
        face_count=face_count,
        coverage=face_area_percent,
        center_distance=center_distance,
        eyes_count=len(eyes),
        mouth_detected=bool(mouth.get("detected")),
        sharpness_label=face_stats.get("sharpness_label"),
        landmark_active=bool(fan_landmarks),
    )
    generation_confidence_score = _score_generation_confidence(
        alignment_score=alignment_score,
        identity_reliability_score=identity_reliability_score,
        face_count=face_count,
    )
    multi_face_ambiguity = _ambiguity_label(face_count)

    # Prompt-safe geometry notes. No identity, age, ethnicity or gender labels.
    features = [
        f"one primary face detected" if len(boxes) == 1 else f"{len(boxes)} faces detected; use the largest/primary face",
        f"face box {_format_bbox(main_box)} covering {_safe_float(face_area_percent, 1)}% of the image",
        f"face center offset x {_safe_float(offset_x_percent, 1)}%, y {_safe_float(offset_y_percent, 1)}%",
        f"head pose: {pose.get('yaw_label')}, pitch {pose.get('pitch_label')}, eye-line {pose.get('eye_line')}",
        f"face lighting: {face_stats.get('lighting_label')}, temperature {face_stats.get('temperature_label')}, contrast {face_stats.get('contrast_label')}",
        f"sharpness: {face_stats.get('sharpness_label')} ({face_stats.get('sharpness_laplacian')})",
    ]
    if len(eyes) >= 2:
        features.append(
            f"two eyes detected; eye distance {pose.get('eye_distance_percent_of_face_width')}% of face width; roll {pose.get('roll_degrees')} degrees"
        )
    else:
        features.append("eyes not confidently detected; enforce symmetric natural eyes in generation")
    if mouth.get("detected"):
        features.append("mouth/smile region detected; preserve natural mouth placement")
    else:
        features.append("mouth not confidently detected; keep natural neutral mouth placement")
    if fan_landmarks:
        features.extend(str(item) for item in fan_landmarks.get("prompt_features", []))
    else:
        features.append(f"face-alignment-master status: {fan_status.get('status')}")

    notes = []
    if len(boxes) > 1:
        notes.append("Multiple faces were detected. Identity-preserving generation must use only the largest primary face and should not claim exact identity confidence.")
    if face_area_percent < 18:
        notes.append("Face coverage is below the production target for likeness. Move closer or crop tighter for stronger identity preservation.")
    if center_distance > 18:
        notes.append("Face is off-center. The generated image should intentionally keep or correct this composition depending on the selected framing.")
    if len(eyes) < 2:
        notes.append("Eye landmarks are weak. Add prompt constraints for coherent eyes and stable face symmetry.")
    if face_stats.get("sharpness_label") == "soft / slightly blurry":
        notes.append("Reference is soft. Add prompt constraints for sharper skin texture and clear facial structure.")
    if fan_landmarks:
        notes.append("face-alignment-master FAN 68-point landmarks are active and used for pose/eye/mouth cues.")
    else:
        notes.append(f"face-alignment-master is vendored but not active for landmarks in this run: {fan_status.get('status')}.")
    if not notes:
        notes.append("Face geometry is usable for prompt guidance.")

    analysis.update(
        {
            "primary_face_bbox": {"x": x, "y": y, "w": fw, "h": fh},
            "primary_face_bbox_label": _format_bbox(main_box),
            "face_position": {
                "coverage_percent": _safe_float(face_area_percent, 1),
                "center_offset_x_percent": _safe_float(offset_x_percent, 1),
                "center_offset_y_percent": _safe_float(offset_y_percent, 1),
                "center_distance_percent": _safe_float(center_distance, 1),
                "framing_label": _framing_from_coverage(face_area_percent, offset_x_percent, offset_y_percent, True, _label_orientation(w, h)),
            },
            "pose_estimate": pose,
            "eye_analysis": {"detected_count": len(eyes), "eyes": eyes},
            "mouth_analysis": mouth,
            "face_region_quality": face_stats,
            "face_alignment_master": fan_status,
            "landmark_analysis": fan_landmarks,
            "alignment_score": alignment_score,
            "identity_reliability_score": identity_reliability_score,
            "generation_confidence_score": generation_confidence_score,
            "multi_face_ambiguity": multi_face_ambiguity,
            "features_for_prompt": features,
            "professional_notes": notes,
        }
    )
    return analysis


def _prompt_from_analysis(analysis: dict[str, Any]) -> tuple[str, str]:
    if not analysis.get("face_detected"):
        en = (
            "No confident face box was detected. Use the uploaded image only as a broad composition reference; "
            "ask for a clearer, front-facing reference if exact face alignment is required."
        )
        fr = (
            "Aucun visage n'a été détecté avec confiance. Utilise l'image surtout comme référence de composition; "
            "demande une référence plus claire et frontale pour un alignement visage précis."
        )
        return en, fr

    pos = analysis.get("face_position", {})
    pose = analysis.get("pose_estimate", {})
    eyes = analysis.get("eye_analysis", {})
    mouth = analysis.get("mouth_analysis", {})
    quality = analysis.get("face_region_quality", {})
    score = analysis.get("alignment_score")
    identity_score = analysis.get("identity_reliability_score")
    generation_score = analysis.get("generation_confidence_score")
    ambiguity = analysis.get("multi_face_ambiguity")
    bbox = analysis.get("primary_face_bbox_label")
    fan_status = analysis.get("face_alignment_master") or {}
    landmark = analysis.get("landmark_analysis") or None
    if landmark:
        fan_phrase_en = "face-alignment-master FAN 68-point landmarks are active and used for eyes, mouth, roll and yaw cues. "
        fan_phrase_fr = "Les landmarks FAN 68 points de face-alignment-master sont actifs et utilisés pour les yeux, la bouche, le roll et le yaw. "
    else:
        fan_phrase_en = f"face-alignment-master is vendored; landmark runtime status: {fan_status.get('status')}. "
        fan_phrase_fr = f"face-alignment-master est inclus; statut runtime landmarks : {fan_status.get('status')}. "

    en = (
        f"Real face analysis: detected {analysis.get('face_count', 1)} face(s); use the primary face box {bbox}. "
        f"Framing is {pos.get('framing_label')}; face coverage {pos.get('coverage_percent')}% with center offset "
        f"x {pos.get('center_offset_x_percent')}%, y {pos.get('center_offset_y_percent')}%. "
        f"Pose is {pose.get('yaw_label')}, pitch {pose.get('pitch_label')}, eye-line {pose.get('eye_line')}, roll {pose.get('roll_degrees')} degrees. "
        f"Eyes detected: {eyes.get('detected_count', 0)}; mouth: {mouth.get('label')}. "
        f"Face lighting is {quality.get('lighting_label')}, color temperature {quality.get('temperature_label')}, contrast {quality.get('contrast_label')}, sharpness {quality.get('sharpness_label')}. "
        f"Alignment score: {score}/100. Identity reliability score: {identity_score}/100. Generation confidence score: {generation_score}/100. Multi-face ambiguity: {ambiguity}. {fan_phrase_en}Preserve face geometry, gaze direction, head pose, shoulder/clothing silhouette and camera perspective without inventing warped features."
    )
    fr = (
        f"Analyse réelle du visage : {analysis.get('face_count', 1)} visage(s) détecté(s); utiliser le visage principal {bbox}. "
        f"Cadrage : {pos.get('framing_label')}; couverture visage {pos.get('coverage_percent')}%, décalage centre "
        f"x {pos.get('center_offset_x_percent')}%, y {pos.get('center_offset_y_percent')}%. "
        f"Pose : {pose.get('yaw_label')}, pitch {pose.get('pitch_label')}, ligne des yeux {pose.get('eye_line')}, roll {pose.get('roll_degrees')} degrés. "
        f"Yeux détectés : {eyes.get('detected_count', 0)}; bouche : {mouth.get('label')}. "
        f"Lumière visage : {quality.get('lighting_label')}, température {quality.get('temperature_label')}, contraste {quality.get('contrast_label')}, netteté {quality.get('sharpness_label')}. "
        f"Score alignement : {score}/100. Score fiabilité identité : {identity_score}/100. Score confiance génération : {generation_score}/100. Ambiguïté multi-visage : {ambiguity}. {fan_phrase_fr}Préserver géométrie du visage, direction du regard, pose de tête, silhouette épaules/vêtements et perspective caméra sans créer de déformations."
    )
    return en, fr



def _grade_from_score(score: int | None) -> str:
    if score is None:
        return "N/A"
    if score >= 85:
        return "A"
    if score >= 72:
        return "B"
    if score >= 58:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _build_production_assessment(real: dict[str, Any]) -> dict[str, Any]:
    alignment_score = real.get("alignment_score")
    identity_score = real.get("identity_reliability_score")
    generation_score = real.get("generation_confidence_score")
    score_for_grade = generation_score if isinstance(generation_score, int) else alignment_score
    grade = _grade_from_score(score_for_grade if isinstance(score_for_grade, int) else None)

    pos = real.get("face_position") or {}
    pose = real.get("pose_estimate") or {}
    quality = real.get("face_region_quality") or {}
    eyes = real.get("eye_analysis") or {}
    mouth = real.get("mouth_analysis") or {}
    face_count = int(real.get("face_count") or 0)
    ambiguity = real.get("multi_face_ambiguity") or _ambiguity_label(face_count)

    strengths: list[str] = []
    risks: list[str] = []
    recommendations: list[str] = []

    face_detected = bool(real.get("face_detected"))
    fan_status = real.get("face_alignment_master") or {}
    landmark = real.get("landmark_analysis") or None

    if face_detected:
        strengths.append("A primary face was detected locally and the subject framing can be measured.")
    else:
        risks.append("No face was confidently detected, so exact face alignment is not reliable.")
        recommendations.append("Use a clearer reference with the face fully visible and front-facing.")

    if face_count > 1:
        risks.append("Multiple faces were detected; identity generation can drift unless only the primary face crop is used.")
        recommendations.append("Use a cleaner single-person reference or crop tightly around the target face before generation.")

    if landmark:
        strengths.append("face-alignment-master 68-point FAN landmarks are active for production pose/eye/mouth guidance.")
    else:
        risks.append(f"face-alignment-master landmarks are not active in this runtime ({fan_status.get('status') or 'unknown'}).")
        recommendations.append("Install/cache FAN model weights before claiming production-grade landmark accuracy.")

    coverage = float(pos.get("coverage_percent") or 0.0)
    if coverage >= 18:
        strengths.append("Face coverage is strong enough for head-and-shoulders prompt guidance.")
    elif coverage >= 10:
        risks.append("The face is usable but still smaller than the production likeness target.")
        recommendations.append(f"Move the camera closer so the face covers at least {FACE_MIN_COVERAGE_FOR_GENERATION:g}% of the frame.")
    else:
        risks.append("The face is too small in the frame for production-grade identity preservation.")
        recommendations.append("Retake closer to the camera or crop tightly around the head and shoulders.")

    center_distance = float(pos.get("center_distance_percent") or 0.0)
    if center_distance <= 10 and face_detected:
        strengths.append("The face is reasonably centered, which helps stable composition.")
    elif center_distance > 18:
        risks.append("The face is noticeably off-center in the current capture.")
        recommendations.append("Center the subject more clearly unless an off-center composition is intentional.")

    eye_count = int(eyes.get("detected_count") or 0)
    if eye_count >= 2:
        strengths.append("Both eyes were detected, so pose and symmetry cues are more trustworthy.")
    else:
        risks.append("Eye landmarks are incomplete, so the model may guess eye symmetry or gaze direction.")
        recommendations.append("Retake with both eyes clearly visible, looking toward the camera, and avoid occlusion.")

    if mouth.get("detected"):
        strengths.append("The mouth region was detected, which helps keep natural mouth placement.")
    else:
        risks.append("The mouth region was not confidently detected.")
        recommendations.append("Keep the mouth visible with neutral expression and avoid motion blur.")

    sharpness_label = quality.get("sharpness_label")
    if sharpness_label == "crisp":
        strengths.append("The reference is sharp, which supports cleaner facial reconstruction.")
    elif sharpness_label == "usable":
        strengths.append("Sharpness is usable for generation, though it is not premium-grade.")
    else:
        risks.append("The reference is soft or slightly blurry, which reduces facial precision.")
        recommendations.append("Improve focus, hold the camera steady, and use better light to increase sharpness.")

    lighting_label = quality.get("lighting_label")
    if lighting_label == "balanced":
        strengths.append("Lighting on the face is balanced.")
    elif lighting_label:
        risks.append(f"Face lighting is {lighting_label}, which may limit natural detail recovery.")
        recommendations.append("Use even frontal light on the face and reduce heavy shadows or overexposure.")

    pose_yaw = pose.get("yaw_label")
    if pose_yaw and "front-facing" in str(pose_yaw):
        strengths.append("The head pose is close to front-facing.")
    elif pose_yaw:
        risks.append(f"Head pose is {pose_yaw}, so exact frontal face matching is less certain.")
        recommendations.append("Capture a more front-facing head pose when precise alignment is required.")

    gen = generation_score if isinstance(generation_score, int) else 0
    identity = identity_score if isinstance(identity_score, int) else 0

    if (
        gen >= FACE_MIN_GENERATION_CONFIDENCE
        and identity >= FACE_MIN_IDENTITY_RELIABILITY
        and face_count == 1
        and coverage >= FACE_MIN_COVERAGE_FOR_GENERATION
        and bool(landmark)
    ):
        readiness = "production_ready"
        if coverage >= FACE_TARGET_COVERAGE_FOR_PREMIUM_IDENTITY:
            headline = "Production-ready premium reference for identity-preserving img2img"
        else:
            headline = "Production-ready reference; closer crop is optional for premium likeness"
    elif gen >= 90 and identity >= 90 and face_count == 1 and coverage >= 12 and bool(landmark):
        readiness = "review_required"
        headline = "Almost ready; crop closer for stronger identity lock"
    elif gen >= 50:
        readiness = "needs_improvement"
        headline = "Needs improvement before client-facing generation"
    else:
        readiness = "retake_recommended"
        headline = "Retake recommended for reliable identity preservation"

    if not landmark and readiness == "production_ready":
        readiness = "usable_with_identity_risk"
        headline = "Usable, but landmark engine is not active"
        grade = "B" if grade == "A" else grade

    if face_count > 1 and readiness == "production_ready":
        readiness = "usable_with_identity_risk"
        headline = "Usable, but multiple faces make identity ambiguous"
        grade = "B" if grade == "A" else grade

    if not recommendations:
        recommendations.append("Reference is solid; keep the same framing and lighting style for best consistency.")

    summary_parts = []
    if face_detected:
        summary_parts.append(f"{face_count} face(s) detected using {real.get('detector') or 'local detector'}")
    else:
        summary_parts.append("No reliable face detection")
    if coverage:
        summary_parts.append(f"face coverage {coverage}%")
    if alignment_score is not None:
        summary_parts.append(f"alignment {alignment_score}/100")
    if identity_score is not None:
        summary_parts.append(f"identity reliability {identity_score}/100")
    if generation_score is not None:
        summary_parts.append(f"generation confidence {generation_score}/100")
    summary = "; ".join(summary_parts) + "."

    weak_reference = (
        (not face_detected)
        or face_count != 1
        or (not bool(landmark))
        or coverage < FACE_MIN_COVERAGE_FOR_GENERATION
        or identity < FACE_MIN_IDENTITY_RELIABILITY
        or gen < FACE_MIN_GENERATION_CONFIDENCE
    )
    # Production UX rule: analysis must warn, not block. The generation route
    # applies auto-crop and lets the provider attempt the requested image/video.
    hard_block_generation = False
    requires_face_crop = face_detected and coverage < FACE_MIN_COVERAGE_FOR_GENERATION
    warning_level = "medium" if weak_reference or readiness != "production_ready" else "low"

    if weak_reference:
        readiness = "usable_with_auto_crop_review"
        headline = "Usable with auto-crop and result review"
        grade = "B" if face_detected else "C"

    return {
        "grade": grade,
        "readiness": readiness,
        "headline": headline,
        "summary": summary,
        "alignment_score": alignment_score,
        "identity_reliability_score": identity_score,
        "generation_confidence_score": generation_score,
        "multi_face_ambiguity": ambiguity,
        "strengths": strengths[:5],
        "risks": risks[:6],
        "recommendations": recommendations[:6],
        "requires_face_crop": requires_face_crop,
        "hard_block_generation": hard_block_generation,
        "warning_level": warning_level,
        "can_generate": True,
        "can_generate_confidently": gen >= FACE_MIN_GENERATION_CONFIDENCE and identity >= FACE_MIN_IDENTITY_RELIABILITY and face_count == 1 and coverage >= FACE_MIN_COVERAGE_FOR_GENERATION and bool(landmark),
    }


def _readable_summary(real: dict[str, Any], assessment: dict[str, Any], *, lang: str) -> str:
    alignment = real.get("alignment_score")
    identity = real.get("identity_reliability_score")
    generation = real.get("generation_confidence_score")
    grade = assessment.get("grade") or "N/A"
    headline = assessment.get("headline") or ("Production review" if lang == "en" else "Revue production")
    risks = assessment.get("risks") or []
    recommendations = assessment.get("recommendations") or []
    quality = real.get("face_region_quality") or {}
    pos = real.get("face_position") or {}
    face_count = real.get("face_count")

    if lang == "fr":
        issue_text = "; ".join(risks[:3]) if risks else "Aucun risque majeur détecté."
        reco_text = "; ".join(recommendations[:2]) if recommendations else "Aucune action requise."
        return (
            f"Verdict production : {headline} · note {grade}. "
            f"Visages détectés {face_count}; couverture {pos.get('coverage_percent')}%. "
            f"Alignement {alignment}/100 · fiabilité identité {identity}/100 · confiance génération {generation}/100. "
            f"Netteté {quality.get('sharpness_label')}, lumière {quality.get('lighting_label')}. "
            f"Points d'attention : {issue_text} Recommandation : {reco_text}"
        )

    issue_text = "; ".join(risks[:3]) if risks else "No major risk flags."
    reco_text = "; ".join(recommendations[:2]) if recommendations else "No action needed."
    return (
        f"Production verdict: {headline} · grade {grade}. "
        f"Faces detected {face_count}; face coverage {pos.get('coverage_percent')}%. "
        f"Alignment {alignment}/100 · identity reliability {identity}/100 · generation confidence {generation}/100. "
        f"Sharpness {quality.get('sharpness_label')}, lighting {quality.get('lighting_label')}. "
        f"Key risks: {issue_text} Recommendation: {reco_text}"
    )

def analyze_face_reference(image_path: str | Path, hint: str = "") -> FaceAlignmentProfile:
    path = Path(image_path)
    with Image.open(path) as img:
        rgb_pil = img.convert("RGB")
        w, h = rgb_pil.size
        stat = ImageStat.Stat(rgb_pil.resize((128, 128)))
        r, g, b = stat.mean
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        std = sum(stat.stddev) / 3.0

    orientation = _label_orientation(w, h)
    global_lighting = _brightness_label(luminance)
    global_temperature = _temperature_label(r, b)
    global_contrast = _contrast_label(std)
    real_analysis = _build_real_face_analysis(path)

    detected_prompt_en, detected_prompt_fr = _prompt_from_analysis(real_analysis)
    face_position = real_analysis.get("face_position", {})
    framing = face_position.get("framing_label") or ("close-up / upper-body reference" if h >= w else "wide camera reference")

    likely_region = (
        "primary detected face box; preserve head pose, gaze direction, face proportions, hair/beard outline if visible, "
        "shoulder/clothing silhouette, camera angle, and lighting mood"
        if real_analysis.get("face_detected")
        else "no confident face box; use overall subject/composition reference and ask for clearer face if needed"
    )
    sharpness_label = real_analysis.get("face_region_quality", {}).get("sharpness_label") or real_analysis.get("global_sharpness_label") or "unknown"
    sharpness_value = real_analysis.get("face_region_quality", {}).get("sharpness_laplacian") or real_analysis.get("global_sharpness_laplacian")
    sharpness = f"{sharpness_label}; Laplacian sharpness {sharpness_value}"
    if hint:
        sharpness += f"; user hint: {hint.strip()}"

    notes = [
        "real face detector executed locally; no identity recognition",
        *[str(item) for item in real_analysis.get("features_for_prompt", [])[:8]],
        *[str(item) for item in real_analysis.get("professional_notes", [])[:4]],
        "negative prompt must block warped eyes, asymmetric mouth, extra face parts, fake teeth/text, plastic skin and unstable anatomy",
    ]

    prompt_en = (
        f"Use the uploaded reference image as a real face and pose guide. {detected_prompt_en} "
        f"Global image: {orientation}, {global_lighting} light, {global_temperature} color temperature, {global_contrast}. "
        "Create a realistic, natural-looking person with stable face geometry, coherent eyes, natural mouth placement, "
        "consistent head pose, matching camera perspective, matching shoulder/clothing outline and believable lighting. "
        "Do not identify the person; use only visual geometry and composition."
    )
    prompt_fr = (
        f"Utilise l'image importée comme vraie référence de visage et de pose. {detected_prompt_fr} "
        f"Image globale : {orientation}, lumière {global_lighting}, température {global_temperature}, contraste {global_contrast}. "
        "Génère une personne réaliste avec géométrie du visage stable, yeux cohérents, bouche naturelle, pose de tête cohérente, "
        "perspective caméra similaire, silhouette épaules/vêtements similaire et lumière crédible. "
        "Ne pas identifier la personne; utiliser seulement la géométrie visuelle et la composition."
    )

    face_lighting = real_analysis.get("face_region_quality", {}).get("lighting_label") or global_lighting
    face_temperature = real_analysis.get("face_region_quality", {}).get("temperature_label") or global_temperature
    face_contrast = real_analysis.get("face_region_quality", {}).get("contrast_label") or global_contrast

    production_assessment = _build_production_assessment(real_analysis)
    readable_summary_en = _readable_summary(real_analysis, production_assessment, lang="en")
    readable_summary_fr = _readable_summary(real_analysis, production_assessment, lang="fr")

    return FaceAlignmentProfile(
        image_size=f"{w}x{h}",
        orientation=orientation,
        framing=framing,
        lighting=face_lighting,
        color_temperature=face_temperature,
        contrast=face_contrast,
        sharpness_note=sharpness,
        likely_subject_region=likely_region,
        alignment_notes=notes,
        prompt_details_en=prompt_en,
        prompt_details_fr=prompt_fr,
        real_face_analysis=real_analysis,
        production_assessment=production_assessment,
        readable_summary_en=readable_summary_en,
        readable_summary_fr=readable_summary_fr,
        detected_face_prompt_en=detected_prompt_en,
        detected_face_prompt_fr=detected_prompt_fr,
    )
