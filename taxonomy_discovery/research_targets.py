from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import Any, Iterable

from taxonomy_discovery.classification import (
    CLASS_B,
    CLASS_D,
    CLASS_E,
    CLASSIFICATION_VERSION,
)
from taxonomy_discovery.technology_registry import (
    TechnologyRegistry,
    get_default_registry,
    normalise,
)


RESEARCH_TARGET_VERSION = "tqd3-research-target-extraction-v1.2.0"

TARGET_TECHNOLOGY_RELATIONSHIP = "technology_relationship"
TARGET_TECHNOLOGY_IDENTITY = "technology_identity"
TARGET_CAPABILITY_CONCEPT = "capability_concept"

RESEARCH_TARGET_TYPES = (
    TARGET_TECHNOLOGY_RELATIONSHIP,
    TARGET_TECHNOLOGY_IDENTITY,
    TARGET_CAPABILITY_CONCEPT,
)

RESEARCH_QUESTION_VERSION = "tqd3-external-research-question-v1.0.0"

RESEARCH_QUERY_VERSION = "tqd3-provider-search-query-v1.0.0"


def _external_search_query(
    *,
    target_type: str,
    label: str,
) -> str:
    cleaned = _clean(label)
    if target_type == TARGET_TECHNOLOGY_IDENTITY:
        return (
            f'"{cleaned}" software engineering technology '
            "official documentation"
        )
    if target_type == TARGET_TECHNOLOGY_RELATIONSHIP:
        return (
            f'"{cleaned}" software engineering common use cases '
            "developer activities official documentation"
        )
    if target_type == TARGET_CAPABILITY_CONCEPT:
        return (
            f'"{cleaned}" software engineering capability '
            "responsibilities skills"
        )
    raise ValueError(f"Unsupported research target type: {target_type}")

_RESEARCH_PROFILES = {
    TARGET_TECHNOLOGY_IDENTITY: {
        "profile": "technology_identity_external_facts",
        "requested_facts": [
            "canonical_name",
            "entity_type",
            "primary_purpose",
            "maintainer_vendor_or_standards_body",
            "common_aliases",
            "ambiguity_notes",
        ],
    },
    TARGET_TECHNOLOGY_RELATIONSHIP: {
        "profile": "technology_relationship_external_facts",
        "requested_facts": [
            "canonical_name",
            "entity_type",
            "primary_use_cases",
            "reusable_engineering_activities",
            "adjacent_concepts",
        ],
    },
    TARGET_CAPABILITY_CONCEPT: {
        "profile": "capability_concept_external_facts",
        "requested_facts": [
            "standard_terminology",
            "scope",
            "common_tasks",
            "adjacent_concepts",
            "evidence_of_reuse",
        ],
    },
}


def _research_profile(target_type: str) -> dict[str, Any]:
    profile = _RESEARCH_PROFILES.get(target_type)
    if profile is None:
        raise ValueError(f"Unsupported research target type: {target_type}")
    return deepcopy(profile)


def _external_research_question(
    *,
    target_type: str,
    label: str,
) -> str:
    if target_type == TARGET_TECHNOLOGY_IDENTITY:
        return (
            f"What does the term '{label}' refer to in software engineering? "
            "Identify its canonical name, technology/entity type, primary "
            "purpose, maintainer/vendor or standards body when applicable, "
            "common aliases, and any important ambiguity. Use external facts "
            "only. Do not decide whether it belongs in any internal taxonomy "
            "or technology registry."
        )

    if target_type == TARGET_TECHNOLOGY_RELATIONSHIP:
        return (
            f"What is the known technology '{label}' primarily used for in "
            "software engineering? Identify its canonical technology/entity "
            "type, common use cases, the reusable engineering activities "
            "practitioners perform when using it, and adjacent concepts. "
            "Use external facts only. Do not decide any internal capability "
            "mapping, taxonomy relationship, or registry relationship."
        )

    if target_type == TARGET_CAPABILITY_CONCEPT:
        return (
            f"In software engineering and technical job descriptions, what "
            f"reusable work capability does the requirement '{label}' "
            "describe? Identify standard terminology, scope, common tasks, "
            "and closely related concepts, and provide evidence that the "
            "concept is reused across contexts. Use external facts only. "
            "Do not decide whether it is distinct from or should be added to "
            "any internal taxonomy."
        )

    raise ValueError(f"Unsupported research target type: {target_type}")

_TECH_CONTEXT_MARKERS = (
    "knowledge of",
    "experience with",
    "familiar with",
    "comfortable using",
    "using",
    "programming",
    "language",
    "languages",
    "framework",
    "frameworks",
    "database",
    "databases",
    "technology",
    "technologies",
    "runtime",
    "runtimes",
    "platform",
    "platforms",
    "protocol",
    "protocols",
    "tool",
    "tools",
)

_GENERIC_TECH_LIST_STOP = {
    "advantage",
    "common",
    "development",
    "experience",
    "framework",
    "frameworks",
    "knowledge",
    "preferred",
    "software",
    "technology",
    "technologies",
    "tool",
    "tools",
    "using",
}

_STRICT_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    r"(?:[A-Z][A-Z0-9]{1,9})"
    r"|(?:[A-Za-z][A-Za-z0-9]*[+#]{1,2})"
    r"|(?:[A-Za-z]+(?:\.[A-Za-z0-9]+)+)"
    r"|(?:[A-Z][a-z]+[A-Z][A-Za-z0-9]*)"
    r")(?![A-Za-z0-9])"
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _candidate_text(candidate: dict[str, Any]) -> str:
    observed = candidate.get("observed_terms", []) or []
    for value in observed:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return _clean(candidate.get("normalised_observed_text"))


def _stable_id(target_type: str, key: str) -> str:
    digest = hashlib.sha256(
        f"{RESEARCH_TARGET_VERSION}|{target_type}|{key}".encode("utf-8")
    ).hexdigest()[:20]
    return f"tqdrt_{digest}"


def _registry_alias_index(
    registry: TechnologyRegistry,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in registry.entries:
        if not isinstance(entry, dict):
            continue
        technology_id = _clean(entry.get("technology_id"))
        for alias in entry.get("aliases", []) or []:
            alias_text = _clean(alias)
            alias_key = normalise(alias_text)
            if alias_key and technology_id:
                index[alias_key] = {
                    "technology_id": technology_id,
                    "technology_label": _clean(entry.get("label")),
                    "alias": alias_text,
                }
    return index


def _known_alias_mentions(
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    result = candidate.get("tqd3_classification", {}) or {}
    signals = result.get("signals", {}) or {}
    rows = signals.get("registry_alias_mentions", []) or []
    return [
        dict(row)
        for row in rows
        if isinstance(row, dict)
    ]


def _has_tech_context(text: str) -> bool:
    normalized = normalise(text)
    return any(
        marker in normalized
        for marker in _TECH_CONTEXT_MARKERS
    )


def _strict_unknown_terms(
    text: str,
    *,
    registry: TechnologyRegistry,
) -> list[str]:
    """Extract only conservative technology-shaped unknown tokens.

    This is a research routing heuristic, not a production registry decision.
    """
    if not _has_tech_context(text):
        return []

    alias_index = _registry_alias_index(registry)
    found: dict[str, str] = {}

    for match in _STRICT_TOKEN_RE.finditer(text):
        token = _clean(match.group(1))
        key = normalise(token)
        if not key or key in alias_index:
            continue
        if key in _GENERIC_TECH_LIST_STOP:
            continue
        found[key] = token

    # Once a known technology anchors a comma/and-separated list, admit
    # adjacent simple technology-like names from the same bounded list.
    # This lets a row such as "C#, Java, Javascript, HTML5 and Python"
    # produce research identities without treating arbitrary title-case
    # prose as technology.
    known_mentions = _known_alias_mentions_from_registry_text(
        text,
        registry=registry,
    )
    if known_mentions:
        segment = text
        for prefix in (
            "knowledge of ",
            "experience with ",
            "familiar with ",
            "comfortable using ",
            "using ",
        ):
            idx = segment.lower().find(prefix)
            if idx >= 0:
                segment = segment[idx + len(prefix):]
                break
        segment = re.split(
            r"\b(?:is|are)\s+(?:an?\s+)?(?:advantage|preferred|desired)\b",
            segment,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        parts = re.split(r",|/|\band\b", segment, flags=re.IGNORECASE)
        for part in parts:
            token = _clean(part).strip("().:;")
            token = re.sub(
                r"^(?:and|or|other)\s+",
                "",
                token,
                flags=re.IGNORECASE,
            ).strip()
            if not token or " " in token:
                continue
            key = normalise(token)
            if not key or key in alias_index:
                continue
            if key in _GENERIC_TECH_LIST_STOP:
                continue
            if len(token) < 2 or len(token) > 30:
                continue
            found[key] = token

    return [
        found[key]
        for key in sorted(found)
    ]


def _known_alias_mentions_from_registry_text(
    text: str,
    *,
    registry: TechnologyRegistry,
) -> list[dict[str, Any]]:
    normalized = f" {normalise(text)} "
    rows: list[dict[str, Any]] = []
    for entry in registry.entries:
        if not isinstance(entry, dict):
            continue
        technology_id = _clean(entry.get("technology_id"))
        for alias in entry.get("aliases", []) or []:
            alias_text = _clean(alias)
            alias_key = normalise(alias_text)
            if alias_key and f" {alias_key} " in normalized:
                rows.append(
                    {
                        "technology_id": technology_id,
                        "technology_label": _clean(entry.get("label")),
                        "alias": alias_text,
                    }
                )
                break
    rows.sort(
        key=lambda row: (
            row["technology_id"],
            normalise(row["alias"]),
        )
    )
    return rows


def _base_target(
    *,
    target_type: str,
    target_key: str,
    label: str,
    research_question: str,
    source_class_id: str,
    candidate: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    profile = _research_profile(target_type)
    return {
        "research_target_version": RESEARCH_TARGET_VERSION,
        "research_question_version": RESEARCH_QUESTION_VERSION,
        "research_query_version": RESEARCH_QUERY_VERSION,
        "research_profile": profile["profile"],
        "requested_facts": list(profile["requested_facts"]),
        "search_query": _external_search_query(
            target_type=target_type,
            label=label,
        ),
        "target_id": _stable_id(target_type, target_key),
        "target_type": target_type,
        "target_key": target_key,
        "label": label,
        "research_question": research_question,
        "source_class_id": source_class_id,
        "source_candidate_ids": [
            _clean(candidate.get("candidate_id"))
        ],
        "source_terms": [_candidate_text(candidate)],
        "source_job_count": int(candidate.get("job_count") or 0),
        "source_observation_count": int(
            candidate.get("observation_count") or 0
        ),
        "routing_reason": reason,
        "tavily_eligible": True,
        "requires_human_review": True,
        "mutates_taxonomy": False,
        "mutates_registry": False,
        "influences_scoring": False,
    }


def extract_research_targets_for_candidate(
    candidate: dict[str, Any],
    *,
    registry: TechnologyRegistry | None = None,
) -> list[dict[str, Any]]:
    """Create deterministic, focused research units from one TQ-D3 candidate."""
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a dictionary")

    registry = registry or get_default_registry()
    classification = candidate.get("tqd3_classification", {}) or {}
    class_id = _clean(classification.get("class_id"))
    text = _candidate_text(candidate)

    if not class_id:
        return []

    # D is explicitly excluded from external research.
    if class_id == CLASS_D:
        return []

    targets: list[dict[str, Any]] = []

    # Known registry aliases that are recognized but have no approved mapping
    # become relationship-research targets. Already-mapped aliases are excluded.
    if class_id == CLASS_B:
        for row in _known_alias_mentions(candidate):
            if row.get("mapping_status") != "recognized_unmapped":
                continue
            technology_id = _clean(row.get("technology_id"))
            label = _clean(row.get("technology_label")) or technology_id
            if not technology_id:
                continue
            targets.append(
                _base_target(
                    target_type=TARGET_TECHNOLOGY_RELATIONSHIP,
                    target_key=technology_id,
                    label=label,
                    research_question=_external_research_question(
                        target_type=TARGET_TECHNOLOGY_RELATIONSHIP,
                        label=label,
                    ),
                    source_class_id=class_id,
                    candidate=candidate,
                    reason="known_registry_technology_without_approved_mapping",
                )
            )

    # B and U may reveal strict unknown technology terms. This creates only a
    # research question; it does not add a registry entry or influence scoring.
    if class_id in {CLASS_B, "U_unclassified"}:
        for term in _strict_unknown_terms(
            text,
            registry=registry,
        ):
            key = normalise(term)
            targets.append(
                _base_target(
                    target_type=TARGET_TECHNOLOGY_IDENTITY,
                    target_key=key,
                    label=term,
                    research_question=_external_research_question(
                        target_type=TARGET_TECHNOLOGY_IDENTITY,
                        label=term,
                    ),
                    source_class_id=class_id,
                    candidate=candidate,
                    reason="strict_unknown_technology_shaped_term",
                )
            )

    if class_id == CLASS_E:
        concept_key = normalise(
            candidate.get("normalised_observed_text") or text
        )
        if concept_key:
            targets.append(
                _base_target(
                    target_type=TARGET_CAPABILITY_CONCEPT,
                    target_key=concept_key,
                    label=text or concept_key,
                    research_question=_external_research_question(
                        target_type=TARGET_CAPABILITY_CONCEPT,
                        label=text or concept_key,
                    ),
                    source_class_id=class_id,
                    candidate=candidate,
                    reason="recurrent_new_capability_research_candidate",
                )
            )

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in targets:
        key = (
            str(row.get("target_type") or ""),
            str(row.get("target_key") or ""),
        )
        unique[key] = row

    return [
        unique[key]
        for key in sorted(unique)
    ]


def build_research_target_report(
    classification_report: dict[str, Any],
    *,
    registry: TechnologyRegistry | None = None,
) -> dict[str, Any]:
    """Aggregate focused TQ-D3 research targets deterministically."""
    if not isinstance(classification_report, dict):
        raise TypeError("classification_report must be a dictionary")

    registry = registry or get_default_registry()
    aggregated: dict[tuple[str, str], dict[str, Any]] = {}

    candidates = [
        row
        for row in classification_report.get("candidates", []) or []
        if isinstance(row, dict)
    ]
    candidates.sort(
        key=lambda row: (
            _clean(row.get("candidate_id")),
            _candidate_text(row),
        )
    )

    for candidate in candidates:
        for target in extract_research_targets_for_candidate(
            candidate,
            registry=registry,
        ):
            key = (
                str(target.get("target_type") or ""),
                str(target.get("target_key") or ""),
            )
            existing = aggregated.get(key)
            if existing is None:
                aggregated[key] = deepcopy(target)
                continue

            existing["source_candidate_ids"] = sorted(
                set(existing.get("source_candidate_ids", []) or [])
                | set(target.get("source_candidate_ids", []) or [])
            )
            existing["source_terms"] = sorted(
                set(existing.get("source_terms", []) or [])
                | set(target.get("source_terms", []) or []),
                key=lambda value: (normalise(value), value.casefold(), value),
            )
            existing["source_job_count"] = int(
                existing.get("source_job_count", 0) or 0
            ) + int(target.get("source_job_count", 0) or 0)
            existing["source_observation_count"] = int(
                existing.get("source_observation_count", 0) or 0
            ) + int(target.get("source_observation_count", 0) or 0)

    targets = [
        aggregated[key]
        for key in sorted(aggregated)
    ]

    type_counts = {
        target_type: 0
        for target_type in RESEARCH_TARGET_TYPES
    }
    for row in targets:
        type_counts[str(row["target_type"])] += 1

    return {
        "research_target_version": RESEARCH_TARGET_VERSION,
        "source_classification_version": (
            classification_report.get("classification_version")
            or CLASSIFICATION_VERSION
        ),
        "technology_registry_version": registry.version,
        "candidate_count": len(candidates),
        "target_count": len(targets),
        "type_counts": type_counts,
        "targets": targets,
        "governance": {
            "tavily_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "taxonomy_mutations": 0,
            "registry_mutations": 0,
            "scoring_influence": False,
            "human_approval_required": True,
        },
    }
