"""Focused offline tests for corpus coverage and local-first gap resolution."""
from __future__ import annotations

from copy import deepcopy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from job_discovery.matching import current_match_versions
from taxonomy_discovery import corpus_gap_resolution as gaps
from taxonomy_discovery.regression_corpus import CORPUS_VERSION
from tests.tqd3_publication_fixture_support import PublicationFixture


def requirement(text, rid, *, importance="required"):
    return {
        "job_id": 1,
        "snapshot_id": 10,
        "requirement_id": rid,
        "requirement_text": text,
        "importance": importance,
        "score_eligible": True,
        "resolution_status": "unresolved",
        "resolution_source": "unresolved",
        "technology_registry_resolution": {"status": "unresolved"},
    }


def corpus(*texts):
    versions = current_match_versions()
    rows = [requirement(text, f"req-{index}") for index, text in enumerate(texts, 1)]
    stable_rows = [{"requirement_id": row["requirement_id"], "atomic_focus": row["requirement_text"],
                    "importance": row["importance"], "score_eligible": True,
                    "group_weight_fraction": 1.0} for row in rows]
    return {
        "corpus_version": CORPUS_VERSION,
        "jobs": [{
            "job_id": 1,
            "snapshot_id": 10,
            "job_content_hash": "hash",
            "versions": {
                "scoring_version": versions["scoring_version"],
                "taxonomy_version": versions["taxonomy_version"],
                "technology_registry_version": versions["technology_registry_version"],
            },
            "requirements": rows,
            "baseline_stable_analysis": {"canonical_requirements": stable_rows},
        }],
        "job_count": 1,
        "read_only": True,
    }


class CorpusGapAuditTests(unittest.TestCase):
    def test_whole_corpus_uses_current_production_resolver_and_exact_routes(self):
        fixture = corpus(
            "React",
            "Python",
            "C#",
            "BigFix",
            "distributed systems",
            "only shortlisted candidates will be notified",
            "implement access controls and audit logging for sensitive personal data",
        )
        with PublicationFixture() as f:
            original = deepcopy(fixture)
            report = gaps.audit_corpus_resolution(corpus=fixture)
            self.assertEqual(fixture, original)
            self.assertEqual(report["summary"]["total_requirements"], 7)
            self.assertGreaterEqual(report["summary"]["resolved_scorable_requirements"], 1)
            routes = {row["concept"]: row["operational_route"] for row in report["queue"]
                      if not row.get("parent_candidate_id")}
            self.assertEqual(routes["bigfix"], "technology_identity_missing")
            self.assertEqual(routes["c#"], "technology_relationship_missing")
            self.assertEqual(routes["distributed systems"], "possible_new_capability")
            self.assertEqual(routes["only shortlisted candidates will be notified"], "noise_or_non_capability")
            self.assertNotEqual(routes["implement access controls and audit logging for sensitive personal data"],
                                "noise_or_non_capability")
            self.assertTrue(set(routes.values()).issubset(set(gaps.OPERATIONAL_ROUTES)))
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_compound_parent_retains_provenance_and_children_reenter_same_queue(self):
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=corpus("Python and SQL"))
        parent = next(row for row in report["queue"] if not row.get("parent_candidate_id"))
        self.assertEqual(parent["operational_route"], "needs_decomposition")
        children = [row for row in report["queue"] if row.get("parent_candidate_id") == parent["candidate_id"]]
        self.assertEqual({row["concept"] for row in children}, {"python", "sql"})
        self.assertTrue(all(row["provenance"][0]["parent_candidate_id"] == parent["candidate_id"] for row in children))
        self.assertTrue(all(row["operational_route"] == "technology_identity_missing" for row in children))

    def test_resolved_or_noise_children_cannot_reclassify_parent(self):
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=corpus("React and UnknownNovelTool"))
        parent = next(row for row in report["queue"] if not row.get("parent_candidate_id"))
        children = [row for row in report["queue"] if row.get("parent_candidate_id") == parent["candidate_id"]]
        self.assertNotIn("react", {row["concept"] for row in children})
        self.assertTrue(children)
        self.assertTrue(all(not row["local_safe"] for row in children
                            if row["operational_route"] == "noise_or_non_capability"))

    def test_open_ended_example_list_cannot_claim_complete_decomposition(self):
        text = ("proven experience building efficient secure restful apis with frameworks such as "
                "express js fastify fastapi spring boot or equivalent enterprise grade tools")
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=corpus(text))
        parent = next(row for row in report["queue"] if not row.get("parent_candidate_id"))
        self.assertEqual(parent["operational_route"], "needs_decomposition")
        self.assertFalse(parent["local_safe"])
        self.assertIn("Open-ended example list", parent["local_plan"]["reason"])

    def test_arbitrary_prose_is_not_split_and_cloud_identity_does_not_force_mapping(self):
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=corpus(
                "design reliable systems and communicate tradeoffs with stakeholders",
                "manage your own time and changing priorities",
                "AWS / Azure / GCP",
            ))
        prose = next(row for row in report["queue"] if row["concept"].startswith("design reliable"))
        self.assertNotEqual(prose["operational_route"], "needs_decomposition")
        generic = next(row for row in report["queue"] if row["concept"].startswith("manage your own time"))
        self.assertEqual(generic["operational_route"], "noise_or_non_capability")
        cloud_parent = next(row for row in report["queue"] if not row.get("parent_candidate_id") and "aws" in row["concept"])
        self.assertEqual(cloud_parent["operational_route"], "needs_decomposition")
        cloud_children = [row for row in report["queue"] if row.get("parent_candidate_id") == cloud_parent["candidate_id"]]
        self.assertTrue(cloud_children)
        self.assertTrue(all((row["local_plan"].get("identity") or {}).get("canonical_name") for row in cloud_children))
        self.assertTrue(all("relationship" not in row["local_plan"] for row in cloud_children))

    def test_coverage_uses_production_importance_weights_without_changing_scoring(self):
        fixture = corpus("React", "BigFix")
        fixture["jobs"][0]["requirements"][1]["importance"] = "preferred"
        fixture["jobs"][0]["baseline_stable_analysis"]["canonical_requirements"][1]["importance"] = "preferred"
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=fixture)
        summary = report["summary"]
        self.assertEqual(summary["required_core_weighted_coverage"]["percent"], 100.0)
        self.assertEqual(summary["supporting_preferred_weighted_coverage"]["percent"], 0.0)
        self.assertFalse(report["scoring_semantics_changed"])

    def test_each_requirement_calls_shared_production_resolver(self):
        fixture = corpus("React", "BigFix")
        native = gaps.resolve_requirement_with_production_knowledge
        with PublicationFixture(), patch.object(
            gaps, "resolve_requirement_with_production_knowledge", wraps=native
        ) as resolver:
            gaps.audit_corpus_resolution(corpus=fixture)
        self.assertEqual(resolver.call_count, 2)

    def test_hard_cases_are_valid_existing_governed_research_candidates(self):
        from taxonomy_discovery.governed_research import research_plan, validate_candidate
        from taxonomy_discovery.research_readiness import audit_candidate
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=corpus("BigFix", "distributed systems"))
            by_concept = {row["concept_key"]: row for row in report["candidates"]}
            bigfix = by_concept["bigfix"]
            distributed = by_concept["distributed systems"]
            validate_candidate(bigfix)
            validate_candidate(distributed)
            bigfix_ready = audit_candidate(bigfix, queue_state="external_research_required")
            distributed_ready = audit_candidate(distributed, queue_state="external_research_required")
            plan = research_plan([bigfix, distributed], selected_candidate_ids=[
                bigfix["candidate_id"], distributed["candidate_id"]])
        self.assertEqual(bigfix["candidate_route"], "technology_identity")
        self.assertEqual(bigfix_ready["research_readiness"], "identity_research_ready")
        self.assertEqual(distributed["candidate_route"], "possible_new_capability")
        self.assertEqual(distributed_ready["research_readiness"], "capability_research_ready")
        purposes = {target["subject"]: target["research_purpose"] for target in plan["targets"]}
        self.assertEqual(purposes["BigFix"], "verify_technology_identity")
        self.assertEqual(purposes["distributed systems"], "research_capability_definition_and_boundaries")
        self.assertTrue(all(target["external_requested"] for target in plan["targets"]))


class LocalProposalAndSeedTests(unittest.TestCase):
    def test_bundled_seed_is_broad_unique_and_keeps_required_top_corpus_technologies(self):
        with PublicationFixture():
            report = gaps.load_bulk_technology_seed()
        names = {row["canonical_name"] for row in report["entries"]}
        self.assertEqual(report["seed_technology_count"], report["unique_canonical_technologies"])
        self.assertGreaterEqual(report["unique_canonical_technologies"], 100)
        self.assertGreater(report["aliases_proposed"], report["unique_canonical_technologies"])
        self.assertTrue({"Python", "SQL", "Amazon Web Services", "Microsoft Azure", "JavaScript",
                         "MongoDB", "TypeScript", "C#", ".NET", "Elasticsearch",
                         "Google Cloud Platform", "Java", "Node.js", "Ansible"}.issubset(names))
        self.assertEqual(report["alias_collisions"], [])

    def test_seed_rejects_duplicate_identity_and_alias_collision(self):
        duplicate = {"entries": [
            {"canonical_name": "Fixture Tool", "aliases": ["Fixture Tool"], "technology_kind": "tool",
             "relationship_hypotheses": []},
            {"canonical_name": "fixture tool", "aliases": ["Other"], "technology_kind": "tool",
             "relationship_hypotheses": []},
        ]}
        collision = {"entries": [
            {"canonical_name": "Fixture One", "aliases": ["Shared Alias"], "technology_kind": "tool",
             "relationship_hypotheses": []},
            {"canonical_name": "Fixture Two", "aliases": ["Shared Alias"], "technology_kind": "tool",
             "relationship_hypotheses": []},
        ]}
        with PublicationFixture():
            with self.assertRaisesRegex(ValueError, "Duplicate bulk seed identity"):
                gaps.import_bulk_seed(duplicate)
            with self.assertRaisesRegex(ValueError, "alias collision"):
                gaps.import_bulk_seed(collision)

    def test_bootstrap_separates_identity_relationship_and_broad_platform(self):
        seed = {"entries": [
            {"canonical_name": "Fixture Observe", "aliases": ["Fixture Observe"], "technology_kind": "tool",
             "category": "observability", "confidence": 1.0, "review_status": "proposed",
             "relationship_hypotheses": [{"capability_id": "devops.observability",
                 "reason": "Focused monitoring fixture", "taxonomy_boundary_checks": ["monitoring only"],
                 "safe_for_local_review": True, "external_research_recommended": False}]},
            {"canonical_name": "Fixture Cloud", "aliases": ["Fixture Cloud"], "technology_kind": "platform",
             "category": "cloud", "confidence": 1.0, "review_status": "proposed",
             "relationship_hypotheses": []},
        ]}
        with PublicationFixture() as f:
            audit = gaps.audit_corpus_resolution(corpus=corpus("Fixture Observe", "Fixture Cloud"))
            plan = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
            observe_identity = next(row for row in plan["identity_only_proposals"]
                                    if row["technology"] == "Fixture Observe")
            observe_relationship = next(row for row in plan["safe_relationship_proposals"]
                                        if row["technology"] == "Fixture Observe")
            cloud_identity = next(row for row in plan["identity_only_proposals"]
                                  if row["technology"] == "Fixture Cloud")
            selected = gaps.select_bulk_bootstrap_proposals(
                plan, selected_proposal_ids=[observe_relationship["proposal_id"]], explicit_creation=True)
            preview = gaps.preview_local_resolution(audit, selected["proposals"])
        self.assertIn(observe_identity["proposal_id"], observe_relationship["depends_on_proposal_ids"])
        self.assertIn(observe_identity["proposal_id"], selected["dependency_proposal_ids"])
        self.assertNotIn("relationship", cloud_identity["proposed_change"])
        self.assertEqual(preview["would_resolve_after"], 1)
        self.assertFalse(preview["scoring_influence"])
        self.assertEqual(preview["production_mutations"], 0)
        f.network_guard.assert_not_called()
        f.model_guard.assert_not_called()

    def test_conflicting_relationships_and_missing_capability_fail_closed(self):
        seed = {"entries": [
            {"canonical_name": "Fixture Ambiguous", "aliases": ["Fixture Ambiguous"], "technology_kind": "platform",
             "relationship_hypotheses": [
                 {"capability_id": "devops.observability", "safe_for_local_review": True},
                 {"capability_id": "data.processing", "safe_for_local_review": True},
             ]},
            {"canonical_name": "Fixture IaC", "aliases": ["Fixture IaC"], "technology_kind": "tool",
             "relationship_hypotheses": [], "gap_route": "possible_new_capability"},
        ]}
        with PublicationFixture():
            audit = gaps.audit_corpus_resolution(corpus=corpus("Fixture Ambiguous", "Fixture IaC"))
            plan = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
        manual = plan["groups"]["E_ambiguous_manual"]
        new_capability = plan["groups"]["D_possible_new_capability"]
        self.assertTrue(any(row["technology"] == "Fixture Ambiguous" and
                            row["reason"] == "conflicting_relationship_candidates" for row in manual))
        self.assertTrue(any(row["technology"] == "Fixture IaC" for row in new_capability))
        self.assertFalse(any(row["technology"] == "Fixture Ambiguous"
                             for row in plan["safe_relationship_proposals"]))

    def test_bootstrap_curve_is_temporary_and_does_not_mutate_production_or_scoring(self):
        seed = {"entries": [{
            "canonical_name": "BigFix", "aliases": ["BigFix"], "technology_kind": "tool",
            "relationship_hypotheses": [{"capability_id": "devops.observability",
                "reason": "Focused monitoring fixture", "taxonomy_boundary_checks": ["monitoring only"],
                "safe_for_local_review": True, "external_research_recommended": False}],
        }]}
        with PublicationFixture() as f:
            from tailoring import capability_taxonomy
            before_registry = f.real_registry.read_bytes()
            taxonomy_path = Path(capability_taxonomy.TAXONOMY_PATH)
            before_taxonomy = taxonomy_path.read_bytes()
            audit = gaps.audit_corpus_resolution(corpus=corpus("BigFix"))
            plan = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
            preview = gaps.preview_bulk_technology_bootstrap(audit, plan)
            self.assertEqual(f.real_registry.read_bytes(), before_registry)
            self.assertEqual(taxonomy_path.read_bytes(), before_taxonomy)
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()
        stages = {row["stage"]: row for row in preview["coverage_curve"]}
        self.assertEqual(stages["current_production"]["overall_percent"], 0.0)
        self.assertEqual(stages["identity_only_proposals"]["overall_percent"], 0.0)
        self.assertEqual(stages["safe_relationship_proposals"]["overall_percent"], 100.0)
        self.assertEqual(preview["newly_scorable_requirements"], 1)
        self.assertEqual(preview["production_mutations"], 0)
        self.assertFalse(preview["scoring_influence"])
        self.assertFalse(preview["score_changes_claimed"])

    def test_common_identity_is_local_proposal_with_zero_network_and_no_mapping(self):
        with PublicationFixture() as f:
            audit = gaps.audit_corpus_resolution(corpus=corpus("Python"))
            queue = gaps.build_gap_resolution_queue(audit)
            row = next(item for item in queue["rows"] if item["concept"] == "python")
            self.assertTrue(row["local_safe"])
            self.assertFalse(row["external_research_required"])
            outcome = gaps.create_local_proposals(queue, selected_candidate_ids=[row["candidate_id"]], explicit_creation=True)
            proposal = outcome["proposals"][0]
            handoff = gaps.build_native_regression_handoff(outcome["proposals"])
            self.assertEqual(proposal["resolution_type"], "add_technology_identity")
            self.assertNotIn("relationship", proposal["proposed_change"])
            self.assertFalse(proposal["approval"])
            self.assertFalse(proposal["publication"])
            self.assertTrue(handoff["uses_existing_bulk_regression"])
            self.assertEqual(handoff["result_drafts"][0]["draft"]["kind"], "technology")
            self.assertEqual(handoff["result_drafts"][0]["draft"]["proposal_bundle"]["proposals"][0]["proposal_classification"],
                             "recognized_unmapped")
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_local_creation_is_explicit_and_read_only_preview_uses_native_overlay(self):
        with PublicationFixture() as f:
            audit = gaps.audit_corpus_resolution(corpus=corpus("Node.js"))
            seed = {"entries": [{"canonical_name": "Node.js", "aliases": ["Node.js", "NodeJS"],
                     "technology_kind": "runtime", "relationship_hypotheses": [{"capability_id": "backend.api_development"}]}]}
            queue = gaps.build_gap_resolution_queue(audit, bulk_seed=seed)
            seed_row = next(row for row in queue["rows"] if row["source"] == "bulk_seed")
            with self.assertRaisesRegex(ValueError, "Explicit"):
                gaps.create_local_proposals(queue, selected_candidate_ids=[seed_row["candidate_id"]])
            before_registry = f.real_registry.read_bytes()
            outcome = gaps.create_local_proposals(queue, selected_candidate_ids=[seed_row["candidate_id"]], explicit_creation=True)
            preview = gaps.preview_local_resolution(audit, outcome["proposals"])
            self.assertEqual(preview["would_resolve_after"], 1)
            self.assertEqual(preview["potential_new_matches"], 1)
            self.assertFalse(preview["scoring_influence"])
            self.assertFalse(preview["score_changes_claimed"])
            self.assertEqual(preview["production_mutations"], 0)
            self.assertEqual(f.real_registry.read_bytes(), before_registry)
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()

    def test_seed_validation_is_dry_run_and_preserves_provenance(self):
        payload = {"entries": [{"canonical_name": "FixtureDB", "aliases": ["FixtureDB"],
                    "technology_kind": "product", "relationship_hypotheses": []}]}
        with PublicationFixture():
            report = gaps.import_bulk_seed(payload)
            audit = gaps.audit_corpus_resolution(corpus=corpus("BigFix"))
            queue = gaps.build_gap_resolution_queue(audit, bulk_seed=payload)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["production_mutations"], 0)
        seeded = next(row for row in queue["rows"] if row["source"] == "bulk_seed")
        self.assertEqual(seeded["provenance"][0]["source"], "bulk_seed")
        self.assertEqual(queue["production_mutations"], 0)

    def test_noise_and_decomposition_proposals_never_publish_or_approve(self):
        with PublicationFixture():
            audit = gaps.audit_corpus_resolution(corpus=corpus(
                "only shortlisted candidates will be notified", "Python and SQL"))
            queue = gaps.build_gap_resolution_queue(audit)
            selected = [row["candidate_id"] for row in queue["rows"]
                        if not row.get("parent_candidate_id") and row["local_safe"]]
            outcome = gaps.create_local_proposals(queue, selected_candidate_ids=selected, explicit_creation=True)
            preview = gaps.preview_local_resolution(audit, outcome["proposals"])
        self.assertEqual({p["resolution_type"] for p in outcome["proposals"]},
                         {"mark_noise_non_capability", "deterministic_decomposition"})
        self.assertFalse(outcome["approval"])
        self.assertFalse(outcome["publication"])
        self.assertEqual(preview["coverage_before_percent"], preview["projected_coverage_after_percent"])
        self.assertEqual(preview["would_resolve_after"], 0)

    def test_untrusted_broad_mining_candidate_enters_existing_identity_research(self):
        from taxonomy_discovery.broad_mining_candidates import extract_broad_mining_candidates
        from taxonomy_discovery.governed_research import validate_candidate
        raw = {"provider_request_id": "saved-request", "target_id": "target-1", "seed_id": "seed-1",
               "domain": "Messaging", "structured_output": {"technologies": [{
                   "canonical_name": "Fixture Novel Broker", "entity_type": "platform",
                   "primary_purpose": "Messaging", "adoption_evidence": "Saved evidence"}]}}
        with PublicationFixture():
            broad = extract_broad_mining_candidates(raw)
            audit = gaps.audit_corpus_resolution(corpus=corpus("React"))
            queue = gaps.build_gap_resolution_queue(audit, broad_candidates=broad)
            row = next(item for item in queue["rows"] if item["source"] == "broad_mining")
            validate_candidate(row["candidate"])
        self.assertEqual(row["operational_route"], "technology_identity_missing")
        self.assertEqual(row["candidate"]["candidate_route"], "technology_identity")
        self.assertTrue(row["external_research_required"])
        self.assertFalse(row["local_safe"])
        self.assertEqual(row["provenance"][0]["provider_request_ids"], ["saved-request"])


class MaintenanceUIContractTests(unittest.TestCase):
    def test_ui_uses_one_maintenance_workflow_and_passive_render_executes_nothing(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        from tests.test_tqd3_bulk_candidate_operations import BulkFakeStreamlit
        st = BulkFakeStreamlit()
        with patch.dict(sys.modules, {"streamlit": st}), \
             patch("taxonomy_discovery.corpus_gap_resolution.audit_corpus_resolution") as audit, \
             patch("taxonomy_discovery.governed_research.prepare_gap_review") as prepare:
            ui.render_bulk_candidate_operations()
        audit.assert_not_called()
        prepare.assert_not_called()
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("Taxonomy Knowledge Maintenance", rendered)
        source = Path(ui.__file__).read_text(encoding="utf-8")
        for label in ("A. Corpus Coverage", "B. Unresolved Gaps", "C. Resolve Batch",
                      "D. Needs Research", "E. Proposals / regression", "F. Review / Publish"):
            self.assertIn(label, source)
        self.assertIn("bulk.preview_bulk_regression", source)
        self.assertIn("Prepare bundled technology bootstrap", source)
        self.assertIn("Bulk review selection · identity-only safe and relationship-safe groups", source)


if __name__ == "__main__":
    unittest.main()

