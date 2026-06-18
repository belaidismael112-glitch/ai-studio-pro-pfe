from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OperatorActionType(str, Enum):
    improve_prompt = "improve_prompt"
    check_credits = "check_credits"
    generate_image = "generate_image"
    save_history = "save_history"
    suggest_next_steps = "suggest_next_steps"


class OperatorActionStatus(str, Enum):
    pending = "pending"
    waiting_confirmation = "waiting_confirmation"
    approved = "approved"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class OperatorPlanRequest(BaseModel):
    command: str = Field(..., min_length=3, max_length=4000)
    brand_name: Optional[str] = None
    max_credits: Optional[int] = Field(default=None, ge=0)
    allow_image: bool = True
    auto_execute_safe_actions: bool = True
    context: Dict[str, Any] = Field(default_factory=dict)


class OperatorAction(BaseModel):
    id: str
    type: OperatorActionType
    title: str
    description: str
    credits_cost: int = 0
    requires_confirmation: bool = False
    status: OperatorActionStatus = OperatorActionStatus.pending
    payload: Dict[str, Any] = Field(default_factory=dict)


class OperatorPlanResponse(BaseModel):
    session_id: str
    title: str
    summary: str
    total_estimated_credits: int
    requires_confirmation: bool
    actions: List[OperatorAction]
    assistant_message: str
    cursor_script: List[Dict[str, Any]] = Field(default_factory=list)


class OperatorConfirmRequest(BaseModel):
    session_id: str
    approved: bool


class OperatorExecutionEvent(BaseModel):
    id: str
    kind: str
    title: str
    message: str
    status: OperatorActionStatus = OperatorActionStatus.running
    progress: int = Field(default=0, ge=0, le=100)
    cursor_target: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class OperatorExecutionResponse(BaseModel):
    session_id: str
    approved: bool
    message: str
    events: List[OperatorExecutionEvent]
    final_result: Dict[str, Any] = Field(default_factory=dict)


class OperatorHealthResponse(BaseModel):
    status: str = "ok"
    module: str = "ai-studio-operator"
    version: str = "1.1.0-image-first-safe"
