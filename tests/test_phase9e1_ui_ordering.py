"""Static acceptance checks for the Phase 9E.1 application UI order."""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase9E1UIOrderingTests(unittest.TestCase):
    def test_application_flow_renders_source_before_analysis_details(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        flow_start = text.index('        if current_application_id is not None:\n            st.caption(f"Current application session: #{current_application_id}")')
        flow = text[flow_start:]

        overview = flow.index("render_application_workflow_overview(")
        selection = flow.index("render_phase9e_blueprint_selection(")
        phase9a = flow.index("render_evidence_opportunity_analysis(")
        analysis = flow.index("render_application_analysis_details(")
        tailoring = flow.index('st.header("Tailor Résumé Content")')

        self.assertLess(overview, selection)
        self.assertLess(selection, phase9a)
        self.assertLess(phase9a, analysis)
        self.assertLess(analysis, tailoring)

    def test_immutable_result_precedes_collapsed_analysis_details(self) -> None:
        text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        branch_start = text.index("                render_phase9e_application_result(")
        branch_end = text.index("                st.stop()", branch_start)
        branch = text[branch_start:branch_end]

        self.assertLess(
            branch.index("render_phase9e_application_result("),
            branch.index("render_evidence_opportunity_analysis("),
        )
        self.assertLess(
            branch.index("render_evidence_opportunity_analysis("),
            branch.index("render_application_analysis_details("),
        )
        self.assertLess(
            branch.index("render_application_analysis_details("),
            branch.index("render_application_analysis_chat("),
        )

    def test_source_page_uses_workflow_heading(self) -> None:
        text = (
            REPO_ROOT / "tailoring" / "phase9e_blueprint_selection_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('st.header("Tailoring Base")', text)
        self.assertNotIn('st.header("Select a Global Blueprint")', text)

    def test_long_workflow_labels_are_not_streamlit_metrics(self) -> None:
        text = (
            REPO_ROOT / "tailoring" / "phase9e1_workflow_ui.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('metric("Role family"', text)
        self.assertNotIn('metric("Current source"', text)
        self.assertNotIn('metric("Current result"', text)


if __name__ == "__main__":
    unittest.main()
