"""Verify that Phase 9B uses Phase 8's resolved current-scorer baseline."""

from __future__ import annotations

from tailoring.phase9b_blueprint_candidate import (
    PHASE9B_VERSION,
    build_blueprint_candidate,
)


def main() -> int:
    generation = {
        "application_id": 94,
        "generation_id": "ac8191407bea4aecac63b1330729e5ec",
        "status": "approved",
        "projects": {
            "recommended_projects": [
                {"title": "Generated project"}
            ]
        },
        "skills": {
            "skill_lines": [
                {
                    "category": "Programming",
                    "items": ["Python"],
                }
            ]
        },
        "fit_result": {
            "fit_one_page": True,
            "page_count": 1,
            "tailored_projects_used": {
                "recommended_projects": [
                    {"title": "Final fitted project"}
                ]
            },
            "tailored_skills_used": {
                "skill_lines": [
                    {
                        "category": "Programming",
                        "items": ["Python", "TypeScript"],
                    }
                ]
            },
        },
    }
    verification = {
        "phase8_version": (
            "phase8-before-after-verification-v7"
        ),
        "verification_id": "verification-v7",
        "verification_fingerprint": (
            "verification-v7-fingerprint"
        ),
        "generation_id": generation["generation_id"],
        "comparison_valid": True,
        "blueprint_ready": True,
        "blueprint_readiness_reasons": {
            "is_approved": True,
            "fits_one_page": True,
            "canonical_requirement_ids_stable": True,
            "no_required_core_regression": True,
            "no_claim_review_risks": True,
            "score_not_lower": True,
        },
        "comparison": {
            "before_score": 32,
            "after_score": 92,
            "score_delta": 60,
            "required_core_coverage_delta": 74,
            "improved_requirements": [],
            "important_regressions": [],
        },
        "claim_lineage": {
            "lineage_version": "phase8-claim-lineage-v2",
            "claim_review_required_count": 0,
        },
        "before_stable_analysis": {
            "deterministic_alignment_score": 32,
            "input_fingerprint": (
                "resolved-phase6d7-before-fingerprint"
            ),
        },
        "after_stable_analysis": {
            "deterministic_alignment_score": 92,
            "scoring_version": (
                "stable-evidence-v1.3-phase6d7"
            ),
            "capability_taxonomy_version": (
                "phase6d-capability-taxonomy-v1.2"
            ),
            "canonical_requirements": [],
        },
    }
    baseline = {
        "jd_profile": {
            "job_title": (
                "Junior AI and Full-Stack Software Engineer"
            ),
            "company": "Synthetic Test",
        },
        "resume_profile": {
            "education": [],
            "experience": [],
            "projects": [],
            "skills": {},
        },
        "stable_analysis": {
            "deterministic_alignment_score": 36,
            "input_fingerprint": (
                "stored-phase6d6-before-fingerprint"
            ),
        },
    }

    candidate = build_blueprint_candidate(
        application_id=94,
        generation_state=generation,
        verification=verification,
        baseline_report=baseline,
        role_family=(
            "AI & Full-Stack Software Engineering"
        ),
        candidate_name=(
            "AI & Full-Stack — App 94 — ac819140"
        ),
    )

    assert PHASE9B_VERSION == (
        "phase9b-blueprint-candidate-v3"
    )
    assert candidate["phase9b_version"] == PHASE9B_VERSION
    assert (
        candidate["score_summary"]["original_resume_score"]
        == 32
    )
    assert (
        candidate["score_summary"]["approved_tailored_score"]
        == 92
    )
    assert (
        candidate["evaluation_metadata"][
            "baseline_stable_fingerprint"
        ]
        == "resolved-phase6d7-before-fingerprint"
    )

    print("PHASE 9B RESOLVED BASELINE PROVENANCE: PASS")
    print("Phase 9B version:", PHASE9B_VERSION)
    print(
        "Candidate score summary:",
        candidate["score_summary"]["original_resume_score"],
        "->",
        candidate["score_summary"]["approved_tailored_score"],
    )
    print(
        "Baseline fingerprint:",
        candidate["evaluation_metadata"][
            "baseline_stable_fingerprint"
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
