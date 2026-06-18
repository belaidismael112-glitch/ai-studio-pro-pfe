"""Professional Neural Camera / Identity source-lock report renderer.

This renderer creates an honest review report, not a fake AI portrait.  It is
used only when the user explicitly asks for an identity/source-lock analysis
board.  Normal Person / Identity generation should use the AI workflow and this
report should not replace the final generated image.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
import os
import math

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageStat


@dataclass(slots=True)
class IdentityBoardResult:
    local_path: str
    width: int
    height: int
    source_locked: bool
    identity_strategy: str
    portrait_local_path: str | None = None


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return int(default)


def _font(size: int, *, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, max(10, int(size)))
        except Exception:
            pass
    return ImageFont.load_default()


def _finish_portrait(img: Image.Image) -> Image.Image:
    """Apply restrained photographic finishing without changing identity."""
    out = ImageOps.exif_transpose(img).convert("RGB")
    out = ImageOps.autocontrast(out, cutoff=(0.18, 0.18))
    out = ImageEnhance.Contrast(out).enhance(1.028)
    out = ImageEnhance.Color(out).enhance(1.010)
    out = ImageEnhance.Sharpness(out).enhance(1.030)
    return out


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=max(1, radius), fill=255)
    return mask


def _fit_cover(img: Image.Image, size: tuple[int, int], *, centering: tuple[float, float] = (0.5, 0.48)) -> Image.Image:
    return ImageOps.fit(ImageOps.exif_transpose(img).convert("RGB"), size, Image.Resampling.LANCZOS, centering=centering)


def _fit_contain_with_blur(img: Image.Image, size: tuple[int, int], *, pad: int = 0) -> Image.Image:
    w, h = size
    src = ImageOps.exif_transpose(img).convert("RGB")
    plate = _fit_cover(src, (w, h), centering=(0.5, 0.48)).filter(ImageFilter.GaussianBlur(max(6, min(w, h) // 36)))
    plate = ImageEnhance.Brightness(plate).enhance(0.70)
    plate = ImageEnhance.Contrast(plate).enhance(0.86)
    available = (max(1, w - 2 * pad), max(1, h - 2 * pad))
    fg = ImageOps.contain(src, available, Image.Resampling.LANCZOS)
    x = (w - fg.width) // 2
    y = (h - fg.height) // 2
    plate.paste(fg, (x, y))
    return plate


def _paste_rounded(canvas: Image.Image, img: Image.Image, box: tuple[int, int, int, int], *, radius: int = 24, cover: bool = True, border=(255, 255, 255, 56)) -> None:
    x1, y1, x2, y2 = box
    w, h = max(1, x2 - x1), max(1, y2 - y1)
    fitted = _fit_cover(img, (w, h)) if cover else _fit_contain_with_blur(img, (w, h), pad=max(4, min(w, h) // 54))
    mask = _rounded_mask((w, h), radius)
    canvas.paste(fitted, (x1, y1), mask)
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, outline=border, width=2)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in (text or "").split():
        probe = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), probe, font=font)
        if not current or box[2] - box[0] <= max_width:
            current = probe
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _gradient_background(size: tuple[int, int]) -> Image.Image:
    w, h = size
    canvas = Image.new("RGB", size, (5, 7, 16))
    draw = ImageDraw.Draw(canvas)
    for y in range(h):
        t = y / max(1, h - 1)
        draw.line((0, y, w, y), fill=(int(5 + 5 * t), int(7 + 10 * t), int(16 + 20 * t)))
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((w * 0.36, -h * 0.20, w * 1.10, h * 0.60), fill=(82, 59, 245, 45))
    gd.ellipse((w * 0.58, h * 0.48, w * 1.10, h * 1.13), fill=(16, 170, 220, 25))
    gd.ellipse((-w * 0.18, h * 0.50, w * 0.34, h * 1.12), fill=(121, 72, 255, 22))
    return Image.alpha_composite(canvas.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(max(20, w // 30)))).convert("RGB")


def _draw_check_icon(draw: ImageDraw.ImageDraw, x: int, y: int, *, size: int = 14, color=(88, 235, 165, 255)) -> None:
    stroke = max(2, size // 5)
    draw.ellipse((x, y, x + size, y + size), outline=color, width=max(1, stroke // 2))
    draw.line((x + int(size * 0.26), y + int(size * 0.55), x + int(size * 0.43), y + int(size * 0.72), x + int(size * 0.78), y + int(size * 0.30)), fill=color, width=stroke, joint="curve")


def _draw_warn_icon(draw: ImageDraw.ImageDraw, x: int, y: int, *, size: int = 14, color=(255, 195, 91, 255)) -> None:
    draw.rounded_rectangle((x, y, x + size, y + size), radius=max(2, size // 4), outline=color, width=2)
    font = _font(max(10, size - 2), bold=True)
    draw.text((x + size * 0.36, y - 1), "!", font=font, fill=color)


def _bullet_lines(draw: ImageDraw.ImageDraw, x: int, y: int, lines: list[tuple[str, str] | str], *, max_width: int, font_size: int = 16) -> int:
    font = _font(font_size)
    step = int(font_size * 1.44)
    for item in lines:
        level, line = ("ok", item) if isinstance(item, str) else item
        wrapped = _wrap(draw, line, font, max_width - 30)
        for idx, part in enumerate(wrapped):
            if idx == 0:
                if level == "warn":
                    _draw_warn_icon(draw, x, y + 3, size=max(11, font_size - 2))
                else:
                    _draw_check_icon(draw, x, y + 3, size=max(11, font_size - 2))
            draw.text((x + 26, y), part, font=font, fill=(224, 233, 247, 248))
            y += step
        y += 4
    return y


def _section_header(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, *, font_size: int = 20) -> int:
    font = _font(font_size, bold=True)
    draw.text((x, y), text.upper(), font=font, fill=(247, 249, 255, 255))
    return y + int(font_size * 1.48)


def _metric_card(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, label: str, value: str, status: str = "OK") -> None:
    status_ok = status.upper() in {"OK", "READY", "GOOD", "PASS"}
    fill = (10, 17, 31, 230)
    outline = (91, 235, 169, 90) if status_ok else (255, 196, 92, 90)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=fill, outline=outline, width=2)
    label_font = _font(14, bold=True)
    value_font = _font(22, bold=True)
    status_font = _font(12, bold=True)
    draw.text((x + 16, y + 13), label.upper(), font=label_font, fill=(156, 170, 198, 255))
    draw.text((x + 16, y + 39), value, font=value_font, fill=(255, 255, 255, 255))
    sw = draw.textbbox((0, 0), status.upper(), font=status_font)
    chip_w = max(54, sw[2] - sw[0] + 18)
    draw.rounded_rectangle((x + w - chip_w - 14, y + 14, x + w - 14, y + 38), radius=10, fill=(25, 92, 65, 210) if status_ok else (108, 74, 21, 220))
    draw.text((x + w - chip_w - 5, y + 19), status.upper(), font=status_font, fill=(226, 255, 242, 255) if status_ok else (255, 238, 203, 255))


def _quality_report(img: Image.Image) -> dict[str, str | float]:
    src = ImageOps.exif_transpose(img).convert("RGB")
    w, h = src.size
    small = src.resize((min(320, w), max(1, int(min(320, w) * h / max(1, w)))), Image.Resampling.BILINEAR)
    gray = small.convert("L")
    stat = ImageStat.Stat(gray)
    luminance = float(stat.mean[0])
    contrast = float(stat.stddev[0])
    edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    # Lightweight, dependency-free quality estimation. Values are deliberately
    # conservative because the report is advisory, not a security decision.
    sharp_score = max(0.0, min(100.0, edges * 2.4))
    light_score = max(0.0, min(100.0, 100.0 - abs(luminance - 132.0) * 0.78))
    contrast_score = max(0.0, min(100.0, contrast * 2.7))
    overall = round((sharp_score * 0.42 + light_score * 0.32 + contrast_score * 0.26), 1)
    aspect = w / max(1, h)
    if overall >= 70:
        quality_label = "Ready"
    elif overall >= 52:
        quality_label = "Review"
    else:
        quality_label = "Retake"
    lighting_label = "Balanced" if 72 <= luminance <= 188 else ("Dark" if luminance < 72 else "Bright")
    sharp_label = "Sharp" if sharp_score >= 50 else "Soft"
    return {
        "resolution": f"{w}×{h}",
        "aspect": f"{aspect:.2f}:1",
        "quality": f"{overall:.0f}/100",
        "quality_label": quality_label,
        "lighting_label": lighting_label,
        "sharp_label": sharp_label,
        "luminance": luminance,
        "sharp_score": sharp_score,
    }


def _prompt_summary(prompt: str) -> str:
    clean = " ".join((prompt or "").replace("\n", " ").split())
    if not clean:
        return "No user prompt supplied. Report generated from the uploaded source image."
    return clean[:145] + ("…" if len(clean) > 145 else "")


def _preview_variant(img: Image.Image, index: int) -> Image.Image:
    out = _finish_portrait(img)
    if index == 0:
        return ImageEnhance.Brightness(out).enhance(0.99)
    if index == 1:
        return ImageEnhance.Contrast(out).enhance(1.04)
    return ImageEnhance.Color(ImageEnhance.Brightness(out).enhance(1.015)).enhance(1.018)


def _save_portrait_export(source: Image.Image, target_dir: Path, *, min_long_edge: int = 1600) -> Path:
    portrait = _finish_portrait(source)
    long_edge = max(portrait.size)
    if long_edge < min_long_edge:
        scale = min_long_edge / max(1, long_edge)
        portrait = portrait.resize((max(1, int(round(portrait.width * scale))), max(1, int(round(portrait.height * scale)))), Image.Resampling.LANCZOS)
    target = target_dir / f"generated_identity_portrait_source_lock_{uuid4().hex}.png"
    portrait.save(target, format="PNG", optimize=True)
    return target


def render_identity_production_board(source_path: str | Path, *, prompt: str = "", output_dir: str | Path | None = None, width: int | None = None, height: int | None = None) -> IdentityBoardResult:
    """Render a professional source-analysis board and clean portrait export.

    The uploaded face is never regenerated in this report.  The report is for
    review / quality control only; the normal Person Identity route should show
    the AI-generated output when this optional board is not requested.
    """
    source = ImageOps.exif_transpose(Image.open(source_path)).convert("RGB")
    report = _quality_report(source)
    board_w = max(1500, int(width or _env_int("IDENTITY_BOARD_WIDTH", 1760)))
    board_h = max(980, int(height or _env_int("IDENTITY_BOARD_HEIGHT", 1080)))
    if board_w / board_h < 1.48:
        board_w = int(board_h * 1.58)

    target_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2] / "static" / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    portrait_target = _save_portrait_export(source, target_dir)

    canvas = _gradient_background((board_w, board_h)).convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")

    margin = max(24, board_w // 70)
    gap = max(16, board_w // 105)
    left_w = int(board_w * 0.31)
    hero_x1 = left_w + margin + gap
    hero_x2 = board_w - margin
    hero_y1 = margin
    hero_y2 = int(board_h * 0.635)

    # Left rail: honest report, not fake generation copy.
    draw.rounded_rectangle((margin, margin, left_w, board_h - margin), radius=26, fill=(3, 8, 19, 238), outline=(255, 255, 255, 44), width=2)
    x = margin + 26
    y = margin + 28
    title_font = _font(max(25, board_w // 58), bold=True)
    sub_font = _font(max(13, board_w // 118), bold=True)
    body_size = max(13, board_w // 124)
    draw.text((x, y), "NEURAL CAMERA", font=title_font, fill=(255, 255, 255, 255))
    y += int(getattr(title_font, "size", 30) * 1.05)
    draw.text((x, y), "ANALYSIS REPORT", font=title_font, fill=(255, 255, 255, 255))
    y += int(getattr(title_font, "size", 30) * 1.35)
    draw.text((x, y), "SOURCE-LOCK / QUALITY GATE", font=sub_font, fill=(169, 132, 255, 255))
    y += 42

    y = _section_header(draw, x, y, "What this file is", font_size=max(16, board_w // 106))
    y = _bullet_lines(draw, x, y, [
        ("ok", "Reference image preserved for identity safety."),
        ("warn", "This board is a diagnostic report, not the final AI portrait."),
        ("ok", "Use the generated result image for delivery; use this board for review."),
    ], max_width=left_w - x - 18, font_size=body_size)
    y += 10

    y = _section_header(draw, x, y, "Generation decision", font_size=max(16, board_w // 106))
    qlabel = str(report.get("quality_label"))
    y = _bullet_lines(draw, x, y, [
        ("ok" if qlabel != "Retake" else "warn", f"Image readiness: {report['quality']} · {qlabel}."),
        ("ok", "Recommended route: Person / Identity with source-lock."),
        ("ok", "Keep denoise low to avoid facial drift."),
        ("warn", "For AI beautification/stylization, leave the report option OFF."),
    ], max_width=left_w - x - 18, font_size=body_size)
    y += 10

    y = _section_header(draw, x, y, "Prompt intent", font_size=max(16, board_w // 106))
    prompt_font = _font(body_size)
    prompt_box_h = max(82, int(board_h * 0.082))
    draw.rounded_rectangle((x, y, left_w - 22, y + prompt_box_h), radius=18, fill=(8, 15, 28, 230), outline=(255, 255, 255, 28), width=1)
    py = y + 14
    for line in _wrap(draw, _prompt_summary(prompt), prompt_font, left_w - x - 60)[:4]:
        draw.text((x + 16, py), line, font=prompt_font, fill=(220, 229, 245, 246))
        py += int(body_size * 1.38)
    y += prompt_box_h + 18

    y = _section_header(draw, x, y, "QC notes", font_size=max(16, board_w // 106))
    _bullet_lines(draw, x, y, [
        ("ok", f"Resolution: {report['resolution']}"),
        ("ok" if report["lighting_label"] == "Balanced" else "warn", f"Lighting: {report['lighting_label']}"),
        ("ok" if report["sharp_label"] == "Sharp" else "warn", f"Sharpness: {report['sharp_label']}"),
    ], max_width=left_w - x - 18, font_size=body_size)

    # Hero visual.
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((hero_x1 + 8, hero_y1 + 12, hero_x2 + 8, hero_y2 + 12), radius=32, fill=(0, 0, 0, 120))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(18)))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((hero_x1, hero_y1, hero_x2, hero_y2), radius=32, fill=(8, 12, 22, 255), outline=(255, 255, 255, 48), width=2)
    _paste_rounded(canvas, _finish_portrait(source), (hero_x1 + 8, hero_y1 + 8, hero_x2 - 8, hero_y2 - 8), radius=28, cover=False)

    chip_w = max(315, board_w // 4)
    chip_h = max(50, board_h // 21)
    chip_x = hero_x1 + (hero_x2 - hero_x1 - chip_w) // 2
    draw.rounded_rectangle((chip_x, hero_y1 + 12, chip_x + chip_w, hero_y1 + 12 + chip_h), radius=18, fill=(54, 28, 114, 238), outline=(191, 130, 255, 95), width=2)
    chip_font = _font(max(13, board_w // 112), bold=True)
    chip_text = "REPORT ONLY · FINAL AI OUTPUT SEPARATE"
    tb = draw.textbbox((0, 0), chip_text, font=chip_font)
    draw.text((chip_x + (chip_w - (tb[2] - tb[0])) / 2, hero_y1 + 12 + (chip_h - (tb[3] - tb[1])) / 2 - 2), chip_text, font=chip_font, fill=(255, 255, 255, 255))

    # Metrics strip.
    metrics_y = hero_y2 + gap
    metrics_h = max(92, board_h // 10)
    metric_gap = 14
    metric_w = (hero_x2 - hero_x1 - 3 * metric_gap) // 4
    _metric_card(draw, hero_x1, metrics_y, metric_w, metrics_h, "Quality", str(report["quality"]), "READY" if report["quality_label"] == "Ready" else str(report["quality_label"]))
    _metric_card(draw, hero_x1 + (metric_w + metric_gap), metrics_y, metric_w, metrics_h, "Lighting", str(report["lighting_label"]), "OK" if report["lighting_label"] == "Balanced" else "Review")
    _metric_card(draw, hero_x1 + 2 * (metric_w + metric_gap), metrics_y, metric_w, metrics_h, "Sharpness", str(report["sharp_label"]), "OK" if report["sharp_label"] == "Sharp" else "Review")
    _metric_card(draw, hero_x1 + 3 * (metric_w + metric_gap), metrics_y, metric_w, metrics_h, "Resolution", str(report["resolution"]), "OK")

    # Original + finishing previews, clearly labelled as source-preserved.
    strip_y1 = metrics_y + metrics_h + gap
    strip_y2 = board_h - margin - 60
    draw.rounded_rectangle((hero_x1, strip_y1, hero_x2, strip_y2), radius=24, fill=(3, 8, 18, 226), outline=(255, 255, 255, 36), width=2)
    label_font = _font(max(12, board_w // 128), bold=True)
    draw.text((hero_x1 + 18, strip_y1 + 14), "ORIGINAL SOURCE", font=label_font, fill=(190, 143, 255, 255))
    source_w = max(170, int((hero_x2 - hero_x1) * 0.22))
    thumb_y1 = strip_y1 + 44
    thumb_y2 = strip_y2 - 14
    _paste_rounded(canvas, source, (hero_x1 + 16, thumb_y1, hero_x1 + 16 + source_w, thumb_y2), radius=15, cover=False)

    previews_x = hero_x1 + 34 + source_w
    draw.text((previews_x, strip_y1 + 14), "SOURCE-PRESERVED FINISHING PREVIEWS", font=label_font, fill=(190, 143, 255, 255))
    available = hero_x2 - previews_x - 16
    preview_gap = 12
    preview_w = max(116, (available - preview_gap * 2) // 3)
    for idx in range(3):
        vx1 = previews_x + idx * (preview_w + preview_gap)
        _paste_rounded(canvas, _preview_variant(source, idx), (vx1, thumb_y1, vx1 + preview_w, thumb_y2), radius=15, cover=False)

    footer_y = board_h - margin - 46
    draw.rounded_rectangle((hero_x1, footer_y, hero_x2, board_h - margin), radius=18, fill=(42, 18, 86, 240), outline=(184, 118, 255, 90), width=2)
    footer_font = _font(max(13, board_w // 116), bold=True)
    footer = "NEURAL CAMERA REPORT  •  SOURCE PRESERVED  •  NOT A FINAL AI-GENERATED PORTRAIT"
    fb = draw.textbbox((0, 0), footer, font=footer_font)
    draw.text((hero_x1 + (hero_x2 - hero_x1 - (fb[2] - fb[0])) / 2, footer_y + 14), footer, font=footer_font, fill=(255, 255, 255, 255))

    target = target_dir / f"generated_identity_board_source_lock_{uuid4().hex}.png"
    canvas.convert("RGB").save(target, format="PNG", optimize=True)
    return IdentityBoardResult(
        local_path=str(target),
        width=board_w,
        height=board_h,
        source_locked=True,
        identity_strategy="neural_camera_identity_report_v3_optional",
        portrait_local_path=str(portrait_target),
    )
