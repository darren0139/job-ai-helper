from __future__ import annotations

import unittest

from tailoring.phase8_requirement_reconciliation import (
    reconcile_final_requirement_matches,
)


def requirement(
    requirement_id: str,
    text: str,
    label: str,
    *,
    importance: str = "required",
    evidence: list[dict] | None = None,
) -> dict:
    values = {
        "none": (0.0, 0),
        "weak": (0.2, 2),
        "transferable": (0.55, 3),
        "direct": (1.0, 5),
    }
    match_value, evidence_strength = values[label]
    return {
        "requirement_id": requirement_id,
        "text": text,
        "importance": importance,
        "group_weight_fraction": 1.0,
        "match_label": label,
        "match_value": match_value,
        "evidence_strength": evidence_strength,
        "evidence": evidence or [],
    }


def analysis(rows: list[dict], score: int = 0) -> dict:
    return {
        "canonical_requirements": rows,
        "deterministic_alignment_score": score,
        "required_core_coverage_score": score,
        "preferred_coverage_score": 0,
        "evidence_strength_score": 0,
        "score_weights": {
            "required_core_coverage": 0.8,
            "preferred_coverage": 0.1,
            "evidence_strength": 0.1,
        },
    }


def generation(
    projects: list[dict],
    skills: list[str] | None = None,
    rankings: list[dict] | None = None,
) -> dict:
    skill_payload = {
        "skill_lines": [
            {
                "category": "Skills",
                "items": skills or [],
            }
        ],
        "skill_rankings": rankings or [],
    }
    return {
        "projects": {
            "recommended_projects": projects,
        },
        "skills": skill_payload,
        "fit_result": {
            "tailored_projects_used": {
                "recommended_projects": projects,
            },
            "tailored_skills_used": skill_payload,
        },
    }


def lineage(
    *,
    project_bullets: list[tuple[str, str, str]] | None = None,
    skills: list[str] | None = None,
) -> dict:
    return {
        "verified_project_bullets": [
            {
                "project_id": project_id,
                "project": project_title,
                "bullet": bullet,
                "supported": True,
            }
            for project_id, project_title, bullet in (
                project_bullets or []
            )
        ],
        "verified_skills": [
            {
                "category": "Skills",
                "skill": skill,
                "supported": True,
            }
            for skill in (skills or [])
        ],
    }


class Phase8RequirementReconciliationTests(unittest.TestCase):
    def test_unchanged_experience_evidence_cannot_regress(self):
        before = analysis(
            [
                requirement(
                    "req-team",
                    "Collaborate in a software team",
                    "direct",
                    evidence=[
                        {
                            "section": "experience",
                            "text": "Collaborated with team members.",
                            "source": (
                                "resume_profile.experience[0].bullets[0]"
                            ),
                        }
                    ],
                )
            ],
            score=100,
        )
        after = analysis(
            [
                requirement(
                    "req-team",
                    "Collaborate in a software team",
                    "transferable",
                )
            ],
            score=55,
        )

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=before,
            after_analysis=after,
            generation_state=generation([]),
            claim_lineage=lineage(),
        )

        row = reconciled["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(
            report["reconciled_requirements"][0]["support_type"],
            "unchanged_resume_section",
        )

    def test_verified_project_and_skills_restore_direct_match(self):
        requirement_id = "req-access"
        bullet = (
            "Implemented backend data access through PostgREST and applied "
            "Row-Level Security policies to secure database operations."
        )
        project = {
            "project_id": "project-query",
            "title": "QueryAI",
            "display_title": "QueryAI (React, Team of 4)",
            "draft_bullets": [bullet],
            "requirement_matches": [
                {
                    "requirement_id": requirement_id,
                    "requirement_text": (
                        "Implement authentication workflows, Row-Level "
                        "Security policies, and secure database access"
                    ),
                    "match_label": "direct",
                    "evidence_snippets": [bullet],
                }
            ],
        }
        before = analysis(
            [
                requirement(
                    requirement_id,
                    (
                        "Implement authentication workflows, Row-Level "
                        "Security policies, and secure database access"
                    ),
                    "weak",
                )
            ],
            score=20,
        )
        after = analysis(
            [
                requirement(
                    requirement_id,
                    (
                        "Implement authentication workflows, Row-Level "
                        "Security policies, and secure database access"
                    ),
                    "none",
                )
            ],
            score=0,
        )
        state = generation(
            [project],
            skills=[
                "authentication workflows",
                "access control",
            ],
            rankings=[
                {
                    "skill": "authentication workflows",
                    "matched_requirement_ids": [requirement_id],
                },
                {
                    "skill": "access control",
                    "matched_requirement_ids": [requirement_id],
                },
            ],
        )

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=before,
            after_analysis=after,
            generation_state=state,
            claim_lineage=lineage(
                project_bullets=[
                    (
                        "project-query",
                        "QueryAI (React, Team of 4)",
                        bullet,
                    )
                ],
                skills=[
                    "authentication workflows",
                    "access control",
                ],
            ),
        )

        row = reconciled["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(
            report["reconciled_requirement_count"],
            1,
        )

    def test_partial_compound_evidence_is_capped_to_transferable(self):
        requirement_id = "req-product"
        final_bullet = (
            "Built a full-stack help-desk workflow in a 4-person team."
        )
        project = {
            "project_id": "project-query",
            "title": "QueryAI",
            "draft_bullets": [final_bullet],
            "requirement_matches": [
                {
                    "requirement_id": requirement_id,
                    "requirement_text": (
                        "Experience taking a software project from initial "
                        "setup to a working user-facing application"
                    ),
                    "match_label": "direct",
                    "evidence_snippets": [
                        (
                            "Set up the project environment and connected "
                            "the frontend to the backend."
                        ),
                        final_bullet,
                    ],
                }
            ],
        }
        before = analysis(
            [
                requirement(
                    requirement_id,
                    (
                        "Experience taking a software project from initial "
                        "setup to a working user-facing application"
                    ),
                    "transferable",
                )
            ],
            score=55,
        )
        after = analysis(
            [
                requirement(
                    requirement_id,
                    (
                        "Experience taking a software project from initial "
                        "setup to a working user-facing application"
                    ),
                    "none",
                )
            ],
            score=0,
        )

        reconciled, _ = reconcile_final_requirement_matches(
            before_analysis=before,
            after_analysis=after,
            generation_state=generation([project]),
            claim_lineage=lineage(
                project_bullets=[
                    (
                        "project-query",
                        "QueryAI",
                        final_bullet,
                    )
                ]
            ),
        )

        self.assertEqual(
            reconciled["canonical_requirements"][0]["match_label"],
            "transferable",
        )

    def test_unverified_mapping_does_not_hide_real_regression(self):
        requirement_id = "req-outage"
        project = {
            "project_id": "project-query",
            "title": "QueryAI",
            "draft_bullets": [
                "Built a React help-desk interface."
            ],
            "requirement_matches": [
                {
                    "requirement_id": requirement_id,
                    "requirement_text": (
                        "Managed global production outages for five years"
                    ),
                    "match_label": "direct",
                    "evidence_snippets": [
                        "Managed global production outages for five years."
                    ],
                }
            ],
        }
        before = analysis(
            [
                requirement(
                    requirement_id,
                    "Managed global production outages for five years",
                    "direct",
                )
            ],
            score=100,
        )
        after = analysis(
            [
                requirement(
                    requirement_id,
                    "Managed global production outages for five years",
                    "none",
                )
            ],
            score=0,
        )

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=before,
            after_analysis=after,
            generation_state=generation([project]),
            claim_lineage=lineage(
                project_bullets=[
                    (
                        "project-query",
                        "QueryAI",
                        "Built a React help-desk interface.",
                    )
                ]
            ),
        )

        self.assertEqual(
            reconciled["canonical_requirements"][0]["match_label"],
            "none",
        )
        self.assertEqual(
            report["unresolved_regression_count"],
            1,
        )

    def test_summary_scores_are_recalculated_after_reconciliation(self):
        before = analysis(
            [
                requirement(
                    "req-a",
                    "Python",
                    "direct",
                )
            ],
            score=100,
        )
        after = analysis(
            [
                requirement(
                    "req-a",
                    "Python",
                    "none",
                )
            ],
            score=0,
        )
        state = generation(
            [],
            skills=["Python"],
            rankings=[],
        )

        # No project mapping means this remains a real regression.
        reconciled, _ = reconcile_final_requirement_matches(
            before_analysis=before,
            after_analysis=after,
            generation_state=state,
            claim_lineage=lineage(skills=["Python"]),
        )
        self.assertEqual(
            reconciled["deterministic_alignment_score"],
            0,
        )

        # Unchanged source evidence restores it and recalculates all totals.
        before["canonical_requirements"][0]["evidence"] = [
            {
                "section": "experience",
                "text": "Used Python for data cleaning.",
                "source": "resume_profile.experience[0].bullets[0]",
            }
        ]
        reconciled, _ = reconcile_final_requirement_matches(
            before_analysis=before,
            after_analysis=after,
            generation_state=state,
            claim_lineage=lineage(skills=["Python"]),
        )
        self.assertEqual(
            reconciled["deterministic_alignment_score"],
            90,
        )
        self.assertEqual(
            reconciled["required_core_coverage_score"],
            100,
        )
        self.assertEqual(
            reconciled["evidence_strength_score"],
            100,
        )

    def test_app93_style_false_regressions_are_reconciled(self):
        rows_before = [
            requirement(
                "req-access",
                (
                    "Experience implementing authentication workflows or "
                    "database access control"
                ),
                "direct",
            ),
            requirement(
                "req-product",
                (
                    "Experience taking a software project from initial setup "
                    "to a working user-facing application"
                ),
                "transferable",
            ),
            requirement(
                "req-database",
                "Experience with SQLite or PostgreSQL database design",
                "transferable",
            ),
            requirement(
                "req-team",
                (
                    "Use Git and GitHub for version control and collaborate "
                    "effectively in a small software team"
                ),
                "direct",
                evidence=[
                    {
                        "section": "experience",
                        "text": "Collaborated with team members.",
                        "source": (
                            "resume_profile.experience[0].bullets[0]"
                        ),
                    }
                ],
            ),
            requirement(
                "req-rls",
                (
                    "Implement authentication workflows, Row-Level Security "
                    "policies, and secure database access"
                ),
                "weak",
            ),
        ]
        rows_after = [
            requirement(
                row["requirement_id"],
                row["text"],
                (
                    "transferable"
                    if row["requirement_id"] == "req-team"
                    else "none"
                ),
            )
            for row in rows_before
        ]

        query_bullet_1 = (
            "Built full-stack help-desk workflows in a 4-person team using "
            "React and Supabase/PostgreSQL, including login and ticket editing."
        )
        query_bullet_2 = (
            "Implemented backend data access through PostgREST and applied "
            "Row-Level Security policies to secure database operations."
        )
        job_bullet = (
            "Built a Streamlit application for résumé and job-description "
            "analysis."
        )

        query_matches = [
            {
                "requirement_id": "req-access",
                "requirement_text": rows_before[0]["text"],
                "match_label": "direct",
                "evidence_snippets": [
                    query_bullet_1,
                    query_bullet_2,
                ],
            },
            {
                "requirement_id": "req-product",
                "requirement_text": rows_before[1]["text"],
                "match_label": "direct",
                "evidence_snippets": [
                    "Set up the React and Supabase project environment.",
                    query_bullet_1,
                ],
            },
            {
                "requirement_id": "req-database",
                "requirement_text": rows_before[2]["text"],
                "match_label": "direct",
                "evidence_snippets": [
                    query_bullet_1,
                    query_bullet_2,
                    "database design",
                ],
            },
            {
                "requirement_id": "req-rls",
                "requirement_text": rows_before[4]["text"],
                "match_label": "direct",
                "evidence_snippets": [
                    query_bullet_1,
                    query_bullet_2,
                    "Row-Level Security",
                ],
            },
        ]
        projects = [
            {
                "project_id": "project-query",
                "title": "QueryAI",
                "display_title": "QueryAI (React, Team of 4)",
                "draft_bullets": [
                    query_bullet_1,
                    query_bullet_2,
                ],
                "requirement_matches": query_matches,
            },
            {
                "project_id": "project-job-ai",
                "title": "Job AI Helper",
                "draft_bullets": [job_bullet],
                "requirement_matches": [
                    {
                        "requirement_id": "req-product",
                        "requirement_text": rows_before[1]["text"],
                        "match_label": "direct",
                        "evidence_snippets": [
                            (
                                "Built a complete AI application with saved "
                                "sessions and user-facing workflows."
                            )
                        ],
                    }
                ],
            },
        ]
        skills = [
            "PostgreSQL",
            "access control",
            "authentication workflows",
            "database design",
            "GitHub",
        ]
        rankings = [
            {
                "skill": skill,
                "matched_requirement_ids": [
                    {
                        "PostgreSQL": "req-database",
                        "access control": "req-access",
                        "authentication workflows": "req-rls",
                        "database design": "req-database",
                        "GitHub": "req-team",
                    }[skill]
                ],
            }
            for skill in skills
        ]

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=analysis(rows_before, score=50),
            after_analysis=analysis(rows_after, score=20),
            generation_state=generation(
                projects,
                skills=skills,
                rankings=rankings,
            ),
            claim_lineage=lineage(
                project_bullets=[
                    (
                        "project-query",
                        "QueryAI (React, Team of 4)",
                        query_bullet_1,
                    ),
                    (
                        "project-query",
                        "QueryAI (React, Team of 4)",
                        query_bullet_2,
                    ),
                    (
                        "project-job-ai",
                        "Job AI Helper",
                        job_bullet,
                    ),
                ],
                skills=skills,
            ),
        )

        labels = {
            row["requirement_id"]: row["match_label"]
            for row in reconciled["canonical_requirements"]
        }
        self.assertEqual(labels["req-access"], "direct")
        self.assertEqual(labels["req-product"], "transferable")
        self.assertEqual(labels["req-database"], "direct")
        self.assertEqual(labels["req-team"], "direct")
        self.assertEqual(labels["req-rls"], "direct")
        self.assertEqual(
            report["unresolved_regression_count"],
            0,
        )


    def test_new_verified_evidence_upgrades_baseline_none(self):
        requirement_id = "req-access-new"
        requirement_text = (
            "Experience implementing authentication workflows or "
            "database access control"
        )
        bullet = (
            "Implemented backend data access through PostgREST and applied "
            "Row-Level Security policies to secure database operations."
        )
        project = {
            "project_id": "project-query",
            "title": "QueryAI",
            "display_title": "QueryAI (React, Team of 4)",
            "draft_bullets": [bullet],
            "requirement_matches": [
                {
                    "requirement_id": requirement_id,
                    "requirement_text": requirement_text,
                    "match_label": "direct",
                    "evidence_snippets": [bullet],
                }
            ],
        }
        state = generation(
            [project],
            skills=[
                "authentication workflows",
                "access control",
            ],
            rankings=[
                {
                    "skill": "authentication workflows",
                    "matched_requirement_ids": [requirement_id],
                },
                {
                    "skill": "access control",
                    "matched_requirement_ids": [requirement_id],
                },
            ],
        )

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=analysis(
                [requirement(requirement_id, requirement_text, "none")]
            ),
            after_analysis=analysis(
                [requirement(requirement_id, requirement_text, "none")]
            ),
            generation_state=state,
            claim_lineage=lineage(
                project_bullets=[
                    (
                        "project-query",
                        "QueryAI (React, Team of 4)",
                        bullet,
                    )
                ],
                skills=[
                    "authentication workflows",
                    "access control",
                ],
            ),
        )

        row = reconciled["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(
            row["phase8_reconciliation"]["support_type"],
            "verified_new_generation_evidence",
        )
        self.assertEqual(
            report["newly_supported_requirement_count"],
            1,
        )
        self.assertEqual(report["reconciled_requirement_count"], 0)

    def test_unverified_new_mapping_does_not_create_match(self):
        requirement_id = "req-outage-new"
        requirement_text = (
            "Managed global production outages for five years"
        )
        final_bullet = "Built a React help-desk interface."
        project = {
            "project_id": "project-query",
            "title": "QueryAI",
            "draft_bullets": [final_bullet],
            "requirement_matches": [
                {
                    "requirement_id": requirement_id,
                    "requirement_text": requirement_text,
                    "match_label": "direct",
                    "evidence_snippets": [
                        "Managed global production outages for five years."
                    ],
                }
            ],
        }

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=analysis(
                [requirement(requirement_id, requirement_text, "none")]
            ),
            after_analysis=analysis(
                [requirement(requirement_id, requirement_text, "none")]
            ),
            generation_state=generation([project]),
            claim_lineage=lineage(
                project_bullets=[
                    (
                        "project-query",
                        "QueryAI",
                        final_bullet,
                    )
                ]
            ),
        )

        self.assertEqual(
            reconciled["canonical_requirements"][0]["match_label"],
            "none",
        )
        self.assertEqual(
            report["newly_supported_requirement_count"],
            0,
        )

    def test_app94_queryai_new_evidence_removes_none_gaps(self):
        requirements = [
            (
                "req-fullstack",
                (
                    "Build frontend and full-stack application features "
                    "using React and JavaScript or TypeScript"
                ),
            ),
            (
                "req-database",
                "Experience with SQLite or PostgreSQL database design",
            ),
            (
                "req-access",
                (
                    "Experience implementing authentication workflows or "
                    "database access control"
                ),
            ),
        ]
        bullet_1 = (
            "Built full-stack help-desk workflows in a 4-person team using "
            "React and Supabase/PostgreSQL, including login, note submission, "
            "and ticket editing."
        )
        bullet_2 = (
            "Implemented backend data access through PostgREST and applied "
            "Row-Level Security policies to secure database operations."
        )
        project = {
            "project_id": "project-query",
            "title": "QueryAI",
            "display_title": "QueryAI (React, Team of 4)",
            "draft_bullets": [bullet_1, bullet_2],
            "requirement_matches": [
                {
                    "requirement_id": requirement_id,
                    "requirement_text": text,
                    "match_label": "direct",
                    "evidence_snippets": [bullet_1, bullet_2],
                }
                for requirement_id, text in requirements
            ],
        }
        skills = [
            "React",
            "JavaScript",
            "PostgreSQL",
            "authentication workflows",
            "access control",
        ]
        rankings = [
            {
                "skill": "React",
                "matched_requirement_ids": ["req-fullstack"],
            },
            {
                "skill": "JavaScript",
                "matched_requirement_ids": ["req-fullstack"],
            },
            {
                "skill": "PostgreSQL",
                "matched_requirement_ids": ["req-database"],
            },
            {
                "skill": "authentication workflows",
                "matched_requirement_ids": ["req-access"],
            },
            {
                "skill": "access control",
                "matched_requirement_ids": ["req-access"],
            },
        ]

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=analysis(
                [
                    requirement(requirement_id, text, "none")
                    for requirement_id, text in requirements
                ]
            ),
            after_analysis=analysis(
                [
                    requirement(requirement_id, text, "none")
                    for requirement_id, text in requirements
                ]
            ),
            generation_state=generation(
                [project],
                skills=skills,
                rankings=rankings,
            ),
            claim_lineage=lineage(
                project_bullets=[
                    (
                        "project-query",
                        "QueryAI (React, Team of 4)",
                        bullet_1,
                    ),
                    (
                        "project-query",
                        "QueryAI (React, Team of 4)",
                        bullet_2,
                    ),
                ],
                skills=skills,
            ),
        )

        labels = {
            row["requirement_id"]: row["match_label"]
            for row in reconciled["canonical_requirements"]
        }
        self.assertNotEqual(labels["req-fullstack"], "none")
        self.assertNotEqual(labels["req-database"], "none")
        self.assertEqual(labels["req-access"], "direct")
        self.assertEqual(
            report["newly_supported_requirement_count"],
            3,
        )


if __name__ == "__main__":
    unittest.main()
