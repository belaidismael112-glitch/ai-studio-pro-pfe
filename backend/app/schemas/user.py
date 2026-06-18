"""User schemas"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    # Keep create/update validation strict, but never crash while serializing a
    # legacy database row created by an older local build. Startup compatibility
    # migrations normalize known .local aliases; this output model is the final
    # defensive layer for unexpected historical rows.
    email: str
    full_name: Optional[str] = None
    id: int
    credits: int
    subscription_tier: str
    subscription_status: str
    is_active: bool
    is_admin: bool
    role: str = "USER"
    created_at: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)
