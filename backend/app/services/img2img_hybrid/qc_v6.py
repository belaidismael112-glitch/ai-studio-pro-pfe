from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageStat

from app.services.comfy_prompt_director_v6 import ComfyPromptPack, VisualDecision


def qc_comfy_v6(image_path: str, decision: VisualDecision, pack: ComfyPromptPack) -> dict:
    """Lightweight V7 QC.

    For Full Comfy Flyer, we do NOT reject because the product was not an exact pasted source-lock composite.
    ComfyUI is allowed to design the full poster. We only block missing/blank/broken outputs.
    """
    p = Path(image_path)
    if not p.exists():
        return {"ok": False, "reason": "output image missing"}
    try:
        img = Image.open(p).convert("RGB")
        if img.size[0] < 512 or img.size[1] < 512:
            return {"ok": False, "reason": f"output too small: {img.size}"}
        stat = ImageStat.Stat(img.resize((96, 96)))
        variance = sum(stat.var) / max(1, len(stat.var))
        if variance < 35:
            return {"ok": False, "reason": "output appears blank/flat", "variance": round(variance, 2), "size": list(img.size)}
        return {
            "ok": True,
            "reason": "comfy v7 full flyer pass",
            "size": list(img.size),
            "variance": round(variance, 2),
            "source_lock_strict": False if pack.mode == "flyer_poster" else None,
        }
    except Exception as exc:
        return {"ok": False, "reason": f"qc exception: {exc}"}
