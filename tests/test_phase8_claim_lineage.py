from __future__ import annotations

import unittest

from tailoring.phase8_claim_lineage import audit_claim_lineage_v2


BASELINE = {
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
        },
        {
            "title": "The Great Migration",
            "bullets": [
                (
                    "Built an asset manager to centralise and optimise "
                    "the asset pipeline for efficiency."
                ),
                (
                    "Integrated FMOD into the engine and utilised it for "
                    "the game logic of audio proximity."
                ),
            ],
        },
        {
            "title": "CyberSphere",
            "bullets": [
                (
                    "Scripting power-ups, environmental hazards, and a "
                    "high-score tracking table system."
                ),
                (
                    "Worked on creating user-friendly UI features like "
                    "sliders and level-locking UI."
                ),
            ],
        },
    ],
    "experience": [
        {
            "title": "Software Engineer Intern",
            "company": "Example",
            "bullets": [
                "Collaborated on backend API integration.",
            ],
        }
    ],
    "skills": {
        "languages": ["TypeScript", "Python"],
        "frameworks": ["React"],
        "platforms": ["Supabase", "PostgreSQL"],
        "concepts": ["Row-Level Security (RLS)"],
    },
}


QUERY_BULLET = (
    "Built full-stack help-desk workflows in a 4-person team using React "
    "and Supabase/PostgreSQL, including login, note submission, and "
    "ticket editing."
)


GENERATION = {
    "generation_id": "generation-a",
    "projects": {
        "recommended_projects": [
            {
                "project_id": "project_queryai",
                "title": "QueryAI",
                "display_title": "QueryAI (React, Team of 4)",
                "draft_bullets": [QUERY_BULLET],
                "allocated_blueprint_bullets": [QUERY_BULLET],
                "allocated_bullet_ids": ["bullet_queryai_1"],
            },
            {
                "project_id": "project_engine",
                "title": "The Great Migration",
                "display_title": (
                    "The Great Migration "
                    "(C++ Custom Engine, Team of 8)"
                ),
                "draft_bullets": [
                    (
                        "Built a C++ asset manager for a custom game engine, "
                        "centralising asset loading and improving pipeline "
                        "consistency."
                    )
                ],
                "allocated_blueprint_bullets": [
                    (
                        "Built a C++ asset manager for a custom game engine, "
                        "centralising asset loading and improving pipeline "
                        "consistency."
                    )
                ],
                "allocated_bullet_ids": ["bullet_engine_1"],
            },
        ],
    },
    "skills": {
        "skill_lines": [
            {
                "category": "Game & Engine",
                "items": [
                    "Custom Game Engine",
                    "game engine development",
                ],
            },
            {
                "category": "Backend & Database",
                "items": [
                    "access control",
                    "authentication workflows",
                    "backend integration",
                    "database design",
                ],
            },
            {
                "category": "Programming",
                "items": [
                    "TypeScript",
                    "JavaScript",
                ],
            },
        ],
        "evidence_supported_additions": [
            {
                "skill": "Custom Game Engine",
                "evidence_titles": [
                    "The Great Migration "
                    "(C++ Custom Engine, Team of 8)"
                ],
                "reason": (
                    "Supported by the custom-engine asset manager and "
                    "FMOD integration."
                ),
            }
        ],
        "skill_rankings": [
            {
                "skill": "game engine development",
                "skill_key": "game engine development",
                "category": "Game & Engine",
                "evidence_strength": 3,
                "selected_project_support": True,
                "selected_project_support_methods": [
                    "exact_display_title"
                ],
                "resume_support": False,
                "evidence_titles": [
                    "The Great Migration "
                    "(C++ Custom Engine, Team of 8)"
                ],
                "ranking_version": "phase6b1-skill-ranking-v2",
            },
            {
                "skill": "access control",
                "skill_key": "access control",
                "category": "Backend & Database",
                "evidence_strength": 3,
                "selected_project_support": True,
                "selected_project_support_methods": [
                    "exact_display_title"
                ],
                "resume_support": False,
                "evidence_titles": [
                    "QueryAI (React, Team of 4)"
                ],
                "ranking_version": "phase6b1-skill-ranking-v2",
            },
            {
                "skill": "authentication workflows",
                "skill_key": "authentication workflows",
                "category": "Backend & Database",
                "evidence_strength": 3,
                "selected_project_support": True,
                "selected_project_support_methods": [
                    "exact_display_title"
                ],
                "resume_support": False,
                "evidence_titles": [
                    "QueryAI (React, Team of 4)"
                ],
                "ranking_version": "phase6b1-skill-ranking-v2",
            },
            {
                "skill": "backend integration",
                "skill_key": "backend integration",
                "category": "Backend & Database",
                "evidence_strength": 3,
                "selected_project_support": True,
                "selected_project_support_methods": [
                    "exact_display_title"
                ],
                "resume_support": False,
                "evidence_titles": [
                    "QueryAI (React, Team of 4)"
                ],
                "ranking_version": "phase6b1-skill-ranking-v2",
            },
            {
                "skill": "database design",
                "skill_key": "database design",
                "category": "Backend & Database",
                "evidence_strength": 3,
                "selected_project_support": True,
                "selected_project_support_methods": [
                    "exact_display_title"
                ],
                "resume_support": False,
                "evidence_titles": [
                    "QueryAI (React, Team of 4)"
                ],
                "ranking_version": "phase6b1-skill-ranking-v2",
            },
            {
                "skill": "JavaScript",
                "skill_key": "javascript",
                "category": "Programming",
                "evidence_strength": 3,
                "selected_project_support": True,
                "selected_project_support_methods": [
                    "exact_display_title"
                ],
                "resume_support": False,
                "evidence_titles": [
                    "QueryAI (React, Team of 4)"
                ],
                "ranking_version": "phase6b1-skill-ranking-v2",
            },
        ],
    },
    "fit_result": {
        "tailored_projects_used": {
            "recommended_projects": [
                {
                    "project_id": "project_queryai",
                    "title": "QueryAI",
                    "display_title": "QueryAI (React, Team of 4)",
                    "draft_bullets": [QUERY_BULLET],
                    "allocated_blueprint_bullets": [QUERY_BULLET],
                    "allocated_bullet_ids": ["bullet_queryai_1"],
                },
                {
                    "project_id": "project_engine",
                    "title": "The Great Migration",
                    "display_title": (
                        "The Great Migration "
                        "(C++ Custom Engine, Team of 8)"
                    ),
                    "draft_bullets": [
                        (
                            "Built a C++ asset manager for a custom game "
                            "engine, centralising asset loading and improving "
                            "pipeline consistency."
                        )
                    ],
                    "allocated_blueprint_bullets": [
                        (
                            "Built a C++ asset manager for a custom game "
                            "engine, centralising asset loading and improving "
                            "pipeline consistency."
                        )
                    ],
                    "allocated_bullet_ids": ["bullet_engine_1"],
                },
            ]
        },
        "tailored_skills_used": {
            "skill_lines": [
                {
                    "category": "Game & Engine",
                    "items": [
                        "Custom Game Engine",
                        "game engine development",
                    ],
                },
                {
                    "category": "Backend & Database",
                    "items": [
                        "access control",
                        "authentication workflows",
                        "backend integration",
                        "database design",
                    ],
                },
                {
                    "category": "Programming",
                    "items": [
                        "TypeScript",
                        "JavaScript",
                    ],
                },
            ],
            "evidence_supported_additions": [
                {
                    "skill": "Custom Game Engine",
                    "evidence_titles": [
                        "The Great Migration "
                        "(C++ Custom Engine, Team of 8)"
                    ],
                    "reason": "Supported by custom-engine evidence.",
                }
            ],
            "skill_rankings": [],
        },
    },
    "debug_inputs": {
        "candidate_pool": [
            {
                "project_id": "project_queryai",
                "title": "QueryAI (React, Team of 4)",
                "evidence_records": [
                    {
                        "evidence_id": "ev_query",
                        "kind": "bullet",
                        "text": QUERY_BULLET,
                    },
                    {
                        "evidence_id": "ev_access",
                        "kind": "skill",
                        "text": "access control",
                    },
                    {
                        "evidence_id": "ev_auth",
                        "kind": "skill",
                        "text": "authentication workflows",
                    },
                    {
                        "evidence_id": "ev_backend",
                        "kind": "skill",
                        "text": "backend integration",
                    },
                    {
                        "evidence_id": "ev_database",
                        "kind": "skill",
                        "text": "database design",
                    },
                ],
            },
        ]
    },
}


class Phase8ClaimLineageTests(unittest.TestCase):
    def test_stable_allocation_verifies_final_bullets(self):
        result = audit_claim_lineage_v2(BASELINE, GENERATION)
        self.assertEqual(
            result["verified_project_bullet_count"],
            2,
        )
        self.assertEqual(
            result["project_bullet_review_risks"],
            [],
        )
        self.assertTrue(
            all(
                row["support_method"]
                == "deterministic_bullet_allocation"
                for row in result["verified_project_bullets"]
            )
        )

    def test_parenthetical_title_matches_base_resume_title(self):
        generation = {
            **GENERATION,
            "fit_result": {
                **GENERATION["fit_result"],
                "tailored_projects_used": {
                    "recommended_projects": [
                        {
                            "title": "QueryAI",
                            "display_title": (
                                "QueryAI (React, Team of 4)"
                            ),
                            "draft_bullets": [
                                (
                                    "Set up the React and Supabase project "
                                    "environment and connected the frontend "
                                    "to the PostgreSQL-backed service."
                                )
                            ],
                        }
                    ]
                },
            },
        }
        result = audit_claim_lineage_v2(BASELINE, generation)
        self.assertEqual(
            result["project_bullet_review_risks"],
            [],
        )
        methods = result["verified_project_bullets"][0][
            "identity_methods"
        ]
        self.assertIn("baseline_base_title", methods)

    def test_unsupported_project_claim_remains_a_risk(self):
        generation = {
            **GENERATION,
            "fit_result": {
                **GENERATION["fit_result"],
                "tailored_projects_used": {
                    "recommended_projects": [
                        {
                            "title": "QueryAI",
                            "display_title": (
                                "QueryAI (React, Team of 4)"
                            ),
                            "draft_bullets": [
                                (
                                    "Managed global production outages for "
                                    "five years."
                                )
                            ],
                        }
                    ]
                },
            },
        }
        result = audit_claim_lineage_v2(BASELINE, generation)
        self.assertEqual(
            len(result["project_bullet_review_risks"]),
            1,
        )

    def test_supported_addition_and_rankings_verify_derived_skills(self):
        generation = {
            **GENERATION,
            "fit_result": {
                **GENERATION["fit_result"],
                "tailored_skills_used": GENERATION["skills"],
            },
        }
        result = audit_claim_lineage_v2(BASELINE, generation)
        risk_names = {
            row["skill"]
            for row in result["skill_review_risks"]
        }
        self.assertNotIn("Custom Game Engine", risk_names)
        self.assertNotIn("game engine development", risk_names)
        self.assertNotIn("access control", risk_names)
        self.assertNotIn("authentication workflows", risk_names)
        self.assertNotIn("backend integration", risk_names)
        self.assertNotIn("database design", risk_names)

    def test_programming_language_requires_explicit_evidence(self):
        generation = {
            **GENERATION,
            "fit_result": {
                **GENERATION["fit_result"],
                "tailored_skills_used": GENERATION["skills"],
            },
        }
        result = audit_claim_lineage_v2(BASELINE, generation)
        risk_names = {
            row["skill"]
            for row in result["skill_review_risks"]
        }
        self.assertNotIn("TypeScript", risk_names)
        self.assertIn("JavaScript", risk_names)

    def test_candidate_evidence_can_be_nested(self):
        result = audit_claim_lineage_v2(BASELINE, GENERATION)
        verified_names = {
            row["skill"]
            for row in result["verified_skills"]
        }
        self.assertIn("access control", verified_names)
        self.assertIn("database design", verified_names)

    def test_result_exposes_lineage_version_and_support_counts(self):
        result = audit_claim_lineage_v2(BASELINE, GENERATION)
        self.assertEqual(
            result["lineage_version"],
            "phase8-claim-lineage-v2",
        )
        self.assertTrue(result["support_method_counts"])


if __name__ == "__main__":
    unittest.main()
