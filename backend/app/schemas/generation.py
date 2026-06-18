"""Generation schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class GenerationType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    IMG2IMG = "img2img"
    IMG2VID = "img2vid"


class GenerationStatus(str, Enum):
    QUEUED = "queued"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageStyle(str, Enum):
    PHOTOREALISTIC = "photorealistic"
    DIGITAL_ART = "digital_art"
    ANIME = "anime"
    OIL_PAINTING = "oil_painting"
    WATERCOLOR = "watercolor"
    SKETCH = "sketch"
    STUDIO = "studio"
    CINEMATIC = "cinematic"
    NEONPUNK = "neonpunk"
    FANTASY = "fantasy"
    THREE_D = "3d"


class ImageGenerationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: Optional[str] = Field(None, max_length=1000)
    width: int = Field(1024, ge=256, le=2048)
    height: int = Field(1024, ge=256, le=2048)
    style: Optional[ImageStyle] = None
    num_inference_steps: int = Field(30, ge=10, le=100)
    guidance_scale: float = Field(7.5, ge=1.0, le=20.0)
    model_id: Optional[str] = Field(None, description="Model identifier, e.g. sdxl, sd15")


class VideoGenerationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: Optional[str] = Field(None, max_length=1000)
    duration: int = Field(4, ge=2, le=16)  # seconds
    width: int = Field(1024, ge=256, le=1920)
    height: int = Field(576, ge=256, le=1080)
    fps: int = Field(24, ge=12, le=60)
    model_id: Optional[str] = Field(None, description="Model identifier, e.g. runway-gen3")


class GenerationResponse(BaseModel):
    id: int
    generation_type: GenerationType
    prompt: str
    status: GenerationStatus
    result_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    style: Optional[str] = None
    credits_used: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GenerationListResponse(BaseModel):
    items: list[GenerationResponse]
    total: int
    page: int
    page_size: int


class GenerationWebhook(BaseModel):
    generation_id: int
    status: GenerationStatus
    result_url: Optional[str] = None
    error_message: Optional[str] = None
