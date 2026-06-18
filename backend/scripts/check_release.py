"""Static release sanity check for the image-first production package.

Run from backend directory:
    python scripts/check_release.py

This does not replace the live ComfyUI preflight. It verifies the packaged
configuration and the image-first safety invariants without external services.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent

checks: list[tuple[str, bool]] = []

def add(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))
    print(f"{name}: {'OK' if ok else 'FAILED'}")

def contains(path: Path, text: str) -> bool:
    return path.is_file() and text in path.read_text(encoding="utf-8", errors="ignore")

def main() -> int:
    print("AI Studio Pro V15.5 — static release check")
    workflows = BACKEND / "comfy_workflows"
    add("text-to-image workflow", (workflows / "AIStudio_Image_FLUX_BASE_Correct_ComfyUI.json").is_file())
    add("image-to-image workflow", (workflows / "AIStudio_Image_FLUX_IDENTITY_IMG2IMG.json").is_file())

    env_example = BACKEND / ".env.production.example"
    add("production env provider", contains(env_example, "AI_PROVIDER=comfy"))
    add("production env image checkpoint", contains(env_example, "COMFY_IMAGE_CHECKPOINT="))
    add("production env strict workflow", contains(env_example, "COMFY_STRICT_WORKFLOW_MODE=true"))

    generations = BACKEND / "app/api/v1/endpoints/generations.py"
    generation_source = generations.read_text(encoding="utf-8", errors="ignore") if generations.is_file() else ""
    add("legacy video HTTP gate", generation_source.count("_raise_video_disabled()") >= 3)
    add("runtime status router", contains(BACKEND / "app/api/v1/router.py", "include_router(runtime.router"))
    add("worker legacy video gate", contains(BACKEND / "app/workers/tasks.py", 'if gen.generation_type in {"video", "img2vid"}'))

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8", errors="ignore")
    add("compose celery worker", "celery" in compose and "--concurrency=1" in compose)
    add("compose shared uploads", compose.count("ai_uploads:/tmp/ai_studio_pro") >= 2)
    add("compose shared database", compose.count("ai_db:/app/data") >= 2)
    add("compose ComfyUI host bridge", "host.docker.internal:8188" in compose)
    add("compose frontend build args", "NEXT_PUBLIC_API_URL:" in compose and "NEXT_PUBLIC_ASSISTANT_API_URL:" in compose)

    add("frontend image-to-image route", (ROOT / "frontend/src/app/generate/image-to-image/page.tsx").is_file())
    add("frontend legacy video redirect", contains(ROOT / "frontend/src/app/generate/video/page.tsx", 'redirect("/generate/image-to-image")'))
    add("frontend runtime settings", contains(ROOT / "frontend/src/app/settings/page.tsx", "runtimeApi.getStatus()"))

    operator_service = BACKEND / "app/services/ai_operator_service.py"
    operator_routes = BACKEND / "app/api/routes/ai_operator.py"
    autonomous_service = BACKEND / "app/services/autonomous_platform_service.py"
    autonomous_routes = BACKEND / "app/api/routes/autonomous_platform.py"
    builder_ui = ROOT / "frontend/src/components/autonomous-platform-pro/autonomous-platform-pro.tsx"
    operator_ui = ROOT / "frontend/src/components/ai-operator/ai-studio-operator-live.tsx"
    add("operator one-time approval guard", contains(operator_service, "session.consumed = True"))
    add("operator authenticated routes", contains(operator_routes, "Depends(get_current_user_id)"))
    add("platform builder cycle rejection", contains(autonomous_service, "Workflow graph contains a cycle"))
    add("platform builder authenticated routes", contains(autonomous_routes, "Depends(get_current_user_id)"))
    add("platform builder human approval gate", contains(builder_ui, "Human approval required"))
    add("operator offline read-only fallback", contains(operator_ui, "local-readonly-"))
    add("operator platform smoke script", (BACKEND / "scripts/check_operator_platform.py").is_file())
    add("operator platform Windows check", (BACKEND / "CHECK_OPERATOR_PLATFORM_WINDOWS.bat").is_file())

    frontend_package = ROOT / "frontend/package.json"
    frontend_package_text = frontend_package.read_text(encoding="utf-8", errors="ignore") if frontend_package.is_file() else ""
    add("frontend Next.js 16.2.7", '"next": "16.2.7"' in frontend_package_text)
    add("frontend Axios 1.17.0", '"axios": "1.17.0"' in frontend_package_text)
    add("frontend direct ESLint CLI", '"lint": "eslint . --max-warnings=0"' in frontend_package_text)
    add("frontend typecheck script", '"typecheck": "tsc --noEmit"' in frontend_package_text)
    add("frontend production audit script", '"audit:prod": "npm audit --omit=dev --audit-level=high"' in frontend_package_text)
    add("frontend flat ESLint config", (ROOT / "frontend/eslint.config.mjs").is_file())
    add("local verified Windows checker", (ROOT / "VERIFY_LOCAL_PRODUCTION_WINDOWS.bat").is_file())
    add("local verified Windows launcher", (ROOT / "START_LOCAL_PRODUCTION_VERIFIED_WINDOWS.bat").is_file())
    add("live ComfyUI GPU smoke script", (BACKEND / "scripts/check_comfyui_generation.py").is_file())
    add("verification requirements", (BACKEND / "requirements-verify.txt").is_file())
    add("live ComfyUI GPU Windows check", (BACKEND / "CHECK_COMFYUI_GENERATION_WINDOWS.bat").is_file())
    add("cross-platform local verifier", (ROOT / "VERIFY_LOCAL_PRODUCTION.sh").is_file())
    add("cross-platform verified launcher", (ROOT / "START_LOCAL_PRODUCTION_VERIFIED.sh").is_file())

    failed = [name for name, ok in checks if not ok]
    if failed:
        print("RESULT: NOT READY")
        print("Failed checks:")
        for name in failed:
            print(f"- {name}")
        return 1
    print("RESULT: READY")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
