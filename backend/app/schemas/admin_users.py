from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserOut(BaseModel):
    id: int
    # Output models accept legacy rows during safe startup migration.
    # Input/update models below stay strict with EmailStr.
    email: str
    full_name: str | None = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    role: str
    credits: int
    subscription_tier: str | None = None
    subscription_status: str | None = None
    subscription_expires_at: datetime | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_admin: Optional[bool] = None
    credits: Optional[int] = Field(None, ge=0)


class AdminUserRoleUpdate(BaseModel):
    # "USER" | "ADMIN" (and any others you added)
    role: str


class AdminUserResetPassword(BaseModel):
    new_password: str
