"""Application configuration

This file is a DROP-IN replacement for your existing app/core/config.py.
Only additions:
- INITIAL_ADMIN_* (initial admin seed)
- SMTP_* settings (optional)
- COMFY_CHECKPOINT (optional)
"""

from typing import List, Optional, Literal
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AI Studio Pro"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str  # REQUIRED: set in .env

    # AI provider
    AI_PROVIDER: Literal["replicate", "comfy"] = "replicate"

    # Local Ollama assistant / workflow planner
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_FAST_MODEL: str = "llama3.2:3b"
    OLLAMA_ADVANCED_MODEL: str = "qwen2.5:7b"
    OLLAMA_DEFAULT_MODE: Literal["auto", "fast", "advanced"] = "auto"
    OLLAMA_VISION_ENABLED: bool = True
    OLLAMA_VISION_MODEL: str = "qwen2.5vl:3b"
    OLLAMA_VISION_TIMEOUT_SECONDS: int = 120
    ASSISTANT_USE_OLLAMA: bool = True
    REQUIRE_OLLAMA: bool = False
    OPERATOR_USE_OLLAMA: bool = True
    AUTONOMOUS_PLATFORM_USE_OLLAMA: bool = True
    COMFY_URL: str = "http://127.0.0.1:8188"
    COMFY_CHECKPOINT: str = "v1-5-pruned-emaonly.safetensors"

    # Backend public URL for generated assets
    BACKEND_PUBLIC_URL: str = "http://127.0.0.1:8000"

    # ComfyUI strict production/local workflow settings
    COMFY_IMAGE_CHECKPOINT: str = "flux1-schnell-fp8.safetensors"
    COMFY_LTXV_CHECKPOINT: str = "ltx-video-2b-v0.9.safetensors"
    COMFY_VIDEO_CHECKPOINT: str = "ltx-video-2b-v0.9.safetensors"
    COMFY_LTXV_CLIP: str = "t5xxl_fp8_e4m3fn.safetensors"
    COMFY_STRICT_WORKFLOW_MODE: bool = True
    COMFY_USE_PROMPT_ENGINE: bool = False
    COMFY_RANDOM_SEED: bool = True
    COMFY_IMAGE_DEFAULT_WIDTH: int = 640
    COMFY_IMAGE_DEFAULT_HEIGHT: int = 896
    COMFY_IMAGE_STEPS: int = 8
    COMFY_IMAGE_CFG: float = 1.0
    COMFY_IMAGE_SAMPLER: str = "euler"
    COMFY_IMAGE_SCHEDULER: str = "simple"
    # Maximum frames allowed when the UI duration is converted to LTXV latent frames.
    # 385 supports 16s at 24fps rounded to 8n+1; lower this in production if your GPU is smaller.
    COMFY_LTXV_MAX_FRAMES: int = 385
    COMFY_LTXV_MIN_FRAMES: int = 25
    COMFY_LTXV_FPS: int = 25
    COMFY_LTXV_OUTPUT_FPS: int = 24
    COMFY_LTXV_STEPS: int = 20
    COMFY_LTXV_CFG: float = 3.0
    COMFY_LTXV_SAMPLER: str = "euler"
    COMFY_LTXV_MAX_SHIFT: float = 2.05
    COMFY_LTXV_BASE_SHIFT: float = 0.95
    COMFY_LTXV_TERMINAL: float = 0.1
    COMFY_LTXV_LANDSCAPE_WIDTH: int = 768
    COMFY_LTXV_LANDSCAPE_HEIGHT: int = 448
    COMFY_LTXV_SQUARE_WIDTH: int = 512
    COMFY_LTXV_SQUARE_HEIGHT: int = 512
    COMFY_LTXV_PORTRAIT_WIDTH: int = 448
    COMFY_LTXV_PORTRAIT_HEIGHT: int = 704
    COMFY_VIDEO_CRF: int = 16
    COMFY_IMAGE_TIMEOUT_SECONDS: int = 900
    COMFY_VIDEO_TIMEOUT_SECONDS: int = 1800

    # Stability
    STABILITY_API_KEY: Optional[str] = None
    STABILITY_BASE_URL: str = "https://api.stability.ai"

    # Database
    DATABASE_URL: str = "sqlite:///./ai_studio.db"

    # JWT
    JWT_SECRET_KEY: str  # REQUIRED: set in .env
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "ai-studio-pro"
    JWT_AUDIENCE: str = "ai-studio-pro"
    JWT_LEEWAY_SECONDS: int = 30
    TOKEN_BLACKLIST_PREFIX: str = "blacklist:jti"
    REFRESH_ALLOWLIST_PREFIX: str = "allowlist:refresh"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Security headers / CORS
    ENABLE_SECURITY_HEADERS: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Frontend / local checkout helpers
    FRONTEND_PUBLIC_URL: str = "http://localhost:3000"
    LOCAL_CREDIT_PURCHASE_ENABLED: bool = False
    # Fail local production acceptance on suspicious legacy/debug balances until reviewed.
    DATA_HEALTH_MAX_CREDITS_WITHOUT_REVIEW: int = 100000
    ALLOW_HIGH_LEGACY_CREDITS: bool = False

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_STARTER: Optional[str] = None
    STRIPE_PRICE_PRO: Optional[str] = None
    STRIPE_PRICE_ENTERPRISE: Optional[str] = None

    # AI APIs
    REPLICATE_API_TOKEN: Optional[str] = None
    RUNWAY_API_KEY: Optional[str] = None
    FAL_KEY: Optional[str] = None

    # Object storage (AWS S3 / Cloudflare R2 / MinIO)
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None
    S3_REGION: str = "us-east-1"
    SIGNED_URL_EXPIRE_SECONDS: int = 3600

    # Redis / Celery (queue)
    REDIS_URL: str = "redis://localhost:6379/0"
    REQUIRE_REDIS: bool = False
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # Desktop updates
    LATEST_DESKTOP_VERSION: str = "1.0.0"
    DESKTOP_UPDATE_URL: Optional[str] = None

    # Monitoring (optional)
    SENTRY_DSN: Optional[str] = None

    # Credit costs
    CREDIT_COST_IMAGE: int = 10
    CREDIT_COST_VIDEO: int = 50
    CREDIT_COST_VIDEO_PER_SECOND: int = 10

    # Upload safety
    MAX_UPLOAD_MB: int = 15
    MAX_IMAGE_DIMENSION: int = 8192
    MAX_IMAGE_PIXELS: int = 40000000

    # Prompt safety/quality
    PROMPT_MAX_CHARS: int = 600
    PROMPT_MIN_WORDS_FOR_BOOST: int = 4

    # Provider HTTP resilience
    AI_HTTP_MAX_RETRIES: int = 3
    AI_HTTP_RETRY_BACKOFF: float = 0.8

    # Reject near-copy outputs for modes that promise visible transformation.
    # Person / Identity is intentionally excluded because conservative edits are valid.
    REFERENCE_MIN_VISUAL_DELTA_PRODUCT_AD: float = 0.075
    REFERENCE_MIN_VISUAL_DELTA_FLYER_POSTER: float = 0.060
    REFERENCE_MIN_VISUAL_DELTA_BACKGROUND_REPLACE: float = 0.055
    REFERENCE_MIN_VISUAL_DELTA_CREATIVE_IMAGE: float = 0.070
    COMFY_IMG2IMG_RETRY_ON_NEAR_COPY: bool = True
    REFERENCE_ALLOW_NEAR_COPY_BEST_EFFORT: bool = True
    # Vision-directed commercial composition
    VISION_PROMPT_DIRECTOR_ENABLED: bool = True
    COMMERCIAL_ALLOW_AI_BACKDROP_FOR_SAFE_MODES: bool = True
    COMMERCIAL_ENABLE_DETERMINISTIC_FALLBACK: bool = False
    COMMERCIAL_DRAW_SOURCE_LOCK_PODIUM: bool = False
    COMMERCIAL_ADD_DECORATIVE_GEOMETRY: bool = False
    COMMERCIAL_SUBJECT_GLOW_ENABLED: bool = False
    COMMERCIAL_SANITIZE_AI_HERO_ZONE: bool = False
    COMFY_REFERENCE_TRANSFORM_STEPS: int = 12
    COMFY_REFERENCE_TRANSFORM_CFG: float = 1.2

    ALLOWED_IMAGE_MIME: List[str] = ["image/png", "image/jpeg", "image/webp"]

    # Free trial credits
    FREE_TRIAL_CREDITS: int = 100

    # -------- Admin seed (optional) --------
    INITIAL_ADMIN_EMAIL: Optional[str] = None
    INITIAL_ADMIN_PASSWORD: Optional[str] = None
    INITIAL_ADMIN_FULL_NAME: Optional[str] = None

    INITIAL_ADMIN_EMAIL_2: Optional[str] = None
    INITIAL_ADMIN_PASSWORD_2: Optional[str] = None
    INITIAL_ADMIN_FULL_NAME_2: Optional[str] = None

    # -------- SMTP email (optional) --------
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False

    def model_post_init(self, __context) -> None:
        # Default Celery broker/backend to REDIS_URL if not provided
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL


settings = Settings()