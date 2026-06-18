from __future__ import annotations

import json
import os
import re
import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_token
from app.core.database import AsyncSessionLocal
from app.core import cache
from app.models.user import User
from app.models.generation import Generation
from app.services.credit_service import credit_service
from app.services.ollama_service import chat as ollama_chat, env_bool, parse_json_object

from app.schemas.ai_operator import (
    OperatorAction,
    OperatorActionStatus,
    OperatorActionType,
    OperatorConfirmRequest,
    OperatorExecutionEvent,
    OperatorExecutionResponse,
    OperatorPlanRequest,
    OperatorPlanResponse,
)

OPERATOR_USE_OLLAMA = os.getenv("OPERATOR_USE_OLLAMA", "true").lower() != "false"
APP_BASE_URL = os.getenv("APP_BASE_URL", os.getenv("BACKEND_PUBLIC_URL", "http://127.0.0.1:8000")).rstrip("/")

IMAGE_COST = int(settings.CREDIT_COST_IMAGE)
OPERATOR_SESSION_TTL_SECONDS = max(60, int(os.getenv("OPERATOR_SESSION_TTL_SECONDS", "900")))

ALLOWED_IMAGE_STYLES = {
    "photorealistic",
    "digital_art",
    "anime",
    "oil_painting",
    "watercolor",
    "sketch",
    "studio",
    "cinematic",
    "neonpunk",
    "fantasy",
    "3d",
}
STYLE_ALIASES = {
    "commercial": "cinematic",
    "premium": "cinematic",
    "luxury": "studio",
    "clean": "studio",
    "minimal": "studio",
    "realistic": "photorealistic",
    "photo": "photorealistic",
    "photography": "photorealistic",
    "illustration": "digital_art",
    "digital": "digital_art",
    "3d_render": "3d",
    "3d_rendering": "3d",
    "3_d": "3d",
    "three_d": "3d",
    "minimalist": "studio",
    "corporate": "studio",
    "editorial": "cinematic",
}

ALLOWED_OPERATOR_MODES = {"chat", "image", "video", "image_video"}
MODE_ALIASES = {
    "generate_image": "image",
    "image_generation": "image",
    "text_to_image": "image",
    "text2image": "image",
    "text2img": "image",
    "img": "image",
    "photo": "image",
    "poster": "image",
    "design": "image",
    "generate_video": "video",
    "video_generation": "video",
    "text_to_video": "video",
    "text2video": "video",
    "text2vid": "video",
}

MAX_OPERATOR_PROMPT_CHARS = 1900
MAX_OPERATOR_NEGATIVE_PROMPT_CHARS = 900


@dataclass
class OperatorSession:
    session_id: str
    user_id: int
    request: OperatorPlanRequest
    response: OperatorPlanResponse
    approved: bool = False
    consumed: bool = False
    cancelled: bool = False
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AIStudioOperatorService:
    def __init__(self) -> None:
        self._sessions: Dict[str, OperatorSession] = {}

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"operator:session:{session_id}"

    def _cleanup_sessions(self) -> None:
        now = time.time()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.created_at > OPERATOR_SESSION_TTL_SECONDS
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    async def _save_session(self, session: OperatorSession) -> None:
        self._sessions[session.session_id] = session
        await cache.set_json(
            self._session_key(session.session_id),
            {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "request": session.request.model_dump(mode="json"),
                "response": session.response.model_dump(mode="json"),
                "approved": session.approved,
                "consumed": session.consumed,
                "cancelled": session.cancelled,
                "created_at": session.created_at,
                "metadata": session.metadata,
            },
            ttl_seconds=OPERATOR_SESSION_TTL_SECONDS,
        )

    async def _load_session(self, session_id: str) -> OperatorSession | None:
        session = self._sessions.get(session_id)
        if session:
            return session
        data = await cache.get_json(self._session_key(session_id))
        if not isinstance(data, dict):
            return None
        try:
            session = OperatorSession(
                session_id=str(data["session_id"]),
                user_id=int(data["user_id"]),
                request=OperatorPlanRequest.model_validate(data["request"]),
                response=OperatorPlanResponse.model_validate(data["response"]),
                approved=bool(data.get("approved", False)),
                consumed=bool(data.get("consumed", False)),
                cancelled=bool(data.get("cancelled", False)),
                created_at=float(data.get("created_at") or time.time()),
                metadata=dict(data.get("metadata") or {}),
            )
        except Exception:
            return None
        self._sessions[session_id] = session
        return session

    async def _delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        await cache.delete_key(self._session_key(session_id))

    @staticmethod
    def _confirm_lock_key(session_id: str) -> str:
        return f"operator:confirm-lock:{session_id}"

    async def _available_credits(self, user_id: int) -> int | None:
        """Return the current wallet balance when the database is reachable."""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User.credits).where(User.id == user_id, User.is_active.is_(True)))
                value = result.scalar_one_or_none()
                return int(value) if value is not None else None
        except Exception:
            return None

    async def create_plan(self, request: OperatorPlanRequest, *, user_id: int) -> OperatorPlanResponse:
        self._cleanup_sessions()
        session_id = str(uuid.uuid4())
        command = request.command.strip()
        available_credits = await self._available_credits(user_id)

        context = request.context or {}
        force_mode = str(context.get("force_mode") or "").strip().lower()
        direct_payload = context.get("direct_payload") if isinstance(context.get("direct_payload"), dict) else None

        # Smart Agent can ask the Operator to execute an already-approved tool
        # while preserving the exact prompt/settings prepared by Director Mode,
        # Brand Studio, Audience Mirror, Neural Camera Analysis, or voice input. Ollama is
        # still used for natural-language commands when force_mode is absent.
        if force_mode in {"image", "video", "image_video"} and direct_payload:
            safe_direct_payload = self._sanitize_image_payload(direct_payload, command)
            intent = {
                "mode": "image",
                "answer": None,
                "image_prompt": safe_direct_payload.get("prompt") or command,
                "style": safe_direct_payload.get("style") or "cinematic",
                "direct_payload": safe_direct_payload,
            }
        else:
            intent = await self._detect_intent(command, request)
            if intent.get("style"):
                intent["style"] = self._normalize_style(intent.get("style"))

        mode = self._normalize_mode(intent.get("mode", "chat"), command)
        intent["mode"] = mode
        # V15 production policy: operator is image-first. Any old video intent is
        # converted to a still-image plan instead of queueing a disabled route.
        if mode in {"video", "image_video"}:
            mode = "image" if request.allow_image else "chat"
            intent["answer"] = "Video generation is disabled in this build. I prepared an image-first alternative."
        if mode == "image" and not request.allow_image:
            mode = "chat"
            intent["answer"] = "Image actions are disabled. Enable 'Allow image actions' and run the operator again."

        actions: List[OperatorAction] = []
        actions.append(OperatorAction(
            id="understand-command",
            type=OperatorActionType.improve_prompt,
            title="Understand command",
            description="Analyze the request with the Ollama intent router. Deterministic fallback is development-only.",
            credits_cost=0,
            requires_confirmation=False,
            payload={"mode": mode, "command": command},
        ))

        actions.append(OperatorAction(
            id="check-credits",
            type=OperatorActionType.check_credits,
            title="Check available credits",
            description="Verify that the requested generation stays inside the selected budget.",
            credits_cost=0,
            requires_confirmation=False,
            payload={"max_credits": request.max_credits, "available_credits": available_credits},
        ))

        direct_payload = intent.get("direct_payload") if isinstance(intent.get("direct_payload"), dict) else None
        image_payload = direct_payload if mode == "image" and direct_payload else self._image_payload(intent, command)

        if mode == "image":
            actions.append(OperatorAction(
                id="generate-image",
                type=OperatorActionType.generate_image,
                title="Generate image",
                description="Send a real request to POST /api/v1/generations/images after approval.",
                credits_cost=IMAGE_COST,
                requires_confirmation=True,
                status=OperatorActionStatus.waiting_confirmation,
                payload=image_payload,
            ))



        actions.append(OperatorAction(
            id="save-history",
            type=OperatorActionType.save_history,
            title="Save generation history",
            description="Generated jobs are saved by the existing generation system and visible in History.",
            credits_cost=0,
            requires_confirmation=False,
        ))

        total_credits = sum(action.credits_cost for action in actions)
        max_credits = request.max_credits if request.max_credits is not None else total_credits
        if total_credits > max_credits and total_credits > 0:
            actions = [a for a in actions if a.type != OperatorActionType.generate_image]
            total_credits = sum(action.credits_cost for action in actions)
            mode = "chat"
            intent["answer"] = "The requested generation exceeds the selected credit budget. Increase the budget or simplify the request."

        if available_credits is not None and total_credits > available_credits and total_credits > 0:
            actions = [a for a in actions if a.type != OperatorActionType.generate_image]
            total_credits = sum(action.credits_cost for action in actions)
            mode = "chat"
            intent["answer"] = f"Insufficient credits. Available balance: {available_credits}. Add credits before launching generation."

        requires_confirmation = any(action.requires_confirmation for action in actions)
        assistant_message = self._assistant_message(mode, intent, total_credits)

        response = OperatorPlanResponse(
            session_id=session_id,
            title=self._title(command),
            summary=self._summary(mode, intent),
            total_estimated_credits=total_credits,
            requires_confirmation=requires_confirmation,
            actions=actions,
            assistant_message=assistant_message,
            cursor_script=self._plan_cursor_script(mode),
        )
        await self._save_session(OperatorSession(session_id=session_id, user_id=user_id, request=request, response=response, metadata={"intent": intent, "mode": mode}))
        return response

    async def confirm(self, request: OperatorConfirmRequest, *, user_id: int, auth_header: Optional[str] = None) -> OperatorExecutionResponse:
        self._cleanup_sessions()
        lock_key = self._confirm_lock_key(request.session_id)
        lock_token = await cache.acquire_lock(lock_key, ttl_seconds=120)
        if not lock_token:
            return OperatorExecutionResponse(
                session_id=request.session_id,
                approved=False,
                message="This operator plan is already being processed. Wait for the existing execution result.",
                events=[],
                final_result={"error": "operator_confirmation_in_progress"},
            )
        try:
            return await self._confirm_locked(request, user_id=user_id, auth_header=auth_header)
        finally:
            await cache.release_lock(lock_key, lock_token)

    async def _confirm_locked(self, request: OperatorConfirmRequest, *, user_id: int, auth_header: Optional[str] = None) -> OperatorExecutionResponse:
        session = await self._load_session(request.session_id)
        if not session:
            return OperatorExecutionResponse(
                session_id=request.session_id,
                approved=False,
                message="Session not found or expired. Please create a new operator plan.",
                events=[],
                final_result={"error": "session_not_found_or_expired"},
            )

        if session.user_id != user_id:
            return OperatorExecutionResponse(
                session_id=request.session_id,
                approved=False,
                message="This operator plan belongs to another user.",
                events=[],
                final_result={"error": "operator_session_owner_mismatch"},
            )

        if session.consumed or session.cancelled:
            return OperatorExecutionResponse(
                session_id=request.session_id,
                approved=False,
                message="This operator plan has already been used. Create a new plan before running another generation.",
                events=[],
                final_result={"error": "session_already_used"},
            )

        if not request.approved:
            session.cancelled = True
            await self._delete_session(request.session_id)
            return OperatorExecutionResponse(
                session_id=request.session_id,
                approved=False,
                message="Execution cancelled. No credits were spent.",
                events=[OperatorExecutionEvent(
                    id="cancelled",
                    kind="system",
                    title="Cancelled",
                    message="The operator stopped before launching generation.",
                    status=OperatorActionStatus.skipped,
                    progress=100,
                    cursor_target={"x": 50, "y": 78},
                )],
                final_result={"cancelled": True},
            )

        # Consume the plan before any await that could queue a job. This makes
        # approval idempotent and prevents accidental double-click credit spend.
        session.approved = True
        session.consumed = True
        await self._save_session(session)
        events: List[OperatorExecutionEvent] = []
        final_result: Dict[str, Any] = {"generations": []}

        events.append(OperatorExecutionEvent(
            id="exec-read",
            kind="analysis",
            title="Reading user command",
            message="The operator extracted intent, prompt, output type, and safety constraints.",
            status=OperatorActionStatus.completed,
            progress=12,
            cursor_target={"x": 18, "y": 24},
        ))
        events.append(OperatorExecutionEvent(
            id="exec-credits",
            kind="credits",
            title="Checking credits",
            message=f"Estimated cost: {session.response.total_estimated_credits} credits. Real credit deduction happens inside the existing generation endpoint.",
            status=OperatorActionStatus.completed,
            progress=25,
            cursor_target={"x": 58, "y": 42},
        ))

        for action in session.response.actions:
            if action.requires_confirmation:
                action.status = OperatorActionStatus.approved

        headers: Dict[str, str] = {}
        if auth_header:
            headers["Authorization"] = auth_header

        queued_ok = False
        if any(a.type == OperatorActionType.generate_image for a in session.response.actions):
            action = next(a for a in session.response.actions if a.type == OperatorActionType.generate_image)
            data, ok, message = await self._post_existing_endpoint("/api/v1/generations/images", action.payload, headers, expected_user_id=session.user_id)
            queued_ok = ok
            status_value = OperatorActionStatus.completed if ok else OperatorActionStatus.failed
            final_result.setdefault("images", []).append(data)
            if ok:
                final_result["generations"].append(data)
            events.append(OperatorExecutionEvent(
                id="exec-image",
                kind="image",
                title="Image generation queued" if ok else "Image generation failed",
                message=message,
                status=status_value,
                progress=58,
                cursor_target={"x": 70, "y": 52},
                data={"endpoint": "/api/v1/generations/images", "response": data},
            ))

        expected_generation = session.response.total_estimated_credits > 0
        if queued_ok:
            done_message = "Real backend image generation has been queued. Watch the live preview or open History."
            done_status = OperatorActionStatus.completed
        elif expected_generation:
            done_message = "The operator could not queue generation. Check the failed event details."
            done_status = OperatorActionStatus.failed
        else:
            done_message = "No credit-spending generation was required for this request."
            done_status = OperatorActionStatus.completed

        events.append(OperatorExecutionEvent(
            id="exec-done",
            kind="done",
            title="Operator workflow completed" if done_status == OperatorActionStatus.completed else "Operator workflow failed",
            message=done_message,
            status=done_status,
            progress=100,
            cursor_target={"x": 50, "y": 82},
            data=final_result,
        ))

        await self._delete_session(request.session_id)
        success = done_status == OperatorActionStatus.completed
        return OperatorExecutionResponse(
            session_id=request.session_id,
            approved=success,
            message="Approved. The operator executed the backend workflow." if success else "Approved, but the backend generation could not be queued.",
            events=events,
            final_result=final_result,
        )

    async def _post_existing_endpoint(self, endpoint: str, payload: Dict[str, Any], headers: Dict[str, str], *, expected_user_id: int | None = None) -> Tuple[Dict[str, Any], bool, str]:
        """Queue generation reliably.

        Production fix: the old operator called the backend through APP_BASE_URL.
        That fails when the backend is behind a proxy, running inside Docker, or when
        localhost points to the wrong container. For the image endpoint, queue the
        same Generation record internally and only fall back to HTTP if auth is missing.
        """
        if endpoint == "/api/v1/generations/images":
            internal = await self._queue_generation_internal(endpoint, payload, headers, expected_user_id=expected_user_id)
            if internal is not None:
                return internal

        try:
            async with httpx.AsyncClient(base_url=APP_BASE_URL, timeout=600, headers=headers) as client:
                response = await client.post(endpoint, json=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text}
            if response.status_code >= 400:
                return data, False, f"Backend returned HTTP {response.status_code}: {data}"
            gen_id = data.get("id") or data.get("generation_id")
            return data, True, f"Queued successfully. Generation ID: {gen_id}. Credits are deducted by the generation endpoint."
        except Exception as exc:
            return {"error": str(exc)}, False, f"Could not call {endpoint}: {exc}"

    async def _queue_generation_internal(self, endpoint: str, payload: Dict[str, Any], headers: Dict[str, str], *, expected_user_id: int | None = None) -> Optional[Tuple[Dict[str, Any], bool, str]]:
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return ({"error": "auth_required"}, False, "Sign in before approving an Operator generation.")

        token_payload = decode_token(auth.split(" ", 1)[1].strip())
        if not token_payload or token_payload.get("type") != "access" or token_payload.get("sub") is None:
            return ({"error": "invalid_auth"}, False, "Operator could not verify the current user token.")

        try:
            user_id = int(token_payload["sub"])
        except (TypeError, ValueError):
            return ({"error": "invalid_auth"}, False, "Operator token user id is invalid.")
        if expected_user_id is not None and user_id != expected_user_id:
            return ({"error": "operator_session_owner_mismatch"}, False, "Operator plan owner does not match the current access token.")

        from app.api.v1.endpoints.generations import (
            _image_effective_dimensions,
            _enqueue_or_refund,
            _validate_or_422,
            _prompt_requires_reference_image,
            _raise_reference_required_for_text2img,
            _enforce_source_lock_prompt_gate,
        )
        from app.schemas.generation import GenerationResponse

        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return ({"error": "empty_prompt"}, False, "Operator prompt is empty.")

        try:
            _validate_or_422(prompt)
            if _prompt_requires_reference_image(prompt):
                _raise_reference_required_for_text2img("/api/v1/generations/image/img2img")
            _enforce_source_lock_prompt_gate(prompt, subject_lock=False)
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            return ({"error": detail}, False, f"Prompt validation failed: {detail}")

        if endpoint != "/api/v1/generations/images":
            return ({"error": "unsupported_operator_endpoint"}, False, "Operator supports image generation only in this build.")
        cost = settings.CREDIT_COST_IMAGE

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.is_active:
                return ({"error": "inactive_user"}, False, "Current user is inactive or missing.")

            has_credits = await credit_service.has_sufficient_credits(db, user_id, cost)
            if not has_credits:
                return ({"error": "insufficient_credits"}, False, "Insufficient credits. Please purchase more credits.")

            width, height = _image_effective_dimensions(self._safe_dimension(payload.get("width"), 640), self._safe_dimension(payload.get("height"), 896))
            generation = Generation(
                user_id=user_id,
                generation_type="image",
                prompt=prompt,
                negative_prompt=str(payload.get("negative_prompt") or ""),
                width=width,
                height=height,
                style=payload.get("style") or None,
                status="queued",
                credits_used=cost,
                model_used=payload.get("model_id") or "sdxl",
            )

            db.add(generation)
            await db.flush()

            tx = await credit_service.deduct_credits(
                db,
                user_id,
                cost,
                description=f"Operator {generation.generation_type} generation #{generation.id}",
                generation_id=generation.id,
            )
            if tx is None:
                await db.rollback()
                return ({"error": "insufficient_credits"}, False, "Insufficient credits. Please purchase more credits.")

            await db.commit()
            await db.refresh(generation)

            try:
                await _enqueue_or_refund(db, generation)
            except Exception as exc:
                detail = getattr(exc, "detail", str(exc))
                return ({"error": "queue_unavailable", "detail": detail}, False, str(detail))
            await db.refresh(generation)

            data = GenerationResponse.model_validate(generation).model_dump(mode="json")
            return data, True, f"Queued successfully. Generation ID: {generation.id}. Credits were deducted by the generation system."

    async def _detect_intent(self, command: str, request: OperatorPlanRequest) -> Dict[str, Any]:
        fallback = self._fallback_intent(command)
        use_ollama = env_bool("OPERATOR_USE_OLLAMA", OPERATOR_USE_OLLAMA)
        require_ollama = env_bool("REQUIRE_OLLAMA", False)
        if not use_ollama:
            if require_ollama:
                raise HTTPException(
                    status_code=503,
                    detail="Operator requires Ollama in production, but OPERATOR_USE_OLLAMA is disabled.",
                )
            return fallback
        system = (
            "You are AI Studio Operator for an image-first SaaS. "
            "Return JSON only with keys: mode, answer, image_prompt, style. "
            "mode must be one of: chat, image. "
            "style must be one of: photorealistic, digital_art, anime, oil_painting, watercolor, sketch, studio, cinematic, neonpunk, fantasy, 3d. "
            "Do not require the word generate. Poster, image, visual, ad, design, affiche and visuel requests => image. "
            "Video, reel, animation, motion or clip requests must be converted into a strong still-image alternative. "
            "Normal questions, app help, debugging, settings explanations and opinions are chat. "
            "Respect requested image orientation or resolution when present."
        )
        user = f"Brand: {request.brand_name or 'AI Studio Pro'}\nCommand: {command}"
        try:
            result = await ollama_chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                mode="fast",
                feature="operator_intent",
                json_mode=True,
                timeout_seconds=45,
            )
            parsed = parse_json_object(result.content) or {}
            if not result.ok or not parsed:
                if require_ollama:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Operator Ollama intent router is unavailable: {result.error or 'invalid or empty Ollama response'}",
                    )
                return fallback
            return {**fallback, **parsed}
        except HTTPException:
            raise
        except Exception as exc:
            if require_ollama:
                raise HTTPException(
                    status_code=503,
                    detail=f"Operator Ollama intent router is unavailable: {exc}",
                ) from exc
            return fallback

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return {}
        return json.loads(match.group(0))

    @staticmethod
    def _contains_word(text: str, word: str) -> bool:
        token = re.escape(word.lower())
        return bool(re.search(rf"(?<![a-z0-9_]){token}(?![a-z0-9_])", text.lower()))

    @classmethod
    def _fallback_intent(cls, command: str) -> Dict[str, Any]:
        c = command.lower()
        latin_words = [
            "image", "photo", "picture", "poster", "visual", "design", "affiche", "visuel", "campaign",
            "ad", "advert", "pub", "video", "vidéo", "reel", "animation", "animate", "motion", "clip",
            # Tunisian / Arabic transliteration used frequently by local users.
            "taswira", "tswira", "sawer", "sawwar", "sawerly", "aamel", "a3mel", "amel", "sammem", "samem",
        ]
        arabic_markers = ["صورة", "تصويرة", "اعمل", "اعمللي", "أعمل", "صمم", "بوستر", "إعلان", "اعلان"]
        image_like = any(cls._contains_word(c, w) for w in latin_words) or any(w in c for w in arabic_markers)
        mode = "image" if image_like else "chat"
        return {
            "mode": mode,
            "answer": "I can help with image generation or image-to-image workflows." if mode == "chat" else None,
            "image_prompt": cls._safe_prompt(f"premium cinematic visual, {command}, professional lighting, sharp details, commercial advertising style"),
            "style": "cinematic",
        }

    @classmethod
    def _normalize_mode(cls, value: Any, command: str = "") -> str:
        raw = str(value or "chat").strip().lower().replace("-", "_").replace(" ", "_")
        raw = MODE_ALIASES.get(raw, raw)
        if raw in ALLOWED_OPERATOR_MODES:
            return raw
        return str(cls._fallback_intent(command).get("mode") or "chat")

    @staticmethod
    def _safe_prompt(value: Any, default: str = "premium cinematic commercial image", *, max_chars: int = MAX_OPERATOR_PROMPT_CHARS) -> str:
        text = re.sub(r"\s+", " ", str(value or default)).strip()
        if not text:
            text = default
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0].rstrip() or text[:max_chars].rstrip()
        return text


    @staticmethod
    def _normalize_style(value: Any) -> str:
        raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        raw = STYLE_ALIASES.get(raw, raw)
        return raw if raw in ALLOWED_IMAGE_STYLES else "cinematic"

    @staticmethod
    def _safe_dimension(value: Any, default: int) -> int:
        try:
            number = int(value)
        except Exception:
            number = default
        return max(256, min(2048, number))

    @staticmethod
    def _safe_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except Exception:
            number = default
        return max(minimum, min(maximum, number))

    @staticmethod
    def _safe_float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except Exception:
            number = default
        return max(minimum, min(maximum, number))

    @classmethod
    def _sanitize_image_payload(cls, payload: Dict[str, Any], command: str) -> Dict[str, Any]:
        settings = cls._infer_image_settings(command)
        prompt = cls._safe_prompt(payload.get("prompt") or command, command.strip() or "premium cinematic commercial image")
        safe = {
            "prompt": prompt,
            "negative_prompt": cls._safe_prompt(payload.get("negative_prompt") or "low quality, blurry, distorted, watermark, unreadable text, artifacts, bad anatomy", "low quality, blurry, distorted, watermark, unreadable text, artifacts, bad anatomy", max_chars=MAX_OPERATOR_NEGATIVE_PROMPT_CHARS),
            "width": cls._safe_dimension(payload.get("width"), settings["width"]),
            "height": cls._safe_dimension(payload.get("height"), settings["height"]),
            "style": cls._normalize_style(payload.get("style") or settings["style"]),
            "num_inference_steps": cls._safe_int(payload.get("num_inference_steps"), 24, minimum=10, maximum=100),
            "guidance_scale": cls._safe_float(payload.get("guidance_scale"), 7.0, minimum=1.0, maximum=20.0),
            "model_id": str(payload.get("model_id") or "comfy-flux"),
        }
        return safe


    @staticmethod
    def _infer_image_settings(command: str) -> Dict[str, Any]:
        c = command.lower()
        width, height = 640, 896
        if any(w in c for w in ["square", "carré", "carre"]):
            width, height = 1024, 1024
        elif any(w in c for w in ["landscape", "horizontal", "paysage", "hd"]):
            width, height = 1024, 576
        elif any(w in c for w in ["portrait", "vertical", "story", "reel", "reels"]):
            width, height = 576, 1024

        style = "photorealistic"
        if any(w in c for w in ["digital", "illustration", "art"]):
            style = "digital_art"
        elif any(w in c for w in ["cinematic", "cinema", "cinéma", "film"]):
            style = "cinematic"
        return {"width": width, "height": height, "style": style}



    @staticmethod
    def _image_payload(intent: Dict[str, Any], command: str) -> Dict[str, Any]:
        prompt = AIStudioOperatorService._safe_prompt(intent.get("image_prompt") or f"premium cinematic image, {command}")
        settings = AIStudioOperatorService._infer_image_settings(command)
        return {
            "prompt": prompt,
            "negative_prompt": AIStudioOperatorService._safe_prompt("low quality, blurry, distorted, watermark, unreadable text, artifacts, bad anatomy", max_chars=MAX_OPERATOR_NEGATIVE_PROMPT_CHARS),
            "width": settings["width"],
            "height": settings["height"],
            "style": AIStudioOperatorService._normalize_style(intent.get("style") or settings["style"]),
            "num_inference_steps": 24,
            "guidance_scale": 7.0,
            "model_id": "comfy-flux",
        }



    @staticmethod
    def _title(command: str) -> str:
        cleaned = re.sub(r"\s+", " ", command).strip()
        return cleaned if len(cleaned) <= 55 else cleaned[:52].rstrip() + "..."

    @staticmethod
    def _summary(mode: str, intent: Dict[str, Any]) -> str:
        if mode == "chat":
            return "The operator detected a chat/help request and will answer without spending credits."
        if mode == "image":
            return "The operator will generate one image through the existing backend generation queue."
        return "The operator will generate one image through the existing backend generation queue."

    @staticmethod
    def _assistant_message(mode: str, intent: Dict[str, Any], total_credits: int) -> str:
        if mode == "chat":
            return str(intent.get("answer") or "I answered this as a chat request. No credits will be spent.")
        return f"I prepared a real generation plan. Estimated cost: {total_credits} credits. After approval, I will queue the real backend generation and show live progress."

    @staticmethod
    def _plan_cursor_script(mode: str) -> List[Dict[str, Any]]:
        script = [
            {"x": 18, "y": 24, "label": "Reading command"},
            {"x": 36, "y": 39, "label": "Building plan"},
            {"x": 58, "y": 42, "label": "Checking credits"},
        ]
        if mode == "image":
            script.append({"x": 70, "y": 52, "label": "Image workflow"})
        script.append({"x": 50, "y": 82, "label": "Waiting approval"})
        return script


operator_service = AIStudioOperatorService()
