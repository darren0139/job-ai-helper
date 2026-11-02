"""Focused regression coverage for read-only diagnostics and skill retention."""
import unittest
from unittest.mock import patch

from tailoring import stable_tailoring_ranking as ranking


class SkillRetentionV1Tests(unittest.TestCase):
    def setUp(self):
        self.requirement = {
            "text": "Familiarity with Nvidia CUDA",
            "importance": "preferred",
            "match_label": "transferable",
            "evidence": [{
                "text": "NVIDIA cuDF",
                "section": "skills",
                "source": "resume_profile.skills.frameworks[6]",
            }],
        }

    def test_exact_baseline_credit_recovers_preferred_rank_only(self):
        with patch.object(ranking, "match_requirement_to_candidate", return_value={"label": "none"}):
            rel, req, pref, ids, details = ranking._skill_requirement_relevance(
                "NVIDIA cuDF", {"req_cuda": self.requirement}
            )
        self.assertEqual(rel, 3)
        self.assertFalse(req)
        self.assertTrue(pref)
        self.assertEqual(ids, ["req_cuda"])
        self.assertEqual(details[0]["strategy"], "frozen_baseline_exact_selected_skill_v1")

    def test_does_not_transfer_credit_to_other_skills(self):
        self.assertEqual(ranking._frozen_baseline_skill_match("nvidia cuda", self.requirement), "")
        self.assertEqual(ranking._frozen_baseline_skill_match("mongodb", self.requirement), "")

    def test_does_not_credit_unselected_or_unverified_evidence(self):
        for altered in (
            {**self.requirement, "match_label": "none"},
            {**self.requirement, "evidence": [{**self.requirement["evidence"][0], "source": "evidence_library.tools"}]},
            {**self.requirement, "evidence": [{**self.requirement["evidence"][0], "section": "projects"}]},
        ):
            with self.subTest(altered=altered):
                self.assertEqual(ranking._frozen_baseline_skill_match("nvidia cudf", altered), "")

    def test_native_requirement_is_not_modified(self):
        before = repr(self.requirement)
        with patch.object(ranking, "match_requirement_to_candidate", return_value={"label": None}):
            ranking._skill_requirement_relevance("NVIDIA cuDF", {"req_cuda": self.requirement})
        self.assertEqual(repr(self.requirement), before)


if __name__ == "__main__":
    unittest.main()
