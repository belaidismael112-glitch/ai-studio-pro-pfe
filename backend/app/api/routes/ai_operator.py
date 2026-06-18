from fastapi import APIRouter, Depends, Request

from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.schemas.ai_operator import (
    OperatorConfirmRequest,
    OperatorExecutionResponse,
    OperatorHealthResponse,
    OperatorPlanRequest,
    OperatorPlanResponse,
)
from app.services.ai_operator_service import operator_service

router = APIRouter(prefix="/operator", tags=["ai-studio-operator"])


@router.get("/health", response_model=OperatorHealthResponse)
def operator_health() -> OperatorHealthResponse:
    return OperatorHealthResponse()


@router.post("/plan", response_model=OperatorPlanResponse)
@limiter.limit("30/minute")
async def create_operator_plan(
    request: Request,
    payload: OperatorPlanRequest,
    current_user_id: int = Depends(get_current_user_id),
) -> OperatorPlanResponse:
    # Authentication is required so an unauthenticated caller cannot abuse
    # local Ollama or build executable plans against the user's credit wallet.
    return await operator_service.create_plan(payload, user_id=current_user_id)


@router.post("/confirm", response_model=OperatorExecutionResponse)
@limiter.limit("30/minute")
async def confirm_operator_plan(
    request: Request,
    payload: OperatorConfirmRequest,
    current_user_id: int = Depends(get_current_user_id),
) -> OperatorExecutionResponse:
    auth_header = request.headers.get("authorization")
    return await operator_service.confirm(payload, user_id=current_user_id, auth_header=auth_header)
