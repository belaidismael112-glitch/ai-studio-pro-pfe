from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field, ConfigDict


AutonomousNodeKind = Literal[
    "trigger",
    "ai_strategist",
    "creative_director",
    "prompt_engineer",
    "model_advisor",
    "approval",
    "image_generation",
    "vision_analyzer",
    "quality_critic",
    "auto_improve",
    "condition",
    "output",
]


class AutonomousNode(BaseModel):
    id: str = Field(..., min_length=1, max_length=160)
    kind: AutonomousNodeKind
    title: str = Field(..., min_length=1, max_length=240)
    description: str = Field(default="", max_length=1200)
    x: float = 0
    y: float = 0
    status: str = Field(default="idle", max_length=40)
    progress: float = Field(default=0, ge=0, le=100)
    elapsedMs: float = Field(default=0, ge=0)
    config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(protected_namespaces=())


class AutonomousEdge(BaseModel):
    id: str = Field(..., min_length=1, max_length=160)
    from_: str = Field(alias="from", min_length=1, max_length=160)
    to: str = Field(..., min_length=1, max_length=160)

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())


class AutonomousWorkflowRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=240)
    goal: str = Field(..., min_length=1, max_length=2000)
    nodes: List[AutonomousNode] = Field(default_factory=list, max_length=120)
    edges: List[AutonomousEdge] = Field(default_factory=list, max_length=320)

    model_config = ConfigDict(protected_namespaces=())


class AutonomousLog(BaseModel):
    id: str
    level: Literal["info", "success", "warning", "error"] = "info"
    message: str
    timestamp: str


class AutonomousWorkflowResponse(BaseModel):
    ok: bool = True
    run_id: str
    summary: str
    logs: List[AutonomousLog] = Field(default_factory=list)
    node_outputs: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(protected_namespaces=())
