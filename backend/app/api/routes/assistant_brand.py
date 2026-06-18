"""Brand Studio / Launch Pack with Ollama augmentation and explicit fallback."""
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.services.ollama_service import env_bool, json_chat

router = APIRouter(prefix="/assistant/brand", tags=["assistant-brand"])
CODE_VERSION = "brand-dual-ollama-reload-hotfix-2026-06-09"
Lang = Literal["auto", "en", "fr"]
Target = Literal["image"]


class BrandPackRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    brand_name: str = Field(..., min_length=1, max_length=160)
    business_type: str = Field(default="", max_length=240)
    audience: str = Field(default="", max_length=300)
    idea: str = Field(default="", max_length=2000)
    lang: Lang | str = "auto"
    target: Target = "image"
    model_mode: Literal["auto", "fast", "advanced"] | str = "advanced"


class BrandSuggestion(BaseModel):
    action: Literal["generate_image", "copy_pack"]
    title: str
    description: str
    prompt: str
    negative_prompt: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None


class BrandPackResponse(BaseModel):
    success: bool = True
    code_version: str = CODE_VERSION
    provider: str
    analysis_mode: str = "ollama_augmented_or_explicit_rule_based_fallback"
    lang: str
    target: Target
    brand_name: str
    business_type: str
    audience: str
    slogan: str
    brand_voice: str
    colors: list[str]
    description: str
    captions: list[str]
    hashtags: list[str]
    cta: str
    image_prompt: str
    negative_prompt: str
    launch_plan: list[str]
    suggestions: list[BrandSuggestion]
    error: str | None = None


def lang_of(value: str | None, text: str = "") -> str:
    value = (value or "auto").lower()
    if value in {"en", "fr"}:
        return value
    return "fr" if any(w in text.lower() for w in ["bonjour", "francais", "français", "publicité", "marque"]) else "en"


def text_value(data: dict[str, Any], key: str, fallback: str, limit: int = 3000) -> str:
    value = str(data.get(key) or "").strip()
    return value[:limit] if value else fallback


def list_value(data: dict[str, Any], key: str, fallback: list[str], *, limit: int = 8) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        return fallback
    cleaned = [str(item).strip()[:300] for item in value if str(item).strip()]
    return cleaned[:limit] or fallback


def fallback_pack(name: str, business: str, audience: str, lang: str) -> dict[str, Any]:
    negative = "low quality, blurry, noisy, watermark, fake text, unreadable typography, distorted product, bad composition, artifacts"
    image = f"Premium advertising visual for {name}, {business}, made for {audience}. Clean brand composition, sharp subject, elegant lighting, modern commercial design, realistic details, readable layout."
    if lang == "fr":
        return {
            "slogan": f"{name} — clair, premium, mémorable",
            "brand_voice": "Chaleureux, premium, moderne et orienté client.",
            "description": f"Fallback déterministe: {name} est une marque {business} pensée pour {audience}.",
            "captions": [f"Découvrez {name} avec une expérience premium.", f"Une nouvelle façon de présenter {business} avec confiance.", f"{name}: simple, élégant et mémorable."],
            "hashtags": ["#AIStudioPro", "#CreativeAI", "#BrandDesign"],
            "cta": "Découvrir maintenant",
            "image_prompt": image,
            "negative_prompt": negative,
            "launch_plan": ["Clarifier l'offre", "Créer les visuels", "Tester deux hooks", "Publier et mesurer", "Optimiser selon les résultats"],
            "colors": ["#0F172A", "#22D3EE", "#D946EF"],
        }
    return {
        "slogan": f"{name} — clear, premium, memorable",
        "brand_voice": "Warm, premium, modern, and customer-focused.",
        "description": f"Deterministic fallback: {name} is a {business} brand built for {audience}.",
        "captions": [f"Discover {name} with a premium experience.", f"A better way to present {business} with confidence.", f"{name}: simple, elegant, and memorable."],
        "hashtags": ["#AIStudioPro", "#CreativeAI", "#BrandDesign"],
        "cta": "Discover now",
        "image_prompt": image,
        "negative_prompt": negative,
        "launch_plan": ["Clarify the offer", "Create visual assets", "Test two hooks", "Publish and measure", "Optimize from results"],
        "colors": ["#0F172A", "#22D3EE", "#D946EF"],
    }


@router.get("/health")
async def brand_health():
    return {"ok": True, "service": "brand_studio_ollama_augmented", "code_version": CODE_VERSION, "languages": ["en", "fr"], "fallback_policy": "explicit_rule_based_fallback"}


@router.post("/pack", response_model=BrandPackResponse)
@limiter.limit("20/minute")
async def brand_pack(request: Request, payload: BrandPackRequest, current_user_id: int = Depends(get_current_user_id)):
    del current_user_id
    lang = lang_of(payload.lang, payload.brand_name + " " + payload.idea)
    name = " ".join(payload.brand_name.split()) or "New Brand"
    business = payload.business_type.strip() or "creative business"
    audience = payload.audience.strip() or "modern customers"
    fallback = fallback_pack(name, business, audience, lang)
    system = (
        "Return JSON only with keys slogan, brand_voice, colors, description, captions, hashtags, cta, image_prompt, negative_prompt, launch_plan. "
        "You build a practical image-first launch pack. Use 3 to 5 colors as hex strings, 3 captions, 3 to 6 hashtags, and 5 launch steps. "
        f"Write values in {'French' if lang == 'fr' else 'English'}. Do not claim assets were generated."
    )
    user = f"Brand: {name}\nBusiness: {business}\nAudience: {audience}\nIdea: {payload.idea.strip()}"
    parsed, llm = await json_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        mode=payload.model_mode,
        feature="brand_studio",
        timeout_seconds=45,
    )
    data = dict(fallback)
    if not parsed and env_bool("REQUIRE_OLLAMA", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama is required for production brand studio but no valid structured AI response was returned: " + (llm.error or "invalid structured response"),
        )
    provider = "local_rule_based_brand_studio"
    error = llm.error
    if parsed:
        for key in ["slogan", "brand_voice", "description", "cta", "image_prompt", "negative_prompt"]:
            data[key] = text_value(parsed, key, str(fallback[key]))
        for key, limit in [("colors", 5), ("captions", 4), ("hashtags", 8), ("launch_plan", 7)]:
            data[key] = list_value(parsed, key, list(fallback[key]), limit=limit)
        provider = llm.provider
        error = None
    if lang == "fr":
        titles = ("Copier le pack", "Générer image")
    else:
        titles = ("Copy pack", "Generate image")
    suggestions = [
        BrandSuggestion(action="copy_pack", title=titles[0], description=data["description"], prompt=data["image_prompt"], negative_prompt=data["negative_prompt"]),
        BrandSuggestion(action="generate_image", title=titles[1], description=data["description"], prompt=data["image_prompt"], negative_prompt=data["negative_prompt"], width=1280, height=720),
    ]
    return BrandPackResponse(provider=provider, lang=lang, target=payload.target, brand_name=name, business_type=business, audience=audience, suggestions=suggestions, error=error, **data)
