from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from tailoring import phase9e_blueprint_selection_ui as ui


HARNESS = """
from tailoring.phase9e_blueprint_selection_ui import render_phase9e_blueprint_selection
render_phase9e_blueprint_selection(application_id=94, baseline_report={})
"""


def button(app, key):
    return next(item for item in app.button if item.key == key)


class Phase9EChangeSourceRenderingTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "status": "current",
            "can_generate": True,
            "decision": {
                "scope_activation_status": "active",
                "current_scope_status": "current",
                "decision_id": "bound-decision",
                "decision_fingerprint": "bound-fingerprint",
            },
        }
        stack = self.enterContext(ExitStack())
        self.resolve = stack.enter_context(patch.object(
            ui, "resolve_current_phase9e_generation_context",
            side_effect=lambda application_id: deepcopy(self.context),
        ))
        # Guard against restoring the standalone lookup alongside context
        # resolution (and keep this isolated UI fixture away from real DBs).
        stack.enter_context(patch.object(
            ui, "get_current_application_blueprint_decision", create=True,
            side_effect=AssertionError("Duplicate bound-decision validation"),
        ))
        self.observed_modes = []
        self.active = stack.enter_context(patch.object(
            ui, "_show_active_binding",
            side_effect=lambda **kwargs: self.observed_modes.append(
                bool(ui.st.session_state.get("phase9e_change_source_mode_94"))
            ),
        ))
        stack.enter_context(patch.object(ui, "_render_decision_history"))
        stack.enter_context(patch.object(ui, "phase9f_d_execution_state", return_value=None))
        # Stop at source selection: isolate UI transitions from expensive scoring
        # and all database access. The real acceptance test covers full previews.
        self.source_lookup = stack.enter_context(patch.object(
            ui, "get_exact_job_description_for_application",
            side_effect=ui.Phase9EDecisionError("Source selection unavailable"),
        ))

    def reset_counts(self):
        self.resolve.reset_mock()
        self.active.reset_mock()
        self.source_lookup.reset_mock()
        self.observed_modes.clear()

    def test_change_and_cancel_render_once_with_fresh_validated_context(self):
        app = AppTest.from_string(HARNESS).run()
        self.assertEqual(list(app.exception), [])
        self.reset_counts()

        button(app, "phase9e_change_source_94").click().run()
        self.assertEqual(list(app.exception), [])
        self.resolve.assert_called_once_with(94)
        self.active.assert_called_once()
        self.source_lookup.assert_called_once_with(94)
        self.assertEqual(self.observed_modes, [True])
        self.assertEqual(
            self.active.call_args.kwargs["current"], self.context["decision"]
        )
        self.assertIs(
            self.active.call_args.kwargs["current"],
            self.active.call_args.kwargs["generation_context"]["decision"],
        )
        self.assertIsNotNone(button(app, "phase9e_cancel_change_source_94"))
        self.assertFalse(any(item.key == "phase9e_bind_94" for item in app.button))

        self.reset_counts()
        button(app, "phase9e_cancel_change_source_94").click().run()
        self.assertEqual(list(app.exception), [])
        self.resolve.assert_called_once_with(94)
        self.active.assert_called_once()
        self.source_lookup.assert_not_called()
        self.assertEqual(self.observed_modes, [False])
        self.assertIsNotNone(button(app, "phase9e_change_source_94"))
        self.assertEqual(self.context["decision"]["decision_id"], "bound-decision")

    def test_change_source_rechecks_currentness_instead_of_reusing_prior_render(self):
        app = AppTest.from_string(HARNESS).run()
        self.assertEqual(list(app.exception), [])
        self.reset_counts()
        self.context["status"] = "stale"
        self.context["can_generate"] = False
        self.context["decision"]["current_scope_status"] = "stale"

        button(app, "phase9e_change_source_94").click().run()
        self.assertEqual(list(app.exception), [])
        self.resolve.assert_called_once_with(94)
        self.active.assert_not_called()
        self.source_lookup.assert_called_once_with(94)
        self.assertFalse(any(item.key == "phase9e_bind_94" for item in app.button))
        self.assertFalse(self.context["can_generate"])


if __name__ == "__main__":
    unittest.main()
