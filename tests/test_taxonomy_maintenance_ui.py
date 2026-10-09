from contextlib import ExitStack
from copy import deepcopy
import os
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from taxonomy_discovery import maintenance_service as service
from tests.test_taxonomy_maintenance_service import fixture_corpus, capability_fields, legacy_attempt, seal_candidate
from tests.test_tqd3_governed_research import execute, fake_raw, fake_capability_raw
from database import taxonomy_discovery_review_manager as store
from tests.tqd3_publication_fixture_support import PublicationFixture

HARNESS = Path(__file__).with_name("taxonomy_maintenance_streamlit_harness.py")


class MaintenanceUITests(unittest.TestCase):
    def test_distinct_canonical_namespaces_have_distinguishable_read_only_options(self):
        self.corpus = fixture_corpus("network access control")
        db = self.fixture.tmp / "h1.sqlite"
        snapshot = service.run_corpus_audit(corpus=self.corpus, explicit_execution=True, review_db_path=db)
        for namespace in ("vendor.alpha", "vendor.beta"):
            c = deepcopy(snapshot["gap_rows"][0]["candidate"])
            c["technology_id"] = namespace
            c["provenance"][0]["job_content_hash"] = "distinct-source-" + namespace
            legacy_attempt(self.fixture, seal_candidate(c))
        self.stack.enter_context(patch.dict(os.environ, {"TAXONOMY_DISCOVERY_REVIEW_DB": str(db)}))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        self.assertEqual(list(app.exception), [])
        options = app.selectbox(key="tm_result").options
        self.assertEqual(len(options), 2)
        self.assertEqual(len(set(options)), 2)
        self.assertTrue(all("scope" in label for label in options))
        self.assertTrue(app.button(key="tm_refresh_saved").disabled)
        self.assertTrue(any("current candidate lineage" in item.value for item in app.warning))
        self.research.assert_not_called()
        self.publish.assert_not_called()

    def test_old_version_attempts_have_one_primary_and_refresh_current_gap_without_provider(self):
        self.corpus = fixture_corpus("network access control")
        db = self.fixture.tmp / "h1.sqlite"
        snapshot = service.run_corpus_audit(corpus=self.corpus, explicit_execution=True, review_db_path=db)
        c = snapshot["gap_rows"][0]["candidate"]
        for i in range(3):
            legacy_attempt(self.fixture, c, research_round=i)
        self.stack.enter_context(patch.dict(os.environ, {"TAXONOMY_DISCOVERY_REVIEW_DB": str(db)}))
        provider = self.stack.enter_context(patch.object(service.research, "tavily_transport", side_effect=AssertionError("No provider on refresh")))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        app.button(key="tm_build_tranche").click().run()
        current = app.session_state["tm_tranche"]["targets"][0]["candidate_id"]
        app.multiselect(key="tm_research_ids").set_value([current]).run()
        app.button(key="tm_plan").click().run()
        self.assertEqual(list(app.exception), [])
        plan = app.session_state["tm_plan_receipt"]
        self.assertEqual(plan["planned_tavily_calls"], 0)
        self.assertEqual(plan["execution_targets"], [])
        self.assertTrue(any("No provider execution is planned" in item.value for item in app.info))
        self.assertTrue(app.button(key="tm_research").disabled)
        self.assertEqual(len(app.selectbox(key="tm_result").options), 1)
        self.assertIn("3 historical attempts", app.selectbox(key="tm_result").options[0])
        self.assertTrue(any("Historical attempts (3)" in item.label for item in app.expander))
        app.button(key="tm_refresh_saved").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertFalse(any("Candidate knowledge versions changed" in item.value for item in app.error))
        self.assertEqual(len(app.selectbox(key="tm_result").options), 1)
        self.assertEqual(app.selectbox(key="tm_result").value, app.session_state["tm_new_results"][0])
        saved = store.list_governed_research_results(db_path=db)
        self.assertEqual(len(saved), 4)
        self.assertTrue(all(row["draft"] is None and row["review"]["decision"] == "undecided" for row in saved))
        app.run()
        self.assertEqual(len(store.list_governed_research_results(db_path=db)), 4)
        provider.assert_not_called()
        self.research.assert_not_called()
        self.publish.assert_not_called()
        self.fixture.network_guard.assert_not_called()
        self.fixture.model_guard.assert_not_called()

    def test_pre_v2_refresh_removes_stale_zero_call_preview(self):
        from tests.test_tqd3_refresh_planner_handoff import RefreshPlannerHandoffTests
        self.corpus = fixture_corpus("cloud security")
        snapshot, c, old = RefreshPlannerHandoffTests().seed(self.fixture)
        db = self.fixture.tmp / "h1.sqlite"
        self.stack.enter_context(patch.dict(os.environ, {"TAXONOMY_DISCOVERY_REVIEW_DB": str(db)}))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        app.button(key="tm_build_tranche").click().run()
        app.multiselect(key="tm_research_ids").set_value([c["candidate_id"]]).run()
        app.button(key="tm_plan").click().run()
        self.assertEqual(app.session_state["tm_plan_receipt"]["planned_tavily_calls"], 0)
        self.assertTrue(any("Refresh existing saved evidence" in item.value for item in app.info))
        app.button(key="tm_refresh_saved").click().run()
        app.button(key="tm_plan").click().run()
        self.assertEqual(list(app.exception), [])
        plan = app.session_state["tm_plan_receipt"]
        self.assertEqual(plan["planned_tavily_calls"], 1)
        self.assertEqual(plan["execution_preview"][0]["execution_status"], "READY TO EXECUTE")
        self.assertFalse(any("Refresh existing saved evidence" in item.value for item in app.info))
        groups = service.build_review_targets(app.session_state["tm_snapshot"],
            saved_rows=store.list_governed_research_results(db_path=db))
        self.assertEqual(groups[0]["primary"]["result"]["research_result_id"], app.session_state["tm_new_results"][0])
        self.research.assert_not_called()
        self.publish.assert_not_called()
        self.fixture.network_guard.assert_not_called()
        self.fixture.model_guard.assert_not_called()

    def test_gap_assistant_first_press_is_dry_run_and_reuses_current_audit(self):
        from taxonomy_discovery import gap_reduction_assistant as assistant
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.audit.assert_not_called()
        with patch.object(assistant, "build_plan", wraps=assistant.build_plan) as shared:
            app.button(key="tm_gap_run").click().run()
            self.assertEqual(list(app.exception), [])
            shared.assert_called_once()
        plan = app.session_state["tm_gap_plan"]
        self.assertEqual(plan["provider_calls"], 0)
        self.assertTrue(app.button(key="tm_gap_execute").disabled)
        self.assertEqual(self.audit.call_count, 1)
        app.button(key="tm_gap_run").click().run()
        app.run()
        self.assertEqual(self.audit.call_count, 1)
        self.assertEqual(app.session_state["tm_gap_plan"], plan)
        for label in ("RELATIONSHIP WORK", "DEPENDENCY BUNDLES", "DECOMPOSITION / PARSER BOTTLENECKS", "DEFERRED"):
            self.assertTrue(any(label in exp.label for exp in app.expander), label)
        self.assertTrue(any("FOUNDATIONAL ACTIONS" in element.value for element in app.markdown))
        self.assertTrue(any("DIRECT GAP-REDUCTION ACTIONS" in element.value for element in app.markdown))
        self.assertTrue(any("Foundational ≠ directly resolving" in element.value for element in app.caption))
        self.assertIn("dependency_ids", plan["all_actions"][0])
        app.number_input(key="tm_gap_budget").set_value(0).run()
        self.assertTrue(app.button(key="tm_gap_execute").disabled)
        self.assertTrue(any("inputs changed" in warning.value for warning in app.warning))
        self.research.assert_not_called(); self.publish.assert_not_called()
        self.fixture.network_guard.assert_not_called(); self.fixture.model_guard.assert_not_called()

    def test_running_audit_is_disabled_and_not_reentered(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        label = "Running deterministic corpus audit… No model or external research calls are being made."
        app.session_state["tm_running_" + label] = True
        app.run()
        self.assertTrue(app.button(key="tm_audit").disabled)
        self.audit.assert_not_called()

    def test_stale_saved_evidence_refresh_is_explicit_local_and_unapproved(self):
        self.corpus = fixture_corpus("crystalline computing protocols")
        snapshot = service.run_corpus_audit(corpus=self.corpus, explicit_execution=True,
            review_db_path=self.fixture.tmp / "h1.sqlite")
        c = snapshot["gap_rows"][0]["candidate"]
        result = execute(self.fixture, c, fake_raw(c["concept_key"]))
        authority = Path(result["authority_registry_path"])
        raw = json.loads(authority.read_text())
        raw["version"] = "new-test-version"
        authority.write_text(json.dumps(raw))
        self.stack.enter_context(patch.dict(os.environ, {"TAXONOMY_DISCOVERY_REVIEW_DB": str(self.fixture.tmp / "h1.sqlite")}))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        self.assertIn("STALE / REFRESH REQUIRED", app.selectbox(key="tm_result").options[0])
        app.button(key="tm_refresh_saved").click().run()
        self.assertEqual(list(app.exception), [])
        saved = store.list_governed_research_results(db_path=self.fixture.tmp / "h1.sqlite")
        self.assertEqual(len(saved), 2)
        rid = app.session_state["tm_new_results"][0]
        self.assertEqual(app.selectbox(key="tm_result").value, rid)
        refreshed = next(row for row in saved if row["result"]["research_result_id"] == rid)
        self.assertEqual(refreshed["result"]["provider_request_id"], result["provider_request_id"])
        self.assertFalse(refreshed["draft"])
        self.assertFalse(refreshed["result"]["approval"])
        self.research.assert_not_called()
        self.publish.assert_not_called()
        self.fixture.network_guard.assert_not_called()

    def test_audit_completion_deduplicates_double_click_and_rerender(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any("Audit complete" in item.value for item in app.success))
        self.assertTrue(any("Running deterministic corpus audit" in item.label for item in app.status))
        app.button(key="tm_audit").click().run()
        app.run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(self.audit.call_count, 1)
        self.research.assert_not_called()

    def test_excluded_candidates_are_inspectable_and_bulk_routing_stays_local(self):
        self.corpus = fixture_corpus("distributed systems", "critical infrastructure security implement robust security protocols to protect national infrastructure")
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        app.button(key="tm_build_tranche").click().run()
        self.assertEqual(list(app.exception), [])
        tranche = app.session_state["tm_tranche"]
        self.assertEqual(len(tranche["excluded_targets"]), 1)
        self.assertTrue(any("Excluded candidates" in item.label for item in app.expander))
        cid = tranche["targets"][0]["candidate_id"]
        app.multiselect(key="tm_route_ids").set_value([cid]).run()
        app.button(key="tm_route_" + service.REVIEW_FIX_LAYER).click().run()
        app.button(key="tm_build_tranche").click().run()
        self.assertEqual(app.session_state["tm_tranche"]["targets"], [])
        self.assertFalse((self.fixture.tmp / "missing.sqlite").exists())
        self.research.assert_not_called()
        self.publish.assert_not_called()

    def test_unavailable_provider_disables_confirmed_research(self):
        self.stack.enter_context(patch.dict(os.environ, {"TAVILY_API_KEY": ""}))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        app.button(key="tm_build_tranche").click().run()
        cid = app.session_state["tm_tranche"]["targets"][0]["candidate_id"]
        app.multiselect(key="tm_research_ids").set_value([cid]).run()
        app.button(key="tm_plan").click().run()
        plan = app.session_state["tm_plan_receipt"]
        app.checkbox(key="tm_confirm_research_" + plan["plan_fingerprint"]).check().run()
        self.assertTrue(app.button(key="tm_research").disabled)
        self.assertTrue(any("TAVILY_API_KEY" in item.value for item in app.warning))
        self.research.assert_not_called()

    def test_successful_explicit_fake_research_is_selected_in_human_review(self):
        self.corpus = fixture_corpus("data analysis and insights")
        self.stack.enter_context(patch.dict(os.environ, {"TAVILY_API_KEY": "fake-test-key"}))
        # Preserve the native executor; replace only the provider transport.
        # Original callable is captured explicitly in setUp, before patching.
        self.research.side_effect = self.real_execute
        provider = self.stack.enter_context(patch.object(service.research, "tavily_transport", return_value=fake_raw("data analysis and insights")))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        app.button(key="tm_build_tranche").click().run()
        cid = app.session_state["tm_tranche"]["targets"][0]["candidate_id"]
        app.multiselect(key="tm_research_ids").set_value([cid]).run()
        app.button(key="tm_plan").click().run()
        self.assertTrue(app.button(key="tm_research").disabled)
        plan = app.session_state["tm_plan_receipt"]
        self.assertEqual(plan["planned_tavily_calls"], 1)
        app.checkbox(key="tm_confirm_research_" + plan["plan_fingerprint"]).check().run()
        self.assertFalse(app.button(key="tm_research").disabled)
        provider.assert_not_called()
        app.button(key="tm_research").click().run()
        self.assertEqual(list(app.exception), [])
        receipt = app.session_state["tm_research_receipt"]
        self.assertEqual(receipt["candidates_completed"], 1)
        rid = receipt["outcomes"][cid]["research_result_id"]
        self.assertEqual(app.selectbox(key="tm_result").value, rid)
        self.assertIn("data analysis and insights", app.selectbox(key="tm_result").options[0])
        self.assertTrue(any("Research complete" in item.value for item in app.success))
        app.run()
        provider.assert_called_once()
        self.publish.assert_not_called()
        saved = store.list_governed_research_results(db_path=self.fixture.tmp / "missing.sqlite")
        self.assertFalse(saved[0]["draft"])
        self.assertEqual(saved[0]["result"]["support_bundle"]["outcome"], "research_more")
        self.assertTrue(app.button(key="tm_draft").disabled)
        self.assertTrue(any("exact support text" in exp.label for exp in app.expander))
        self.assertFalse(saved[0]["result"]["approval"])
        self.fixture.network_guard.assert_not_called()
        self.fixture.model_guard.assert_not_called()

    def test_explicit_research_failure_has_visible_error_and_receipt(self):
        self.stack.enter_context(patch.dict(os.environ, {"TAVILY_API_KEY": "fake-test-key"}))
        self.research.side_effect = self.real_execute
        self.stack.enter_context(patch.object(service.research, "tavily_transport", side_effect=RuntimeError("Fake provider failed")))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        app.button(key="tm_build_tranche").click().run()
        cid = app.session_state["tm_tranche"]["targets"][0]["candidate_id"]
        app.multiselect(key="tm_research_ids").set_value([cid]).run()
        app.button(key="tm_plan").click().run()
        plan = app.session_state["tm_plan_receipt"]
        app.checkbox(key="tm_confirm_research_" + plan["plan_fingerprint"]).check().run()
        app.button(key="tm_research").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any("Research failed" in item.value for item in app.error))
        self.assertEqual(app.session_state["tm_research_receipt"]["candidates_failed"], 1)
        self.assertEqual(store.list_governed_research_results(db_path=self.fixture.tmp / "missing.sqlite"), [])
        self.publish.assert_not_called()

    def setUp(self):
        # PublicationFixture restores sys.modules after its fake llm injection.
        # Load Streamlit's binary dataframe dependencies before that snapshot;
        # NumPy extensions cannot be reimported after module-cache rollback.
        __import__("numpy")
        __import__("pandas")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fixture = self.stack.enter_context(PublicationFixture())
        self.stack.enter_context(patch.dict(os.environ, {
            "TAXONOMY_DISCOVERY_REVIEW_DB": str(self.fixture.tmp / "missing.sqlite")}))
        self.corpus = fixture_corpus("distributed systems", "Python", "BigFix", "React")
        self.stack.enter_context(patch.object(service, "export_saved_corpus", side_effect=lambda **kw: deepcopy(self.corpus)))
        self.audit = self.stack.enter_context(patch.object(service, "run_corpus_audit", wraps=service.run_corpus_audit))
        self.real_execute = service.execute_research
        self.research = self.stack.enter_context(patch.object(service, "execute_research", side_effect=AssertionError("No research on rerender")))
        self.publish = self.stack.enter_context(patch.object(service, "publish_validated", side_effect=AssertionError("No publication on rerender")))

    def test_page_load_audit_filter_tranche_detail_and_export_are_offline(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        self.audit.assert_not_called()
        app.button(key="tm_audit").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(self.audit.call_count, 1)
        app.selectbox(key="tm_layer").select(service.CAPABILITY_GAP).run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(app.selectbox(key="tm_detail").options)
        app.button(key="tm_build_tranche").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(app.session_state["tm_tranche"]["targets"])
        app.button(key="tm_export_button").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(app.session_state["tm_export"]["zip"])
        self.assertEqual(self.audit.call_count, 1)
        self.research.assert_not_called()
        self.publish.assert_not_called()
        self.assertFalse((self.fixture.tmp / "missing.sqlite").exists())
        self.fixture.network_guard.assert_not_called()
        self.fixture.model_guard.assert_not_called()

    def test_selected_research_needs_exact_plan_and_confirmation(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        app.button(key="tm_build_tranche").click().run()
        cid = app.session_state["tm_tranche"]["targets"][0]["candidate_id"]
        app.multiselect(key="tm_research_ids").set_value([cid]).run()
        self.assertTrue(app.button(key="tm_research").disabled)
        app.button(key="tm_plan").click().run()
        self.assertEqual(list(app.exception), [])
        plan = app.session_state["tm_plan_receipt"]
        self.assertEqual(plan["selected_candidate_ids"], [cid])
        self.assertTrue(app.button(key="tm_research").disabled)
        self.research.assert_not_called()

    def test_navigation_is_secondary_and_job_match_dispatch_unchanged(self):
        source = (HARNESS.parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('elif page == "Taxonomy Maintenance":\n    render_taxonomy_maintenance()', source)
        self.assertIn('elif page == "Capability Discovery":\n    render_capability_discovery_review()', source)
        self.assertIn('"Job Market Insights",\n            "Taxonomy Maintenance",', source)

    def test_review_approval_validation_and_publication_are_separate_actions(self):
        self.corpus = fixture_corpus("crystalline computing protocols")
        snapshot = service.run_corpus_audit(corpus=self.corpus, explicit_execution=True,
            review_db_path=self.fixture.tmp / "missing.sqlite")
        c = snapshot["gap_rows"][0]["candidate"]
        result = execute(self.fixture, c, fake_capability_raw(c["concept_key"]))
        draft = service.research.create_draft(result, explicit_creation=True,
            capability_fields=capability_fields(c["concept_key"]))
        store.save_governed_research_draft(result, draft, db_path=self.fixture.tmp / "h1.sqlite",
            proposal_db_path=self.fixture.proposal_db)
        self.stack.enter_context(patch.dict(os.environ, {
            "TAXONOMY_DISCOVERY_REVIEW_DB": str(self.fixture.tmp / "h1.sqlite")}))
        app = AppTest.from_file(str(HARNESS), default_timeout=30).run()
        app.button(key="tm_audit").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(app.button(key="tm_validate").disabled)
        app.button(key="tm_review_preview_button").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertFalse(app.session_state["tm_review_preview"]["approved_validation"])
        app.selectbox(key="tm_decision").select("approve_for_publication")
        app.text_input(key="tm_reviewer").set_value("fixture human")
        app.button(key="tm_save_review").click().run()
        self.assertEqual(list(app.exception), [])
        rid = result["research_result_id"]
        app.multiselect(key="tm_validate_results").set_value([rid]).run()
        app.button(key="tm_validate").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(app.session_state["tm_validation"]["approved_validation"])
        self.assertTrue(app.button(key="tm_publish").disabled)
        self.publish.assert_not_called()
        self.research.assert_not_called()


if __name__ == "__main__":
    unittest.main()
