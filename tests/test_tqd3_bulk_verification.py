import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from database.taxonomy_discovery_review_manager import list_focused_verification_results
from taxonomy_discovery.focused_verification import execute_focused_bulk, focused_review_rows, MAX_FOCUSED_BATCH
from tests.test_tqd3_focused_verification_pipeline import target


class BulkVerificationTests(unittest.TestCase):
    def test_chunking_selection_and_persistence_after_later_failure(self):
        targets = [target("BulkTool" + str(i)) for i in range(8)]
        selected = [t["target_id"] for t in targets[:7]]
        calls = []
        def fake(endpoint, payload, headers, timeout):
            if len(calls) == 4:
                raise RuntimeError("later chunk failed")
            calls.append(payload)
            return {"request_id": str(len(calls)), "results": []}
        with tempfile.TemporaryDirectory() as tmp:
            options = dict(db_path=Path(tmp)/"review.sqlite", transport=fake, api_key="fake")
            with self.assertRaises(ValueError):
                execute_focused_bulk(targets, selected_target_ids=selected, **options)
            from taxonomy_discovery import focused_verification as module
            original = module.execute_focused_verification
            with patch.object(module, "execute_focused_verification", wraps=original) as execute:
                with self.assertRaises(RuntimeError):
                    execute_focused_bulk(targets, selected_target_ids=selected, explicit_execution=True, **options)
                self.assertEqual([len(c.kwargs["selected_target_ids"]) for c in execute.call_args_list], [MAX_FOCUSED_BATCH, MAX_FOCUSED_BATCH])
            saved = list_focused_verification_results(db_path=options["db_path"])
            self.assertEqual(len(saved), 4)
            self.assertTrue(all(r["decision"] is None for r in saved))
            self.assertTrue(all("BulkTool7" not in c["query"] for c in calls))
            report = focused_review_rows(saved)
            self.assertEqual(len(report), 4)
            self.assertTrue(all(r["Human decision"] == "unreviewed" for r in report))
            self.assertTrue(all(r["Verification outcome"] == "insufficient_evidence" for r in report))

    def test_success_all_chunks_and_reload_without_transport(self):
        targets = [target("BulkTool" + str(i)) for i in range(7)]
        calls = []
        def fake(*args):
            calls.append(args)
            return {"request_id": str(len(calls)), "results": []}
        with tempfile.TemporaryDirectory() as tmp:
            options = dict(selected_target_ids=[t["target_id"] for t in targets], explicit_execution=True,
                db_path=Path(tmp)/"review.sqlite", api_key="fake", transport=fake)
            self.assertEqual(len(execute_focused_bulk(targets, **options)), 7)
            self.assertEqual(len(execute_focused_bulk(targets, **options)), 7)
            self.assertEqual(len(calls), 7)
