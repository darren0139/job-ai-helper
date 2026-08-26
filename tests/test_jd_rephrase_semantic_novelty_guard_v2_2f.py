from __future__ import annotations

import unittest

import tailoring.jd_specific_rephrase_preview as rephrase


class RephraseSemanticNoveltyGuardTests(unittest.TestCase):
    def _context(self) -> dict:
        return {
            "canonical_bullet": (
                "Implemented backend data access through PostgREST and applied "
                "Row-Level Security policies to secure database operations."
            ),
            "current_bullet": (
                "Implemented backend data access through PostgREST and applied "
                "Row-Level Security policies to secure database operations."
            ),
            "frozen_project_evidence": [
                "Implemented backend data access through PostgREST.",
                "Applied Row-Level Security policies to secure database operations.",
                "PostgREST",
                "Row-Level Security",
                "PostgreSQL",
            ],
            "raw_jd_text": (
                "Build responsive interfaces and real-time user experiences."
            ),
        }

    def test_real_time_capability_borrowed_from_jd_is_blocked(self):
        result = rephrase.validate_rephrase_suggestion(
            context=self._context(),
            suggested_bullet=(
                "Applied Row-Level Security policies and PostgREST for secure "
                "database access and real-time queries."
            ),
        )

        self.assertFalse(result["safe_for_lineage_evaluation"])
        self.assertIn(
            "unsupported_jd_term",
            result["guard_reasons"],
        )
        self.assertTrue(
            {"real", "time"}
            & set(result["unsupported_jd_tokens"])
        )

    def test_non_jd_invented_capability_phrase_is_blocked(self):
        context = self._context()
        context["raw_jd_text"] = "Build secure web applications."

        result = rephrase.validate_rephrase_suggestion(
            context=context,
            suggested_bullet=(
                "Implemented backend data access through PostgREST with "
                "distributed caching for secure database operations."
            ),
        )

        self.assertFalse(result["safe_for_lineage_evaluation"])
        self.assertIn(
            "unsupported_material_terms",
            result["guard_reasons"],
        )

    def test_safe_paraphrase_verbs_do_not_trigger_novelty_guard(self):
        context = {
            "canonical_bullet": (
                "Set up the React and Supabase project environment and connected "
                "the frontend to the PostgreSQL-backed service."
            ),
            "current_bullet": (
                "Set up the React and Supabase project environment and connected "
                "the frontend to the PostgreSQL-backed service."
            ),
            "frozen_project_evidence": [
                "React",
                "Supabase",
                "PostgreSQL-backed service",
                "frontend",
                "project environment",
            ],
            "raw_jd_text": "React frontend development.",
        }

        result = rephrase.validate_rephrase_suggestion(
            context=context,
            suggested_bullet=(
                "Configured the React and Supabase project environment to "
                "integrate the frontend with the PostgreSQL-backed service."
            ),
        )

        self.assertNotIn(
            "unsupported_jd_term",
            result["guard_reasons"],
        )
        self.assertNotIn(
            "unsupported_material_terms",
            result["guard_reasons"],
        )

    def test_prompt_tells_model_not_to_borrow_unsupported_jd_capabilities(self):
        prompt = rephrase.JD_REPHRASE_BATCH_PROMPT

        self.assertIn(
            "Never borrow a JD capability",
            prompt,
        )
        self.assertIn(
            "Prefer the CURRENT wording unchanged",
            prompt,
        )
        self.assertIn(
            "reason must describe the actual wording change",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
