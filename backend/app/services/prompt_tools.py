"""Prompt safety + deterministic prompt enhancement.

This module converts raw user text into stable image/video prompts for the
current local ComfyUI setup. For flyers/posters, it also extracts text fields
so the backend can render real readable text with Pillow instead of asking the
diffusion model to spell everything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings


@dataclass
class PromptResult:
    prompt: str
    negative_prompt: str | None = None
    warnings: list[str] | None = None
    meta: dict[str, Any] = field(default_factory=dict)


BANNED_PATTERNS = [
    r"\bchild\b.*\b(nude|naked|sex)\b",
    r"\b(cs?am)\b",
]

FLYER_HINTS = (
    "flyer", "poster", "brochure", "ad", "advert", "promotion", "promo",
    "event", "open day", "university", "register", "scholarship", "conference",
    "campus", "cta", "call to action", "headline", "subheadline", "button",
    "register now", "open day", "business", "design", "engineering",
)


def validate_prompt(prompt: str) -> None:
    p = (prompt or "").strip()
    if not p:
        raise ValueError("Prompt is required")
    if len(p) > int(getattr(settings, "PROMPT_MAX_CHARS", 8000)):
        raise ValueError("Prompt too long")
    low = p.lower()
    for pat in BANNED_PATTERNS:
        if re.search(pat, low):
            raise ValueError("Prompt not allowed")


def _clean_line(line: str) -> str:
    line = (line or "").strip().strip('"').strip("'")
    line = re.sub(r"^[•\-–—\*#]+\s*", "", line).strip()
    line = re.sub(r"\s+", " ", line)
    return line


def _dedupe_csv(text: str) -> str:
    seen: list[str] = []
    for part in [p.strip() for p in re.split(r",", text) if p.strip()]:
        if part.lower() not in [x.lower() for x in seen]:
            seen.append(part)
    return ", ".join(seen)


def looks_like_flyer(prompt: str) -> bool:
    low = (prompt or "").lower()
    return any(h in low for h in FLYER_HINTS)


def _extract_text_lines(prompt: str) -> list[str]:
    lines: list[str] = []
    for raw in (prompt or "").splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        # Drop instruction lines that are not text to display.
        low = line.lower()
        if low.startswith(("make the", "keep the", "create a", "avoid ", "use ", "the design", "design goals")):
            continue
        if len(line) <= 140:
            lines.append(line)

    if not lines:
        chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+|\s*;\s*", (prompt or "").strip()) if c.strip()]
        lines = [_clean_line(c) for c in chunks[:7] if len(c) <= 140]

    out: list[str] = []
    for line in lines:
        if line and line.lower() not in [x.lower() for x in out]:
            out.append(line)
    return out[:10]


def extract_flyer_meta(prompt: str) -> dict[str, Any]:
    lines = _extract_text_lines(prompt)
    joined = "\n".join(lines)

    def first_matching(patterns: list[str], fallback: str) -> str:
        for line in lines:
            low = line.lower()
            if any(p in low for p in patterns):
                return line.strip('"').strip()
        return fallback

    title = first_matching(["open day", "conference", "scholarship", "business", "engineering", "design"], "UNIVERSITY OPEN DAY")
    cta = first_matching(["register", "apply", "book", "join"], "REGISTER NOW")

    # Build detail lines from likely event/contact lines
    details: list[str] = []
    for line in lines:
        low = line.lower()
        if line == title or line == cta:
            continue
        if any(token in low for token in ["www.", "http", "+", "campus", "date", "june", "2026", "engineering", "business", "design", "scholarship", "tunis"]):
            details.append(line)

    if not details:
        details = ["Engineering • Business • Design", "Scholarships available", "Main Campus • Tunis"]

    # Make title concise for overlay
    title = re.sub(r'["“”]', "", title).strip()
    if len(title) > 34:
        title = title[:34].rstrip(" -•,") + "..."

    cta = re.sub(r'["“”]', "", cta).strip()
    if len(cta) > 24:
        cta = "REGISTER NOW"

    return {
        "title": title.upper(),
        "subtitle": "BUILD YOUR FUTURE WITH US",
        "details": details[:4],
        "cta": cta.upper(),
    }


def _build_flyer_background_prompt(prompt: str, style: str | None = None) -> str:
    # Do NOT ask FLUX to draw flyer text. It often creates wrong letters.
    # Generate clean background only; backend overlays real readable text afterwards.
    meta = extract_flyer_meta(prompt)
    style_hint = f", {style}" if style else ""
    theme = meta.get("title", "UNIVERSITY OPEN DAY")
    return (
        "premium photorealistic university promotional poster background, "
        "one confident friendly university student standing on the right third of the image, "
        "modern clean campus architecture, bright academic atmosphere, natural realistic face, realistic hands, "
        "left third reserved as a clean dark blue gradient empty panel for later graphic typography, "
        "professional commercial advertising layout, clear visual hierarchy, polished editorial design, "
        "soft daylight, sharp subject, balanced composition, blue and white brand palette, high quality, "
        "background only, absolutely no generated writing, no fake letters, no logo, no watermark, "
        "leave clean empty space for real text overlay"
        f"{style_hint}. Theme: {theme}"
    )


def _negative_for_flyer_background() -> str:
    return (
        "generated text, letters, words, logo, watermark, readable typography, unreadable typography, "
        "fake text, misspelled words, blurry, low quality, lowres, noisy, cluttered layout, chaotic composition, "
        "deformed face, bad hands, extra fingers, distorted anatomy, oversaturated, duplicate people"
    )


def _build_generic_prompt(prompt: str, style: str | None = None) -> tuple[str, list[str]]:
    p = re.sub(r"\s+", " ", (prompt or "").strip())
    warnings: list[str] = []
    words = [w for w in re.split(r"\s+", p) if w]
    if len(words) <= int(getattr(settings, "PROMPT_MIN_WORDS_FOR_BOOST", 4)):
        p = (
            f"{p}, photorealistic, centered subject, natural composition, soft realistic lighting, "
            "sharp focus, detailed texture, clean background, professional photography, high quality"
        )
        warnings.append("Prompt boosted for quality")
    if style:
        p = _dedupe_csv(f"{p}, {style}")
    return p, warnings


def _negative_generic_image() -> str:
    return (
        "blurry, low quality, lowres, noisy, jpeg artifacts, compression artifacts, "
        "deformed, distorted anatomy, bad hands, extra fingers, fused fingers, duplicate limbs, "
        "warped face, cross-eye, ugly, oversaturated, watermark, logo, fake text"
    )


def enhance_prompt(prompt: str, style: str | None = None) -> PromptResult:
    """Enhance image prompts."""
    p = (prompt or "").strip()

    if looks_like_flyer(p):
        return PromptResult(
            prompt=_build_flyer_background_prompt(p, style=style),
            negative_prompt=_negative_for_flyer_background(),
            warnings=["Flyer background generated without AI text; backend overlays real text"],
            meta={"kind": "flyer", "flyer": extract_flyer_meta(p)},
        )

    generic_prompt, warnings = _build_generic_prompt(p, style=style)
    return PromptResult(prompt=generic_prompt, negative_prompt=_negative_generic_image(), warnings=warnings or None, meta={})


def _negative_video_default() -> str:
    return (
        "low quality, worst quality, blurry, noisy, compression artifacts, distorted, deformed, disfigured, "
        "motion smear, motion artifacts, flicker, unstable motion, bad anatomy, bad hands, fused fingers, "
        "extra limbs, duplicate subject, warped face, text, watermark, logo"
    )


def _summarize_subject(prompt: str) -> str:
    p = re.sub(r"\s+", " ", (prompt or "").strip())
    if not p:
        return "a realistic subject"

    low = p.lower().strip()
    one_word_map = {
        "cat": "a realistic tabby cat",
        "dog": "a realistic friendly dog",
        "woman": "a realistic young woman",
        "man": "a realistic young man",
        "student": "a realistic university student",
        "girl": "a realistic young woman",
        "boy": "a realistic young man",
    }
    if low in one_word_map:
        return one_word_map[low]

    if len(p.split()) > 45:
        p = " ".join(p.split()[:45]).rstrip(",.;")
    return p


def enhance_video_prompt(
    prompt: str,
    negative_prompt: str | None = None,
    duration: int | None = None,
    width: int | None = None,
    height: int | None = None,
) -> PromptResult:
    raw = (prompt or "").strip()
    subject = _summarize_subject(raw)
    low = raw.lower()

    if any(x in low for x in ["walk", "walking", "campus", "student"]):
        action = "walking slowly with natural body movement"
        camera = "medium shot, stable camera, gentle cinematic tracking"
        scene = "bright university campus or modern school corridor"
    elif any(x in low for x in ["cat", "dog", "pet", "animal"]):
        action = "looking at the camera, blinking, and moving its head slightly"
        camera = "stable close-up camera, natural shallow depth of field"
        scene = "clean indoor environment with soft daylight"
    elif any(x in low for x in ["smile", "smiling", "portrait", "face"]):
        action = "smiling naturally with subtle head movement"
        camera = "stable close-up cinematic camera"
        scene = "soft realistic background with warm natural light"
    else:
        action = "moving subtly and naturally"
        camera = "stable cinematic camera, smooth motion"
        scene = "realistic clean environment with natural light"

    try:
        seconds = max(2, min(int(duration or 4), 16))
    except Exception:
        seconds = 4

    final = (
        f"A realistic cinematic video of {subject}, {action}. "
        f"Scene: {scene}. Camera: {camera}. Lighting: natural, soft, realistic, not overexposed. "
        "Motion: smooth, slow, coherent, stable subject identity, no sudden changes, no camera shake. "
        "Composition: centered single subject, clean uncluttered background, professional real-life footage, "
        "sharp details, natural colors, realistic texture, high quality. "
        f"Duration: about {seconds} seconds, 8 fps look."
    )

    neg = (negative_prompt or "").strip()
    bad_subject_words = ["cat", "dog", "woman", "man", "student", "person", "people", "girl", "boy", "campus", "face", "camera", "realistic"]
    if neg:
        parts = [p.strip() for p in neg.split(",") if p.strip()]
        parts = [p for p in parts if p.lower() not in bad_subject_words]
        neg = _dedupe_csv(f"{', '.join(parts)}, {_negative_video_default()}")
    else:
        neg = _negative_video_default()

    return PromptResult(prompt=final, negative_prompt=neg, warnings=["Video prompt normalized for LTXV stability"], meta={})
