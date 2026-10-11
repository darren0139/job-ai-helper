"""Frozen native presentation data; no replay, classifier or provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from taxonomy_discovery import coverage_presentation as coverage
from taxonomy_discovery import maintenance_service as maintenance

FIXTURE = Path(__file__).with_name("fixtures") / "confirmed_taxonomy_coverage.json"


class ConfirmedCoverageTests(unittest.TestCase):
    def setUp(self):
        # Real corpus reduced to native summary, source/weight identities and
        # existing semantic proofs; candidate evidence and research are omitted.
        self.receipt = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def view(self):
        return coverage.confirmed_coverage(self.receipt["snapshot"], self.receipt["plan"])

    def test_count_denominator_is_192_plus_two_not_raw_unresolved(self):
        v = self.view()
        self.assertEqual((v["numerator"], v["denominator"]), (192, 194))
        self.assertAlmostEqual(v["percentage"], 98.96907216494846)
        self.assertEqual(f"{v['percentage']:.0f}%", "99%")
        self.assertNotEqual(v["denominator"], 474)
        self.assertNotEqual(v["denominator"], 192 + 276)

    def test_raw_engineering_metrics_are_preserved(self):
        before = deepcopy(self.receipt)
        v = self.view()
        raw = v["raw_summary"]
        self.assertEqual(raw["required_core_weighted_coverage"]["percent"], 42.21)
        self.assertEqual(raw["overall_weighted_coverage"]["percent"], 42.18)
        self.assertEqual([raw[k] for k in ("meaningful_technical_requirements", "knowledge_resolved_requirements",
                                         "taxonomy_unresolved_requirements")], [474, 198, 276])
        self.assertEqual(self.receipt, before)

    def test_only_authoritative_nac_requirements_are_proven_gaps(self):
        rows = self.view()["proven_gaps"]
        self.assertEqual({(r["job_id"], r["requirement_id"]) for r in rows},
                         {(163, "req_2f6aedb603aa"), (163, "req_6677d37f660c")})
        self.assertTrue(all("network access control" in r["canonical_text"].lower() for r in rows))
        self.assertFalse(any("mongodb" in r["canonical_text"].lower() for r in rows))

    def test_non_gap_categories_cannot_enter_capability_discovery(self):
        v = self.view()
        self.assertEqual(v["breakdown"], {
            "Governed capability discovery / research": 2, "Technology identity workflow": 11,
            "Contextual relationship review": 9, "Structural backlog": 53,
            "No capability-discovery action": 6, "Deferred / needs review": 195})
        self.assertEqual(sum(r["capability_discovery_eligible"] for r in v["routes"]), 2)
        for r in v["routes"]:
            if r["lane"] != coverage.campaign.GAP:
                self.assertFalse(r["capability_discovery_eligible"])
        identity_ids = {r["requirement_id"] for r in self.receipt["snapshot"]["audit"]["requirements"]
                        if r["current_resolution"]["knowledge_status"] == "TECHNOLOGY_IDENTITY_RESOLVED"}
        self.assertEqual(len(identity_ids), 6)
        self.assertFalse(identity_ids.intersection(r["requirement_id"] for r in v["proven_gaps"]))

    def test_weighted_values_use_existing_authoritative_weights(self):
        v = self.view()
        overall = v["weighted"]["overall"]
        self.assertEqual(overall["numerator"], 478.437655)
        self.assertEqual(overall["denominator"], 478.437655 + 3.3)
        self.assertAlmostEqual(overall["percentage"], 99.31497985142971)
        self.assertAlmostEqual(v["weighted"]["required_core"]["percentage"], 99.29447630210572)

    def test_missing_native_weights_are_unavailable(self):
        s = self.receipt["snapshot"]
        s["audit"]["summary"].pop("capability_overall_weighted_coverage")
        maintenance._seal(s, "audit_fingerprint")
        a = self.receipt["plan"]["taxonomy_addressability"]
        a["audit_fingerprint"] = s["audit_fingerprint"]
        maintenance._seal(a, "addressability_fingerprint")
        self.assertIsNone(self.view()["weighted"]["overall"])

    def test_missing_stale_and_mismatched_accounting_fail_closed(self):
        self.assertIsNone(coverage.session_coverage({})[0])
        with patch.object(maintenance, "currentness", return_value={"current":False,"blockers":["stale"]}):
            self.assertIsNone(coverage.session_coverage({"tm_coverage_receipt":self.receipt})[0])
        self.receipt["plan"]["taxonomy_addressability"]["audit_fingerprint"] = "other"
        maintenance._seal(self.receipt["plan"]["taxonomy_addressability"], "addressability_fingerprint")
        with self.assertRaisesRegex(ValueError, "another audit"):
            self.view()

    def test_edited_or_unproven_semantic_claim_fails_closed(self):
        a = self.receipt["plan"]["taxonomy_addressability"]
        gap = next(r for r in a["rows"] if r["semantic_addressability"] == coverage.address.GAP)
        gap["proof"]["gap_contract"].pop("not_primary_relationship")
        maintenance._seal(a, "addressability_fingerprint")
        with self.assertRaisesRegex(ValueError, "proof contract"):
            self.view()

    def test_scores_rank_order_evidence_and_saved_identity_unchanged(self):
        before = deepcopy(self.receipt)
        before_ranks = sorted((j["baseline_stable_analysis"]["deterministic_alignment_score"], j["job_id"])
                              for j in before["snapshot"]["audit"]["corpus"]["jobs"])
        self.view()
        self.assertEqual(self.receipt, before)
        after_ranks = sorted((j["baseline_stable_analysis"]["deterministic_alignment_score"], j["job_id"])
                             for j in self.receipt["snapshot"]["audit"]["corpus"]["jobs"])
        self.assertEqual(before_ranks, after_ranks)

    def test_rerender_has_no_classifier_research_publication_or_replay(self):
        from taxonomy_discovery import taxonomy_addressability, governed_research, governed_publication
        code = '''import streamlit as st
from taxonomy_discovery.coverage_presentation import render_confirmed_coverage
st.metric("Job Match", "23/100")
render_confirmed_coverage(st, key="acceptance")
'''
        app = AppTest.from_string(code, default_timeout=30)
        app.session_state["tm_coverage_receipt"] = self.receipt
        with patch.object(maintenance, "currentness", return_value={"current":True,"blockers":[]}), \
                patch.object(taxonomy_addressability, "classify") as classify, \
                patch.object(maintenance, "run_corpus_audit") as audit, \
                patch.object(governed_research, "execute_plan") as research, \
                patch.object(governed_publication, "publish_approved_change") as publish:
            for _ in range(2):
                app.run()
                self.assertEqual(list(app.exception), [])
            metrics = {m.label:m.value for m in app.metric}
            self.assertEqual(metrics["Global confirmed taxonomy coverage"], "99%")
            self.assertEqual(metrics["Proven capability gaps"], "2")
            self.assertEqual(metrics["Raw unresolved"], "276")
            self.assertEqual(metrics["Required/core model-resolved requirement share"], "42.21%")
            self.assertTrue(any(e.label == "Advanced diagnostics — raw knowledge coverage" for e in app.expander))
            classify.assert_not_called(); audit.assert_not_called()
            research.assert_not_called(); publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
