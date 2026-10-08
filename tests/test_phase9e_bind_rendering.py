from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from tailoring import phase9e_blueprint_selection_ui as ui
from tailoring import phase9e1_resume_workspace_ui as workspace


HARNESS = """
from tailoring.phase9e_blueprint_selection_ui import render_phase9e_blueprint_selection
render_phase9e_blueprint_selection(application_id=94, baseline_report={})
"""


class Phase9EBindRenderingTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.context = {"status": "unbound", "can_generate": False, "decision": None}
        self.decision = {
            "scope_activation_status": "active", "current_scope_status": "current",
            "decision_fingerprint": "original-source-decision",
            "recommended_tailoring": "full_regeneration",
            "selection": {"selected_source": "original_resume"},
        }
        stack = self.enterContext(ExitStack())
        self.resolve = stack.enter_context(patch.object(
            ui, "resolve_current_phase9e_generation_context", side_effect=self.resolve_context,
        ))
        self.bind = stack.enter_context(patch.object(
            ui, "evaluate_and_bind_application_blueprint", side_effect=self.bind_source,
        ))
        self.active = stack.enter_context(patch.object(
            ui, "_show_active_binding", wraps=ui._show_active_binding,
        ))
        self.preview = stack.enter_context(patch.object(
            ui, "preview_application_blueprint_decision", return_value=self.decision,
        ))
        self.recommend = stack.enter_context(patch.object(
            ui, "_cached_blueprint_recommendation", return_value={
                "classification": {}, "recommended_source": "original_resume",
                "active_blueprints": [],
            },
        ))
        stack.enter_context(patch.object(ui, "get_exact_job_description_for_application", return_value={}))
        stack.enter_context(patch.object(ui, "list_reusable_global_blueprints", return_value=[]))
        stack.enter_context(patch.object(ui, "get_phase9e_base_resume_starting_snapshot", return_value={}))
        stack.enter_context(patch.object(ui, "_tailoring_base_resolution_identity", return_value={}))
        stack.enter_context(patch.object(ui, "_render_tailoring_base_snapshot_preview"))
        stack.enter_context(patch.object(ui, "_show_decision"))
        stack.enter_context(patch.object(ui, "_render_decision_history"))
        stack.enter_context(patch.object(ui, "phase9f_d_execution_state", return_value=None))
        stack.enter_context(patch.object(ui, "get_current_application_resume_result", return_value=None))
        self.validate_workspace = stack.enter_context(patch.object(
            workspace, "get_current_application_blueprint_decision",
            side_effect=AssertionError("Duplicate same-render bound-decision validation"),
        ))
        stack.enter_context(patch.object(workspace, "get_application_generation_control", return_value={}))
        stack.enter_context(patch.object(workspace, "list_tailoring_generations", return_value=[]))
        self.rerun = stack.enter_context(patch.object(
            ui.st, "rerun", side_effect=AssertionError("Extra bind rerun"),
        ))

    def resolve_context(self, application_id):
        self.events.append("resolve")
        return deepcopy(self.context)

    def bind_source(self, **kwargs):
        self.events.append("bind")
        if kwargs["scope_replacement_confirmed"] is not True:
            raise ui.Phase9EDecisionError("Explicit confirmation required")
        self.context = {"status": "current", "can_generate": True, "decision": deepcopy(self.decision)}
        return {"cache_status": "miss"}

    def ready_app(self):
        app = AppTest.from_string(HARNESS, default_timeout=60).run()
        self.assertEqual(list(app.exception), [])
        self.bind.assert_not_called()
        app.text_input[0].set_value("Current reviewer").run()
        next(c for c in app.checkbox if c.key == "phase9e_scope_replacement_ack_94").set_value(True).run()
        self.events.clear()
        for mock in (self.resolve, self.bind, self.preview, self.recommend, self.active):
            mock.reset_mock()
        return app

    def click_bind(self, app):
        next(b for b in app.button if b.key == "phase9e_bind_94").click().run()

    def test_original_bind_precedes_one_fresh_render_without_duplicate_preview(self):
        app = self.ready_app()
        self.click_bind(app)
        self.assertEqual(list(app.exception), [])
        self.assertEqual(self.events, ["bind", "resolve"])
        self.bind.assert_called_once_with(
            application_id=94, scope_replacement_confirmed=True,
            selected_source="original_resume", selected_blueprint_id="",
            selected_base_resume_id="", selection_mode="recommended",
            mismatch_acknowledged=False, actor_label="Current reviewer",
        )
        self.resolve.assert_called_once_with(94)
        self.active.assert_called_once()
        self.preview.assert_not_called()
        self.recommend.assert_not_called()
        self.validate_workspace.assert_not_called()
        self.rerun.assert_not_called()
        self.assertTrue(any("active starting source" in i.value for i in app.info))
        self.assertFalse(any(b.key == "phase9e_regenerate_original_94" for b in app.button))
        self.assertTrue(any("bound a new immutable" in s.value for s in app.success))
        self.assertEqual(self.active.call_args.kwargs["current"]["selection"]["selected_source"], "original_resume")

        self.events.clear()
        self.bind.reset_mock()
        self.resolve.reset_mock()
        self.context["status"] = "stale"
        self.context["decision"]["current_scope_status"] = "stale"
        app.run()
        self.resolve.assert_called_once_with(94)
        self.bind.assert_not_called()
        self.assertEqual(self.events, ["resolve"])

    def test_failed_backend_validation_does_not_activate_or_report_success(self):
        app = self.ready_app()
        self.bind.side_effect = ui.Phase9EDecisionError("Source changed; binding blocked")
        self.click_bind(app)
        self.assertEqual(list(app.exception), [])
        self.bind.assert_called_once()
        self.resolve.assert_called_once_with(94)
        self.assertIsNone(self.context["decision"])
        self.assertTrue(any("binding blocked" in e.value for e in app.error))
        self.assertFalse(any("bound a new immutable" in s.value for s in app.success))
        self.rerun.assert_not_called()

    def test_callback_reads_live_confirmation_and_rejects_changed_selection(self):
        state = {
            "phase9e_selection_94": "original_resume",
            "phase9e_scope_replacement_ack_94": False,
        }
        with patch.object(ui.st, "session_state", state):
            ui._bind_tailoring_base(94, "original_resume", "original_resume", "", "", "original_resume", False)
            self.assertFalse(self.bind.call_args.kwargs["scope_replacement_confirmed"])
            self.assertIsNone(self.context["decision"])
            self.assertIn("confirmation", state["phase9e_action_error_94"])
            self.bind.reset_mock()
            state["phase9e_selection_94"] = "base_resume"
            state["phase9e_scope_replacement_ack_94"] = True
            ui._bind_tailoring_base(94, "original_resume", "original_resume", "", "", "original_resume", False)
            self.bind.assert_not_called()
            self.assertIn("changed", state["phase9e_action_error_94"])

    def test_standalone_workspace_still_validates_fresh_on_every_call(self):
        self.validate_workspace.side_effect = [deepcopy(self.decision), None]
        with patch.object(workspace.st, "session_state", {}):
            first = workspace.get_resume_workspace_context(94)
            second = workspace.get_resume_workspace_context(94)
        self.assertEqual(self.validate_workspace.call_count, 2)
        self.assertEqual(first["phase9e_binding"]["decision_fingerprint"], "original-source-decision")
        self.assertIsNone(second["phase9e_binding"])


if __name__ == "__main__":
    unittest.main()
