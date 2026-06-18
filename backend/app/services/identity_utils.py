"""Small identity normalization helpers shared by auth and admin endpoints."""

from __future__ import annotations


def normalize_email(value: object) -> str:
    """Return a stable lowercase email string for storage and comparisons."""

    return str(value or "").strip().lower()
