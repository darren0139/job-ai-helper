"""Offline maintenance adapters: native fixtures, fake providers, temp stores."""
from copy import deepcopy
import io
import json
import os
import socket
import unittest
from unittest.mock import Mock, patch
import zipfile

from database import taxonomy_discovery_review_manager as store
from taxonomy_discovery import maintenance_service as service
from taxonomy_discovery.corpus_expansion import fingerprint
from taxonomy_discovery.regression_corpus import build_regression_corpus
from tests.test_tqd3_regression_corpus import frozen_snapshot
from tests.test_tqd3_governed_research import candidate, execute, fake_raw, rules
from tests.tqd3_publication_fixture_support import PublicationFixture


def fixture_corpus(*concepts):
    snapshots = []
    for index, concept in enumerate(concepts or ("distributed systems",), 1):
        row = frozen_snapshot(concept)
        row.update(id=index, discovered_job_id=index)
        snapshots.append(row)
    return build_regression_corpus(snapshots)


def capability_fields(subject):
    return {"capability_id": "test.crystalline_computing", "label": subject, "domain": "distributed_systems",
        "definition": "Synthetic computing protocols only.", "match_concepts": [subject],
        "does_not_prove": ["Name mention only"], "evidence_expectations": {
            "policy_references": ["native bounded evidence predicates"], "evidence_tiers": [
                {"label": "direct", "all_groups": [[subject], ["built", "implemented"]],
                 "reason": "explicit_application", "concepts": [subject]}]}}


def seal_candidate(value):
    value["candidate_fingerprint"] = fingerprint({k: v for k, v in value.items() if k not in {"candidate_id", "candidate_fingerprint"}})
    value["candidate_id"] = "tqd3taxgap_" + value["candidate_fingerprint"][:24]
    return value


def legacy_attempt(f, current, research_round=0, historical_route=None):
    """Produce a normal saved result under the historical scorer/contract."""
    old = deepcopy(current)
    if historical_route:
        old["candidate_route"] = historical_route
    versions = {**old["current_versions"], "scoring_version": "stable-evidence-v1.11-phase6d17",
        "match_contract_version": "job-match-snapshot-v2.2.0",
        "match_version": "job-match-snapshot-v2.2.0|registry=technology-registry-v1.2"}
    old["current_versions"] = versions
    seal_candidate(old)
    authority = rules(f, [current["concept_key"]])
    from pathlib import Path
    scoped_authority = f.tmp / ("legacy_authority_" + fingerprint(current["concept_key"])[:12] + ".json")
    scoped_authority.write_bytes(Path(authority).read_bytes())
    provider = Mock(return_value=fake_raw(current["concept_key"], request_id="legacy-" + old["candidate_id"] + str(research_round)))
    with patch.object(service.research, "current_match_versions", return_value=versions), \
            patch("taxonomy_discovery.taxonomy_evolution.current_match_versions", return_value=versions):
        plan = service.research.research_plan([old], selected_candidate_ids=[old["candidate_id"]],
            research_round=research_round, authority_registry_path=scoped_authority)
        receipt = service.research.execute_plan(plan, [old], explicit_execution=True, transport=provider,
            db_path=f.tmp / "h1.sqlite", authority_registry_path=scoped_authority)
    if receipt["failures"]:
        raise AssertionError(receipt["failures"])
    provider.assert_called_once()
    return receipt["results"][0]


class MaintenanceServiceTests(unittest.TestCase):
    def test_current_candidate_rebinds_old_versions_and_preserves_all_attempts(self):
        with PublicationFixture() as f:
            db = f.tmp / "h1.sqlite"
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("network access control"), review_db_path=db, explicit_execution=True)
            c = snapshot["gap_rows"][0]["candidate"]
            old = [legacy_attempt(f, c, research_round=i) for i in range(3)]
            with self.assertRaisesRegex(ValueError, "Candidate knowledge versions changed"):
                service.research.re_evaluate_saved_evidence(old[-1], explicit_execution=True)
            before = store.list_governed_research_results(db_path=db)
            groups = service.build_review_targets(snapshot, saved_rows=before)
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(groups[0]["historical_attempts"]), 3)
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            preview = service.plan_research(snapshot, tranche, [c["candidate_id"]], transport=Mock(), review_db_path=db)
            self.assertEqual(preview["execution_preview"][0]["execution_status"], "EXISTING RESEARCH / REFRESH REQUIRED")
            self.assertEqual(groups[0]["primary"]["result"], old[-1])
            self.assertEqual(groups[0]["current_candidate"], c)
            with patch.object(service.research, "tavily_transport", side_effect=AssertionError("No provider")) as provider:
                refreshed = service.refresh_saved_research(snapshot, c["candidate_id"], explicit_execution=True, review_db_path=db)
                provider.assert_not_called()
            service.research.validate_result(refreshed)
            self.assertEqual(refreshed["candidate"], c)
            self.assertEqual(refreshed["research"]["raw_provider_evidence"], old[-1]["research"]["raw_provider_evidence"])
            self.assertEqual(refreshed["provider_request_id"], old[-1]["provider_request_id"])
            self.assertEqual(refreshed["interpretation_lineage"]["previous_research_result_id"], old[-1]["research_result_id"])
            after = store.list_governed_research_results(db_path=db)
            self.assertEqual(len(after), 4)
            for original in before:
                self.assertIn(original, after)
            self.assertTrue(all(not row["draft"] and row["review"]["decision"] == "undecided" for row in after))
            self.assertFalse(refreshed["approval"])
            groups = service.build_review_targets(snapshot, saved_rows=after)
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["primary"]["result"], refreshed)
            self.assertEqual(len(groups[0]["historical_attempts"]), 3)
            preview = service.plan_research(snapshot, tranche, [c["candidate_id"]], transport=Mock(), review_db_path=db)
            self.assertNotEqual(preview["execution_preview"][0]["execution_status"], "EXISTING RESEARCH / REFRESH REQUIRED")
            self.assertEqual(service.refresh_saved_research(snapshot, c["candidate_id"], explicit_execution=True, review_db_path=db), refreshed)
            self.assertEqual(len(store.list_governed_research_results(db_path=db)), 4)
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()
            self.assertEqual(f.real_registry.read_bytes(), f.real_registry_bytes)

    def test_review_grouping_uses_canonical_namespace_not_display_text(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("network access control", "sql querying"),
                review_db_path=f.tmp / "h1.sqlite", explicit_execution=True)
            for row in snapshot["gap_rows"]:
                if row["candidate"]:
                    for i in range(2):
                        # A historical SQL capability route can now be ineligible.
                        # Keep its history grouped; do not relax current routing.
                        legacy_attempt(f, row["candidate"], research_round=i,
                            historical_route="possible_new_capability" if row["concept"] == "sql querying" else None)
            saved = store.list_governed_research_results(db_path=f.tmp / "h1.sqlite")
            groups = service.build_review_targets(snapshot, saved_rows=saved)
            self.assertEqual({g["concept"] for g in groups}, {"network access control", "sql querying"})
            self.assertTrue(all(len(g["attempts"]) == 2 for g in groups))
            # Same subject in genuinely different canonical technology namespaces
            # remains distinct; neither can substitute for the current gap.
            scoped_rows = []
            for namespace in ("vendor.alpha", "vendor.beta"):
                scoped = deepcopy(next(row["candidate"] for row in snapshot["gap_rows"] if row["concept"] == "network access control"))
                scoped["technology_id"] = namespace
                scoped["provenance"][0]["job_content_hash"] = "distinct-source-" + namespace
                seal_candidate(scoped)
                scoped_rows.append({"result": legacy_attempt(f, scoped), "review": {"decision": "undecided"}, "draft": None})
            distinct = service.build_review_targets(snapshot, saved_rows=scoped_rows)
            self.assertEqual(len(distinct), 2)
            self.assertTrue(all(g["binding_blocker"] for g in distinct))

    def test_refresh_rejects_incompatible_lineage_and_stale_current_context(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("network access control"),
                review_db_path=f.tmp / "h1.sqlite", explicit_execution=True)
            c = snapshot["gap_rows"][0]["candidate"]
            old = legacy_attempt(f, c)
            wrong = deepcopy(c)
            wrong["provenance"][0]["job_content_hash"] = "different-job-content"
            seal_candidate(wrong)
            with self.assertRaisesRegex(ValueError, "current candidate lineage"):
                service.research.re_evaluate_saved_evidence(old, current_candidate=wrong, explicit_execution=True)
            with self.assertRaisesRegex(ValueError, "Candidate knowledge versions changed"):
                service.research.re_evaluate_saved_evidence(old, current_candidate=old["candidate"], explicit_execution=True)
            identity = service.production_identity()
            identity["taxonomy_fingerprint"] = "changed-content"
            with patch.object(service, "production_identity", return_value=identity), patch.object(service.research, "re_evaluate_saved_evidence") as native:
                with self.assertRaisesRegex(ValueError, "STALE"):
                    service.refresh_saved_research(snapshot, c["candidate_id"], explicit_execution=True, review_db_path=f.tmp / "h1.sqlite")
                native.assert_not_called()
            with self.assertRaisesRegex(ValueError, "Explicit"):
                service.refresh_saved_research(snapshot, c["candidate_id"], review_db_path=f.tmp / "h1.sqlite")
            edited = deepcopy(old)
            edited["research"]["raw_provider_evidence"]["results"][0]["content"] = "changed"
            edited.pop("research_result_id")
            service._seal(edited, "result_fingerprint")
            edited["research_result_id"] = "tqd3h1_" + edited["result_fingerprint"][:24]
            with self.assertRaisesRegex(ValueError, "Raw evidence fingerprint edited"):
                service.research.re_evaluate_saved_evidence(edited, current_candidate=c, explicit_execution=True)
            self.assertEqual(len(store.list_governed_research_results(db_path=f.tmp / "h1.sqlite")), 1)
            f.network_guard.assert_not_called()

    def test_ambiguous_current_lineage_remains_diagnostics_only(self):
        with PublicationFixture() as f:
            db = f.tmp / "h1.sqlite"
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("network access control"), review_db_path=db, explicit_execution=True)
            c = snapshot["gap_rows"][0]["candidate"]
            legacy_attempt(f, c)
            duplicate = deepcopy(snapshot["gap_rows"][0])
            duplicate["candidate"]["source_gap_ids"].append("another-current-scope")
            seal_candidate(duplicate["candidate"])
            duplicate["candidate_id"] = duplicate["candidate"]["candidate_id"]
            snapshot["gap_rows"].append(duplicate)
            service._seal(snapshot, "audit_fingerprint")
            groups = service.build_review_targets(snapshot, saved_rows=store.list_governed_research_results(db_path=db))
            self.assertEqual(len(groups), 1)
            self.assertIsNone(groups[0]["current_candidate"])
            self.assertIn("unambiguously", groups[0]["binding_blocker"])
            with self.assertRaisesRegex(ValueError, "current candidate lineage"):
                service.refresh_saved_research(snapshot, c["candidate_id"], explicit_execution=True, review_db_path=db)
            self.assertEqual(len(store.list_governed_research_results(db_path=db)), 1)

    def test_secondary_boundary_real_review_examples(self):
        good = ["network access control", "data analysis and insights", "microservices architecture", "cloud security", "distributed systems"]
        compound = [
            "critical infrastructure security implement robust security protocols to protect national infrastructure",
            "deploying and maintaining content management systems and web applications in the cloud",
            "experience debugging software hardware integration issues across embedded processors FPGA DSP and RF subsystems",
            "the code first entity framework and cloud deployment",
            "a good understanding of image processing and databases is an advantage",
            "data analysis and cloud security", "database design and cloud architecture"]
        with PublicationFixture():
            for text in good + compound:
                with self.subTest(text=text):
                    c = {"concept_key": text, "examples": [text], "candidate_route": "possible_new_capability"}
                    state, reason = service.capability_boundary(c)
                    self.assertEqual(state, service.RESEARCH_READY if text in good else service.NEEDS_DECOMPOSITION)
                    self.assertTrue(reason)
            state, _ = service.capability_boundary({"concept_key": "strong analytical debugging and problem solving skills"})
            self.assertEqual(state, service.REVIEW_FIX_LAYER)

    def test_tranche_exclusions_and_bulk_routing_are_read_only(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("distributed systems",
                "critical infrastructure security implement robust security protocols to protect national infrastructure"),
                review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            original = deepcopy(snapshot)
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            self.assertEqual([r["concept"] for r in tranche["targets"]], ["distributed systems"])
            self.assertEqual(len(tranche["excluded_targets"]), 1)
            self.assertEqual(tranche["excluded_targets"][0]["boundary_state"], service.NEEDS_DECOMPOSITION)
            cid = tranche["targets"][0]["candidate_id"]
            receipt = service.route_for_review(snapshot, [cid, cid], service.REVIEW_FIX_LAYER)
            self.assertEqual(receipt, service.route_for_review(snapshot, [cid], service.REVIEW_FIX_LAYER))
            routed = service.build_research_tranche(snapshot, explicit_creation=True, routing=[receipt])
            self.assertEqual(routed["targets"], [])
            self.assertEqual(next(row for row in routed["excluded_targets"] if row["candidate_id"] == cid)["boundary_state"], service.REVIEW_FIX_LAYER)
            self.assertEqual(snapshot, original)
            self.assertFalse((f.tmp / "missing.sqlite").exists())
            f.network_guard.assert_not_called()

    def test_audit_network_ban_is_enforced_and_restored(self):
        with PublicationFixture() as f:
            def forbidden(**kwargs):
                socket.socket.connect(None, ("fake", 0))
            with patch.object(service.gaps, "audit_corpus_resolution", side_effect=forbidden):
                with self.assertRaisesRegex(RuntimeError, "Maintenance audit is offline"):
                    service.run_corpus_audit(corpus=fixture_corpus(), explicit_execution=True)
            self.assertIs(socket.socket.connect, f.network_guard)
            f.network_guard.assert_not_called()

    def test_explicit_fake_research_persists_in_fresh_context_and_never_approves(self):
        from taxonomy_discovery.offline_execution import offline_execution, _reason
        with PublicationFixture() as f:
            db = f.tmp / "research.sqlite"
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("data analysis and insights"), review_db_path=db, explicit_execution=True)
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            selected = [tranche["targets"][0]["candidate_id"]]
            def fake(target):
                self.assertIsNone(_reason.get())
                return fake_raw("data analysis and insights")
            provider = Mock(side_effect=fake)
            plan = service.plan_research(snapshot, tranche, selected, review_db_path=db, transport=provider)
            provider.assert_not_called()
            self.assertEqual(plan["planned_tavily_calls"], 1)
            self.assertEqual(plan["execution_preview"][0]["execution_status"], "READY TO EXECUTE")
            with self.assertRaises(ValueError):
                service.execute_research(snapshot, tranche, selected, transport=provider, review_db_path=db)
            with self.assertRaisesRegex(ValueError, "plan changed"):
                service.execute_research(snapshot, tranche, selected, explicit_execution=True, transport=provider,
                    review_db_path=db, confirmed_plan_fingerprint="edited")
            provider.assert_not_called()
            with offline_execution("Offline corpus forbids network"):
                receipt = service.execute_research(snapshot, tranche, selected, explicit_execution=True, transport=provider,
                    review_db_path=db, confirmed_plan_fingerprint=plan["plan_fingerprint"])
            self.assertEqual(receipt["calls_completed"], 1)
            self.assertEqual(receipt["candidates_failed"], 0)
            self.assertFalse(receipt["approval"])
            provider.assert_called_once()
            saved = store.list_governed_research_results(db_path=db)
            self.assertEqual(len(saved), 1)
            self.assertFalse(saved[0]["result"]["approval"])
            self.assertFalse(saved[0]["draft"])
            self.assertNotEqual(saved[0]["review"].get("decision"), "approve_for_publication")
            self.assertEqual(f.real_registry.read_bytes(), f.real_registry_bytes)
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_missing_provider_preview_and_execution_agree_without_receipt_writes(self):
        with PublicationFixture() as f, patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
            db = f.tmp / "missing.sqlite"
            snapshot = service.run_corpus_audit(corpus=fixture_corpus(), review_db_path=db, explicit_execution=True)
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            selected = [tranche["targets"][0]["candidate_id"]]
            plan = service.plan_research(snapshot, tranche, selected, review_db_path=db)
            self.assertIn("TAVILY_API_KEY", plan["provider_blocker"])
            self.assertEqual(plan["execution_preview"][0]["execution_status"], "BLOCKED")
            with self.assertRaisesRegex(ValueError, "TAVILY_API_KEY"):
                service.execute_research(snapshot, tranche, selected, review_db_path=db, explicit_execution=True)
            self.assertFalse(db.exists())
            f.network_guard.assert_not_called()

    def test_stale_research_remains_refresh_review_with_zero_calls(self):
        with PublicationFixture() as f:
            source = fixture_corpus("crystalline computing protocols")
            snapshot = service.run_corpus_audit(corpus=source, explicit_execution=True, review_db_path=f.tmp / "h1.sqlite")
            c = snapshot["gap_rows"][0]["candidate"]
            result = execute(f, c, fake_raw(c["concept_key"]))
            from pathlib import Path
            authority = Path(result["authority_registry_path"])
            payload = json.loads(authority.read_text())
            payload["version"] = "changed-test-authority"
            authority.write_text(json.dumps(payload))
            snapshot = service.run_corpus_audit(corpus=source, explicit_execution=True, review_db_path=f.tmp / "h1.sqlite")
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            provider = Mock(side_effect=AssertionError("No duplicate research"))
            selected = [c["candidate_id"]]
            plan = service.plan_research(snapshot, tranche, selected, transport=provider, review_db_path=f.tmp / "h1.sqlite")
            self.assertEqual(plan["planned_tavily_calls"], 0)
            self.assertEqual(plan["execution_preview"][0]["execution_status"], "EXISTING RESEARCH / REFRESH REQUIRED")
            receipt = service.execute_research(snapshot, tranche, selected, explicit_execution=True, transport=provider,
                confirmed_plan_fingerprint=plan["plan_fingerprint"], review_db_path=f.tmp / "h1.sqlite")
            provider.assert_not_called()
            self.assertEqual(len(store.list_governed_research_results(db_path=f.tmp / "h1.sqlite")), 1)
            self.assertEqual(receipt["calls_attempted"], 0)

    def test_failed_provider_saves_diagnostic_without_eligible_result(self):
        with PublicationFixture() as f:
            db = f.tmp / "research.sqlite"
            snapshot = service.run_corpus_audit(corpus=fixture_corpus(), review_db_path=db, explicit_execution=True)
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            selected = [tranche["targets"][0]["candidate_id"]]
            receipt = service.execute_research(snapshot, tranche, selected, explicit_execution=True,
                transport=Mock(side_effect=RuntimeError("Provider denied test request")), review_db_path=db)
            self.assertEqual(receipt["candidates_failed"], 1)
            self.assertIn("Provider denied", receipt["outcomes"][selected[0]]["error"])
            self.assertFalse(receipt["approval"])
            self.assertEqual(store.list_governed_research_results(db_path=db), [])

    def test_audit_requires_explicit_execution(self):
        with self.assertRaises(ValueError):
            service.run_corpus_audit(corpus={})

    def test_read_only_audit_reuses_native_consolidation_and_full_identity(self):
        with PublicationFixture() as f:
            source = fixture_corpus("React", "Python", "BigFix", "distributed systems")
            original = deepcopy(source)
            with patch.object(service.gaps, "audit_corpus_resolution", wraps=service.gaps.audit_corpus_resolution) as native:
                first = service.run_corpus_audit(corpus=source, review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            second = service.run_corpus_audit(corpus=source, review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            native.assert_called_once_with(corpus=source, replay_current=True)
            self.assertEqual(first["gap_rows"], second["gap_rows"])
            self.assertEqual(source, original)
            self.assertEqual(first["model_calls"], 0)
            self.assertEqual(first["network_calls"], 0)
            self.assertEqual(first["production_writes"], 0)
            self.assertFalse((f.tmp / "missing.sqlite").exists())
            self.assertEqual(f.real_registry.read_bytes(), f.real_registry_bytes)
            self.assertEqual(first["manifest"]["scoring_version"], service.current_match_versions()["scoring_version"])
            self.assertTrue(service.currentness(first)["current"])
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()
            f.embedding_guard.assert_not_called()

    def test_fix_layer_separation_and_exact_provenance(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("Python", "C#", "distributed systems", "Python and SQL"),
                review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            by_concept = {r["concept"]: r for r in snapshot["gap_rows"]}
            self.assertEqual(by_concept["python"]["fix_layer"], service.IDENTITY_GAP)
            self.assertEqual(by_concept["c#"]["fix_layer"], service.RELATIONSHIP_GAP)
            row = by_concept["distributed systems"]
            self.assertEqual(row["fix_layer"], service.CAPABILITY_GAP)
            self.assertTrue(row["requirements"])
            detail = service.get_concept_detail(snapshot, row["candidate_id"], review_db_path=f.tmp / "missing.sqlite")
            self.assertEqual(detail["requirements"][0]["requirement_text"], "distributed systems")
            self.assertEqual(detail["requirements"][0]["job_id"], 3)
            self.assertEqual(detail["candidate"]["provenance"][0]["requirement_id"], detail["requirements"][0]["requirement_id"])

    def test_tranche_is_deterministic_bounded_and_actual_gaps_only(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("distributed systems", "cloud security", "Python", "BigFix"),
                review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            first = service.build_research_tranche(snapshot, explicit_creation=True)
            self.assertEqual(first, service.build_research_tranche(snapshot, explicit_creation=True))
            self.assertTrue(first["targets"])
            self.assertTrue(all(r["fix_layer"] == service.CAPABILITY_GAP for r in first["targets"]))
            self.assertEqual(len(first["targets"]), len({r["candidate_id"] for r in first["targets"]}))
            self.assertEqual(first["provider_calls"], 0)
            for size in (0, 21, True):
                with self.assertRaises(ValueError):
                    service.build_research_tranche(snapshot, size=size, explicit_creation=True)
            with self.assertRaises(ValueError):
                service.build_research_tranche(snapshot)
            self.assertEqual(len(service.build_research_tranche(snapshot, size=1, explicit_creation=True)["targets"]), 1)

    def test_noise_parsing_and_evidence_triage_never_enters_tranche(self):
        with PublicationFixture() as f:
            source = fixture_corpus("distributed systems")
            audit = service.gaps.audit_corpus_resolution(corpus=source, replay_current=True)
            audit["top_20_taxonomy_maintenance_priorities"].append({
                "candidate_id": "existing_capability:frontend.ui_development",
                "concept": "frontend.ui_development", "operational_route": "existing_capability_evidence_boundary",
                "usefulness_reasons": ["native cap diagnostic"], "occurrences": 1, "job_count": 1,
                "required_core_impact": 1, "maintenance_priority_score": 110})
            # The adapter consumes existing triage, without reconstructing it.
            rows = service.list_gap_rows(audit, saved_rows=[], publications=[])
            self.assertEqual(next(r for r in rows if r["candidate"] is None)["fix_layer"], service.EVIDENCE_PROBLEM)
            self.assertEqual(service.ROUTE_LAYERS["noise_or_non_capability"], service.NOISE)
            self.assertEqual(service.ROUTE_LAYERS["needs_decomposition"], service.PARSING_PROBLEM)

    def test_compound_activity_scope_uses_native_readiness_boundary(self):
        with PublicationFixture() as f:
            text = "build test deploy maintain distributed software services"
            snapshot = service.run_corpus_audit(corpus=fixture_corpus(text, "distributed systems"),
                review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            compound = next(r for r in snapshot["gap_rows"] if r["concept"] == text)
            self.assertEqual(compound["fix_layer"], service.CAPABILITY_GAP)
            self.assertEqual(compound["boundary_state"], service.NEEDS_DECOMPOSITION)
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            self.assertNotIn(compound["candidate_id"], [r["candidate_id"] for r in tranche["targets"]])
            self.assertTrue(any(r["concept"] == "distributed systems" for r in tranche["targets"]))

    def test_existing_backlog_is_a_reference_not_a_second_target(self):
        with PublicationFixture() as f:
            source = fixture_corpus("crystalline computing protocols")
            snapshot = service.run_corpus_audit(corpus=source, review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            c = snapshot["gap_rows"][0]["candidate"]
            result = execute(f, c, fake_raw(c["concept_key"], c["concept_key"] + " is an engineering capability for implementing distinct computing protocols."))
            updated = service.run_corpus_audit(corpus=source, review_db_path=f.tmp / "h1.sqlite", explicit_execution=True)
            self.assertEqual(updated["gap_rows"][0]["research_targets"], [result["research_result_id"]])
            tranche = service.build_research_tranche(updated, explicit_creation=True)
            self.assertEqual(len(tranche["targets"]), 1)
            self.assertEqual(len(store.list_governed_research_results(db_path=f.tmp / "h1.sqlite")), 1)

    def test_changed_versions_corpus_and_edited_artifacts_fail_closed(self):
        with PublicationFixture() as f:
            source = fixture_corpus()
            snapshot = service.run_corpus_audit(corpus=source, review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            identity = service.production_identity()
            identity["git_head"] = "different"
            with patch.object(service, "production_identity", return_value=identity):
                self.assertFalse(service.currentness(snapshot)["current"])
                with self.assertRaises(ValueError):
                    service.build_research_tranche(snapshot, explicit_creation=True)
            edited = deepcopy(snapshot)
            edited["gap_rows"][0]["fix_layer"] = service.CAPABILITY_GAP + "edited"
            self.assertFalse(service.currentness(edited)["current"])
            with patch.object(service, "export_saved_corpus", return_value=source):
                stored = service.run_corpus_audit(review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            changed = deepcopy(source)
            changed["jobs"][0]["job_content_hash"] = "changed"
            with patch.object(service, "export_saved_corpus", return_value=changed):
                self.assertFalse(service.currentness(stored)["current"])

    def test_missing_frozen_inputs_block_tranche_and_validation(self):
        with PublicationFixture() as f:
            source = fixture_corpus()
            source["jobs"][0]["frozen_inputs"] = {}
            snapshot = service.run_corpus_audit(corpus=source, review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            self.assertFalse(service.currentness(snapshot)["current"])
            with self.assertRaises(ValueError):
                service.build_research_tranche(snapshot, explicit_creation=True)

    def test_selected_scope_and_export_bundle(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("distributed systems", "Python"), job_ids=[1],
                review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            self.assertEqual(snapshot["manifest"]["job_ids"], [1])
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            exported = service.export_audit_bundle(snapshot, tranche=tranche)
            with zipfile.ZipFile(io.BytesIO(exported["zip"])) as archive:
                self.assertEqual(len(archive.namelist()), 7)
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest, snapshot["manifest"])
                self.assertIn("distributed systems", archive.read("consolidated_gaps.csv").decode())
                exported_rows = json.loads(archive.read("consolidated_gaps.json"))
                self.assertTrue(exported_rows[0]["contributing_requirements"][0]["requirement_id"])

    def test_research_is_explicit_selected_and_delegates_to_native_executor(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus(), review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            tranche = service.build_research_tranche(snapshot, explicit_creation=True)
            selected = [tranche["targets"][0]["candidate_id"]]
            with patch.object(service.bulk, "execute_bulk_plan", return_value={"fake": True}) as executor:
                with self.assertRaises(ValueError):
                    service.execute_research(snapshot, tranche, selected)
                executor.assert_not_called()
                service.execute_research(snapshot, tranche, selected, explicit_execution=True, transport=Mock(), review_db_path=f.tmp / "missing.sqlite")
                self.assertEqual(executor.call_count, 1)
                self.assertTrue(executor.call_args.kwargs["explicit_execution"])
            with self.assertRaises(ValueError):
                service.plan_research(snapshot, tranche, ["unknown"], review_db_path=f.tmp / "missing.sqlite")

    def test_native_validation_approval_boundary_receipts_and_no_production_writes(self):
        with PublicationFixture() as f:
            snapshot = service.run_corpus_audit(corpus=fixture_corpus("crystalline computing protocols"),
                review_db_path=f.tmp / "missing.sqlite", explicit_execution=True)
            c = snapshot["gap_rows"][0]["candidate"]
            subject = c["concept_key"]
            result = execute(f, c, fake_raw(subject, subject + " is an engineering capability for implementing distinct computing protocols."))
            draft = service.research.create_draft(result, explicit_creation=True, capability_fields=capability_fields(subject))
            db = f.tmp / "h1.sqlite"
            store.save_governed_research_draft(result, draft, db_path=db, proposal_db_path=f.proposal_db)
            rid = result["research_result_id"]
            with self.assertRaises(ValueError):
                service.run_candidate_validation(snapshot, [rid], explicit_execution=True, review_db_path=db)
            preview = service.run_candidate_validation(snapshot, [rid], explicit_execution=True, approved=False, review_db_path=db)
            self.assertEqual(preview["production_writes"], 0)
            self.assertTrue(preview["requirement_receipts"])
            self.assertGreaterEqual(preview["newly_resolved"], 1)
            self.assertEqual(len(preview["before_ranking"]), 1)
            self.assertEqual(len(preview["after_ranking"]), 1)
            store.save_governed_temporary_impact(rid, preview["native"]["per_item"][0]["report"], db_path=db)
            store.save_governed_research_review(rid, result_fingerprint=result["result_fingerprint"],
                decision="approve_for_publication", reviewer="fixture reviewer", draft=draft,
                regression=preview["native"]["per_item"][0]["report"], db_path=db)
            validation = service.run_candidate_validation(snapshot, [rid], explicit_execution=True, review_db_path=db)
            self.assertTrue(validation["approved_validation"])
            self.assertNotIn("test.crystalline_computing", service.get_default_taxonomy().by_id())
            self.assertEqual(f.real_registry.read_bytes(), f.real_registry_bytes)
            with patch.object(service.publication, "publish_approved_change") as publish:
                with self.assertRaises(ValueError):
                    service.publish_validated(snapshot, validation, rid, review_db_path=db)
                publish.assert_not_called()
            self.assertFalse(service.publication_preflight(snapshot, preview, rid, review_db_path=db)["ready"])
            preflight = service.publication_preflight(snapshot, validation, rid, review_db_path=db,
                proposal_db_path=f.proposal_db)
            self.assertTrue(preflight["ready"], preflight["blockers"])
            with patch.object(service.publication, "publish_approved_change", return_value={"fake": "receipt"}) as publish:
                self.assertEqual(service.publish_validated(snapshot, validation, rid, explicit_publish=True,
                    review_db_path=db, proposal_db_path=f.proposal_db), {"fake": "receipt"})
                publish.assert_called_once_with(rid, explicit_publish=True, db_path=db, proposal_db_path=f.proposal_db)
            edited = deepcopy(validation)
            edited["draft_fingerprints"][rid] = "changed"
            self.assertFalse(service.publication_preflight(snapshot, edited, rid, review_db_path=db)["ready"])
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
