"""Pure production taxonomy and technology-registry requirement resolution."""

from __future__ import annotations

from typing import Any

from tailoring.capability_taxonomy import (
    classify_requirement_diagnostics,
    classify_requirement_fallback_diagnostics,
    evaluate_capability_evidence,
    get_default_taxonomy,
    strip_leading_alpha_list_marker,
)
from taxonomy_discovery.technology_registry import resolve_requirement_text
from tailoring.requirement_scope import technology_identity_scope


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

    identity = None
    knowledge_status = "CAPABILITY_RESOLVED" if decision.get("capability_id") else "UNRESOLVED"
    if knowledge_status == "UNRESOLVED":
        identity = technology_identity_scope(requirement)
        if identity["identity_resolved"]:
            knowledge_status = "TECHNOLOGY_IDENTITY_RESOLVED"
            resolution_source = "technology_identity"
    identities = (identity or {}).get("identities", [])
    recognition_rule=None
    if knowledge_status=='UNRESOLVED':
        fallback=classify_requirement_fallback_diagnostics(requirement,taxonomy)
        if fallback:
            taxonomy_diagnostics=fallback
            recognition_rule=fallback['recognition_rule']
            decision=evaluate_capability_evidence(fallback['capability_id'],requirement,evidence_text,taxonomy)
            knowledge_status='CAPABILITY_RESOLVED'
            resolution_source='canonical_taxonomy'
    primary = identities[0] if len(identities) == 1 else (registry_resolution or {})
    return {
        "status": "resolved" if knowledge_status != "UNRESOLVED" else "unresolved",
        "knowledge_status": knowledge_status,
        "knowledge_outcome": "RESOLVED_BY_TECHNOLOGY_IDENTITY" if knowledge_status == "TECHNOLOGY_IDENTITY_RESOLVED" else knowledge_status,
        "technology_id": primary.get("technology_id"),
        "technology_label": primary.get("technology_label"),
        "matched_alias": primary.get("matched_alias"),
        "matched_term": primary.get("matched_term"),
        "identity_scope": identity,
        "resolution_source": resolution_source,
        "decision": decision,
        "registry_resolution": registry_resolution,
        "taxonomy_diagnostics": taxonomy_diagnostics,
        "recognition_rule": recognition_rule,
    }
