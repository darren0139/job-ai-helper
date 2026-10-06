"""Read-only whole-corpus taxonomy coverage and local-first gap planning.

The audit reuses the production requirement resolver.  Local proposals are
review artifacts only: temporary copied knowledge is used for impact previews,
and no taxonomy, registry, Job Match snapshot, score, review, or publication is
written here.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import ExitStack
from copy import deepcopy
import re
from typing import Any

from analysis_stability.stable_evidence_scoring import (
    IMPORTANCE_WEIGHTS,
    requirement_is_score_eligible,
)
from job_discovery.matching import current_match_versions
from tailoring.capability_taxonomy import (
    CapabilityTaxonomy,
    get_default_taxonomy,
    normalise as taxonomy_normalise,
    temporary_taxonomy_scope,
)
from tailoring.production_requirement_resolver import (
    resolve_requirement_with_production_knowledge,
)
from taxonomy_discovery.candidate_refinement import (
    concept_key,
    phrase_present,
    technology_entities,
    route_candidate,
)
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.regression_corpus import (
    CORPUS_VERSION,
    export_saved_corpus,
)
from taxonomy_discovery.research_atomicity import candidate_atomicity
from taxonomy_discovery.taxonomy_evolution import overlap_check
from taxonomy_discovery.technology_registry import (
    TechnologyRegistry,
    _validate_registry,
    get_default_registry,
    normalise,
    resolve_requirement_text,
    temporary_registry_scope,
)


CORPUS_GAP_RESOLUTION_VERSION = "tqd3-corpus-gap-resolution-v1"
LOCAL_PROPOSAL_VERSION = "tqd3-local-gap-proposal-v1"

OPERATIONAL_ROUTES = (
    "phrase_or_alias_gap",
    "technology_identity_missing",
    "technology_relationship_missing",
    "possible_new_capability",
    "needs_decomposition",
    "local_resolver_issue",
    "manual_review",
    "noise_or_non_capability",
)

_ROUTE_TO_RESEARCH = {
    "phrase_or_alias_gap": "existing_capability_resolver_issue",
    "local_resolver_issue": "existing_capability_resolver_issue",
    "technology_identity_missing": "technology_identity",
    "technology_relationship_missing": "technology_relationship",
    "possible_new_capability": "possible_new_capability",
    "needs_decomposition": "insufficient_signal",
    "manual_review": "insufficient_signal",
    "noise_or_non_capability": "administrative_or_non_capability",
}

# A bounded local identity vocabulary for the common technologies named in the
# milestone.  It establishes identity/aliases only.  No capability relationship
# is inferred from this table.
_COMMON_IDENTITIES = {
    "python": {"canonical_name": "Python", "aliases": ["Python"], "technology_kind": "language"},
    "sql": {"canonical_name": "SQL", "aliases": ["SQL"], "technology_kind": "language"},
    "java": {"canonical_name": "Java", "aliases": ["Java"], "technology_kind": "language"},
    "javascript": {"canonical_name": "JavaScript", "aliases": ["JavaScript"], "technology_kind": "language"},
    "postgresql": {"canonical_name": "PostgreSQL", "aliases": ["PostgreSQL", "Postgres"], "technology_kind": "product"},
    "aws": {"canonical_name": "Amazon Web Services", "aliases": ["AWS", "Amazon Web Services"], "technology_kind": "platform"},
    "amazon web services": {"canonical_name": "Amazon Web Services", "aliases": ["AWS", "Amazon Web Services"], "technology_kind": "platform"},
    "azure": {"canonical_name": "Microsoft Azure", "aliases": ["Azure", "Microsoft Azure"], "technology_kind": "platform"},
    "microsoft azure": {"canonical_name": "Microsoft Azure", "aliases": ["Azure", "Microsoft Azure"], "technology_kind": "platform"},
    "gcp": {"canonical_name": "Google Cloud Platform", "aliases": ["GCP", "Google Cloud Platform"], "technology_kind": "platform"},
    "google cloud platform": {"canonical_name": "Google Cloud Platform", "aliases": ["GCP", "Google Cloud Platform"], "technology_kind": "platform"},
}


def _resolution(requirement: dict[str, Any]) -> dict[str, Any]:
    resolved = resolve_requirement_with_production_knowledge(requirement)
    decision = resolved.get("decision") or {}
    registry = resolved.get("registry_resolution") or {}
    status = "resolved" if decision.get("capability_id") else registry.get("status", "unresolved")
    return {
        "status": status,
        "resolution_source": resolved.get("resolution_source"),
        "capability_id": decision.get("capability_id"),
        "technology_id": registry.get("technology_id"),
        "technology_label": registry.get("technology_label"),
        "registry_status": registry.get("status") or "not_checked",
        "registry_reason": registry.get("reason"),
        "taxonomy_diagnostics": {
            key: deepcopy(value)
            for key, value in (resolved.get("taxonomy_diagnostics") or {}).items()
            if key != "capability_record"
        },
    }


def _weight(row: dict[str, Any]) -> float:
    importance = str(row.get("importance") or "").lower()
    fraction = float(row.get("group_weight_fraction", 1.0) or 1.0)
    return IMPORTANCE_WEIGHTS.get(importance, 0.0) * fraction


def _coverage(rows: list[dict[str, Any]], accepted: set[str]) -> dict[str, Any]:
    selected = [row for row in rows if str(row.get("importance") or "").lower() in accepted]
    denominator = sum(_weight(row) for row in selected)
    numerator = sum(_weight(row) for row in selected if row["current_resolution"]["status"] == "resolved")
    return {
        "resolved_weight": round(numerator, 6),
        "total_weight": round(denominator, 6),
        "percent": round(100.0 * numerator / denominator, 2) if denominator else 0.0,
    }


def _candidate_base(group: list[dict[str, Any]]) -> dict[str, Any]:
    examples = sorted({row["requirement_text"] for row in group})
    text = examples[0]
    versions = current_match_versions()
    provenance = [deepcopy(row["provenance"]) for row in group]
    jobs = {row["job_id"] for row in group}
    importance = Counter(str(row.get("importance") or "unknown") for row in group)
    overlap = overlap_check(text)
    entities = technology_entities(text, [])
    gap = {
        "provenance": provenance,
        "job_count": len(jobs),
        "occurrence_count": len(group),
    }
    research_route, reason = route_candidate(gap, text, overlap, entities)
    candidate = {
        "normalized_cluster": concept_key(text),
        "concept_key": concept_key(text),
        "examples": examples,
        "occurrence_count": len(group),
        "job_count": len(jobs),
        "importance_distribution": dict(sorted(importance.items())),
        "provenance": provenance,
        "technology_terms": sorted({row["term"] for row in entities["concrete_entities"]}),
        "technology_entity_diagnostics": entities,
        "overlap": overlap,
        "routing_reason": reason,
        "candidate_route": research_route,
        "source_gap_ids": sorted({"corpus_gap_" + row["requirement_id"] for row in group}),
        "observed_job_count": len(jobs),
        "observed_occurrence_count": len(group),
        "recurrence_priority": "repeated_cross_job" if len(jobs) > 1 else "single_job",
        "current_versions": versions,
        "observed_scoring_versions": sorted({str(row["provenance"]["observed_versions"].get("scoring_version") or "unknown") for row in group}),
        "observed_taxonomy_versions": sorted({str(row["provenance"]["observed_versions"].get("taxonomy_version") or "unknown") for row in group}),
        "observed_registry_versions": sorted({str(row["provenance"]["observed_versions"].get("technology_registry_version") or "unknown") for row in group}),
    }
    candidate["candidate_fingerprint"] = fingerprint(candidate)
    candidate["candidate_id"] = "tqd3taxgap_" + candidate["candidate_fingerprint"][:24]
    return candidate


def _operational_route(candidate: dict[str, Any]) -> tuple[str, str]:
    research_route = candidate["candidate_route"]
    atomicity = candidate_atomicity(candidate)
    if atomicity["atomicity_status"] == "compound_requires_decomposition" or len(_compound_entities(candidate)) > 1:
        return "needs_decomposition", "Multiple concrete technology entities require deterministic atomic children"
    if research_route in {"ambiguous_or_noise", "insufficient_signal"} and _local_identity(candidate["concept_key"]):
        return "technology_identity_missing", "Bounded common-technology identity is absent from production registry"
    if research_route in {"administrative_or_non_capability", "ambiguous_or_noise"}:
        return "noise_or_non_capability", candidate["routing_reason"]
    if research_route == "existing_capability_resolver_issue":
        high = candidate["overlap"].get("high_overlap_candidates") or []
        ids = {row.get("capability_id") for row in high if row.get("capability_id")}
        safe = len(ids) == 1 and all(not row.get("unmet_requirement_groups") for row in high)
        return ("phrase_or_alias_gap" if safe else "local_resolver_issue",
                "One native capability has bounded phrase evidence" if safe else candidate["routing_reason"])
    mapped = {
        "technology_identity": "technology_identity_missing",
        "technology_relationship": "technology_relationship_missing",
        "possible_new_capability": "possible_new_capability",
    }
    if research_route == "insufficient_signal":
        text = " ".join(candidate.get("examples") or [])
        technical = bool(
            candidate.get("technology_terms")
            or candidate.get("overlap", {}).get("semantic_resolver_evidence")
            or re.search(
                r"\b(?:software|systems?|technical|technologies|data|database|security|cybersecurity|network|"
                r"cloud|code|coding|programming|api|backend|frontend|architecture|algorithm|automation|"
                r"deployment|integration|infrastructure|platform|application|debug|troubleshoot|testing|"
                r"observability|monitoring|protocol|firmware|machine learning|artificial intelligence|ai|ml)\b",
                text,
                re.I,
            )
        )
        return ("manual_review", candidate["routing_reason"]) if technical else (
            "noise_or_non_capability", "No deterministic technical capability signal"
        )
    return mapped.get(research_route, "manual_review"), candidate["routing_reason"]


def _local_identity(subject: str) -> dict[str, Any] | None:
    key = normalise(subject)
    direct = _COMMON_IDENTITIES.get(key)
    if direct:
        return deepcopy(direct)
    for row in _COMMON_IDENTITIES.values():
        if key in {normalise(value) for value in row["aliases"]}:
            return deepcopy(row)
    return None


def _compound_entities(candidate: dict[str, Any]) -> list[str]:
    """Find only configured/registered identities in an obvious entity list.

    This supplements the historical H.1 research atomicity diagnostic without
    broadening it. In particular, SQL is useful in ``Python and SQL`` here but
    remains outside the generic research entity detector.
    """
    text = " ".join(candidate.get("examples") or [candidate.get("concept_key", "")])
    names = list(candidate_atomicity(candidate)["detected_entities"])
    identity_keys = {normalise(name) for name in names}
    for identity in _COMMON_IDENTITIES.values():
        canonical_key = normalise(identity["canonical_name"])
        if canonical_key in identity_keys:
            continue
        matched = next((alias for alias in identity["aliases"] if phrase_present(text, alias)), None)
        if matched:
            names.append(matched)
            identity_keys.add(canonical_key)
    return sorted(dict.fromkeys(names), key=normalise)


def _local_plan(candidate: dict[str, Any], route: str, *, seed: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = resolve_requirement_text(candidate["examples"][0])
    if route == "phrase_or_alias_gap":
        ids = sorted({row["capability_id"] for row in candidate["overlap"].get("high_overlap_candidates", [])
                      if row.get("capability_id") and not row.get("unmet_requirement_groups")})
        if len(ids) == 1 and len(candidate["concept_key"].split()) >= 2:
            return {"possible": True, "resolution_type": "add_capability_phrase", "local_safe": True,
                    "target_capability_id": ids[0], "proposed_phrase": candidate["concept_key"],
                    "reason": "One existing capability has bounded native phrase evidence"}
    if route == "technology_identity_missing":
        terms = candidate.get("technology_terms") or [candidate["concept_key"]]
        identity = deepcopy(seed) if seed else next((_local_identity(term) for term in terms if _local_identity(term)), None)
        if identity:
            return {"possible": True, "resolution_type": "add_technology_identity", "local_safe": True,
                    "identity": identity, "reason": "Bounded common-technology identity vocabulary or reviewed bulk seed"}
    if route == "technology_relationship_missing":
        hypotheses = list((seed or {}).get("relationship_hypotheses") or [])
        valid = [row for row in hypotheses if isinstance(row, dict) and row.get("capability_id") in get_default_taxonomy().by_id()]
        if len(valid) == 1:
            return {"possible": True, "resolution_type": "add_technology_relationship", "local_safe": True,
                    "technology_id": registry.get("technology_id"), "relationship": deepcopy(valid[0]),
                    "reason": "One explicit reviewed seed relationship hypothesis; production knowledge remains unchanged"}
    if route == "needs_decomposition":
        children = _compound_entities(candidate)
        if len(children) > 1:
            return {"possible": True, "resolution_type": "deterministic_decomposition", "local_safe": True,
                    "atomic_children": children, "reason": "Multiple concrete entity boundaries are already known"}
    if route == "noise_or_non_capability":
        if candidate.get("parent_candidate_id"):
            return {"possible": False, "resolution_type": None, "local_safe": False,
                    "reason": "Atomic-child noise cannot reclassify its parent requirement"}
        return {"possible": True, "resolution_type": "mark_noise_non_capability", "local_safe": True,
                "reason": candidate["routing_reason"]}
    return {"possible": False, "resolution_type": None, "local_safe": False,
            "reason": "External governed research or manual review is required"}


def _queue_row(candidate: dict[str, Any], route: str, reason: str, *, seed: dict[str, Any] | None = None) -> dict[str, Any]:
    local = _local_plan(candidate, route, seed=seed)
    first = candidate["examples"][0]
    registry = resolve_requirement_text(first)
    importance = candidate.get("importance_distribution") or {}
    required_core = int(importance.get("required", 0)) + int(importance.get("core", 0)) + int(importance.get("deal_breaker", 0))
    external = route in {"technology_identity_missing", "technology_relationship_missing", "possible_new_capability"} and not local["possible"]
    priority = required_core * 1_000_000 + candidate["job_count"] * 1_000 + candidate["occurrence_count"]
    return {
        "candidate_id": candidate["candidate_id"],
        "concept": candidate["concept_key"],
        "example_jd_text": first,
        "job_ids": sorted({row.get("job_id") for row in candidate["provenance"] if row.get("job_id") is not None}),
        "job_count": candidate["job_count"],
        "occurrences": candidate["occurrence_count"],
        "importance": deepcopy(importance),
        "required_core_impact": required_core,
        "current_taxonomy_result": deepcopy(candidate["overlap"]),
        "current_registry_result": registry,
        "recommended_resolution_type": local["resolution_type"] or route,
        "operational_route": route,
        "local_resolution_possible": bool(local["possible"]),
        "local_safe": bool(local["local_safe"]),
        "external_research_required": external,
        "blocker_reason": reason if not local["possible"] else local["reason"],
        "local_plan": local,
        "parent_candidate_id": candidate.get("parent_candidate_id"),
        "source": candidate.get("source", "jd_corpus"),
        "provenance": deepcopy(candidate["provenance"]),
        "priority_score": priority,
        "candidate": candidate,
    }


def _child_candidate(parent: dict[str, Any], name: str) -> dict[str, Any]:
    provenance = [{**deepcopy(row), "parent_candidate_id": parent["candidate_id"],
                   "parent_requirement_text": parent["examples"][0]} for row in parent["provenance"]]
    group = [{
        "requirement_text": name,
        "requirement_id": row.get("requirement_id"),
        "job_id": row.get("job_id"),
        "importance": next(iter(parent.get("importance_distribution") or {"required": 1})),
        "provenance": row,
    } for row in provenance]
    child = _candidate_base(group)
    child["parent_candidate_id"] = parent["candidate_id"]
    child["parent_text"] = parent["examples"][0]
    child["source"] = "deterministic_decomposition"
    child["candidate_fingerprint"] = fingerprint({k: v for k, v in child.items() if k not in {"candidate_id", "candidate_fingerprint"}})
    child["candidate_id"] = "tqd3taxgap_" + child["candidate_fingerprint"][:24]
    return child


def _set_operational_route(candidate: dict[str, Any], route: str, reason: str) -> None:
    candidate["operational_route"] = route
    candidate["operational_reason"] = reason
    candidate["candidate_fingerprint"] = fingerprint({
        key: value for key, value in candidate.items()
        if key not in {"candidate_id", "candidate_fingerprint"}
    })
    candidate["candidate_id"] = "tqd3taxgap_" + candidate["candidate_fingerprint"][:24]


def _merge_atomic_children(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one atomic child queue item per concept across all parents."""
    parents = [row for row in rows if not row.get("parent_candidate_id")]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("parent_candidate_id"):
            grouped[row["concept"]].append(row)
    merged = []
    for concept, group in sorted(grouped.items()):
        if len(group) == 1:
            only = group[0]
            only["parent_candidate_ids"] = [only["parent_candidate_id"]]
            merged.append(only)
            continue
        row = deepcopy(group[0])
        provenance_index = {}
        for item in group:
            for source in item["provenance"]:
                key = (source.get("job_id"), source.get("snapshot_id"), source.get("requirement_id"),
                       source.get("parent_candidate_id"))
                provenance_index[key] = deepcopy(source)
        provenance = [provenance_index[key] for key in sorted(provenance_index, key=lambda value: tuple(str(v) for v in value))]
        parent_ids = sorted({source.get("parent_candidate_id") for source in provenance if source.get("parent_candidate_id")})
        importance = Counter()
        for item in group:
            importance.update(item.get("importance") or {})
        candidate = row["candidate"]
        candidate.update(
            provenance=provenance,
            occurrence_count=len(provenance),
            observed_occurrence_count=len(provenance),
            job_count=len({source.get("job_id") for source in provenance if source.get("job_id") is not None}),
            observed_job_count=len({source.get("job_id") for source in provenance if source.get("job_id") is not None}),
            importance_distribution=dict(sorted(importance.items())),
            parent_candidate_id=parent_ids[0],
            parent_candidate_ids=parent_ids,
            source_gap_ids=sorted({gap_id for item in group for gap_id in item["candidate"].get("source_gap_ids", [])}),
        )
        _set_operational_route(candidate, row["operational_route"], candidate["operational_reason"])
        refreshed = _queue_row(candidate, row["operational_route"], candidate["operational_reason"])
        refreshed["parent_candidate_id"] = parent_ids[0]
        refreshed["parent_candidate_ids"] = parent_ids
        merged.append(refreshed)
    return parents + merged


def audit_corpus_resolution(*, corpus: dict[str, Any] | None = None, db_path=None) -> dict[str, Any]:
    """Audit every saved canonical requirement against current production knowledge."""
    frozen = deepcopy(corpus) if corpus is not None else export_saved_corpus(db_path=db_path)
    if frozen.get("corpus_version") != CORPUS_VERSION:
        raise ValueError("Unsupported frozen Job Match corpus")
    rows: list[dict[str, Any]] = []
    unresolved_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in frozen.get("jobs", []):
        versions = deepcopy(job.get("versions") or {})
        for requirement in job.get("requirements", []):
            raw = next((row for row in (job.get("baseline_stable_analysis") or {}).get("canonical_requirements", [])
                        if row.get("requirement_id") == requirement.get("requirement_id")), requirement)
            if not requirement_is_score_eligible(raw):
                continue
            text = str(requirement.get("requirement_text") or "").strip()
            if not text:
                continue
            current = _resolution({"text": text, "atomic_focus": text})
            row = {
                "job_id": job.get("job_id"),
                "snapshot_id": job.get("snapshot_id"),
                "requirement_id": requirement.get("requirement_id"),
                "requirement_text": text,
                "importance": requirement.get("importance"),
                "group_weight_fraction": raw.get("group_weight_fraction", 1.0),
                "current_resolution": current,
                "provenance": {
                    "job_id": job.get("job_id"), "snapshot_id": job.get("snapshot_id"),
                    "requirement_id": requirement.get("requirement_id"),
                    "job_content_hash": job.get("job_content_hash"), "observed_versions": versions,
                },
            }
            rows.append(row)
            if current["status"] != "resolved":
                unresolved_groups[concept_key(text)].append(row)

    candidates: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    noise_requirement_ids: set[tuple[Any, Any]] = set()
    for key in sorted(unresolved_groups):
        candidate = _candidate_base(unresolved_groups[key])
        route, reason = _operational_route(candidate)
        _set_operational_route(candidate, route, reason)
        candidates.append(candidate)
        queue.append(_queue_row(candidate, route, reason))
        if route == "noise_or_non_capability":
            noise_requirement_ids.update((row["job_id"], row["requirement_id"]) for row in unresolved_groups[key])
        if route == "needs_decomposition":
            for child_name in _compound_entities(candidate):
                if _resolution({"text": child_name, "atomic_focus": child_name})["status"] == "resolved":
                    continue
                child = _child_candidate(candidate, child_name)
                child_route, child_reason = _operational_route(child)
                _set_operational_route(child, child_route, child_reason)
                candidates.append(child)
                queue.append(_queue_row(child, child_route, child_reason))

    queue = _merge_atomic_children(queue)
    candidates = [row["candidate"] for row in queue]

    meaningful = [row for row in rows if (row["job_id"], row["requirement_id"]) not in noise_requirement_ids]
    resolved = [row for row in meaningful if row["current_resolution"]["status"] == "resolved"]
    unresolved = [row for row in meaningful if row["current_resolution"]["status"] != "resolved"]
    queue.sort(key=lambda row: (-row["required_core_impact"], -row["job_count"], -row["occurrences"], row["concept"], row["candidate_id"]))
    for index, row in enumerate(queue, 1):
        row["priority_rank"] = index
    route_counts = Counter(row["operational_route"] for row in queue if not row.get("parent_candidate_id"))
    local_count = sum(row["local_safe"] for row in queue if row["operational_route"] != "noise_or_non_capability")
    local_safe_count = sum(row["local_safe"] for row in queue)
    summary = {
        "total_requirements": len(rows),
        "meaningful_technical_requirements": len(meaningful),
        "resolved_scorable_requirements": len(resolved),
        "unresolved_technical_requirements": len(unresolved),
        "required_core_weighted_coverage": _coverage(meaningful, {"deal_breaker", "required", "core"}),
        "supporting_preferred_weighted_coverage": _coverage(meaningful, {"preferred"}),
        "overall_weighted_coverage": _coverage(meaningful, {"deal_breaker", "required", "core", "preferred"}),
        "locally_resolvable_count": local_count,
        "local_safe_proposal_count": local_safe_count,
        "technology_identity_missing_count": route_counts["technology_identity_missing"],
        "relationship_missing_count": route_counts["technology_relationship_missing"],
        "capability_candidate_count": route_counts["possible_new_capability"],
        "decomposition_count": route_counts["needs_decomposition"],
        "research_required_count": sum(row["external_research_required"] for row in queue if not row.get("parent_candidate_id")),
        "manual_noise_count": route_counts["manual_review"] + route_counts["noise_or_non_capability"],
        "manual_review_count": route_counts["manual_review"],
        "noise_count": route_counts["noise_or_non_capability"],
    }
    top = [{key: deepcopy(row[key]) for key in ("candidate_id", "concept", "operational_route", "required_core_impact", "job_count", "occurrences", "example_jd_text")}
           for row in queue if row["operational_route"] != "noise_or_non_capability"][:30]
    return {
        "audit_version": CORPUS_GAP_RESOLUTION_VERSION,
        "corpus_version": frozen["corpus_version"],
        "current_versions": current_match_versions(),
        "summary": summary,
        "route_counts": dict(sorted(route_counts.items())),
        "top_unresolved_concepts": top,
        "requirements": rows,
        "candidates": candidates,
        "queue": queue,
        "corpus": frozen,
        "read_only": True,
        "network_calls": 0,
        "model_calls": 0,
        "production_mutations": 0,
        "scoring_semantics_changed": False,
    }


def import_bulk_seed(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Validate a proposed broad seed list and return queue-ready dry-run rows."""
    raw_entries = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(raw_entries, list):
        raise ValueError("Bulk seed must be a list or an object with entries")
    allowed_kinds = {"framework", "runtime", "platform", "product", "protocol", "tool", "language", "architecture_pattern"}
    cleaned = []
    seen = set()
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise ValueError("Every bulk seed entry must be an object")
        name = " ".join(str(raw.get("canonical_name") or "").split())
        aliases = sorted({" ".join(str(value).split()) for value in raw.get("aliases", []) if str(value).strip()})
        kind = str(raw.get("technology_kind") or "").strip()
        if not name or not aliases or kind not in allowed_kinds:
            raise ValueError(f"Bulk seed entry {index} requires canonical_name, aliases, and a valid technology_kind")
        key = normalise(name)
        if key in seen:
            raise ValueError(f"Duplicate bulk seed identity: {name}")
        seen.add(key)
        relationships = raw.get("relationship_hypotheses", [])
        if not isinstance(relationships, list) or any(not isinstance(row, dict) or not row.get("capability_id") for row in relationships):
            raise ValueError(f"{name}: relationship_hypotheses must be capability objects")
        cleaned.append({"canonical_name": name, "aliases": aliases, "technology_kind": kind,
                        "relationship_hypotheses": deepcopy(relationships), "source": "bulk_seed"})
    return {"seed_version": "tqd3-bulk-technology-seed-v1", "entries": cleaned,
            "dry_run": True, "production_mutations": 0, "network_calls": 0, "model_calls": 0}


def build_gap_resolution_queue(audit: dict[str, Any], *, bulk_seed=None, broad_candidates=None) -> dict[str, Any]:
    if audit.get("audit_version") != CORPUS_GAP_RESOLUTION_VERSION:
        raise ValueError("Unsupported corpus gap audit")
    rows = deepcopy(audit["queue"])
    candidates = deepcopy(audit["candidates"])
    seed_report = import_bulk_seed(bulk_seed) if bulk_seed is not None else None
    if seed_report:
        for seed in seed_report["entries"]:
            registry = resolve_requirement_text(seed["canonical_name"])
            route = "technology_relationship_missing" if registry["status"] == "recognized_unmapped" else "technology_identity_missing"
            text = seed["canonical_name"]
            group = [{"requirement_text": text, "requirement_id": "bulk_seed:" + normalise(text), "job_id": None,
                      "importance": "preferred", "provenance": {"job_id": None, "snapshot_id": None,
                      "requirement_id": "bulk_seed:" + normalise(text), "job_content_hash": None,
                      "observed_versions": current_match_versions(), "source": "bulk_seed"}}]
            candidate = _candidate_base(group)
            candidate.update(source="bulk_seed", bulk_seed=deepcopy(seed), operational_route=route,
                             operational_reason="Proposed bulk seed requires governed review")
            candidate["candidate_fingerprint"] = fingerprint({k: v for k, v in candidate.items() if k not in {"candidate_id", "candidate_fingerprint"}})
            candidate["candidate_id"] = "tqd3taxgap_" + candidate["candidate_fingerprint"][:24]
            candidates.append(candidate)
            rows.append(_queue_row(candidate, route, candidate["operational_reason"], seed=seed))
    if broad_candidates is not None:
        from taxonomy_discovery.broad_mining_candidates import (
            BROAD_MINING_CANDIDATE_VERSION,
            STATUS_ALREADY_KNOWN,
        )
        if not isinstance(broad_candidates, list):
            raise ValueError("Broad Mining candidates must be a list")
        for broad in broad_candidates:
            if not isinstance(broad, dict) or broad.get("candidate_version") != BROAD_MINING_CANDIDATE_VERSION:
                raise ValueError("Unsupported Broad Mining candidate")
            if (broad.get("governance") or {}).get("untrusted_research") is not True:
                raise ValueError("Broad Mining provenance must remain untrusted research")
            name = str(broad.get("canonical_name") or "").strip()
            if not name:
                raise ValueError("Broad Mining candidate canonical_name required")
            registry = resolve_requirement_text(name)
            if broad.get("status") == STATUS_ALREADY_KNOWN and registry.get("status") == "recognized_unmapped":
                route = "technology_relationship_missing"
                research_route = "technology_relationship"
            elif broad.get("status") == STATUS_ALREADY_KNOWN and registry.get("status") == "resolved":
                continue
            else:
                route = "technology_identity_missing"
                research_route = "technology_identity"
            provenance = {"job_id": None, "snapshot_id": None,
                "requirement_id": "broad_mining:" + str(broad.get("candidate_id") or normalise(name)),
                "job_content_hash": None, "observed_versions": current_match_versions(),
                "source": "broad_mining", "provider_request_ids": deepcopy(broad.get("provider_request_ids") or []),
                "target_ids": deepcopy(broad.get("target_ids") or []), "seed_ids": deepcopy(broad.get("seed_ids") or [])}
            candidate = _candidate_base([{"requirement_text": name, "requirement_id": provenance["requirement_id"],
                "job_id": None, "importance": "preferred", "provenance": provenance}])
            candidate.update(source="broad_mining", broad_mining_candidate=deepcopy(broad),
                             candidate_route=research_route,
                             routing_reason="Structured Broad Mining identity enters existing governed route")
            _set_operational_route(candidate, route, "Untrusted Broad Mining evidence requires governed verification")
            candidates.append(candidate)
            row = _queue_row(candidate, route, candidate["operational_reason"])
            row["local_plan"] = {"possible": False, "resolution_type": None, "local_safe": False,
                                 "reason": "Untrusted Broad Mining evidence cannot create local knowledge"}
            row["local_resolution_possible"] = False
            row["local_safe"] = False
            row["external_research_required"] = True
            row["recommended_resolution_type"] = route
            row["blocker_reason"] = row["local_plan"]["reason"]
            rows.append(row)
    rows.sort(key=lambda row: (-row["priority_score"], row["concept"], row["candidate_id"]))
    for index, row in enumerate(rows, 1):
        row["priority_rank"] = index
    return {"audit_version": audit["audit_version"], "rows": rows, "candidates": candidates,
            "seed": seed_report, "queue_fingerprint": fingerprint([{k: v for k, v in row.items() if k != "candidate"} for row in rows]),
            "network_calls": 0, "model_calls": 0, "production_mutations": 0}


def create_local_proposals(queue: dict[str, Any], *, selected_candidate_ids: list[str], explicit_creation=False) -> dict[str, Any]:
    if explicit_creation is not True:
        raise ValueError("Explicit local proposal creation required")
    selected = list(dict.fromkeys(selected_candidate_ids))
    by_id = {row["candidate_id"]: row for row in queue.get("rows", [])}
    if not selected or any(candidate_id not in by_id for candidate_id in selected):
        raise ValueError("Select known queue candidates")
    proposals = []
    skipped = []
    for candidate_id in selected:
        row = by_id[candidate_id]
        plan = row["local_plan"]
        if not plan.get("local_safe"):
            skipped.append({"candidate_id": candidate_id, "reason": plan.get("reason")})
            continue
        proposal = {
            "proposal_version": LOCAL_PROPOSAL_VERSION,
            "candidate_id": candidate_id,
            "candidate_fingerprint": row["candidate"]["candidate_fingerprint"],
            "concept": row["concept"],
            "resolution_type": plan["resolution_type"],
            "proposed_change": deepcopy(plan),
            "affected_requirement_keys": sorted({(p.get("job_id"), p.get("requirement_id")) for p in row["provenance"]}),
            "affected_jobs": row["job_ids"],
            "source_provenance": deepcopy(row["provenance"]),
            "current_versions": current_match_versions(),
            "status": "draft",
            "requires_human_review": True,
            "requires_human_approval": True,
            "approval": False,
            "publication": False,
        }
        proposal["proposal_fingerprint"] = fingerprint(proposal)
        proposal["proposal_id"] = "tqd3local_" + proposal["proposal_fingerprint"][:24]
        proposals.append(proposal)
    return {"proposal_version": LOCAL_PROPOSAL_VERSION, "proposals": proposals, "skipped": skipped,
            "approval": False, "publication": False, "production_mutations": 0,
            "network_calls": 0, "model_calls": 0}


def build_native_regression_handoff(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """Adapt compatible local identity drafts to the existing registry contract.

    Other local actions deliberately remain unsupported until an existing
    governed draft contract can represent them without weakening its evidence
    requirements.
    """
    from taxonomy_discovery.research_proposals import (
        PROPOSAL_CONTRACT_VERSION,
        validate_proposal_bundle,
    )
    taxonomy = get_default_taxonomy()
    registry = get_default_registry()
    items = []
    unsupported = []
    for proposal in proposals:
        if proposal.get("resolution_type") != "add_technology_identity":
            unsupported.append({"proposal_id": proposal.get("proposal_id"),
                                "reason": "existing_native_draft_contract_unavailable"})
            continue
        identity = proposal["proposed_change"]["identity"]
        technology_id = re.sub(r"[^a-z0-9]+", ".", normalise(identity["canonical_name"])).strip(".")
        native = {
            "proposal_id": proposal["proposal_id"],
            "technology_id": technology_id,
            "label": identity["canonical_name"],
            "entry_kind": identity["technology_kind"],
            "aliases": identity["aliases"],
            "proposal_classification": "recognized_unmapped",
            "proposed_capability_id": None,
            "relationship_type": None,
            "confidence": 1.0,
            "summary": "Local deterministic identity draft; no capability relationship is asserted.",
            "sources": [],
            "governed_research": {"local_proposal_id": proposal["proposal_id"],
                                  "source_provenance": deepcopy(proposal["source_provenance"])},
        }
        bundle = validate_proposal_bundle({
            "proposal_bundle_version": PROPOSAL_CONTRACT_VERSION,
            "taxonomy_version": taxonomy.version,
            "registry_version": registry.version,
            "research_method": CORPUS_GAP_RESOLUTION_VERSION,
            "proposals": [native],
        })
        draft = {"kind": "technology", "draft_id": proposal["proposal_id"], "status": "draft",
                 "requires_human_approval": True, "proposal_bundle": bundle,
                 "local_proposal_fingerprint": proposal["proposal_fingerprint"]}
        items.append({"result_id": proposal["proposal_id"], "draft": draft})
    return {"result_drafts": items, "unsupported": unsupported,
            "uses_existing_bulk_regression": True, "approval": False,
            "publication": False, "production_mutations": 0}


def _temporary_knowledge(proposals: list[dict[str, Any]]) -> tuple[CapabilityTaxonomy, TechnologyRegistry]:
    taxonomy = get_default_taxonomy()
    capabilities = deepcopy(list(taxonomy.capabilities))
    registry = get_default_registry()
    entries = deepcopy(list(registry.entries))
    by_technology = {row["technology_id"]: row for row in entries}
    for proposal in proposals:
        change = proposal["proposed_change"]
        kind = proposal["resolution_type"]
        if kind == "add_capability_phrase":
            entry = next(row for row in capabilities if row["capability_id"] == change["target_capability_id"])
            phrases = entry["requirement"].setdefault("any_terms", [])
            if change["proposed_phrase"] not in phrases:
                phrases.append(change["proposed_phrase"])
        elif kind == "add_technology_identity":
            identity = change["identity"]
            technology_id = re.sub(r"[^a-z0-9]+", ".", normalise(identity["canonical_name"])).strip(".")
            entry = by_technology.get(technology_id)
            if entry is None:
                entry = {"technology_id": technology_id, "label": identity["canonical_name"],
                         "entry_kind": identity["technology_kind"], "aliases": [], "status": "approved",
                         "capability_relationships": [], "notes": "Temporary local proposal preview"}
                entries.append(entry)
                by_technology[technology_id] = entry
            entry["aliases"] = sorted(set(entry.get("aliases", []) + identity["aliases"]))
        elif kind == "add_technology_relationship":
            technology_id = change.get("technology_id")
            entry = by_technology.get(technology_id)
            if entry is None:
                raise ValueError("Relationship proposal requires an existing production technology identity")
            relationship = change["relationship"]
            approved = [row for row in entry.get("capability_relationships", [])
                        if row.get("status") == "approved" and row.get("relationship_type") == "maps_to_capability"]
            if approved and any(row.get("capability_id") != relationship["capability_id"] for row in approved):
                raise ValueError("Relationship proposal conflicts with production knowledge")
            if not approved:
                entry.setdefault("capability_relationships", []).append({"capability_id": relationship["capability_id"],
                    "relationship_type": "maps_to_capability", "status": "approved"})
    shadow_taxonomy = CapabilityTaxonomy(taxonomy.version + "+local-preview", tuple(capabilities))
    _validate_registry({"registry_version": registry.version + "+local-preview", "entries": entries})
    shadow_registry = TechnologyRegistry(registry.version + "+local-preview", tuple(entries))
    return shadow_taxonomy, shadow_registry


def preview_local_resolution(audit: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare current and temporary draft knowledge using the native resolver."""
    if audit.get("audit_version") != CORPUS_GAP_RESOLUTION_VERSION or not proposals:
        raise ValueError("Current audit and selected local proposals required")
    if any(proposal.get("proposal_version") != LOCAL_PROPOSAL_VERSION or proposal.get("status") != "draft"
           or proposal.get("requires_human_approval") is not True for proposal in proposals):
        raise ValueError("Governed local draft proposals required")
    shadow_taxonomy, shadow_registry = _temporary_knowledge(proposals)
    source_ids = {tuple(key): proposal["proposal_id"] for proposal in proposals for key in proposal["affected_requirement_keys"]}
    decomposition = {tuple(key): proposal for proposal in proposals if proposal["resolution_type"] == "deterministic_decomposition"
                     for key in proposal["affected_requirement_keys"]}
    noise = {tuple(key) for proposal in proposals if proposal["resolution_type"] == "mark_noise_non_capability"
             for key in proposal["affected_requirement_keys"]}
    output = []
    with ExitStack() as stack:
        stack.enter_context(temporary_taxonomy_scope(shadow_taxonomy))
        stack.enter_context(temporary_registry_scope(shadow_registry))
        for row in audit["requirements"]:
            key = (row["job_id"], row["requirement_id"])
            before = deepcopy(row["current_resolution"])
            after = _resolution({"text": row["requirement_text"], "atomic_focus": row["requirement_text"]})
            child_resolutions = []
            if key in decomposition:
                for child in decomposition[key]["proposed_change"]["atomic_children"]:
                    child_resolutions.append({"text": child, "resolution": _resolution({"text": child, "atomic_focus": child})})
                if child_resolutions and all(item["resolution"]["status"] == "resolved" for item in child_resolutions):
                    after = {"status": "resolved", "resolution_source": "deterministic_decomposition",
                             "capability_id": None, "technology_id": None, "technology_label": None,
                             "registry_status": "decomposed", "registry_reason": "all_atomic_children_resolved",
                             "taxonomy_diagnostics": {}}
            excluded = key in noise
            semantic_fields = (
                "status", "resolution_source", "capability_id", "technology_id",
                "technology_label", "registry_status", "registry_reason",
            )
            changed = any(before.get(field) != after.get(field) for field in semantic_fields) or excluded
            output.append({"job_id": row["job_id"], "snapshot_id": row["snapshot_id"],
                           "requirement_id": row["requirement_id"], "requirement_text": row["requirement_text"],
                           "importance": row["importance"], "before": before, "after": after,
                           "changed": changed, "would_resolve": before["status"] != "resolved" and after["status"] == "resolved",
                           "would_exclude_as_noise": excluded, "child_resolutions": child_resolutions,
                           "responsible_proposal_id": source_ids.get(key) if changed else None})
    before_meaningful = [row for row in audit["requirements"]
                         if not any(not q.get("parent_candidate_id") and q["operational_route"] == "noise_or_non_capability" and
                                    (row["job_id"], row["requirement_id"]) in {(p.get("job_id"), p.get("requirement_id")) for p in q["provenance"]}
                                    for q in audit["queue"])]
    after_meaningful = []
    by_key = {(row["job_id"], row["requirement_id"]): row for row in output}
    for row in before_meaningful:
        key = (row["job_id"], row["requirement_id"])
        if key in noise:
            continue
        copied = deepcopy(row)
        copied["current_resolution"] = by_key[key]["after"]
        after_meaningful.append(copied)
    before_cov = _coverage(before_meaningful, {"deal_breaker", "required", "core", "preferred"})
    after_cov = _coverage(after_meaningful, {"deal_breaker", "required", "core", "preferred"})
    changed = [row for row in output if row["changed"]]
    intended = {(key[0], key[1]) for proposal in proposals for key in proposal["affected_requirement_keys"]}
    conflicts = [{"job_id": row["job_id"], "requirement_id": row["requirement_id"], "reason": "changed_outside_source_provenance"}
                 for row in changed if (row["job_id"], row["requirement_id"]) not in intended]
    return {
        "preview_version": "tqd3-local-gap-impact-preview-v1",
        "requirements_evaluated": len(output),
        "unresolved_before": sum(row["before"]["status"] != "resolved" for row in output),
        "would_resolve_after": sum(row["would_resolve"] for row in output),
        "affected_requirement_ids": [row["requirement_id"] for row in changed],
        "affected_jobs": sorted({row["job_id"] for row in changed}),
        "potential_new_matches": sum(row["would_resolve"] for row in output),
        "unchanged_requirements": sum(not row["changed"] for row in output),
        "conflicts_ambiguity": conflicts,
        "rows": output,
        "coverage_before_percent": before_cov["percent"],
        "projected_coverage_after_percent": after_cov["percent"],
        "scoring_influence": False,
        "score_changes_claimed": False,
        "review_only": True,
        "approval": False,
        "publication": False,
        "production_mutations": 0,
        "network_calls": 0,
        "model_calls": 0,
    }

