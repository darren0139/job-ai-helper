from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class Phase9E1BlueprintLifecycleUsabilityTests(unittest.TestCase):
    def test_phase9d_navigation_is_deferred_until_before_sidebar_widget(
        self,
    ) -> None:
        lifecycle = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_blueprint_lifecycle_ui.py"
        ).read_text(encoding="utf-8")
        app = (REPO_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn(
            'st.session_state["_pending_navigation_page"] = (',
            lifecycle,
        )
        self.assertNotIn(
            'st.session_state["navigation_page"] = "Global Blueprints"',
            lifecycle,
        )
        self.assertIn('"Blueprint Library"', lifecycle)

        pending = app.index(
            'pending_navigation_page = st.session_state.pop('
        )
        widget = app.index('key="navigation_page"')
        self.assertLess(pending, widget)
        self.assertIn(
            'st.session_state["navigation_page"] = pending_navigation_page',
            app[pending:widget],
        )

    def test_application_phase9c_is_scoped_to_current_candidate(
        self,
    ) -> None:
        text = (
            REPO_ROOT
            / "tailoring"
            / "phase9c_blueprint_evaluation_ui.py"
        ).read_text(encoding="utf-8")

        self.assertIn("preferred_id = _clean(preferred_candidate_id)", text)
        self.assertIn("candidate_options = [preferred_id]", text)
        self.assertIn(
            'st.session_state["phase9c_candidate_id"] = preferred_id',
            text,
        )
        self.assertIn(
            "This application lifecycle is locked to its current ",
            text,
        )
        self.assertIn(
            "Phase 9B candidate. Historical or unrelated candidates are ",
            text,
        )

    def test_phase9c_recovery_can_reopen_phase8(self) -> None:
        lifecycle = (
            REPO_ROOT
            / "tailoring"
            / "phase9e1_blueprint_lifecycle_ui.py"
        ).read_text(encoding="utf-8")
        app = (REPO_ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn("Open Phase 8 for re-verification", lifecycle)
        self.assertIn(
            'f"phase8_force_open_{application_id}"',
            lifecycle,
        )
        self.assertIn("phase8_force_open = bool(", app)
        self.assertIn("expanded=phase8_force_open", app)


    def test_global_blueprints_route_reads_application_id_from_session_state(
        self,
    ) -> None:
        app = (REPO_ROOT / "app.py").read_text(encoding="utf-8")

        render_index = app.index("render_phase9d_global_blueprints(")
        route = app[max(0, render_index - 300):render_index + 350]

        self.assertIn(
            "global_blueprint_application_id = st.session_state.get(",
            route,
        )
        self.assertIn(
            '"current_application_id"',
            route,
        )
        self.assertIn(
            "current_application_id=global_blueprint_application_id",
            route,
        )
        self.assertNotIn(
            "current_application_id=current_application_id",
            route,
        )

if __name__ == "__main__":
    unittest.main()
