from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.database import async_session
from app.core import cache
from app.core.deps import get_current_user
from app.core.roles import Role, require_role
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.schemas.support_tickets import TicketAdminUpdate, TicketCreate, TicketOut

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Support"])
admin_router = APIRouter(tags=["Admin - Support"], dependencies=[Depends(require_role(Role.ADMIN))])

VALID_TICKET_STATUSES = {"open", "in_progress", "resolved", "closed"}


def _ticket_to_out(ticket: SupportTicket) -> TicketOut:
    data = TicketOut.model_validate(ticket)
    user = getattr(ticket, "user", None)
    if user:
        data.user_email = getattr(user, "email", None)
        data.user_name = getattr(user, "full_name", None)
    return data


def _clean_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    value = status.strip().lower()
    if value not in VALID_TICKET_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Invalid ticket status. Use open, in_progress, resolved, or closed.",
        )
    return value


@router.post("/tickets", response_model=TicketOut)
async def create_ticket(payload: TicketCreate, current_user: User = Depends(get_current_user)):
    subject = (payload.subject or "").strip()
    message = (payload.message or "").strip()

    if not subject or not message:
        raise HTTPException(status_code=400, detail="Subject and message are required")

    async with async_session() as db:
        ticket = SupportTicket(
            user_id=current_user.id,
            subject=subject[:200],
            message=message[:8000],
            status="open",
        )
        db.add(ticket)
        await db.commit()
        await cache.invalidate_admin_caches()

        ticket = (
            await db.execute(
                select(SupportTicket)
                .options(selectinload(SupportTicket.user))
                .where(SupportTicket.id == ticket.id)
            )
        ).scalar_one()

        return _ticket_to_out(ticket)


@router.get("/tickets", response_model=dict)
async def my_tickets(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    async with async_session() as db:
        base = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.user))
            .where(SupportTicket.user_id == current_user.id)
            .where(SupportTicket.is_deleted == False)  # noqa: E712
        )
        total = int((await db.execute(
            select(func.count(SupportTicket.id))
            .where(SupportTicket.user_id == current_user.id)
            .where(SupportTicket.is_deleted == False)  # noqa: E712
        )).scalar() or 0)
        rows = (
            await db.execute(
                base.order_by(SupportTicket.created_at.desc()).offset(offset).limit(page_size)
            )
        ).scalars().all()

        return {
            "items": [_ticket_to_out(t) for t in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


# ---------------- Admin ----------------


@admin_router.get("/tickets", response_model=dict)
async def list_tickets(
    q: Optional[str] = Query(None, description="Search subject/message/user email"),
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    offset = (page - 1) * page_size
    clean_status = _clean_status(status) if status else None

    async with async_session() as db:
        stmt = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.user))
            .join(User, User.id == SupportTicket.user_id)
            .where(SupportTicket.is_deleted == False)  # noqa: E712
        )
        count_stmt = (
            select(func.count(SupportTicket.id))
            .select_from(SupportTicket)
            .join(User, User.id == SupportTicket.user_id)
            .where(SupportTicket.is_deleted == False)  # noqa: E712
        )

        if clean_status:
            stmt = stmt.where(SupportTicket.status == clean_status)
            count_stmt = count_stmt.where(SupportTicket.status == clean_status)

        if q:
            like = f"%{q.strip()}%"
            search_expr = or_(
                SupportTicket.subject.ilike(like),
                SupportTicket.message.ilike(like),
                User.email.ilike(like),
                User.full_name.ilike(like),
            )
            stmt = stmt.where(search_expr)
            count_stmt = count_stmt.where(search_expr)

        total = int((await db.execute(count_stmt)).scalar() or 0)
        rows = (
            await db.execute(
                stmt.order_by(SupportTicket.created_at.desc()).offset(offset).limit(page_size)
            )
        ).scalars().all()

        return {
            "items": [_ticket_to_out(t) for t in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@admin_router.patch("/tickets/{ticket_id}", response_model=TicketOut)
async def update_ticket(ticket_id: int, payload: TicketAdminUpdate):
    async with async_session() as db:
        ticket = (
            await db.execute(
                select(SupportTicket)
                .options(selectinload(SupportTicket.user))
                .where(SupportTicket.id == ticket_id)
            )
        ).scalar_one_or_none()
        if not ticket or ticket.is_deleted:
            raise HTTPException(status_code=404, detail="Ticket not found")

        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] is not None:
            data["status"] = _clean_status(data["status"])
        if "admin_notes" in data and data["admin_notes"] is not None:
            data["admin_notes"] = str(data["admin_notes"]).strip()[:8000]

        for key, value in data.items():
            setattr(ticket, key, value)

        await db.commit()
        await cache.invalidate_admin_caches()
        await db.refresh(ticket)
        return _ticket_to_out(ticket)


@admin_router.delete("/tickets/{ticket_id}", response_model=dict)
async def delete_ticket(ticket_id: int):
    async with async_session() as db:
        ticket = (await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket.is_deleted = True
        await db.commit()
        await cache.invalidate_admin_caches()
        return {"ok": True}
