"""Dedicated Image-to-Image mode routes.
Import-safe V10 router for existing generations.py.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from app.core.database import get_db
except Exception:  # pragma: no cover
    from app.db.session import get_db  # type: ignore

try:
    from app.core.security import get_current_user_id
except Exception:  # pragma: no cover
    from app.api.v1.dependencies import get_current_user_id  # type: ignore

from app.api.v1.endpoints.generations import _generate_image_img2img_internal, GenerationResponse

router = APIRouter()


def _mode_handler(forced_mode: str):
    async def handler(
        request: Request,
        image: UploadFile = File(...),
        prompt: str = Form(""),
        negative_prompt: str = Form(""),
        strength: float = Form(0.22),
        style: Optional[str] = Form(None),
        size: Optional[str] = Form(None),
        model_id: Optional[str] = Form(None),
        subject_lock: bool = Form(True),
        gate_status: Optional[str] = Form(None),
        reference_quality_score: Optional[float] = Form(None),
        subject_preservation_score: Optional[float] = Form(None),
        subject_coverage_percent: Optional[float] = Form(None),
        subject_type: Optional[str] = Form(None),
        generation_mode: Optional[str] = Form("auto"),
        auto_crop: bool = Form(False),
        apply_template_overlay: bool = Form(False),
        identity_board: bool = Form(False),
        current_user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
    ):
        return await _generate_image_img2img_internal(
            request=request, image=image, prompt=prompt, negative_prompt=negative_prompt,
            strength=strength, style=style, size=size, model_id=model_id, subject_lock=subject_lock,
            gate_status=gate_status, reference_quality_score=reference_quality_score,
            subject_preservation_score=subject_preservation_score, subject_coverage_percent=subject_coverage_percent,
            subject_type=subject_type, generation_mode=generation_mode, auto_crop=auto_crop,
            apply_template_overlay=apply_template_overlay, identity_board=identity_board,
            current_user_id=current_user_id, db=db, forced_mode=forced_mode,
        )
    handler.__name__ = f"generate_img2img_{forced_mode}"
    return handler

for suffix, mode in [
    ("auto", "auto"), ("person-identity", "person_identity"), ("product-ad", "product_ad"),
    ("flyer-poster", "flyer_poster"), ("background-replace", "background_replace"), ("creative-image", "creative_image"),
]:
    router.add_api_route(f"/image/img2img/{suffix}", _mode_handler(mode), methods=["POST"], response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
