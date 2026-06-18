"""Backend semantic runner for the visual Platform Builder.

The builder is intentionally image-first. This module validates the DAG and
executes deterministic, auditable semantics for every non-credit node. Image
creation itself is queued by the authenticated frontend only after explicit
human approval, using the existing generation endpoint.

Important: the service never fabricates a vision score. If pixel-level analysis
has not run, vision/quality nodes return a warning instead of a fake success.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any, Dict, List

from fastapi import HTTPException, status

from app.core.config import settings
from app.services.ollama_service import chat as ollama_chat, env_bool

from app.schemas.autonomous_platform import (
    AutonomousLog,
    AutonomousWorkflowRequest,
    AutonomousWorkflowResponse,
)

USE_OLLAMA = os.getenv("AUTONOMOUS_PLATFORM_USE_OLLAMA", "true").lower() == "true"

ALLOWED_IMAGE_STYLES = {
    "photorealistic", "digital_art", "anime", "oil_painting", "watercolor",
    "sketch", "studio", "cinematic", "neonpunk", "fantasy", "3d",
}
STYLE_ALIASES = {
    "commercial": "cinematic",
    "premium": "cinematic",
    "luxury": "studio",
    "clean": "studio",
    "minimal": "studio",
    "realistic": "photorealistic",
    "photo": "photorealistic",
    "illustration": "digital_art",
    "digital": "digital_art",
    "3d_render": "3d",
    "3d_rendering": "3d",
    "3_d": "3d",
    "three_d": "3d",
    "minimalist": "studio",
    "corporate": "studio",
    "editorial": "cinematic",
}

MAX_GENERATION_PROMPT_CHARS = 1900
MAX_GENERATION_NEGATIVE_CHARS = 900


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _log(level: str, message: str) -> AutonomousLog:
    return AutonomousLog(id=str(uuid.uuid4()), level=level, message=message, timestamp=_ts())


def _order(req: AutonomousWorkflowRequest) -> List[str]:
    """Validate links and return a deterministic topological order."""

    ids = [node.id for node in req.nodes]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Workflow contains duplicate node ids.")

    edge_ids = [edge.id for edge in req.edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Workflow contains duplicate edge ids.")

    incoming = {node_id: 0 for node_id in ids}
    outgoing = {node_id: [] for node_id in ids}
    seen_links: set[tuple[str, str]] = set()

    for edge in req.edges:
        if edge.from_ not in outgoing or edge.to not in incoming:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Workflow edge {edge.id} references a missing node.",
            )
        if edge.from_ == edge.to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Workflow edge {edge.id} cannot connect a node to itself.",
            )
        link = (edge.from_, edge.to)
        if link in seen_links:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Workflow contains duplicate connection {edge.from_} -> {edge.to}.",
            )
        seen_links.add(link)
        outgoing[edge.from_].append(edge.to)
        incoming[edge.to] += 1

    queue = [node_id for node_id in ids if incoming[node_id] == 0]
    result: List[str] = []
    while queue:
        current = queue.pop(0)
        result.append(current)
        for target in outgoing.get(current, []):
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)

    if len(result) != len(ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Workflow graph contains a cycle. Remove the loop before running.",
        )
    return result


def _reachable(outgoing: Dict[str, List[str]], start: str, target: str) -> bool:
    queue = [start]
    seen: set[str] = set()
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if current == target:
            return True
        queue.extend(outgoing.get(current, []))
    return False


def _workflow_meta(req: AutonomousWorkflowRequest) -> Dict[str, Any]:
    """Validate production semantics and return approval/cost metadata."""
    if not req.nodes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Workflow must contain at least one node.",
        )

    ids = {node.id for node in req.nodes}
    outgoing: Dict[str, List[str]] = {node_id: [] for node_id in ids}
    for edge in req.edges:
        if edge.from_ in outgoing:
            outgoing[edge.from_].append(edge.to)

    image_nodes = [node for node in req.nodes if node.kind == "image_generation"]
    approvals = [node for node in req.nodes if node.kind == "approval" and _bool((node.config or {}).get("required", True), True)]

    if image_nodes and not approvals:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image-generation workflows require a Human Approval node before generation.",
        )

    for image_node in image_nodes:
        if not any(_reachable(outgoing, approval.id, image_node.id) for approval in approvals):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Image-generation node {image_node.id} must be downstream of a required Human Approval node.",
            )

    estimated_credits = len(image_nodes) * int(settings.CREDIT_COST_IMAGE)
    return {
        "image_generation_count": len(image_nodes),
        "estimated_credits": estimated_credits,
        "requires_approval": bool(image_nodes),
        "condition_mode": "review_marker_only",
    }


async def _ollama(prompt: str) -> str:
    use_ollama = env_bool("AUTONOMOUS_PLATFORM_USE_OLLAMA", USE_OLLAMA)
    require_ollama = env_bool("REQUIRE_OLLAMA", False)
    if not use_ollama:
        if require_ollama:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Platform Builder requires Ollama in production, but AUTONOMOUS_PLATFORM_USE_OLLAMA is disabled.",
            )
        return ""
    result = await ollama_chat(
        [
            {"role": "system", "content": "You are an image-first creative workflow planner. Be concise, factual, and do not claim actions that were not executed."},
            {"role": "user", "content": prompt},
        ],
        mode="advanced",
        feature="platform_builder",
        timeout_seconds=45,
    )
    content = (result.content or "").strip()
    if not content and require_ollama:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Platform Builder Ollama planner is unavailable: {result.error or 'empty Ollama response'}",
        )
    return content


def _int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(int(value), maximum))
    except Exception:
        return default


def _float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    try:
        return max(minimum, min(float(value), maximum))
    except Exception:
        return default


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return default


def _safe_text(value: Any, default: str, *, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or default)).strip()
    if not text:
        text = default
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip() or text[:max_chars].rstrip()
    return text


def _style(value: Any, default: str = "cinematic") -> str:
    raw = str(value or default).strip().lower().replace("-", "_").replace(" ", "_")
    raw = STYLE_ALIASES.get(raw, raw)
    return raw if raw in ALLOWED_IMAGE_STYLES else default


def _resolution(value: Any, default: tuple[int, int] = (768, 768)) -> tuple[int, int]:
    # Accept common UI forms: "768x768", "768 x 768", and "768×768".
    match = re.fullmatch(r"\s*(\d{3,4})\s*[x×]\s*(\d{3,4})\s*", str(value or ""), flags=re.I)
    if not match:
        return default
    return _int(match.group(1), default[0], minimum=256, maximum=2048), _int(match.group(2), default[1], minimum=256, maximum=2048)


def _status_log_level(node_status: str) -> str:
    if node_status == "warning":
        return "warning"
    if node_status == "error":
        return "error"
    return "success"


def _semantic_output(node, req: AutonomousWorkflowRequest, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(node.config or {})
    kind = node.kind
    output: Dict[str, Any] = {"kind": kind, "title": node.title, "status": "success", "config": cfg}

    if kind == "trigger":
        command = str(cfg.get("command") or req.goal).strip()
        context["command"] = command
        output["message"] = f"Captured workflow request: {command}"
        output["command"] = command

    elif kind == "ai_strategist":
        objective = str(cfg.get("objective") or "campaign")
        audience = str(cfg.get("audience") or "target audience")
        tone = str(cfg.get("tone") or "clean")
        strategy = f"Objective: {objective}. Audience: {audience}. Tone: {tone}. Goal: {req.goal}"
        context["strategy"] = strategy
        output.update(message="Campaign strategy extracted from node configuration and workflow goal.", strategy=strategy)

    elif kind == "creative_director":
        direction = (
            f"Composition with {cfg.get('camera', 'balanced framing')}; "
            f"{cfg.get('lighting', 'clean')} lighting; {cfg.get('mood', 'professional')} mood."
        )
        context["art_direction"] = direction
        output.update(message="Art direction prepared from explicit composition, lighting and mood settings.", art_direction=direction)

    elif kind == "prompt_engineer":
        rough = str(context.get("command") or req.goal)
        style = str(cfg.get("style") or "clean commercial")
        direction = str(context.get("art_direction") or "clear composition and readable subject")
        prompt = _safe_text(f"{rough}. {direction} Style: {style}. Sharp main subject, professional details, controlled background.", "production-ready commercial image", max_chars=MAX_GENERATION_PROMPT_CHARS)
        negative = _safe_text(cfg.get("negative") or "low quality, blurry, distorted, watermark, unreadable text", "low quality, blurry, distorted, watermark, unreadable text", max_chars=MAX_GENERATION_NEGATIVE_CHARS)
        context.update(prompt=prompt, negative_prompt=negative)
        output.update(message="Production prompt and negative prompt generated deterministically.", prompt=prompt, negative_prompt=negative)

    elif kind == "model_advisor":
        width, height = _resolution(cfg.get("resolution"), (768, 768))
        model_settings = {
            "model_id": "comfy-flux",
            "width": width,
            "height": height,
            # /generations/images validates num_inference_steps >= 10.
            # Keep the advisor output compatible even if Comfy strict mode later ignores it.
            "num_inference_steps": _int(cfg.get("steps"), 10, minimum=10, maximum=32),
            "guidance_scale": _float(cfg.get("cfg"), 1.0, minimum=1.0, maximum=3.0),
        }
        context["model_settings"] = model_settings
        output.update(message="Local ComfyUI FLUX settings selected from the advisor configuration.", model_settings=model_settings)

    elif kind == "approval":
        required = _bool(cfg.get("required", True), True)
        context["approval_required"] = required
        output.update(
            status="waiting_approval" if required else "success",
            message="Human approval is required before any credit-spending generation." if required else "Approval node is configured as optional.",
            approval_required=required,
        )

    elif kind == "image_generation":
        advisor = dict(context.get("model_settings") or {})
        payload = {
            "prompt": _safe_text(cfg.get("prompt") or context.get("prompt") or req.goal, "production-ready commercial image", max_chars=MAX_GENERATION_PROMPT_CHARS),
            "negative_prompt": _safe_text(cfg.get("negative") or context.get("negative_prompt") or "low quality, blurry", "low quality, blurry", max_chars=MAX_GENERATION_NEGATIVE_CHARS),
            "width": _int(cfg.get("width", advisor.get("width")), 768, minimum=256, maximum=2048),
            "height": _int(cfg.get("height", advisor.get("height")), 768, minimum=256, maximum=2048),
            "style": _style(cfg.get("style") or "cinematic"),
            "num_inference_steps": _int(advisor.get("num_inference_steps"), 10, minimum=10, maximum=32),
            "guidance_scale": _float(advisor.get("guidance_scale"), 1.0, minimum=1.0, maximum=3.0),
            "model_id": str(advisor.get("model_id") or "comfy-flux"),
        }
        context["generation_payload"] = payload
        output.update(
            status="ready",
            message="Generation payload prepared. The frontend queues this real image request only after human approval.",
            generation_payload=payload,
        )

    elif kind == "vision_analyzer":
        output.update(
            status="warning",
            message="Vision analysis is configured but not fabricated. Run Neural Camera Analysis on the generated asset for pixel-level analysis.",
            required_action="open_image_check_after_generation",
            checks=str(cfg.get("check") or "composition, clarity, subject, brand"),
        )

    elif kind == "quality_critic":
        output.update(
            status="warning",
            message="Quality checklist prepared. No score is invented before a real image analysis result exists.",
            minimum_score=_int(cfg.get("minScore"), 80, minimum=0, maximum=100),
            dimensions=str(cfg.get("dimensions") or "quality, alignment, brand, composition"),
        )

    elif kind == "auto_improve":
        improve = str(cfg.get("improve") or "sharper, clearer subject")
        improved = _safe_text(f"{context.get('prompt') or req.goal}. Improvement pass: {improve}.", "improved production-ready commercial image", max_chars=MAX_GENERATION_PROMPT_CHARS)
        context["prompt"] = improved
        output.update(message="Prompt improvement pass applied deterministically.", improved_prompt=improved)

    elif kind == "condition":
        expression = str(cfg.get("condition") or "quality_score >= 80")
        output.update(
            status="warning",
            message="Review-only condition marker registered. Automatic branching is not executed until a real metric and an explicit branch runner are available.",
            condition=expression,
            evaluated=False,
            execution_mode="review_marker_only",
        )

    elif kind == "output":
        output.update(
            message="Final output manifest prepared from executed workflow context.",
            manifest={
                "prompt": context.get("prompt"),
                "negative_prompt": context.get("negative_prompt"),
                "generation_payload": context.get("generation_payload"),
                "approval_required": context.get("approval_required", False),
            },
        )

    else:  # pragma: no cover - schema prevents this
        output.update(status="error", message=f"Unsupported node kind: {kind}")

    return output


async def plan_workflow(req: AutonomousWorkflowRequest) -> AutonomousWorkflowResponse:
    run_id = str(uuid.uuid4())
    order = _order(req)
    meta = _workflow_meta(req)
    kinds = sorted({node.kind for node in req.nodes})
    ai = await _ollama(f"Plan this image-first creative workflow.\nTitle: {req.title}\nGoal: {req.goal}\nNodes: {', '.join(kinds)}")
    logs = [
        _log("info", f"Planning workflow: {req.title}"),
        _log("success", f"Workflow contains {len(req.nodes)} nodes and {len(req.edges)} valid links."),
    ]
    logs.append(_log("success" if ai else "warning", f"Ollama plan: {ai[:500]}" if ai else "Ollama summary unavailable; deterministic plan prepared."))
    return AutonomousWorkflowResponse(
        ok=True,
        run_id=run_id,
        summary="Workflow plan is ready for deterministic backend preflight.",
        logs=logs,
        node_outputs={"ordered_nodes": order, "node_kinds": kinds, "workflow_meta": meta},
    )


async def run_workflow(req: AutonomousWorkflowRequest) -> AutonomousWorkflowResponse:
    run_id = str(uuid.uuid4())
    order = _order(req)
    meta = _workflow_meta(req)
    nodes = {node.id: node for node in req.nodes}
    context: Dict[str, Any] = {}
    outputs: Dict[str, Any] = {}
    logs: List[AutonomousLog] = [_log("info", f"Backend semantic preflight {run_id} started.")]

    for node_id in order:
        output = _semantic_output(nodes[node_id], req, context)
        outputs[node_id] = output
        logs.append(_log(_status_log_level(str(output.get("status"))), f"{nodes[node_id].title}: {output.get('message')}"))

    outputs["workflow_meta"] = meta
    logs.append(_log("success", "Backend semantic preflight completed. Credit-spending generation remains behind human approval."))
    return AutonomousWorkflowResponse(
        ok=True,
        run_id=run_id,
        summary="Backend semantic workflow preflight completed without fabricated node results.",
        logs=logs,
        node_outputs=outputs,
    )
