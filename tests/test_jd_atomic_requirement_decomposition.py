from __future__ import annotations

from copy import deepcopy
import unittest
from pathlib import Path

from analysis_stability.stable_evidence_scoring import (
    CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION,
    MATCH_VALUES,
    SCORING_VERSION,
    _weighted_coverage,
    build_stable_analysis,
    canonicalise_requirements,
    compute_deterministic_alignment,
)


FIXTURE_ROOT = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "jd_atomic_decomposition"
)


def _canonical(raw: str, profile: dict | None = None) -> dict:
    return canonicalise_requirements(profile or {}, raw)


class JDAtomicRequirementDecompositionTests(unittest.TestCase):
    def test_development_fixture_003_repairs_punctuation_adjacent_technical_tokens(self):
        raw = (FIXTURE_ROOT / "003_dConstruct_Software_Engineer_jdv_4537aa97.txt").read_text(
            encoding="utf-8"
        )
        result = _canonical(raw)
        texts = [row["text"] for row in result["requirements"]]

        self.assertEqual(len(texts), 21)
        self.assertIn("Good foundation in modern C/C++ programming", texts)
        self.assertIn("Experience working with OpenGL and/or Vulkan", texts)
        self.assertEqual(
            result["canonical_requirement_decomposition_version"],
            CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION,
        )

    def test_development_visible_fixture_pack_is_deterministic(self):
        fixture_paths = sorted(
            path
            for path in FIXTURE_ROOT.glob("*.txt")
            if path.name != "README.txt"
        )
        self.assertEqual(len(fixture_paths), 5)
        for path in fixture_paths:
            with self.subTest(fixture=path.name):
                raw = path.read_text(encoding="utf-8")
                first = _canonical(raw)
                second = _canonical(raw)
                self.assertEqual(first["requirements"], second["requirements"])
                self.assertTrue(first["requirements"])
                self.assertFalse(
                    {
                        row["text"]
                        for row in first["requirements"]
                    }
                    & {
                        row["text"]
                        for row in first["filtered_section_headings"]
                    }
                )

    def test_unheaded_explicit_role_requirement_is_admitted_from_raw_with_later_headings(self):
        raw = (
            "About our company\n"
            "We are a robotics company working alongside industry experts.\n"
            "You will build backend APIs and write automated tests.\n"
            "Requirements\n"
            "C++\n"
        )
        result = _canonical(raw)
        rows = [
            row
            for row in result["requirements"]
            if row["text"] in {"build backend APIs", "write automated tests"}
        ]

        self.assertEqual(
            [row["text"] for row in rows],
            ["build backend APIs", "write automated tests"],
        )
        for row in rows:
            provenance = row["source_provenance"]
            self.assertEqual(len(provenance), 1)
            self.assertEqual(
                provenance[0]["grounding"]["kind"],
                "unheaded_explicit_role_obligation",
            )
            self.assertEqual(
                provenance[0]["source"],
                "raw_jd.unheaded_explicit_role_obligation",
            )
            self.assertTrue(provenance[0]["contributes_scoring_allocation"])

    def test_fixture_003_recovers_raw_unheaded_role_responsibilities_and_excludes_context(self):
        raw = (FIXTURE_ROOT / "003_dConstruct_Software_Engineer_jdv_4537aa97.txt").read_text(
            encoding="utf-8"
        )
        result = _canonical(raw)
        rows = [
            row
            for row in result["requirements"]
            if row["sources"] == ["raw_jd.unheaded_explicit_role_obligation"]
        ]

        self.assertEqual(
            [row["text"] for row in rows],
            [
                "performing software integration for specific use cases",
                (
                    "coding, calling into our software stack and creating applications "
                    "which utilise our software stack to meet the needs of clients"
                ),
                (
                    "working with clients to understand their needs and in turn, "
                    "implement their requirements accordingly"
                ),
                "familiarised with the entire robotics development and software workflow",
            ],
        )
        self.assertEqual(len({row["atomic_group_id"] for row in rows}), 1)
        for expected_sentence_index, row in enumerate(rows, start=1):
            if expected_sentence_index == 4:
                expected_sentence_index = 5
            provenance = row["source_provenance"]
            self.assertEqual(len(provenance), 1)
            source = provenance[0]
            self.assertEqual(row["importance"], "core")
            self.assertEqual(row["group_weight_fraction"], 0.25)
            self.assertEqual(source["source"], "raw_jd.unheaded_explicit_role_obligation")
            self.assertEqual(source["source_group_fraction"], 0.25)
            self.assertTrue(source["contributes_scoring_allocation"])
            self.assertEqual(source["parent_text"], raw.splitlines()[0])
            self.assertEqual(
                source["grounding"]["kind"],
                "unheaded_explicit_role_obligation",
            )
            self.assertEqual(source["grounding"]["line_index"], 1)
            self.assertEqual(
                source["grounding"]["sentence_index"],
                expected_sentence_index,
            )
            self.assertTrue(source["grounding"]["sentence_text"])

        self.assertNotIn(
            "working alongside industry experts",
            [row["text"] for row in result["requirements"]],
        )
        self.assertEqual(
            result["decomposition_debug"]["unheaded_raw_exclusions"],
            [
                {
                    "text": "You will be working alongside industry experts",
                    "span_id": "jdspan_efd1502032e2",
                    "line_index": 1,
                    "sentence_index": 4,
                    "reason": "contextual_company_or_team_prose",
                }
            ],
        )

    def test_fixture_003_unheaded_parent_group_conserves_core_weight(self):
        raw = (FIXTURE_ROOT / "003_dConstruct_Software_Engineer_jdv_4537aa97.txt").read_text(
            encoding="utf-8"
        )
        result = _canonical(raw)
        rows = [
            deepcopy(row)
            for row in result["requirements"]
            if row["sources"] == ["raw_jd.unheaded_explicit_role_obligation"]
        ]
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({row["atomic_group_id"] for row in rows}), 1)

        for row in rows:
            row["match_label"] = "direct"
            row["match_value"] = MATCH_VALUES["direct"]
            row["evidence_strength"] = 4

        score, numerator, denominator = _weighted_coverage(rows, {"core"})
        self.assertEqual((score, numerator, denominator), (100.0, 3.0, 3.0))

        unsplit_parent = deepcopy(rows[0])
        unsplit_parent["atomic_group_id"] = "grp_unsplit_parent_control"
        unsplit_score, unsplit_numerator, unsplit_denominator = _weighted_coverage(
            [unsplit_parent],
            {"core"},
        )
        self.assertEqual(
            (unsplit_score, unsplit_numerator, unsplit_denominator),
            (100.0, 3.0, 3.0),
        )

        alignment = compute_deterministic_alignment(rows)
        self.assertEqual(alignment["required_core_coverage_score"], 100)
        self.assertEqual(alignment["requirement_group_count"], 1)

    def test_unheaded_employer_marketing_with_verbs_is_excluded(self):
        result = _canonical(
            "We build innovative software and develop solutions for global customers.\n"
            "Requirements\n"
            "Python\n"
        )

        self.assertEqual([row["text"] for row in result["requirements"]], ["Python"])
        self.assertEqual(
            result["decomposition_debug"]["unheaded_raw_exclusions"][0]["reason"],
            "ambiguous_unheaded_prose",
        )

    def test_foundation_subject_lists_remain_one_coherent_competency(self):
        for adjective in ("Good", "Strong"):
            with self.subTest(adjective=adjective):
                value = f"{adjective} foundation in linear algebra, calculus and geometry"
                rows = _canonical(f"Requirements\n{value}\n")["requirements"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["text"], value)
                self.assertEqual(rows[0]["group_weight_fraction"], 1.0)

        # The structural foundation guard must not disable established shared
        # head decomposition for separately addressable skills.
        rows = _canonical(
            "Requirements\nExperience using Git, relational databases, and REST APIs\n"
        )["requirements"]
        self.assertEqual(len(rows), 3)

    def test_split_children_inherit_section_importance_without_explicit_optionality(self):
        parent = "Familiarity with Git, relational databases, and REST APIs"
        rows = _canonical(f"Requirements\n{parent}\n")["requirements"]

        # "Familiarity" describes proficiency depth; it does not make an item
        # optional when the enclosing section explicitly says Requirements.
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["importance"] for row in rows}, {"required"})
        for row in rows:
            source = row["source_provenance"][0]
            self.assertEqual(source["parent_text"], parent)
            self.assertEqual(row["importance"], "required")

        profile_only_rows = _canonical(
            "",
            {"preferred_skills": [parent]},
        )["requirements"]
        self.assertEqual(len(profile_only_rows), 3)
        self.assertEqual(
            {row["importance"] for row in profile_only_rows},
            {"preferred"},
        )

        explicit_preferred = _canonical(
            "Requirements\n"
            "Familiarity with Kubernetes is preferred.\n"
        )["requirements"]
        self.assertEqual(
            [(row["text"], row["importance"]) for row in explicit_preferred],
            [("Familiarity with Kubernetes is preferred", "preferred")],
        )

        # Explicit source-language transitions still override section defaults.
        transitioned = _canonical(
            "Requirements\n"
            "Experience with Python, preferably production cloud operations\n"
        )["requirements"]
        self.assertEqual(
            [(row["text"], row["importance"]) for row in transitioned],
            [
                ("Experience with Python", "required"),
                ("production cloud operations", "preferred"),
            ],
        )

    def test_example_introducers_preserve_one_coherent_requirement(self):
        coherent_examples = (
            "Proficiency in modern web technologies including FrameworkA, LanguageB and StylingSystemC",
            "Demonstrated expertise in browser performance optimisation, such as memory management, MetricA and MetricB",
            "Familiarity with low-level technologies, including ToolA, ToolB and ToolC",
            "Experience with modern technologies, for example FrameworkA, LanguageB and StylingSystemC",
            "Experience with modern technologies, e.g. FrameworkA, LanguageB and StylingSystemC",
            "Experience with modern technologies, E.g. FrameworkA, LanguageB and StylingSystemC",
            "Experience with modern technologies, especially FrameworkA, LanguageB and StylingSystemC",
            "Experience with modern technologies, including but not limited to FrameworkA, LanguageB and StylingSystemC",
        )
        for value in coherent_examples:
            with self.subTest(value=value):
                rows = _canonical(f"Requirements\n{value}\n")["requirements"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["text"], value)
                self.assertEqual(rows[0]["group_weight_fraction"], 1.0)

        # A normal shared-head skill list remains independently addressable.
        split_rows = _canonical(
            "Requirements\nExperience using Git, relational databases, and REST APIs\n"
        )["requirements"]
        self.assertEqual(len(split_rows), 3)

    def test_recruitment_context_is_excluded_but_explicit_role_obligations_remain(self):
        call_to_actions = (
            "We'd love to hear from you!",
            "Apply now to join our team.",
            "Excited about building great products? We'd love to meet you.",
            "Join our dynamic engineering team.",
            "We are seeking motivated engineers to join our growing company.",
        )
        for context in call_to_actions:
            with self.subTest(context=context):
                result = _canonical(f"{context}\nRequirements\nPython\n")
                self.assertEqual(
                    [row["text"] for row in result["requirements"]],
                    ["Python"],
                )
                exclusions = result["decomposition_debug"]["unheaded_raw_exclusions"]
                self.assertTrue(exclusions)
                self.assertTrue(
                    all(
                        item["reason"] == "recruiting_call_to_action"
                        for item in exclusions
                    )
                )

        result = _canonical(
            "As a Front-End Engineer, you will implement user interfaces.\n"
            "The candidate must have a strong foundation in web technologies.\n"
            "Requirements\nPython\n"
        )
        self.assertEqual(
            [row["text"] for row in result["requirements"]],
            [
                "implement user interfaces",
                "have a strong foundation in web technologies",
                "Python",
            ],
        )

    def test_one_or_more_bullet_alternatives_remain_one_parent_requirement(self):
        result = _canonical(
            "Requirements\n"
            "Experience with AI systems, including one or more of:\n"
            "- RAG pipelines\n"
            "- model inference services\n"
            "- vector search / retrieval systems\n"
            "- orchestration workflows\n"
        )
        rows = result["requirements"]
        self.assertEqual(len(rows), 1)
        self.assertIn("one or more of", rows[0]["text"])
        self.assertEqual(rows[0]["group_weight_fraction"], 1.0)
        grounding = rows[0]["source_provenance"][0]["grounding"]
        self.assertEqual(grounding["list_structure"], "one_or_more_of")
        self.assertEqual(grounding["list_item_count"], 4)
        self.assertEqual(len(grounding["list_item_span_ids"]), 4)

    def test_multiline_example_and_alternative_lists_preserve_item_boundaries(self):
        result = _canonical(
            "Requirements\n"
            "Experience working with AI systems, including one or more of:\n"
            "- LLM applications\n"
            "- RAG pipelines\n"
            "model inference services\n"
            "vector search / retrieval systems\n"
            "- AI orchestration workflows\n"
            "Strong understanding of communication and integration protocols such as:\n"
            "- gRPC\n"
            "- REST\n"
            "- MQTT\n"
            "real-time messaging / streaming systems\n"
            "Experience with Docker\n"
        )
        rows = result["requirements"]

        self.assertEqual(
            [row["text"] for row in rows],
            [
                (
                    "Experience working with AI systems, including one or more of: "
                    "LLM applications ; RAG pipelines ; model inference services ; "
                    "vector search / retrieval systems ; AI orchestration workflows"
                ),
                (
                    "Strong understanding of communication and integration protocols "
                    "such as: gRPC ; REST ; MQTT ; real-time messaging / streaming systems"
                ),
                "Experience with Docker",
            ],
        )
        self.assertEqual({row["importance"] for row in rows}, {"required"})
        self.assertEqual(
            [
                row["source_provenance"][0]["grounding"].get("list_structure")
                for row in rows[:2]
            ],
            ["one_or_more_of", "example_list"],
        )
        self.assertEqual(
            [
                row["source_provenance"][0]["grounding"].get("list_item_count")
                for row in rows[:2]
            ],
            [5, 4],
        )
        self.assertTrue(all(row["group_weight_fraction"] == 1.0 for row in rows))

    def test_explicit_section_mixed_intro_context_and_importance_are_sentence_local(self):
        result = _canonical(
            "Role Overview\n"
            "We’re looking for a Front-End Engineer who enjoys solving hard problems. "
            "This is a hands-on engineering role for builders who like shipping systems. "
            "We are seeking skilled engineers with proven web expertise (mobile is a plus!) "
            "to join our dynamic team. "
            "As a Front-End Engineer, you will implement user interfaces for web applications. "
            "The candidate must have a strong foundation in web technologies.\n"
            "Preferred Qualifications\n"
            "Familiarity with testing frameworks for front-end development.\n"
            "Excited about building high-performance applications? "
            "We'd love to hear from you!\n"
        )
        rows = result["requirements"]

        self.assertEqual(
            [(row["text"], row["importance"]) for row in rows],
            [
                (
                    "As a Front-End Engineer, you will implement user interfaces "
                    "for web applications",
                    "core",
                ),
                (
                    "The candidate must have a strong foundation in web technologies",
                    "required",
                ),
                (
                    "Familiarity with testing frameworks for front-end development",
                    "preferred",
                ),
            ],
        )

        filtered = {
            (row["text"], row["reason"])
            for row in result["filtered_non_requirement_rows"]
        }
        self.assertIn(
            (
                "We’re looking for a Front-End Engineer who enjoys solving hard problems",
                "recruiting_role_intro",
            ),
            filtered,
        )
        self.assertIn(
            (
                "This is a hands-on engineering role for builders who like shipping systems",
                "role_summary_context",
            ),
            filtered,
        )
        self.assertIn(
            (
                "We are seeking skilled engineers with proven web expertise (mobile is a plus!) "
                "to join our dynamic team",
                "recruiting_role_intro",
            ),
            filtered,
        )
        self.assertIn(
            (
                "Excited about building high-performance applications?",
                "recruiting_call_to_action",
            ),
            filtered,
        )
        self.assertIn(
            ("We'd love to hear from you!", "recruiting_call_to_action"),
            filtered,
        )

    def test_standalone_preferred_heading_is_structural_and_controls_following_rows(self):
        result = _canonical(
            "Requirements\n"
            "Strong Python software engineering skills.\n"
            "Preferred\n"
            "AWS or other cloud deployment experience.\n"
            "CI/CD experience.\n"
        )

        self.assertEqual(
            [(row["text"], row["importance"]) for row in result["requirements"]],
            [
                ("Strong Python software engineering skills", "required"),
                ("AWS or other cloud deployment experience", "preferred"),
                ("CI/CD experience", "preferred"),
            ],
        )
        self.assertIn(
            {
                "text": "Preferred",
                "section": "preferred",
                "source": "raw_jd",
            },
            result["filtered_section_headings"],
        )

    def test_required_section_familiarity_does_not_leak_preferred_importance(self):
        rows = _canonical(
            "Job Requirements\n"
            "Interest in online games and familiarity with recent tactical "
            "shooting titles.\n"
        )["requirements"]

        self.assertEqual(
            [(row["text"], row["importance"]) for row in rows],
            [
                ("Interest in online games", "required"),
                (
                    "familiarity with recent tactical shooting titles",
                    "required",
                ),
            ],
        )
        self.assertTrue(row["is_atomic"] for row in rows)
        self.assertTrue(
            all(row["group_weight_fraction"] == 0.5 for row in rows)
        )

    def test_fuzzy_dedup_does_not_broaden_stronger_importance_across_sections(self):
        result = _canonical(
            "Responsibilities\n"
            "Design and implement Python backend services and REST APIs.\n"
            "Requirements\n"
            "Experience designing REST APIs.\n"
        )

        self.assertEqual(
            [(row["text"], row["importance"]) for row in result["requirements"]],
            [
                (
                    "Design and implement Python backend services and REST APIs",
                    "core",
                ),
                ("Experience designing REST APIs", "required"),
            ],
        )
        self.assertEqual(result["merge_debug"], [])

        # Exact duplicates are still one capability and may inherit the
        # strongest importance without broadening the wording.
        exact = _canonical(
            "Responsibilities\n"
            "Build backend APIs.\n"
            "Requirements\n"
            "Build backend APIs.\n"
        )["requirements"]
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0]["text"], "Build backend APIs")
        self.assertEqual(exact[0]["importance"], "required")
        self.assertEqual(len(exact[0]["source_provenance"]), 2)

    def test_wrapped_lines_and_bullet_boundaries_are_metamorphically_stable(self):
        variants = (
            "Requirements\n"
            "- Build production\n"
            "  applications using Python\n"
            "- MQTT\n"
            "- real-time messaging / streaming systems\n",
            "Requirements\r\n"
            "* Build production\r\n"
            "    applications using Python\r\n"
            "* MQTT\r\n"
            "* real-time messaging / streaming systems\r\n",
            "Requirements\n"
            "• Build production\n"
            " applications using Python\n"
            "• MQTT\n"
            "• real-time messaging / streaming systems\n",
        )
        canonical_rows = []
        for raw in variants:
            rows = _canonical(raw)["requirements"]
            canonical_rows.append(
                [
                    (
                        row["requirement_id"],
                        row["text"],
                        row["importance"],
                        row["atomic_group_id"],
                        row["group_weight_fraction"],
                    )
                    for row in rows
                ]
            )
            self.assertEqual(
                [row["text"] for row in rows],
                [
                    "Build production applications using Python",
                    "MQTT",
                    "real-time messaging / streaming systems",
                ],
            )
        self.assertEqual(canonical_rows[0], canonical_rows[1])
        self.assertEqual(canonical_rows[0], canonical_rows[2])

    def test_approved_non_split_controls_remain_coherent(self):
        controls = (
            "Experience with OpenGL and/or Vulkan",
            "Good foundation in linear algebra, calculus and geometry",
            "Strong foundation in linear algebra, calculus and geometry",
            "Design and implement backend services",
            "Experience with C/C++",
            "Work independently with some guidance",
        )
        for value in controls:
            with self.subTest(value=value):
                rows = _canonical(f"Requirements\n{value}\n")["requirements"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["text"], value)
                self.assertEqual(rows[0]["group_weight_fraction"], 1.0)

    def test_unheaded_context_and_ungrounded_model_profile_are_not_canonical(self):
        raw = (
            "We are a robotics company working alongside industry experts.\n"
            "Join our team to build the future.\n"
        )
        result = _canonical(
            raw,
            {"required_skills": ["Kubernetes administration"]},
        )

        self.assertEqual(result["requirements"], [])
        debug = result["decomposition_debug"]
        self.assertEqual(len(debug["ungrounded_profile_requirements"]), 1)
        self.assertTrue(debug["rejected_unheaded_spans"])

    def test_exact_duplicate_standalone_requirement_does_not_add_scoring_row(self):
        result = _canonical(
            "Requirements\n"
            "Build backend APIs and write automated tests\n"
            "Build backend APIs\n"
        )
        rows = result["requirements"]
        api = next(row for row in rows if row["text"] == "Build backend APIs")

        self.assertEqual(len(rows), 2)
        self.assertEqual(len(api["source_provenance"]), 2)
        self.assertEqual(
            [item["contributes_scoring_allocation"] for item in api["source_provenance"]],
            [True, False],
        )

    def test_exact_duplicate_compound_parent_does_not_add_second_allocation(self):
        result = _canonical(
            "Requirements\n"
            "Build backend APIs and write automated tests\n"
            "Build backend APIs and write automated tests\n"
        )
        rows = result["requirements"]

        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["atomic_group_id"] for row in rows}), 1)
        self.assertTrue(
            all(
                [
                    item["contributes_scoring_allocation"]
                    for item in row["source_provenance"]
                ].count(True)
                == 1
                for row in rows
            )
        )

    def test_partially_overlapping_compound_parents_do_not_transitively_collapse(self):
        result = _canonical(
            "Requirements\n"
            "Build backend APIs and write automated tests\n"
            "Build backend APIs and deploy services\n"
        )
        rows = result["requirements"]
        api = next(row for row in rows if row["text"] == "Build backend APIs")
        testing = next(row for row in rows if row["text"] == "write automated tests")
        deployment = next(row for row in rows if row["text"] == "deploy services")

        self.assertEqual(len(rows), 3)
        self.assertEqual(api["atomic_group_id"], testing["atomic_group_id"])
        self.assertNotEqual(api["atomic_group_id"], deployment["atomic_group_id"])
        self.assertEqual(
            sorted(
                sum(
                    row["atomic_group_id"] == group
                    for row in rows
                )
                for group in {row["atomic_group_id"] for row in rows}
            ),
            [1, 2],
        )

    def test_source_group_fraction_is_provenance_not_a_second_weighting_engine(self):
        result = _canonical(
            "Requirements\n"
            "Experience using Git, relational databases, and REST APIs\n"
        )
        rows = result["requirements"]
        self.assertEqual(len(rows), 3)
        for row in rows:
            row["match_label"] = "direct"
            row["match_value"] = MATCH_VALUES["direct"]
            self.assertAlmostEqual(row["group_weight_fraction"], 1 / 3, places=6)
            source = row["source_provenance"][0]
            self.assertAlmostEqual(source["source_group_fraction"], 1 / 3, places=6)
            self.assertNotIn("parent_group_weight_fraction", source)

        score, numerator, denominator = _weighted_coverage(rows, {"required"})
        self.assertEqual(score, 100.0)
        self.assertAlmostEqual(numerator, 4.0)
        self.assertAlmostEqual(denominator, 4.0)

    def test_formatting_variants_keep_ids_groups_and_source_fractions_stable(self):
        first = _canonical(
            "Requirements\nBuild backend APIs and write automated tests\n"
        )["requirements"]
        second = _canonical(
            "Requirements:\n  Build backend APIs and write automated tests.  \n"
        )["requirements"]

        self.assertEqual(
            [(row["requirement_id"], row["atomic_group_id"], row["group_weight_fraction"]) for row in first],
            [(row["requirement_id"], row["atomic_group_id"], row["group_weight_fraction"]) for row in second],
        )

    def test_decomposition_version_is_emitted_and_changes_stable_currentness(self):
        analysis = build_stable_analysis(
            jd_profile={},
            keyword_match={"present": [], "missing": []},
            raw_jd_text="Requirements\nBuild backend APIs\n",
            resume_profile={},
            retrieval_mode_override="off",
        )

        self.assertEqual(analysis["scoring_version"], "stable-evidence-v1.5-phase6d10")
        self.assertEqual(analysis["scoring_version"], SCORING_VERSION)
        self.assertEqual(
            analysis["canonicalisation_debug"][
                "canonical_requirement_decomposition_version"
            ],
            CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION,
        )

    def test_adversarial_formatting_matrix_preserves_conservative_boundaries(self):
        cases = (
            ("Requirements\nC/C++programming\n", 1, "C/C++ programming"),
            ("Requirements\nC++programming\n", 1, "C++ programming"),
            ("Requirements\nC++ programming\n", 1, "C++ programming"),
            ("Requirements\nExperience with OpenGLand/or Vulkan\n", 1, "OpenGL and/or"),
            ("Requirements\nBuild APIs.Test services\n", 2, "Build APIs"),
            ("Requirements\nGood written and verbal communication skills\n", 1, "communication"),
            ("Requirements\nKnowledge of A, B, or C\n", 1, "Knowledge of"),
            ("Requirements\nExperience using Git, SQL, and REST APIs\n", 3, "Experience using"),
            ("Preferred Skills\nDocker\n", 1, "Docker"),
            ("Core Requirements\nDistributed systems\n", 1, "Distributed"),
            ("Requirements\nExperience with\nKubernetes\n", 1, "Kubernetes"),
            ("Requirements\nBuild backend APIs and deploy services\n", 2, "Build backend"),
            ("- Experience with Python\n", 1, "Python"),
            ("We are a company working alongside industry experts.\n", 0, ""),
            ("Benefits\nMedical coverage and annual leave\n", 0, ""),
        )
        for raw, expected_count, expected_fragment in cases:
            with self.subTest(raw=raw):
                rows = _canonical(raw)["requirements"]
                self.assertEqual(len(rows), expected_count)
                if expected_fragment:
                    self.assertTrue(
                        any(expected_fragment in row["text"] for row in rows)
                    )

    def test_random_whitespace_and_line_wrap_are_metamorphically_stable(self):
        single_line = _canonical(
            "Requirements\nExperience with Kubernetes\n"
        )["requirements"]
        wrapped = _canonical(
            "Requirements\nExperience with\nKubernetes\n"
        )["requirements"]
        self.assertEqual(
            [(row["requirement_id"], row["text"]) for row in single_line],
            [(row["requirement_id"], row["text"]) for row in wrapped],
        )


if __name__ == "__main__":
    unittest.main()
