"""Compatibility module for entrypoints that import `from app.main import app`.

The canonical FastAPI app is defined in the repository root `main.py`.
This file keeps older launch scripts working.
"""

from main import app  # noqa: F401
