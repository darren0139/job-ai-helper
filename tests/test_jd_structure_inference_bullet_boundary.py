from __future__ import annotations

import unittest

from analysis_stability.jd_section_inference import infer_semantic_list_heading
from analysis_stability.stable_evidence_scoring import canonicalise_requirements


class JDStructureInferenceBulletBoundaryTests(unittest.TestCase):
    def test_bullet_item_is_never_custom_heading_candidate(self):
        for bullet in ("-", "*", "•"):
            with self.subTest(bullet=bullet):
                result = infer_semantic_list_heading(
                    [
                        f"{bullet} Data Structures",
                        "- Android/Kotlin",
                        "- CUDA",
                    ],
                    0,
                )
                self.assertFalse(result["is_heading_candidate"])
                self.assertEqual(result["reason"], "not_heading_shape")

    def test_required_bullet_data_structures_survives(self):
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

    def test_first_alternative_bullet_does_not_clear_section(self):
        result = infer_semantic_list_heading(
            [
                "- RAG pipelines",
                "- model inference services",
                "- vector search / retrieval systems",
                "- orchestration workflows",
            ],
            0,
        )
        self.assertFalse(result["is_heading_candidate"])
        self.assertEqual(result["reason"], "not_heading_shape")

    def test_one_or_more_list_coalescing_and_provenance_survive(self):
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
        self.assertEqual(
            rows[0]["text"],
            (
                "Experience with AI systems, including one or more of: "
                "RAG pipelines ; model inference services ; "
                "vector search / retrieval systems ; orchestration workflows"
            ),
        )
        grounding = rows[0]["source_provenance"][0]["grounding"]
        self.assertEqual(grounding.get("list_structure"), "one_or_more_of")
        self.assertEqual(grounding.get("list_item_count"), 4)
        self.assertEqual(len(grounding.get("list_item_span_ids") or []), 4)


if __name__ == "__main__":
    unittest.main()
