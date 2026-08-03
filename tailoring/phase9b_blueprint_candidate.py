"""Phase 9B: promote verified Approved generations to global candidates."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from tailoring.phase8_verification import (
    build_final_resume_profile,
    build_resume_text_from_profile,
)
from tailoring.phase9b_role_family import (
    canonical_role_family_id,
    compact_requirement_summary,
    source_job_metadata,
)
from tailoring.tailoring_generation_fingerprint import (
    get_effective_generation_sections,
)


PHASE9B_VERSION = "phase9b-blueprint-candidate-v2"


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").replace("\u00a0", " ").split()
    ).strip()


def blueprint_candidate_eligibility(
    *,
    generation_state: dict[str, Any] | None,
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    generation = generation_state or {}
    result = verification or {}
    fit_result = generation.get("fit_result")
    if not isinstance(fit_result, dict):
        fit_result = {}

    generation_id = _clean(generation.get("generation_id"))
    verification_generation_id = _clean(
        result.get("generation_id")
    )
    reasons = {
        "approved_generation": (
            _clean(generation.get("status")).lower()
            == "approved"
        ),
        "verification_exists": bool(result),
        "verification_matches_generation": bool(
            generation_id
            and verification_generation_id == generation_id
        ),
        "comparison_valid": bool(
            result.get("comparison_valid")
        ),
        "phase8_blueprint_ready": bool(
            result.get("blueprint_ready")
        ),
        "fits_one_page": (
            fit_result.get("fit_one_page") is True
        ),
        "no_claim_review_risks": (
            int(
                (
                    result.get("claim_lineage") or {}
                ).get("claim_review_required_count", 0)
                or 0
            )
            == 0
        ),
    }
    return {
        "eligible": all(reasons.values()),
        "reasons": reasons,
    }


def _candidate_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _evaluation_metadata(
    *,
    baseline_report: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    before = baseline_report.get("stable_analysis") or {}
    after = verification.get("after_stable_analysis") or {}
    comparison = verification.get("comparison") or {}
    requirements = compact_requirement_summary(verification)

    important = {
        "deal_breaker",
        "required",
        "core",
    }
    remaining_gaps = [
        row
        for row in requirements
        if row.get("importance") in important
        and row.get("match_label") == "none"
    ]

    return {
        "evaluation_seed_version": "phase9c-seed-v1",
        "baseline_stable_fingerprint": _clean(
            before.get("input_fingerprint")
        ),
        "source_scoring_version": _clean(
            after.get("scoring_version")
        ),
        "capability_taxonomy_version": _clean(
            after.get("capability_taxonomy_version")
        ),
        "source_jd_requirement_summary": requirements,
        "source_jd_requirement_count": len(requirements),
        "source_jd_remaining_important_gaps": remaining_gaps,
        "source_jd_remaining_important_gap_count": len(
            remaining_gaps
        ),
        "comparison_summary": {
            "before_score": int(
                comparison.get("before_score", 0) or 0
            ),
            "after_score": int(
                comparison.get("after_score", 0) or 0
            ),
            "score_delta": int(
                comparison.get("score_delta", 0) or 0
            ),
            "required_core_coverage_delta": int(
                comparison.get(
                    "required_core_coverage_delta",
                    0,
                )
                or 0
            ),
            "improved_requirement_ids": [
                _clean(row.get("requirement_id"))
                for row in comparison.get(
                    "improved_requirements",
                    [],
                )
                or []
                if isinstance(row, dict)
                and _clean(row.get("requirement_id"))
            ],
            "important_regression_count": len(
                comparison.get("important_regressions", [])
                or []
            ),
        },
    }


def build_blueprint_candidate(
    *,
    application_id: int,
    generation_state: dict[str, Any],
    verification: dict[str, Any],
    baseline_report: dict[str, Any],
    role_family: str,
    candidate_name: str,
    notes: str = "",
    evidence_opportunity: dict[str, Any] | None = None,
    role_family_id: str | None = None,
    role_family_suggestion: dict[str, Any] | None = None,
    candidate_name_source: str = "user_or_ui",
    notes_source: str = "user_or_ui",
) -> dict[str, Any]:
    eligibility = blueprint_candidate_eligibility(
        generation_state=generation_state,
        verification=verification,
    )
    if not eligibility["eligible"]:
        failed = [
            name
            for name, passed in eligibility["reasons"].items()
            if not passed
        ]
        raise ValueError(
            "The Approved generation is not eligible for blueprint "
            f"promotion. Failed gates: {', '.join(failed)}"
        )

    cleaned_role_family = _clean(role_family)
    cleaned_name = _clean(candidate_name)
    if not cleaned_role_family:
        raise ValueError("Role family is required.")
    if not cleaned_name:
        raise ValueError("Candidate name is required.")

    effective = get_effective_generation_sections(
        generation_state
    )
    projects = effective.get("projects")
    skills = effective.get("skills")
    if not isinstance(projects, dict) or not isinstance(
        skills,
        dict,
    ):
        raise ValueError(
            "The Approved generation does not contain final Projects "
            "and Skills snapshots."
        )

    fit_result = deepcopy(
        generation_state.get("fit_result") or {}
    )
    stable_before = baseline_report.get("stable_analysis") or {}
    stable_after = (
        verification.get("after_stable_analysis") or {}
    )
    opportunity = evidence_opportunity or {}
    final_resume_profile = build_final_resume_profile(
        baseline_report.get("resume_profile", {}) or {},
        generation_state,
    )
    final_resume_text = build_resume_text_from_profile(
        final_resume_profile
    )
    cleaned_role_family_id = _clean(role_family_id) or (
        canonical_role_family_id(cleaned_role_family)
    )

    snapshot = {
        "phase9b_version": PHASE9B_VERSION,
        "source_application_id": int(application_id),
        "source_generation_id": _clean(
            generation_state.get("generation_id")
        ),
        "source_verification_id": _clean(
            verification.get("verification_id")
        ),
        "source_verification_fingerprint": _clean(
            verification.get("verification_fingerprint")
        ),
        "source_job": source_job_metadata(baseline_report),
        "role_family_id": cleaned_role_family_id,
        "role_family": cleaned_role_family,
        "role_family_suggestion": deepcopy(
            role_family_suggestion or {}
        ),
        "candidate_name": cleaned_name,
        "notes": _clean(notes),
        "candidate_metadata": {
            "candidate_name_source": _clean(
                candidate_name_source
            )
            or "user_or_ui",
            "notes_source": _clean(notes_source)
            or "user_or_ui",
            "notes_optional": True,
            "notes_influence_scoring": False,
            "metadata_in_candidate_fingerprint": False,
        },
        "status": "candidate",
        "global_scope": True,
        "projects": deepcopy(projects),
        "skills": deepcopy(skills),
        "resume_profile_snapshot": deepcopy(
            final_resume_profile
        ),
        "resume_text_snapshot": final_resume_text,
        "fit_result": fit_result,
        "score_summary": {
            "original_resume_score": int(
                stable_before.get(
                    "deterministic_alignment_score",
                    0,
                )
                or 0
            ),
            "approved_tailored_score": int(
                stable_after.get(
                    "deterministic_alignment_score",
                    0,
                )
                or 0
            ),
            "evidence_potential_score": (
                int(opportunity.get("potential_score", 0) or 0)
                if opportunity
                else None
            ),
        },
        "quality_gates": deepcopy(
            verification.get(
                "blueprint_readiness_reasons",
                {},
            )
        ),
        "claim_lineage": {
            "lineage_version": (
                verification.get("claim_lineage") or {}
            ).get("lineage_version"),
            "claim_review_required_count": int(
                (
                    verification.get("claim_lineage") or {}
                ).get("claim_review_required_count", 0)
                or 0
            ),
        },
        "canonical_requirement_ids": sorted(
            _clean(row.get("requirement_id"))
            for row in stable_after.get(
                "canonical_requirements",
                [],
            )
            or []
            if isinstance(row, dict)
            and _clean(row.get("requirement_id"))
        ),
        "evaluation_metadata": _evaluation_metadata(
            baseline_report=baseline_report,
            verification=verification,
        ),
        "provenance": {
            "source_generation_id": _clean(
                generation_state.get("generation_id")
            ),
            "phase8_verification_id": _clean(
                verification.get("verification_id")
            ),
            "phase8_verification_fingerprint": _clean(
                verification.get("verification_fingerprint")
            ),
            "phase8_version": _clean(
                verification.get("phase8_version")
            ),
            "phase9a_evidence_opportunity_id": _clean(
                opportunity.get("opportunity_id")
            ),
            "phase9a_evidence_opportunity_fingerprint": _clean(
                opportunity.get("opportunity_fingerprint")
            ),
            "full_debug_json_embedded": False,
        },
        "evidence_opportunity_id": _clean(
            opportunity.get("opportunity_id")
        ),
        "evidence_opportunity_fingerprint": _clean(
            opportunity.get("opportunity_fingerprint")
        ),
    }

    fingerprint_payload = {
        "phase9b_version": PHASE9B_VERSION,
        "source_generation_id": snapshot[
            "source_generation_id"
        ],
        "source_verification_fingerprint": snapshot[
            "source_verification_fingerprint"
        ],
        "role_family_id": snapshot["role_family_id"],
        "role_family": snapshot["role_family"],
        "resume_profile_snapshot": snapshot[
            "resume_profile_snapshot"
        ],
        "fit_result": snapshot["fit_result"],
    }
    snapshot["candidate_fingerprint"] = (
        _candidate_fingerprint(fingerprint_payload)
    )
    return snapshot
