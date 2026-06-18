from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Img2ImgMode = Literal[
    "auto",
    "person_identity",
    "product_ad",
    "flyer_poster",
    "background_replace",
    "creative_image",
]

RendererType = Literal[
    "comfy",
    "deterministic_flyer",
    "deterministic_composite",
    "hybrid",
]


@dataclass
class Img2ImgRequest:
    mode: str
    source_image_path: str
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    style: str | None = None
    strength: float = 0.25
    subject_type: str | None = None
    user_id: int | None = None
    output_dir: str = "static/images"
    ai_backdrop_path: str | None = None


@dataclass
class ImageAnalysis:
    subject_label: str
    subject_type: str
    category: str
    mood: str
    main_colors: list[str] = field(default_factory=list)
    is_product: bool = False
    is_person: bool = False
    is_living_subject: bool = False
    is_packshot: bool = False
    contains_text: bool = False
    suggested_mode: str = "creative_image"
    confidence: float = 0.5
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CreativeBrief:
    mode: str
    title: str
    subtitle: str
    cta: str
    badge: str = ""
    bullets: list[str] = field(default_factory=list)
    scene_description: str = ""
    style_direction: str = ""
    layout_type: str = ""
    palette: list[str] = field(default_factory=list)
    negative_prompt: str = ""


@dataclass
class RenderPlan:
    mode: str
    renderer: str
    analysis: ImageAnalysis
    brief: CreativeBrief
    source_subject_path: str | None = None
    background_prompt: str = ""
    ai_backdrop_path: str | None = None
    final_width: int = 1024
    final_height: int = 1024
    output_dir: str = "static/images"
    ai_backdrop_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderResult:
    success: bool
    local_path: str | None = None
    public_url: str | None = None
    renderer_used: str = ""
    provider: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
