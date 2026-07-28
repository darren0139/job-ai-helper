"""Optional Phase 6D validation adapter for Phase 6A stable scoring.

This module is intentionally opt-in. Integrate it at the point where Phase 6A
has gathered candidate evidence but before it calculates the final score.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tailoring.capability_taxonomy import evaluate_evidence, get_default_taxonomy
from tailoring.phase6d5_retrieval import (
    build_capability_retrieval_trace,
)

_LABEL_ORDER = {"none": 0, "weak": 1, "transferable": 2, "direct": 3}
_LABEL_VALUE = {"none": 0.0, "weak": 0.20, "transferable": 0.55, "direct": 1.0}
_EVIDENCE_STRENGTH_CAP = {
    "none": 0,
    "weak": 2,
    "transferable": 3,
    "direct": 5,
}


def cap_requirement_with_taxonomy(
    requirement: dict[str, Any],
) -> dict[str, Any]:
    """Cap an existing stable requirement label using its own cited evidence."""
    row = deepcopy(requirement)
    evidence_text = "\n".join(
        str(item.get("text", ""))
        for item in row.get("evidence", []) or []
        if isinstance(item, dict)
    )
    decision = evaluate_evidence(
        row,
        evidence_text,
        get_default_taxonomy(),
    )

    row["capability_retrieval"] = (
        build_capability_retrieval_trace(
            row,
            exact_capability_id=decision.get(
                "capability_id"
            ),
        )
    )

    taxonomy_label = decision.get("label")
    current_label = str(row.get("match_label") or "none")
    if taxonomy_label is None:
        row["capability_taxonomy_cap_status"] = "unrecognised"
        return row

    row["capability_id"] = decision.get("capability_id")
    row["capability_taxonomy_version"] = decision.get("taxonomy_version")
    row["capability_does_not_prove"] = decision.get("does_not_prove", [])

    # Canonicalisation uses is_atomic=True for clauses created by splitting,
    # but a standalone one-capability requirement can legitimately retain
    # is_atomic=False. Phase 6A performs compound-clause splitting before this
    # adapter runs, so do not skip a row solely because is_atomic is false.

    if _LABEL_ORDER.get(taxonomy_label, 0) < _LABEL_ORDER.get(current_label, 0):
        row["match_label"] = taxonomy_label
        row["match_value"] = _LABEL_VALUE[taxonomy_label]
        current_strength = int(row.get("evidence_strength", 0) or 0)
        row["evidence_strength"] = min(
            current_strength,
            _EVIDENCE_STRENGTH_CAP[taxonomy_label],
        )
        row["capability_taxonomy_cap_status"] = "applied"
        row.setdefault("validation_warnings", []).append(
            {
                "code": "taxonomy_cap_applied",
                "message": (
                    f"Phase 6D capped {current_label} to {taxonomy_label}: "
                    f"{decision.get('reason', 'taxonomy rule')}."
                ),
            }
        )
    else:
        row["capability_taxonomy_cap_status"] = "not_needed"

    return row


def apply_taxonomy_caps_to_requirements(
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        cap_requirement_with_taxonomy(item)
        for item in requirements
        if isinstance(item, dict)
    ]
