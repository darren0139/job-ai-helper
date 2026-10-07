"""Deterministic, zero-network preflight for governed TQ-D3 research."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.source_authority import (
    PRIMARY_OFFICIAL,
    candidate_official_domains,
    candidate_official_source_scopes,
    classify_candidate_source_url,
    load_source_authority_registry,
)
from taxonomy_discovery.technology_registry import get_default_registry, normalise, resolve_requirement_text


RESEARCH_READINESS_VERSION = "tqd3-research-readiness-v1.2.0"
BENCHMARK_VERSION = "tqd3-research-readiness-benchmark-v1"
READY = "ready"
ALREADY_RESOLVED = "already_resolved"
MISSING_AUTHORITY = "missing_official_authority_mapping"
QUERY_INCOMPLETE = "query_strategy_incomplete"
NEEDS_DECOMPOSITION = "needs_decomposition"
CACHED_CURRENT = "cached_current"
STALE_RESEARCH = "stale_research"
BLOCKED = "blocked"
MANUAL_REVIEW = "manual_review"
RELATIONSHIP_RESEARCH_READY = "relationship_research_ready"
IDENTITY_RESEARCH_READY = "identity_research_ready"
CAPABILITY_RESEARCH_READY = "capability_research_ready"
LOCAL_REVIEW_REQUIRED = "local_review_required"
BLOCKED_NOISE_OR_INSUFFICIENT = "blocked_noise_or_insufficient"

PAID_RESEARCH_READY_STATES = {
    RELATIONSHIP_RESEARCH_READY,
    IDENTITY_RESEARCH_READY,
    CAPABILITY_RESEARCH_READY,
}

_NON_OWNED_CONCEPT_KINDS = {
    "architecture_pattern",
    "capability",
    "concept",
    "methodology",
}

_BLOCKED_QUEUE_STATES = {
    "already_published", "already_rejected", "deferred", "blocked",
    "partial_resolution_decomposition_required", "stale_requires_refresh",
}

# Deterministic discovery hints fill known gaps in the existing entity detector.
# They identify review hypotheses only; they never establish identity or authority.
_IDENTITY_DISCOVERY_HINTS = (
    "SQL", "NoSQL", "Power BI", "Tableau", "ROS 2", "Bash", "R",
    "Fastify", "Spring Boot", "GitHub", "SLAM", "CI", "CD",
)
_GENERIC_IDENTITY_CONCEPTS = {"devops", "nosql", "ci", "cd", "slam"}


def benchmark_path() -> Path:
    return Path(__file__).resolve().parents[1] / "taxonomy" / "research_readiness_benchmark_v1.json"


def load_benchmark(path: str | Path | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or benchmark_path()).read_text(encoding="utf-8"))
    if (payload.get("benchmark_version") != BENCHMARK_VERSION
            or not isinstance(payload.get("technologies"), list)
            or not isinstance(payload.get("route_cases"), list)):
        raise ValueError("Unsupported research-readiness benchmark")
    return payload


def build_query_strategy(subject: str, official_domains: list[str] | tuple[str, ...], *, known_identity: bool) -> dict[str, Any]:
    """Build neutral first-party research intents; never assert a capability mapping."""
    subject = " ".join(str(subject or "").split()).strip()
    domains = sorted({str(value).lower().strip() for value in official_domains if str(value).strip()})
    if not subject or not domains:
        return {
            "ready": False,
            "strategy_version": RESEARCH_READINESS_VERSION,
            "queries": [],
            "primary_query": "",
            "fallback_queries": [],
            "include_domains": domains,
            "known_identity_skips_rediscovery": bool(known_identity),
            "maximum_queries": 3,
            "reason": "subject_or_governed_official_domain_missing",
        }
    queries = [
        f"official {subject} documentation overview",
        f"official {subject} what is",
        f"official {subject} documentation use cases architecture usage",
    ]
    return {
        "ready": True,
        "strategy_version": RESEARCH_READINESS_VERSION,
        "queries": queries,
        "primary_query": queries[0],
        "fallback_queries": queries[1:],
        "include_domains": domains,
        "known_identity_skips_rediscovery": bool(known_identity),
        "maximum_queries": 3,
        "reason": "governed_first_party_strategy_available",
    }


def build_identity_query_strategy(subject: str) -> dict[str, Any]:
    """Neutral, open-domain identity and authority discovery; no domain is pre-approved."""
    subject = " ".join(str(subject or "").split()).strip()
    queries = [] if not subject else [
        f"official {subject} documentation",
        f"official {subject} product framework tool canonical name maintainer",
        f"official {subject} site repository ownership",
    ]
    return {
        "ready": bool(queries),
        "strategy_version": RESEARCH_READINESS_VERSION,
        "queries": queries,
        "primary_query": queries[0] if queries else "",
        "fallback_queries": queries[1:],
        "include_domains": [],
        "known_identity_skips_rediscovery": False,
        "maximum_queries": 3,
        "authority_discovery": True,
        "discovered_domains_are_governed": False,
        "reason": "bounded_neutral_identity_and_authority_discovery" if queries else "concrete_identity_subject_missing",
    }


def build_capability_query_strategy(subject: str) -> dict[str, Any]:
    """Neutral concept-boundary research; never asserts that a capability should exist."""
    subject = " ".join(str(subject or "").split()).strip()
    queries = [] if not subject else [
        f"authoritative definition {subject} engineering practice",
        f"standards documentation {subject} scope boundaries",
        f"official guidance {subject} responsibilities evidence",
    ]
    return {
        "ready": bool(queries),
        "strategy_version": RESEARCH_READINESS_VERSION,
        "queries": queries,
        "primary_query": queries[0] if queries else "",
        "fallback_queries": queries[1:],
        "include_domains": [],
        "known_identity_skips_rediscovery": False,
        "maximum_queries": 3,
        "authority_discovery": False,
        "discovered_domains_are_governed": False,
        "reason": "bounded_authoritative_capability_boundary_research" if queries else "capability_subject_missing",
    }


def _approved_capability(entry: dict[str, Any]) -> str | None:
    return next((row.get("capability_id") for row in entry.get("capability_relationships", [])
                 if row.get("relationship_type") == "maps_to_capability" and row.get("status") == "approved"), None)


def _registry_entry(technology_id: str | None, registry=None) -> dict[str, Any] | None:
    if not technology_id:
        return None
    registry = registry or get_default_registry()
    return next((deepcopy(row) for row in registry.entries
                 if row.get("technology_id") == technology_id), None)


def _is_non_owned_concept(entry: dict[str, Any] | None) -> bool:
    return bool(entry and entry.get("entry_kind") in _NON_OWNED_CONCEPT_KINDS)


def _authority_details(label: str, aliases: list[str], *, authority_registry_path=None) -> dict[str, Any]:
    rules = load_source_authority_registry(authority_registry_path)
    keys = {normalise(value) for value in [label, *aliases] if str(value).strip()}
    matched = [row for row in rules.get("technology_domains", []) or []
               if keys.intersection(normalise(value) for value in row.get("technology_aliases", []) or [])]
    maintainers = sorted({str(row.get("maintainer") or "").strip() for row in matched if row.get("maintainer")})
    repositories = sorted({str(value).strip() for row in matched
                           for value in row.get("official_repositories", []) or [] if str(value).strip()})
    candidate = {"canonical_name": label}
    return {
        "official_domains": candidate_official_domains(candidate, registry_path=authority_registry_path),
        "official_source_scopes": candidate_official_source_scopes(candidate, registry_path=authority_registry_path),
        "official_repositories": repositories,
        "maintainers_vendors_or_standards_bodies": maintainers,
        "authority_registry_version": str(rules.get("version") or ""),
        "authority_rules_fingerprint": fingerprint(rules),
    }


def audit_technology_registry(*, registry=None, authority_registry_path=None) -> dict[str, Any]:
    registry = registry or get_default_registry()
    entries = []
    for raw in registry.entries:
        entry = deepcopy(raw)
        label = str(entry.get("label") or entry["technology_id"])
        aliases = list(entry.get("aliases") or [])
        authority = _authority_details(label, aliases, authority_registry_path=authority_registry_path)
        capability_id = _approved_capability(entry)
        query = build_query_strategy(label, authority["official_domains"], known_identity=True)
        if capability_id:
            state, reason = ALREADY_RESOLVED, "approved_capability_relationship_already_resolves_identity"
        elif not authority["official_domains"] and _is_non_owned_concept(entry):
            state, reason = MANUAL_REVIEW, "non_owned_concept_has_no_single_official_authority"
        elif not authority["official_domains"]:
            state, reason = MISSING_AUTHORITY, "known_identity_has_no_governed_official_source_scope"
        elif not query["ready"]:
            state, reason = QUERY_INCOMPLETE, query["reason"]
        else:
            state, reason = READY, "known_unmapped_identity_has_governed_authority_and_query_strategy"
        entries.append({
            "technology_id": entry["technology_id"],
            "canonical_name": label,
            "aliases": aliases,
            "capability_id": capability_id,
            **authority,
            "authority_rule_covered": bool(authority["official_domains"]),
            "source_classification_ready": bool(authority["official_source_scopes"]),
            "query_planner_ready": query["ready"],
            "known_identity_skips_rediscovery": True,
            "research_readiness": state,
            "blocker_reason": reason,
        })
    counts = Counter(row["research_readiness"] for row in entries)
    report = {
        "readiness_version": RESEARCH_READINESS_VERSION,
        "technology_registry_version": registry.version,
        "entries": entries,
        "technology_count": len(entries),
        "authority_covered_count": sum(row["authority_rule_covered"] for row in entries),
        "missing_authority_coverage_count": sum(not row["authority_rule_covered"] for row in entries),
        "state_counts": dict(sorted(counts.items())),
        "network_calls": 0,
        "model_calls": 0,
        "production_writes": 0,
    }
    report["audit_fingerprint"] = fingerprint(report)
    return report


def _candidate_subject(candidate: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from taxonomy_discovery.research_atomicity import candidate_atomicity
    atomicity = candidate_atomicity(candidate)
    names = atomicity.get("detected_entities") or []
    subject = names[0] if len(names) == 1 else candidate.get("concept_key") or candidate.get("normalized_cluster") or ""
    return " ".join(str(subject).split()).strip(), atomicity


def _identity_hypotheses(candidate: dict[str, Any], atomicity: dict[str, Any]) -> list[str]:
    from taxonomy_discovery.candidate_refinement import phrase_present
    text = " ".join(candidate.get("examples") or [candidate.get("normalized_cluster", "")])
    names = {str(value).strip() for value in atomicity.get("detected_entities") or [] if str(value).strip()}
    names.update(value for value in _IDENTITY_DISCOVERY_HINTS if phrase_present(text, value))
    # Prefer the complete product name over a nested acronym or family token.
    return sorted(name for name in names if not any(
        normalise(name) != normalise(other) and phrase_present(other, name)
        for other in names
    ))


def _identity_hypothesis_blocker(candidate: dict[str, Any], hypotheses: list[str]) -> str | None:
    if len(hypotheses) > 1:
        return "multiple_concrete_identity_hypotheses_require_decomposition"
    if not hypotheses:
        return "no_concrete_technology_identity_hypothesis"
    subject = normalise(hypotheses[0])
    text = normalise(" ".join(candidate.get("examples") or [candidate.get("normalized_cluster", "")]))
    if subject in _GENERIC_IDENTITY_CONCEPTS:
        return "generic_technical_concept_is_not_a_concrete_identity_hypothesis"
    if re.search(r"\b(?:portfolio|profile|account|resume|cv)\b", text) and subject in {"github", "gitlab"}:
        return "entity_is_an_evidence_container_not_the_required_technology"
    return None


def _capability_requires_decomposition(candidate: dict[str, Any], atomicity: dict[str, Any]) -> bool:
    text = normalise(" ".join(candidate.get("examples") or [candidate.get("normalized_cluster", "")]))
    words = text.split()
    relation = atomicity.get("logical_relation")
    if relation in {"or", "alternative_list"}:
        return True
    activities = set(re.findall(
        r"\b(?:analys\w*|build\w*|coordinat\w*|design\w*|develop\w*|deploy\w*|"
        r"document\w*|estimat\w*|implement\w*|integrat\w*|maintain\w*|operat\w*|"
        r"refactor\w*|support\w*|test\w*|validat\w*)\b",
        text,
    ))
    if len(activities) >= 3:
        return True
    if relation == "example_list" and len(words) > 14:
        return True
    return relation == "and" and len(words) > 18


def audit_candidate(candidate: dict[str, Any], *, queue_state: str, authority_registry_path=None) -> dict[str, Any]:
    subject, atomicity = _candidate_subject(candidate)
    route = str(candidate.get("candidate_route") or "")
    identity_hypotheses = _identity_hypotheses(candidate, atomicity) if route == "technology_identity" else []
    if route == "technology_identity" and len(identity_hypotheses) == 1:
        subject = identity_hypotheses[0]
    identity = resolve_requirement_text(subject)
    known_identity = identity.get("status") in {"recognized_unmapped", "resolved"}
    canonical = identity.get("technology_label") or subject
    registry_entry = _registry_entry(identity.get("technology_id")) if known_identity else None
    detected = []
    for name in atomicity.get("detected_entities") or []:
        resolved = resolve_requirement_text(name)
        if resolved.get("status") in {"recognized_unmapped", "resolved"}:
            detected.append(resolved.get("technology_id"))
    if known_identity:
        detected.append(identity.get("technology_id"))
    detected_ids = sorted({value for value in detected if value})

    # Governed authority is inherited only through an exact production identity.
    # Candidate text may provide an audit hint, but an authority-registry alias is
    # not itself proof that the technology identity exists in production.
    hint_domains = candidate_official_domains({"canonical_name": subject}, registry_path=authority_registry_path)
    domains = (candidate_official_domains({"canonical_name": canonical}, registry_path=authority_registry_path)
               if known_identity else [])
    scopes = (candidate_official_source_scopes({"canonical_name": canonical}, registry_path=authority_registry_path)
              if known_identity else [])
    if route == "technology_identity":
        query = build_identity_query_strategy(subject)
        domains, scopes = [], []
    elif route == "possible_new_capability":
        query = build_capability_query_strategy(subject)
        domains, scopes = [], []
    else:
        query = build_query_strategy(canonical, domains, known_identity=known_identity)

    identity_blocker = _identity_hypothesis_blocker(candidate, identity_hypotheses) if route == "technology_identity" else None
    capability_decomposition = (
        _capability_requires_decomposition(candidate, atomicity)
        if route == "possible_new_capability" else False
    )
    provenance_ready = bool(candidate.get("provenance")) and bool(
        candidate.get("occurrence_count") or candidate.get("observed_occurrence_count")
    )

    if (atomicity.get("atomicity_status") == "compound_requires_decomposition"
            or queue_state == "partial_resolution_decomposition_required"
            or identity_blocker == "multiple_concrete_identity_hypotheses_require_decomposition"
            or capability_decomposition):
        state, reason = NEEDS_DECOMPOSITION, "candidate_must_be_decomposed_before_research"
    elif queue_state == "resolved_locally" or identity.get("status") == "resolved":
        state, reason = ALREADY_RESOLVED, "current_production_knowledge_already_resolves_candidate"
    elif queue_state == "research_current_cached":
        state, reason = CACHED_CURRENT, "current_reusable_research_is_already_persisted"
    elif queue_state == "stale_requires_refresh":
        state, reason = STALE_RESEARCH, "persisted_research_requires_local_reinterpretation_or_refresh"
    elif queue_state in _BLOCKED_QUEUE_STATES:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, f"queue_state_{queue_state}"
    elif route == "existing_capability_resolver_issue" or queue_state == "local_review_required":
        state, reason = LOCAL_REVIEW_REQUIRED, "local_deterministic_review_does_not_require_paid_research"
    elif route == "technology_relationship" and not known_identity:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, "relationship_research_requires_current_production_technology_id"
    elif route == "technology_relationship" and not domains:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, "recognized_identity_has_no_governed_official_source_scope"
    elif route == "technology_relationship" and not query["ready"]:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, query["reason"]
    elif route == "technology_relationship":
        state, reason = RELATIONSHIP_RESEARCH_READY, "recognized_atomic_identity_has_governed_authority_and_query_strategy"
    elif route == "technology_identity" and known_identity:
        state, reason = LOCAL_REVIEW_REQUIRED, "technology_identity_already_exists_in_current_registry"
    elif route == "technology_identity" and identity_blocker:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, identity_blocker
    elif route == "technology_identity" and not query["ready"]:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, query["reason"]
    elif route == "technology_identity":
        state, reason = IDENTITY_RESEARCH_READY, "one_concrete_identity_hypothesis_has_bounded_neutral_discovery_queries"
    elif route == "possible_new_capability" and not domains and _is_non_owned_concept(registry_entry):
        state, reason = MANUAL_REVIEW, "non_owned_concept_has_no_single_official_authority"
    elif route == "possible_new_capability" and not provenance_ready:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, "capability_research_requires_source_provenance"
    elif route == "possible_new_capability" and not query["ready"]:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, query["reason"]
    elif route == "possible_new_capability":
        state, reason = CAPABILITY_RESEARCH_READY, "coherent_unresolved_capability_concept_has_provenance_and_bounded_queries"
    else:
        state, reason = BLOCKED_NOISE_OR_INSUFFICIENT, "candidate_route_is_not_paid_research_eligible"

    purpose = {
        "technology_relationship": "Research capability relationship",
        "technology_identity": "Verify technology identity",
        "possible_new_capability": "Research capability definition and boundaries",
        "existing_capability_resolver_issue": "Review local resolver behavior",
    }.get(route, "Review candidate")
    authority_state = (
        "governed_official_scope" if route == "technology_relationship" and domains
        else "candidate_evidence_only_not_governed" if route == "technology_identity"
        else "authoritative_definition_discovery" if route == "possible_new_capability"
        else "not_applicable"
    )
    return {
        "readiness_version": RESEARCH_READINESS_VERSION,
        "candidate_id": candidate.get("candidate_id"),
        "candidate": candidate.get("concept_key") or candidate.get("normalized_cluster"),
        "candidate_route": route,
        "research_purpose": purpose,
        "technology_identity": canonical or None,
        "technology_id": identity.get("technology_id"),
        "identity_match_result": identity.get("status"),
        "detected_technology_ids": detected_ids,
        "recognized_identity_count": len(detected_ids),
        "identity_hypotheses": identity_hypotheses,
        "technology_entry_kind": (registry_entry or {}).get("entry_kind"),
        "known_identity": known_identity,
        "known_identity_skips_rediscovery": known_identity,
        "official_domains": domains,
        "official_source_scopes": scopes,
        "candidate_text_authority_hints": hint_domains,
        "authority_inherited_from": (
            f"technology_id={identity.get('technology_id')}" if known_identity and domains else None
        ),
        "authority_covered": bool(domains),
        "authority_state": authority_state,
        "source_classification_ready": bool(scopes),
        "query_strategy": query,
        "query_ready": query["ready"],
        "cache_currentness": queue_state,
        "decomposition_status": atomicity.get("atomicity_status"),
        "research_readiness": state,
        "paid_research_eligible": state in PAID_RESEARCH_READY_STATES,
        "requires_human_review": True,
        "automatic_approval": False,
        "automatic_publication": False,
        "automatic_registry_or_taxonomy_mutation": False,
        "blocker_reason": reason,
    }


def external_audit_category(row: dict[str, Any]) -> str:
    """Mutually exclusive A-G classification for paid-research preflight."""
    if row.get("cache_currentness") in {"research_current_cached", "stale_requires_refresh"}:
        return "F"
    if (row.get("decomposition_status") == "compound_requires_decomposition"
            or row.get("recognized_identity_count", 0) > 1):
        return "B"
    if not row.get("known_identity"):
        return "C"
    if not row.get("authority_covered"):
        return "G" if row.get("technology_entry_kind") in _NON_OWNED_CONCEPT_KINDS else "D"
    if row.get("research_readiness") in PAID_RESEARCH_READY_STATES:
        return "A"
    if row.get("research_readiness") == MANUAL_REVIEW:
        return "G"
    return "E"


def audit_candidate_queue(rows: list[dict[str, Any]], *, authority_registry_path=None) -> dict[str, Any]:
    audited = [audit_candidate(row["candidate"], queue_state=row["research_status"],
                               authority_registry_path=authority_registry_path) for row in rows]
    counts = Counter(row["research_readiness"] for row in audited)
    external = [row for source, row in zip(rows, audited) if source.get("external_research_required")]
    for row in audited:
        row["external_audit_category"] = external_audit_category(row)
    category_counts = Counter(row["external_audit_category"] for row in external)
    report = {
        "readiness_version": RESEARCH_READINESS_VERSION,
        "candidates": audited,
        "current_external_candidates": len(external),
        "ready_for_paid_research": sum(row["paid_research_eligible"] for row in external),
        "blocked_by_readiness": sum(not row["paid_research_eligible"] for row in external),
        "blocked_by_authority_coverage": sum(row["research_readiness"] == MISSING_AUTHORITY for row in external),
        "blocked_by_query_planning": sum(row["research_readiness"] == QUERY_INCOMPLETE for row in external),
        "external_category_counts": {key: category_counts.get(key, 0) for key in "ABCDEFG"},
        "route_readiness_counts": {key: counts.get(key, 0) for key in (
            RELATIONSHIP_RESEARCH_READY,
            IDENTITY_RESEARCH_READY,
            CAPABILITY_RESEARCH_READY,
            LOCAL_REVIEW_REQUIRED,
            NEEDS_DECOMPOSITION,
            CACHED_CURRENT,
            STALE_RESEARCH,
            MANUAL_REVIEW,
            BLOCKED_NOISE_OR_INSUFFICIENT,
        )},
        "needs_decomposition": counts.get(NEEDS_DECOMPOSITION, 0),
        "cached_current": counts.get(CACHED_CURRENT, 0),
        "state_counts": dict(sorted(counts.items())),
        "network_calls": 0,
        "model_calls": 0,
        "production_writes": 0,
    }
    report["audit_fingerprint"] = fingerprint(report)
    return report


def audit_saved_research_evidence(saved_rows: list[dict[str, Any]], *, result_ids=None,
                                  authority_registry_path=None) -> list[dict[str, Any]]:
    """Reclassify immutable raw URLs in memory; never overwrite saved interpretations."""
    selected = set(result_ids or [])
    output = []
    for saved in saved_rows:
        result = saved.get("result") or {}
        result_id = result.get("research_result_id")
        if selected and result_id not in selected:
            continue
        target = result.get("research", {}).get("target", {})
        subject = target.get("subject") or result.get("candidate", {}).get("concept_key") or ""
        stored = result.get("sources") or []
        rows = result.get("research", {}).get("raw_provider_evidence", {}).get("results", []) or []
        sources = []
        for index, raw in enumerate(rows):
            classification = classify_candidate_source_url(
                {"canonical_name": subject}, raw.get("url", ""), registry_path=authority_registry_path)
            sources.append({
                "url": raw.get("url"),
                "stored_source_class": (stored[index] if index < len(stored) else {}).get("source_class"),
                "current_authority": classification["authority"],
                "current_source_class": "first_party_official_docs"
                if classification["authority"] == PRIMARY_OFFICIAL else "not_first_party_for_candidate",
                "matched_rule_domain": classification["matched_rule_domain"],
            })
        output.append({
            "research_result_id": result_id,
            "subject": subject,
            "provider_request_id": result.get("provider_request_id"),
            "raw_evidence_fingerprint": result.get("research", {}).get("evidence_fingerprint"),
            "source_count": len(rows),
            "first_party_source_count_after": sum(row["current_authority"] == PRIMARY_OFFICIAL for row in sources),
            "sources": sources,
            "history_mutated": False,
        })
    return output
