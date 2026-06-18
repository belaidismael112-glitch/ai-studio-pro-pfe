"""Security utilities"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
import logging

from jose import JWTError, jwt
import hashlib
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core import cache

logger = logging.getLogger(__name__)

# Password hashing
PASSWORD_HASH_PREFIX = "bcrypt_sha256$"

# JWT security
security = HTTPBearer()


def _password_digest(password: str) -> bytes:
    """Return a deterministic bcrypt-safe digest.

    bcrypt accepts at most 72 bytes. Hashing the UTF-8 password with SHA-256
    first avoids the passlib/bcrypt compatibility issue and supports long
    passwords safely.
    """

    return hashlib.sha256((password or "").encode("utf-8")).hexdigest().encode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against either the new or legacy bcrypt format."""

    if not hashed_password:
        return False

    try:
        if hashed_password.startswith(PASSWORD_HASH_PREFIX):
            raw_hash = hashed_password[len(PASSWORD_HASH_PREFIX):].encode("utf-8")
            return bool(bcrypt.checkpw(_password_digest(plain_password), raw_hash))

        # Legacy plain-bcrypt/passlib hashes: bcrypt truncates to 72 bytes.
        return bool(bcrypt.checkpw((plain_password or "").encode("utf-8")[:72], hashed_password.encode("utf-8")))
    except Exception:
        logger.exception("Password verification failed")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password with stable bcrypt + SHA-256 pre-hash."""

    hashed = bcrypt.hashpw(_password_digest(password), bcrypt.gensalt(rounds=12)).decode("utf-8")
    return f"{PASSWORD_HASH_PREFIX}{hashed}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _base_claims(token_type: str, expires_in: timedelta) -> dict:
    now = _utcnow()
    return {
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "nbf": int((now - timedelta(seconds=settings.JWT_LEEWAY_SECONDS)).timestamp()),
        "exp": int((now + expires_in).timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "type": token_type,
    }


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    expires = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update(_base_claims("access", expires))
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    to_encode.update(_base_claims("refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)))
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def revoke_jti(jti: str, ttl_seconds: int) -> None:
    """Blacklist a token JTI for ttl_seconds."""
    key = f"{settings.TOKEN_BLACKLIST_PREFIX}:{jti}"
    await cache.set_str(key, "revoked", ttl_seconds=ttl_seconds)


async def is_jti_revoked(jti: str) -> bool:
    key = f"{settings.TOKEN_BLACKLIST_PREFIX}:{jti}"
    return (await cache.get_str(key)) is not None


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token (signature + standard claims)."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={
                "require_aud": True,
                "require_iat": True,
                "require_nbf": True,
                "require_exp": True,
            },
        )
        return payload
    except JWTError as e:
        logger.warning("Invalid JWT: %s", str(e))
        return None


async def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Return validated access-token payload and enforce revocation."""
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if await is_jti_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user_id(payload: dict = Depends(get_current_token_payload)) -> int:
    """Get the active current user ID from a validated access token.

    Access-token signature validation alone is not enough: a token issued before
    an admin deactivates or soft-deletes an account must stop working
    immediately. Keep the active-account check here so every protected route —
    including routes that only depend on ``get_current_user_id`` — inherits the
    same rule.
    """
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        resolved_user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Import lazily to avoid a module cycle during application startup.
    from sqlalchemy import select
    from app.core.database import async_session
    from app.models.user import User

    async with async_session() as db:
        user = (
            await db.execute(
                select(User.id, User.is_active, User.auth_token_version).where(User.id == resolved_user_id)
            )
        ).one_or_none()

    if not user or not bool(user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_version = int(payload.get("ver", 0) or 0)
        account_version = int(user.auth_token_version or 0)
    except (TypeError, ValueError):
        token_version, account_version = -1, 0
    if token_version != account_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired after account security update",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return resolved_user_id


def generate_api_key() -> str:
    """Generate a random API key"""
    import secrets
    return f"ak_{secrets.token_urlsafe(32)}"
