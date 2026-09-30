from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable

from taxonomy_discovery.technology_registry import (
    get_default_registry,
    resolve_candidate,
)
from taxonomy_discovery.research_proposals import (
    detect_possible_compound_requirement,
)

TRIAGE_VERSION = "capability-taxonomy-discovery-triage-v1"

TRIAGE_STATUSES = (
    "unreviewed",
    "research_candidate",
    "existing_taxonomy_near_miss",
    "decomposition_issue",
    "scope_review",
    "defer",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _stable_analysis(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = snapshot.get("stable_analysis")
    return value if isinstance(value, dict) else {}


def _canonical_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _stable_analysis(snapshot).get("canonical_requirements", [])
    return [row for row in rows if isinstance(row, dict)]


def _retrieval_summary(row: dict[str, Any]) -> dict[str, Any]:
    retrieval = row.get("capability_retrieval")
    if not isinstance(retrieval, dict):
        retrieval = {}

    candidates: list[dict[str, Any]] = []
    for raw in retrieval.get("candidates", []) or []:
        if not isinstance(raw, dict):
            continue
        candidates.append(
            {
                "capability_id": _clean(raw.get("capability_id")),
                "lexical_score": _safe_float(raw.get("lexical_score")),
                "vector_distance": _safe_float(raw.get("vector_distance")),
                "retrieval_sources": list(raw.get("retrieval_sources", []) or []),
            }
        )

    candidates.sort(
        key=lambda item: (
            -1.0 if item.get("lexical_score") is None else -float(item["lexical_score"]),
            str(item.get("capability_id") or ""),
        )
    )
    top = candidates[0] if candidates else None

    return {
        "status": _clean(retrieval.get("status")),
        "requested_mode": _clean(retrieval.get("requested_mode")),
        "effective_mode": _clean(retrieval.get("effective_mode")),
        "exact_capability_id": _clean(retrieval.get("exact_capability_id")) or None,
        "lexical_top_score": _safe_float(retrieval.get("lexical_top_score")),
        "shadow_only": bool(retrieval.get("shadow_only", False)),
        "influences_scoring": bool(retrieval.get("influences_scoring", False)),
        "top_candidate": top,
        "candidates": candidates,
    }


def _build_snapshot_indexes(
    snapshots: Iterable[dict[str, Any]],
) -> tuple[
    dict[tuple[int, str], dict[str, Any]],
    dict[tuple[int, str], list[dict[str, Any]]],
]:
    by_requirement: dict[tuple[int, str], dict[str, Any]] = {}
    by_group: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        try:
            job_id = int(snapshot.get("discovered_job_id") or 0)
        except (TypeError, ValueError):
            job_id = 0
        if job_id <= 0:
            continue

        for row in _canonical_rows(snapshot):
            requirement_id = _clean(row.get("requirement_id"))
            if requirement_id:
                by_requirement[(job_id, requirement_id)] = row

            group_id = (
                _clean(row.get("atomic_group_id"))
                or _clean(row.get("scoring_parent_occurrence_id"))
            )
            if group_id:
                by_group[(job_id, group_id)].append(row)

    return by_requirement, by_group


def _context_for_observation(
    observation: dict[str, Any],
    *,
    by_requirement: dict[tuple[int, str], dict[str, Any]],
    by_group: dict[tuple[int, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    try:
        job_id = int(observation.get("discovered_job_id") or 0)
    except (TypeError, ValueError):
        job_id = 0
    requirement_id = _clean(observation.get("requirement_id"))
    row = by_requirement.get((job_id, requirement_id))

    if not isinstance(row, dict):
        return {
            "context_available": False,
            "parent_text": "",
            "is_atomic": False,
            "atomic_group_id": "",
            "group_weight_fraction": None,
            "semantic_type": "",
            "eligibility_rule": "",
            "explicit_only_requirement": False,
            "scoring_parent_occurrence_id": "",
            "taxonomy_cap_status": "",
            "capability_id": None,
            "retrieval": _retrieval_summary({}),
            "atomic_siblings": [],
        }

    group_id = (
        _clean(row.get("atomic_group_id"))
        or _clean(row.get("scoring_parent_occurrence_id"))
    )
    sibling_rows = by_group.get((job_id, group_id), []) if group_id else []
    siblings: list[dict[str, Any]] = []
    for sibling in sibling_rows:
        sibling_id = _clean(sibling.get("requirement_id"))
        if not sibling_id or sibling_id == requirement_id:
            continue
        siblings.append(
            {
                "requirement_id": sibling_id,
                "requirement_text": _clean(sibling.get("text") or sibling.get("atomic_focus")),
                "match_label": _clean(sibling.get("match_label")),
                "capability_id": _clean(sibling.get("capability_id")) or None,
                "is_atomic": bool(sibling.get("is_atomic", False)),
                "group_weight_fraction": _safe_float(
                    sibling.get("group_weight_fraction")
                ),
            }
        )

    return {
        "context_available": True,
        "parent_text": _clean(row.get("parent_text")),
        "is_atomic": bool(row.get("is_atomic", False)),
        "atomic_group_id": _clean(row.get("atomic_group_id")),
        "group_weight_fraction": _safe_float(row.get("group_weight_fraction")),
        "semantic_type": _clean(row.get("semantic_type")),
        "eligibility_rule": _clean(row.get("eligibility_rule")),
        "explicit_only_requirement": bool(
            row.get("explicit_only_requirement", False)
        ),
        "scoring_parent_occurrence_id": _clean(
            row.get("scoring_parent_occurrence_id")
        ),
        "taxonomy_cap_status": _clean(
            row.get("capability_taxonomy_cap_status")
        ),
        "capability_id": _clean(row.get("capability_id")) or None,
        "retrieval": _retrieval_summary(row),
        "atomic_siblings": siblings,
    }


def _diagnostic_flags(
    observations: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
) -> list[str]:
    flags: set[str] = set()

    labels = {
        _clean(observation.get("match_label")).lower()
        for observation in observations
    }
    if "direct" in labels:
        flags.add("candidate_match_direct")
    if "transferable" in labels:
        flags.add("candidate_match_transferable")
    if "weak" in labels:
        flags.add("candidate_match_weak")
    if labels == {"none"}:
        flags.add("candidate_match_none_only")

    available = [ctx for ctx in contexts if ctx.get("context_available")]
    if len(available) != len(contexts):
        flags.add("missing_snapshot_context")

    if any(ctx.get("is_atomic") for ctx in available):
        flags.add("atomic_child")
    if any(
        ctx.get("is_atomic")
        and _clean(ctx.get("parent_text"))
        and _clean(ctx.get("parent_text"))
        != _clean(obs.get("requirement_text"))
        for obs, ctx in zip(observations, contexts)
    ):
        flags.add("atomic_parent_context_available")
    if any(ctx.get("atomic_siblings") for ctx in available):
        flags.add("atomic_siblings_present")

    retrievals = [
        ctx.get("retrieval", {})
        for ctx in available
        if isinstance(ctx.get("retrieval"), dict)
    ]
    if any(r.get("exact_capability_id") for r in retrievals):
        flags.add("retrieval_exact_capability_present")
    if any(r.get("candidates") for r in retrievals):
        flags.add("retrieval_candidates_present")
    elif available:
        flags.add("no_retrieval_candidates")

    if any(
        (r.get("top_candidate") or {}).get("lexical_score") is not None
        for r in retrievals
    ):
        flags.add("lexical_retrieval_signal_present")

    return sorted(flags)


def enrich_discovery_report(
    discovery_report: dict[str, Any],
    snapshots: Iterable[dict[str, Any]],
    *,
    reviews: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Enrich TQ-D2 candidates with snapshot context and persisted human review.

    This function is deterministic. It does not classify candidates into a final
    triage state and makes no model, network, Tavily, or taxonomy-mutation calls.
    """
    report = deepcopy(discovery_report)
    snapshot_list = [s for s in snapshots if isinstance(s, dict)]
    by_requirement, by_group = _build_snapshot_indexes(snapshot_list)

    review_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for review in reviews:
        if not isinstance(review, dict):
            continue
        key = (
            _clean(review.get("candidate_id")),
            _clean(review.get("taxonomy_version")),
        )
        if all(key):
            review_lookup[key] = dict(review)

    enriched_candidates: list[dict[str, Any]] = []
    status_counts = {status: 0 for status in TRIAGE_STATUSES}

    for raw_candidate in report.get("candidates", []) or []:
        if not isinstance(raw_candidate, dict):
            continue
        candidate = deepcopy(raw_candidate)
        observations = [
            obs
            for obs in candidate.get("observations", []) or []
            if isinstance(obs, dict)
        ]

        contexts = [
            _context_for_observation(
                obs,
                by_requirement=by_requirement,
                by_group=by_group,
            )
            for obs in observations
        ]

        taxonomy_version = _clean(
            candidate.get("taxonomy_version")
            or report.get("taxonomy_version")
        )
        candidate_id = _clean(candidate.get("candidate_id"))
        review = review_lookup.get((candidate_id, taxonomy_version))

        if review is None:
            triage = {
                "status": "unreviewed",
                "target_capability_id": None,
                "notes": "",
                "reviewed_at": None,
                "triage_version": TRIAGE_VERSION,
            }
        else:
            triage = {
                "status": _clean(review.get("triage_status")) or "unreviewed",
                "target_capability_id": (
                    _clean(review.get("target_capability_id")) or None
                ),
                "notes": str(review.get("notes") or ""),
                "reviewed_at": review.get("updated_at"),
                "triage_version": _clean(
                    review.get("triage_version")
                ) or TRIAGE_VERSION,
            }

        if triage["status"] not in status_counts:
            triage["status"] = "unreviewed"

        registry_resolution = resolve_candidate(
            candidate,
            registry=get_default_registry(),
        )

        status_counts[triage["status"]] += 1
        diagnostic_flags = _diagnostic_flags(
            observations,
            contexts,
        )
        registry_status = str(
            registry_resolution.get("status") or "unresolved"
        )
        if registry_status == "resolved":
            diagnostic_flags.append("technology_registry_resolved")
        elif registry_status == "recognized_unmapped":
            diagnostic_flags.append(
                "technology_registry_recognized_unmapped"
            )
        elif registry_status == "ambiguous":
            diagnostic_flags.append("technology_registry_ambiguous")

        compound = detect_possible_compound_requirement(
            {
                **candidate,
                "observation_contexts": contexts,
            }
        )
        if compound.get("possible"):
            diagnostic_flags.append("possible_compound_requirement")

        candidate["diagnostic_flags"] = sorted(set(diagnostic_flags))
        candidate["observation_contexts"] = contexts
        candidate["technology_registry_resolution"] = (
            registry_resolution
        )
        candidate["triage"] = triage
        enriched_candidates.append(candidate)

    registry = get_default_registry()
    registry_resolved = sum(
        1
        for candidate in enriched_candidates
        if (
            candidate.get("technology_registry_resolution", {})
            or {}
        ).get("status")
        == "resolved"
    )
    registry_recognized_unmapped = sum(
        1
        for candidate in enriched_candidates
        if (
            candidate.get("technology_registry_resolution", {})
            or {}
        ).get("status")
        == "recognized_unmapped"
    )
    registry_unresolved = len(enriched_candidates) - registry_resolved

    manual_review_eligible = [
        candidate
        for candidate in enriched_candidates
        if (
            candidate.get("technology_registry_resolution", {})
            or {}
        ).get("status")
        != "resolved"
    ]
    pending_human_review = [
        candidate
        for candidate in manual_review_eligible
        if (
            candidate.get("triage", {}) or {}
        ).get("status", "unreviewed")
        == "unreviewed"
    ]
    reviewed_human_queue = (
        len(manual_review_eligible)
        - len(pending_human_review)
    )

    report["triage_version"] = TRIAGE_VERSION
    report["technology_registry_version"] = registry.version
    report["registry_resolved_candidate_count"] = registry_resolved
    report["registry_recognized_unmapped_candidate_count"] = (
        registry_recognized_unmapped
    )
    report["registry_unresolved_candidate_count"] = (
        registry_unresolved
    )
    report["manual_review_eligible_candidate_count"] = (
        len(manual_review_eligible)
    )
    report["human_reviewed_queue_count"] = reviewed_human_queue
    report["pending_human_review_candidate_count"] = (
        len(pending_human_review)
    )
    # Backward-compatible field: from v1.0.1 onward this means candidates
    # still awaiting a human decision, not merely all registry-unresolved rows.
    report["manual_review_queue_count"] = (
        len(pending_human_review)
    )
    report["triage_status_counts"] = status_counts
    report["reviewed_candidate_count"] = (
        len(enriched_candidates) - status_counts["unreviewed"]
    )
    report["unreviewed_candidate_count"] = status_counts["unreviewed"]
    report["candidates"] = enriched_candidates
    return report


def _load_default_discovery_report() -> dict[str, Any]:
    from database.job_match_manager import (
        list_latest_compatible_job_match_snapshots,
    )
    from job_discovery.matching import current_match_versions
    from taxonomy_discovery.observations import build_discovery_report

    versions = current_match_versions()
    if not isinstance(versions, dict):
        raise RuntimeError(
            "current_match_versions() did not return the expected dictionary."
        )

    match_version = str(versions.get("match_version") or "")
    scoring_version = str(versions.get("scoring_version") or "")
    taxonomy_version = str(versions.get("taxonomy_version") or "")
    if not all((match_version, scoring_version, taxonomy_version)):
        raise RuntimeError(
            "Current Job Match version identity is incomplete: "
            f"{versions!r}"
        )

    snapshots = list_latest_compatible_job_match_snapshots(
        match_version=match_version,
        scoring_version=scoring_version,
        taxonomy_version=taxonomy_version,
    )
    report = build_discovery_report(
        snapshots,
        match_version=match_version,
        scoring_version=scoring_version,
        taxonomy_version=taxonomy_version,
    )
    if not isinstance(report, dict):
        raise RuntimeError("TQ-D2 discovery report is not a dictionary.")
    return report


def _load_compatible_snapshots(
    discovery_report: dict[str, Any],
) -> list[dict[str, Any]]:
    from database.job_match_manager import (
        list_latest_compatible_job_match_snapshots,
    )

    snapshots = list_latest_compatible_job_match_snapshots(
        match_version=str(discovery_report.get("match_version") or ""),
        scoring_version=str(discovery_report.get("scoring_version") or ""),
        taxonomy_version=str(discovery_report.get("taxonomy_version") or ""),
    )
    return [row for row in snapshots or [] if isinstance(row, dict)]


def build_triage_report(
    *,
    discovery_report: dict[str, Any] | None = None,
    snapshots: Iterable[dict[str, Any]] | None = None,
    reviews: Iterable[dict[str, Any]] | None = None,
    review_db_path: str | None = None,
) -> dict[str, Any]:
    """Build the TQ-D2.5 triage view over the existing TQ-D2 ledger."""
    report = discovery_report or _load_default_discovery_report()
    snapshot_rows = (
        list(snapshots)
        if snapshots is not None
        else _load_compatible_snapshots(report)
    )

    if reviews is None:
        from database.taxonomy_discovery_review_manager import list_reviews

        reviews = list_reviews(
            taxonomy_version=str(report.get("taxonomy_version") or ""),
            db_path=review_db_path,
        )

    return enrich_discovery_report(
        report,
        snapshot_rows,
        reviews=reviews,
    )
