"""Audience Mirror: honest qualitative guidance with optional Ollama augmentation.

This route never claims measured user research. Scores remain indicative review
signals for iteration, whether the advanced local Ollama model is available or
the deterministic fallback is used.
"""
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.services.ollama_service import env_bool, json_chat

router = APIRouter(prefix="/assistant/audience", tags=["assistant-audience"])
CODE_VERSION = "audience-ollama-guidance-honest-reload-hotfix-2026-06-09"
Lang = Literal["auto", "en", "fr"]
ContentType = Literal["image", "brand_pack", "prompt", "other"]
AudienceSet = Literal["general", "students", "workers", "premium", "social"]


class AudienceReviewRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    content_title: str = Field(default="Untitled", max_length=180)
    content_type: ContentType = "prompt"
    content: str = Field(..., min_length=1, max_length=8000)
    brand_name: str = Field(default="", max_length=180)
    target_audience: str = Field(default="", max_length=400)
    audience_set: AudienceSet = "general"
    lang: Lang | str = "auto"
    model_mode: Literal["auto", "fast", "advanced"] | str = "advanced"


class PersonaReview(BaseModel):
    persona: str
    first_impression: str
    understood: str
    liked: str
    confused: str
    click_probability: int
    improvement: str


class AudienceScores(BaseModel):
    clarity: int
    emotional_appeal: int
    conversion_chance: int
    brand_fit: int
    trust: int
    urgency: int
    curiosity: int
    premium_feel: int


class AudienceSuggestion(BaseModel):
    action: Literal["fix_prompt", "generate_image", "copy_review"]
    title: str
    description: str
    prompt: str
    negative_prompt: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None


class AudienceReviewResponse(BaseModel):
    success: bool = True
    code_version: str = CODE_VERSION
    provider: str
    analysis_mode: str
    lang: str
    content_title: str
    content_type: ContentType
    audience_set: AudienceSet
    executive_summary: str
    scores: AudienceScores
    personas: list[PersonaReview]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    improved_prompt: str
    negative_prompt: str
    publish_advice: str
    suggestions: list[AudienceSuggestion]
    error: str | None = None


def lang_of(value: str | None, text: str = "") -> str:
    value = (value or "auto").lower()
    if value in {"en", "fr"}:
        return value
    return "fr" if any(w in text.lower() for w in ["bonjour", "merci", "francais", "français", "publicité"]) else "en"


def clamp_score(value: Any, fallback: int) -> int:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return fallback


def list_value(data: dict[str, Any], key: str, fallback: list[str], *, limit: int = 6) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        return fallback
    cleaned = [str(item).strip()[:400] for item in value if str(item).strip()]
    return cleaned[:limit] or fallback


def text_value(data: dict[str, Any], key: str, fallback: str, limit: int = 3000) -> str:
    value = str(data.get(key) or "").strip()
    return value[:limit] if value else fallback


def fallback_review(content: str, lang: str) -> dict[str, Any]:
    negative = "blurry, low quality, cluttered, confusing text, weak CTA, watermark, distorted, noisy, artifacts"
    improved = f"{content}. Clear main benefit, strong call to action, premium composition, readable hierarchy, clean commercial style, high quality."
    scores = {"clarity": 76, "emotional_appeal": 72, "conversion_chance": 68, "brand_fit": 78, "trust": 74, "urgency": 62, "curiosity": 70, "premium_feel": 76}
    if lang == "fr":
        return {
            "executive_summary": "Fallback indicatif: clarifier le bénéfice principal et renforcer le CTA.",
            "strengths": ["Idée exploitable", "Direction visuelle claire", "Potentiel social"],
            "weaknesses": ["CTA à renforcer", "Bénéfice principal à montrer plus tôt", "Hiérarchie visuelle à simplifier"],
            "recommendations": ["Ajouter une promesse claire", "Rendre le CTA plus visible", "Tester une version courte et directe"],
            "improved_prompt": improved,
            "negative_prompt": negative,
            "publish_advice": "Publier seulement après avoir renforcé le hook et le CTA.",
            "scores": scores,
        }
    return {
        "executive_summary": "Indicative fallback: clarify the main benefit and strengthen the CTA.",
        "strengths": ["Usable idea", "Clear visual direction", "Social potential"],
        "weaknesses": ["CTA could be stronger", "Main benefit should appear earlier", "Visual hierarchy can be simpler"],
        "recommendations": ["Add a clear promise", "Make the CTA more visible", "Test a shorter direct version"],
        "improved_prompt": improved,
        "negative_prompt": negative,
        "publish_advice": "Publish after strengthening the hook and CTA.",
        "scores": scores,
    }


@router.get("/health")
async def audience_health():
    return {"ok": True, "service": "audience_ollama_guidance_en_fr", "code_version": CODE_VERSION, "languages": ["en", "fr"], "analysis_mode": "qualitative_guidance_not_measured_user_research", "fallback_policy": "explicit_rule_based_fallback"}


@router.post("/review", response_model=AudienceReviewResponse)
@limiter.limit("30/minute")
async def audience_review(request: Request, payload: AudienceReviewRequest, current_user_id: int = Depends(get_current_user_id)):
    del current_user_id
    lang = lang_of(payload.lang, payload.content)
    fallback = fallback_review(payload.content, lang)
    system = (
        "Return JSON only with keys executive_summary, strengths, weaknesses, recommendations, improved_prompt, negative_prompt, publish_advice, scores. "
        "scores must contain clarity, emotional_appeal, conversion_chance, brand_fit, trust, urgency, curiosity, premium_feel from 0 to 100. "
        "This is qualitative creative guidance, NOT measured audience research. Be practical and never claim real users were surveyed. "
        f"Write values in {'French' if lang == 'fr' else 'English'}."
    )
    user = f"Audience set: {payload.audience_set}\nTarget audience: {payload.target_audience}\nBrand: {payload.brand_name}\nContent: {payload.content}"
    parsed, llm = await json_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        mode=payload.model_mode,
        feature="audience_mirror",
        timeout_seconds=45,
    )
    data = dict(fallback)
    if not parsed and env_bool("REQUIRE_OLLAMA", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama is required for production audience mirror but no valid structured AI response was returned: " + (llm.error or "invalid structured response"),
        )
    provider = "local_rule_based_audience_guidance"
    analysis_mode = "rule_based_guidance_not_measured_user_research"
    error = llm.error
    if parsed:
        for key in ["executive_summary", "improved_prompt", "negative_prompt", "publish_advice"]:
            data[key] = text_value(parsed, key, str(fallback[key]))
        for key in ["strengths", "weaknesses", "recommendations"]:
            data[key] = list_value(parsed, key, list(fallback[key]))
        scores_raw = parsed.get("scores") if isinstance(parsed.get("scores"), dict) else {}
        data["scores"] = {key: clamp_score(scores_raw.get(key), fallback["scores"][key]) for key in fallback["scores"]}
        provider = f"ollama_guidance:{llm.model}"
        analysis_mode = "ollama_guidance_not_measured_user_research"
        error = None
    if lang == "fr":
        persona = PersonaReview(persona="Client cible indicatif", first_impression="Signal créatif à revoir", understood="Le bénéfice doit rester explicite", liked="La direction proposée", confused="Le prochain clic si le CTA est faible", click_probability=data["scores"]["conversion_chance"], improvement="Rendre le CTA plus clair")
        titles = ("Corriger le prompt", "Générer image", "Copier analyse")
    else:
        persona = PersonaReview(persona="Indicative target customer", first_impression="Creative signal to review", understood="The benefit should remain explicit", liked="The proposed direction", confused="The next action if CTA is weak", click_probability=data["scores"]["conversion_chance"], improvement="Make the CTA clearer")
        titles = ("Fix prompt", "Generate image", "Copy review")
    suggestions = [
        AudienceSuggestion(action="fix_prompt", title=titles[0], description=data["executive_summary"], prompt=data["improved_prompt"], negative_prompt=data["negative_prompt"]),
        AudienceSuggestion(action="generate_image", title=titles[1], description=data["executive_summary"], prompt=data["improved_prompt"], negative_prompt=data["negative_prompt"], width=1280, height=720),
        AudienceSuggestion(action="copy_review", title=titles[2], description=data["executive_summary"], prompt=data["improved_prompt"], negative_prompt=data["negative_prompt"]),
    ]
    return AudienceReviewResponse(provider=provider, analysis_mode=analysis_mode, lang=lang, content_title=payload.content_title or "Campaign review", content_type=payload.content_type, audience_set=payload.audience_set, executive_summary=data["executive_summary"], scores=AudienceScores(**data["scores"]), personas=[persona], strengths=data["strengths"], weaknesses=data["weaknesses"], recommendations=data["recommendations"], improved_prompt=data["improved_prompt"], negative_prompt=data["negative_prompt"], publish_advice=data["publish_advice"], suggestions=suggestions, error=error)
