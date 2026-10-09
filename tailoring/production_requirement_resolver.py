"""Pure production taxonomy and technology-registry requirement resolution."""

from __future__ import annotations

from typing import Any

from tailoring.capability_taxonomy import (
    classify_requirement_diagnostics,
    evaluate_capability_evidence,
    get_default_taxonomy,
    strip_leading_alpha_list_marker,
)
from taxonomy_discovery.technology_registry import resolve_requirement_text


def resolve_requirement_with_production_knowledge(
    requirement: dict[str, Any],
    *,
    evidence_text: str = "",
) -> dict[str, Any]:
    """Resolve using the production taxonomy, then approved registry fallback.

    The helper stops before retrieval, evidence-label mutation, scoring, or
    persistence.  Production scoring and read-only diagnostics share it.
    """
    taxonomy = get_default_taxonomy()
    taxonomy_diagnostics = classify_requirement_diagnostics(
        requirement, taxonomy
    )
    capability = taxonomy_diagnostics.get("capability_record")
    registry_resolution: dict[str, Any] | None = None

    if capability is not None:
        decision = evaluate_capability_evidence(
            str(capability["capability_id"]),
            requirement,
            evidence_text,
            taxonomy,
        )
        resolution_source = "canonical_taxonomy"
    else:
        focus = str(
            requirement.get("atomic_focus") or requirement.get("text") or ""
        )
        focus = strip_leading_alpha_list_marker(focus)
        registry_resolution = resolve_requirement_text(focus)
        # Additional identity diagnostics only. Parent status, capability decision,
        # evidence labels and scoring weights remain governed by existing contracts.
        from tailoring.phase6d6_structured_matching import technology_requirement_structure
        structure = technology_requirement_structure(requirement)
        if structure["components"]:
            registry_resolution["native_component_resolution"] = {
                **structure, "components": [{**component,
                    "registry_resolution": resolve_requirement_text(component["atomic_focus"])}
                    for component in structure["components"]],
                "parent_resolution_inferred": False,
            }
        if (
            registry_resolution.get("status") == "resolved"
            and registry_resolution.get("capability_id")
        ):
            decision = evaluate_capability_evidence(
                str(registry_resolution["capability_id"]),
                requirement,
                evidence_text,
                taxonomy,
            )
            resolution_source = "technology_registry"
        else:
            decision = {
                "capability_id": None,
                "label": None,
                "reason": "unrecognised_capability",
                "concepts": [],
                "taxonomy_version": taxonomy.version,
                "does_not_prove": [],
            }
            resolution_source = "unresolved"

    return {
        "resolution_source": resolution_source,
        "decision": decision,
        "registry_resolution": registry_resolution,
        "taxonomy_diagnostics": taxonomy_diagnostics,
    }
