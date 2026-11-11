"""Regression controls for the master Job Match publication boundary."""
from copy import deepcopy
import unittest

from analysis_stability.requirement_presentation import report_for_score_publication
from tailoring.job_match_ab_analysis import build_job_match_snapshot, build_job_match_ab_analysis
from tailoring.phase9e_blueprint_selection import _blueprint_variant_ranking_key
from tailoring.phase9e_blueprint_selection_ui import _score_suffix
from tailoring.phase9f_starting_source_ranking import order_scored_candidates


class WithheldScorePublicationTests(unittest.TestCase):
    def test_zero_is_numeric_and_unavailable_has_no_rank(self):
        zero = {"deterministic_alignment_score": 0}
        missing = {"canonical_requirements": []}
        held = {"deterministic_alignment_score": None,
                "score_publication_status": "WITHHELD_PENDING_POLICY_REVIEW"}
        for analysis in (held, missing):
            snapshot = build_job_match_snapshot(
                role="initial", stable_analysis=analysis, raw_jd_text="Synthetic JD")
            self.assertIsNone(snapshot["score"])
            self.assertFalse(build_job_match_ab_analysis(snapshot, snapshot)["comparable"])
            self.assertIn("Job Match Unavailable", _score_suffix(analysis))
            self.assertNotIn("Unavailable%", _score_suffix(analysis))
            self.assertLess(_blueprint_variant_ranking_key({"comparison": zero}),
                            _blueprint_variant_ranking_key({"comparison": analysis}))
        self.assertEqual(build_job_match_snapshot(
            role="initial", stable_analysis=zero, raw_jd_text="Synthetic JD")["score"], 0)
        self.assertEqual(order_scored_candidates([held, missing]), [])

    def test_legacy_snapshot_with_native_hold_is_incompatible(self):
        held = {"deterministic_alignment_score": None, "score_interpretation": "Review pending"}
        view = build_job_match_snapshot(role="initial", stable_analysis=held, raw_jd_text="Synthetic JD")
        historical = {**view, "score": 0, "integrity_blockers": []}
        comparison = build_job_match_ab_analysis(historical, historical)
        self.assertFalse(comparison["comparable"])
        self.assertIn("score_unavailable", comparison["blockers"])

    def test_new_receipt_does_not_copy_legacy_numeric_score_on_hold(self):
        native = {"deterministic_alignment_score": None, "score_interpretation": "Review pending"}
        historical = {"overall_score": 47, "passes_ats_threshold": True, "stable_analysis": native}
        before = deepcopy(historical)
        projected = report_for_score_publication(historical)
        self.assertEqual(historical, before)
        self.assertIsNone(projected["overall_score"])
        self.assertIsNone(projected["passes_ats_threshold"])
        self.assertEqual(projected["summary"], "Review pending")
        self.assertEqual(projected["stable_analysis"], native)
        for value in (0, 67):
            ordinary = {"overall_score": value, "stable_analysis": {"deterministic_alignment_score": value}}
            self.assertEqual(report_for_score_publication(ordinary), ordinary)
