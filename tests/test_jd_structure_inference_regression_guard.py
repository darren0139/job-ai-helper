from __future__ import annotations

import unittest

from analysis_stability.jd_section_inference import infer_semantic_list_heading
from analysis_stability.stable_evidence_scoring import canonicalise_requirements


class JDStructureInferenceRegressionGuardTests(unittest.TestCase):
    def test_requirement_list_introducer_is_not_custom_heading(self):
        result = infer_semantic_list_heading(
            [
                "Experience with AI systems, including one or more of:",
                "- RAG pipelines",
                "- model inference services",
                "- vector search / retrieval systems",
            ],
            0,
        )
        self.assertFalse(result["is_heading_candidate"])
        self.assertEqual(result["reason"], "requirement_like_line")

    def test_action_requirement_is_not_custom_heading(self):
        result = infer_semantic_list_heading(
            [
                "Build production applications using Python",
                "- MQTT",
                "- real-time messaging / streaming systems",
            ],
            0,
        )
        self.assertFalse(result["is_heading_candidate"])
        self.assertEqual(result["reason"], "requirement_like_line")

    def test_lowercase_wrapped_continuation_is_not_heading(self):
        result = infer_semantic_list_heading(
            [
                "applications using Python",
                "- MQTT",
                "- real-time messaging / streaming systems",
            ],
            0,
        )
        self.assertFalse(result["is_heading_candidate"])
        self.assertEqual(result["reason"], "not_heading_shape")

    def test_one_or_more_contract_survives(self):
        result = canonicalise_requirements(
            {},
            "Requirements\n"
            "Experience with AI systems, including one or more of:\n"
            "- RAG pipelines\n"
            "- model inference services\n"
            "- vector search / retrieval systems\n"
            "- orchestration workflows\n",
        )
        rows = result["requirements"]
        self.assertEqual(len(rows), 1)
        grounding = rows[0]["source_provenance"][0]["grounding"]
        self.assertEqual(grounding.get("list_structure"), "one_or_more_of")
        self.assertEqual(grounding.get("list_item_count"), 4)

    def test_multiline_example_contract_survives(self):
        result = canonicalise_requirements(
            {},
            "Requirements\n"
            "Strong understanding of communication and integration protocols such as:\n"
            "- gRPC\n"
            "- REST\n"
            "- MQTT\n"
            "real-time messaging / streaming systems\n"
            "Experience with Docker\n",
        )
        self.assertEqual(
            [row["text"] for row in result["requirements"]],
            [
                (
                    "Strong understanding of communication and integration protocols "
                    "such as: gRPC ; REST ; MQTT ; real-time messaging / streaming systems"
                ),
                "Experience with Docker",
            ],
        )

    def test_wrapped_line_contract_survives(self):
        result = canonicalise_requirements(
            {},
            "Requirements\n"
            "- Build production\n"
            "  applications using Python\n"
            "- MQTT\n"
            "- real-time messaging / streaming systems\n",
        )
        self.assertEqual(
            [row["text"] for row in result["requirements"]],
            [
                "Build production applications using Python",
                "MQTT",
                "real-time messaging / streaming systems",
            ],
        )

    def test_heading_diagnostics_keep_legacy_shape(self):
        result = canonicalise_requirements(
            {},
            "Requirements\nPython\nPreferred\nAWS experience\n",
        )
        self.assertIn(
            {"text": "Preferred", "section": "preferred", "source": "raw_jd"},
            result["filtered_section_headings"],
        )

    def test_mixed_section_contract_survives(self):
        result = canonicalise_requirements(
            {},
            "Requirements and Skills\n"
            "• C++\n"
            "• Data Structures\n\n"
            "Bonus Requirements and Skills\n"
            "• Android/Kotlin\n"
            "• CUDA\n",
        )
        self.assertEqual(
            [(row["text"], row["importance"]) for row in result["requirements"]],
            [
                ("C++", "required"),
                ("Data Structures", "required"),
                ("Android/Kotlin", "preferred"),
                ("CUDA", "preferred"),
            ],
        )

    def test_generic_company_heading_capability_is_retained(self):
        result = canonicalise_requirements(
            {},
            "How You'll Make an Impact\n"
            "- Build and maintain backend services.\n"
            "- Collaborate with engineers on application design.\n"
            "- Troubleshoot production software issues.\n"
            "What You Bring\n"
            "- Experience with Python and Java.\n"
            "- Knowledge of SQL databases.\n"
            "- Ability to work in a collaborative team.\n",
        )
        text = "\n".join(row["text"] for row in result["requirements"])
        self.assertIn("Build and maintain backend services", text)
        self.assertIn("Knowledge of SQL databases", text)


if __name__ == "__main__":
    unittest.main()
