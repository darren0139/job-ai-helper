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


class Phase9EImmutableReuseRenderingTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.created = False
        self.context = {
            "status": "current", "can_generate": True,
            "decision": {
                "scope_activation_status": "active",
                "current_scope_status": "current",
                "recommended_tailoring": "reuse_approved_blueprint",
            },
        }
        stack = self.enterContext(ExitStack())
        self.resolve = stack.enter_context(patch.object(
            ui, "resolve_current_phase9e_generation_context",
            side_effect=self.resolve_context,
        ))
        self.render = stack.enter_context(patch.object(
            ui, "_show_active_binding", side_effect=self.show_binding,
        ))
        self.action = stack.enter_context(patch.object(
            ui, "set_application_blueprint_workflow_action",
            side_effect=lambda **kwargs: self.events.append("validate_action"),
        ))
        self.materialize = stack.enter_context(patch.object(
            ui, "create_or_reuse_current_application_result",
            side_effect=self.create_result,
        ))
        stack.enter_context(patch.object(ui, "_render_decision_history"))
        stack.enter_context(patch.object(ui, "phase9f_d_execution_state", return_value=None))
        self.editable = stack.enter_context(patch.object(
            ui, "create_or_reuse_phase9e_editable_action_draft",
            side_effect=AssertionError("Immutable reuse must not create a draft"),
        ))

    def resolve_context(self, application_id):
        self.events.append("validate_render")
        return deepcopy(self.context)

    def show_binding(self, **kwargs):
        self.events.append("render")
        if not self.created:
            ui._render_workflow_actions(
                application_id=kwargs["application_id"],
                decision=kwargs["current"], actor_label=kwargs["actor_label"],
            )

    def create_result(self, **kwargs):
        self.events.append("validate_and_materialize")
        self.created = True
        return {
            "cache_status": "miss",
            "application_result": {"application_result_id": "immutable-result"},
        }

    def reset_counts(self):
        self.events.clear()
        for mock in (self.resolve, self.render, self.action, self.materialize):
            mock.reset_mock()

    def test_reuse_validates_and_materializes_before_one_render(self):
        app = AppTest.from_string(HARNESS).run()
        self.assertEqual(list(app.exception), [])
        self.action.assert_not_called()
        self.materialize.assert_not_called()
        app.text_input[0].set_value("Current reviewer").run()
        self.reset_counts()
        next(b for b in app.button if b.key == "phase9e_reuse_unchanged_94").click().run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(self.events, [
            "validate_action", "validate_and_materialize", "validate_render", "render",
        ])
        self.resolve.assert_called_once_with(94)
        self.render.assert_called_once()
        self.action.assert_called_once_with(
            application_id=94, workflow_action="use_blueprint_unchanged",
            acknowledgement=False, reason="", actor_label="Current reviewer",
        )
        self.materialize.assert_called_once_with(
            application_id=94, actor_label="Current reviewer",
        )
        self.editable.assert_not_called()
        self.assertTrue(any("one immutable application result" in s.value for s in app.success))
        self.reset_counts()
        app.run()
        self.action.assert_not_called()
        self.materialize.assert_not_called()
        self.resolve.assert_called_once_with(94)

    def test_currentness_failure_does_not_materialize_or_report_success(self):
        app = AppTest.from_string(HARNESS).run()
        self.reset_counts()
        self.action.side_effect = ui.Phase9EDecisionError("Binding changed; reuse blocked")
        next(b for b in app.button if b.key == "phase9e_reuse_unchanged_94").click().run()
        self.assertEqual(list(app.exception), [])
        self.action.assert_called_once()
        self.materialize.assert_not_called()
        self.resolve.assert_called_once_with(94)
        self.render.assert_called_once()
        self.assertTrue(any("reuse blocked" in e.value for e in app.error))
        self.assertFalse(any("one immutable application result" in s.value for s in app.success))


if __name__ == "__main__":
    unittest.main()
