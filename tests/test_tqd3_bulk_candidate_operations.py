"""Focused tests for bounded bulk TQ-D3 orchestration; fake transports/temp stores only."""
from __future__ import annotations

from copy import deepcopy
import json
import sys
import threading
import unittest
from unittest.mock import Mock, patch

from database.taxonomy_discovery_review_manager import (
    list_governed_research_results,
    save_governed_research_review,
)
from taxonomy_discovery import bulk_candidate_operations as bulk
from taxonomy_discovery import governed_research as research
from taxonomy_discovery.corpus_expansion import fingerprint
from tests.test_tqd3_publication_ui import FakeStreamlit
from tests.test_tqd3_taxonomy_evolution import candidate
from tests.tqd3_publication_fixture_support import PublicationFixture


REST = "Knowledge of web services, API, REST, and gRPC"
AWS = "Hands-on experience with Amazon Web Services (EC2, Cognito, S3, DynamoDB, etc.)"


def novel_candidates(count):
    technologies = ("MongoDB", "Node.js", ".NET", "Keycloak", "C#")
    return [candidate(
        f"Experience with {technologies[index % len(technologies)]} for fixture project {index + 1}",
        "technology_identity",
    ) for index in range(count)]


def authority_file(fixture, candidates):
    path = fixture.tmp / "bulk-authority.json"
    path.write_text(json.dumps({"version": "bulk-test", "technology_domains": [
        {"technology_aliases": ["C#", "MongoDB", "Node.js", ".NET", "Keycloak"],
         "safe_identity_aliases": ["C#", "MongoDB", "Node.js", ".NET", "Keycloak"],
         "official_domains": ["fixture.example"]}
    ]}), encoding="utf-8")
    return path


def successful_transport(calls=None):
    def transport(target):
        if calls is not None:
            calls.append(target["candidate"]["candidate_id"])
        subject = target["subject"]
        return {"request_id": "fake-" + target["candidate"]["candidate_id"], "results": [
            {"url": "https://fixture.example/docs", "content": f"{subject} is a software engineering tool."}
        ]}
    return transport


class BulkFakeStreamlit(FakeStreamlit):
    """Widget-aware fake for the staged bulk workflow."""

    def __init__(self, *, click_keys=()):
        super().__init__()
        self.click_keys = set(click_keys)
        self.reruns = 0
        self.multiselects = []

    def button(self, label, **kwargs):
        self.buttons.append((label, kwargs))
        return not kwargs.get("disabled", False) and kwargs.get("key") in self.click_keys

    def radio(self, label, options, **kwargs):
        key = kwargs.get("key")
        return self.session_state.get(key, options[0])

    def multiselect(self, label, options, **kwargs):
        self.multiselects.append((label, list(options), kwargs))
        return self.session_state.get(kwargs.get("key"), [])

    def selectbox(self, label, options, **kwargs):
        return self.session_state.get(kwargs.get("key"), options[0] if options else None)

    def checkbox(self, label, **kwargs):
        return bool(self.session_state.get(kwargs.get("key"), False))

    def text_input(self, label, **kwargs):
        return self.session_state.get(kwargs.get("key"), "")

    def text_area(self, label, **kwargs):
        return self.session_state.get(kwargs.get("key"), "")

    def rerun(self):
        self.reruns += 1


def ui_queue(candidate_id="candidate-1"):
    row = {
        "priority_rank": 1,
        "candidate_id": candidate_id,
        "concept": "Candidate One",
        "route": "technology_identity",
        "distinct_job_count": 1,
        "occurrence_count": 1,
        "importance_distribution": {"required": 1},
        "local_evidence_status": "unresolved",
        "research_status": "external_research_required",
        "external_research_required": True,
        "prior_recommended_action": None,
        "draft_status": "none",
        "review_status": "undecided",
        "publication_status": "not_published",
        "priority_score": 1,
        "blockers": [],
    }
    return {"route_counts": {"technology_identity": 1},
            "status_counts": {"external_research_required": 1},
            "rows": [row], "default_rows": [row]}


def ui_plan(*, external=1, targets=True):
    execution_targets = [{
        "candidate_id": "candidate-1",
        "research_route": "technology_identity",
        "research_purpose": "Verify technology identity",
        "authority_state": "candidate_evidence_only_not_governed",
        "planned_query": "official Candidate One documentation",
        "external": bool(external),
        "planned_tavily_calls": 1 if external else 0,
        "planned_questions": ["What is Candidate One?"],
    }] if targets else []
    return {
        "selected_count": 1,
        "precheck_counts": {"external_research_required": 1} if external else {"resolved_locally": 1},
        "external_candidates_required": external,
        "ready_external_candidates": external,
        "blocked_by_readiness": 0,
        "selected_readiness": [{"candidate_id": "candidate-1", "candidate": "Candidate One",
            "candidate_route": "technology_identity", "research_purpose": "Verify technology identity",
            "authority_state": "candidate_evidence_only_not_governed",
            "technology_identity": "Candidate One", "official_domains": [],
            "query_strategy": {"primary_query": "official Candidate One documentation"},
            "query_ready": True, "cache_currentness": "external_research_required",
            "decomposition_status": "atomic", "research_readiness": "identity_research_ready",
            "paid_research_eligible": True, "blocker_reason": "ready"}],
        "readiness_blockers": [],
        "external_candidates_next_run": external,
        "planned_tavily_calls": external,
        "hard_tavily_call_cap": 20,
        "maximum_queries_per_candidate": 3,
        "maximum_parallelism": 4,
        "execution_targets": execution_targets,
    }


class QueueAndPlanningTests(unittest.TestCase):
    def test_zero_result_follow_up_queries_stop_after_three_distinct_intents(self):
        item = candidate("MongoDB", "technology_relationship")
        row = {"candidate": item, "research_status": "research_more_required"}
        saved = [{"result": {
            "candidate_fingerprint": item["candidate_fingerprint"],
            "research": {"target": {"research_round": 1}},
        }}]
        self.assertEqual(bulk._research_round(row, saved), 2)
        saved[0]["result"]["research"]["target"]["research_round"] = 2
        self.assertIsNone(bulk._research_round(row, saved))

    def test_historical_registry_relationship_is_revalidated_against_current_mapping(self):
        with PublicationFixture():
            react = candidate("responsive user interfaces using React.js", "technology_relationship")
            queue = bulk.build_candidate_queue([react], saved_rows=[], publications=[])
            row = queue["rows"][0]
            self.assertEqual(row["route"], "technology_relationship")
            self.assertEqual(row["research_status"], "resolved_locally")
            self.assertFalse(row["external_research_required"])
            self.assertEqual(row["approved_capability_relationships"], [{
                "text": "React", "capability_id": "frontend.ui_development", "resolution_source": "technology_registry"}])
            self.assertEqual(row["recognized_technology_identities"][0]["technology_id"], "react")

    def test_historical_gap_is_revalidated_against_current_taxonomy(self):
        with PublicationFixture():
            current = candidate(REST)
            row = bulk.build_candidate_queue([current], saved_rows=[], publications=[])["rows"][0]
            self.assertEqual(row["full_production_resolution"]["capability_id"], "backend.api_development")
            self.assertEqual(row["research_status"], "resolved_locally")
            self.assertFalse(row["external_research_required"])
            self.assertEqual(bulk.prepare_bulk_plan([current], selected_candidate_ids=[current["candidate_id"]],
                saved_rows=[], publications=[])["execution_targets"], [])

    def test_compound_partial_resolution_is_visible_and_parent_is_not_globally_resolved(self):
        with PublicationFixture():
            parent = candidate("React and UnknownNovelTool", "technology_relationship")
            row = bulk.build_candidate_queue([parent], saved_rows=[], publications=[])["rows"][0]
            self.assertEqual(row["atomicity"], "compound_requires_decomposition")
            self.assertEqual(row["local_evidence_status"], "partial_resolution")
            self.assertEqual(row["research_status"], "partial_resolution_decomposition_required")
            self.assertFalse(row["external_research_required"])
            self.assertIn("UnknownNovelTool", row["unresolved_components"])
            self.assertEqual(row["approved_capability_relationships"][0]["capability_id"], "frontend.ui_development")
            child = candidate("UnknownNovelTool", "technology_identity")
            child_row = bulk.build_candidate_queue([child], saved_rows=[], publications=[])["rows"][0]
            self.assertEqual(child_row["research_status"], "external_research_required")
            self.assertTrue(child_row["external_research_required"])

    def test_real_dotnet_sql_phrase_is_partial_and_requires_decomposition(self):
        with PublicationFixture():
            parent = candidate(".NET MVC and Core and SQL Server for backend development", "technology_relationship")
            row = bulk.build_candidate_queue([parent], saved_rows=[], publications=[])["rows"][0]
            self.assertEqual(row["atomicity"], "atomic")  # Preserve the historical H.1.1 diagnostic.
            self.assertEqual(row["operational_atomicity"], "compound_requires_decomposition")
            self.assertEqual(row["research_status"], "partial_resolution_decomposition_required")
            self.assertFalse(row["external_research_required"])
            self.assertEqual(row["recognized_technology_identities"][0]["technology_id"], "dotnet")
            self.assertIn("sql server", row["unresolved_components"])

    def test_aws_negative_and_keycloak_stale_research_more_remain_fail_closed(self):
        with PublicationFixture():
            aws = candidate(AWS, "technology_identity")
            keycloak = candidate("Keycloak", "technology_relationship")
            old = deepcopy(keycloak)
            old["routing_reason"] += " historical"
            old.pop("candidate_id"); old.pop("candidate_fingerprint")
            old["candidate_fingerprint"] = fingerprint(old)
            old["candidate_id"] = "tqd3taxgap_" + old["candidate_fingerprint"][:24]
            saved = [{"result": {"candidate": old, "candidate_fingerprint": old["candidate_fingerprint"],
                "research_result_id": "old-keycloak", "recommended_next_action": "research_more"},
                "draft": None, "review": {"decision": "undecided"}}]
            queue = bulk.build_candidate_queue([aws, keycloak], saved_rows=saved, publications=[])
            rows = {row["concept"]: row for row in queue["rows"]}
            aws_row = rows[aws["concept_key"]]
            self.assertNotEqual(aws_row["full_production_resolution"]["capability_id"], "backend.api_development")
            self.assertFalse(aws_row["external_research_required"])
            self.assertIn(aws_row["research_status"], {"blocked", "partial_resolution_decomposition_required"})
            keycloak_row = rows["keycloak"]
            self.assertEqual(keycloak_row["research_status"], "stale_requires_refresh")
            self.assertEqual(keycloak_row["prior_recommended_action"], "research_more")
            self.assertEqual(keycloak_row["recognized_technology_identities"][0]["registry_status"], "recognized_unmapped")

    def test_current_state_revalidation_is_deterministic_and_preview_zero_cost(self):
        with PublicationFixture() as f:
            rows = [candidate("responsive user interfaces using React.js", "technology_relationship"),
                    candidate("Experience with C# for fixture validation", "technology_identity")]
            rules = authority_file(f, [rows[1]])
            before = deepcopy(rows)
            first = bulk.build_candidate_queue(rows, saved_rows=[], publications=[], authority_registry_path=rules)
            second = bulk.build_candidate_queue(deepcopy(rows), saved_rows=[], publications=[], authority_registry_path=rules)
            self.assertEqual(first, second)
            unresolved = next(row for row in first["rows"] if row["external_research_required"])
            provider = Mock(side_effect=AssertionError("planning must not execute"))
            with patch.object(research, "tavily_transport", provider):
                plan = bulk.prepare_bulk_plan(rows, selected_candidate_ids=[row["candidate_id"] for row in rows],
                                              saved_rows=[], publications=[], authority_registry_path=rules)
            provider.assert_not_called()
            self.assertEqual(plan["external_candidates_required"], 1)
            self.assertEqual(plan["execution_targets"][0]["candidate_id"], unresolved["candidate_id"])
            self.assertEqual(plan["network_calls_during_preview"], 0)
            self.assertEqual(plan["model_calls_during_preview"], 0)
            self.assertEqual(plan["production_writes_during_preview"], 0)
            self.assertEqual(rows, before)
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_deterministic_route_order_recurrence_and_importance_weighting(self):
        with PublicationFixture():
            rows = [
                candidate("NovelToolA", "technology_identity"),
                candidate("NovelToolB", "technology_identity"),
                candidate("novel distributed protocols", "capability_gap"),
            ]
            # Re-sign fixture metadata after creating transparent priority differences.
            rows[0]["job_count"] = rows[0]["observed_job_count"] = 3
            rows[0]["occurrence_count"] = rows[0]["observed_occurrence_count"] = 4
            rows[0]["importance_distribution"] = {"required": 4}
            rows[0].pop("candidate_fingerprint"); rows[0].pop("candidate_id")
            rows[0]["candidate_fingerprint"] = fingerprint(rows[0])
            rows[0]["candidate_id"] = "tqd3taxgap_" + rows[0]["candidate_fingerprint"][:24]
            first = bulk.build_candidate_queue(rows, saved_rows=[], publications=[])
            second = bulk.build_candidate_queue(deepcopy(rows), saved_rows=[], publications=[])
            self.assertEqual(first, second)
            ordered = first["rows"]
            self.assertEqual(ordered[0]["candidate_id"], rows[0]["candidate_id"])
            self.assertGreater(ordered[0]["priority_components"]["required"], 0)
            self.assertGreater(ordered[0]["priority_components"]["distinct_jobs"], ordered[1]["priority_components"]["distinct_jobs"])
            self.assertGreater(bulk.ROUTE_WEIGHT["technology_identity"], bulk.ROUTE_WEIGHT["possible_new_capability"])

    def test_local_resolution_and_published_rejected_deferred_filters(self):
        with PublicationFixture() as f:
            rest = candidate(REST)
            published = candidate("NovelToolA", "technology_identity")
            rejected = candidate("NovelToolB", "technology_identity")
            deferred = candidate("NovelToolC", "technology_identity")
            def saved(candidate_row, decision):
                return {"result": {"candidate": candidate_row, "candidate_fingerprint": candidate_row["candidate_fingerprint"],
                    "research_result_id": "r-" + decision, "recommended_next_action": "technology_identity_proposal"},
                    "draft": None, "review": {"decision": decision}}
            saved_rows = [saved(rejected, "reject"), saved(deferred, "defer")]
            publications = [{"candidate_id": published["candidate_id"], "status": "published"}]
            with patch.object(bulk, "_valid_result", return_value=True):
                queue = bulk.build_candidate_queue([rest, published, rejected, deferred], saved_rows=saved_rows, publications=publications)
            by_id = {row["candidate_id"]: row for row in queue["rows"]}
            self.assertEqual(by_id[rest["candidate_id"]]["research_status"], "resolved_locally")
            self.assertEqual(by_id[published["candidate_id"]]["research_status"], "already_published")
            self.assertEqual(by_id[rejected["candidate_id"]]["research_status"], "already_rejected")
            self.assertEqual(by_id[deferred["candidate_id"]]["research_status"], "deferred")
            self.assertEqual(queue["default_rows"], [])
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_plan_preview_is_local_exact_and_deterministically_caps_next_eight(self):
        with PublicationFixture() as f:
            candidates = novel_candidates(9)
            rules = authority_file(f, candidates)
            calls = Mock(side_effect=AssertionError("preview must not execute"))
            with patch.object(research, "tavily_transport", calls):
                plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=[c["candidate_id"] for c in reversed(candidates)],
                                              saved_rows=[], publications=[], authority_registry_path=rules)
            calls.assert_not_called()
            self.assertEqual(plan["selected_count"], 9)
            self.assertEqual(plan["external_candidates_required"], 9)
            self.assertEqual(plan["external_candidates_next_run"], 8)
            self.assertEqual(plan["planned_tavily_calls"], 8)
            self.assertEqual(plan["hard_tavily_call_cap"], 20)
            self.assertEqual(len(plan["pending_external_candidate_ids"]), 1)
            self.assertEqual(plan["network_calls_during_preview"], 0)
            self.assertLessEqual(max(len(item["planned_questions"]) for item in plan["execution_targets"]), 3)
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_stale_cache_fails_closed_and_current_cache_skips_provider(self):
        with PublicationFixture() as f:
            candidates = novel_candidates(1)
            rules = authority_file(f, candidates)
            db = f.tmp / "bulk.sqlite3"
            plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=[candidates[0]["candidate_id"]], saved_rows=[],
                                          publications=[], authority_registry_path=rules)
            first_calls = []
            first = bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=successful_transport(first_calls),
                                           db_path=db, authority_registry_path=rules)
            self.assertEqual(first["candidates_completed"], 1)
            self.assertEqual(len(first_calls), 1)
            saved_rows = list_governed_research_results(db_path=db)
            queue = bulk.build_candidate_queue(candidates, saved_rows=saved_rows, publications=[], authority_registry_path=rules)
            self.assertEqual(queue["rows"][0]["research_status"], "research_more_required")
            self.assertTrue(queue["rows"][0]["current_result"])
            rerun_calls = []
            rerun = bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=successful_transport(rerun_calls),
                                           db_path=db, authority_registry_path=rules)
            self.assertEqual(rerun_calls, [])
            self.assertEqual(rerun["cache_hits"], 1)
            changed = deepcopy(candidates[0])
            changed["routing_reason"] += " material change"
            changed.pop("candidate_id"); changed.pop("candidate_fingerprint")
            changed["candidate_fingerprint"] = fingerprint(changed)
            changed["candidate_id"] = "tqd3taxgap_" + changed["candidate_fingerprint"][:24]
            stale_queue = bulk.build_candidate_queue([changed], saved_rows=saved_rows, publications=[])
            self.assertEqual(stale_queue["rows"][0]["research_status"], "stale_requires_refresh")
            self.assertEqual(stale_queue["rows"][0]["prior_recommended_action"], "research_more")
            stale_plan = bulk.prepare_bulk_plan([changed], selected_candidate_ids=[changed["candidate_id"]],
                                                saved_rows=saved_rows, publications=[], authority_registry_path=rules)
            self.assertEqual(stale_plan["execution_targets"], [])
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()


class ExecutionAndReviewTests(unittest.TestCase):
    def test_bounded_parallel_execution_persists_each_and_resumes_without_charge(self):
        with PublicationFixture() as f:
            candidates = novel_candidates(9)
            rules = authority_file(f, candidates)
            db = f.tmp / "bulk.sqlite3"
            plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=[c["candidate_id"] for c in candidates], saved_rows=[],
                                          publications=[], authority_registry_path=rules)
            calls, active, maximum = [], 0, 0
            lock = threading.Lock()
            def transport(target):
                nonlocal active, maximum
                with lock:
                    active += 1; maximum = max(maximum, active); calls.append(target["candidate"]["candidate_id"])
                try:
                    return successful_transport()(target)
                finally:
                    with lock:
                        active -= 1
            receipt = bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=transport,
                                             db_path=db, authority_registry_path=rules)
            self.assertEqual(receipt["candidates_completed"], 8)
            self.assertEqual(receipt["candidates_pending"], 1)
            self.assertEqual(len(calls), 8)
            self.assertLessEqual(maximum, 4)
            self.assertEqual(len(list_governed_research_results(db_path=db)), 8)
            second_calls = []
            resumed = bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=successful_transport(second_calls),
                                             db_path=db, authority_registry_path=rules)
            self.assertEqual(second_calls, [])
            self.assertEqual(resumed["cache_hits"], 8)
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_retry_and_systemic_failure_bounds_are_enforced(self):
        with PublicationFixture() as f:
            candidates = novel_candidates(8)
            rules = authority_file(f, candidates)
            db = f.tmp / "bulk.sqlite3"
            plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=[c["candidate_id"] for c in candidates], saved_rows=[],
                                          publications=[], authority_registry_path=rules)
            auth = Mock(side_effect=ValueError("authentication failed"))
            receipt = bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=auth, db_path=db,
                                             authority_registry_path=rules)
            self.assertLessEqual(receipt["calls_attempted"], 4)
            self.assertGreaterEqual(receipt["candidates_pending"], 4)
            self.assertEqual(receipt["candidates_failed"], 4)
            self.assertEqual(len(list_governed_research_results(db_path=db)), 0)
            self.assertIsNotNone(bulk.load_bulk_run_receipt(plan["plan_fingerprint"], db_path=db))
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_transient_retries_stay_under_global_and_per_candidate_caps(self):
        with PublicationFixture() as f:
            candidates = novel_candidates(8)
            rules = authority_file(f, candidates)
            db = f.tmp / "bulk.sqlite3"
            plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=[c["candidate_id"] for c in candidates], saved_rows=[],
                                          publications=[], authority_registry_path=rules)
            attempts = {}
            lock = threading.Lock()
            def transport(target):
                candidate_id = target["candidate"]["candidate_id"]
                with lock:
                    attempts[candidate_id] = attempts.get(candidate_id, 0) + 1
                    attempt = attempts[candidate_id]
                if attempt == 1:
                    raise TimeoutError("synthetic retry")
                return successful_transport()(target)
            receipt = bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=transport,
                                             db_path=db, authority_registry_path=rules)
            self.assertEqual(receipt["calls_attempted"], 16)
            self.assertEqual(receipt["calls_completed"], 8)
            self.assertLessEqual(receipt["calls_attempted"], bulk.MAX_TAVILY_CALLS_PER_RUN)
            self.assertTrue(all(count <= bulk.MAX_QUERIES_PER_CANDIDATE for count in attempts.values()))
            self.assertEqual(receipt["candidates_completed"], 8)

    def test_one_candidate_failure_keeps_other_results_durable(self):
        with PublicationFixture() as f:
            candidates = novel_candidates(4)
            rules = authority_file(f, candidates)
            db = f.tmp / "bulk.sqlite3"
            plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=[c["candidate_id"] for c in candidates], saved_rows=[],
                                          publications=[], authority_registry_path=rules)
            failed_id = plan["execution_targets"][0]["candidate_id"]
            def transport(target):
                if target["candidate"]["candidate_id"] == failed_id:
                    raise ValueError("candidate-specific fixture failure")
                return successful_transport()(target)
            receipt = bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=transport,
                                             db_path=db, authority_registry_path=rules)
            self.assertEqual(receipt["candidates_failed"], 1)
            self.assertEqual(receipt["candidates_completed"], 3)
            self.assertEqual(len(list_governed_research_results(db_path=db)), 3)
            self.assertEqual(bulk.load_bulk_run_receipt(plan["plan_fingerprint"], db_path=db)["outcomes"][failed_id]["status"], "failed")

    def test_selection_and_research_do_not_approve_and_defer_persists(self):
        with PublicationFixture() as f:
            candidates = novel_candidates(1)
            rules = authority_file(f, candidates)
            db = f.tmp / "bulk.sqlite3"
            plan = bulk.prepare_bulk_plan(candidates, selected_candidate_ids=[candidates[0]["candidate_id"]], saved_rows=[],
                                          publications=[], authority_registry_path=rules)
            bulk.execute_bulk_plan(plan, candidates, explicit_execution=True, transport=successful_transport(), db_path=db,
                                   authority_registry_path=rules)
            row = list_governed_research_results(db_path=db)[0]
            self.assertFalse(row["result"]["approval"])
            self.assertEqual(row["review"]["decision"], "undecided")
            save_governed_research_review(row["result"]["research_result_id"],
                result_fingerprint=row["result"]["result_fingerprint"], decision="defer", reviewer="TEST", db_path=db)
            deferred = bulk.build_candidate_queue(candidates, saved_rows=list_governed_research_results(db_path=db), publications=[])
            self.assertEqual(deferred["rows"][0]["research_status"], "deferred")
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()

    def test_keycloak_and_sccm_research_more_are_never_forced_into_drafts(self):
        with PublicationFixture():
            results = []
            for index, name in enumerate(("Keycloak", "Microsoft SCCM")):
                results.append({"research_result_id": f"control-{index}", "recommended_next_action": "research_more"})
            outcome = bulk.create_bulk_drafts(results, selected_result_ids=[r["research_result_id"] for r in results],
                                              explicit_creation=True, db_path="unused")
            self.assertEqual(len(outcome["skipped"]), 2)
            self.assertEqual(outcome["created"], [])
            self.assertTrue(all(row["reason"] == "research_more" for row in outcome["skipped"]))


class RegressionPublicationAndUITests(unittest.TestCase):
    def test_combined_capability_regression_uses_native_overlay_and_preserves_inputs(self):
        corpus = {"fixture": "unchanged"}
        original = deepcopy(corpus)
        drafts = [{"result_id": "r1", "draft": {"kind": "capability", "proposal": {"proposal_id": "p1"}}},
                  {"result_id": "r2", "draft": {"kind": "capability", "proposal": {"proposal_id": "p2"}}}]
        item_report = {"jobs": [], "affected_jobs": [], "regression_fingerprint": "item"}
        combined = {"jobs": [{"classification": "requires_review", "duplicate_credit_violations": [],
                               "requirement_changes": [{"interaction_review_required": True}]}],
                    "affected_jobs": [1], "regression_fingerprint": "old"}
        with patch("taxonomy_discovery.governed_research.temporary_impact", return_value=item_report), \
             patch("taxonomy_discovery.governed_research.knowledge_fingerprint", return_value="knowledge"), \
             patch("taxonomy_discovery.taxonomy_evolution.temporary_regression", return_value=combined) as native, \
             patch.object(bulk, "bulk_canary_status", return_value={"all": {"safe": True}}):
            report = bulk.preview_bulk_regression(corpus, drafts)
        native.assert_called_once_with(corpus, [{"proposal_id": "p1"}, {"proposal_id": "p2"}])
        self.assertTrue(report["combined_overlay_supported"])
        self.assertEqual(report["production_writes"], 0)
        self.assertEqual(corpus, original)
        self.assertEqual(report["canaries"]["all"]["safe"], True)

    def test_mixed_or_multi_publication_preflight_fails_closed_and_publish_is_explicit(self):
        def preflight(result_id, **_):
            kind = "resolver_improvement" if result_id == "r1" else "technology_identity"
            return {"ready": True, "blockers": [], "kind": kind, "version_before": "v1", "version_after": "v2"}
        with patch("taxonomy_discovery.governed_publication.prepare_publication", side_effect=preflight):
            mixed = bulk.prepare_publication_tranche(["r1", "r2"])
        self.assertFalse(mixed["ready"])
        self.assertIn("mixed_artifact_atomicity_unsupported_split_tranche_by_family", mixed["blockers"])
        self.assertIn("native_multi_proposal_single_version_publication_unavailable", mixed["blockers"])
        with self.assertRaises(ValueError):
            bulk.publish_publication_tranche(mixed)
        with patch("taxonomy_discovery.governed_publication.prepare_publication", side_effect=preflight), \
             patch("taxonomy_discovery.governed_publication.publish_approved_change", return_value={"publication_id": "p"}) as publish:
            single = bulk.prepare_publication_tranche(["r1"])
            bulk.publish_publication_tranche(single, explicit_publish=True)
        publish.assert_called_once_with("r1", explicit_publish=True, db_path=None, proposal_db_path=None)

    def test_permanent_canaries_cover_web_aws_cpp_and_react(self):
        with PublicationFixture():
            canaries = bulk.bulk_canary_status()
            self.assertTrue(canaries["web_services_positive"]["safe"])
            self.assertTrue(canaries["aws_negative"]["safe"])
            self.assertTrue(canaries["cpp"]["safe"])
            self.assertTrue(canaries["react"]["safe"])

    def test_passive_ui_render_executes_nothing(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch.object(research, "prepare_gap_review") as prepare, \
             patch.object(bulk, "prepare_bulk_plan") as plan, \
             patch.object(bulk, "execute_bulk_plan") as execute, \
             patch.object(bulk, "publish_publication_tranche") as publish:
            ui.render_bulk_candidate_operations()
        prepare.assert_not_called(); plan.assert_not_called(); execute.assert_not_called(); publish.assert_not_called()
        labels = [label for label, _ in st.buttons]
        self.assertEqual(st.session_state[ui.ACTIVE_STAGE_KEY], "select")
        self.assertIn("Prepare selected batch →", labels)
        self.assertNotIn("Research next bounded batch →", labels)
        self.assertNotIn("Run publication preflight", labels)
        self.assertNotIn("Publish approved tranche", labels)
        source = __import__("pathlib").Path(ui.__file__).read_text(encoding="utf-8")
        self.assertLess(source.index('"Run publication preflight"'), source.index('"Publish approved tranche"'))

    def test_zero_selected_disables_prepare(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit(click_keys={"tqd3_bulk_plan"})
        st.session_state.update({
            "tqd3_bulk_prepared": {"candidates": [{"candidate_id": "candidate-1"}]},
            "tqd3_bulk_queue": ui_queue(),
            "tqd3_bulk_selected": [],
        })
        with patch.dict(sys.modules, {"streamlit": st}), patch.object(bulk, "prepare_bulk_plan") as planner:
            ui.render_bulk_candidate_operations()
        planner.assert_not_called()
        prepare = next(kwargs for label, kwargs in st.buttons if label == "Prepare selected batch →")
        self.assertTrue(prepare["disabled"])

    def test_prepare_uses_existing_planner_and_advances_without_paid_calls(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit(click_keys={"tqd3_bulk_plan"})
        candidates = [{"candidate_id": "candidate-1"}]
        st.session_state.update({
            "tqd3_bulk_prepared": {"candidates": candidates},
            "tqd3_bulk_queue": ui_queue(),
            "tqd3_bulk_selected": ["candidate-1"],
        })
        plan = ui_plan()
        with PublicationFixture() as f, \
             patch.dict(sys.modules, {"streamlit": st}), \
             patch.object(bulk, "prepare_bulk_plan", return_value=plan) as planner, \
             patch.object(bulk, "execute_bulk_plan") as execute:
            ui.render_bulk_candidate_operations()
            planner.assert_called_once_with(candidates, selected_candidate_ids=["candidate-1"])
            execute.assert_not_called()
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()
        self.assertEqual(st.session_state[ui.ACTIVE_STAGE_KEY], "plan")
        self.assertEqual(st.session_state["tqd3_bulk_plan_receipt"], plan)
        self.assertEqual(st.session_state["tqd3_bulk_selected"], ["candidate-1"])
        self.assertEqual(st.reruns, 1)

    def test_plan_render_does_not_execute_research_and_shows_explicit_action(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit()
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "plan",
            "tqd3_bulk_prepared": {"candidates": [{"candidate_id": "candidate-1"}]},
            "tqd3_bulk_selected": ["candidate-1"],
            "tqd3_bulk_plan_receipt": ui_plan(),
        })
        with patch.dict(sys.modules, {"streamlit": st}), patch.object(bulk, "execute_bulk_plan") as execute:
            ui.render_bulk_candidate_operations()
        execute.assert_not_called()
        labels = [label for label, _ in st.buttons]
        self.assertIn("← Back to selection", labels)
        self.assertIn("Research next safe route-aware batch →", labels)
        self.assertEqual(st.session_state[ui.ACTIVE_STAGE_KEY], "plan")
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("Registry readiness summary", rendered)
        self.assertIn("Safe paid research routes", rendered)
        self.assertIn("Identity research ready", rendered)
        self.assertIn("Verify technology identity", rendered)
        self.assertIn("Not yet governed; discovery evidence only", rendered)
        self.assertIn("official Candidate One documentation", rendered)

    def test_plan_paid_action_executes_only_on_click_and_advances_to_research(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit(click_keys={"tqd3_bulk_execute_plan"})
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "plan",
            "tqd3_bulk_prepared": {"candidates": [{"candidate_id": "candidate-1"}]},
            "tqd3_bulk_selected": ["candidate-1"],
            "tqd3_bulk_plan_receipt": ui_plan(),
        })
        receipt = {"calls_attempted": 1, "calls_completed": 1, "cache_hits": 0,
                   "candidates_completed": 1, "candidates_failed": 0, "candidates_pending": 0,
                   "outcomes": {"candidate-1": {"status": "completed"}}}
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch.object(bulk, "execute_bulk_plan", return_value=receipt) as execute:
            ui.render_bulk_candidate_operations()
        execute.assert_called_once()
        self.assertEqual(st.session_state[ui.ACTIVE_STAGE_KEY], "research")
        self.assertEqual(st.session_state["tqd3_bulk_run_receipt"], receipt)

    def test_research_requires_explicit_button_and_does_not_create_drafts(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        base = {
            ui.ACTIVE_STAGE_KEY: "research",
            "tqd3_bulk_prepared": {"candidates": [{"candidate_id": "candidate-1"}]},
            "tqd3_bulk_plan_receipt": ui_plan(),
        }
        passive = BulkFakeStreamlit()
        passive.session_state.update(deepcopy(base))
        with patch.dict(sys.modules, {"streamlit": passive}), \
             patch.object(bulk, "execute_bulk_plan") as execute:
            ui.render_bulk_candidate_operations()
        execute.assert_not_called()

        clicked = BulkFakeStreamlit(click_keys={"tqd3_bulk_execute"})
        clicked.session_state.update(deepcopy(base))
        receipt = {"calls_attempted": 1, "calls_completed": 1, "cache_hits": 0,
                   "candidates_completed": 1, "candidates_failed": 0, "candidates_pending": 0,
                   "outcomes": {"candidate-1": {"status": "completed"}}}
        with patch.dict(sys.modules, {"streamlit": clicked}), \
             patch.object(bulk, "execute_bulk_plan", return_value=receipt) as execute, \
             patch.object(bulk, "create_bulk_drafts") as drafts:
            ui.render_bulk_candidate_operations()
        execute.assert_called_once_with(clicked.session_state["tqd3_bulk_plan_receipt"],
                                        clicked.session_state["tqd3_bulk_prepared"]["candidates"],
                                        explicit_execution=True)
        drafts.assert_not_called()
        self.assertEqual(clicked.session_state["tqd3_bulk_run_receipt"], receipt)
        self.assertEqual(clicked.session_state[ui.ACTIVE_STAGE_KEY], "research")

    def test_proposal_stage_does_not_approve_automatically(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit()
        st.session_state.update({ui.ACTIVE_STAGE_KEY: "proposals", "tqd3_bulk_saved": []})
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch("database.taxonomy_discovery_review_manager.save_governed_research_review") as review, \
             patch.object(bulk, "publish_publication_tranche") as publish:
            ui.render_bulk_candidate_operations()
        review.assert_not_called(); publish.assert_not_called()

    def test_proposals_auto_load_current_batch_filter_non_draftable_and_use_readable_labels(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        def saved(result_id, concept, action, *, decision="undecided", blockers=None):
            return {"result": {"research_result_id": result_id, "candidate": {"concept_key": concept},
                "candidate_route": "technology_identity", "recommended_next_action": action,
                "sources": [], "conflicts_blockers": blockers or [], "result_fingerprint": "fp-" + result_id},
                "draft": None, "review": {"decision": decision}}
        rows = [
            saved("current-ready", "Node.js", "technology_identity_proposal"),
            saved("current-more", "MongoDB", "research_more"),
            saved("historical-ready", "Keycloak", "technology_identity_proposal"),
            saved("historical-defer", "SCCM", "technology_identity_proposal", decision="defer"),
        ]
        st = BulkFakeStreamlit()
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "proposals",
            "tqd3_bulk_run_receipt": {"outcomes": {
                "node": {"research_result_id": "current-ready"},
                "mongo": {"research_result_id": "current-more"},
            }},
        })
        with PublicationFixture() as f, patch.dict(sys.modules, {"streamlit": st}), \
             patch("database.taxonomy_discovery_review_manager.list_governed_research_results", return_value=rows), \
             patch.object(bulk, "create_bulk_drafts") as drafts:
            ui.render_bulk_candidate_operations()
            f.network_guard.assert_not_called(); f.model_guard.assert_not_called()
        drafts.assert_not_called()
        self.assertEqual([row["result"]["research_result_id"] for row in st.session_state["tqd3_bulk_saved"]],
                         ["current-ready", "current-more"])
        selector = next(item for item in st.multiselects if item[0] == "Research results for explicit draft creation")
        self.assertEqual(selector[1], ["current-ready"])
        self.assertEqual(selector[2]["format_func"]("current-ready"), "Node.js — technology identity proposal")

        historical = BulkFakeStreamlit()
        historical.session_state.update(deepcopy(st.session_state))
        historical.session_state["tqd3_bulk_show_historical"] = True
        with patch.dict(sys.modules, {"streamlit": historical}), \
             patch("database.taxonomy_discovery_review_manager.list_governed_research_results", return_value=rows):
            ui.render_bulk_candidate_operations()
        selector = next(item for item in historical.multiselects if item[0] == "Research results for explicit draft creation")
        self.assertEqual(selector[1], ["current-ready", "historical-ready"])

    def test_proposals_show_exact_empty_eligibility_message(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        row = {"result": {"research_result_id": "r-more", "candidate": {"concept_key": "MongoDB"},
            "candidate_route": "technology_relationship", "recommended_next_action": "research_more",
            "sources": [], "conflicts_blockers": ["insufficient"], "result_fingerprint": "fp"},
            "draft": None, "review": {"decision": "undecided"}}
        st = BulkFakeStreamlit()
        st.session_state.update({ui.ACTIVE_STAGE_KEY: "proposals",
            "tqd3_bulk_run_receipt": {"outcomes": {"mongo": {"research_result_id": "r-more"}}}})
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch("database.taxonomy_discovery_review_manager.list_governed_research_results", return_value=[row]):
            ui.render_bulk_candidate_operations()
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("No current research result is eligible for proposal creation.", rendered)
        self.assertFalse(any(item[0] == "Research results for explicit draft creation" for item in st.multiselects))

    def test_review_render_does_not_publish_automatically(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit()
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "review",
            "tqd3_bulk_saved": [{
                "result": {"research_result_id": "r1", "result_fingerprint": "rf"},
                "draft": {"kind": "technology_identity"},
                "review": {"decision": "approve_for_publication"},
            }],
        })
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch.object(bulk, "prepare_publication_tranche") as preflight, \
             patch.object(bulk, "publish_publication_tranche") as publish:
            ui.render_bulk_candidate_operations()
        preflight.assert_not_called(); publish.assert_not_called()
        self.assertIn("Run publication preflight →", [label for label, _ in st.buttons])

    def test_successful_review_preflight_advances_without_publishing(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit(click_keys={"tqd3_bulk_review_preflight"})
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "review",
            "tqd3_bulk_saved": [{
                "result": {"research_result_id": "r1", "result_fingerprint": "rf"},
                "draft": {"kind": "technology_identity"},
                "review": {"decision": "approve_for_publication"},
            }],
        })
        preflight = {"ready": True, "blockers": []}
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch.object(bulk, "prepare_publication_tranche", return_value=preflight) as prepare, \
             patch.object(bulk, "publish_publication_tranche") as publish:
            ui.render_bulk_candidate_operations()
        prepare.assert_called_once_with(["r1"])
        publish.assert_not_called()
        self.assertEqual(st.session_state[ui.ACTIVE_STAGE_KEY], "publish")
        self.assertEqual(st.session_state["tqd3_bulk_preflight"], preflight)

    def test_rerun_preserves_active_stage_and_selected_batch(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit()
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "plan",
            "tqd3_bulk_selected": ["candidate-1"],
            "tqd3_bulk_plan_receipt": ui_plan(),
            "tqd3_bulk_prepared": {"candidates": [{"candidate_id": "candidate-1"}]},
        })
        with patch.dict(sys.modules, {"streamlit": st}):
            ui.render_bulk_candidate_operations()
            ui.render_bulk_candidate_operations()
        self.assertEqual(st.session_state[ui.ACTIVE_STAGE_KEY], "plan")
        self.assertEqual(st.session_state["tqd3_bulk_selected"], ["candidate-1"])
        self.assertEqual(st.session_state["tqd3_bulk_plan_receipt"], ui_plan())

    def test_back_navigation_preserves_selection_and_plan(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = BulkFakeStreamlit(click_keys={"tqd3_bulk_plan_back"})
        plan = ui_plan()
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "plan",
            "tqd3_bulk_selected": ["candidate-1"],
            "tqd3_bulk_plan_receipt": plan,
            "tqd3_bulk_prepared": {"candidates": [{"candidate_id": "candidate-1"}]},
        })
        with patch.dict(sys.modules, {"streamlit": st}):
            ui.render_bulk_candidate_operations()
        self.assertEqual(st.session_state[ui.ACTIVE_STAGE_KEY], "select")
        self.assertEqual(st.session_state["tqd3_bulk_selected"], ["candidate-1"])
        self.assertIs(st.session_state["tqd3_bulk_plan_receipt"], plan)

    def test_explicit_bulk_regression_preview_persists_each_native_item_report(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        st = FakeStreamlit()
        st.session_state.update({
            ui.ACTIVE_STAGE_KEY: "proposals",
            "tqd3_bulk_prepared": {"corpus": {"corpus_version": "fixture"}},
            "tqd3_bulk_run_receipt": {"outcomes": {"candidate-1": {"research_result_id": "r1"}}},
            "tqd3_bulk_saved": [{"result": {"research_result_id": "r1", "candidate": {"concept_key": "x"},
                "candidate_route": "technology_identity", "recommended_next_action": "technology_identity_proposal",
                "sources": [], "conflicts_blockers": [], "result_fingerprint": "rf"},
                "draft": {"kind": "technology_identity"}, "review": {"decision": "undecided"}}],
        })
        st.button = lambda label, **kwargs: kwargs.get("key") == "tqd3_bulk_regression"
        preview = {"per_item": [{"result_id": "r1", "report": {"regression_fingerprint": "impact"}}],
                   "combined": {}, "combined_overlay_supported": True, "publication_blockers": []}
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch("database.taxonomy_discovery_review_manager.list_governed_research_results",
                   return_value=st.session_state["tqd3_bulk_saved"]), \
             patch.object(bulk, "preview_bulk_regression", return_value=preview), \
             patch("database.taxonomy_discovery_review_manager.save_governed_temporary_impact") as save:
            ui.render_bulk_candidate_operations()
        save.assert_called_once_with("r1", {"regression_fingerprint": "impact"})
        self.assertEqual(st.session_state["tqd3_bulk_regression"], preview)


if __name__ == "__main__":
    unittest.main()
