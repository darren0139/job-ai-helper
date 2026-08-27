from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    build_stable_analysis,
    canonicalise_requirements,
    compute_deterministic_alignment,
    learn_acronym_map,
)


class StableEvidenceScoringTests(unittest.TestCase):
    def test_acronym_is_learned_from_input(self) -> None:
        aliases = learn_acronym_map(
            [
                "Continuous Integration (CI)",
                "CI pipeline maintenance",
            ]
        )
        self.assertEqual(
            aliases.get("ci"),
            "continuous integration",
        )

    def test_near_duplicate_requirements_merge(self) -> None:
        result = canonicalise_requirements(
            {
                "required_skills": [
                    "Experience with automated software testing",
                ],
                "responsibilities": [
                    "Perform automated software tests",
                ],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            }
        )
        self.assertEqual(
            len(result["requirements"]),
            1,
        )

    def test_positive_match_without_evidence_is_downgraded(self) -> None:
        stable = build_stable_analysis(
            jd_profile={
                "required_skills": ["Build data pipelines"],
                "responsibilities": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            keyword_match={
                "present": [
                    {
                        "keyword": "Build data pipelines",
                        "match_type": "direct",
                        "evidence_type": "direct",
                        "matched_resume_term": "",
                    }
                ],
                "missing": [],
            },
        )
        row = stable["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "none")
        self.assertTrue(stable["validation_warnings"])

    def test_repeated_scoring_is_identical(self) -> None:
        kwargs = {
            "jd_profile": {
                "required_skills": [
                    "Experience building REST APIs",
                ],
                "responsibilities": [
                    "Maintain backend services",
                ],
                "preferred_skills": [
                    "Docker experience",
                ],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            "keyword_match": {
                "present": [
                    {
                        "keyword": "Experience building REST APIs",
                        "match_type": "equivalent",
                        "evidence_type": "direct",
                        "found_in": "projects",
                        "matched_resume_term": "Built REST APIs with FastAPI",
                        "match_reason": "Direct implementation evidence.",
                    }
                ],
                "missing": [
                    {
                        "keyword": "Maintain backend services",
                    },
                    {
                        "keyword": "Docker experience",
                    },
                ],
            },
            "raw_jd_text": "Build REST APIs and maintain backend services. Docker preferred.",
            "raw_resume_text": "Built REST APIs with FastAPI.",
            "bullet_quality_score": 70,
            "structure_score": 90,
        }

        first = build_stable_analysis(**kwargs)
        second = build_stable_analysis(**kwargs)

        self.assertEqual(first, second)

    def test_preferred_requirement_has_lower_weight(self) -> None:
        common_match = {
            "match_type": "direct",
            "evidence_type": "direct",
            "found_in": "projects",
            "matched_resume_term": "Implemented the requirement",
            "match_reason": "Explicit evidence.",
        }

        required = build_stable_analysis(
            jd_profile={
                "required_skills": ["Requirement alpha"],
                "responsibilities": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            keyword_match={
                "present": [
                    {
                        "keyword": "Requirement alpha",
                        **common_match,
                    }
                ],
                "missing": [],
            },
        )

        preferred = build_stable_analysis(
            jd_profile={
                "required_skills": [],
                "responsibilities": [],
                "preferred_skills": ["Requirement alpha"],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            keyword_match={
                "present": [
                    {
                        "keyword": "Requirement alpha",
                        **common_match,
                    }
                ],
                "missing": [],
            },
        )

        self.assertGreaterEqual(
            required["deterministic_alignment_score"],
            preferred["deterministic_alignment_score"],
        )

    def test_soft_skills_are_included(self) -> None:
        result = canonicalise_requirements(
            {
                "required_skills": [],
                "responsibilities": [],
                "soft_skills": [
                    "Communicate clearly with cross-functional teams",
                ],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            }
        )
        texts = [row["text"] for row in result["requirements"]]
        self.assertIn(
            "Communicate clearly with cross-functional teams",
            texts,
        )

    def test_raw_jd_anchors_requirement_ids_across_profile_variation(self) -> None:
        raw_jd = """
Job Requirements
Experience with automated software testing.
Good written communication skills.
"""
        first = canonicalise_requirements(
            {
                "required_skills": [
                    "Automated testing experience",
                ],
                "responsibilities": [],
                "soft_skills": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            raw_jd,
        )
        second = canonicalise_requirements(
            {
                "required_skills": [],
                "responsibilities": [],
                "soft_skills": [
                    "Good written communication skills",
                ],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            raw_jd,
        )
        self.assertEqual(
            [row["requirement_id"] for row in first["requirements"]],
            [row["requirement_id"] for row in second["requirements"]],
        )

    def test_preferred_clause_is_split_from_required_clause(self) -> None:
        result = canonicalise_requirements(
            {
                "required_skills": [
                    "Knowledge of games, preferably being familiar with recent shooting games",
                ],
                "responsibilities": [],
                "soft_skills": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            }
        )
        importances = sorted(
            row["importance"]
            for row in result["requirements"]
        )
        self.assertEqual(importances, ["preferred", "required"])

    def test_qualified_non_qa_experience_is_rejected_by_taxonomy(self) -> None:
        stable = build_stable_analysis(
            jd_profile={
                "required_skills": [
                    "Experience in quality assurance",
                ],
                "responsibilities": [],
                "soft_skills": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            keyword_match={
                "present": [
                    {
                        "keyword": "Experience in quality assurance",
                        "match_type": "partial",
                        "evidence_type": "transferable",
                        "found_in": "experience",
                        "matched_resume_term": "Software Engineer Intern",
                        "match_reason": "Technical experience, but not quality assurance duties.",
                    }
                ],
                "missing": [],
            },
        )
        row = stable["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "none")
        self.assertTrue(
            any(
                warning["code"] == "qualified_evidence_capped"
                for warning in stable["validation_warnings"]
            )
        )


class AtomicRequirementMatchingTests(unittest.TestCase):
    def _garena_raw_jd(self) -> str:
        return """
Job Description
Operate and maintain the daily operations of the gaming product from configuration, quality assurance, live environment handling (including bugs and hacks), and operational evaluation.
Coordinate configuration & QA tasks between different offices.
Collaborate with both local and global stakeholders in resolving product-related problems.

Job Requirements
Minimum 1 year of experience in quality assurance, live operations, or related fields, preferably within tech or gaming companies.
Passionate about games with basic knowledge of the gaming industry, preferably being familiar with recent shooting games.
Good written and verbal communication skills along with the ability to effectively collaborate with cross-functional teams.
Having a track record of working with meticulous works that require high attention to detail would be preferred.
"""

    def _resume_profile(self) -> dict:
        return {
            "education": [
                {
                    "school": "DigiPen",
                    "degree": "Computer Science in Interactive Media and Game Development",
                    "graduation_date": "2026",
                    "courses": [],
                }
            ],
            "projects": [
                {
                    "title": "CyberSphere",
                    "date": "2018",
                    "bullets": [
                        "Built gameplay features for a mobile game published on Google Play."
                    ],
                }
            ],
            "experience": [
                {
                    "title": "Game Developer Intern",
                    "company": "Example",
                    "date": "2018",
                    "bullets": [
                        "Collaborated with a team of interns in a SCRUM environment."
                    ],
                }
            ],
            "skills": {},
        }

    def test_compound_responsibility_is_split_atomically(self) -> None:
        result = canonicalise_requirements(
            {},
            self._garena_raw_jd(),
        )
        texts = [row["text"].lower() for row in result["requirements"]]
        self.assertTrue(any("gaming product configuration" in text for text in texts))
        self.assertTrue(any("gaming product quality assurance" in text for text in texts))
        self.assertTrue(any("live environment handling" in text for text in texts))
        self.assertTrue(any("bugs and hacks handling" in text for text in texts))
        self.assertTrue(any("operational evaluation" in text for text in texts))

    def test_atomic_children_do_not_merge_back_into_parent(self) -> None:
        result = canonicalise_requirements({}, self._garena_raw_jd())
        first_group = [
            row
            for row in result["requirements"]
            if "daily operations of the gaming product" in row.get("parent_text", "").lower()
        ]
        self.assertGreaterEqual(len(first_group), 6)
        self.assertEqual(len({row["requirement_id"] for row in first_group}), len(first_group))

    def test_published_game_does_not_prove_daily_operations_or_qa(self) -> None:
        stable = build_stable_analysis(
            jd_profile={},
            raw_jd_text=self._garena_raw_jd(),
            raw_resume_text="Built a mobile game published on Google Play.",
            resume_profile=self._resume_profile(),
            keyword_match={
                "present": [
                    {
                        "keyword": "Gaming product",
                        "match_type": "equivalent",
                        "evidence_type": "direct",
                        "found_in": "projects",
                        "matched_resume_term": "CyberSphere published on Google Play",
                        "match_reason": "Published game project demonstrates work on a gaming product.",
                    },
                    {
                        "keyword": "Basic knowledge of the gaming industry",
                        "match_type": "equivalent",
                        "evidence_type": "direct",
                        "found_in": "education",
                        "matched_resume_term": "Computer Science in Interactive Media and Game Development",
                        "match_reason": "Game-development education supports gaming-industry knowledge.",
                    },
                ],
                "missing": [
                    {"keyword": "Configuration"},
                    {"keyword": "Quality assurance"},
                    {"keyword": "Live environment handling"},
                    {"keyword": "Bug and hack handling"},
                    {"keyword": "Operational evaluation"},
                ],
            },
        )
        rows = stable["canonical_requirements"]
        by_text = {row["text"].lower(): row for row in rows}
        self.assertTrue(
            any(
                row["match_label"] == "direct"
                for text, row in by_text.items()
                if "basic knowledge of the gaming industry" in text
            )
        )
        for phrase in (
            "gaming product configuration",
            "gaming product quality assurance",
            "live environment handling",
            "bugs and hacks handling",
            "operational evaluation",
        ):
            matching = [row for text, row in by_text.items() if phrase in text]
            self.assertTrue(matching, phrase)
            self.assertTrue(all(row["match_label"] == "none" for row in matching), phrase)

    def test_general_teamwork_is_consistently_weak_for_cross_functional(self) -> None:
        stable = build_stable_analysis(
            jd_profile={},
            raw_jd_text=self._garena_raw_jd(),
            raw_resume_text="Collaborated with a team of interns in SCRUM.",
            resume_profile=self._resume_profile(),
            keyword_match={
                "present": [],
                "missing": [
                    {"keyword": "Cross-functional teams"},
                ],
            },
        )
        row = next(
            row
            for row in stable["canonical_requirements"]
            if "cross-functional teams" in row["text"].lower()
        )
        self.assertEqual(row["match_label"], "weak")

    def test_negative_clause_only_caps_the_relevant_atomic_requirement(self) -> None:
        stable = build_stable_analysis(
            jd_profile={},
            raw_jd_text=self._garena_raw_jd(),
            raw_resume_text="Computer Science in Interactive Media and Game Development.",
            resume_profile=self._resume_profile(),
            keyword_match={
                "present": [
                    {
                        "keyword": "Passionate about games with basic knowledge of the gaming industry, preferably being familiar with recent shooting games",
                        "match_type": "equivalent",
                        "evidence_type": "direct",
                        "found_in": "education",
                        "matched_resume_term": "Computer Science in Interactive Media and Game Development",
                        "match_reason": "Game-development education supports gaming knowledge, but not stated passion or recent shooting-game familiarity.",
                    }
                ],
                "missing": [],
            },
        )
        knowledge = next(
            row
            for row in stable["canonical_requirements"]
            if "basic knowledge of the gaming industry" in row["text"].lower()
        )
        passion = next(
            row
            for row in stable["canonical_requirements"]
            if row["text"].lower() == "passionate about games"
        )
        shooting = next(
            row
            for row in stable["canonical_requirements"]
            if "recent shooting games" in row["text"].lower()
        )
        self.assertEqual(knowledge["match_label"], "direct")
        self.assertEqual(passion["match_label"], "none")
        self.assertEqual(shooting["match_label"], "none")

    def test_related_domain_evidence_does_not_prove_passion(self) -> None:
        stable = build_stable_analysis(
            jd_profile={},
            raw_jd_text=self._garena_raw_jd(),
            raw_resume_text=(
                "Computer Science in Interactive Media and Game Development. "
                "Built a mobile game published on Google Play."
            ),
            resume_profile=self._resume_profile(),
            keyword_match={
                "present": [
                    {
                        "keyword": (
                            "Passionate about games with basic knowledge of "
                            "the gaming industry"
                        ),
                        "match_type": "equivalent",
                        "evidence_type": "direct",
                        "found_in": "education",
                        "matched_resume_term": (
                            "Computer Science in Interactive Media and Game Development"
                        ),
                        "match_reason": (
                            "Game-development education and projects demonstrate "
                            "gaming-industry knowledge."
                        ),
                    }
                ],
                "missing": [],
            },
        )
        passion = next(
            row
            for row in stable["canonical_requirements"]
            if row["text"].lower() == "passionate about games"
        )
        knowledge = next(
            row
            for row in stable["canonical_requirements"]
            if "basic knowledge of the gaming industry" in row["text"].lower()
        )
        self.assertTrue(passion["explicit_only_requirement"])
        self.assertEqual(passion["match_label"], "none")
        self.assertEqual(knowledge["match_label"], "direct")
        self.assertTrue(
            any(
                warning["code"]
                == "subjective_requirement_requires_explicit_evidence"
                for warning in stable["validation_warnings"]
            )
        )

    def test_subjective_requirement_never_receives_weak_fallback(self) -> None:
        stable = build_stable_analysis(
            jd_profile={
                "required_skills": ["Strong interest in cybersecurity"],
                "responsibilities": [],
                "soft_skills": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            raw_resume_text=(
                "Bachelor of Science in Cybersecurity. Built security tools."
            ),
            resume_profile={
                "education": [
                    {
                        "school": "Example",
                        "degree": "Bachelor of Science in Cybersecurity",
                        "graduation_date": "2026",
                        "courses": [],
                    }
                ],
                "projects": [
                    {
                        "title": "Security Tool",
                        "date": "2025",
                        "bullets": ["Built security tools."],
                    }
                ],
                "experience": [],
                "skills": {},
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": "Strong interest in cybersecurity"}],
            },
        )
        row = stable["canonical_requirements"][0]
        self.assertTrue(row["explicit_only_requirement"])
        self.assertEqual(row["match_label"], "none")
        self.assertEqual(row["evidence"], [])

    def test_explicit_subjective_statement_receives_direct_credit(self) -> None:
        stable = build_stable_analysis(
            jd_profile={
                "required_skills": ["Strong interest in data engineering"],
                "responsibilities": [],
                "soft_skills": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            raw_resume_text="Strong interest in data engineering.",
            resume_profile={
                "summary": "Strong interest in data engineering.",
                "education": [],
                "projects": [],
                "experience": [],
                "skills": {},
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": "Strong interest in data engineering"}],
            },
        )
        row = stable["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["match_source"], "explicit_resume_evidence")
        self.assertTrue(row["evidence"])

    def test_explicit_subjective_statement_must_match_domain(self) -> None:
        stable = build_stable_analysis(
            jd_profile={
                "required_skills": ["Passionate about games"],
                "responsibilities": [],
                "soft_skills": [],
                "preferred_skills": [],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            raw_resume_text="Passionate about cloud computing.",
            resume_profile={
                "summary": "Passionate about cloud computing.",
                "education": [],
                "projects": [],
                "experience": [],
                "skills": {},
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": "Passionate about games"}],
            },
        )
        row = stable["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "none")

    def test_document_quality_does_not_change_role_alignment(self) -> None:
        rows = [
            {
                "importance": "required",
                "match_value": 0.55,
                "match_label": "transferable",
                "evidence_strength": 3,
                "group_weight_fraction": 1.0,
                "atomic_group_id": "group_1",
            }
        ]
        low_quality = compute_deterministic_alignment(
            rows,
            bullet_quality_score=10,
            structure_score=20,
        )
        high_quality = compute_deterministic_alignment(
            rows,
            bullet_quality_score=100,
            structure_score=100,
        )
        self.assertEqual(
            low_quality["deterministic_alignment_score"],
            high_quality["deterministic_alignment_score"],
        )
        self.assertEqual(low_quality["score_weights"]["bullet_quality"], 0.0)
        self.assertEqual(low_quality["score_weights"]["structure"], 0.0)


if __name__ == "__main__":
    unittest.main()


class JdSectionHeadingFilterTests(unittest.TestCase):
    def test_phase_2_3b_required_heading_excludes_marker_and_keeps_short_skill(
        self,
    ) -> None:
        result = canonicalise_requirements(
            {},
            """
Requirements and Skills
• C++
• Data Structures
""",
        )
        by_text = {row["text"]: row for row in result["requirements"]}

        self.assertEqual(set(by_text), {"C++", "Data Structures"})
        self.assertTrue(
            all(row["importance"] == "required" for row in by_text.values())
        )
        self.assertIn(
            "Requirements and Skills",
            {row["text"] for row in result["filtered_section_headings"]},
        )

    def test_phase_2_3b_preferred_heading_propagates_to_stable_analysis(
        self,
    ) -> None:
        raw_jd = """
Bonus Requirements and Skills
• Experience working with Android app development and Kotlin
• Familiarity with Nvidia CUDA
"""
        stable = build_stable_analysis(
            jd_profile={},
            keyword_match={"present": [], "missing": []},
            raw_jd_text=raw_jd,
            raw_resume_text="",
            resume_profile={},
        )
        rows = stable["canonical_requirements"]

        self.assertEqual(stable["requirement_count"], 2)
        self.assertEqual(stable["preferred_requirement_count"], 2)
        self.assertEqual(stable["required_core_requirement_count"], 0)
        self.assertTrue(all(row["importance"] == "preferred" for row in rows))
        self.assertNotIn(
            "Bonus Requirements and Skills",
            {row["text"] for row in rows},
        )

    def test_phase_2_3b_mixed_sections_have_no_heading_rows_or_merges(self) -> None:
        raw_jd = """
Requirements and Skills
• C++
• Data Structures

Bonus Requirements and Skills
• Android/Kotlin
• CUDA
"""
        result = canonicalise_requirements({}, raw_jd)
        rows = result["requirements"]
        by_text = {row["text"]: row for row in rows}
        heading_texts = {
            "Requirements and Skills",
            "Bonus Requirements and Skills",
        }

        self.assertEqual(len(rows), 4)
        self.assertEqual(by_text["C++"]["importance"], "required")
        self.assertEqual(by_text["Data Structures"]["importance"], "required")
        self.assertEqual(by_text["Android/Kotlin"]["importance"], "preferred")
        self.assertEqual(by_text["CUDA"]["importance"], "preferred")
        self.assertFalse(heading_texts & set(by_text))
        self.assertFalse(
            any(
                str(merge.get("kept_text") or "") in heading_texts
                or str(merge.get("merged_text") or "") in heading_texts
                for merge in result["merge_debug"]
            )
        )

    def test_phase_2_3b_heading_aliases_preserve_required_core_and_preferred_context(
        self,
    ) -> None:
        cases = {
            "Required Skills": "required",
            "Core Requirements": "core",
            "Preferred Skills": "preferred",
            "Optional Skills": "preferred",
        }
        for heading, expected_importance in cases.items():
            with self.subTest(heading=heading):
                result = canonicalise_requirements(
                    {},
                    f"{heading}:\n• Demonstrated deterministic capability",
                )
                self.assertEqual(len(result["requirements"]), 1)
                self.assertEqual(
                    result["requirements"][0]["importance"],
                    expected_importance,
                )
                self.assertEqual(
                    result["filtered_section_headings"][0]["text"],
                    f"{heading}:",
                )

    def test_phase_2_3b_real_requirement_prose_is_not_a_heading(self) -> None:
        result = canonicalise_requirements(
            {},
            """
Strong skills in systems design are required.
Experience with CUDA is preferred.
""",
        )
        by_text = {row["text"]: row for row in result["requirements"]}

        self.assertEqual(
            by_text["Strong skills in systems design are required"]["importance"],
            "required",
        )
        self.assertEqual(
            by_text["Experience with CUDA is preferred"]["importance"],
            "preferred",
        )
        self.assertEqual(result["filtered_section_headings"], [])

    def test_section_headings_are_excluded_and_preferred_items_stay_preferred(
        self,
    ) -> None:
        raw_jd = """
Job Description

Key Responsibilities:
Build reliable Python services.

Job Requirements
Hands-on experience with Python.

Preferred Qualifications
Experience with Docker.

Benefits
Medical coverage and annual leave.
"""
        result = canonicalise_requirements({}, raw_jd)
        rows = result["requirements"]
        by_text = {row["text"]: row for row in rows}

        for heading in (
            "Job Description",
            "Key Responsibilities",
            "Job Requirements",
            "Preferred Qualifications",
            "Benefits",
        ):
            self.assertNotIn(heading, by_text)

        self.assertEqual(
            by_text["Build reliable Python services"]["importance"],
            "core",
        )
        self.assertEqual(
            by_text["Hands-on experience with Python"]["importance"],
            "required",
        )
        self.assertEqual(
            by_text["Experience with Docker"]["importance"],
            "preferred",
        )
        self.assertNotIn("Medical coverage and annual leave", by_text)

        filtered = result["filtered_section_headings"]
        filtered_texts = {row["text"] for row in filtered}
        self.assertIn("Key Responsibilities:", filtered_texts)
        self.assertIn("Preferred Qualifications", filtered_texts)

    def test_numbered_case_and_punctuation_variants_are_filtered(self) -> None:
        raw_jd = """
KEY RESPONSIBILITIES:
Build internal tools.

1. Job Requirements
Experience with SQL.

Preferred Qualifications:
Experience with Docker.
"""
        result = canonicalise_requirements({}, raw_jd)
        texts = {row["text"] for row in result["requirements"]}

        self.assertNotIn("KEY RESPONSIBILITIES:", texts)
        self.assertNotIn("1. Job Requirements", texts)
        self.assertNotIn("Preferred Qualifications:", texts)
        self.assertIn("Build internal tools", texts)
        self.assertIn("Experience with SQL", texts)
        self.assertIn("Experience with Docker", texts)

    def test_real_requirement_sentence_containing_responsibilities_is_kept(
        self,
    ) -> None:
        raw_jd = """
Job Description
Responsibilities include implementing production monitoring workflows.
"""
        result = canonicalise_requirements({}, raw_jd)
        texts = {row["text"] for row in result["requirements"]}

        self.assertIn(
            "Responsibilities include implementing production monitoring workflows",
            texts,
        )
