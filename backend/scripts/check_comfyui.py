"""Standalone image-first ComfyUI preflight.

Run from backend directory:
    python scripts/check_comfyui.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

# Allow running directly from backend/scripts.
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402


def workflow_status() -> list[tuple[str, bool]]:
    workflow_dir = BACKEND / "comfy_workflows"
    names = [
        "AIStudio_Image_FLUX_BASE_Correct_ComfyUI.json",
        "AIStudio_Image_FLUX_IDENTITY_IMG2IMG.json",
    ]
    return [(name, (workflow_dir / name).is_file()) for name in names]


def checkpoint_names(payload: object) -> list[str]:
    try:
        node = payload["CheckpointLoaderSimple"]  # type: ignore[index]
        values = node["input"]["required"]["ckpt_name"][0]
        return [str(item) for item in values] if isinstance(values, list) else []
    except Exception:
        return []


def candidate_urls(raw: str) -> list[str]:
    """Return configured URL plus a host-run fallback for Docker host aliases."""
    clean = str(raw).rstrip("/")
    values = [clean]
    try:
        parts = urlsplit(clean)
        if (parts.hostname or "").lower() == "host.docker.internal":
            host = "127.0.0.1"
            if parts.port:
                host = f"{host}:{parts.port}"
            local = urlunsplit((parts.scheme or "http", host, parts.path, "", "")).rstrip("/")
            if local not in values:
                values.append(local)
    except Exception:
        pass
    return values


def main() -> int:
    print("AI Studio Pro V15.5 — ComfyUI preflight")
    print(f"AI_PROVIDER={settings.AI_PROVIDER}")
    print(f"COMFY_URL={settings.COMFY_URL}")
    print(f"COMFY_IMAGE_CHECKPOINT={settings.COMFY_IMAGE_CHECKPOINT}")
    print(f"COMFY_STRICT_WORKFLOW_MODE={settings.COMFY_STRICT_WORKFLOW_MODE}")

    failed = False
    if str(settings.AI_PROVIDER).lower() != "comfy":
        print("provider mode: FAILED (AI_PROVIDER must be comfy)")
        failed = True
    else:
        print("provider mode: OK")
    if not bool(settings.COMFY_STRICT_WORKFLOW_MODE):
        print("strict workflow: FAILED (COMFY_STRICT_WORKFLOW_MODE must be true)")
        failed = True
    else:
        print("strict workflow: OK")

    for name, present in workflow_status():
        print(f"workflow {name}: {'OK' if present else 'MISSING'}")
        failed = failed or not present

    connected_url = None
    last_error = None
    timeout = httpx.Timeout(5.0, connect=2.0)
    with httpx.Client(timeout=timeout) as client:
        for base_url in candidate_urls(str(settings.COMFY_URL)):
            try:
                response = client.get(f"{base_url}/system_stats")
                response.raise_for_status()
                connected_url = base_url
                break
            except Exception as exc:
                last_error = exc

        if not connected_url:
            print(f"ComfyUI connectivity: FAILED ({last_error})")
            failed = True
        else:
            print(f"ComfyUI connectivity: OK ({connected_url})")
            try:
                info = client.get(f"{connected_url}/object_info/CheckpointLoaderSimple")
                info.raise_for_status()
                names = checkpoint_names(info.json())
                if names:
                    available = str(settings.COMFY_IMAGE_CHECKPOINT) in names
                    print(f"checkpoint available: {'OK' if available else 'MISSING'}")
                    failed = failed or not available
                else:
                    print("checkpoint availability: FAILED (ComfyUI object_info did not list names)")
                    failed = True
            except Exception as exc:
                print(f"checkpoint availability: FAILED ({exc})")
                failed = True

    if failed:
        print("RESULT: NOT READY")
        return 1
    print("RESULT: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
