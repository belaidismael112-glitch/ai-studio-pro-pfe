"""Shared rate limiter instance.

Improvement: rate limit by authenticated user when possible, otherwise fall back to IP.
This avoids punishing multiple users behind the same NAT and is harder to bypass than IP-only.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import decode_token


def rate_limit_key(request: Request) -> str:
    """Prefer user-based key when a valid Bearer access token is present."""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        payload = decode_token(token)
        if payload and payload.get("type") == "access" and payload.get("sub") is not None:
            return f"user:{payload['sub']}"
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key, default_limits=["120/minute"])
