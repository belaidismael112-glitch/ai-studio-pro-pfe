"""Backend source-lock gate utilities.

Person identity-lock requests are practical: ambiguous/tiny references are blocked
before credits are deducted, while premium-score misses remain warnings. This keeps
Neural Camera usable for high-quality DJI/browser captures even when optional FAN
landmarks or conservative 90/100 scores are not available. Product/object/flyer
modes remain warning-only so their workflows are not coupled to face thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from app.core.production_rules import (
    FACE_MIN_COVERAGE_FOR_GENERATION,
    SUBJECT_MIN_REFERENCE_QUALITY,
    SUBJECT_MIN_PRESERVATION,
    SUBJECT_MIN_COVERAGE,
    SUBJECT_MAX_COVERAGE,
)

# Hard stop thresholds for actually unusable person references.
# 90/100 remains the premium/client-ready target in production_rules and UI, but
# generation should not be blocked solely because a DJI/browser capture scores
# 70-89 or because optional FAN landmarks are unavailable.
PERSON_IDENTITY_BLOCK_BELOW = 50
PERSON_GENERATION_BLOCK_BELOW = 45
# 14% remains the ideal production minimum, but 8-14% should be allowed
# with crop/review warnings instead of blocking a valid DJI/browser capture.
PERSON_FACE_HARD_MIN_COVERAGE = 8.0


@dataclass(slots=True)
class GateFailure:
    field: str
    value: Any
    required: Any
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "required": self.required,
            "message": self.message,
        }


@dataclass(slots=True)
class GateResult:
    allowed: bool
    status: str
    reason: str
    required_action: str
    failures: list[GateFailure]

    def as_http_detail(self) -> dict[str, Any]:
        message = (
            "Reference is not production-ready for identity lock. Retake or crop closer before generating."
            if not self.allowed
            else "Reference is weak, but generation is allowed with auto-crop/review warnings."
        )
        return {
            "error_code": self.reason,
            "message": message,
            "status": self.status,
            "required_action": self.required_action,
            "details": {"failures": [item.as_dict() for item in self.failures]},
        }


_SEP = r"\s*(?:[:=]|-|–|—)?\s*"
_SCORE = r"([0-9]+(?:\.[0-9]+)?)\s*(?:/\s*100|%)?"
_SUBJECT_TYPE_RE = re.compile(r"(?:subject\s+type|subject_type|type\s+sujet|type_sujet)" + _SEP + r"([a-zA-Z0-9_\-/]+)", re.I)
_COVERAGE_RE = re.compile(r"(?:face\s+coverage|subject\s+coverage|coverage|couverture|couverture\s+visage)" + _SEP + r"([0-9]+(?:\.[0-9]+)?)\s*%", re.I)
_REF_QUALITY_RE = re.compile(r"(?:reference\s+quality|reference_quality|qualit[ée]\s+r[ée]f[ée]rence|qualite\s+reference)" + _SEP + _SCORE, re.I)
_PRESERVATION_RE = re.compile(r"(?:subject\s+preservation|subject_preservation|pr[ée]servation\s+sujet|preservation\s+sujet)" + _SEP + _SCORE, re.I)
_IDENTITY_RE = re.compile(r"(?:identity\s+reliability|identity_reliability(?:_score)?|fiabilit[ée]\s+identit[ée]|fiabilite\s+identite|score\s+fiabilit[ée]\s+identit[ée])\s*(?:score)?" + _SEP + _SCORE, re.I)
_GENERATION_RE = re.compile(r"(?:generation\s+confidence|generation_confidence(?:_score)?|confiance\s+g[ée]n[ée]ration|confiance\s+generation|score\s+confiance\s+g[ée]n[ée]ration)\s*(?:score)?" + _SEP + _SCORE, re.I)
_FACE_COUNT_RE = re.compile(r"(?:detected\s+([0-9]+)\s+face|([0-9]+)\s+face\s*\(?s?\)?|face\s+count" + _SEP + r"([0-9]+)|faces" + _SEP + r"([0-9]+)|([0-9]+)\s+visage|visages\s+d[ée]tect[ée]s" + _SEP + r"([0-9]+))", re.I)
_LANDMARK_ACTIVE_RE = re.compile(r"(?:face-alignment-master\s+FAN\s+68-point\s+landmarks\s+are\s+active|landmarks\s+FAN\s+68\s+points.*actifs|landmarks.*active)", re.I)
_GATE_BLOCKED_RE = re.compile(r"(?:generation[_\s-]*gate|gate)" + _SEP + r"(blocked|bloqu[ée]|bloque)", re.I)


def _clean_prompt_text(text: str) -> str:
    return (text or "").replace(" ", " ").replace("​", " ").replace("؛", ";")


def _num(regex: re.Pattern[str], text: str) -> float | None:
    match = regex.search(_clean_prompt_text(text))
    if not match:
        return None
    try:
        for group in match.groups():
            if group is not None:
                return float(group)
        return None
    except Exception:
        return None


def _subject_type(text: str) -> str | None:
    match = _SUBJECT_TYPE_RE.search(_clean_prompt_text(text))
    return match.group(1).lower() if match else None


def evaluate_prompt_subject_lock_gate(prompt: str, *, subject_lock: bool = False) -> GateResult:
    """Evaluate prompt-embedded subject metrics.

    This protects legacy/frontend paths where a full analysis prompt is pasted
    into the assistant and then treated as a normal text-to-image request. If the
    prompt contains production metrics, the backend refuses weak source-locked
    generation regardless of what the frontend did.
    """
    text = _clean_prompt_text(prompt or "")
    stype = _subject_type(text)
    lowered = text.lower()
    gate_blocked = bool(_GATE_BLOCKED_RE.search(text))
    has_lock_metadata = bool(
        stype
        or "subject preservation" in lowered
        or "préservation sujet" in lowered
        or "preservation sujet" in lowered
        or "identity reliability" in lowered
        or "fiabilité identité" in lowered
        or "fiabilite identite" in lowered
        or "reference quality" in lowered
        or "qualité référence" in lowered
        or "qualite reference" in lowered
        or gate_blocked
    )

    if not subject_lock and not has_lock_metadata:
        return GateResult(True, "allowed", "NO_SOURCE_LOCK_METADATA", "none", [])

    failures: list[GateFailure] = []
    coverage = _num(_COVERAGE_RE, text)
    quality = _num(_REF_QUALITY_RE, text)
    preservation = _num(_PRESERVATION_RE, text)
    identity = _num(_IDENTITY_RE, text)
    generation = _num(_GENERATION_RE, text)
    face_count_num = _num(_FACE_COUNT_RE, text)
    landmarks_active = bool(_LANDMARK_ACTIVE_RE.search(text))

    # Person/face generation blocks only genuinely unusable references. Premium
    # thresholds are shown as warnings by Neural Camera; they should not prevent a
    # good DJI capture from reaching img2img/source-lock. Missing optional FAN
    # landmarks is also a warning, not a hard stop.
    is_person = stype in {"person", "person_face", "person_full"} or identity is not None or generation is not None

    if is_person:
        if face_count_num is not None and int(face_count_num) != 1:
            failures.append(GateFailure("face_count", int(face_count_num), 1, "Exactly one primary face is required."))
        if coverage is None or coverage < PERSON_FACE_HARD_MIN_COVERAGE:
            failures.append(GateFailure("coverage_percent", coverage, PERSON_FACE_HARD_MIN_COVERAGE, "Face coverage is too small for identity-preserving generation."))
        if identity is not None and identity < PERSON_IDENTITY_BLOCK_BELOW:
            failures.append(GateFailure("identity_reliability_score", identity, PERSON_IDENTITY_BLOCK_BELOW, "Identity reliability is too weak for source-lock generation."))
        if generation is not None and generation < PERSON_GENERATION_BLOCK_BELOW:
            failures.append(GateFailure("generation_confidence_score", generation, PERSON_GENERATION_BLOCK_BELOW, "Generation confidence is too weak for source-lock generation."))
        # landmarks_active is intentionally not a failure: OpenCV/dlib geometry can
        # still generate with review when face-alignment-master is not cached.
    else:
        if coverage is None or coverage < SUBJECT_MIN_COVERAGE or coverage > SUBJECT_MAX_COVERAGE:
            failures.append(GateFailure("subject_coverage_percent", coverage, f"{SUBJECT_MIN_COVERAGE}-{SUBJECT_MAX_COVERAGE}", "Subject coverage is outside the production range."))
        if quality is None or quality < SUBJECT_MIN_REFERENCE_QUALITY:
            failures.append(GateFailure("reference_quality_score", quality, SUBJECT_MIN_REFERENCE_QUALITY, "Reference quality is below production threshold."))
        if preservation is None or preservation < SUBJECT_MIN_PRESERVATION:
            failures.append(GateFailure("subject_preservation_score", preservation, SUBJECT_MIN_PRESERVATION, "Subject preservation score is below production threshold."))

    # Old UI builds could leave `generation_gate blocked` inside an otherwise
    # valid prompt (for example coverage 18.8% or 22.7% with 100/100 identity).
    # Do not block solely because of that stale text; block it only when the
    # current production metrics also fail.
    if gate_blocked and failures:
        failures.insert(0, GateFailure("generation_gate", "blocked", "allowed", "Generation gate is explicitly blocked."))
    elif gate_blocked and not failures:
        # Metrics are now authoritative; stale prompt text is treated as allowed.
        pass

    if failures:
        if is_person:
            return GateResult(False, "blocked", "REFERENCE_NOT_READY_FOR_IDENTITY_LOCK", "retake_or_crop_closer", failures)
        return GateResult(True, "allowed_with_warnings", "REFERENCE_WEAK_BUT_ALLOWED_WITH_AUTOCROP", "auto_crop_or_review", failures)

    return GateResult(True, "allowed", "REFERENCE_READY", "none", [])
