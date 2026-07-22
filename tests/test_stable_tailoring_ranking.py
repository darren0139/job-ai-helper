from __future__ import annotations

from copy import deepcopy
import unittest

from tailoring.stable_tailoring_ranking import (
    build_bullet_evidence_priorities,
    build_candidate_evidence_profile,
    build_deterministic_skills_result,
    rank_projects_deterministically,
    select_complementary_projects,
)


def _stable_analysis() -> dict:
    return {
        "canonical_requirements": [
            {
                "requirement_id": "req_game_knowledge",
                "text": "basic knowledge of the gaming industry",
                "atomic_focus": "basic knowledge of the gaming industry",
                "importance": "required",
                "group_weight_fraction": 0.333333,
                "explicit_only_requirement": False,
            },
            {
                "requirement_id": "req_passion",
                "text": "Passionate about games",
                "atomic_focus": "Passionate about games",
                "importance": "required",
                "group_weight_fraction": 0.333333,
                "explicit_only_requirement": True,
            },
            {
                "requirement_id": "req_config",
                "text": "gaming product configuration",
                "atomic_focus": "configuration",
                "importance": "core",
                "group_weight_fraction": 0.166667,
                "explicit_only_requirement": False,
            },
            {
                "requirement_id": "req_operational_evaluation",
                "text": "gaming product operational evaluation",
                "atomic_focus": "operational evaluation",
                "importance": "core",
                "group_weight_fraction": 0.166667,
                "explicit_only_requirement": False,
            },
            {
                "requirement_id": "req_cross_functional",
                "text": "the ability to effectively collaborate with cross-functional teams",
                "atomic_focus": "collaborate with cross-functional teams",
                "importance": "required",
                "group_weight_fraction": 0.5,
                "explicit_only_requirement": False,
            },
            {
                "requirement_id": "req_detail",
                "text": "track record of meticulous work requiring high attention to detail",
                "atomic_focus": "meticulous work high attention to detail",
                "importance": "preferred",
                "group_weight_fraction": 1.0,
                "explicit_only_requirement": False,
            },
        ]
    }


def _candidates() -> list[dict]:
    return [
        {
            "title": "CyberSphere (Unity, Published)",
            "display_title": "CyberSphere (Unity, Published)",
            "currently_in_resume": True,
            "in_evidence_library": True,
            "period": "Jan 2018 - Feb 2018",
            "resume_evidence": {"bullets": ["Built a published Unity game."]},
            "evidence_library_evidence": {
                "bullets": [
                    "Scripted Unity gameplay features for a published mobile game."
                ],
                "skills": ["Game Systems"],
                "tools": ["Unity", "C#"],
                "impact": "Released on Google Play.",
            },
        },
        {
            "title": "The Great Migration (C++ Game Engine)",
            "display_title": "The Great Migration (C++ Game Engine)",
            "currently_in_resume": True,
            "in_evidence_library": True,
            "period": "Sep 2023 - Apr 2024",
            "resume_evidence": {"bullets": ["Built a C++ asset manager."]},
            "evidence_library_evidence": {
                "bullets": [
                    "Built a C++ asset manager for a custom game engine."
                ],
                "skills": ["Game Engine Development"],
                "tools": ["C++", "FMOD"],
                "impact": "Improved an 8-person game-engine workflow.",
            },
        },
        {
            "title": "QueryAI (React, Team of 4)",
            "display_title": "QueryAI (React, Team of 4)",
            "currently_in_resume": True,
            "in_evidence_library": True,
            "period": "Mar 2025 - Apr 2025",
            "resume_evidence": {
                "bullets": ["Created Row-Level Security policies."]
            },
            "evidence_library_evidence": {
                "bullets": [
                    "Implemented PostgREST data access and Row-Level Security policies to secure database operations.",
                    "Built full-stack help-desk workflows in a 4-person team.",
                ],
                "skills": ["Access Control", "Team Collaboration"],
                "tools": ["React", "Supabase", "PostgreSQL"],
                "impact": "Connected frontend workflows with secure database access.",
            },
        },
        {
            "title": "Job AI Helper (Python, Solo)",
            "display_title": "Job AI Helper (Python, Solo)",
            "currently_in_resume": False,
            "in_evidence_library": True,
            "period": "Mar 2025 - Apr 2025",
            "resume_evidence": None,
            "evidence_library_evidence": {
                "bullets": [
                    "Created a multi-step analysis pipeline with keyword matching and bullet review."
                ],
                "skills": ["Resume Analysis", "RAG"],
                "tools": ["Python", "Streamlit"],
                "impact": "Built a complete resume-analysis application.",
            },
        },
    ]


def _rows(ai_score: int = 5) -> list[dict]:
    base = {
        "must_have_match_score": ai_score,
        "responsibility_match_score": ai_score,
        "tool_domain_match_score": ai_score,
        "evidence_strength_score": ai_score,
        "impact_scope_score": ai_score,
        "final_score": ai_score * 10,
        "reason": "AI diagnostic only.",
        "matched_jd_requirements": [],
        "transferable_jd_requirements": [],
    }
    return [
        {
            **base,
            "title": "CyberSphere (Unity, Published)",
            "display_title": "CyberSphere (Unity, Published)",
            "currently_in_resume": True,
            "in_evidence_library": True,
            "requirement_matches": [
                {
                    "requirement_id": "req_game_knowledge",
                    "match_label": "direct",
                    "evidence_snippets": [
                        "Scripted Unity gameplay features for a published mobile game."
                    ],
                }
            ],
        },
        {
            **base,
            "title": "The Great Migration (C++ Game Engine)",
            "display_title": "The Great Migration (C++ Game Engine)",
            "currently_in_resume": True,
            "in_evidence_library": True,
            "requirement_matches": [
                {
                    "requirement_id": "req_game_knowledge",
                    "match_label": "direct",
                    "evidence_snippets": [
                        "Built a C++ asset manager for a custom game engine."
                    ],
                }
            ],
        },
        {
            **base,
            "title": "QueryAI (React, Team of 4)",
            "display_title": "QueryAI (React, Team of 4)",
            "currently_in_resume": True,
            "in_evidence_library": True,
            "requirement_matches": [
                {
                    "requirement_id": "req_config",
                    "match_label": "transferable",
                    "evidence_snippets": [
                        "Implemented PostgREST data access and Row-Level Security policies to secure database operations."
                    ],
                },
                {
                    "requirement_id": "req_cross_functional",
                    "match_label": "weak",
                    "evidence_snippets": [
                        "Built full-stack help-desk workflows in a 4-person team."
                    ],
                },
            ],
        },
        {
            **base,
            "title": "Job AI Helper (Python, Solo)",
            "display_title": "Job AI Helper (Python, Solo)",
            "currently_in_resume": False,
            "in_evidence_library": True,
            "requirement_matches": [
                {
                    "requirement_id": "req_operational_evaluation",
                    "match_label": "transferable",
                    "evidence_snippets": [
                        "Created a multi-step analysis pipeline with keyword matching and bullet review."
                    ],
                },
                {
                    "requirement_id": "req_detail",
                    "match_label": "transferable",
                    "evidence_snippets": [
                        "Created a multi-step analysis pipeline with keyword matching and bullet review."
                    ],
                },
            ],
        },
    ]


class StableTailoringRankingTests(unittest.TestCase):
    def test_candidate_ids_and_fingerprint_are_stable(self) -> None:
        first = build_candidate_evidence_profile(_candidates())
        second = build_candidate_evidence_profile(list(reversed(_candidates())))
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(
            [row["project_id"] for row in first["projects"]],
            [row["project_id"] for row in second["projects"]],
        )

    def test_ai_numeric_scores_do_not_control_phase6b_score(self) -> None:
        low_rows = _rows(ai_score=0)
        high_rows = _rows(ai_score=5)
        low, _ = rank_projects_deterministically(
            ranked_rows=low_rows,
            project_candidates=_candidates(),
            stable_analysis=_stable_analysis(),
        )
        high, _ = rank_projects_deterministically(
            ranked_rows=high_rows,
            project_candidates=_candidates(),
            stable_analysis=_stable_analysis(),
        )
        self.assertEqual(
            {row["project_id"]: row["final_score"] for row in low},
            {row["project_id"]: row["final_score"] for row in high},
        )

    def test_subjective_requirement_requires_explicit_evidence(self) -> None:
        rows = _rows()
        rows[0]["requirement_matches"].append(
            {
                "requirement_id": "req_passion",
                "match_label": "direct",
                "evidence_snippets": [
                    "Scripted Unity gameplay features for a published mobile game."
                ],
            }
        )
        ranked, _ = rank_projects_deterministically(
            ranked_rows=rows,
            project_candidates=_candidates(),
            stable_analysis=_stable_analysis(),
        )
        cyber = next(row for row in ranked if row["title"].startswith("CyberSphere"))
        self.assertNotIn(
            "req_passion",
            {match["requirement_id"] for match in cyber["requirement_matches"]},
        )

    def test_queryai_beats_job_ai_helper_for_complementary_third_slot(self) -> None:
        ranked, _ = rank_projects_deterministically(
            ranked_rows=_rows(),
            project_candidates=_candidates(),
            stable_analysis=_stable_analysis(),
        )
        ordered, _ = select_complementary_projects(
            ranked_rows=ranked,
            selected_count=3,
        )
        selected_titles = [row["title"] for row in ordered[:3]]
        self.assertIn("QueryAI (React, Team of 4)", selected_titles)
        self.assertNotIn("Job AI Helper (Python, Solo)", selected_titles)

    def test_complementary_selection_is_repeatable(self) -> None:
        ranked, _ = rank_projects_deterministically(
            ranked_rows=_rows(),
            project_candidates=_candidates(),
            stable_analysis=_stable_analysis(),
        )
        first, _ = select_complementary_projects(
            ranked_rows=ranked,
            selected_count=3,
        )
        second, _ = select_complementary_projects(
            ranked_rows=deepcopy(ranked),
            selected_count=3,
        )
        self.assertEqual(
            [row["project_id"] for row in first[:3]],
            [row["project_id"] for row in second[:3]],
        )

    def test_skills_ignore_ai_priority_numbers_and_unsupported_additions(self) -> None:
        raw_one = {
            "skill_lines": [
                {"category": "Tools", "items": ["Quality Assurance", "Git"]},
                {"category": "Game & Engine", "items": ["Unity", "C#"]},
            ],
            "skill_priorities": [
                {"skill": "Quality Assurance", "jd_relevance": 5, "evidence_strength": 5},
                {"skill": "Git", "jd_relevance": 0, "evidence_strength": 0},
            ],
            "notes": [],
        }
        raw_two = {
            "skill_lines": list(reversed(raw_one["skill_lines"])),
            "skill_priorities": list(reversed(raw_one["skill_priorities"])),
            "notes": [],
        }
        resume_profile = {
            "skills": {
                "languages": ["C#", "Python"],
                "tools": ["Git"],
                "platforms": ["Unity"],
            }
        }
        evidence_items = [
            {
                "title": "CyberSphere (Unity, Published)",
                "skills": ["Game Systems"],
                "tools": ["Unity", "C#", "Git"],
            }
        ]
        selected = {
            "recommended_projects": [
                {"title": "CyberSphere (Unity, Published)"}
            ]
        }
        first = build_deterministic_skills_result(
            raw_result=raw_one,
            resume_profile=resume_profile,
            evidence_items=evidence_items,
            stable_analysis=_stable_analysis(),
            selected_projects_result=selected,
            max_items=10,
        )
        second = build_deterministic_skills_result(
            raw_result=raw_two,
            resume_profile=resume_profile,
            evidence_items=evidence_items,
            stable_analysis=_stable_analysis(),
            selected_projects_result=selected,
            max_items=10,
        )
        self.assertEqual(first["skill_lines"], second["skill_lines"])
        all_items = {
            item
            for line in first["skill_lines"]
            for item in line["items"]
        }
        self.assertNotIn("Quality Assurance", all_items)
        self.assertIn("Unity", all_items)
        self.assertEqual(
            first["skill_selection_owner"],
            "python_canonical_supported_evidence_pool",
        )

    def test_recognised_requirement_mappings_ignore_ai_variation(self) -> None:
        variants = []
        base = _rows()

        first = deepcopy(base)
        first[1]["requirement_matches"][0]["match_label"] = "transferable"
        first[2]["requirement_matches"][0]["match_label"] = "transferable"
        first[3]["requirement_matches"] = []
        variants.append(first)

        second = deepcopy(base)
        second[1]["requirement_matches"].append(
            {
                "requirement_id": "req_detail",
                "match_label": "weak",
                "evidence_snippets": ["Built a C++ asset manager."],
            }
        )
        second[3]["requirement_matches"] = [
            {
                "requirement_id": "req_operational_evaluation",
                "match_label": "transferable",
                "evidence_snippets": [
                    "Created a multi-step analysis pipeline with keyword matching and bullet review."
                ],
            },
            {
                "requirement_id": "req_detail",
                "match_label": "transferable",
                "evidence_snippets": [
                    "Created a multi-step analysis pipeline with keyword matching and bullet review."
                ],
            },
        ]
        variants.append(second)

        third = deepcopy(base)
        third[1]["requirement_matches"][0]["match_label"] = "weak"
        third[2]["requirement_matches"].append(
            {
                "requirement_id": "req_detail",
                "match_label": "weak",
                "evidence_snippets": [
                    "Implemented Row-Level Security policies."
                ],
            }
        )
        variants.append(third)

        outputs = []
        for rows in variants:
            ranked, _ = rank_projects_deterministically(
                ranked_rows=rows,
                project_candidates=_candidates(),
                stable_analysis=_stable_analysis(),
            )
            ordered, _ = select_complementary_projects(
                ranked_rows=ranked,
                selected_count=3,
            )
            outputs.append(
                {
                    "scores": {row["project_id"]: row["final_score"] for row in ranked},
                    "labels": {
                        row["project_id"]: {
                            match["requirement_id"]: match["match_label"]
                            for match in row["requirement_matches"]
                        }
                        for row in ranked
                    },
                    "selected": [row["project_id"] for row in ordered[:3]],
                }
            )

        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])

    def test_job_ai_audits_do_not_become_game_qa_or_operational_evaluation(self) -> None:
        rows = _rows()
        rows[3]["requirement_matches"].extend(
            [
                {
                    "requirement_id": "req_operational_evaluation",
                    "match_label": "transferable",
                    "evidence_snippets": [
                        "Created a multi-step analysis pipeline with keyword matching and bullet review."
                    ],
                },
            ]
        )
        stable = _stable_analysis()
        stable["canonical_requirements"].append(
            {
                "requirement_id": "req_game_qa",
                "text": "gaming product quality assurance",
                "atomic_focus": "gaming product quality assurance",
                "importance": "core",
                "group_weight_fraction": 0.166667,
                "explicit_only_requirement": False,
            }
        )
        rows[3]["requirement_matches"].append(
            {
                "requirement_id": "req_game_qa",
                "match_label": "transferable",
                "evidence_snippets": [
                    "Created a multi-step analysis pipeline with keyword matching and bullet review."
                ],
            }
        )

        ranked, _ = rank_projects_deterministically(
            ranked_rows=rows,
            project_candidates=_candidates(),
            stable_analysis=stable,
        )
        job_ai = next(row for row in ranked if row["title"].startswith("Job AI Helper"))
        labels = {
            match["requirement_id"]: match["match_label"]
            for match in job_ai["requirement_matches"]
        }
        self.assertNotIn("req_game_qa", labels)
        self.assertNotIn("req_operational_evaluation", labels)
        self.assertEqual(labels.get("req_detail"), "weak")

    def test_queryai_configuration_is_weak_and_stable(self) -> None:
        ranked, _ = rank_projects_deterministically(
            ranked_rows=_rows(),
            project_candidates=_candidates(),
            stable_analysis=_stable_analysis(),
        )
        query = next(row for row in ranked if row["title"].startswith("QueryAI"))
        labels = {
            match["requirement_id"]: match["match_label"]
            for match in query["requirement_matches"]
        }
        self.assertEqual(labels.get("req_config"), "weak")
        self.assertEqual(labels.get("req_cross_functional"), "weak")
        self.assertEqual(labels.get("req_detail"), "weak")

    def test_bullet_evidence_priority_protects_queryai_security_bullet(self) -> None:
        ranked, _ = rank_projects_deterministically(
            ranked_rows=_rows(),
            project_candidates=_candidates(),
            stable_analysis=_stable_analysis(),
        )
        query = next(row for row in ranked if row["title"].startswith("QueryAI"))
        priorities = build_bullet_evidence_priorities(
            bullets=[
                "Built full-stack help-desk workflows in a 4-person team using React and Supabase/PostgreSQL.",
                "Implemented PostgREST data access and Row-Level Security policies to secure database operations.",
            ],
            ranking_row=query,
        )
        self.assertEqual(priorities[1]["evidence_priority"], 1)
        self.assertIn("req_config", priorities[1]["protected_requirement_ids"])
        self.assertTrue(priorities[1]["protect_during_fitting"])

    def test_skill_display_is_not_controlled_by_ai_spelling_or_category(self) -> None:
        resume_profile = {
            "skills": {
                "languages": ["C#"],
                "tools": ["GitHub"],
                "platforms": ["Unity"],
            }
        }
        evidence_items = [
            {
                "title": "CyberSphere (Unity, Published)",
                "skills": ["Game Systems"],
                "tools": ["Unity", "C#", "GitHub"],
            }
        ]
        selected = {
            "recommended_projects": [
                {"title": "CyberSphere (Unity, Published)"}
            ]
        }
        first = build_deterministic_skills_result(
            raw_result={
                "skill_lines": [
                    {"category": "Random", "items": ["UNITY", "github"]}
                ]
            },
            resume_profile=resume_profile,
            evidence_items=evidence_items,
            stable_analysis=_stable_analysis(),
            selected_projects_result=selected,
            max_items=10,
        )
        second = build_deterministic_skills_result(
            raw_result={
                "skill_lines": [
                    {"category": "Other", "items": ["Unity Engine", "GitHub"]}
                ]
            },
            resume_profile=resume_profile,
            evidence_items=evidence_items,
            stable_analysis=_stable_analysis(),
            selected_projects_result=selected,
            max_items=10,
        )
        self.assertEqual(first["skill_lines"], second["skill_lines"])


if __name__ == "__main__":
    unittest.main()
