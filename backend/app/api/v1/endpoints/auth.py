"""Authentication endpoints"""


from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user_id,
    get_current_token_payload,
    revoke_jti,
)
from app.core.config import settings
from app.core import cache
from app.models.user import User
from app.services.identity_utils import normalize_email
from app.schemas.user import (
    UserCreate,
    UserLogin,
    TokenResponse,
    UserResponse,
    PasswordChange,
)

from app.core.rate_limit import limiter

router = APIRouter()
security = HTTPBearer()


from pydantic import BaseModel


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


def _ttl_from_exp(exp: int) -> int:
    now = int(datetime.now(timezone.utc).timestamp())
    return max(0, exp - now)


async def _allowlist_refresh_jti(user_id: int, refresh_payload: dict) -> None:
    jti = refresh_payload.get("jti")
    exp = refresh_payload.get("exp")
    if not jti or not exp:
        return
    key = f"{settings.REFRESH_ALLOWLIST_PREFIX}:{user_id}"
    await cache.s_add(key, str(jti), ttl_seconds=_ttl_from_exp(int(exp)))


async def _remove_refresh_jti(user_id: int, jti: str) -> None:
    key = f"{settings.REFRESH_ALLOWLIST_PREFIX}:{user_id}"
    await cache.s_remove(key, str(jti))


async def _is_refresh_jti_allowed(user_id: int, jti: str) -> bool:
    key = f"{settings.REFRESH_ALLOWLIST_PREFIX}:{user_id}"
    return await cache.s_is_member(key, str(jti))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user"""

    email = normalize_email(user_data.email)
    result = await db.execute(select(User).where(func.lower(User.email) == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        credits=settings.FREE_TRIAL_CREDITS,
    )

    db.add(new_user)
    await db.flush()
    # Load database-generated defaults (notably created_at) before Pydantic
    # serializes the response. Without this refresh, a clean registration can
    # intermittently return HTTP 500 even though the row was inserted.
    await db.refresh(new_user)

    access_token = create_access_token({"sub": str(new_user.id), "ver": int(new_user.auth_token_version or 0)})
    refresh_token = create_refresh_token({"sub": str(new_user.id), "ver": int(new_user.auth_token_version or 0)})

    refresh_payload = decode_token(refresh_token) or {}
    await _allowlist_refresh_jti(new_user.id, refresh_payload)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(new_user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login user"""

    email = normalize_email(credentials.email)
    result = await db.execute(select(User).where(func.lower(User.email) == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()

    access_token = create_access_token({"sub": str(user.id), "ver": int(user.auth_token_version or 0)})
    refresh_token = create_refresh_token({"sub": str(user.id), "ver": int(user.auth_token_version or 0)})

    refresh_payload = decode_token(refresh_token) or {}
    await _allowlist_refresh_jti(user.id, refresh_payload)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=dict)
@limiter.limit("20/minute")
async def refresh_token(payload_in: RefreshTokenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = payload_in.refresh_token
    """Refresh access token (refresh token rotation + allowlist)"""

    payload = decode_token(refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not user_id or not jti or not exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Enforce allowlist (rotation)
    if not await _is_refresh_jti_allowed(int(user_id), str(jti)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure user still valid
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if int(payload.get("ver", 0) or 0) != int(user.auth_token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired after account security update",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rotate: remove old refresh jti + blacklist it (defense-in-depth)
    await _remove_refresh_jti(int(user_id), str(jti))
    await revoke_jti(str(jti), ttl_seconds=_ttl_from_exp(int(exp)))

    new_access_token = create_access_token({"sub": str(user.id), "ver": int(user.auth_token_version or 0)})
    new_refresh_token = create_refresh_token({"sub": str(user.id), "ver": int(user.auth_token_version or 0)})

    new_refresh_payload = decode_token(new_refresh_token) or {}
    await _allowlist_refresh_jti(user.id, new_refresh_payload)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    body: LogoutRequest | None = None,
    payload: dict = Depends(get_current_token_payload),
):
    refresh_token = body.refresh_token if body else None
    """Logout user: revoke current access token and (optionally) the provided refresh token."""

    access_jti = payload.get("jti")
    access_exp = payload.get("exp")
    if access_jti and access_exp:
        await revoke_jti(str(access_jti), ttl_seconds=_ttl_from_exp(int(access_exp)))

    # Optional refresh token revocation
    if refresh_token:
        rp = decode_token(refresh_token)
        if rp and rp.get("type") == "refresh" and rp.get("sub") == payload.get("sub"):
            rjti = rp.get("jti")
            rexp = rp.get("exp")
            if rjti and rexp:
                await _remove_refresh_jti(int(payload["sub"]), str(rjti))
                await revoke_jti(str(rjti), ttl_seconds=_ttl_from_exp(int(rexp)))

    return {"message": "Successfully logged out"}


@router.post("/change-password")
@limiter.limit("10/minute")
async def change_password(
    request: Request,
    password_data: PasswordChange,
    current_user_id: int = Depends(get_current_user_id),
    token_payload: dict = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Change user password"""

    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(password_data.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.hashed_password = get_password_hash(password_data.new_password)
    user.auth_token_version = int(user.auth_token_version or 0) + 1
    await db.flush()

    # Revoke refresh sessions and the current access JTI immediately. The
    # account-level version also invalidates every other previously issued
    # access token without waiting for its normal expiration.
    await cache.delete_key(f"{settings.REFRESH_ALLOWLIST_PREFIX}:{current_user_id}")
    access_jti = token_payload.get("jti")
    access_exp = token_payload.get("exp")
    if access_jti and access_exp:
        await revoke_jti(str(access_jti), ttl_seconds=_ttl_from_exp(int(access_exp)))

    return {"message": "Password changed successfully. Sign in again on every device."}
