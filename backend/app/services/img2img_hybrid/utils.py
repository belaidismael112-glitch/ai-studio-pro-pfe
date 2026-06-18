from __future__ import annotations
from pathlib import Path
import os, uuid


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def ensure_output_dir(output_dir: str | None = None) -> Path:
    p = Path(output_dir or os.getenv("IMG2IMG_HYBRID_OUTPUT_DIR", "static/images"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def unique_name(prefix: str, suffix: str = ".png") -> str:
    return f"{prefix}_{uuid.uuid4().hex}{suffix}"


def backend_public_image_url(local_path: str) -> str:
    backend = os.getenv("BACKEND_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{backend}/images/{Path(local_path).name}"
