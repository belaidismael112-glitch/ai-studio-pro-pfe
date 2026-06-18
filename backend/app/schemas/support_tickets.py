from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TicketCreate(BaseModel):
    subject: str
    message: str


class TicketOut(BaseModel):
    id: int
    user_id: int
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    subject: str
    message: str
    status: str
    admin_notes: Optional[str] = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TicketAdminUpdate(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None
    is_deleted: Optional[bool] = None
