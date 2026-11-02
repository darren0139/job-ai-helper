"""UI-only controls for full-page Job Finder and saved score provenance."""
from pathlib import Path
import ast
import unittest

from tailoring.initial_score_breakdown_ui import initial_score_math, _score_map_csv


ROOT = Path(__file__).resolve().parents[1]


class FullPageAndSessionControlsTests(unittest.TestCase):
    def test_job_finder_no_one_job_dropdown_and_all_sizes(self):
        ui = (ROOT / "job_discovery/ui.py").read_text(encoding="utf-8")
        self.assertIn('options=[5, 10, 20, 40, 50, 100, "All"]', ui)
        self.assertIn('for card_offset, card_job in enumerate(page_jobs, start=1)', ui)
        self.assertIn('match_display_label(card_job, card_state)', ui)
        self.assertIn('Full job description · #', ui)
        self.assertIn('job_finder_select_card_v17_', ui)
        self.assertNotIn('"Open job details"', ui)
        self.assertIn('max(1, len(filtered_jobs))', ui)
        ast.parse(ui)

    def test_sidebar_has_no_arbitrary_all_cap(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"application_session_display_limit_v2"', app)
        self.assertIn('options=[5, 10, 20, 40, 50, 100, "All"]', app)
        self.assertIn('application_session_limit = -1 if show_all_application_sessions', app)
        self.assertNotIn('application_session_limit = 1000 if', app)
        ast.parse(app)

    def test_initial_score_is_gated_on_native_saved_parity(self):
        self.assertIsNone(initial_score_math({"contribution_status": "Historical contributions unavailable"}))
        self.assertIsNone(initial_score_math({"contribution_status": "available", "stable_analysis": {}}))

    def test_initial_score_map_uses_exact_receipt_rows(self):
        receipt = {"jd_requirements": [
            {"requirement_id": "req_1", "requirement": "Build REST APIs",
             "importance": "core", "match_label": "direct", "current_final_points": 12.5},
        ]}
        csv_text = _score_map_csv(receipt)
        self.assertIn("Build REST APIs", csv_text)
        self.assertIn("req_1", csv_text)
        self.assertIn("12.5", csv_text)

    def test_phase8_calculation_remains_native_and_unchanged(self):
        old = (ROOT / "tailoring/phase8_score_explainability_ui.py").read_text(encoding="utf-8")
        self.assertIn('Which JD requirements make up the 100 points?', old)
        self.assertIn('Show requirement-level math', old)
        initial = (ROOT / "tailoring/initial_analysis_explainer_ui.py").read_text(encoding="utf-8")
        self.assertIn('render_initial_score_math(st, view)', initial)
        self.assertIn('Exact historical score contributions are unavailable', (ROOT / "tailoring/initial_score_breakdown_ui.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
