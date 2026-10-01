from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from database import job_match_manager
from taxonomy_discovery import focused_verification_ui as ui
from tests.test_tqd3_focused_verification_pipeline import target


class FakeStreamlit:
    def __init__(self, clicked=None):
        self.clicked = clicked
        self.messages = []

    def multiselect(self, label, options, **kwargs):
        return options[:1]

    def button(self, label, **kwargs):
        return label == self.clicked and not kwargs.get("disabled", False)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def spinner(self, *args):
        return self

    def expander(self, *args):
        return self

    def columns(self, count):
        return [self] * count

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.messages.append((name, args))


class FocusedVerificationPipelineUITests(unittest.TestCase):
    def test_rerenders_and_selection_never_execute_research(self):
        with patch.object(ui, "st", FakeStreamlit()), patch.object(ui, "execute_focused_verification") as execute, \
                patch.object(ui, "list_focused_verification_results", return_value=[]):
            for _ in range(2):
                ui.render_focused_verification({"targets": [target(), target("OtherTool")]})
            execute.assert_not_called()

    def test_explicit_button_executes_only_selected_target(self):
        targets = [target(), target("OtherTool")]
        with patch.object(ui, "st", FakeStreamlit("Run focused verification")), \
                patch.object(ui, "execute_focused_verification") as execute, \
                patch.object(ui, "list_focused_verification_results", return_value=[]):
            ui.render_focused_verification({"targets": targets})
            execute.assert_called_once_with(targets, selected_target_ids=[targets[0]["target_id"]], explicit_execution=True)

    def test_read_only_snapshot_loader_does_not_initialize_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.sqlite3"
            with closing(sqlite3.connect(path)) as conn:
                conn.execute("""CREATE TABLE job_match_snapshots (
                    id INTEGER PRIMARY KEY, discovered_job_id INTEGER,
                    match_version TEXT, scoring_version TEXT, taxonomy_version TEXT)""")
                conn.commit()
            before = path.read_bytes()
            with patch.object(job_match_manager, "DB_PATH", path), \
                    patch.object(job_match_manager, "init_job_match_schema", side_effect=AssertionError("write")):
                self.assertEqual(job_match_manager.list_latest_compatible_job_match_snapshots(
                    match_version="match", scoring_version="score", taxonomy_version="taxonomy", read_only=True), [])
            self.assertEqual(path.read_bytes(), before)

    def test_missing_snapshot_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.sqlite3"
            with patch.object(job_match_manager, "DB_PATH", path):
                with self.assertRaises(sqlite3.OperationalError):
                    job_match_manager.list_latest_compatible_job_match_snapshots(
                        match_version="match", scoring_version="score", taxonomy_version="taxonomy", read_only=True)
            self.assertFalse(path.exists())

    def test_ui_never_records_approval_or_scores(self):
        source = Path(ui.__file__).read_text(encoding="utf-8")
        for text in ("Send draft to review", "Research more", "No change", "Advanced / Diagnostics"):
            self.assertIn(text, source)
        self.assertNotIn("save_proposal_review", source)
        self.assertNotIn("approve_mapping", source)
        self.assertNotIn("save_job_match_snapshot", source)

    def test_review_and_no_change_do_not_research_and_more_is_explicit(self):
        t = target()
        saved = {"artifact_id": "saved", "decision": None,
                 "result": {"target_id": t["target_id"], "target": t}}
        interpretation = {"canonical_name": "QuasarTool", "outcome": "verified_identity",
            "authoritative_sources": [], "existing_registry_knowledge": {"status": "unresolved"},
            "existing_taxonomy_knowledge": None, "maintainer": "Review evidence",
            "recognized_first_party_organizations": [], "safe_aliases": ["QuasarTool"]}
        draft = {"action": "add_technology_identity", "proposal_bundle": {"proposals": [{"proposal_id": "draft"}]}}
        for label, decision in (("Send draft to review", "send_to_review"), ("No change", "no_change"),
                                ("Research more", "research_more")):
            with self.subTest(label=label), patch.object(ui, "st", FakeStreamlit(label)), \
                    patch.object(ui, "execute_focused_verification") as execute, \
                    patch.object(ui, "list_focused_verification_results", return_value=[saved]), \
                    patch.object(ui, "interpret_focused_verification", return_value=interpretation), \
                    patch.object(ui, "build_focused_draft", return_value=draft), \
                    patch.object(ui, "load_focused_preview_snapshots", return_value=[]), \
                    patch.object(ui, "build_focused_impact_preview", return_value={"available": False, "reason": "missing"}), \
                    patch.object(ui, "save_focused_verification_decision") as save, \
                    patch.object(ui, "import_proposal_bundle") as import_bundle:
                ui.render_focused_verification({"targets": [t]})
                save.assert_called_once_with(artifact_id="saved", decision=decision, draft=draft)
                if label == "Research more":
                    execute.assert_called_once_with([t], selected_target_ids=[t["target_id"]],
                                                    explicit_execution=True, research_more=True)
                else:
                    execute.assert_not_called()
                if label == "Send draft to review":
                    import_bundle.assert_called_once_with(draft["proposal_bundle"])
                else:
                    import_bundle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
