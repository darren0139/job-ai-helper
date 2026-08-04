"""Phase 9C deterministic cross-JD evaluation of one frozen blueprint."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from statistics import fmean, pstdev
from typing import Any, Iterable

from analysis_stability.stable_evidence_scoring import (
    MATCH_VALUES,
    SCORING_VERSION,
    build_deterministic_keyword_match,
    build_resume_evidence_index,
    build_stable_analysis,
    canonicalise_requirements,
    compute_deterministic_alignment,
)
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.phase9b_blueprint_candidate import PHASE9B_VERSION
from tailoring.phase9b_role_family import (
    canonical_role_family_id,
    suggest_role_family,
)


PHASE9C_VERSION = "phase9c-cross-jd-evaluation-v1"
PHASE9C_POLICY_VERSION = "phase9c-same-family-explicit-scope-v3"
PHASE9C_EVIDENCE_LINK_VERSION = "phase9c-full-snapshot-evidence-v2"
PORTABILITY_PASS_THRESHOLD = 65
MINIMUM_NON_PROVISIONAL_JDS = 2
IMPORTANT = {"deal_breaker", "required", "core"}


class Phase9CEvaluationError(ValueError):
    """Raised when Phase 9C cannot make a reproducible comparison."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    return " ".join(
        "".join(character if character.isalnum() else " " for character in text).split()
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text_sha256(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def fingerprint_semantic_identity(value: dict[str, Any]) -> str:
    """Public deterministic hash used by cache regression tests."""
    return _fingerprint(value)


def source_requirement_summary_fingerprint(
    candidate: dict[str, Any],
) -> str:
    metadata = candidate.get("evaluation_metadata") or {}
    rows = metadata.get("source_jd_requirement_summary") or []
    compact = sorted(
        (
            {
                "requirement_id": _clean(row.get("requirement_id")),
                "text": _clean(row.get("text")),
                "importance": _clean(row.get("importance")),
                "match_label": _clean(row.get("match_label")).lower(),
                "evidence_strength": int(row.get("evidence_strength", 0) or 0),
                "capability_id": _clean(row.get("capability_id")),
            }
            for row in rows
            if isinstance(row, dict)
        ),
        key=lambda row: (row["requirement_id"], row["text"]),
    )
    if not compact:
        raise Phase9CEvaluationError(
            "The Phase 9B source requirement summary is missing."
        )
    return _fingerprint(compact)


def _candidate_role_family_id(candidate: dict[str, Any]) -> str:
    return _clean(candidate.get("role_family_id")) or canonical_role_family_id(
        _clean(candidate.get("role_family"))
    )


def validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate all immutable Phase 9B v3 and provenance gates."""
    if not isinstance(candidate, dict):
        raise Phase9CEvaluationError("A Phase 9B candidate is required.")
    if _clean(candidate.get("status")).lower() == "archived":
        raise Phase9CEvaluationError("Archived candidates cannot be evaluated in v1.")
    if _clean(candidate.get("status")).lower() not in {"candidate", "active"}:
        raise Phase9CEvaluationError("The selected candidate is not active.")
    if _clean(candidate.get("phase9b_version")) != PHASE9B_VERSION:
        raise Phase9CEvaluationError(
            f"Phase 9C requires {PHASE9B_VERSION}."
        )
    for field in ("candidate_id", "candidate_fingerprint", "role_family"):
        if not _clean(candidate.get(field)):
            raise Phase9CEvaluationError(f"Candidate field {field} is required.")
    role_family_id = _candidate_role_family_id(candidate)
    if not role_family_id:
        raise Phase9CEvaluationError("Candidate role_family_id is required.")

    profile = candidate.get("resume_profile_snapshot")
    resume_text = candidate.get("resume_text_snapshot")
    if not isinstance(profile, dict) or not _clean(resume_text):
        raise Phase9CEvaluationError(
            "Both frozen resume_profile_snapshot and resume_text_snapshot are required."
        )
    missing_sections = [
        field
        for field in ("education", "experience", "projects", "skills")
        if field not in profile
    ]
    if missing_sections:
        raise Phase9CEvaluationError(
            "Frozen resume profile is missing sections: "
            + ", ".join(missing_sections)
        )

    metadata = candidate.get("evaluation_metadata") or {}
    if _clean(metadata.get("source_scoring_version")) != SCORING_VERSION:
        raise Phase9CEvaluationError(
            "Candidate source scoring version does not match production."
        )
    taxonomy_version = get_default_taxonomy().version
    if _clean(metadata.get("capability_taxonomy_version")) != taxonomy_version:
        raise Phase9CEvaluationError(
            "Candidate capability taxonomy version does not match production."
        )
    if not _clean(candidate.get("source_verification_fingerprint")):
        raise Phase9CEvaluationError(
            "source_verification_fingerprint is required."
        )
    source_summary_fingerprint = source_requirement_summary_fingerprint(candidate)

    lineage = candidate.get("claim_lineage") or {}
    if int(lineage.get("claim_review_required_count", 0) or 0) != 0:
        raise Phase9CEvaluationError(
            "Candidates with claim-review risks cannot be evaluated."
        )
    gates = candidate.get("quality_gates") or {}
    required_gates = (
        "is_approved",
        "fits_one_page",
        "canonical_requirement_ids_stable",
        "no_required_core_regression",
        "no_claim_review_risks",
        "score_not_lower",
    )
    failed = [gate for gate in required_gates if gates.get(gate) is not True]
    if failed:
        raise Phase9CEvaluationError(
            "Candidate quality gates are not satisfied: " + ", ".join(failed)
        )
    canonical_ids = sorted(
        _clean(value) for value in candidate.get("canonical_requirement_ids", []) if _clean(value)
    )
    if not canonical_ids:
        raise Phase9CEvaluationError("Candidate canonical requirement IDs are missing.")

    return {
        "role_family_id": role_family_id,
        "taxonomy_version": taxonomy_version,
        "source_requirement_summary_fingerprint": source_summary_fingerprint,
        "canonical_requirement_ids": canonical_ids,
    }


def _jd_key(jd: dict[str, Any]) -> str:
    canonical = _clean(jd.get("canonical_jd_id"))
    if canonical:
        return canonical
    library_id = jd.get("id")
    if library_id is None:
        raise Phase9CEvaluationError("Every target must be a saved JD-library record.")
    return f"library-jd-{int(library_id)}"


def _canonical_jd(jd: dict[str, Any]) -> dict[str, Any]:
    profile = jd.get("jd_profile")
    if not isinstance(profile, dict):
        raise Phase9CEvaluationError(f"JD {_jd_key(jd)} has no jd_profile.")
    return canonicalise_requirements(
        jd_profile=deepcopy(profile),
        raw_jd_text=str(jd.get("raw_text") or ""),
    )


def _canonical_requirement_fingerprint(canonical: dict[str, Any]) -> str:
    rows = [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "text": _clean(row.get("text")),
            "importance": _clean(row.get("importance")),
            "atomic_group_id": _clean(row.get("atomic_group_id")),
            "group_weight_fraction": row.get("group_weight_fraction"),
        }
        for row in canonical.get("requirements", [])
        if isinstance(row, dict)
    ]
    return _fingerprint(rows)


def classify_jd_role_family(
    candidate: dict[str, Any],
    jd: dict[str, Any],
) -> dict[str, Any]:
    profile = deepcopy(jd.get("jd_profile") or {})
    profile.setdefault("job_title", _clean(jd.get("title")))
    profile.setdefault("company", _clean(jd.get("company")))
    suggestion = suggest_role_family({"jd_profile": profile})
    candidate_family_id = _candidate_role_family_id(candidate)
    classified_id = _clean(suggestion.get("role_family_id")) or canonical_role_family_id(
        _clean(suggestion.get("role_family"))
    )
    confidence = _clean(suggestion.get("confidence")).lower() or "low"
    if confidence == "low":
        status = "uncertain"
    elif classified_id == candidate_family_id:
        status = "same"
    else:
        status = "different"
    return {
        "classified_role_family_id": classified_id,
        "classified_role_family": _clean(suggestion.get("role_family")),
        "family_match_status": status,
        "classification_confidence": confidence,
        "matched_terms": list(suggestion.get("matched_terms") or []),
    }


def _application_ids(jd: dict[str, Any]) -> set[int]:
    values = list(jd.get("application_ids") or [])
    if jd.get("application_id") is not None:
        values.append(jd.get("application_id"))
    output: set[int] = set()
    for value in values:
        try:
            output.add(int(value))
        except (TypeError, ValueError):
            continue
    return output


def _optional_source_identity(candidate: dict[str, Any]) -> dict[str, str]:
    identity = candidate.get("source_jd_identity") or {}
    metadata = candidate.get("evaluation_metadata") or {}
    return {
        "canonical_jd_id": _clean(
            identity.get("canonical_jd_id")
            or metadata.get("source_canonical_jd_id")
        ),
        "source_version_id": _clean(
            identity.get("source_version_id")
            or metadata.get("source_version_id")
        ),
        "raw_jd_sha256": _clean(
            identity.get("raw_jd_sha256")
            or metadata.get("source_raw_jd_sha256")
        ),
    }


def resolve_source_jd(
    candidate: dict[str, Any],
    saved_jds: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve the source using every available immutable identity field."""
    validated = validate_candidate(candidate)
    source_application_id = int(candidate.get("source_application_id"))
    expected = _optional_source_identity(candidate)
    expected_ids = validated["canonical_requirement_ids"]
    qualifiers: list[tuple[dict[str, Any], dict[str, Any]]] = []
    diagnostics: list[dict[str, Any]] = []

    for jd in saved_jds:
        if not isinstance(jd, dict):
            continue
        canonical = _canonical_jd(jd)
        actual_ids = sorted(
            _clean(row.get("requirement_id"))
            for row in canonical.get("requirements", [])
            if isinstance(row, dict) and _clean(row.get("requirement_id"))
        )
        comparisons = {
            "source_application_link": source_application_id in _application_ids(jd),
            "canonical_requirement_ids": actual_ids == expected_ids,
            "scorer_version": (
                _clean((candidate.get("evaluation_metadata") or {}).get("source_scoring_version"))
                == SCORING_VERSION
            ),
            "taxonomy_version": (
                _clean((candidate.get("evaluation_metadata") or {}).get("capability_taxonomy_version"))
                == get_default_taxonomy().version
            ),
        }
        if expected["canonical_jd_id"]:
            comparisons["canonical_jd_id"] = (
                _clean(jd.get("canonical_jd_id")) == expected["canonical_jd_id"]
            )
        if expected["source_version_id"]:
            comparisons["source_version_id"] = (
                _clean(jd.get("source_version_id")) == expected["source_version_id"]
            )
        if expected["raw_jd_sha256"]:
            comparisons["raw_jd_sha256"] = (
                _text_sha256(jd.get("raw_text")) == expected["raw_jd_sha256"]
            )
        diagnostic = {
            "jd_key": _jd_key(jd),
            "comparisons": comparisons,
            "actual_canonical_jd_id": _clean(jd.get("canonical_jd_id")),
            "actual_source_version_id": _clean(jd.get("source_version_id")),
            "actual_raw_jd_sha256": _text_sha256(jd.get("raw_text")),
            "actual_canonical_requirement_ids": actual_ids,
        }
        diagnostics.append(diagnostic)
        if all(comparisons.values()):
            qualifiers.append((jd, {**diagnostic, "canonical": canonical}))

    if not qualifiers:
        raise Phase9CEvaluationError(
            "No saved JD satisfies the complete source-JD identity."
        )
    if len(qualifiers) != 1:
        keys = ", ".join(_jd_key(item[0]) for item in qualifiers)
        raise Phase9CEvaluationError(
            "Source-JD identity is ambiguous; qualifying records: " + keys
        )
    return qualifiers[0]


def _scope_row(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    explicitly_allowed_uncertain: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    canonical = _canonical_jd(jd)
    family = classify_jd_role_family(candidate, jd)
    jd_key = _jd_key(jd)
    status = family["family_match_status"]
    if status == "same":
        decision = "evaluated"
        reason = "same_role_family"
    elif status == "uncertain" and jd_key in explicitly_allowed_uncertain:
        decision = "evaluated"
        reason = "uncertain_family_explicitly_included"
    elif status == "uncertain":
        decision = "excluded"
        reason = "uncertain_family_requires_explicit_inclusion"
    else:
        decision = "excluded"
        reason = "different_role_family"
    row = {
        "jd_key": jd_key,
        "library_jd_id": jd.get("id"),
        "canonical_jd_id": _clean(jd.get("canonical_jd_id")),
        "source_version_id": _clean(jd.get("source_version_id")),
        "raw_jd_sha256": _text_sha256(jd.get("raw_text")),
        **family,
        "selection_decision": decision,
        "selection_reason": reason,
        "canonical_requirement_fingerprint": _canonical_requirement_fingerprint(canonical),
        "stable_input_fingerprint": _stable_input_fingerprint(candidate, jd),
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
    }
    return row, canonical


def preview_selected_scope(
    candidate: dict[str, Any],
    selected_jds: Iterable[dict[str, Any]],
    *,
    explicitly_allowed_uncertain: Iterable[str] = (),
) -> list[dict[str, Any]]:
    allowed = {_clean(value) for value in explicitly_allowed_uncertain}
    output = [
        _scope_row(candidate, jd, allowed)[0]
        for jd in selected_jds
        if isinstance(jd, dict)
    ]
    return sorted(
        output,
        key=lambda row: (
            row["canonical_jd_id"],
            row["source_version_id"],
            row["raw_jd_sha256"],
            row["jd_key"],
        ),
    )


def selection_control_signature(
    candidate: dict[str, Any],
    selected_jds: Iterable[dict[str, Any]],
    *,
    explicitly_allowed_uncertain: Iterable[str] = (),
) -> str:
    rows = preview_selected_scope(
        candidate,
        selected_jds,
        explicitly_allowed_uncertain=explicitly_allowed_uncertain,
    )
    return _fingerprint(
        {
            "candidate_id": _clean(candidate.get("candidate_id")),
            "candidate_fingerprint": _clean(candidate.get("candidate_fingerprint")),
            "selected_scope": rows,
            "explicitly_allowed_uncertain": sorted(
                _clean(value) for value in explicitly_allowed_uncertain
            ),
        }
    )


def _stable_input_fingerprint(candidate: dict[str, Any], jd: dict[str, Any]) -> str:
    return _fingerprint(
        {
            "resume_profile_snapshot": candidate.get("resume_profile_snapshot"),
            "resume_text_snapshot_sha256": _text_sha256(
                candidate.get("resume_text_snapshot")
            ),
            "raw_jd_sha256": _text_sha256(jd.get("raw_text")),
            "jd_profile": jd.get("jd_profile"),
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": get_default_taxonomy().version,
            "retrieval_mode": "lexical",
        }
    )


def _source_analysis(
    candidate: dict[str, Any],
    source_jd: dict[str, Any],
    canonical: dict[str, Any],
) -> dict[str, Any]:
    seed_rows = (
        (candidate.get("evaluation_metadata") or {}).get(
            "source_jd_requirement_summary"
        )
        or []
    )
    seed_by_id = {
        _clean(row.get("requirement_id")): row
        for row in seed_rows
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    }
    current_ids = sorted(
        _clean(row.get("requirement_id"))
        for row in canonical.get("requirements", [])
        if isinstance(row, dict) and _clean(row.get("requirement_id"))
    )
    if current_ids != sorted(seed_by_id):
        raise Phase9CEvaluationError(
            "Resolved source-JD canonical requirements do not match the immutable Phase 9B seed."
        )
    hydrated: list[dict[str, Any]] = []
    for row in canonical.get("requirements", []):
        copy = deepcopy(row)
        seed = seed_by_id[_clean(copy.get("requirement_id"))]
        label = _clean(seed.get("match_label")).lower() or "none"
        if label not in MATCH_VALUES:
            raise Phase9CEvaluationError("Invalid source seed match label.")
        copy["match_label"] = label
        copy["match_value"] = MATCH_VALUES[label]
        copy["evidence_strength"] = int(seed.get("evidence_strength", 0) or 0)
        if _clean(seed.get("capability_id")):
            copy["capability_id"] = _clean(seed.get("capability_id"))
        copy["evidence"] = []
        copy["phase9c_source_seed_reused"] = True
        hydrated.append(copy)
    score = compute_deterministic_alignment(hydrated)
    expected_score = int(
        (candidate.get("score_summary") or {}).get("approved_tailored_score", 0)
        or 0
    )
    if score["deterministic_alignment_score"] != expected_score:
        raise Phase9CEvaluationError(
            "Source-JD parity failed: immutable Phase 9B seed no longer reproduces the approved score."
        )
    return {
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": get_default_taxonomy().version,
        "input_fingerprint": _stable_input_fingerprint(candidate, source_jd),
        "canonical_requirements": hydrated,
        **score,
        "source_jd_parity": {
            "accepted": True,
            "expected_approved_score": expected_score,
            "reproduced_score": score["deterministic_alignment_score"],
            "canonical_requirement_ids_match": True,
        },
    }


def _target_analysis(
    candidate: dict[str, Any],
    jd: dict[str, Any],
    canonical: dict[str, Any],
) -> dict[str, Any]:
    keyword_match = build_deterministic_keyword_match(
        requirements=canonical.get("requirements", []),
        acronym_map=canonical.get("acronym_map", {}),
        resume_profile=deepcopy(candidate["resume_profile_snapshot"]),
        raw_resume_text=str(candidate["resume_text_snapshot"]),
    )
    return build_stable_analysis(
        jd_profile=deepcopy(jd.get("jd_profile") or {}),
        keyword_match=keyword_match,
        raw_jd_text=str(jd.get("raw_text") or ""),
        raw_resume_text=str(candidate["resume_text_snapshot"]),
        resume_profile=deepcopy(candidate["resume_profile_snapshot"]),
        retrieval_mode_override="lexical",
    )


def _per_jd_result(
    *,
    candidate: dict[str, Any],
    jd: dict[str, Any],
    scope: dict[str, Any],
    analysis: dict[str, Any],
    is_source: bool,
) -> dict[str, Any]:
    rows = analysis.get("canonical_requirements", []) or []
    important_gaps = [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "text": _clean(row.get("text")),
            "importance": _clean(row.get("importance")),
        }
        for row in rows
        if isinstance(row, dict)
        and row.get("importance") in IMPORTANT
        and row.get("match_label") == "none"
    ]
    evidence_index = build_resume_evidence_index(
        candidate.get("resume_profile_snapshot"),
        str(candidate.get("resume_text_snapshot") or ""),
    )
    sections = {
        section: sum(1 for row in evidence_index if row.get("section") == section)
        for section in ("education", "experience", "projects", "skills", "raw_text")
    }
    return {
        **scope,
        "title": _clean(jd.get("title")),
        "company": _clean(jd.get("company")),
        "evaluation_mode": "immutable_source_seed" if is_source else "full_frozen_snapshot",
        "is_source_jd": is_source,
        "deterministic_alignment_score": int(
            analysis.get("deterministic_alignment_score", 0) or 0
        ),
        "alignment_band": _clean(analysis.get("alignment_band")),
        "required_core_coverage_score": int(
            analysis.get("required_core_coverage_score", 0) or 0
        ),
        "preferred_coverage_score": int(
            analysis.get("preferred_coverage_score", 0) or 0
        ),
        "evidence_strength_score": int(
            analysis.get("evidence_strength_score", 0) or 0
        ),
        "important_gap_count": len(important_gaps),
        "deal_breaker_gap_count": sum(
            gap["importance"] == "deal_breaker" for gap in important_gaps
        ),
        "important_gaps": important_gaps,
        "claim_review_required_count": 0,
        "canonical_requirement_ids": sorted(
            _clean(row.get("requirement_id"))
            for row in rows
            if isinstance(row, dict) and _clean(row.get("requirement_id"))
        ),
        "stable_input_fingerprint": scope["stable_input_fingerprint"],
        "evidence_sections_considered": sections,
        "source_jd_parity": analysis.get("source_jd_parity"),
    }


def aggregate_portability_metrics(
    per_jd_results: list[dict[str, Any]],
    *,
    source_required_core_score: int,
    pass_threshold: int = PORTABILITY_PASS_THRESHOLD,
) -> dict[str, Any]:
    if not per_jd_results:
        raise Phase9CEvaluationError("At least one eligible selected JD is required.")
    scores = [int(row["deterministic_alignment_score"]) for row in per_jd_results]
    required = [int(row["required_core_coverage_score"]) for row in per_jd_results]
    preferred = [int(row["preferred_coverage_score"]) for row in per_jd_results]
    evidence = [int(row["evidence_strength_score"]) for row in per_jd_results]
    mean_score = fmean(scores)
    deviation = pstdev(scores) if len(scores) > 1 else 0.0

    gap_groups: dict[str, dict[str, Any]] = {}
    for result in per_jd_results:
        for gap in result.get("important_gaps", []) or []:
            key = _normalise(gap.get("text")) or _clean(gap.get("requirement_id"))
            group = gap_groups.setdefault(
                key,
                {
                    "text": _clean(gap.get("text")),
                    "requirement_ids": set(),
                    "jd_keys": set(),
                },
            )
            group["requirement_ids"].add(_clean(gap.get("requirement_id")))
            group["jd_keys"].add(_clean(result.get("jd_key")))
    recurring = [
        {
            "text": group["text"],
            "count": len(group["jd_keys"]),
            "requirement_ids": sorted(value for value in group["requirement_ids"] if value),
            "jd_keys": sorted(value for value in group["jd_keys"] if value),
        }
        for group in gap_groups.values()
        if len(group["jd_keys"]) >= 2
    ]
    recurring.sort(key=lambda row: (-row["count"], _normalise(row["text"])))
    outlier_cutoff = mean_score - max(5.0, deviation)
    outliers = [
        {
            "jd_key": row["jd_key"],
            "score": int(row["deterministic_alignment_score"]),
            "distance_below_mean": round(
                mean_score - int(row["deterministic_alignment_score"]), 2
            ),
        }
        for row in per_jd_results
        if int(row["deterministic_alignment_score"]) < outlier_cutoff
    ]
    outliers.sort(key=lambda row: (row["score"], row["jd_key"]))
    required_average = fmean(required)
    source_denominator = max(1, int(source_required_core_score or 0))
    return {
        "evaluated_jd_count": len(scores),
        "mean_score": round(mean_score, 2),
        "minimum_score": min(scores),
        "maximum_score": max(scores),
        "score_spread": max(scores) - min(scores),
        "standard_deviation": round(deviation, 2),
        "pass_threshold": int(pass_threshold),
        "pass_rate": round(
            100 * sum(score >= pass_threshold for score in scores) / len(scores), 2
        ),
        "required_core_average": round(required_average, 2),
        "required_core_minimum": min(required),
        "required_core_retention": round(
            min(100.0, 100 * required_average / source_denominator), 2
        ),
        "preferred_average": round(fmean(preferred), 2),
        "preferred_minimum": min(preferred),
        "evidence_strength_average": round(fmean(evidence), 2),
        "evidence_strength_minimum": min(evidence),
        "recurring_important_gaps": recurring,
        "outlier_jds": outliers,
        "sample_sufficient": len(scores) >= MINIMUM_NON_PROVISIONAL_JDS,
        "provisional": len(scores) < MINIMUM_NON_PROVISIONAL_JDS,
    }


def evaluate_blueprint_candidate(
    *,
    candidate: dict[str, Any],
    selected_jds: list[dict[str, Any]],
    saved_jds_for_source_resolution: list[dict[str, Any]],
    explicitly_allowed_uncertain: Iterable[str] = (),
    pass_threshold: int = PORTABILITY_PASS_THRESHOLD,
) -> dict[str, Any]:
    """Evaluate only the explicitly supplied saved-JD scope."""
    original_candidate = _canonical_json(candidate)
    original_selected = _canonical_json(selected_jds)
    validated = validate_candidate(candidate)
    if not selected_jds:
        raise Phase9CEvaluationError("Explicitly select at least one target JD.")
    keys = [_jd_key(jd) for jd in selected_jds]
    if len(keys) != len(set(keys)):
        raise Phase9CEvaluationError("The explicit selected-JD scope contains duplicates.")

    source_jd, source_identity = resolve_source_jd(
        candidate,
        saved_jds_for_source_resolution,
    )
    source_family = classify_jd_role_family(candidate, source_jd)
    if source_family["family_match_status"] != "same":
        raise Phase9CEvaluationError(
            "The resolved source JD does not validate as the candidate role family."
        )
    source_canonical = source_identity.pop("canonical")
    source_analysis = _source_analysis(candidate, source_jd, source_canonical)

    allowed = {_clean(value) for value in explicitly_allowed_uncertain}
    prepared: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for jd in selected_jds:
        scope, canonical = _scope_row(candidate, jd, allowed)
        prepared.append((scope, canonical, jd))
    prepared.sort(
        key=lambda item: (
            item[0]["canonical_jd_id"],
            item[0]["source_version_id"],
            item[0]["raw_jd_sha256"],
            item[0]["jd_key"],
        )
    )
    semantic_scope = [scope for scope, _canonical, _jd in prepared]
    evaluated_prepared = [
        item for item in prepared if item[0]["selection_decision"] == "evaluated"
    ]
    if not evaluated_prepared:
        raise Phase9CEvaluationError(
            "No selected JD is eligible under the same-family policy."
        )

    candidate_identity = {
        "candidate_id": _clean(candidate.get("candidate_id")),
        "candidate_fingerprint": _clean(candidate.get("candidate_fingerprint")),
        "phase9b_version": _clean(candidate.get("phase9b_version")),
        "role_family_id": validated["role_family_id"],
        "role_family": _clean(candidate.get("role_family")),
        "resume_profile_snapshot_fingerprint": _fingerprint(
            candidate.get("resume_profile_snapshot")
        ),
        "resume_text_snapshot_sha256": _text_sha256(
            candidate.get("resume_text_snapshot")
        ),
        "source_verification_fingerprint": _clean(
            candidate.get("source_verification_fingerprint")
        ),
        "source_jd_requirement_summary_fingerprint": validated[
            "source_requirement_summary_fingerprint"
        ],
        "source_application_id": int(candidate.get("source_application_id")),
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": validated["taxonomy_version"],
    }
    policy = {
        "policy_version": PHASE9C_POLICY_VERSION,
        "evidence_link_version": PHASE9C_EVIDENCE_LINK_VERSION,
        "pass_threshold": int(pass_threshold),
        "minimum_non_provisional_jds": MINIMUM_NON_PROVISIONAL_JDS,
        "different_family_policy": "excluded",
        "uncertain_family_policy": "explicit_inclusion_required",
        "retrieval_mode_override": "lexical",
        "model_calls": 0,
        "embedding_calls": 0,
    }
    semantic_identity = {
        "phase9c_version": PHASE9C_VERSION,
        "candidate": candidate_identity,
        "policy": policy,
        "selected_jd_scope": semantic_scope,
    }
    evaluation_fingerprint = _fingerprint(semantic_identity)

    per_jd: list[dict[str, Any]] = []
    source_key = _jd_key(source_jd)
    for scope, canonical, jd in evaluated_prepared:
        is_source = scope["jd_key"] == source_key
        analysis = (
            source_analysis
            if is_source
            else _target_analysis(candidate, jd, canonical)
        )
        per_jd.append(
            _per_jd_result(
                candidate=candidate,
                jd=jd,
                scope=scope,
                analysis=analysis,
                is_source=is_source,
            )
        )
    aggregate = aggregate_portability_metrics(
        per_jd,
        source_required_core_score=int(
            source_analysis.get("required_core_coverage_score", 0) or 0
        ),
        pass_threshold=pass_threshold,
    )
    result = {
        "phase9c_version": PHASE9C_VERSION,
        "evaluation_fingerprint": evaluation_fingerprint,
        "selection_control_signature": selection_control_signature(
            candidate,
            selected_jds,
            explicitly_allowed_uncertain=allowed,
        ),
        "semantic_identity": semantic_identity,
        "candidate_scope": candidate_identity,
        "source_jd_identity": {
            key: value for key, value in source_identity.items() if key != "canonical"
        },
        "selected_jd_scope": semantic_scope,
        "excluded_jds": [
            row for row in semantic_scope if row["selection_decision"] == "excluded"
        ],
        "per_jd_results": per_jd,
        "aggregate_result": aggregate,
        "mutation_policy": {
            "candidate_mutated": False,
            "saved_jds_mutated": False,
        },
    }
    if _canonical_json(candidate) != original_candidate:
        raise AssertionError("Phase 9C mutated the candidate input.")
    if _canonical_json(selected_jds) != original_selected:
        raise AssertionError("Phase 9C mutated selected JD inputs.")
    if not math.isfinite(float(aggregate["mean_score"])):
        raise AssertionError("Aggregate score must be finite.")
    return result
