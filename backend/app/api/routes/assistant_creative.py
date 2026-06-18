"""Creative Director + Prompt Doctor routes with Ollama augmentation.

When Ollama is ready the advanced local model produces a structured direction.
When it is unavailable the route returns a deterministic, explicitly labelled
fallback so the UI never pretends a model executed when it did not.
"""
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.services.ollama_service import env_bool, json_chat

router = APIRouter(prefix="/assistant/creative", tags=["assistant-creative"])
CODE_VERSION = "creative-dual-ollama-reload-hotfix-2026-06-09"
Lang = Literal["auto", "en", "fr"]
Target = Literal["image"]


class CreativePlanRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    idea: str = Field(..., min_length=1, max_length=5000)
    lang: Lang | str = "auto"
    target: Target = "image"
    page_context: str | None = Field(default=None, max_length=5000)
    model_mode: Literal["auto", "fast", "advanced"] | str = "advanced"


class CreativeSuggestion(BaseModel):
    action: Literal["generate_image", "make_prompt"]
    title: str
    description: str
    prompt: str
    negative_prompt: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None


class CreativePlanResponse(BaseModel):
    success: bool = True
    code_version: str = CODE_VERSION
    provider: str
    analysis_mode: str = "ollama_augmented_or_explicit_rule_based_fallback"
    lang: str
    target: Target
    title: str
    summary: str
    scene: str
    style: str
    lighting: str
    camera: str
    mood: str
    improved_prompt: str
    negative_prompt: str
    caption: str
    suggestions: list[CreativeSuggestion]
    error: str | None = None


def lang_of(value: str | None, text: str = "") -> str:
    value = (value or "auto").lower()
    if value in {"en", "fr"}:
        return value
    return "fr" if any(w in text.lower() for w in ["bonjour", "merci", "francais", "français", "publicité"]) else "en"


def text_value(data: dict[str, Any], key: str, fallback: str, limit: int = 3000) -> str:
    value = str(data.get(key) or "").strip()
    return value[:limit] if value else fallback


def fallback_plan(idea: str, lang: str) -> dict[str, str]:
    negative = "low quality, blurry, noisy, watermark, distorted anatomy, unreadable text, bad composition, oversaturated, artifacts"
    if lang == "fr":
        return {
            "title": "Plan créatif professionnel",
            "summary": "Fallback déterministe: direction créative préparée sans exécution Ollama.",
            "scene": f"Scène commerciale propre autour de: {idea}. Sujet principal lisible, composition premium, arrière-plan contrôlé.",
            "style": "cinématique, réaliste, premium, propre",
            "lighting": "lumière douce, contraste maîtrisé, reflets élégants",
            "camera": "cadre stable, légère profondeur de champ, composition lisible",
            "mood": "moderne, professionnel, confiant",
            "improved_prompt": f"{idea}. Composition premium réaliste, sujet principal net, lumière cinématique douce, détails lisibles, arrière-plan propre, rendu commercial haut de gamme.",
            "negative_prompt": negative,
            "caption": "Direction locale de secours à revoir avant génération.",
        }
    return {
        "title": "Professional creative plan",
        "summary": "Deterministic fallback: creative direction prepared without an Ollama execution.",
        "scene": f"Clean commercial scene based on: {idea}. Clear main subject, premium composition, controlled background.",
        "style": "cinematic, realistic, premium, clean",
        "lighting": "soft cinematic light, controlled contrast, elegant reflections",
        "camera": "stable framing, slight depth of field, clean readable composition",
        "mood": "modern, professional, confident",
        "improved_prompt": f"{idea}. Premium realistic composition, sharp main subject, soft cinematic lighting, readable details, clean background, high-end commercial look.",
        "negative_prompt": negative,
        "caption": "Local fallback direction to review before generation.",
    }


@router.get("/health")
async def creative_health():
    return {"ok": True, "service": "creative_director_ollama_augmented", "code_version": CODE_VERSION, "languages": ["en", "fr"], "fallback_policy": "explicit_rule_based_fallback"}


@router.post("/plan", response_model=CreativePlanResponse)
@limiter.limit("30/minute")
async def creative_plan(request: Request, payload: CreativePlanRequest, current_user_id: int = Depends(get_current_user_id)):
    del current_user_id
    lang = lang_of(payload.lang, payload.idea)
    idea = " ".join(payload.idea.strip().split())
    fallback = fallback_plan(idea, lang)
    system = (
        "Return JSON only with keys title, summary, scene, style, lighting, camera, mood, improved_prompt, negative_prompt, caption. "
        "You are a practical image-first creative director and prompt doctor. Keep prompts realistic and generation-ready. "
        f"Write values in {'French' if lang == 'fr' else 'English'}. Do not claim an image was generated."
    )
    user = f"Idea: {idea}\nPage context: {(payload.page_context or '')[:1200]}"
    parsed, llm = await json_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        mode=payload.model_mode,
        feature="creative_director",
        timeout_seconds=45,
    )
    data = dict(fallback)
    if not parsed and env_bool("REQUIRE_OLLAMA", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama is required for production creative director but no valid structured AI response was returned: " + (llm.error or "invalid structured response"),
        )
    provider = "local_rule_based_creative_director"
    error = llm.error
    if parsed:
        for key, fallback_value in fallback.items():
            data[key] = text_value(parsed, key, fallback_value)
        provider = llm.provider
        error = None
    prompt = data["improved_prompt"]
    negative = data["negative_prompt"]
    if lang == "fr":
        titles = ("Utiliser le prompt amélioré", "Générer une image")
    else:
        titles = ("Use improved prompt", "Generate image")
    suggestions = [
        CreativeSuggestion(action="make_prompt", title=titles[0], description=data["summary"], prompt=prompt, negative_prompt=negative),
        CreativeSuggestion(action="generate_image", title=titles[1], description=data["scene"], prompt=prompt, negative_prompt=negative, width=1280, height=720),
    ]
    return CreativePlanResponse(provider=provider, lang=lang, target=payload.target, suggestions=suggestions, error=error, **data)
