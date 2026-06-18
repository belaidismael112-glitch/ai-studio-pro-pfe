from __future__ import annotations

from PIL import Image, ImageStat


def design_qc(path: str, expected_size: tuple[int, int] = (832, 1024)) -> dict:
    try:
        im = Image.open(path).convert("RGB")
    except Exception as e:
        return {"ok": False, "reason": f"cannot open output: {e}"}
    if im.size != expected_size:
        return {"ok": False, "reason": f"wrong size {im.size}; expected {expected_size}"}
    stat = ImageStat.Stat(im.resize((96, 118)))
    var = sum(stat.var) / 3.0
    if var < 120:
        return {"ok": False, "reason": "output too flat/blank", "variance": round(var, 2)}
    return {"ok": True, "reason": "category design engine pass", "size": list(im.size), "variance": round(var, 2)}
