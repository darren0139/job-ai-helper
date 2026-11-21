"""V1.5 regression pins: eligibility is not a skill; duty idioms are not qualification gates."""
import unittest

from analysis_stability import stable_evidence_scoring as scoring


class JdHardCueContextV15(unittest.TestCase):
    def test_as_required_role_duty_is_core(self):
        self.assertEqual(
            "core", scoring._unheaded_role_importance(
                "You will also assist with Centre-wide events and duties as required"
            )
        )

    def test_where_required_task_is_core(self):
        self.assertEqual(
            "core", scoring._classify_raw_importance(
                "Enhancement of Existing Solutions — support testing and refinement where required", "core"
            )
        )

    def test_as_needed_collaboration_is_core(self):
        self.assertEqual(
            "core", scoring._classify_raw_importance(
                "Troubleshoot issues, collaborating with cross-functional teams as needed", "core"
            )
        )

    def test_minimum_viable_product_is_not_minimum_qualification(self):
        for value in (
            "Develop a minimum viable product (MVP) for a procurement process",
            "You will deliver a minimum viable product of a GenAI solution",
        ):
            with self.subTest(value=value):
                self.assertEqual("core", scoring._classify_raw_importance(value, "core"))

    def test_business_and_workforce_needs_are_not_hard_cues(self):
        for value in (
            "Translate operational data needs into engineering solutions",
            "Keep pace with evolving technologies, industry trends, and workforce needs",
            "Design processes, with future trends and needs in mind",
            "A mindset that balances rigour with the need for continuous improvement",
        ):
            with self.subTest(value=value):
                self.assertEqual("core", scoring._classify_raw_importance(value, "core"))

    def test_explicit_hard_candidate_qualifications_still_required(self):
        for value in (
            "Minimum 5 years of experience in software engineering",
            "Must have experience implementing APIs",
            "Essential knowledge of distributed systems",
            "Required qualifications include a relevant degree",
            "You need to be proficient in Python",
            "You must translate operational data needs into engineering solutions",
        ):
            with self.subTest(value=value):
                self.assertEqual("required", scoring._classify_raw_importance(value, "core"))

    def test_only_singaporeans_need_apply_is_eligibility_not_skill(self):
        statement = "Only Singaporeans need apply"
        meta = scoring.classify_jd_statement_semantics(statement, source="raw_jd.requirements")
        self.assertFalse(meta["score_eligible"])
        self.assertFalse(meta["tailoring_eligible"])
        self.assertEqual("candidate_eligibility_citizenship_notice", meta["eligibility_rule"])

    def test_eligibility_sentence_does_not_remove_adjacent_real_skill(self):
        raw = "Requirements\nMinimum 5 years of experience in Python development\nOnly Singaporeans need apply"
        result = scoring.canonicalise_requirements({}, raw)
        texts = [row["text"] for row in result["requirements"]]
        self.assertTrue(any("Python development" in text for text in texts))
        self.assertFalse(any("Singaporeans" in text for text in texts))

    def test_hard_qualification_and_eligibility_distinguished(self):
        self.assertEqual("core", scoring._classify_raw_importance("assist as required", "core"))
        self.assertEqual("required", scoring._classify_raw_importance("experience required for this role", "core"))

    def test_frozen_review_419_behavior_unchanged(self):
        token = scoring._REVIEW419_LEGACY_PARSER.set(True)
        try:
            self.assertEqual("required", scoring._unheaded_role_importance(
                "You will also assist with Centre-wide events and duties as required"
            ))
            self.assertEqual("required", scoring._classify_raw_importance(
                "Develop a minimum viable product", "core"
            ))
            meta = scoring.classify_jd_statement_semantics(
                "Only Singaporeans need apply", source="raw_jd.requirements"
            )
            self.assertTrue(meta["score_eligible"])
        finally:
            scoring._REVIEW419_LEGACY_PARSER.reset(token)


if __name__ == "__main__":
    unittest.main()
