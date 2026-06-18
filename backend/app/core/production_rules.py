"""Central production readiness rules for AI Studio Pro.

The backend is the source of truth. Frontend checks improve UX only; these
thresholds must still be enforced server-side before any source-locked generation.
"""
from __future__ import annotations

# Person / identity generation gate
# 18% is the real minimum for a clean head-and-shoulders reference.
# 24% remains the recommended premium target, but it must not block an
# otherwise sharp, single-face, FAN-landmarked capture like 18.8%/22.7%.
FACE_MIN_COVERAGE_FOR_GENERATION = 14.0
FACE_TARGET_COVERAGE_FOR_PREMIUM_IDENTITY = 24.0
FACE_MIN_IDENTITY_RELIABILITY = 90
FACE_MIN_GENERATION_CONFIDENCE = 90
FACE_REQUIRE_SINGLE_FACE = True
FACE_REQUIRE_LANDMARKS = True

# Universal subject gate
SUBJECT_MIN_REFERENCE_QUALITY = 55
SUBJECT_MIN_PRESERVATION = 55
SUBJECT_MIN_COVERAGE = 8.0
SUBJECT_MAX_COVERAGE = 92.0

# Safety rule: never fall back to text-to-image when a source lock is requested.
ALLOW_TEXT_FALLBACK_WHEN_REFERENCE_LOCKED = False
