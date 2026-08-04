"""Shared deterministic evidence-support thresholds for stable scoring."""

from __future__ import annotations


def classify_verified_evidence_support(
    *,
    coverage: float,
    best_similarity: float,
    strong_evidence_count: int,
    has_matched_skills: bool,
) -> str:
    """Return the existing Phase 8 support label without adding score semantics."""
    if coverage >= 0.55 and (
        best_similarity >= 0.45 or has_matched_skills
    ):
        return "direct"
    if strong_evidence_count >= 1 or coverage >= 0.30:
        return "transferable"
    if (
        best_similarity >= 0.45
        or coverage >= 0.15
        or has_matched_skills
    ):
        return "weak"
    return "none"
