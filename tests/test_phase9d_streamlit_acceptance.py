from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from database import tailoring_version_manager as base_manager
import database.global_blueprint_manager as global_blueprint_manager_module
import database.phase9f_exact_verified_reuse_manager as exact_reuse_module
from database.global_blueprint_manager import (
    blueprint_variant_id,
    list_global_blueprint_audit_events,
    list_global_blueprints,
)
from tailoring.phase9d_variant_tags import suggest_blueprint_variant_lane
from tests.phase9d_test_support import (
    persist_historical_v2_evaluation,
    persist_non_provisional_evaluation,
    seed_phase9d_database,
)


HARNESS = Path(__file__).with_name("phase9d_streamlit_harness.py")


def _by_key(elements, key):
    return next(element for element in elements if element.key == key)


class Phase9DStreamlitAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.old_environment = os.environ.get("PHASE9D_TEST_DATABASE")
        self.old_artifact_environment = os.environ.get(
            "PHASE9F_BLUEPRINT_ARTIFACT_ROOT"
        )
        self.old_artifact_roots = (
            global_blueprint_manager_module.BLUEPRINT_ARTIFACT_ROOT,
            exact_reuse_module.BLUEPRINT_ARTIFACT_ROOT,
        )
        self.database_path = Path(self.temporary.name) / "streamlit-phase9d.sqlite"
        self.state = seed_phase9d_database(self.database_path)
        self.historical = persist_historical_v2_evaluation(
            self.state["provisional_evaluation"]
        )
        os.environ["PHASE9D_TEST_DATABASE"] = str(self.database_path)
        artifact_root = Path(self.temporary.name) / "blueprint-artifacts"
        os.environ["PHASE9F_BLUEPRINT_ARTIFACT_ROOT"] = str(artifact_root)
        global_blueprint_manager_module.BLUEPRINT_ARTIFACT_ROOT = artifact_root
        exact_reuse_module.BLUEPRINT_ARTIFACT_ROOT = artifact_root

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        if self.old_environment is None:
            os.environ.pop("PHASE9D_TEST_DATABASE", None)
        else:
            os.environ["PHASE9D_TEST_DATABASE"] = self.old_environment
        if self.old_artifact_environment is None:
            os.environ.pop("PHASE9F_BLUEPRINT_ARTIFACT_ROOT", None)
        else:
            os.environ["PHASE9F_BLUEPRINT_ARTIFACT_ROOT"] = (
                self.old_artifact_environment
            )
        (
            global_blueprint_manager_module.BLUEPRINT_ARTIFACT_ROOT,
            exact_reuse_module.BLUEPRINT_ARTIFACT_ROOT,
        ) = self.old_artifact_roots
        self.temporary.cleanup()

    def test_historical_is_disabled_and_provisional_requires_explicit_override(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])

        source = (
            HARNESS.parents[1]
            / "tailoring"
            / "phase9d_global_blueprint_ui.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('state = "Current"', source)
        self.assertIn('"Legacy · read-only"', source)

        show_other = _by_key(
            app.checkbox,
            "phase9d_show_nonpending_evaluations",
        )
        self.assertFalse(show_other.value)
        self.assertFalse(
            any(
                item.key == "phase9d_variant_intent"
                for item in app.radio
            )
        )
        self.assertFalse(
            any(item.key == "phase9d_approve" for item in app.button)
        )

        show_other.set_value(True).run()
        evaluation = _by_key(app.selectbox, "phase9d_evaluation_id")
        evaluation.set_value(self.historical["evaluation_id"]).run()
        self.assertTrue(
            any(
                "legacy" in warning.value.lower()
                and "read-only" in warning.value.lower()
                for warning in app.warning
            )
        )
        self.assertFalse(
            any(
                item.key == "phase9d_review_approval"
                for item in app.button
            )
        )
        self.assertFalse(
            any(item.key == "phase9d_approve" for item in app.button)
        )

        evaluation = _by_key(app.selectbox, "phase9d_evaluation_id")
        evaluation.set_value(
            self.state["provisional_evaluation"]["evaluation_id"]
        ).run()
        self.assertFalse(
            any(
                item.key == "phase9d_variant_intent"
                for item in app.radio
            )
        )
        _by_key(app.button, "phase9d_review_approval").click().run()
        acknowledgement = _by_key(
            app.checkbox,
            "phase9d_provisional_acknowledgement",
        )
        self.assertFalse(acknowledgement.value)
        self.assertTrue(_by_key(app.button, "phase9d_approve").disabled)

        acknowledgement.set_value(True).run()
        self.assertFalse(
            any(
                element.key == "phase9d_provisional_reason"
                for element in app.text_area
            )
        )
        approve = _by_key(app.button, "phase9d_approve")
        self.assertFalse(approve.disabled)
        approve.click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                "immutable blueprint" in message.value.lower()
                for message in app.success
            )
        )
        versions = list_global_blueprints()
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["status"], "active")
        snapshot = versions[0]["blueprint_snapshot"]
        self.assertIn("frozen_resume_snapshot", snapshot)
        self.assertIn("phase9b_candidate_semantic_snapshot", snapshot)
        self.assertIn("phase9c_evaluation_snapshot", snapshot)

    def test_main_app_registers_top_level_blueprint_library_route(self):
        source = (HARNESS.parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('"Blueprint Library"', source)
        self.assertIn('elif page == "Blueprint Library":', source)
        self.assertIn("render_phase9d_global_blueprints(", source)
        self.assertIn(
            "current_application_id=current_application_id",
            source,
        )

    def test_existing_family_requires_explicit_variant_intent(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.button, "phase9d_review_approval").click().run()
        _by_key(
            app.checkbox,
            "phase9d_provisional_acknowledgement",
        ).set_value(True).run()
        _by_key(app.button, "phase9d_approve").click().run()

        non_provisional = persist_non_provisional_evaluation(self.state)
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.selectbox, "phase9d_evaluation_id").set_value(
            non_provisional["evaluation_id"]
        ).run()
        self.assertFalse(
            any(
                item.key == "phase9d_variant_intent"
                for item in app.radio
            )
        )
        _by_key(app.button, "phase9d_review_approval").click().run()
        intent = _by_key(app.radio, "phase9d_variant_intent")
        self.assertIsNone(intent.value)
        self.assertTrue(_by_key(app.button, "phase9d_approve").disabled)

        confirmed_tags = _by_key(app.multiselect, "phase9d_variant_tags")
        confirmed_tags.set_value(["Backend", "AI"]).run()
        self.assertIsNone(_by_key(app.radio, "phase9d_variant_intent").value)
        _by_key(app.radio, "phase9d_variant_intent").set_value(
            "create_new_variant"
        ).run()

        suggested_label = "Backend / AI"
        self.assertEqual(
            _by_key(app.text_input, "phase9d_new_variant_label").value,
            suggested_label,
        )
        self.assertFalse(_by_key(app.button, "phase9d_approve").disabled)
        _by_key(app.button, "phase9d_approve").click().run()
        self.assertTrue(
            any(
                "immutable blueprint" in message.value.lower()
                for message in app.success
            )
        )
        reusable_table = app.dataframe[0].value
        self.assertIn("Variant", reusable_table.columns)
        self.assertTrue(
            {"Primary", suggested_label}.issubset(
                set(reusable_table["Variant"].tolist())
            )
        )
        rows = list_global_blueprints()
        expected_variant_id = blueprint_variant_id(suggested_label)
        self.assertEqual(
            {row["variant_id"] for row in rows if row["status"] == "active"},
            {"primary", expected_variant_id},
        )

        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(
            app.checkbox,
            "phase9d_show_nonpending_evaluations",
        ).set_value(True).run()
        _by_key(app.selectbox, "phase9d_evaluation_id").set_value(
            non_provisional["evaluation_id"]
        ).run()
        self.assertTrue(
            any(
                "already approved" in message.value.lower()
                for message in app.success
            )
        )
        self.assertFalse(
            any(
                item.key == "phase9d_variant_intent"
                for item in app.radio
            )
        )
        _by_key(app.button, "phase9d_use_evaluation_again").click().run()
        self.assertIsNone(_by_key(app.radio, "phase9d_variant_intent").value)
        _by_key(app.multiselect, "phase9d_variant_tags").set_value(
            ["Backend", "AI"]
        ).run()
        _by_key(app.radio, "phase9d_variant_intent").set_value(
            "update_existing_variant"
        ).run()
        self.assertEqual(
            _by_key(app.selectbox, "phase9d_existing_variant_id").value,
            expected_variant_id,
        )

    def test_already_approved_evaluation_is_closed_until_advanced_reuse(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.button, "phase9d_review_approval").click().run()
        _by_key(
            app.checkbox,
            "phase9d_provisional_acknowledgement",
        ).set_value(True).run()
        _by_key(app.button, "phase9d_approve").click().run()
        self.assertEqual(list(app.exception), [])

        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertTrue(
            any(
                "no phase 9c evaluations currently need approval"
                in message.value.lower()
                for message in app.info
            )
        )
        self.assertFalse(
            any(
                item.key == "phase9d_evaluation_id"
                for item in app.selectbox
            )
        )

        _by_key(
            app.checkbox,
            "phase9d_show_nonpending_evaluations",
        ).set_value(True).run()
        _by_key(app.selectbox, "phase9d_evaluation_id").set_value(
            self.state["provisional_evaluation"]["evaluation_id"]
        ).run()
        self.assertTrue(
            any(
                "already approved" in message.value.lower()
                for message in app.success
            )
        )
        self.assertFalse(
            any(
                item.key == "phase9d_variant_intent"
                for item in app.radio
            )
        )
        self.assertFalse(
            any(item.key == "phase9d_approve" for item in app.button)
        )

        _by_key(app.button, "phase9d_use_evaluation_again").click().run()
        self.assertIsNone(_by_key(app.radio, "phase9d_variant_intent").value)
        self.assertTrue(_by_key(app.button, "phase9d_approve").disabled)


    def test_blueprint_library_debug_panel_is_after_inspection_controls(self):
        source = (
            HARNESS.parents[1]
            / "tailoring"
            / "phase9d_global_blueprint_ui.py"
        ).read_text(encoding="utf-8")
        render_source = source[source.index("def render_phase9d_global_blueprints("):]
        bottom_call = render_source.rindex(
            "_render_blueprint_library_debug_panel("
        )
        self.assertGreater(
            bottom_call,
            render_source.index('st.subheader("Blueprint inspection")'),
        )
        self.assertGreater(
            bottom_call,
            render_source.index('"Save display metadata"'),
        )

    def test_blueprint_library_debug_button_generates_snapshot(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        generate = _by_key(
            app.button,
            "phase9d_generate_blueprint_library_debug",
        )
        generate.click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(
            any(
                "debug snapshot generated" in message.value.lower()
                for message in app.success
            )
        )
        self.assertTrue(
            any(
                item.key == "phase9d_show_blueprint_library_debug_preview"
                for item in app.checkbox
            )
        )


    def test_active_variant_lane_tags_can_be_edited_from_inspection(self):
        from database.global_blueprint_tag_manager import get_blueprint_lane_tags

        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.button, "phase9d_review_approval").click().run()
        _by_key(
            app.checkbox,
            "phase9d_provisional_acknowledgement",
        ).set_value(True).run()
        _by_key(app.button, "phase9d_approve").click().run()

        non_provisional = persist_non_provisional_evaluation(self.state)
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.selectbox, "phase9d_evaluation_id").set_value(
            non_provisional["evaluation_id"]
        ).run()
        _by_key(app.button, "phase9d_review_approval").click().run()
        _by_key(app.multiselect, "phase9d_variant_tags").set_value(
            ["Backend", "AI"]
        ).run()
        _by_key(app.radio, "phase9d_variant_intent").set_value(
            "create_new_variant"
        ).run()
        self.assertEqual(
            _by_key(app.text_input, "phase9d_new_variant_label").value,
            "Backend / AI",
        )
        _by_key(app.button, "phase9d_approve").click().run()

        rows = list_global_blueprints()
        backend = next(
            row for row in rows if row["variant_id"] == "backend_ai"
        )

        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.selectbox, "phase9d_inspect_blueprint_id").set_value(
            backend["blueprint_id"]
        ).run()

        suffix = (
            f"{backend['role_family_id']}_{backend['variant_id']}"
        )
        edit_key = f"phase9d_edit_lane_metadata_{suffix}"
        tag_key = f"phase9d_lane_tags_{suffix}"
        save_key = f"phase9d_save_lane_tags_{suffix}"
        cancel_key = f"phase9d_cancel_lane_metadata_{suffix}"

        self.assertFalse(
            any(item.key == tag_key for item in app.multiselect)
        )
        _by_key(app.button, edit_key).click().run()
        self.assertIsNotNone(_by_key(app.multiselect, tag_key))

        _by_key(app.multiselect, tag_key).set_value(
            ["backend", "ai", "data"]
        ).run()
        _by_key(app.button, cancel_key).click().run()
        self.assertFalse(
            any(item.key == tag_key for item in app.multiselect)
        )
        tags_after_cancel = get_blueprint_lane_tags(
            role_family_id=backend["role_family_id"],
            variant_id=backend["variant_id"],
        )
        self.assertEqual(
            [row["tag_id"] for row in tags_after_cancel],
            ["backend", "ai"],
        )

        _by_key(app.button, edit_key).click().run()
        _by_key(app.multiselect, tag_key).set_value(
            ["backend", "ai", "data"]
        ).run()
        _by_key(app.button, save_key).click().run()
        self.assertEqual(list(app.exception), [])
        self.assertFalse(
            any(item.key == tag_key for item in app.multiselect)
        )

        tags = get_blueprint_lane_tags(
            role_family_id=backend["role_family_id"],
            variant_id=backend["variant_id"],
        )
        self.assertEqual(
            [row["tag_id"] for row in tags],
            ["backend", "ai", "data"],
        )

    def test_display_metadata_is_read_only_until_edit_and_cancel_is_non_destructive(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.button, "phase9d_review_approval").click().run()
        _by_key(
            app.checkbox,
            "phase9d_provisional_acknowledgement",
        ).set_value(True).run()
        _by_key(app.button, "phase9d_approve").click().run()
        self.assertEqual(list(app.exception), [])

        blueprint = list_global_blueprints()[0]
        blueprint_id = blueprint["blueprint_id"]
        original_name = blueprint["display_name"]
        original_notes = blueprint["notes"]

        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.selectbox, "phase9d_inspect_blueprint_id").set_value(
            blueprint_id
        ).run()

        edit_key = f"phase9d_edit_display_metadata_{blueprint_id}"
        name_key = f"phase9d_edit_name_{blueprint_id}"
        notes_key = f"phase9d_edit_notes_{blueprint_id}"
        save_key = f"phase9d_save_metadata_{blueprint_id}"
        cancel_key = f"phase9d_cancel_display_metadata_{blueprint_id}"

        self.assertFalse(
            any(item.key == name_key for item in app.text_input)
        )
        _by_key(app.button, edit_key).click().run()

        _by_key(app.text_input, name_key).set_value(
            "Temporary unsaved display name"
        ).run()
        _by_key(app.text_area, notes_key).set_value(
            "Temporary unsaved notes"
        ).run()
        _by_key(app.button, cancel_key).click().run()

        self.assertFalse(
            any(item.key == name_key for item in app.text_input)
        )
        unchanged = next(
            row
            for row in list_global_blueprints()
            if row["blueprint_id"] == blueprint_id
        )
        self.assertEqual(unchanged["display_name"], original_name)
        self.assertEqual(unchanged["notes"], original_notes)

        # Streamlit AppTest can retain a stale element tree after an explicit
        # st.rerun() closes a widget group. Recreate the test client before
        # reopening edit mode so the next interaction starts from the rendered
        # read-only page, matching a fresh browser rerun.
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.selectbox, "phase9d_inspect_blueprint_id").set_value(
            blueprint_id
        ).run()

        _by_key(app.button, edit_key).click().run()
        _by_key(app.text_input, name_key).set_value(
            "Readable Blueprint name"
        ).run()
        _by_key(app.text_area, notes_key).set_value(
            "Saved through explicit edit mode."
        ).run()
        _by_key(app.button, save_key).click().run()
        self.assertEqual(list(app.exception), [])
        self.assertFalse(
            any(item.key == name_key for item in app.text_input)
        )

        updated = next(
            row
            for row in list_global_blueprints()
            if row["blueprint_id"] == blueprint_id
        )
        self.assertEqual(
            updated["display_name"],
            "Readable Blueprint name",
        )
        self.assertEqual(
            updated["notes"],
            "Saved through explicit edit mode.",
        )

    def test_remove_is_confirmed_hidden_by_default_and_restorable(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        _by_key(app.button, "phase9d_review_approval").click().run()
        _by_key(
            app.checkbox, "phase9d_provisional_acknowledgement"
        ).set_value(True).run()
        _by_key(app.button, "phase9d_approve").click().run()
        self.assertEqual(list(app.exception), [])
        blueprint = list_global_blueprints()[0]

        remove = _by_key(
            app.button, f"phase9d_remove_{blueprint['blueprint_id']}"
        )
        remove.click().run()
        confirm = _by_key(
            app.button,
            f"phase9d_confirm_remove_{blueprint['blueprint_id']}",
        )
        self.assertTrue(confirm.disabled)
        _by_key(
            app.checkbox,
            f"phase9d_remove_ack_{blueprint['blueprint_id']}",
        ).set_value(True).run()
        _by_key(
            app.button,
            f"phase9d_confirm_remove_{blueprint['blueprint_id']}",
        ).click().run()
        self.assertEqual(list(app.exception), [])
        removed = list_global_blueprints()[0]
        self.assertEqual(removed["status"], "active")
        self.assertEqual(removed["availability_status"], "removed")
        self.assertTrue(
            any(
                "Historical provenance was preserved" in message.value
                for message in app.success
            )
        )
        self.assertFalse(
            any(
                item.key == f"phase9d_remove_{blueprint['blueprint_id']}"
                for item in app.button
            )
        )
        self.assertTrue(_by_key(app.toggle, "phase9d_show_history").value)

        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        self.assertFalse(_by_key(app.toggle, "phase9d_show_history").value)
        self.assertFalse(
            any(
                "removed" in {
                    str(value).lower()
                    for value in frame.value.get("Availability", [])
                }
                for frame in app.dataframe
                if {
                    "Lifecycle",
                    "Availability",
                    "Evaluation",
                }.issubset(set(frame.value.columns))
            )
        )

        _by_key(app.toggle, "phase9d_show_history").set_value(True).run()
        restore = _by_key(
            app.button, f"phase9d_restore_{blueprint['blueprint_id']}"
        )
        restore.click().run()
        _by_key(
            app.button,
            f"phase9d_confirm_restore_{blueprint['blueprint_id']}",
        ).click().run()
        self.assertEqual(list(app.exception), [])
        restored = list_global_blueprints()[0]
        self.assertEqual(restored["availability_status"], "available")
        self.assertTrue(restored["is_reusable"])
        event_types = {
            event["event_type"]
            for event in list_global_blueprint_audit_events(
                blueprint_id=blueprint["blueprint_id"]
            )
        }
        self.assertIn("removed_from_reuse", event_types)
        self.assertIn("restored_to_reuse", event_types)


if __name__ == "__main__":
    unittest.main()
