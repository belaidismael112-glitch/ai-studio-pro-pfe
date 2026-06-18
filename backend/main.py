"""
AI Studio Pro - Backend API
FastAPI application with authentication, credits system, and AI generation
"""

from contextlib import asynccontextmanager
from pathlib import Path
import logging

# Make local .env values visible to helpers that read os.getenv directly.
# Pydantic settings still remains the source of truth if python-dotenv is absent.
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"), override=False)
except Exception:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import engine, Base, ensure_schema_compatibility
from app.api.v1.router import api_router
from app.core.logging_config import setup_logging
from app.services.admin_seed import ensure_initial_admins
from app.core.rate_limit import limiter
from app.core import cache
from app.api.routes.assistant import router as assistant_router
from app.api.routes.assistant_vision import router as assistant_vision_router
from app.api.routes.assistant_creative import router as assistant_creative_router
from app.api.routes.assistant_brand import router as assistant_brand_router
from app.api.routes.assistant_audience import router as assistant_audience_router
from app.api.routes.ai_operator import router as ai_operator_router
from app.api.routes.autonomous_platform import router as autonomous_platform_router


setup_logging()
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

STATIC_VIDEOS_DIR = BASE_DIR / "static" / "videos"
STATIC_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

STATIC_IMAGES_DIR = BASE_DIR / "static" / "images"
STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

STATIC_MAGIC_LENS_DIR = BASE_DIR / "static" / "magic_lens"
STATIC_MAGIC_LENS_DIR.mkdir(parents=True, exist_ok=True)

STATIC_ASSISTANT_AUDIO_DIR = BASE_DIR / "static" / "assistant_audio"
STATIC_ASSISTANT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Studio Pro Backend...")

    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await ensure_schema_compatibility()
    logger.info("Database tables created/verified and schema compatibility checked")

    await cache.ensure_ready()

    try:
        await ensure_initial_admins()
    except Exception as e:
        logger.error("Failed to seed initial admins: %s", e, exc_info=True)
        if not settings.DEBUG:
            raise

    yield

    logger.info("Shutting down AI Studio Pro Backend...")
    await cache.close()
    await engine.dispose()


app = FastAPI(
    title="AI Studio Pro API",
    description="Professional AI Image & Image-to-Image Platform",
    version="15.5.22",
    lifespan=lifespan,
    # Production hardening: hide interactive API docs and OpenAPI when DEBUG=false.
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Assistant routes:
# GET  /assistant/health
# POST /assistant/chat
# POST /assistant/speech
app.include_router(assistant_router)
app.include_router(assistant_vision_router)
app.include_router(assistant_creative_router)
app.include_router(assistant_brand_router)
app.include_router(assistant_audience_router)

# AI Studio Operator routes:
# GET  /api/v1/operator/health
# POST /api/v1/operator/plan
# POST /api/v1/operator/confirm
app.include_router(ai_operator_router, prefix="/api/v1")
app.include_router(autonomous_platform_router, prefix="/api/v1")

# Static generated videos
app.mount(
    "/videos",
    StaticFiles(directory=str(STATIC_VIDEOS_DIR)),
    name="videos",
)

app.mount(
    "/images",
    StaticFiles(directory=str(STATIC_IMAGES_DIR)),
    name="images",
)


app.mount(
    "/magic_lens",
    StaticFiles(directory=str(STATIC_MAGIC_LENS_DIR)),
    name="magic_lens",
)

# Static generated Smart Agent Piper audio
app.mount(
    "/assistant_audio",
    StaticFiles(directory=str(STATIC_ASSISTANT_AUDIO_DIR)),
    name="assistant_audio",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"},
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if settings.ENABLE_SECURITY_HEADERS:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy",
                "geolocation=(), microphone=(self), camera=(self)",
            )

            if not settings.DEBUG:
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=63072000; includeSubDomains; preload",
                )

        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if settings.DEBUG else None),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Global exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"},
    )


# Main API routes:
# /api/v1/...
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    resp = {
        "name": "AI Studio Pro API",
        "version": "15.5.22",
        "status": "operational",
    }

    if app.docs_url:
        resp["docs"] = app.docs_url
    if app.redoc_url:
        resp["redoc"] = app.redoc_url
    if app.openapi_url:
        resp["openapi"] = app.openapi_url

    return resp


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )