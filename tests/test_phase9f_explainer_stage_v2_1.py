"""Focused tests for Phase 9F origin labels and generated-vs-fitted Projects."""
from __future__ import annotations
import unittest
from unittest.mock import patch
import sys
import types

from tailoring.phase9f_explainer_stage_v2_1 import (
    phase8_baseline_mode, confirmed_phase9f_session, project_fit_retention_rows,
    document_phase8_comparison_sections,
)


def _proj(pid, title, bullets):
    return {"project_id": pid, "title": title, "draft_bullets": bullets}


def _fitted(rows):
    return {"fit_one_page": True, "page_count": 1,
            "docx_path": "/some/saved/verified.docx",
            "tailored_projects_used": {"recommended_projects": rows}}


class ExplainerStageV2Tests(unittest.TestCase):
    def test_pre_fitting_has_no_claimed_retention(self):
        out = project_fit_retention_rows({"recommended_projects": [_proj("a", "Alpha", ["One"])]}, None)
        self.assertEqual(out["rows"], [])
        self.assertIn("No fitted result", out["notice"])

    def test_exact_saved_fit_retention_and_bullet_counts(self):
        generated = {"recommended_projects": [
            _proj("a", "Alpha", ["One", "Two", "Three"]),
            _proj("b", "Beta", ["Single"]),
            _proj("c", "Gamma", ["Only"]),
        ]}
        final = _fitted([_proj("a", "Alpha", ["One", "Three"]),
                         _proj("b", "Beta", ["Single"])])
        out = project_fit_retention_rows(generated, final)
        self.assertEqual(len(out["rows"]), 3)
        self.assertEqual(out["rows"][0]["Project outcome"], "Retained with fewer bullets")
        self.assertEqual(out["rows"][0]["Generated bullets"], 3)
        self.assertEqual(out["rows"][0]["Fitted bullets"], 2)
        self.assertEqual(out["rows"][0]["Exact preserved bullets"], 2)
        self.assertEqual(out["rows"][1]["Project outcome"], "Retained unchanged")
        self.assertEqual(out["rows"][2]["Project outcome"], "Not retained in final fit")
        self.assertIn("manual selection or fitting", out["rows"][2]["Reason"])

    def test_manual_vs_fitter_attribution_not_guessed(self):
        out = project_fit_retention_rows({"recommended_projects": [_proj("a", "A", ["One"])]}, _fitted([]))
        self.assertNotIn("fitter removed", str(out).lower())
        self.assertIn("not proven", out["rows"][0]["Reason"])

    def test_missing_docx_or_non_one_page_is_withheld(self):
        source = {"recommended_projects": [_proj("a", "A", ["One"])]}
        for changes in ({"docx_path": ""}, {"fit_one_page": False}, {"page_count": 2}, {"tailored_projects_used": None}):
            with self.subTest(changes=changes):
                saved = {**_fitted([_proj("a", "A", ["One"])]), **changes}
                self.assertEqual(project_fit_retention_rows(source, saved)["rows"], [])

    def test_ambiguous_or_foreign_project_identity_withheld(self):
        source = {"recommended_projects": [_proj("a", "A", ["One"])]}
        for final in (_fitted([_proj("b", "B", ["One"])]),
                      _fitted([_proj("a", "A", ["One"]), _proj("a", "A", ["One"])])):
            self.assertEqual(project_fit_retention_rows(source, final)["rows"], [])

    def test_document_initial_remains_initial_even_with_saved_base(self):
        self.assertEqual(phase8_baseline_mode({"document_analysis": {"initial": {}}, "application_id": 12}), "initial")

    def test_plain_unverified_case_never_labels_selected_base(self):
        self.assertEqual(phase8_baseline_mode({"application_id": 0}), "baseline")

    def test_exact_saved_phase8_binding_enables_base_label(self):
        package = types.ModuleType("tailoring.phase9f_session_handoff")
        package.load_confirmed_source_view = lambda app: {"selected": {"source_id": "v8"}, "confirmation_id": "abc"}
        compare = types.ModuleType("tailoring.phase9f_base_vs_tailored_explainer")
        compare.verify_selected_base_phase8_pair = lambda base, final, application_id: {"comparison_valid": True} if application_id == 12 else {}
        with patch.dict(sys.modules, {"tailoring.phase9f_session_handoff": package,
                                     "tailoring.phase9f_base_vs_tailored_explainer": compare}):
            self.assertEqual(phase8_baseline_mode({"application_id": 12}), "selected_base")
            self.assertEqual(confirmed_phase9f_session(12), True)

    def test_no_confirmation_yields_initial_label(self):
        package = types.ModuleType("tailoring.phase9f_session_handoff")
        package.load_confirmed_source_view = lambda app: None
        with patch.dict(sys.modules, {"tailoring.phase9f_session_handoff": package}):
            self.assertEqual(phase8_baseline_mode({"application_id": 12}), "baseline")
            self.assertFalse(confirmed_phase9f_session(12))

    def test_app_session_switches_base_and_keeps_both_comparisons(self):
        original = {"comparable": True, "summary": {"initial_score": 30}}
        selected = {"comparable": True, "summary": {"initial_score": 40}}
        result = {
            "document_analysis": {"initial": {"input_authority": "ACTUAL_RESUME_DOCUMENT"}},
            "job_match_ab": original,
            "selected_base_analysis": {"same_as_initial": False},
            "selected_base_job_match_ab": selected,
        }
        rows = document_phase8_comparison_sections(result)
        self.assertEqual([r[0] for r in rows], ["Selected Base vs Final", "Initial vs Final"])
        self.assertIs(rows[0][1], selected)
        self.assertIs(rows[1][1], original)
        self.assertEqual(phase8_baseline_mode(result), "initial")

    def test_identical_initial_and_selected_base_not_double_displayed(self):
        original = {"comparable": True}
        result = {"document_analysis": {"initial": {}}, "job_match_ab": original,
                  "selected_base_analysis": {"same_as_initial": True}}
        self.assertEqual(document_phase8_comparison_sections(result),
                         [("Initial / Selected Base vs Final", original)])

    def test_initial_without_selected_source_keeps_original_comparison(self):
        original = {"comparable": True}
        result = {"document_analysis": {"initial": {}}, "job_match_ab": original}
        self.assertEqual(document_phase8_comparison_sections(result),
                         [("Initial vs Final", original)])

    def test_no_document_receipt_is_not_misnamed_initial(self):
        self.assertEqual(document_phase8_comparison_sections({"application_id": 12}), [])
        self.assertEqual(phase8_baseline_mode({"application_id": 0}), "baseline")

    def test_distinct_selected_base_comparison_withheld_if_unavailable(self):
        result = {"document_analysis": {"initial": {}}, "job_match_ab": {"comparable": True},
                  "selected_base_analysis": {"same_as_initial": False}}
        rows = document_phase8_comparison_sections(result)
        self.assertIsNone(rows[0][1])
        self.assertEqual(rows[0][0], "Selected Base vs Final")


if __name__ == "__main__":
    unittest.main()
