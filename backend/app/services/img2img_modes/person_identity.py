from __future__ import annotations
from app.services.img2img_hybrid import generate_img2img
from app.services.img2img_hybrid.contracts import Img2ImgRequest


async def run_person_identity(source_image_path: str, prompt: str = "", width: int = 1024, height: int = 1024, output_dir: str = "static/images"):
    return await generate_img2img(Img2ImgRequest(mode="person_identity", source_image_path=source_image_path, prompt=prompt or "", width=width, height=height, strength=0.18, output_dir=output_dir))
