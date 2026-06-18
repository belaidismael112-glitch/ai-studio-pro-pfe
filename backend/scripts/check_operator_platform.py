"""Isolated production smoke check for AI Operator and Platform Builder.

Run from backend directory:
    python scripts/check_operator_platform.py

The script uses a temporary SQLite database, never the configured production DB.
It verifies public health endpoints, authenticated-route gates, human approval
behavior, cancellation/replay safety, valid Platform Builder runs, and cycle
rejection without starting a real generation job or spending credits.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

SMOKE_DB = Path(tempfile.gettempdir()) / "ai_studio_operator_platform_smoke.db"
try:
    SMOKE_DB.unlink(missing_ok=True)
except Exception:
    pass

# Isolated test runtime. These values are intentionally assigned, not loaded
# from .env, so running the smoke test can never mutate a production database.
os.environ["SECRET_KEY"] = "operator-platform-smoke-secret-" + "x" * 80
os.environ["JWT_SECRET_KEY"] = "operator-platform-smoke-jwt-" + "y" * 80
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{SMOKE_DB}"
os.environ["DEBUG"] = "false"
os.environ["OPERATOR_USE_OLLAMA"] = "false"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

from fastapi.testclient import TestClient  # noqa: E402
from app.core.security import get_current_user_id  # noqa: E402
from main import app  # noqa: E402


WORKFLOW = {
    "title": "Approved image campaign",
    "goal": "Create one safe approved hero image.",
    "nodes": [
        {"id": "trigger", "kind": "trigger", "title": "Start"},
        {"id": "approval", "kind": "approval", "title": "Human approval"},
        {"id": "image", "kind": "image_generation", "title": "Image"},
        {"id": "output", "kind": "output", "title": "Output"},
    ],
    "edges": [
        {"id": "e1", "from": "trigger", "to": "approval"},
        {"id": "e2", "from": "approval", "to": "image"},
        {"id": "e3", "from": "image", "to": "output"},
    ],
}


def main() -> int:
    checks: list[tuple[str, bool]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok)))
        suffix = f" ({detail})" if detail else ""
        print(f"{name}: {'OK' if ok else 'FAILED'}{suffix}")

    print("AI Studio Pro V15.5 — Operator + Platform Builder isolated smoke check")

    try:
        with TestClient(app) as client:
            add("operator health public", client.get("/api/v1/operator/health").status_code == 200)
            add("platform builder health public", client.get("/api/v1/autonomous-platform/health").status_code == 200)
            add(
                "operator plan authentication gate",
                client.post("/api/v1/operator/plan", json={"command": "Create an image"}).status_code in {401, 403},
            )
            add(
                "platform builder plan authentication gate",
                client.post("/api/v1/autonomous-platform/plan", json=WORKFLOW).status_code in {401, 403},
            )
            add(
                "platform builder run authentication gate",
                client.post("/api/v1/autonomous-platform/run", json=WORKFLOW).status_code in {401, 403},
            )

            # Override only after auth gates have been proven. This simulates a
            # valid authenticated user without requiring production credentials.
            app.dependency_overrides[get_current_user_id] = lambda: 1

            response = client.post(
                "/api/v1/operator/plan",
                json={"command": "Create a square premium cafe poster", "max_credits": 20},
            )
            body = response.json()
            add("operator authenticated plan", response.status_code == 200, f"HTTP {response.status_code}")
            add("operator human approval required", body.get("requires_confirmation") is True)
            add("operator image-first action", any(action.get("type") == "generate_image" for action in body.get("actions", [])))

            session_id = body.get("session_id")
            response = client.post("/api/v1/operator/confirm", json={"session_id": session_id, "approved": False})
            add(
                "operator cancellation accepted without generation",
                response.status_code == 200 and response.json().get("final_result") == {"cancelled": True},
                f"HTTP {response.status_code}",
            )
            response = client.post("/api/v1/operator/confirm", json={"session_id": session_id, "approved": True})
            add(
                "operator cancelled plan cannot replay",
                response.status_code == 200 and response.json().get("approved") is False,
                f"HTTP {response.status_code}",
            )

            response = client.post("/api/v1/autonomous-platform/plan", json=WORKFLOW)
            add("platform builder authenticated plan", response.status_code == 200 and response.json().get("ok") is True, f"HTTP {response.status_code}")
            response = client.post("/api/v1/autonomous-platform/run", json=WORKFLOW)
            add("platform builder authenticated safe run", response.status_code == 200 and response.json().get("ok") is True, f"HTTP {response.status_code}")

            cyclic = {
                **WORKFLOW,
                "nodes": [
                    {"id": "a", "kind": "trigger", "title": "A"},
                    {"id": "b", "kind": "output", "title": "B"},
                ],
                "edges": [
                    {"id": "c1", "from": "a", "to": "b"},
                    {"id": "c2", "from": "b", "to": "a"},
                ],
            }
            response = client.post("/api/v1/autonomous-platform/run", json=cyclic)
            add("platform builder cycle rejection", response.status_code == 422, f"HTTP {response.status_code}")

            app.dependency_overrides.clear()
    finally:
        app.dependency_overrides.clear()
        try:
            SMOKE_DB.unlink(missing_ok=True)
        except Exception:
            pass

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"RESULT: NOT READY ({len(checks) - len(failed)}/{len(checks)} passed)")
        for name in failed:
            print(f"- {name}")
        return 1

    print(f"RESULT: READY ({len(checks)}/{len(checks)} passed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
