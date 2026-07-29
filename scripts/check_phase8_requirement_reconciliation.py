from __future__ import annotations

from tailoring.phase8_requirement_reconciliation import (
    reconcile_final_requirement_matches,
)


def main() -> int:
    requirement_id = "req-access"
    bullet = (
        "Implemented backend data access and applied Row-Level Security "
        "policies to secure database operations."
    )
    before = {
        "canonical_requirements": [
            {
                "requirement_id": requirement_id,
                "text": (
                    "Implement authentication workflows, Row-Level Security "
                    "policies, and secure database access"
                ),
                "importance": "required",
                "match_label": "weak",
                "match_value": 0.2,
                "evidence_strength": 2,
                "group_weight_fraction": 1.0,
            }
        ],
        "score_weights": {
            "required_core_coverage": 0.8,
            "preferred_coverage": 0.1,
            "evidence_strength": 0.1,
        },
    }
    after = {
        **before,
        "canonical_requirements": [
            {
                **before["canonical_requirements"][0],
                "match_label": "none",
                "match_value": 0.0,
                "evidence_strength": 0,
            }
        ],
    }
    project = {
        "project_id": "project-query",
        "title": "QueryAI",
        "draft_bullets": [bullet],
        "requirement_matches": [
            {
                "requirement_id": requirement_id,
                "requirement_text": (
                    "Implement authentication workflows, Row-Level Security "
                    "policies, and secure database access"
                ),
                "match_label": "direct",
                "evidence_snippets": [bullet],
            }
        ],
    }
    skills = {
        "skill_lines": [
            {
                "category": "Backend",
                "items": [
                    "authentication workflows",
                    "access control",
                ],
            }
        ],
        "skill_rankings": [
            {
                "skill": "authentication workflows",
                "matched_requirement_ids": [requirement_id],
            },
            {
                "skill": "access control",
                "matched_requirement_ids": [requirement_id],
            },
        ],
    }
    state = {
        "projects": {
            "recommended_projects": [project],
        },
        "skills": skills,
        "fit_result": {
            "tailored_projects_used": {
                "recommended_projects": [project],
            },
            "tailored_skills_used": skills,
        },
    }
    lineage = {
        "verified_project_bullets": [
            {
                "project_id": "project-query",
                "project": "QueryAI",
                "bullet": bullet,
                "supported": True,
            }
        ],
        "verified_skills": [
            {
                "category": "Backend",
                "skill": "authentication workflows",
                "supported": True,
            },
            {
                "category": "Backend",
                "skill": "access control",
                "supported": True,
            },
        ],
    }

    reconciled, report = reconcile_final_requirement_matches(
        before_analysis=before,
        after_analysis=after,
        generation_state=state,
        claim_lineage=lineage,
    )
    label = reconciled["canonical_requirements"][0][
        "match_label"
    ]
    passed = (
        label == "direct"
        and report["reconciled_requirement_count"] == 1
        and report["unresolved_regression_count"] == 0
    )
    print("Reconciled label:", label)
    print(
        "PHASE 8 FINAL EVIDENCE RECONCILIATION:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
