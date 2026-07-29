from __future__ import annotations

from tailoring.phase8_claim_lineage import audit_claim_lineage_v2


def main() -> int:
    bullet = (
        "Built full-stack help-desk workflows in a 4-person team using "
        "React and Supabase/PostgreSQL, including login, note submission, "
        "and ticket editing."
    )
    baseline = {
        "projects": [
            {
                "title": "QueryAI",
                "bullets": [
                    (
                        "Set up the project environment and integrated React "
                        "with Supabase, a PostgreSQL database."
                    ),
                    (
                        "Worked on the frontend, including the login page, "
                        "submit note, and edit ticket."
                    ),
                ],
            }
        ],
        "skills": {
            "languages": ["TypeScript"],
        },
    }
    generation = {
        "projects": {
            "recommended_projects": [
                {
                    "project_id": "project_queryai",
                    "title": "QueryAI",
                    "display_title": "QueryAI (React, Team of 4)",
                    "draft_bullets": [bullet],
                    "allocated_blueprint_bullets": [bullet],
                    "allocated_bullet_ids": ["bullet_queryai_1"],
                }
            ]
        },
        "skills": {
            "skill_lines": [
                {
                    "category": "Programming",
                    "items": ["TypeScript", "JavaScript"],
                }
            ]
        },
        "fit_result": {
            "tailored_projects_used": {
                "recommended_projects": [
                    {
                        "project_id": "project_queryai",
                        "title": "QueryAI",
                        "display_title": (
                            "QueryAI (React, Team of 4)"
                        ),
                        "draft_bullets": [bullet],
                        "allocated_blueprint_bullets": [bullet],
                        "allocated_bullet_ids": ["bullet_queryai_1"],
                    }
                ]
            },
            "tailored_skills_used": {
                "skill_lines": [
                    {
                        "category": "Programming",
                        "items": ["TypeScript", "JavaScript"],
                    }
                ]
            },
        },
    }

    result = audit_claim_lineage_v2(baseline, generation)
    risk_names = {
        row["skill"]
        for row in result["skill_review_risks"]
    }
    passed = (
        result["verified_project_bullet_count"] == 1
        and not result["project_bullet_review_risks"]
        and "TypeScript" not in risk_names
        and "JavaScript" in risk_names
    )

    print(
        "Verified project bullets:",
        result["verified_project_bullet_count"],
    )
    print("Skill review risks:", sorted(risk_names))
    print(
        "PHASE 8 CLAIM-LINEAGE IDENTITY CHECK:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
