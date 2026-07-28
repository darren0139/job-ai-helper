"""Phase 6D adapter for Phase 6B.1 deterministic project evidence mapping."""

from __future__ import annotations

from typing import Any

from tailoring.capability_taxonomy import (
    capability_anchors,
    evaluate_evidence,
    get_default_taxonomy,
)


def taxonomy_evidence_anchors() -> dict[str, set[str]]:
    return capability_anchors(get_default_taxonomy())


def match_requirement_to_candidate(
    *,
    requirement: dict[str, Any],
    candidate_evidence_text: str,
) -> dict[str, Any]:
    """Return a deterministic taxonomy-owned match decision."""
    return evaluate_evidence(
        requirement,
        candidate_evidence_text,
        get_default_taxonomy(),
    )
