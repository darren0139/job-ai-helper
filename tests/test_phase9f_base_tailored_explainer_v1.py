"""Focused read-only contract tests for selected-Base vs Tailored and project reasons."""
from __future__ import annotations

import copy
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tailoring.phase9f_base_vs_tailored_explainer import (
    load_latest_phase8_read_only, requirement_delta_rows,
    verify_selected_base_phase8_pair,
)
from tailoring.project_selection_explainer_ui import project_explanation_tables


def _analysis(score=42, match="none"):
    return {
        "deterministic_alignment_score": score,
        "scoring_version": "test-score-v1",
        "capability_taxonomy_version": "taxonomy-1",
        "technology_registry_version": "registry-1",
        "jd_structure_inference_version": "jd-1",
        "technology_registry_resolution_version": "resolution-1",
        "canonical_requirements": [
            {"requirement_id": "req-1", "text": "Experience with Python and CI",
             "importance": "core", "match_label": match, "evidence": []},
        ],
    }


def _pair():
    before = _analysis()
    return (
        {"selected": {"source_display_name": "Base V8", "source_type": "base_resume"},
         "confirmation_id": "immutable-confirmation", "analysis": before},
        {"application_id": 12, "generation_id": "fitted-1", "verification_fingerprint": "saved-verification",
         "comparison_valid": True, "before_stable_analysis": copy.deepcopy(before),
         "after_stable_analysis": _analysis(58, "direct"),
         "fit_one_page": True, "generation_status": "draft"},
    )


class Phase9FBaseTailoredExplainerV1Tests(unittest.TestCase):
    def test_pair_is_exact_saved_selected_base_not_initial_analysis(self):
        base, result = _pair()
        pair = verify_selected_base_phase8_pair(base, result, application_id=12)
        self.assertEqual((42, 58, 16), (pair["before_score"], pair["after_score"], pair["score_delta"]))
        self.assertFalse(pair["approved"])
        self.assertEqual("Base V8", pair["source_name"])

    def test_foreign_application_cannot_inherit_base_delta(self):
        base, result = _pair()
        with self.assertRaisesRegex(ValueError, "different Application"):
            verify_selected_base_phase8_pair(base, result, application_id=156)

    def test_different_baseline_same_total_score_fails_closed(self):
        base, result = _pair()
        result["before_stable_analysis"]["canonical_requirements"][0]["match_label"] = "direct"
        with self.assertRaisesRegex(ValueError, "differs from the confirmed"):
            verify_selected_base_phase8_pair(base, result, application_id=12)

    def test_separate_initial_analysis_can_use_verified_selected_base_branch(self):
        base, result = _pair()
        unrelated_initial = _analysis(14)
        result["before_stable_analysis"] = unrelated_initial
        result["selected_base_analysis"] = {"stable_analysis": copy.deepcopy(base["analysis"])}
        result["selected_base_job_match_ab"] = {"comparable": True}
        pair = verify_selected_base_phase8_pair(base, result, application_id=12)
        self.assertEqual(16, pair["score_delta"])
        result["selected_base_job_match_ab"] = {"comparable": False}
        with self.assertRaisesRegex(ValueError, "no compatible selected-base branch"):
            verify_selected_base_phase8_pair(base, result, application_id=12)

    def test_mismatched_version_and_requirement_scope_fail(self):
        base, result = _pair()
        result["after_stable_analysis"]["scoring_version"] = "future-version"
        with self.assertRaisesRegex(ValueError, "scoring_version"):
            verify_selected_base_phase8_pair(base, result, application_id=12)
        base, result = _pair()
        result["after_stable_analysis"]["canonical_requirements"][0]["requirement_id"] = "unrelated"
        with self.assertRaisesRegex(ValueError, "requirement IDs"):
            verify_selected_base_phase8_pair(base, result, application_id=12)

    def test_missing_or_invalid_verification_never_claims_gain(self):
        base, result = _pair()
        result["comparison_valid"] = False
        with self.assertRaisesRegex(ValueError, "did not verify"):
            verify_selected_base_phase8_pair(base, result, application_id=12)
        base, result = _pair()
        result["generation_id"] = ""
        with self.assertRaisesRegex(ValueError, "identity missing"):
            verify_selected_base_phase8_pair(base, result, application_id=12)

    def test_requirement_rows_report_observed_evidence_not_causality(self):
        base, result = _pair()
        rows = requirement_delta_rows(base["analysis"], result["after_stable_analysis"])
        self.assertEqual(1, len(rows))
        self.assertEqual("Yes", rows[0]["Evidence changed"])
        self.assertEqual("none", rows[0]["Base match"])
        self.assertEqual("direct", rows[0]["Tailored match"])
        self.assertNotIn("Cause", rows[0])

    def test_read_only_phase8_loader_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "no.db"
            self.assertIsNone(load_latest_phase8_read_only(12, db_path=path))
            self.assertFalse(path.exists())

    def test_read_only_phase8_loader_picks_exact_application_last_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.db"
            with closing(sqlite3.connect(path)) as conn, conn:
                conn.execute("CREATE TABLE application_tailoring_verifications "
                             "(id INTEGER PRIMARY KEY, application_id INTEGER, created_at TEXT, result_json TEXT)")
                conn.execute("INSERT INTO application_tailoring_verifications(application_id,created_at,result_json) VALUES (?,?,?)",
                             (12, "2026-01-01", json.dumps({"generation_id": "old"})))
                conn.execute("INSERT INTO application_tailoring_verifications(application_id,created_at,result_json) VALUES (?,?,?)",
                             (156, "2026-12-01", json.dumps({"generation_id": "wrong-app"})))
                conn.execute("INSERT INTO application_tailoring_verifications(application_id,created_at,result_json) VALUES (?,?,?)",
                             (12, "2026-11-13", json.dumps({"generation_id": "new"})))
            before = path.read_bytes()
            self.assertEqual("new", load_latest_phase8_read_only(12, db_path=path)["generation_id"])
            self.assertEqual(before, path.read_bytes())

    def test_project_ranking_table_uses_saved_requirement_matches(self):
        saved = {
            "candidate_project_ranking": [
                {"project_id": "p1", "title": "Job AI Helper", "selection_rank": 1,
                 "recommendation": "include", "final_score": 68,
                 "deterministic_coverage_score": 26, "unique_coverage_bonus": 8,
                 "overlap_penalty": 0, "reason": "Direct match to CI requirement",
                 "requirement_matches": [{"requirement_id": "req-1", "requirement_text": "Build CI pipelines",
                     "match_label": "direct", "importance": "core", "coverage_points": 12,
                     "capability_id": "software.ci", "evidence_snippets": ["Built GitHub Actions pipeline"],
                     "evidence_ids": ["evidence-11"], "source": "canonical_evidence"}]},
                {"project_id": "p2", "title": "Unrelated project", "recommendation": "exclude",
                 "final_score": 0, "requirement_matches": []},
            ],
            "recommended_projects": [{"project_id": "p1", "title": "Job AI Helper", "draft_bullets": ["Built CI"]}],
        }
        tables = project_explanation_tables(saved)
        self.assertEqual(2, len(tables["summary"]))
        self.assertEqual("Yes", tables["summary"][0]["Generated"])
        self.assertEqual("No", tables["summary"][1]["Generated"])
        self.assertEqual("Build CI pipelines", tables["summary"][0]["Matched JD requirements"])
        self.assertEqual("software.ci", tables["summary"][0]["Recognized capabilities"])
        self.assertEqual("Built GitHub Actions pipeline", tables["details"][0]["Evidence excerpts"])
        self.assertEqual(1, len(tables["details"]))

    def test_missing_ranking_does_not_invent_project_rank_or_keywords(self):
        saved = {"recommended_projects": [{"project_id": "p1", "title": "Example", "draft_bullets": ["Bullet"]}]}
        data = project_explanation_tables(saved)
        self.assertIsNone(data["summary"][0]["Candidate order"])
        self.assertIsNone(data["summary"][0]["Selection rank"])
        self.assertEqual("", data["summary"][0]["Matched JD requirements"])
        self.assertFalse(data["ranking_available"])


if __name__ == "__main__":
    unittest.main()
