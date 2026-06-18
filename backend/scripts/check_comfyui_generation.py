"""Live ComfyUI GPU smoke test for local production acceptance.

Run from the backend directory after ComfyUI is started and backend/.env is configured:
    python scripts/check_comfyui_generation.py

This performs one small text-to-image request and one small image-to-image request
through the same AIService methods used by the application. It is intentionally
separate from the fast connectivity preflight because it consumes GPU time.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from PIL import Image, ImageDraw  # noqa: E402
from app.services.ai_service import AIService  # noqa: E402


def _make_reference(path: Path) -> None:
    image = Image.new("RGB", (512, 512), (238, 241, 246))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((156, 70, 356, 442), radius=34, fill=(36, 108, 212), outline=(20, 52, 116), width=8)
    draw.ellipse((196, 118, 316, 238), fill=(245, 182, 36), outline=(120, 82, 12), width=6)
    draw.rectangle((190, 290, 322, 352), fill=(247, 247, 247), outline=(40, 40, 40), width=4)
    draw.text((211, 307), "TEST", fill=(20, 20, 20))
    image.save(path, format="PNG")


def _assert_result(label: str, result: dict) -> Path:
    ok = bool(result.get("success"))
    local_path = result.get("local_path")
    error = result.get("error")
    if not ok or not local_path:
        raise RuntimeError(f"{label} FAILED: {error or result}")
    path = Path(str(local_path))
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"{label} FAILED: local output file is missing or empty: {path}")
    print(f"{label}: OK ({path.name}, {path.stat().st_size} bytes)")
    return path


async def _run(keep_output: bool) -> int:
    service = AIService()
    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="aistudio_local_gpu_smoke_") as tmp:
        source = Path(tmp) / "reference.png"
        _make_reference(source)

        print("[1/2] Running live Text-to-Image smoke generation...")
        text_result = await service.generate_image(
            prompt="clean studio product test image, blue bottle on a simple neutral background, no text",
            negative_prompt="watermark, extra objects, unreadable text, blur",
            width=512,
            height=512,
            style="studio",
            num_inference_steps=8,
            guidance_scale=1.0,
        )
        outputs.append(_assert_result("Text-to-Image generation", text_result))

        print("[2/2] Running live Image-to-Image smoke generation...")
        img_result = await service.generate_image_from_image(
            image_path=str(source),
            prompt=(
                "Keep the uploaded bottle recognizable and place it in a clean premium studio environment. "
                "[AI_STUDIO_REFERENCE_MODE:background_replace]"
            ),
            negative_prompt="watermark, distorted bottle, unreadable text, blur",
            strength=0.42,
            width=512,
            height=512,
            style="studio",
            num_inference_steps=8,
            guidance_scale=1.0,
        )
        outputs.append(_assert_result("Image-to-Image generation", img_result))

    if not keep_output:
        for output in outputs:
            try:
                output.unlink(missing_ok=True)
            except Exception:
                pass
    else:
        print("Generated smoke outputs kept for manual review:")
        for output in outputs:
            print(f"- {output}")

    print("RESULT: READY (live ComfyUI text-to-image + image-to-image GPU smoke passed)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-output", action="store_true", help="Keep smoke images for visual review")
    args = parser.parse_args()
    try:
        return asyncio.run(_run(keep_output=args.keep_output))
    except Exception as exc:
        print(f"RESULT: NOT READY ({exc})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
