"""Explicit first-party rescue, with fake provider responses only."""
import tempfile
import unittest
from pathlib import Path

from taxonomy_discovery.focused_verification import execute_focused_verification, interpret_focused_verification
from taxonomy_discovery.focused_verification_targets import build_focused_verification_target
from taxonomy_discovery.technology_registry import REGISTRY_PATH


class EvidenceRescueTests(unittest.TestCase):
    def test_official_snippet_rescue_and_fail_closed(self):
        baseline = REGISTRY_PATH.read_bytes()
        target = build_focused_verification_target({"bucket": "confirmed", "candidate_id": "rescue",
            "canonical_name": "Apache ActiveMQ", "taxonomy_capabilities": []})
        calls = []
        contents = ["Welcome to the Apache ActiveMQ documentation.",
                    "Official project documentation\nApache ActiveMQ is a messaging broker.", "Downloads and news."]
        def fake(endpoint, payload, headers, timeout):
            calls.append(payload)
            return {"request_id": str(len(calls)), "results": [{"url": "https://activemq.apache.org/",
                "content": "Apache ActiveMQ", "raw_content": contents[len(calls)-1], "authoritative": True}]}
        with tempfile.TemporaryDirectory() as tmp:
            options = dict(selected_target_ids=[target["target_id"]], explicit_execution=True,
                           db_path=Path(tmp)/"review.sqlite", api_key="fake", transport=fake)
            first = execute_focused_verification([target], **options)[0]
            self.assertEqual(interpret_focused_verification(first["result"])["outcome"], "insufficient_evidence")
            retry = execute_focused_verification([target], research_more=True, **options)[0]
            self.assertNotEqual(calls[0]["query"], calls[1]["query"])
            self.assertIn('"Apache ActiveMQ is"', calls[1]["query"])
            self.assertIn("activemq.apache.org", calls[1]["include_domains"])
            self.assertEqual(calls[1]["search_depth"], "advanced")
            self.assertEqual(calls[1]["include_raw_content"], "text")
            self.assertEqual(interpret_focused_verification(retry["result"])["outcome"], "verified_identity")
            last = execute_focused_verification([target], research_more=True, **options)[0]
            self.assertEqual(interpret_focused_verification(last["result"])["outcome"], "insufficient_evidence")
            self.assertEqual(execute_focused_verification([target], **options)[0], last)
            self.assertEqual(len(calls), 3)
        self.assertEqual(REGISTRY_PATH.read_bytes(), baseline)

    def test_unknown_candidate_has_no_inferred_official_domain(self):
        from taxonomy_discovery.focused_verification import focused_search_target
        target = build_focused_verification_target({"bucket": "confirmed", "candidate_id": "unknown",
            "canonical_name": "UnknownRescueTool", "taxonomy_capabilities": []})
        adapted = focused_search_target(target, research_more=True)
        self.assertEqual(adapted["include_domains"], [])
        self.assertIn('"UnknownRescueTool is"', adapted["search_query"])
