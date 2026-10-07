from __future__ import annotations

from copy import deepcopy
from typing import Any

from taxonomy_discovery.technology_registry import (
    TechnologyRegistry,
    get_default_registry,
    normalise,
)


CLASSIFICATION_VERSION = "tqd3-unresolved-requirement-classification-v1.0.0"

CLASS_A = "A_existing_capability_near_miss"
CLASS_B = "B_technology_or_registry"
CLASS_C = "C_decomposition_or_structure"
CLASS_D = "D_subjective_or_defer"
CLASS_E = "E_new_capability_research_candidate"
CLASS_U = "U_unclassified"

CLASSIFICATION_CLASSES = (
    CLASS_A,
    CLASS_B,
    CLASS_C,
    CLASS_D,
    CLASS_E,
    CLASS_U,
)

# Shadow retrieval can help route review, but never changes scoring.
NEAR_MISS_MIN_LEXICAL_SCORE = 0.40
NEAR_MISS_MIN_MARGIN = 0.10

# Deliberately small conservative phrase set. These rules route review only.
SUBJECTIVE_DEFER_PHRASES = (
    "ability to learn",
    "learn new software",
    "learn new technologies",
    "quick learner",
    "team player",
    "collaborative team environment",
    "keeping up to date",
    "keep up to date",
    "industry trends",
    "critical thinking",
    "creative problem solving",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_texts(candidate: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for value in candidate.get("observed_terms", []) or []:
        cleaned = _clean(value)
        if cleaned:
            values.append(cleaned)
    for observation in candidate.get("observations", []) or []:
        if not isinstance(observation, dict):
            continue
        cleaned = _clean(observation.get("requirement_text"))
        if cleaned:
            values.append(cleaned)
    fallback = _clean(candidate.get("normalised_observed_text"))
    if fallback:
        values.append(fallback)
    return sorted(set(values), key=lambda value: (normalise(value), value))


def _approved_mapping(entry: dict[str, Any]) -> dict[str, Any] | None:
    rows = [
        relationship
        for relationship in entry.get("capability_relationships", []) or []
        if isinstance(relationship, dict)
        and relationship.get("relationship_type") == "maps_to_capability"
        and relationship.get("status") == "approved"
    ]
    return rows[0] if len(rows) == 1 else None


def _registry_alias_mentions(
    candidate: dict[str, Any],
    registry: TechnologyRegistry,
) -> list[dict[str, Any]]:
    haystacks = [
        f" {normalise(text)} "
        for text in _candidate_texts(candidate)
        if normalise(text)
    ]
    mentions: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in registry.entries:
        technology_id = _clean(entry.get("technology_id"))
        if not technology_id:
            continue
        mapping = _approved_mapping(entry)
        for alias in entry.get("aliases", []) or []:
            alias_text = _clean(alias)
            alias_key = normalise(alias_text)
            if not alias_key:
                continue
            if not any(f" {alias_key} " in haystack for haystack in haystacks):
                continue
            mentions[(technology_id, alias_key)] = {
                "technology_id": technology_id,
                "technology_label": _clean(entry.get("label")),
                "alias": alias_text,
                "mapping_status": (
                    "mapped" if mapping is not None else "recognized_unmapped"
                ),
                "capability_id": (
                    _clean(mapping.get("capability_id"))
                    if mapping is not None
                    else None
                ),
            }
    return [mentions[key] for key in sorted(mentions)]


def _context_rows(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in candidate.get("observation_contexts", []) or []
        if isinstance(row, dict) and row.get("context_available")
    ]


def _subjective_signal(candidate: dict[str, Any]) -> tuple[bool, str]:
    contexts = _context_rows(candidate)
    if any(bool(row.get("explicit_only_requirement")) for row in contexts):
        return True, "explicit_only_requirement"

    normalized_texts = [normalise(text) for text in _candidate_texts(candidate)]
    for phrase in SUBJECTIVE_DEFER_PHRASES:
        needle = f" {normalise(phrase)} "
        if any(needle in f" {text} " for text in normalized_texts if text):
            return True, f"subjective_phrase:{normalise(phrase)}"
    return False, ""


def _near_miss(candidate: dict[str, Any]) -> dict[str, Any] | None:
    winners: list[dict[str, Any]] = []
    ambiguous_strong_context = False

    for context in _context_rows(candidate):
        retrieval = context.get("retrieval")
        if not isinstance(retrieval, dict):
            continue
        scored: list[tuple[float, str]] = []
        for raw in retrieval.get("candidates", []) or []:
            if not isinstance(raw, dict):
                continue
            score = _safe_float(raw.get("lexical_score"))
            capability_id = _clean(raw.get("capability_id"))
            if score is not None and capability_id:
                scored.append((score, capability_id))
        scored.sort(key=lambda row: (-row[0], row[1]))
        if not scored:
            continue
        top_score, top_id = scored[0]
        if top_score < NEAR_MISS_MIN_LEXICAL_SCORE:
            continue
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        margin = top_score - second_score
        if margin + 1e-12 < NEAR_MISS_MIN_MARGIN:
            ambiguous_strong_context = True
            continue
        winners.append(
            {
                "capability_id": top_id,
                "lexical_score": round(top_score, 6),
                "margin": round(margin, 6),
            }
        )

    if ambiguous_strong_context or not winners:
        return None
    capability_ids = {row["capability_id"] for row in winners}
    if len(capability_ids) != 1:
        return None
    strongest = sorted(
        winners,
        key=lambda row: (
            -float(row["lexical_score"]),
            -float(row["margin"]),
            row["capability_id"],
        ),
    )[0]
    return {**strongest, "supporting_context_count": len(winners)}


def _result(
    *,
    class_id: str,
    rule_id: str,
    rationale: str,
    signals: dict[str, Any],
    research_eligible: bool,
    next_action: str,
) -> dict[str, Any]:
    return {
        "classification_version": CLASSIFICATION_VERSION,
        "class_id": class_id,
        "rule_id": rule_id,
        "rationale": rationale,
        "signals": signals,
        "research_eligible": bool(research_eligible),
        "requires_human_review": True,
        "mutates_taxonomy": False,
        "mutates_registry": False,
        "influences_scoring": False,
        "next_action": next_action,
    }


def classify_unresolved_candidate(
    candidate: dict[str, Any],
    *,
    registry: TechnologyRegistry | None = None,
) -> dict[str, Any]:
    """Classify one persistent unresolved candidate without guessing or mutation."""
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a dictionary")

    registry = registry or get_default_registry()
    registry_resolution = candidate.get("technology_registry_resolution")
    registry_resolution = (
        registry_resolution if isinstance(registry_resolution, dict) else {}
    )
    registry_status = _clean(registry_resolution.get("status")) or "unresolved"
    alias_mentions = _registry_alias_mentions(candidate, registry)
    compound_possible = "possible_compound_requirement" in set(
        candidate.get("diagnostic_flags", []) or []
    )
    subjective, subjective_reason = _subjective_signal(candidate)
    near_miss = _near_miss(candidate)

    try:
        job_count = int(candidate.get("job_count") or 0)
    except (TypeError, ValueError):
        job_count = 0
    try:
        observation_count = int(candidate.get("observation_count") or 0)
    except (TypeError, ValueError):
        observation_count = 0

    signals = {
        "registry_status": registry_status,
        "registry_technology_id": _clean(
            registry_resolution.get("technology_id")
        ) or None,
        "registry_capability_id": _clean(
            registry_resolution.get("capability_id")
        ) or None,
        "registry_alias_mentions": alias_mentions,
        "possible_compound_requirement": compound_possible,
        "subjective_or_defer_signal": subjective,
        "subjective_or_defer_reason": subjective_reason or None,
        "near_miss": near_miss,
        "job_count": job_count,
        "observation_count": observation_count,
    }

    # Priority is deliberate: known technology beats generic compound routing.
    if registry_status in {"recognized_unmapped", "ambiguous"}:
        return _result(
            class_id=CLASS_B,
            rule_id=f"registry_{registry_status}",
            rationale="The technology registry has a non-final technology resolution.",
            signals=signals,
            research_eligible=(registry_status == "recognized_unmapped"),
            next_action=(
                "Review the technology relationship; any mapping requires explicit "
                "human approval."
            ),
        )

    if alias_mentions:
        research_needed = any(
            row.get("mapping_status") == "recognized_unmapped"
            for row in alias_mentions
        )
        return _result(
            class_id=CLASS_B,
            rule_id="known_registry_alias_in_unresolved_text",
            rationale=(
                "The unresolved text contains exact aliases already known by the "
                "technology registry."
            ),
            signals=signals,
            research_eligible=research_needed,
            next_action=(
                "Review registry/decomposition handling; do not change evidence "
                "credit from this classification."
            ),
        )

    if compound_possible:
        return _result(
            class_id=CLASS_C,
            rule_id="possible_compound_requirement",
            rationale="Existing deterministic diagnostics mark the candidate as compound.",
            signals=signals,
            research_eligible=False,
            next_action="Review JD decomposition/structure before adding taxonomy concepts.",
        )

    if subjective:
        return _result(
            class_id=CLASS_D,
            rule_id=subjective_reason or "subjective_or_defer",
            rationale=(
                "The requirement is explicit-only or matches a conservative "
                "subjective/general wording rule."
            ),
            signals=signals,
            research_eligible=False,
            next_action=(
                "Defer or require explicit candidate evidence; do not create generic "
                "technical coverage."
            ),
        )

    if near_miss is not None:
        return _result(
            class_id=CLASS_A,
            rule_id="strong_unambiguous_shadow_retrieval_near_miss",
            rationale=(
                "Shadow-only retrieval has one strong, unambiguous existing "
                "capability candidate."
            ),
            signals=signals,
            research_eligible=False,
            next_action=(
                "Review existing capability terminology/matcher coverage before "
                "proposing a new capability."
            ),
        )

    if job_count >= 2 and observation_count >= 2:
        return _result(
            class_id=CLASS_E,
            rule_id="recurrent_persistent_unresolved",
            rationale=(
                "The same normalized unresolved requirement recurs across multiple "
                "jobs without a stronger deterministic routing signal."
            ),
            signals=signals,
            research_eligible=True,
            next_action=(
                "Queue for external capability research; research output is proposal-only "
                "until human approval."
            ),
        )

    return _result(
        class_id=CLASS_U,
        rule_id="insufficient_deterministic_signal",
        rationale="The current deterministic evidence is insufficient to assign A-E.",
        signals=signals,
        research_eligible=False,
        next_action="Keep unresolved for human review or wait for recurrence.",
    )


def build_classification_report(
    enriched_report: dict[str, Any],
    *,
    registry: TechnologyRegistry | None = None,
) -> dict[str, Any]:
    """Build a stable TQ-D3 routing report over the TQ-D2.5 enriched report."""
    if not isinstance(enriched_report, dict):
        raise TypeError("enriched_report must be a dictionary")
    registry = registry or get_default_registry()

    candidates = [
        deepcopy(row)
        for row in enriched_report.get("candidates", []) or []
        if isinstance(row, dict)
    ]
    candidates.sort(
        key=lambda row: (
            _clean(row.get("candidate_id")),
            _clean(row.get("normalised_observed_text")),
        )
    )

    classified: list[dict[str, Any]] = []
    skipped_resolved = 0
    counts = {class_id: 0 for class_id in CLASSIFICATION_CLASSES}

    for candidate in candidates:
        resolution = candidate.get("technology_registry_resolution")
        resolution = resolution if isinstance(resolution, dict) else {}
        if _clean(resolution.get("status")) == "resolved":
            skipped_resolved += 1
            continue
        result = classify_unresolved_candidate(candidate, registry=registry)
        counts[result["class_id"]] += 1
        candidate["tqd3_classification"] = result
        classified.append(candidate)

    return {
        "classification_version": CLASSIFICATION_VERSION,
        "source_discovery_version": _clean(
            enriched_report.get("discovery_version")
        ) or None,
        "source_triage_version": _clean(
            enriched_report.get("triage_version")
        ) or None,
        "taxonomy_version": _clean(enriched_report.get("taxonomy_version")) or None,
        "technology_registry_version": registry.version,
        "input_candidate_count": len(candidates),
        "persistent_unresolved_candidate_count": len(classified),
        "skipped_registry_resolved_count": skipped_resolved,
        "research_queue_count": sum(
            1
            for candidate in classified
            if bool(
                (candidate.get("tqd3_classification") or {}).get("research_eligible")
            )
        ),
        "class_counts": counts,
        "candidates": classified,
        "governance": {
            "model_calls": 0,
            "network_calls": 0,
            "taxonomy_mutations": 0,
            "registry_mutations": 0,
            "scoring_influence": False,
            "human_approval_required": True,
        },
    }
