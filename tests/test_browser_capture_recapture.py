from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from browser_integration.bridge_server import JobAIBridgeServer, TOKEN_HEADER
from database import browser_capture_manager as manager
from job_discovery.structural_text_selection import PROVENANCE_KEY, select_structural_jd_text


PAGE = (Path(__file__).parent / "fixtures/ncs_automatic_capture_page.txt").read_text(encoding="utf-8")


def payload(job_id="A", revision="old"):
    text = PAGE.replace("Recent graduates", f"{revision} revision: Recent graduates")
    return {
        "source": {"url": f"https://www.ncs.co/careers/job-details/?jobSource=sm&jobId={job_id}",
                   "site_adapter": "generic", "capture_mode": "automatic", "captured_at": revision},
        "capture": {"raw_visible_text": text},
        "job": {"job_title": "AI Software Engineer (Nucleus Graduate Programme)", "jd_text": text},
    }


class AutomaticRecaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        db_patch = patch.object(manager, "DB_PATH", Path(temporary.name) / "applications.db")
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def test_changed_a_b_a_refreshes_one_pending_identity_and_latest_fields(self):
        first = manager.save_browser_job_capture(payload())
        other = manager.save_browser_job_capture(payload("B"))
        newest = payload(revision="new")
        newest["source"]["url"] += "&utm_source=recapture"
        last = manager.save_browser_job_capture(newest)
        self.assertEqual(last["id"], first["id"])
        self.assertNotEqual(last["id"], other["id"])
        self.assertNotEqual(last["capture_hash"], first["capture_hash"])
        self.assertEqual(len(manager.list_browser_job_captures()), 2)
        self.assertEqual(len(manager.list_browser_job_captures(status="pending")), 2)
        self.assertEqual(last["raw_page_text"], newest["capture"]["raw_visible_text"])
        expected = select_structural_jd_text(newest["job"]["jd_text"], job_title=newest["job"]["job_title"])
        self.assertEqual(last["jd_text"], expected["selected_description"])
        self.assertIn("new revision", last["jd_text"])
        stored = json.loads(last["payload_json"])
        self.assertEqual(stored[PROVENANCE_KEY], expected)
        self.assertEqual(stored["source"], newest["source"])
        self.assertEqual(stored["job"]["jd_text"], newest["job"]["jd_text"])
        self.assertEqual(last["first_received_at"], first["first_received_at"])

    def test_identical_source_reruns_current_selector_and_updates_old_receipt(self):
        original = payload()
        old_receipt = {"version": "older-selector", "selected_description": "Old derived text"}
        with patch.object(manager, "select_structural_jd_text", return_value=old_receipt):
            old = manager.save_browser_job_capture(original)
        with patch.object(manager, "select_structural_jd_text", wraps=select_structural_jd_text) as selector:
            new = manager.save_browser_job_capture(original)
        selector.assert_called_once_with(original["job"]["jd_text"], job_title=original["job"]["job_title"])
        self.assertEqual(new["id"], old["id"])
        self.assertEqual(new["capture_hash"], old["capture_hash"])
        self.assertEqual(new["raw_page_text"], original["capture"]["raw_visible_text"])
        receipt = json.loads(new["payload_json"])[PROVENANCE_KEY]
        self.assertEqual(receipt, select_structural_jd_text(original["job"]["jd_text"], job_title=original["job"]["job_title"]))
        self.assertEqual(new["jd_text"], receipt["selected_description"])

    def test_same_second_a_b_a_is_ordered_by_latest_receipt(self):
        times = [datetime(2026, 11, 20, 12, 0, 0, microsecond=n) for n in (100, 200, 300)]
        with patch.object(manager, "datetime") as clock:
            clock.now.side_effect = times
            first = manager.save_browser_job_capture(payload())
            other = manager.save_browser_job_capture(payload("B"))
            last = manager.save_browser_job_capture(payload())
        self.assertEqual(last["id"], first["id"])
        self.assertEqual([r["id"] for r in manager.list_browser_job_captures(status="pending")],
                         [first["id"], other["id"]])

    def test_manual_selections_keep_existing_content_hash_revision_behavior(self):
        first_payload = payload()
        first_payload["source"]["capture_mode"] = "user_selection"
        second_payload = deepcopy(first_payload)
        second_payload["job"]["jd_text"] = "Another explicit user selection."
        first = manager.save_browser_job_capture(first_payload)
        second = manager.save_browser_job_capture(second_payload)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(manager.get_browser_job_capture(first["id"])["jd_text"], first_payload["job"]["jd_text"])
        self.assertEqual(second["jd_text"], second_payload["job"]["jd_text"])
        self.assertNotIn(PROVENANCE_KEY, json.loads(second["payload_json"]))

    def test_terminal_exact_hash_revival_and_changed_content_history_stay_unchanged(self):
        for status in ("used", "promoted", "superseded", "cleared"):
            with self.subTest(status=status):
                original = payload(status)
                saved = manager.save_browser_job_capture(original)
                with closing(manager._connect()) as connection:
                    connection.execute("UPDATE browser_job_captures SET status=? WHERE id=?", (status, saved["id"]))
                    connection.commit()
                changed = manager.save_browser_job_capture(payload(status, "new"))
                self.assertNotEqual(changed["id"], saved["id"])
                self.assertEqual(manager.get_browser_job_capture(saved["id"])["status"], status)
                revived = manager.save_browser_job_capture(original)
                self.assertEqual(revived["id"], saved["id"])
                self.assertEqual(revived["status"], "pending")
                self.assertEqual(manager.get_browser_job_capture(changed["id"])["status"], "superseded")

    def test_real_bridge_post_a_b_a_updates_persisted_selected_text(self):
        server = JobAIBridgeServer(("127.0.0.1", 0), "test-recapture-token")
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            def post(value):
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/v1/jd-captures",
                    data=json.dumps(value).encode("utf-8"),
                    headers={TOKEN_HEADER: "test-recapture-token", "Content-Type": "application/json",
                             "Origin": "moz-extension://test-recapture"},
                )
                with urlopen(request, timeout=5) as response:
                    return json.load(response)
            first = post(payload())
            other = post(payload("B"))
            newest = payload(revision="new")
            last = post(newest)
            self.assertTrue(last["ok"])
            self.assertEqual(last["capture"]["id"], first["capture"]["id"])
            self.assertNotEqual(last["capture"]["id"], other["capture"]["id"])
            row = manager.get_browser_job_capture(last["capture"]["id"])
            expected = select_structural_jd_text(newest["job"]["jd_text"], job_title=newest["job"]["job_title"])
            self.assertEqual(row["jd_text"], expected["selected_description"])
            self.assertEqual(json.loads(row["payload_json"])[PROVENANCE_KEY], expected)
            self.assertEqual(len(manager.list_browser_job_captures()), 2)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
