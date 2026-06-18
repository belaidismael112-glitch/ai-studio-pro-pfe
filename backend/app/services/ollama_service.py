"""Shared Ollama client and runtime diagnostics for local AI features.

The app uses a single Ollama server with selectable local models for text and
an optional local vision model for multimodal image understanding.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.core.config import settings


def _setting_or_env(name: str, default: Any = None) -> Any:
    env_value = os.getenv(name)
    if env_value not in {None, ""}:
        return env_value
    value = getattr(settings, name, None)
    if value not in {None, ""}:
        return value
    return default


def env_bool(name: str, default: bool = False) -> bool:
    value = _setting_or_env(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def ollama_base_url() -> str:
    return str(_setting_or_env("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")


def fast_model() -> str:
    return str(_setting_or_env("OLLAMA_FAST_MODEL", "llama3.2:3b")).strip() or "llama3.2:3b"


def advanced_model() -> str:
    return str(_setting_or_env("OLLAMA_ADVANCED_MODEL", "qwen2.5:7b")).strip() or "qwen2.5:7b"


def vision_model() -> str:
    return str(_setting_or_env("OLLAMA_VISION_MODEL", "llama3.2-vision:11b")).strip() or "llama3.2-vision:11b"


def default_mode() -> str:
    value = str(_setting_or_env("OLLAMA_DEFAULT_MODE", "auto")).strip().lower()
    return value if value in {"auto", "fast", "advanced"} else "auto"


def select_model(mode: str | None = None, *, feature: str = "chat", image_paths: list[str] | None = None) -> tuple[str, str]:
    if image_paths:
        return "vision", vision_model()
    selected = (mode or default_mode()).strip().lower()
    if selected not in {"auto", "fast", "advanced"}:
        selected = "auto"
    if selected == "auto":
        selected = "advanced" if feature in {
            "creative_director",
            "brand_studio",
            "audience_mirror",
            "platform_builder",
            "complex_chat",
            "image_understanding",
        } else "fast"
    return selected, advanced_model() if selected == "advanced" else fast_model()


def _model_names(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name:
            names.append(str(name))
    return names


def _matches_model(configured: str, installed: Iterable[str]) -> bool:
    configured = configured.strip()
    if not configured:
        return False
    aliases = {configured}
    if ":" not in configured:
        aliases.add(f"{configured}:latest")
    return any(name in aliases or name.split(":", 1)[0] == configured for name in installed)


@dataclass
class OllamaStatus:
    enabled: bool
    required: bool
    connected: bool
    url: str
    fast_model: str
    advanced_model: str
    installed_models: list[str]
    fast_model_ready: bool
    advanced_model_ready: bool
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.connected and self.fast_model_ready and self.advanced_model_ready

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "required": self.required,
            "connected": self.connected,
            "ready": self.ready,
            "url": self.url,
            "fast_model": self.fast_model,
            "advanced_model": self.advanced_model,
            "vision_model": vision_model(),
            "vision_enabled": env_bool("OLLAMA_VISION_ENABLED", True),
            "installed_models": self.installed_models,
            "fast_model_ready": self.fast_model_ready,
            "advanced_model_ready": self.advanced_model_ready,
            "vision_model_ready": _matches_model(vision_model(), self.installed_models),
            "error": self.error,
            "modes": ["auto", "fast", "advanced", "vision"],
        }


@dataclass
class OllamaChatResult:
    content: str | None
    model: str
    mode: str
    provider: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.content)


async def runtime_status(timeout_seconds: float = 4.0) -> OllamaStatus:
    enabled = env_bool("ASSISTANT_USE_OLLAMA", True)
    required = env_bool("REQUIRE_OLLAMA", False)
    base = ollama_base_url()
    fast = fast_model()
    advanced = advanced_model()
    if not enabled:
        return OllamaStatus(
            enabled=False,
            required=required,
            connected=False,
            url=base,
            fast_model=fast,
            advanced_model=advanced,
            installed_models=[],
            fast_model_ready=False,
            advanced_model_ready=False,
            error="Ollama integration is disabled by ASSISTANT_USE_OLLAMA=false.",
        )
    try:
        timeout = httpx.Timeout(timeout_seconds, connect=min(2.0, timeout_seconds))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base}/api/tags")
            response.raise_for_status()
            installed = _model_names(response.json())
        return OllamaStatus(
            enabled=True,
            required=required,
            connected=True,
            url=base,
            fast_model=fast,
            advanced_model=advanced,
            installed_models=installed,
            fast_model_ready=_matches_model(fast, installed),
            advanced_model_ready=_matches_model(advanced, installed),
        )
    except Exception as exc:
        return OllamaStatus(
            enabled=True,
            required=required,
            connected=False,
            url=base,
            fast_model=fast,
            advanced_model=advanced,
            installed_models=[],
            fast_model_ready=False,
            advanced_model_ready=False,
            error=str(exc)[:500],
        )


def _encode_image_for_ollama(image_path: str) -> str:
    data = Path(image_path).read_bytes()
    return base64.b64encode(data).decode("ascii")


async def chat(
    messages: list[dict[str, Any]],
    *,
    mode: str | None = None,
    feature: str = "chat",
    json_mode: bool = False,
    timeout_seconds: float = 90.0,
    image_paths: list[str] | None = None,
) -> OllamaChatResult:
    selected_mode, model = select_model(mode, feature=feature, image_paths=image_paths)
    if not env_bool("ASSISTANT_USE_OLLAMA", True):
        return OllamaChatResult(None, model, selected_mode, "ollama_disabled", "ASSISTANT_USE_OLLAMA=false")

    payload_messages: list[dict[str, Any]] = []
    for idx, message in enumerate(messages):
        item = dict(message)
        if image_paths and idx == len(messages) - 1:
            item["images"] = [_encode_image_for_ollama(path) for path in image_paths if path]
        payload_messages.append(item)

    payload: dict[str, Any] = {"model": model, "messages": payload_messages, "stream": False}
    if json_mode:
        payload["format"] = "json"
    try:
        timeout = httpx.Timeout(timeout_seconds, connect=8.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{ollama_base_url()}/api/chat", json=payload)
            response.raise_for_status()
            content = ((response.json().get("message") or {}).get("content") or "").strip()
        if not content:
            return OllamaChatResult(None, model, selected_mode, f"ollama:{model}", "Ollama returned an empty response.")
        return OllamaChatResult(content, model, selected_mode, f"ollama:{model}")
    except Exception as exc:
        return OllamaChatResult(None, model, selected_mode, f"ollama:{model}", str(exc)[:500])


def parse_json_object(text: str | None) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


async def json_chat(
    messages: list[dict[str, Any]],
    *,
    mode: str | None = "advanced",
    feature: str,
    timeout_seconds: float = 90.0,
    image_paths: list[str] | None = None,
) -> tuple[dict[str, Any] | None, OllamaChatResult]:
    result = await chat(
        messages,
        mode=mode,
        feature=feature,
        json_mode=True,
        timeout_seconds=timeout_seconds,
        image_paths=image_paths,
    )
    return parse_json_object(result.content), result
