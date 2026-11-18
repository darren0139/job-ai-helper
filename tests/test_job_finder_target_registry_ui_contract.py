from __future__ import annotations

import ast
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from database import job_discovery_manager as manager
from tests.test_job_finder_target_registry_portability import payload, target


class TargetRegistryUIContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / "applications.db"
        db_patch = patch.object(manager, "DB_PATH", self.db_path)
        db_patch.start()
        self.addCleanup(db_patch.stop)
        manager.init_job_discovery_schema()
        self.st = MagicMock()
        self.st.session_state = {}
        self.st.file_uploader.return_value = None
        self.st.button.return_value = False
        # Execute the production controls with real persistence functions and
        # a temporary database, without importing unrelated model integrations.
        source = Path("job_discovery/ui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {"_render_target_registry_import", "_render_target_registry_portability"}
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.namespace = {"st": self.st}
        for name in (
            "export_target_company_registry", "preview_target_company_registry_import",
            "import_target_company_registry", "load_singapore_target_company_registry",
        ):
            self.namespace[name] = getattr(manager, name)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "job_discovery/ui.py", "exec"), self.namespace)

    def render(self, uploaded=None, clicked=None):
        self.st.file_uploader.return_value = uploaded
        self.st.button.side_effect = lambda label, **kw: kw["key"] == clicked
        self.namespace["_render_target_registry_portability"]()

    def test_download_contains_exact_portable_json_and_controls_exist(self):
        manager.upsert_target_company(**target(enabled=False))
        self.render(BytesIO(json.dumps(payload(target())).encode()))
        download = self.st.download_button.call_args
        self.assertEqual(download.args[0], "Download target registry")
        self.assertEqual(download.kwargs["file_name"], "job_finder_target_registry.json")
        self.assertEqual(json.loads(download.kwargs["data"]), manager.export_target_company_registry())
        self.assertTrue(download.kwargs["data"].endswith("\n"))
        self.st.file_uploader.assert_called_once_with(
            "Import registry backup", type=["json"], key="job_finder_registry_upload_v1",
        )
        self.assertIn("Import target registry", [call.args[0] for call in self.st.button.call_args_list])
        self.assertIn("Load Singapore starter targets", [call.args[0] for call in self.st.button.call_args_list])
        self.assertEqual(self.st.expander.call_args.args[0], "Singapore starter targets")

    def test_upload_previews_without_writing_or_importing_seed(self):
        before = self.db_path.read_bytes()
        self.render(BytesIO(json.dumps(payload(target())).encode()))
        self.assertEqual(self.db_path.read_bytes(), before)
        self.assertEqual(manager.list_target_companies(include_disabled=True), [])
        first_preview = self.st.dataframe.call_args_list[0].args[0]
        self.assertEqual(first_preview[0]["Action"], "new")
        self.st.rerun.assert_not_called()

    def test_explicit_upload_import_uses_shared_import_and_shows_receipt(self):
        record = payload(target(enabled=False))
        with patch.dict(self.namespace, {
            "import_target_company_registry": manager.import_target_company_registry,
        }):
            self.render(BytesIO(json.dumps(record).encode()), "job_finder_registry_import_v1")
        self.assertEqual(manager.export_target_company_registry(), record)
        self.assertEqual(self.st.session_state["job_finder_registry_import_receipt_v1"]["new_count"], 1)
        self.st.rerun.assert_called_once()
        self.render()
        self.assertIn("Imported 1 targets.", self.st.success.call_args.args[0])

    def test_explicit_seed_loading_uses_same_import_function(self):
        original = manager.import_target_company_registry
        with patch.dict(self.namespace, {"import_target_company_registry": original}):
            self.render(clicked="job_finder_registry_starter_import_v1")
        self.assertEqual(len(manager.list_target_companies(include_disabled=True)), 18)
        self.assertEqual(self.st.session_state["job_finder_registry_import_receipt_v1"]["new_count"], 18)

    def test_invalid_upload_never_reaches_write_action(self):
        for data in (b"not JSON", b"\xff", json.dumps(payload(target(provider="bad"))).encode()):
            with self.subTest(data=data):
                self.st.reset_mock()
                self.render(BytesIO(data), "job_finder_registry_import_v1")
                self.st.error.assert_called_once()
                self.st.rerun.assert_not_called()
                self.assertEqual(manager.list_target_companies(include_disabled=True), [])

    def test_import_failure_is_visible(self):
        def fail(_payload):
            raise OSError("disk is full")

        with patch.dict(self.namespace, {"import_target_company_registry": fail}):
            self.render(BytesIO(json.dumps(payload(target())).encode()), "job_finder_registry_import_v1")
        self.assertIn("disk is full", self.st.error.call_args.args[0])
        self.st.rerun.assert_not_called()
        self.assertEqual(manager.list_target_companies(include_disabled=True), [])

    def test_portability_controls_are_in_existing_registry_area(self):
        tree = ast.parse(Path("job_discovery/ui.py").read_text(encoding="utf-8"))
        renderer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_render_target_company_registry")
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id == "_render_target_registry_portability"
                            for n in ast.walk(renderer)))


if __name__ == "__main__":
    unittest.main()
