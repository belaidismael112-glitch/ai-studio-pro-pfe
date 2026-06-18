from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

from .contracts import ImageAnalysis


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


async def analyze_image(source_image_path: str, user_prompt: str = "", subject_type: str | None = None) -> ImageAnalysis:
    """Production analyzer for V10 hybrid img2img.

    Main rule:
    - The backend vision route already gives a subject_type hint.
    - If subject_type=product, stale prompt words like "worm" must never override it.
    - Ollama vision is used when available, but if it returns empty text we still
      choose a safe production category from subject_type + visual heuristics.
    """

    subject_hint = (subject_type or "").strip().lower()
    vision_text = ""
    if _env_bool("OLLAMA_VISION_ENABLED", True) or _env_bool("IMG2IMG_ANALYZER_USE_OLLAMA", True):
        vision_text = _call_ollama_vision(source_image_path, user_prompt, subject_hint)

    # First: parse true vision response, not the long generated prompt.
    if vision_text:
        analysis = _analysis_from_text(vision_text, subject_hint=subject_hint, allow_prompt_noise=False)
        if analysis:
            analysis.raw["vision_text"] = vision_text
            analysis.raw["subject_type_hint"] = subject_hint
            analysis.raw["analyzer"] = "ollama_vision_priority"
            return analysis

    # Second: subject_type hint from the main backend route wins.
    if subject_hint in {"product", "object", "document"}:
        product_visual = _visual_product_guess(source_image_path)
        product_visual.raw["vision_text"] = vision_text
        product_visual.raw["subject_type_hint"] = subject_hint
        product_visual.raw["analyzer"] = "subject_type_priority_product"
        return product_visual

    if subject_hint in {"person", "face", "portrait", "human"}:
        return ImageAnalysis(
            subject_label="person",
            subject_type="person",
            category="portrait",
            mood="editorial",
            main_colors=["black", "white"],
            is_person=True,
            is_living_subject=True,
            suggested_mode="person_identity",
            confidence=0.82,
            raw={"vision_text": vision_text, "subject_type_hint": subject_hint, "analyzer": "subject_type_priority_person"},
        )

    if subject_hint in {"animal", "living_subject", "living"}:
        # Only now living/nature is allowed.
        return ImageAnalysis(
            subject_label="living subject",
            subject_type="living_subject",
            category="nature",
            mood="macro discovery",
            main_colors=["green", "brown", "cream"],
            is_living_subject=True,
            suggested_mode="flyer_poster",
            confidence=0.72,
            raw={"vision_text": vision_text, "subject_type_hint": subject_hint, "analyzer": "subject_type_priority_living"},
        )

    # Third: use filename/user prompt only as low-trust fallback.
    low_trust = " ".join([Path(source_image_path).name, user_prompt or ""]).lower()
    analysis = _analysis_from_text(low_trust, subject_hint=subject_hint, allow_prompt_noise=True)
    if analysis:
        analysis.raw["vision_text"] = vision_text
        analysis.raw["subject_type_hint"] = subject_hint
        analysis.raw["analyzer"] = "low_trust_filename_prompt"
        return analysis

    visual = _visual_product_guess(source_image_path)
    visual.raw["vision_text"] = vision_text
    visual.raw["subject_type_hint"] = subject_hint
    visual.raw["analyzer"] = "visual_product_default"
    return visual


def _call_ollama_vision(source_image_path: str, user_prompt: str = "", subject_hint: str = "") -> str:
    url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/generate"
    model = os.getenv("IMG2IMG_ANALYZER_MODEL") or os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:3b")
    timeout = int(os.getenv("IMG2IMG_ANALYZER_TIMEOUT_SECONDS", os.getenv("OLLAMA_VISION_TIMEOUT_SECONDS", "120")))

    try:
        image_b64 = base64.b64encode(Path(source_image_path).read_bytes()).decode("utf-8")
        prompt = (
            "You are a strict product/flyer image analyzer. Look ONLY at the uploaded image, not at past prompts. "
            "Return JSON only. Keys: subject_label, subject_type, category, mood, main_colors, suggested_mode. "
            "Categories allowed: fashion, beverage, beauty, food, sports, nature, portrait, tech, general_product, general. "
            "If the image is a handbag/purse/bag: category=fashion, subject_type=product. "
            "If it is a bottle/can/drink: category=beverage, subject_type=product. "
            "If it is a runner/sports person: category=sports. "
            "If it is a worm/insect/caterpillar: category=nature, subject_type=living_subject. "
            f"Backend subject_type hint: {subject_hint or '(none)'}. "
            "Never classify a product as worm/nature."
        )
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.0},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        return str(data.get("response") or "")
    except Exception:
        return ""


def _analysis_from_text(text: str, subject_hint: str = "", allow_prompt_noise: bool = False) -> ImageAnalysis | None:
    data: dict[str, Any] = {}
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if m:
        try:
            data = json.loads(m.group(0))
        except Exception:
            data = {}

    raw = " ".join([text or "", json.dumps(data).lower()]).lower()

    def has(*words: str) -> bool:
        return any(w in raw for w in words)

    # Product hint blocks nature/worm false positives from stale long prompts.
    product_hint = subject_hint in {"product", "object", "document"}

    if has("handbag", "purse", "leather bag", "shoulder bag", "tote bag", "fashion accessory", "bag"):
        return _fashion_analysis(data, confidence=0.92)

    if has("bottle", "can", "drink", "beverage", "cola", "soda", "juice"):
        return ImageAnalysis(
            subject_label=str(data.get("subject_label") or "beverage bottle"),
            subject_type="product",
            category="beverage",
            mood=str(data.get("mood") or "fresh commercial"),
            main_colors=_colors(data, ["red", "black", "white"]),
            is_product=True,
            is_packshot=True,
            suggested_mode="flyer_poster",
            confidence=0.88,
            raw={"parsed_json": data},
        )

    if not product_hint and has("worm", "insect", "caterpillar", "larva", "bug", "beetle", "ant"):
        return ImageAnalysis(
            subject_label=str(data.get("subject_label") or "worm"),
            subject_type="living_subject",
            category="nature",
            mood=str(data.get("mood") or "macro discovery"),
            main_colors=_colors(data, ["green", "brown", "cream"]),
            is_living_subject=True,
            suggested_mode="flyer_poster",
            confidence=0.84,
            raw={"parsed_json": data},
        )

    if has("runner", "running", "marathon", "gym", "fitness", "sport", "athlete"):
        return ImageAnalysis(
            subject_label=str(data.get("subject_label") or "athlete"),
            subject_type="person",
            category="sports",
            mood=str(data.get("mood") or "energetic event"),
            main_colors=_colors(data, ["orange", "black", "white"]),
            is_person=True,
            is_living_subject=True,
            suggested_mode="flyer_poster",
            confidence=0.86,
            raw={"parsed_json": data},
        )

    if has("burger", "pizza", "cake", "coffee", "food", "meal", "restaurant", "sandwich"):
        return ImageAnalysis(
            subject_label=str(data.get("subject_label") or "food item"),
            subject_type="product",
            category="food",
            mood=str(data.get("mood") or "appetizing"),
            main_colors=_colors(data, ["red", "cream", "brown"]),
            is_product=True,
            suggested_mode="flyer_poster",
            confidence=0.84,
            raw={"parsed_json": data},
        )

    if has("face", "portrait", "person", "woman", "man", "girl", "boy"):
        return ImageAnalysis(
            subject_label=str(data.get("subject_label") or "person"),
            subject_type="person",
            category=str(data.get("category") or "portrait"),
            mood=str(data.get("mood") or "editorial"),
            main_colors=_colors(data, ["black", "white"]),
            is_person=True,
            is_living_subject=True,
            suggested_mode="person_identity",
            confidence=0.8,
            raw={"parsed_json": data},
        )

    return None


def _visual_product_guess(source_image_path: str) -> ImageAnalysis:
    # For production safety: if backend already says product and vision failed,
    # default to fashion/premium product instead of nature/general.
    try:
        im = Image.open(source_image_path).convert("RGB").resize((160, 160))
        pixels = list(im.getdata())

        center_lum = []
        border_lum = []
        gold_score = 0
        dark_score = 0
        for y in range(160):
            for x in range(160):
                r, g, b = pixels[y * 160 + x]
                lum = (r + g + b) / 3
                if 35 <= x <= 125 and 35 <= y <= 132:
                    center_lum.append(lum)
                    if lum < 85:
                        dark_score += 1
                    if r > 130 and g > 90 and b < 80:
                        gold_score += 1
                if x < 20 or x > 140 or y < 20 or y > 140:
                    border_lum.append(lum)

        dark_ratio = dark_score / max(len(center_lum), 1)
        gold_ratio = gold_score / max(len(center_lum), 1)
        border_light = sum(1 for v in border_lum if v > 160) / max(len(border_lum), 1)

        # Handbag-like: dark product with some gold details on light background.
        if dark_ratio > 0.15 and (gold_ratio > 0.005 or border_light > 0.25):
            return _fashion_analysis({}, confidence=0.72)

    except Exception:
        pass

    return ImageAnalysis(
        subject_label="premium product",
        subject_type="product",
        category="general_product",
        mood="premium commercial",
        main_colors=["black", "beige", "white"],
        is_product=True,
        is_packshot=True,
        suggested_mode="flyer_poster",
        confidence=0.62,
        raw={},
    )


def _fashion_analysis(data: dict[str, Any], confidence: float = 0.9) -> ImageAnalysis:
    return ImageAnalysis(
        subject_label=str(data.get("subject_label") or "black leather handbag"),
        subject_type="product",
        category="fashion",
        mood=str(data.get("mood") or "luxury fashion"),
        main_colors=_colors(data, ["black", "gold", "beige"]),
        is_product=True,
        is_packshot=True,
        suggested_mode="flyer_poster",
        confidence=confidence,
        raw={"parsed_json": data},
    )


def _colors(data: dict[str, Any], default: list[str]) -> list[str]:
    colors = data.get("main_colors")
    if isinstance(colors, list) and colors:
        return [str(c) for c in colors[:5]]
    return default
