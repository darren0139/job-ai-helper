"""Optional Phase 6D validation adapter for Phase 6A stable scoring.

This module is intentionally opt-in. Integrate it at the point where Phase 6A
has gathered candidate evidence but before it calculates the final score.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tailoring.capability_taxonomy import (
    evaluate_capability_evidence,
    evaluate_evidence,
    get_default_taxonomy,
)
from tailoring.phase6d5_retrieval import (
    build_capability_retrieval_trace,
)

from taxonomy_discovery.technology_registry import (
    resolve_requirement_text,
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
    *,
    retrieval_mode_override: str | None = None,
) -> dict[str, Any]:
    """Cap evidence using canonical taxonomy, then approved registry fallback.

    Registry resolution can make a JD requirement understandable, but it never
    upgrades candidate evidence. Existing match labels may only stay the same
    or be capped downward by the capability evidence policy.
    """
    row = deepcopy(requirement)
    evidence_text = "\n".join(
        str(item.get("text", ""))
        for item in row.get("evidence", []) or []
        if isinstance(item, dict)
    )
    structured_any_language_group = bool(
        row.get("structured_match_kind") == "programming_language_group"
        and row.get("structured_match_group_mode") == "any"
        and row.get("structured_match_status")
        in {"applied", "confirmed_existing_direct"}
    )
    if structured_any_language_group:
        row["capability_retrieval"] = build_capability_retrieval_trace(
            row, exact_capability_id=None,
            mode_override=retrieval_mode_override,
        )
        row["capability_taxonomy_cap_status"] = (
            "not_applicable_structured_any_language_group"
        )
        return row

    taxonomy = get_default_taxonomy()
    decision = evaluate_evidence(row, evidence_text, taxonomy)
    resolution_source = "canonical_taxonomy"
    registry_resolution: dict[str, Any] | None = None

    if decision.get("capability_id") is None:
        focus = str(row.get("atomic_focus") or row.get("text") or "")
        registry_resolution = resolve_requirement_text(focus)
        row["technology_registry_resolution"] = deepcopy(registry_resolution)
        if (
            registry_resolution.get("status") == "resolved"
            and registry_resolution.get("capability_id")
        ):
            decision = evaluate_capability_evidence(
                str(registry_resolution["capability_id"]),
                row, evidence_text, taxonomy,
            )
            resolution_source = "technology_registry"
        else:
            resolution_source = "unresolved"

    row["capability_retrieval"] = build_capability_retrieval_trace(
        row,
        exact_capability_id=decision.get("capability_id"),
        mode_override=retrieval_mode_override,
    )

    taxonomy_label = decision.get("label")
    current_label = str(row.get("match_label") or "none")
    if taxonomy_label is None:
        row["capability_taxonomy_cap_status"] = "unrecognised"
        row["capability_resolution_source"] = resolution_source
        return row

    row["capability_id"] = decision.get("capability_id")
    row["capability_taxonomy_version"] = decision.get("taxonomy_version")
    row["capability_does_not_prove"] = decision.get("does_not_prove", [])
    row["capability_resolution_source"] = resolution_source

    if registry_resolution is not None and resolution_source == "technology_registry":
        row["technology_registry_version"] = registry_resolution.get("registry_version")
        row["technology_registry_technology_id"] = registry_resolution.get("technology_id")
        row["technology_registry_relationship_type"] = registry_resolution.get("relationship_type")

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
    *,
    retrieval_mode_override: str | None = None,
) -> list[dict[str, Any]]:
    return [
        cap_requirement_with_taxonomy(
            item,
            retrieval_mode_override=retrieval_mode_override,
        )
        for item in requirements
        if isinstance(item, dict)
    ]
