"""Native audits, fake providers, exact plans, and temporary fixtures only."""
from copy import deepcopy
from pathlib import Path
from contextlib import ExitStack
import json
import os
import unittest
from unittest.mock import Mock, patch
from taxonomy_discovery import gap_reduction_assistant as a, maintenance_service as m
from taxonomy_discovery.corpus_expansion import fingerprint
from tests.test_taxonomy_maintenance_service import fixture_corpus, capability_fields
from tests.test_tqd3_governed_research import execute, fake_raw, fake_capability_raw, rules
from tests.test_tqd3_refresh_planner_handoff import reseal
from tests.tqd3_publication_fixture_support import PublicationFixture
from database import taxonomy_discovery_review_manager as store


class GapReductionAssistantTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.f = self.stack.enter_context(PublicationFixture())
        self.db = self.f.tmp / "h1.sqlite"
        self.snapshot = m.run_corpus_audit(corpus=fixture_corpus("crystalline computing protocols", "Python", "BigFix", "React"),
            review_db_path=self.db, explicit_execution=True)
        self.c = next(r["candidate"] for r in self.snapshot["gap_rows"] if r["fix_layer"] == m.CAPABILITY_GAP)

    def plan(self, **kwargs):
        return a.build_plan(self.snapshot, review_db_path=self.db, transport=Mock(), **kwargs)

    def test_native_audit_multiple_layers_order_and_no_side_effects(self):
        with patch.object(m, "run_corpus_audit", side_effect=AssertionError("No replay")):
            first = self.plan()
            self.assertEqual(first, self.plan())
        self.assertEqual(first["audit_fingerprint"], self.snapshot["audit_fingerprint"])
        self.assertEqual(first["baseline"]["unresolved"], 3)
        self.assertEqual(len(first["unresolved_requirement_routing"]), 3)
        self.assertEqual(first["unrouted_unresolved_requirement_keys"], [])
        self.assertGreater(len(first["routing_summary"]), 1)
        self.assertFalse(first["potential_gap_delta"]["validated"])
        self.assertIsNone(first["potential_gap_delta"]["newly_resolved"])
        self.assertFalse(first["automatic_approval"])
        self.assertFalse(first["automatic_publication"])
        self.assertEqual(first["production_writes"], 0)
        self.assertEqual(store.list_governed_research_results(db_path=self.db), [])
        self.f.network_guard.assert_not_called(); self.f.model_guard.assert_not_called()
        self.assertEqual(self.f.real_registry.read_bytes(), self.f.real_registry_bytes)

    def test_required_multijob_local_issue_outranks_research_ready(self):
        rows = deepcopy(self.snapshot["gap_rows"])
        tech = next(r for r in rows if r["fix_layer"] == m.IDENTITY_GAP)
        cap = next(r for r in rows if r["fix_layer"] == m.CAPABILITY_GAP)
        cap["requirements"][0]["importance"] = "preferred"
        tech["requirements"] = [dict(tech["requirements"][0], job_id=i, requirement_id="fixture"+str(i), importance="required") for i in range(8)]
        with patch.object(m, "list_gap_rows", return_value=rows):
            p = self.plan()
        top = p["ranked_actions"][0]
        self.assertEqual(top["candidate_id"], tech["candidate_id"])
        self.assertEqual(top["jobs_affected"], 8)
        self.assertGreater(top["required_core_weight"], 0)
        low = next(x for x in p["all_actions"] if x["candidate_id"] == self.c["candidate_id"])
        self.assertEqual(low["research_state"], "DEFERRED")
        self.assertEqual(low["provider_calls_required"], 0)

    def test_technology_and_native_decomposition_never_enter_capability_research(self):
        rows = deepcopy(self.snapshot["gap_rows"])
        row = next(r for r in rows if r["fix_layer"] == m.CAPABILITY_GAP)
        row["boundary_state"] = m.NEEDS_DECOMPOSITION
        with patch.object(m, "list_gap_rows", return_value=rows):
            p = self.plan()
        self.assertEqual(p["planned_external_calls"], 0)
        self.assertTrue(any(x["research_state"] == m.NEEDS_DECOMPOSITION for x in p["all_actions"]))
        self.assertTrue(all(x["provider_calls_required"] == 0 for x in p["all_actions"]))

    def test_budget_zero_and_maximum_limits(self):
        p = self.plan(research_budget=0)
        self.assertEqual(p["planned_external_calls"], 0)
        self.assertIsNone(p["research_plan"])
        self.assertLessEqual(self.plan(research_budget=1)["planned_external_calls"], 1)
        for kwargs in ({"research_budget":21}, {"research_budget":-1}, {"max_actions":26}):
            with self.assertRaises(ValueError): self.plan(**kwargs)

    def test_exact_plan_confirmation_and_saved_state_invalidation(self):
        p = self.plan(research_budget=0)
        for token in (None, "wrong"):
            with self.assertRaisesRegex(ValueError, "exact assistant"):
                a.execute_plan(self.snapshot,p,confirmed_fingerprint=token,explicit_execution=True,review_db_path=self.db,transport=Mock())
        execute(self.f, self.c, fake_raw(self.c["concept_key"]))
        with self.assertRaisesRegex(ValueError, "changed"):
            a.execute_plan(self.snapshot,p,confirmed_fingerprint=p["assistant_plan_fingerprint"],explicit_execution=True,review_db_path=self.db,transport=Mock())

    def test_stale_audit_fails_closed(self):
        altered = deepcopy(self.snapshot)
        altered["manifest"]["scoring_version"] = "old"
        m._seal(altered,"audit_fingerprint")
        with self.assertRaisesRegex(ValueError,"STALE"):
            a.build_plan(altered, review_db_path=self.db)

    def test_current_partial_support_needs_scope_refinement(self):
        raw = fake_raw(self.c["concept_key"], self.c["concept_key"] + " engineers implement protocols. Documented protocol configuration was implemented and validated.")
        raw["results"][0]["raw_content"] = raw["results"][0]["content"]
        execute(self.f,self.c,raw)
        p=self.plan()
        item=next(x for x in p["all_actions"] if x["candidate_id"]==self.c["candidate_id"])
        self.assertEqual(item["research_state"],"NEEDS_SCOPE_REFINEMENT")
        self.assertTrue(item["supported_semantic_fields"])
        self.assertEqual(p["planned_external_calls"],0)

    def test_repeated_unchanged_deficiencies_stop_and_do_not_count_refresh_as_call(self):
        result=execute(self.f,self.c,fake_raw(self.c["concept_key"]))
        native=m.research.research_plan([self.c],selected_candidate_ids=[self.c["candidate_id"]],research_round=1)
        receipt=m.research.execute_plan(native,[self.c],explicit_execution=True,
            transport=Mock(return_value=fake_raw(self.c["concept_key"],request_id="second-request")),
            db_path=self.db,authority_registry_path=rules(self.f,[self.c["concept_key"]]))
        self.assertFalse(receipt["failures"])
        second=receipt["results"][0]
        authority=Path(second["authority_registry_path"])
        value=json.loads(authority.read_text());value["version"]="refreshed-policy"
        authority.write_text(json.dumps(value))
        refreshed=m.research.re_evaluate_saved_evidence(second,explicit_execution=True,persist=True,db_path=self.db)
        p=self.plan()
        item=next(x for x in p["all_actions"] if x["candidate_id"]==self.c["candidate_id"])
        self.assertEqual(item["calls_used"],2)
        self.assertEqual(item["calls_remaining"],1)
        self.assertEqual(item["research_state"],"NEEDS_SCOPE_REFINEMENT")
        self.assertEqual(item["new_support_gained"],[])

    def test_exhausted_round_is_terminal(self):
        native=m.research.research_plan([self.c],selected_candidate_ids=[self.c["candidate_id"]],research_round=2)
        receipt=m.research.execute_plan(native,[self.c],explicit_execution=True,
            transport=Mock(return_value=fake_raw(self.c["concept_key"])),db_path=self.db,
            authority_registry_path=rules(self.f,[self.c["concept_key"]]))
        self.assertFalse(receipt["failures"])
        item=next(x for x in self.plan()["all_actions"] if x["candidate_id"]==self.c["candidate_id"])
        self.assertEqual(item["research_state"],"RESEARCH_EXHAUSTED")
        self.assertEqual(item["calls_remaining"],0)

    def test_local_refresh_is_explicit_offline_and_requires_repreview(self):
        with patch.object(m.research,"INTERPRETATION_VERSION","old"):
            execute(self.f,self.c,fake_raw(self.c["concept_key"]))
        p=self.plan(research_budget=0)
        self.assertTrue(any(x["local_action_available"] for x in p["ranked_actions"]))
        provider=Mock(side_effect=AssertionError("no calls"))
        receipt=a.execute_plan(self.snapshot,p,explicit_execution=True,confirmed_fingerprint=p["assistant_plan_fingerprint"],review_db_path=self.db,transport=provider)
        self.assertEqual(len(receipt["local_refreshes"]),1)
        provider.assert_not_called()
        self.assertEqual(receipt["drafts_created"],0)
        self.assertTrue(all(not row["draft"] and row["review"]["decision"]=="undecided" for row in store.list_governed_research_results(db_path=self.db)))
        with self.assertRaisesRegex(ValueError,"changed"):
            a.validate_plan(self.snapshot,p,p["assistant_plan_fingerprint"],review_db_path=self.db,transport=provider)

    def test_research_requires_separate_authorization_and_native_executor(self):
        provider=Mock(return_value=fake_raw(self.c["concept_key"]))
        p=self.plan()
        self.assertEqual(p["planned_external_calls"],1)
        with self.assertRaisesRegex(ValueError,"external-research"):
            a.execute_plan(self.snapshot,p,explicit_execution=True,confirmed_fingerprint=p["assistant_plan_fingerprint"],review_db_path=self.db,transport=provider)
        with patch.object(m,"execute_research",wraps=m.execute_research) as native:
            receipt=a.execute_plan(self.snapshot,p,explicit_execution=True,allow_external_research=True,
                confirmed_fingerprint=p["assistant_plan_fingerprint"],review_db_path=self.db,transport=provider)
            native.assert_called_once()
        self.assertEqual(receipt["research"]["calls_attempted"],1)
        self.assertEqual(receipt["drafts_created"],0)

    def test_overlay_validation_reuses_native_unapproved_preview(self):
        result=execute(self.f,self.c,fake_capability_raw(self.c["concept_key"]))
        draft=m.research.create_draft(result,explicit_creation=True,capability_fields=capability_fields(self.c["concept_key"]))
        store.save_governed_research_draft(result,draft,db_path=self.db,proposal_db_path=self.f.proposal_db)
        p=self.plan()
        with patch.object(m,"run_candidate_validation",wraps=m.run_candidate_validation) as native:
            receipt=a.validate_drafts(self.snapshot,p,[result["research_result_id"]],explicit_execution=True,
                confirmed_fingerprint=p["assistant_plan_fingerprint"],review_db_path=self.db)
            self.assertFalse(native.call_args.kwargs["approved"])
        self.assertFalse(receipt["approved_validation"])
        self.assertEqual(receipt["production_writes"],0)

    def test_cli_calls_shared_service_and_writes_portable_report(self):
        from scripts.run_taxonomy_gap_reduction import main
        path=self.f.tmp/"audit.json"
        path.write_text(json.dumps(self.snapshot),encoding="utf-8")
        with patch.dict(os.environ,{"TAXONOMY_DISCOVERY_REVIEW_DB":str(self.db)}), patch.object(a,"build_plan",wraps=a.build_plan) as shared:
            self.assertEqual(main(["--scope","frozen","--audit",str(path),"--dry-run","--research-budget","0","--output",str(self.f.tmp/"out")]),0)
            shared.assert_called_once()
        self.assertTrue((self.f.tmp/"out"/"summary.md").exists())
        self.assertEqual(json.loads((self.f.tmp/"out"/"plan.json").read_text())["provider_calls"],0)

    def test_atomic_technology_child_retains_native_identity_route(self):
        rows = deepcopy(self.snapshot["gap_rows"])
        row = next(r for r in rows if r["fix_layer"] == m.IDENTITY_GAP)
        row["parent_candidate_id"] = "native-parent"
        with patch.object(m,"list_gap_rows",return_value=rows):
            item = next(x for x in self.plan()["all_actions"] if x["candidate_id"] == row["candidate_id"])
        self.assertEqual(item["research_state"],"FIX_LAYER_REQUIRED")
        self.assertEqual(item["fix_layer"],m.IDENTITY_GAP)
        self.assertEqual(item["provider_calls_required"],0)

    def test_identical_native_next_query_does_not_spend_remaining_budget(self):
        result=execute(self.f,self.c,fake_raw(self.c["concept_key"]))
        query=result["research"]["target"]["questions"][0]
        fake={"execution_targets":[{"external":True,"planned_query":query,"planned_tavily_calls":1}]}
        with patch.object(a.bulk,"prepare_bulk_plan",return_value=fake):
            item=next(x for x in self.plan()["all_actions"] if x["candidate_id"]==self.c["candidate_id"])
        self.assertEqual(item["research_state"],"RESEARCH_EXHAUSTED")
        self.assertGreater(item["calls_remaining"],0)
        self.assertEqual(item["provider_calls_required"],0)

    def test_noise_has_no_estimated_technical_weight(self):
        rows=deepcopy(self.snapshot["gap_rows"])
        row=next(r for r in rows if r["fix_layer"]==m.IDENTITY_GAP)
        row["fix_layer"]=m.NOISE
        with patch.object(m,"list_gap_rows",return_value=rows):
            item=next(x for x in self.plan()["all_actions"] if x["candidate_id"]==row["candidate_id"])
        self.assertEqual(item["weighted_impact"],0)
        self.assertEqual(item["meaningful_technical_requirements_affected"],0)

    def test_implementation_and_authority_changes_invalidate_exact_plan(self):
        p=self.plan(research_budget=0)
        with patch.object(a,"ASSISTANT_VERSION","changed"):
            with self.assertRaisesRegex(ValueError,"changed"):
                a.validate_plan(self.snapshot,p,p["assistant_plan_fingerprint"],review_db_path=self.db,transport=Mock())
        identity=m.production_identity()
        identity["source_authority_fingerprint"]="changed"
        with patch.object(m,"production_identity",return_value=identity):
            with self.assertRaisesRegex(ValueError,"STALE"):
                a.validate_plan(self.snapshot,p,p["assistant_plan_fingerprint"],review_db_path=self.db,transport=Mock())

    def test_native_parent_decomposition_route_is_surfaced_without_reclassifying_children(self):
        rows=deepcopy(self.snapshot["gap_rows"])
        row=next(r for r in rows if r["fix_layer"]==m.IDENTITY_GAP)
        row["fix_layer"]=m.PARSING_PROBLEM
        row["candidate"]["operational_route"]="needs_decomposition"
        with patch.object(m,"list_gap_rows",return_value=rows):
            item=next(x for x in self.plan()["all_actions"] if x["candidate_id"]==row["candidate_id"])
        self.assertEqual(item["research_state"],m.NEEDS_DECOMPOSITION)
        self.assertEqual(item["provider_calls_required"],0)

    def test_resolved_evidence_policy_does_not_claim_unresolved_gap_impact(self):
        rows=deepcopy(self.snapshot["gap_rows"])
        policy=deepcopy(rows[0])
        policy["candidate_id"]="policy-family"
        policy["candidate"]=None
        policy["fix_layer"]=m.EVIDENCE_PROBLEM
        policy["requirements"]=[dict(policy["requirements"][0],job_id=i,requirement_id="policy"+str(i),
            importance="required",current_resolution={"status":"resolved"}) for i in range(20)]
        with patch.object(m,"list_gap_rows",return_value=rows+[policy]):
            p=self.plan()
        item=next(a for a in p["all_actions"] if a["candidate_id"]=="policy-family")
        self.assertEqual(item["unresolved_weight"],0)
        self.assertNotEqual(p["ranked_actions"][0]["candidate_id"],"policy-family")
