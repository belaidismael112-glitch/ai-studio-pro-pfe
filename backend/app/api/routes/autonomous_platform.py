from fastapi import APIRouter, Depends, Request

from app.core.rate_limit import limiter
from app.core.security import get_current_user_id
from app.schemas.autonomous_platform import AutonomousWorkflowRequest, AutonomousWorkflowResponse
from app.services.autonomous_platform_service import plan_workflow, run_workflow

router = APIRouter(prefix="/autonomous-platform", tags=["autonomous-platform"])


@router.get("/health")
async def health():
    return {"ok": True, "service": "autonomous-platform", "version": "v3-image-first-safe"}


@router.post("/plan", response_model=AutonomousWorkflowResponse)
@limiter.limit("30/minute")
async def plan(
    request: Request,
    payload: AutonomousWorkflowRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    _ = current_user_id
    return await plan_workflow(payload)


@router.post("/run", response_model=AutonomousWorkflowResponse)
@limiter.limit("30/minute")
async def run(
    request: Request,
    payload: AutonomousWorkflowRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    _ = current_user_id
    return await run_workflow(payload)
