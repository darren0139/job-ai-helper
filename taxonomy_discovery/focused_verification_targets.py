from __future__ import annotations

import hashlib
import json
from typing import Any


FOCUSED_VERIFICATION_TARGET_VERSION = (
    "tqd3-focused-verification-targets-v1.0.0"
)

TARGET_REGISTRY_RELATIONSHIP = (
    "technology_registry_relationship"
)
TARGET_TECHNOLOGY_IDENTITY = (
    "technology_identity"
)
TARGET_IDENTITY_DISAMBIGUATION = (
    "technology_identity_disambiguation"
)
RELATIONSHIP_FOLLOWUP_VERSION = (
    "tqd3-focused-relationship-followup-v1.0.0"
)


def _stable_target_id(
    *,
    candidate_id: str,
    route: str,
) -> str:
    payload = (
        FOCUSED_VERIFICATION_TARGET_VERSION
        + "|"
        + candidate_id.strip()
        + "|"
        + route.strip()
    )
    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:24]
    return "tqd3verify_" + digest


def _taxonomy_capabilities(
    item: dict[str, Any],
) -> list[str]:
    values = item.get(
        "taxonomy_capabilities"
    )
    values = (
        values
        if isinstance(values, list)
        else []
    )
    return sorted(
        {
            str(value).strip()
            for value in values
            if str(value).strip()
        }
    )


def _route_for_ready_item(
    item: dict[str, Any],
) -> str:
    status = str(
        item.get("candidate_status") or ""
    )
    capabilities = _taxonomy_capabilities(
        item
    )

    if status == "ambiguous_registry_match":
        return TARGET_IDENTITY_DISAMBIGUATION

    if capabilities:
        return TARGET_REGISTRY_RELATIONSHIP

    return TARGET_TECHNOLOGY_IDENTITY


def _questions_for_target(
    *,
    canonical_name: str,
    route: str,
    capability_ids: list[str],
) -> list[str]:
    if route == TARGET_REGISTRY_RELATIONSHIP:
        capability_text = ", ".join(
            capability_ids
        )
        return [
            (
                f"Confirm the canonical technology identity for "
                f"{canonical_name}, including official project/product "
                "name, maintainer or standards body, and authoritative "
                "first-party sources."
            ),
            (
                f"Determine whether {canonical_name} should have a "
                "technology-registry entry and whether an approved "
                f"relationship to the existing capability "
                f"{capability_text} is justified."
            ),
            (
                "Identify safe aliases that refer to the same technology "
                "identity without broadening into related but distinct "
                "products, frameworks, services, or concepts."
            ),
        ]

    if route == TARGET_IDENTITY_DISAMBIGUATION:
        return [
            (
                f"Disambiguate the canonical identity of "
                f"{canonical_name} against the exact registry matches "
                "that caused ambiguity."
            ),
            (
                "Identify authoritative first-party sources and safe "
                "canonical aliases for the resolved identity."
            ),
            (
                "Do not infer a capability relationship until the "
                "technology identity is resolved."
            ),
        ]

    return [
        (
            f"Confirm the canonical technology identity for "
            f"{canonical_name}, including what it is, official "
            "maintainer/vendor/standards body, and authoritative "
            "first-party sources."
        ),
        (
            f"Identify safe aliases for {canonical_name} that refer to "
            "the same technology identity."
        ),
        (
            "Determine whether the technology is already represented by "
            "an existing capability concept or whether relationship "
            "research is still required."
        ),
    ]


def build_focused_verification_target(
    item: dict[str, Any],
) -> dict[str, Any]:
    candidate_id = str(
        item.get("candidate_id") or ""
    ).strip()
    canonical_name = str(
        item.get("canonical_name") or ""
    ).strip()

    if not candidate_id:
        raise ValueError(
            "candidate_id is required"
        )
    if not canonical_name:
        raise ValueError(
            "canonical_name is required"
        )

    bucket = str(
        item.get("bucket") or ""
    )
    if bucket != "confirmed":
        raise ValueError(
            "focused verification targets require "
            "a confirmed/ready-to-verify candidate"
        )

    capability_ids = (
        _taxonomy_capabilities(item)
    )
    route = _route_for_ready_item(item)

    target_id = _stable_target_id(
        candidate_id=candidate_id,
        route=route,
    )

    return {
        "target_version":
            FOCUSED_VERIFICATION_TARGET_VERSION,
        "target_id": target_id,
        "candidate_id": candidate_id,
        "canonical_name": canonical_name,
        "route": route,
        "taxonomy_capability_ids":
            capability_ids,
        "source_summary": {
            "supporting_sources": int(
                item.get(
                    "supporting_sources",
                    0,
                )
                or 0
            ),
            "current_review": str(
                item.get("current_review")
                or ""
            ),
            "friendly_reason": str(
                item.get("friendly_reason")
                or ""
            ),
        },
        "questions": _questions_for_target(
            canonical_name=canonical_name,
            route=route,
            capability_ids=capability_ids,
        ),
        "research_policy": {
            "focused": True,
            "broad_mining": False,
            "explicit_execution_required":
                True,
            "preferred_source_order": [
                "official_project_or_product",
                "official_vendor_or_standards_body",
                "high_quality_secondary",
            ],
        },
        "governance": {
            "generated_from_confirmed_candidate":
                True,
            "network_calls": 0,
            "model_calls": 0,
            "automatic_research": False,
            "proposal_creation": False,
            "registry_mutations": 0,
            "taxonomy_mutations": 0,
            "scoring_influence": False,
        },
    }


def build_relationship_followup_target(
    *,
    source_target: dict[str, Any],
    capability_id: str,
) -> dict[str, Any]:
    """Create deterministic relationship research after identity verification.

    This creates research intent only. It performs no network call, proposal
    creation, registry/taxonomy mutation, scoring change, or approval.
    """
    from tailoring.capability_taxonomy import get_default_taxonomy

    source_target = (
        source_target
        if isinstance(source_target, dict)
        else {}
    )
    candidate_id = str(
        source_target.get("candidate_id") or ""
    ).strip()
    canonical_name = str(
        source_target.get("canonical_name") or ""
    ).strip()
    source_target_id = str(
        source_target.get("target_id") or ""
    ).strip()
    source_route = str(
        source_target.get("route") or ""
    ).strip()
    capability_id = str(capability_id or "").strip()

    if not candidate_id or not canonical_name or not source_target_id:
        raise ValueError(
            "relationship follow-up requires a complete verified identity target"
        )
    if source_route not in {
        TARGET_TECHNOLOGY_IDENTITY,
        TARGET_IDENTITY_DISAMBIGUATION,
    }:
        raise ValueError(
            "relationship follow-up must originate from an identity target"
        )

    taxonomy = get_default_taxonomy()
    capability = taxonomy.by_id().get(capability_id)
    if capability is None:
        raise ValueError(
            f"unknown existing capability_id: {capability_id!r}"
        )

    capability_label = str(
        capability.get("label") or capability_id
    ).strip()
    identity = "|".join(
        [
            RELATIONSHIP_FOLLOWUP_VERSION,
            source_target_id,
            candidate_id,
            canonical_name,
            capability_id,
        ]
    )
    target_id = (
        "tqd3verifyrel_"
        + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:24]
    )

    questions = [
        (
            f"Confirm the canonical technology identity for {canonical_name} "
            "using authoritative first-party sources."
        ),
        (
            f"Determine whether {canonical_name} directly provides, implements, "
            f"or is an instance of the existing capability {capability_id} "
            f"({capability_label}). Do not infer the relationship from name "
            "similarity, co-occurrence, popularity, or the human selection alone."
        ),
        (
            "Return first-party evidence specific to the proposed relationship "
            "and identify only safe same-identity aliases."
        ),
    ]

    return {
        "target_version":
            FOCUSED_VERIFICATION_TARGET_VERSION,
        "relationship_followup_version":
            RELATIONSHIP_FOLLOWUP_VERSION,
        "target_id": target_id,
        "candidate_id": candidate_id,
        "canonical_name": canonical_name,
        "route": TARGET_REGISTRY_RELATIONSHIP,
        "taxonomy_capability_ids": [
            capability_id
        ],
        "followup_of_target_id":
            source_target_id,
        "source_summary": {
            "supporting_sources": int(
                (
                    source_target.get(
                        "source_summary"
                    )
                    or {}
                ).get(
                    "supporting_sources",
                    0,
                )
                or 0
            ),
            "current_review":
                "verified_identity_relationship_followup",
            "friendly_reason": (
                "Technology identity was verified. A human selected an "
                "existing capability for focused relationship research; "
                "the selection itself is not evidence or approval."
            ),
        },
        "questions": questions,
        "research_policy": {
            "focused": True,
            "broad_mining": False,
            "explicit_execution_required": True,
            "preferred_source_order": [
                "official_project_or_product",
                "official_vendor_or_standards_body",
                "high_quality_secondary",
            ],
        },
        "governance": {
            "generated_from_confirmed_candidate":
                True,
            "generated_from_verified_identity":
                True,
            "human_selected_capability_id":
                capability_id,
            "selection_is_approval":
                False,
            "network_calls": 0,
            "model_calls": 0,
            "automatic_research": False,
            "proposal_creation": False,
            "registry_mutations": 0,
            "taxonomy_mutations": 0,
            "scoring_influence": False,
        },
    }


def build_focused_verification_targets(
    guided_summary: dict[str, Any],
) -> dict[str, Any]:
    items = guided_summary.get("items")
    items = (
        items
        if isinstance(items, list)
        else []
    )

    targets = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(
            item.get("bucket") or ""
        ) != "confirmed":
            continue
        targets.append(
            build_focused_verification_target(
                item
            )
        )

    targets.sort(
        key=lambda row: (
            row["canonical_name"].casefold(),
            row["target_id"],
        )
    )

    route_counts: dict[str, int] = {}
    for row in targets:
        route = str(row["route"])
        route_counts[route] = (
            route_counts.get(route, 0) + 1
        )

    return {
        "target_version":
            FOCUSED_VERIFICATION_TARGET_VERSION,
        "targets": targets,
        "count": len(targets),
        "route_counts": route_counts,
        "governance": {
            "network_calls": 0,
            "model_calls": 0,
            "automatic_research": False,
            "proposal_creation": False,
            "registry_mutations": 0,
            "taxonomy_mutations": 0,
            "scoring_influence": False,
        },
    }


def dump_focused_verification_targets_json(
    target_report: dict[str, Any],
) -> str:
    return json.dumps(
        target_report,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
