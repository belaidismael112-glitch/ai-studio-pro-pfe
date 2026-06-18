"""AI Studio Pro Assistant API - EN/FR voice only, flexible text input."""

import os
import asyncio
import re
import uuid
import subprocess
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.services.ollama_service import chat as ollama_chat, runtime_status as ollama_runtime_status

router = APIRouter(prefix="/assistant", tags=["assistant"])
ASSISTANT_CODE_VERSION = "assistant-dual-ollama-en-fr-voice-reload-hotfix-2026-06-09"


def support_admin_name() -> str:
    return os.getenv("SUPPORT_ADMIN_NAME", "Support Team").strip() or "Support Team"


def support_admin_email() -> str:
    return os.getenv("SUPPORT_ADMIN_EMAIL", "support@example.com").strip() or "support@example.com"


def support_admin_phone() -> str:
    return os.getenv("SUPPORT_ADMIN_PHONE", "").strip()


APP_KNOWLEDGE_EN = """
AI Studio Pro is a creative AI workspace for generating images and image-to-image assets.
Core user features:
- Image Generation: write a prompt, choose style/size, generate images through the backend and ComfyUI pipeline.
- Image-to-Image: upload a reference image, choose the right source-lock mode, and generate a new image that preserves the important subject details.
- Smart Agent: English/French assistant with voice input/output, visible conversation, approval before actions, Director Mode + Prompt Doctor, Neural Camera Analysis with a two-stage persona workflow, Brand Studio/Launch Pack, Audience Mirror, generate images, create image-to-image variations, regenerate, and download.
- History: review completed, queued, processing, and failed generations.
- Credits: view balance, buy/test credit packs, and track credit usage.
- Reclamations / Support Center: send a message to administration and follow the status/admin notes.
- Model Comparison: compare model/generation performance and results.
- Settings: manage profile, password, account, and workspace preferences.
Admin features:
- Admin Analytics overview for users, credits, generations, failed/completed jobs, and tickets.
- Users management: search users, update credits, activate/disable accounts, promote/remove admins.
- Generations management: inspect and delete generation records.
- Reclamations management: read support tickets, update status, add admin notes, resolve/delete tickets.
Product Studio / Product Campaign has been removed from this app version.
""".strip()

APP_KNOWLEDGE_FR = """
AI Studio Pro est un espace créatif IA pour générer des images et faire de l’image-vers-image à partir d’une image de référence.
Fonctions utilisateur principales :
- Image Generation : écrire un prompt, choisir style/taille, générer une image via le backend et ComfyUI.
- Image-to-Image : envoyer une image de référence, choisir le bon mode source-lock, puis générer une nouvelle image qui préserve les détails importants du sujet.
- Smart Agent : assistant anglais/français avec micro, voix, conversation visible, approbation avant action, Director Mode + Prompt Doctor, Neural Camera Analysis avec workflow persona en deux étapes, Brand Studio/Launch Pack, Audience Mirror, génération image, image-vers-image, régénération et téléchargement.
- History : suivre les générations terminées, en attente, en cours ou échouées.
- Credits : consulter le solde, acheter/tester des packs de crédits et suivre l’usage.
- Reclamations / Support Center : envoyer un message à l’administration et suivre le statut/réponse admin.
- Model Comparison : comparer les modèles et résultats.
- Settings : gérer profil, mot de passe, compte et préférences.
Fonctions admin :
- Admin Analytics : vue d’ensemble utilisateurs, crédits, générations, jobs échoués/terminés et tickets.
- Gestion utilisateurs : rechercher, modifier crédits, activer/désactiver, promouvoir/retirer admin.
- Gestion générations : inspecter et supprimer les générations.
- Gestion réclamations : lire tickets, modifier statut, ajouter notes admin, résoudre/supprimer.
Product Studio / Product Campaign a été supprimé de cette version.
""".strip()


def contact_reply(lang: str) -> str:
    name = support_admin_name()
    email = support_admin_email()
    phone = support_admin_phone()
    if lang == "fr":
        phone_line = f"\n- Téléphone urgent : {phone}" if phone else "\n- Téléphone urgent : non configuré pour le moment."
        return (
            f"Tu peux contacter l'administration de AI Studio Pro ici :\n"
            f"- Support admin : {name}\n"
            f"- Email : {email}"
            f"{phone_line}\n\n"
            "Tu peux aussi envoyer une réclamation directement depuis la page Reclamations / Support Center : explique le problème, envoie le message, puis l'admin peut répondre avec le statut et les notes."
        )
    phone_line = f"\n- Urgent phone: {phone}" if phone else "\n- Urgent phone: not configured yet."
    return (
        f"You can contact the AI Studio Pro administration here:\n"
        f"- Support admin: {name}\n"
        f"- Email: {email}"
        f"{phone_line}\n\n"
        "You can also send an administration message from Reclamations / Support Center: explain the problem, submit it, then the admin can reply with status and notes."
    )


def app_info_reply(lang: str) -> str:
    name = support_admin_name()
    email = support_admin_email()
    phone = support_admin_phone()
    if lang == "fr":
        phone_suffix = f" — {phone}" if phone else ""
        return APP_KNOWLEDGE_FR + f"\n\nContact administration : {name} — {email}{phone_suffix}."
    phone_suffix = f" — {phone}" if phone else ""
    return APP_KNOWLEDGE_EN + f"\n\nAdministration contact: {name} — {email}{phone_suffix}."


def route_app_question(message: str, lang: str) -> str | None:
    lowered = (message or "").lower()
    contact_terms = [
        "contact admin", "contact administration", "administration contact", "support admin", "admin email",
        "how can i contact", "how do i contact", "contact support", "reclamation", "complaint",
        "contacter", "administration", "support", "réclamation", "reclamation", "email admin"
    ]
    app_terms = [
        "what is this app", "what does this app do", "explain the app", "describe the app", "what can this app do",
        "features", "admin features", "how does ai studio pro work", "about this app",
        "c'est quoi", "que fait", "explique l'application", "fonctionnalités", "fonctionnalites", "à quoi sert", "a quoi sert"
    ]
    if any(term in lowered for term in contact_terms):
        return contact_reply(lang)
    if any(term in lowered for term in app_terms):
        return app_info_reply(lang)
    return None


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=12000)


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    message: str = Field(..., min_length=1, max_length=12000)
    messages: list[AssistantMessage] = Field(default_factory=list)
    page_context: str | None = Field(default=None, max_length=6000)
    lang: Literal["en", "fr"] | str = "en"
    model_mode: Literal["auto", "fast", "advanced"] | str = "auto"


class AssistantChatResponse(BaseModel):
    success: bool
    reply: str
    provider: str
    error: str | None = None
    code_version: str = ASSISTANT_CODE_VERSION


class AssistantSpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1200)
    lang: Literal["en", "fr"] | str | None = "en"


class AssistantSpeechResponse(BaseModel):
    success: bool
    audio_url: str | None = None
    error: str | None = None
    lang: str | None = None
    voice: str | None = None
    code_version: str = ASSISTANT_CODE_VERSION


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def contains_unsupported_language(text: str) -> bool:
    """Keep the assistant permissive for user input.

    Users may write Tunisian Arabic, Arabizi, English or French. The selected UI
    language still controls the answer language, but the message is never rejected
    merely because it contains Arabic script or Tunisian transliteration.
    """
    _ = text
    return False


def contains_arabic_script(text: str) -> bool:
    """Block Arabic-script audio synthesis while keeping Arabic text chat accepted."""

    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def looks_french(text: str) -> bool:
    lowered = (text or "").lower()
    markers = ["bonjour", "salut", "merci", "avec", "pour", "vous", "peux", "francais", "français", "generer", "générer", "video", "vidéo", "erreur", "parametres", "paramètres"]
    accents = bool(re.search(r"[àâçéèêëîïôûùüÿœ]", lowered))
    return accents or any(m in lowered for m in markers)


def resolve_lang(requested: str | None, message: str = "") -> Literal["en", "fr"]:
    value = (requested or "auto").lower().strip()
    if value == "fr":
        return "fr"
    if value == "en":
        return "en"
    return "fr" if looks_french(message) else "en"


def unsupported_reply(lang: str) -> str:
    if lang == "fr":
        return "Tu peux écrire en français, en anglais, en tunisien ou en Arabizi. La réponse reste dans la langue de sortie sélectionnée."
    return "You can write in English, French, Tunisian Arabic, or Arabizi. The reply stays in the selected output language."


def clean_reply(text: str, lang: str) -> str:
    reply = (text or "").strip()
    if not reply:
        return fallback_reply("", lang)
    if contains_unsupported_language(reply):
        return fallback_reply("", lang)
    return reply


def fallback_reply(message: str, lang: str = "en") -> str:
    lowered = (message or "").lower()
    routed = route_app_question(message, lang)
    if routed:
        return routed
    if lang == "fr":
        if "comfy" in lowered or "error" in lowered or "erreur" in lowered:
            return "Vérifie d'abord le backend, puis l'onglet Network, puis la console ComfyUI. Copie l'erreur exacte et je te dirai quelle route, quel node ou quel paramètre corriger."
        if "video" in lowered or "vidéo" in lowered:
            return "La génération vidéo est désactivée dans cette version image-first. Utilise Image-to-Image pour créer une variation propre à partir d'une référence."
        if "image" in lowered:
            return "Pour une image plus propre, décris le sujet principal, la composition, la lumière, le style et les détails lisibles. Ne mets jamais le sujet principal dans le negative prompt."
        if "credit" in lowered or "crédit" in lowered:
            return "Les crédits servent aux générations image et image-vers-image. Vérifie le solde, l'historique et les transactions dans la page Credits."
        return "Je peux t'aider en français avec les prompts, les paramètres image et image-vers-image, les erreurs ComfyUI, les crédits et l'historique."
    if "comfy" in lowered or "error" in lowered or "failed" in lowered:
        return "Check the backend terminal first, then the browser Network tab, then the ComfyUI console. Send the exact error and I will identify the broken route, node, or setting."
    if "video" in lowered:
        return "Video generation is disabled in this image-first build. Use Image-to-Image to create a clean variation from a reference image."
    if "image" in lowered:
        return "For a stronger image, describe the subject, composition, lighting, style, readable details, and a clear negative prompt. Never put the main subject in the negative prompt."
    if "credit" in lowered:
        return "Credits are used to run image and image-to-image generations. Review your balance and transaction history on the Credits page."
    return "I can help with prompts, image settings, image-to-image settings, ComfyUI errors, credits, history, and production checks."


def system_prompt(lang: str) -> str:
    language_instruction = (
        "Answer in French only. Never switch to English except product names, exact UI labels, code identifiers, URLs, or endpoint names."
        if lang == "fr"
        else "Answer in English only. Never switch to French except product names, exact UI labels, code identifiers, URLs, or endpoint names."
    )
    return f"""
You are Workspace Assistant inside AI Studio Pro.
{language_instruction}
You must know this app exactly:
{APP_KNOWLEDGE_FR if lang == "fr" else APP_KNOWLEDGE_EN}
Support/admin contact:
- Support admin: {support_admin_name()}
- Email: {support_admin_email()}
- Urgent phone: {support_admin_phone() or "not configured"}
Rules:
- English and French are the supported output languages.
- Do not mix output languages. The selected UI language is the single output language.
- User input may contain Tunisian Arabic, Arabizi transliteration, Arabic script, English or French. Understand it and answer in the selected UI output language.
- Be concise, practical, and focused on AI Studio Pro.
- You help with prompts, image generation, image-to-image, ComfyUI troubleshooting, credits, history, settings, and admin workflows.
- When debugging, ask for the exact backend log, browser Network response, and ComfyUI console error.
""".strip()


def backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


@router.get("/health")
async def assistant_health():
    return {
        "ok": True,
        "service": "assistant_en_fr_image_first",
        "code_version": ASSISTANT_CODE_VERSION,
        "output_languages": ["en", "fr"],
        "voice_output_languages": ["en", "fr"],
        "arabic_voice_enabled": False,
        "accepted_input_styles": ["en", "fr", "tunisian_arabizi", "tunisian_arabic_script"],
        "assistant_modules": ["audience_mirror", "launch_pack_brand_studio", "director_mode_prompt_doctor", "neural_camera_analysis"],
        "model_modes": ["auto", "fast", "advanced"],
        "model_policy": "dual_local_ollama_with_explicit_fallback",
    }


@router.get("/models")
async def assistant_models(current_user_id: int = Depends(get_current_user_id)):
    del current_user_id
    return (await ollama_runtime_status()).as_dict()


@router.post("/chat", response_model=AssistantChatResponse)
@limiter.limit("30/minute")
async def assistant_chat(
    request: Request,
    payload: AssistantChatRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    _ = current_user_id
    lang = resolve_lang(payload.lang, payload.message)
    if contains_unsupported_language(payload.message):
        return AssistantChatResponse(success=True, provider="language_guard", reply=unsupported_reply(lang))

    routed = route_app_question(payload.message, lang)
    if routed:
        return AssistantChatResponse(success=True, provider="app_knowledge", reply=routed)

    history = []
    for item in payload.messages[-8:]:
        if contains_unsupported_language(item.content):
            continue
        history.append({"role": item.role, "content": item.content})

    messages = [{"role": "system", "content": system_prompt(lang)}]
    if payload.page_context:
        messages.append({"role": "system", "content": f"Page context:\n{payload.page_context[:2000]}"})
    messages.extend(history)
    messages.append({"role": "user", "content": payload.message})

    if env_bool("ASSISTANT_USE_OLLAMA", True):
        result = await ollama_chat(messages, mode=payload.model_mode, feature="chat", timeout_seconds=90)
        if result.ok:
            return AssistantChatResponse(success=True, provider=result.provider, reply=clean_reply(result.content or "", lang))
        if env_bool("REQUIRE_OLLAMA", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Ollama assistant is required but unavailable: {result.error or 'unknown error'}",
            )
        return AssistantChatResponse(success=True, provider="local_fallback", reply=fallback_reply(payload.message, lang), error=result.error)

    return AssistantChatResponse(success=True, provider="local_fallback", reply=fallback_reply(payload.message, lang))


@router.post("/speech", response_model=AssistantSpeechResponse)
@limiter.limit("20/minute")
async def assistant_speech(
    request: Request,
    payload: AssistantSpeechRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    _ = current_user_id
    lang = resolve_lang(payload.lang, payload.text)
    if (payload.lang or "").lower().strip() not in {"en", "fr", "auto"} or contains_arabic_script(payload.text):
        return AssistantSpeechResponse(success=False, error="Voice output supports English and French text only. Arabic voice output is disabled.", lang=lang)

    if not env_bool("PIPER_ENABLED", False):
        return AssistantSpeechResponse(success=False, error="Server TTS is disabled by configuration. Browser speech synthesis fallback is supported in the frontend.", lang=lang)

    piper_exe = os.getenv("PIPER_EXE", "").strip()
    voice = os.getenv("PIPER_VOICE_FR" if lang == "fr" else "PIPER_VOICE_EN", "").strip()
    if not piper_exe or not voice:
        return AssistantSpeechResponse(success=False, error="Piper executable or voice file is not configured. Browser speech synthesis fallback is supported in the frontend.", lang=lang)

    audio_dir = backend_root() / "static" / "assistant_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    filename = f"assistant_{uuid.uuid4().hex}.wav"
    output_path = audio_dir / filename
    try:
        await asyncio.to_thread(
            subprocess.run,
            [piper_exe, "--model", voice, "--output_file", str(output_path)],
            input=payload.text.encode("utf-8"),
            check=True,
            timeout=60,
        )
    except Exception as exc:
        return AssistantSpeechResponse(success=False, error=f"Piper failed: {exc}", lang=lang)
    return AssistantSpeechResponse(success=True, audio_url=f"/assistant_audio/{filename}", lang=lang, voice=Path(voice).name)
