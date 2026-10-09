"""Persisted interpretation selection; fake transports and temporary stores only."""
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch
from database import taxonomy_discovery_review_manager as store
from taxonomy_discovery import governed_research as g, maintenance_service as service
from taxonomy_discovery import bulk_candidate_operations as bulk
from taxonomy_discovery.corpus_expansion import fingerprint
from tests.test_taxonomy_maintenance_service import fixture_corpus, seal_candidate
from tests.test_tqd3_governed_research import execute, fake_raw
from tests.tqd3_publication_fixture_support import PublicationFixture


def reseal(result):
    result.pop("research_result_id", None)
    result.pop("result_fingerprint", None)
    result["result_fingerprint"] = fingerprint(result)
    result["research_result_id"] = "tqd3h1_" + result["result_fingerprint"][:24]
    return result


class RefreshPlannerHandoffTests(unittest.TestCase):
    def seed(self, f):
        snapshot = service.run_corpus_audit(corpus=fixture_corpus("cloud security"),
            review_db_path=f.tmp / "h1.sqlite", explicit_execution=True)
        c = snapshot["gap_rows"][0]["candidate"]
        with patch.object(g, "INTERPRETATION_VERSION", "historical-pre-v2"):
            old = execute(f, c, fake_raw("cloud security", "Cloud security references NIST SP 800-144."))
        return snapshot, c, old

    def test_refresh_handoff_preserves_history_and_plans_one_native_call(self):
        with PublicationFixture() as f:
            snapshot, c, old = self.seed(f)
            db = f.tmp / "h1.sqlite"
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            provider = Mock(side_effect=AssertionError("No provider execution"))
            before = store.list_governed_research_results(db_path=db)
            preview = service.plan_research(snapshot, tranche, [c["candidate_id"]], transport=provider, review_db_path=db)
            self.assertEqual(preview["execution_preview"][0]["execution_status"], "EXISTING RESEARCH / REFRESH REQUIRED")
            with patch.object(g, "tavily_transport", provider):
                refreshed = service.refresh_saved_research(snapshot, c["candidate_id"], explicit_execution=True, review_db_path=db)
            after = store.list_governed_research_results(db_path=db)
            self.assertIn(before[0], after)
            self.assertEqual(len(after), 2)
            selected = g.select_saved_interpretation(c, after)
            self.assertTrue(selected["current"])
            self.assertEqual(selected["primary"]["result"], refreshed)
            self.assertEqual(service.build_review_targets(snapshot, saved_rows=after)[0]["primary"], selected["primary"])
            self.assertEqual(bulk._latest_saved(c, after)[0], selected["primary"])
            self.assertEqual(refreshed["executed_at"], old["executed_at"])
            self.assertEqual(refreshed["research"]["raw_provider_evidence"], old["research"]["raw_provider_evidence"])
            preview = service.plan_research(snapshot, tranche, [c["candidate_id"]], transport=provider, review_db_path=db)
            self.assertEqual(preview["execution_preview"][0]["execution_status"], "READY TO EXECUTE")
            self.assertEqual(preview["planned_tavily_calls"], 1)
            self.assertEqual(refreshed["recommended_next_action"], "research_more")
            self.assertTrue(all(not r["draft"] and r["review"]["decision"] == "undecided" for r in after))
            self.assertFalse(refreshed["approval"])
            provider.assert_not_called()
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_newer_incompatible_cannot_override_current(self):
        with PublicationFixture() as f:
            snapshot, c, old = self.seed(f)
            current = g.re_evaluate_saved_evidence(old, explicit_execution=True, persist=False)
            other = deepcopy(current)
            other["candidate"]["technology_id"] = "other.namespace"
            seal_candidate(other["candidate"])
            other["candidate_fingerprint"] = other["candidate"]["candidate_fingerprint"]
            other["re_evaluated_at"] = "2099-01-01T00:00:00+00:00"
            reseal(other)
            rows = [{"result": other}, {"result": current}]
            self.assertEqual(g.select_saved_interpretation(c, rows)["primary"]["result"], current)

    def test_latest_current_wins_and_equal_unrelated_interpretations_fail_closed(self):
        with PublicationFixture() as f:
            snapshot, c, old = self.seed(f)
            current = g.re_evaluate_saved_evidence(old, explicit_execution=True, persist=False)
            newer = deepcopy(current)
            newer["re_evaluated_at"] = "2099-01-01T00:00:00+00:00"
            reseal(newer)
            rows = [{"result": current}, {"result": newer}]
            self.assertEqual(g.select_saved_interpretation(c, rows)["primary"]["result"], newer)
            competing = deepcopy(newer)
            competing["interpretation_lineage"]["previous_research_result_id"] = "different-predecessor"
            reseal(competing)
            rows = [{"result": newer}, {"result": competing}]
            selection = g.select_saved_interpretation(c, rows)
            self.assertTrue(selection["ambiguous"])
            self.assertIsNone(selection["primary"])
            self.assertEqual(bulk._latest_saved(c, rows), (None, None))
            groups = service.build_review_targets(snapshot, saved_rows=rows)
            self.assertTrue(groups[0]["binding_blocker"])
            self.assertEqual(groups[0]["status"], "STALE / REFRESH REQUIRED")

    def test_historical_exhausted_round_cannot_be_reset_by_refresh(self):
        with PublicationFixture() as f:
            snapshot, c, old = self.seed(f)
            current = g.re_evaluate_saved_evidence(old, explicit_execution=True, persist=False)
            exhausted = deepcopy(old)
            exhausted["research"]["target"]["research_round"] = 2
            reseal(exhausted)
            rows = [{"result": current}, {"result": exhausted}]
            self.assertIsNone(bulk._research_round({"candidate": c, "research_status": "research_more_required"}, rows))

    def test_corrupt_compatible_history_cannot_enable_fresh_research(self):
        with PublicationFixture() as f:
            snapshot, c, old = self.seed(f)
            old["interpretation_version"] = g.INTERPRETATION_VERSION
            selection = g.select_saved_interpretation(c, [{"result": old}])
            self.assertIsNone(selection["primary"])
            self.assertTrue(selection["ambiguous"])
            queue = bulk.build_candidate_queue([c], saved_rows=[{"result": old}], publications=[])
            self.assertEqual(queue["rows"][0]["research_status"], "blocked")
            self.assertFalse(queue["rows"][0]["external_research_required"])
