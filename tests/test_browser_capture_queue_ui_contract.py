from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "tailoring" / "browser_capture_ui.py"
MANAGER = ROOT / "database" / "browser_capture_manager.py"


class BrowserCaptureQueueUiContractTests(unittest.TestCase):
    def test_queue_has_confirmed_clear_action(self) -> None:
        text = UI.read_text(encoding="utf-8")

        self.assertIn("Queue maintenance", text)
        self.assertIn("Clear pending queue", text)
        self.assertIn("browser_jd_clear_pending_queue_confirm", text)
        self.assertIn("disabled=not clear_confirmed", text)
        self.assertIn("clear_pending_browser_job_captures()", text)

    def test_manager_clear_is_status_based_not_delete(self) -> None:
        text = MANAGER.read_text(encoding="utf-8")

        self.assertIn("def clear_pending_browser_job_captures()", text)
        self.assertIn("SET status = 'cleared'", text)
        self.assertIn("WHERE status = 'pending'", text)
        self.assertNotIn(
            "DELETE FROM browser_job_captures",
            text,
        )


if __name__ == "__main__":
    unittest.main()
