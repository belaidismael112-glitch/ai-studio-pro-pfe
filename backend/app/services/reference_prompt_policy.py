"""Lightweight policy helpers for source-reference generation requests."""
from __future__ import annotations

VAGUE_REFERENCE_PROMPTS = {
    "do it", "make it", "generate it", "create it", "go", "ok", "okay",
    "same", "try", "retry", "again", "yes", "oui", "vas-y", "vas y",
}

REFERENCE_PROMPT_GUIDANCE = (
    "Describe the requested result before generating from a reference image. "
    "For example: create a clean Instagram shoe flyer with the full product visible, a headline area and a price area."
)


def validate_reference_prompt_actionable(prompt: str, *, mode: str) -> None:
    """Reject placeholder reference prompts that do not describe an output."""
    normalized = " ".join((prompt or "").lower().strip().split())
    meaningful_words = [word for word in normalized.replace("/", " ").split() if len(word) > 1]
    if mode != "text_only" and (normalized in VAGUE_REFERENCE_PROMPTS or len(meaningful_words) < 3):
        raise ValueError(REFERENCE_PROMPT_GUIDANCE)


def append_gate_form_metadata(
    prompt: str,
    *,
    subject_type: str | None = None,
    gate_status: str | None = None,
    reference_quality_score: float | None = None,
    subject_preservation_score: float | None = None,
    subject_coverage_percent: float | None = None,
    identity_reliability_score: float | None = None,
    generation_confidence_score: float | None = None,
) -> str:
    """Make multipart source metrics visible to the shared backend gate parser."""
    parts = [prompt or ""]
    if subject_type:
        parts.append(f"Subject type {subject_type}.")
    if subject_coverage_percent is not None:
        parts.append(f"Coverage {subject_coverage_percent}%.")
    if reference_quality_score is not None:
        parts.append(f"Reference quality {reference_quality_score}/100.")
    if subject_preservation_score is not None:
        parts.append(f"Subject preservation {subject_preservation_score}/100.")
    if identity_reliability_score is not None:
        parts.append(f"Identity reliability {identity_reliability_score}/100.")
    if generation_confidence_score is not None:
        parts.append(f"Generation confidence {generation_confidence_score}/100.")
    if gate_status:
        parts.append(f"generation_gate {gate_status}.")
    return " ".join(part for part in parts if part).strip()
