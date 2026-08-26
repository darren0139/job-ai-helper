from __future__ import annotations

import unittest

import tailoring.jd_specific_rephrase_preview as rephrase


class CompactRephraseContextTests(unittest.TestCase):
    def test_evidence_selection_is_bounded_and_relevant(self):
        evidence = [
            "unrelated evidence " + ("x" * 200),
            "Built the help desk UI with React",
            "Used PostgreSQL through Supabase",
            "Published a mobile game",
        ] + [
            f"irrelevant evidence record {index}"
            for index in range(60)
        ]

        selected = rephrase._select_prompt_evidence(
            evidence=evidence,
            bullet_texts=[
                "Built a React help desk application with Supabase",
            ],
            jd_profile={
                "requirements": [
                    "React web applications",
                    "PostgreSQL",
                ],
            },
            raw_jd_text="Build React web applications backed by PostgreSQL.",
            max_items=3,
            max_chars=1000,
        )

        self.assertLessEqual(len(selected), 3)
        self.assertLessEqual(sum(len(item) for item in selected), 1000)
        self.assertIn("Built the help desk UI with React", selected)
        self.assertIn("Used PostgreSQL through Supabase", selected)

    def test_current_bullet_is_not_duplicated_as_evidence(self):
        contexts = [
            {
                "project_index": 0,
                "bullet_index": 0,
                "project_title": "QueryAI",
                "canonical_bullet": "Built a React help desk app.",
                "current_bullet": "Built a React help desk app.",
                "frozen_project_evidence": [
                    "Built a React help desk app.",
                    "Used Supabase and PostgreSQL.",
                ],
                "jd_profile": {
                    "requirements": ["React", "PostgreSQL"],
                },
                "raw_jd_text": "React and PostgreSQL experience.",
            }
        ]

        grouped = rephrase._group_batch_prompt_contexts(contexts)

        self.assertEqual(len(grouped), 1)
        self.assertNotIn(
            "Built a React help desk app.",
            grouped[0]["frozen_project_evidence"],
        )
        self.assertIn(
            "Used Supabase and PostgreSQL.",
            grouped[0]["frozen_project_evidence"],
        )

    def test_batch_output_budget_is_reduced(self):
        self.assertEqual(rephrase._batch_rephrase_max_tokens(1), 420)
        self.assertEqual(rephrase._batch_rephrase_max_tokens(3), 540)
        self.assertEqual(rephrase._batch_rephrase_max_tokens(10), 1800)
        self.assertEqual(rephrase._batch_rephrase_max_tokens(20), 2200)

    def test_prompt_json_is_compact(self):
        rendered = rephrase._compact_prompt_json(
            {"requirements": ["React", "PostgreSQL"]}
        )
        self.assertEqual(
            rendered,
            '{"requirements":["React","PostgreSQL"]}',
        )
        self.assertNotIn("\n", rendered)


if __name__ == "__main__":
    unittest.main()
