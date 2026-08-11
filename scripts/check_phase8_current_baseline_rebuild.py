"""Zero-cost smoke check for Phase 8 current-scorer baseline rebuild."""

from __future__ import annotations

from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.phase8_verification import (
    PHASE8_VERIFICATION_VERSION,
    build_phase8_verification,
)


ROW = {
    "requirement_id": "req_python",
    "text": "Hands-on experience with Python",
    "importance": "required",
    "match_label": "direct",
    "evidence_strength": 5,
}


def stable(score, rows, *, version, fingerprint):
    return {
        "scoring_version": version,
        "deterministic_alignment_score": score,
        "alignment_band": "partial alignment",
        "required_core_coverage_score": score,
        "preferred_coverage_score": 0,
        "evidence_strength_score": 60,
        "canonical_requirements": rows,
        "input_fingerprint": fingerprint,
    }


def main():
    stored_old = stable(
        36,
        [
            {
                **ROW,
                "requirement_id": "req_heading",
                "text": "Key Responsibilities",
                "match_label": "none",
                "evidence_strength": 0,
            },
            ROW,
        ],
        version="stable-evidence-v1.3-phase6d6",
        fingerprint="stored-old",
    )
    rebuilt_before = stable(
        50,
        [ROW],
        version=SCORING_VERSION,
        fingerprint="rebuilt-before",
    )
    current_after = stable(
        60,
        [ROW],
        version=SCORING_VERSION,
        fingerprint="current-after",
    )

    baseline = {
        "stable_analysis": stored_old,
        "resume_profile": {
            "projects": [],
            "skills": {},
            "experience": [],
            "education": [],
        },
        "jd_profile": {},
        "keyword_match": {"present": [], "missing": []},
        "bullets": {"bullet_quality_avg": 80},
        "structure": {"structure_score": 100},
    }
    generation = {
        "application_id": 94,
        "generation_id": "generation-a",
        "status": "approved",
        "updated_at": "2026-08-03T17:00:00",
        "candidate_pool": [],
        "projects": {"recommended_projects": []},
        "skills": {"skill_lines": []},
        "fit_result": {"fit_one_page": True, "page_count": 1},
    }

    with patch(
        "tailoring.phase8_verification.build_stable_analysis",
        side_effect=[rebuilt_before, current_after],
    ) as mocked_build:
        result = build_phase8_verification(
            baseline_report=baseline,
            generation_state=generation,
            raw_jd_text=(
                "Job Description\n\n"
                "Hands-on experience with Python."
            ),
        )

    assert mocked_build.call_count == 2
    assert result["comparison_valid"] is True
    assert result["blueprint_ready"] is True
    assert result["comparison"]["before_score"] == 50
    assert (
        result["raw_comparison_before_reconciliation"]["after_score"]
        == 60
    )
    assert (
        result["comparison"]["after_score"]
        == result["after_stable_analysis"][
            "deterministic_alignment_score"
        ]
    )
    assert result["comparison"]["after_score"] >= 60
    assert result["comparison"]["removed_requirements"] == []
    assert result["comparison"]["added_requirements"] == []
    assert result["baseline_resolution"]["rebuilt"] is True
    assert (
        result["baseline_resolution"]["stored_scoring_version"]
        == "stable-evidence-v1.3-phase6d6"
    )
    assert (
        result["baseline_resolution"]["resolved_scoring_version"]
        == SCORING_VERSION
    )
    assert (
        result["phase8_version"]
        == PHASE8_VERIFICATION_VERSION
    )

    print("PHASE 8 CURRENT-SCORER BASELINE REBUILD: PASS")
    print(f"Phase 8 version: {PHASE8_VERIFICATION_VERSION}")
    print(
        "Baseline versions:",
        result["baseline_resolution"]["stored_scoring_version"],
        "->",
        result["baseline_resolution"]["resolved_scoring_version"],
    )
    print(
        "Raw scorer comparison:",
        result["raw_comparison_before_reconciliation"][
            "before_score"
        ],
        "->",
        result["raw_comparison_before_reconciliation"][
            "after_score"
        ],
    )
    print(
        "Post-reconciliation comparison:",
        result["comparison"]["before_score"],
        "->",
        result["comparison"]["after_score"],
    )


if __name__ == "__main__":
    main()
