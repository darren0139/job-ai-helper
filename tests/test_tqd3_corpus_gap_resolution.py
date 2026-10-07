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


def with_saved_evidence(fixture, *evidence_texts):
    updated = deepcopy(fixture)
    profile = {
        "education": [], "experience": [], "projects": [],
        "skills": {"fixture": list(evidence_texts)},
    }
    updated["jobs"][0]["frozen_inputs"] = {
        "context": {
            "resume_profile": profile,
            "raw_resume_text": "\n".join(evidence_texts),
        }
    }
    updated["jobs"][0]["baseline_stable_analysis"]["canonicalisation_debug"] = {
        "acronym_map": {}
    }
    return updated


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


class JobMatchHealthReportingTests(unittest.TestCase):
    @staticmethod
    def _set_scoring_row(fixture, index, *, label="none", evidence=False, cap_status="unrecognised"):
        row = fixture["jobs"][0]["baseline_stable_analysis"]["canonical_requirements"][index]
        row.update({
            "match_label": label,
            "match_value": {"none": 0.0, "weak": 0.2, "transferable": 0.55, "direct": 1.0}[label],
            "evidence": ([{"evidence_id": f"ev-{index}", "text": row["atomic_focus"]}]
                         if evidence else []),
            "capability_taxonomy_cap_status": cap_status,
        })

    def test_score_eligible_positive_match_does_not_require_capability_resolution(self):
        fixture = corpus("BigFix")
        self._set_scoring_row(fixture, 0, label="direct", evidence=True)
        with PublicationFixture() as f:
            report = gaps.audit_corpus_resolution(corpus=fixture)
        health = report["job_match_health"]
        knowledge = report["taxonomy_knowledge"]
        self.assertEqual(health["score_eligible_requirements"], 1)
        self.assertEqual(health["positive_grounded_evidence_matches"], 1)
        self.assertEqual(health["taxonomy_unresolved_positive_evidence_matches"], 1)
        self.assertEqual(knowledge["taxonomy_resolved_requirements"], 0)
        self.assertIsNone(report["requirements"][0]["current_resolution"]["capability_id"])
        self.assertFalse(report["scoring_semantics_changed"])
        f.network_guard.assert_not_called()
        f.model_guard.assert_not_called()

    def test_recognized_unmapped_and_resolved_without_evidence_are_distinct(self):
        fixture = corpus("C#", "React")
        self._set_scoring_row(fixture, 0)
        self._set_scoring_row(fixture, 1)
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=fixture)
        health = report["job_match_health"]
        knowledge = report["taxonomy_knowledge"]
        self.assertEqual(health["no_evidence_requirements"], 2)
        self.assertEqual(knowledge["technology_recognized_unmapped_requirements"], 1)
        self.assertEqual(knowledge["taxonomy_resolved_requirements"], 1)
        cross_tab = {row["knowledge_state"]: row for row in report["evidence_taxonomy_cross_tab"]}
        self.assertEqual(cross_tab["technology_recognized_unmapped"]["evidence_negative"], 1)
        self.assertEqual(cross_tab["taxonomy_resolved"]["evidence_negative"], 1)

    def test_taxonomy_cap_and_rejection_reporting_uses_final_grounded_match(self):
        fixture = corpus("React", "C++")
        self._set_scoring_row(fixture, 0, label="weak", evidence=True, cap_status="applied")
        self._set_scoring_row(fixture, 1, label="none", evidence=True, cap_status="applied")
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=fixture)
        health = report["job_match_health"]
        self.assertEqual(health["taxonomy_capped_or_rejected_pre_cap_positive_matches"], 2)
        self.assertEqual(health["taxonomy_capped_but_still_positive_matches"], 1)
        self.assertEqual(health["taxonomy_rejected_pre_cap_positive_matches"], 1)
        self.assertEqual(health["positive_grounded_evidence_matches"], 1)
        self.assertEqual(health["no_evidence_requirements"], 0)
        self.assertEqual(health["no_positive_grounded_match_requirements"], 1)

    def test_compatibility_alias_is_explicitly_taxonomy_resolution_only(self):
        fixture = corpus("React", "BigFix", "Python")
        self._set_scoring_row(fixture, 0)
        self._set_scoring_row(fixture, 1, label="direct", evidence=True)
        self._set_scoring_row(fixture, 2, label="direct", evidence=True)
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=fixture)
        summary = report["summary"]
        self.assertEqual(
            summary["resolved_scorable_requirements"],
            summary["taxonomy_resolved_requirements"],
        )
        self.assertNotEqual(
            summary["taxonomy_resolved_requirements"],
            summary["positive_grounded_evidence_matches"],
        )
        self.assertIn("score_eligible", report["metric_definitions"])

    def test_validated_capability_dispositions_are_review_only(self):
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=corpus("Python", "SQL", "MongoDB"))
        by_id = {row["capability_id"]: row for row in report["capability_draft_dispositions"]}
        self.assertEqual(by_id["language.python_development"]["disposition"],
                         "drop_duplicate_technology_semantics")
        self.assertEqual(by_id["database.sql_querying"]["disposition"],
                         "retain_capability_candidate")
        self.assertEqual(by_id["database.mongodb_engineering"]["disposition"],
                         "contextual_relationship")
        self.assertEqual(by_id["systems.distributed_systems"]["disposition"],
                         "research_only_blocked")
        self.assertEqual(report["production_mutations"], 0)


class TrueJobMatchGapTriageTests(unittest.TestCase):
    def test_every_true_no_evidence_row_has_one_primary_category(self):
        fixture = with_saved_evidence(
            corpus(
                "Kubernetes cluster operations",
                "Bachelor degree in computer science",
                "Complete the coding assessment before interview",
                "Python and SQL",
                "Our company is a leading provider",
                "Friendly and adaptable personality",
            ),
            "Unrelated product delivery evidence",
        )
        with PublicationFixture() as f:
            report = gaps.audit_corpus_resolution(corpus=fixture)
        triage = report["true_job_match_gap_triage"]
        self.assertEqual(
            triage["true_no_evidence_requirement_count"],
            report["job_match_health"]["no_evidence_requirements"],
        )
        self.assertEqual(
            sum(triage["classification_counts"].values()),
            triage["true_no_evidence_requirement_count"],
        )
        by_text = {row["requirement_text"]: row for row in triage["requirements"]}
        self.assertEqual(by_text["Kubernetes cluster operations"]["category_code"], "A")
        self.assertEqual(by_text["Bachelor degree in computer science"]["category_code"], "D")
        self.assertEqual(by_text["Complete the coding assessment before interview"]["category_code"], "E")
        self.assertEqual(by_text["Python and SQL"]["category_code"], "F")
        self.assertEqual(by_text["Our company is a leading provider"]["category_code"], "C")
        self.assertEqual(by_text["Friendly and adaptable personality"]["category_code"], "I")
        self.assertTrue(all(row["score_eligible"] for row in triage["requirements"]))
        self.assertFalse(triage["scoring_semantics_changed"])
        f.network_guard.assert_not_called()
        f.model_guard.assert_not_called()

    def test_saved_evidence_diagnostics_reuse_production_thresholds_read_only(self):
        fixture = with_saved_evidence(
            corpus(
                "NovelWidget software deployment",
                "Design and implement secure highly available Kubernetes deployment architecture across multiple production environments",
                "React frontend development",
                "This role reports to the engineering director",
            ),
            "NovelWidget software deployment",
            "Kubernetes deployment",
            "React frontend development",
            "This role reports to the engineering director",
        )
        original = deepcopy(fixture)
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=fixture)
        self.assertEqual(fixture, original)
        triage = report["true_job_match_gap_triage"]
        by_text = {row["requirement_text"]: row for row in triage["requirements"]}
        self.assertEqual(by_text["NovelWidget software deployment"]["category_code"], "H")
        self.assertEqual(
            by_text["Design and implement secure highly available Kubernetes deployment architecture across multiple production environments"]["category_code"],
            "B",
        )
        self.assertEqual(by_text["React frontend development"]["category_code"], "G")
        self.assertEqual(by_text["This role reports to the engineering director"]["category_code"], "C")
        for row in by_text.values():
            diagnostic = row["candidate_evidence_considered"]
            self.assertTrue(diagnostic["historical_evidence_available"])
            self.assertFalse(diagnostic["scoring_influence"])
            self.assertIsNotNone(diagnostic["best_compatible_evidence"])
        self.assertFalse(report["scoring_semantics_changed"])
        self.assertEqual(report["production_mutations"], 0)

    def test_eligibility_audit_identifies_review_categories_without_changing_behavior(self):
        fixture = with_saved_evidence(
            corpus(
                "Only shortlisted candidates will be notified",
                "Preferred AWS certification",
                "Python and SQL",
                "Our mission is to transform transport",
                "Kubernetes administration",
                "Ensure resilience of our mission-critical applications",
                "Operate with a high degree of autonomy",
            ),
            "unrelated evidence",
        )
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=fixture)
        eligibility = report["true_job_match_gap_triage"]["score_eligibility_audit"]
        self.assertTrue(eligibility["all_currently_score_eligible"])
        self.assertFalse(eligibility["behavior_changed"])
        statuses = {row["requirement_text"]: row["status"] for row in eligibility["requirements"]}
        self.assertEqual(statuses["Only shortlisted candidates will be notified"], "likely_should_not_score")
        self.assertEqual(statuses["Preferred AWS certification"], "credential_policy_review")
        self.assertEqual(statuses["Python and SQL"], "decompose_before_scoring")
        self.assertEqual(statuses["Our mission is to transform transport"], "likely_should_not_score")
        self.assertNotIn("Kubernetes administration", statuses)
        self.assertNotIn("Ensure resilience of our mission-critical applications", statuses)
        self.assertNotIn("Operate with a high degree of autonomy", statuses)

    def test_quality_fix_ranking_is_not_taxonomy_coverage_ranking(self):
        fixture = with_saved_evidence(
            corpus("NovelWidget software deployment", "Our company is a leading provider"),
            "NovelWidget software deployment",
        )
        with PublicationFixture():
            report = gaps.audit_corpus_resolution(corpus=fixture)
        fixes = report["top_20_job_match_quality_fixes"]
        self.assertTrue(fixes)
        self.assertTrue(all(not row["taxonomy_coverage_used_for_ranking"] for row in fixes))
        self.assertEqual(fixes[0]["category_code"], "H")


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


class CapabilityClosureTests(unittest.TestCase):
    @staticmethod
    def _profile(name, aliases, failure_type, *, safe_capability=None):
        return {"profile_version": "fixture", "profiles": [{
            "canonical_concept": name,
            "aliases": aliases,
            "failure_type": failure_type,
            "closest_capability_ids": [safe_capability or "backend.api_development"],
            "why_existing_insufficient": "Fixture boundary analysis",
            "safe_existing_capability_id": safe_capability,
            "relationship_rationale": "Fixture relationship supported by the existing capability definition",
            "boundary_checks": ["Fixture boundary only"],
        }]}

    def test_identity_exists_but_relationship_missing_and_existing_capability_fits(self):
        seed = {"entries": [{"canonical_name": "Node.js", "aliases": ["Node.js", "NodeJS"],
                             "technology_kind": "runtime", "relationship_hypotheses": []}]}
        with PublicationFixture() as f:
            audit = gaps.audit_corpus_resolution(corpus=corpus("Node.js"))
            bootstrap = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
            closure = gaps.build_capability_closure_matrix(
                audit, top_n=1, bootstrap_plan=bootstrap,
                profile_report=self._profile("Node.js", ["Node.js", "NodeJS"],
                                             "relationship_missing", safe_capability="backend.api_development"),
            )
        row = next(item for item in closure["matrix"] if item["display_concept"] == "Node.js")
        self.assertEqual(row["current_technology_identity_status"], "recognized_unmapped")
        self.assertEqual(row["failure_type_code"], "B")
        self.assertTrue(row["appropriate_existing_capability_exists"])
        self.assertEqual(row["safe_relationship_capability_id"], "backend.api_development")
        self.assertEqual(len(closure["safe_relationship_drafts"]), 1)
        f.network_guard.assert_not_called()
        f.model_guard.assert_not_called()

    def test_identity_only_missing_can_depend_on_safe_relationship_draft(self):
        seed = {"entries": [{"canonical_name": "BigFix", "aliases": ["BigFix"],
                             "technology_kind": "product", "relationship_hypotheses": []}]}
        with PublicationFixture():
            audit = gaps.audit_corpus_resolution(corpus=corpus("BigFix"))
            bootstrap = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
            closure = gaps.build_capability_closure_matrix(
                audit, top_n=1, bootstrap_plan=bootstrap,
                profile_report=self._profile("BigFix", ["BigFix"], "identity_only_missing",
                                             safe_capability="operations.configuration"),
            )
        row = next(item for item in closure["matrix"] if item["display_concept"] == "BigFix")
        relationship = closure["safe_relationship_drafts"][0]
        self.assertEqual(row["failure_type_code"], "A")
        self.assertEqual(row["identity"], "proposal_ready")
        self.assertTrue(relationship["depends_on_proposal_ids"])

    def test_missing_capability_enters_existing_research_and_overlap_contract(self):
        from taxonomy_discovery.taxonomy_evolution import research_target
        seed = {"entries": [{"canonical_name": "HCL BigFix", "aliases": ["HCL BigFix", "BigFix"],
                             "technology_kind": "product", "relationship_hypotheses": [],
                             "gap_route": "possible_new_capability"}]}
        with PublicationFixture() as f:
            audit = gaps.audit_corpus_resolution(corpus=corpus("BigFix"))
            bootstrap = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
            closure = gaps.build_capability_closure_matrix(audit, top_n=1, bootstrap_plan=bootstrap)
            row = next(item for item in closure["matrix"] if item["display_concept"] == "HCL BigFix")
            draft = next(item for item in closure["possible_new_capability_drafts"]
                         if item["proposed_capability_id"] == "operations.endpoint_management")
            target = research_target(draft["candidate"])
        self.assertEqual(row["failure_type_code"], "C")
        self.assertFalse(row["appropriate_existing_capability_exists"])
        self.assertIn("operations.configuration", draft["closest_existing_capabilities"])
        self.assertTrue(draft["overlap_diagnostics"]["diagnostic_only"])
        self.assertTrue(target["research_input_only"])
        self.assertFalse(draft["publishable"])
        f.network_guard.assert_not_called()
        f.model_guard.assert_not_called()

    def test_broad_platform_remains_contextual_without_universal_relationship(self):
        seed = {"entries": [{"canonical_name": "Amazon Web Services", "aliases": ["AWS", "Amazon Web Services"],
                             "technology_kind": "platform", "relationship_hypotheses": []}]}
        with PublicationFixture():
            audit = gaps.audit_corpus_resolution(corpus=corpus("AWS"))
            bootstrap = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
            closure = gaps.build_capability_closure_matrix(audit, top_n=1, bootstrap_plan=bootstrap)
        row = next(item for item in closure["matrix"] if item["display_concept"] == "Amazon Web Services")
        self.assertEqual(row["failure_type_code"], "D")
        self.assertEqual(row["relationship"], "contextual")
        self.assertFalse(row["safe_relationship_can_be_proposed"])
        self.assertFalse(any(item["technology"] == "Amazon Web Services"
                             for item in closure["safe_relationship_drafts"]))

    def test_temporary_new_capability_impact_is_read_only_and_score_neutral(self):
        seed = {"entries": [{"canonical_name": "HCL BigFix", "aliases": ["HCL BigFix", "BigFix"],
                             "technology_kind": "product", "relationship_hypotheses": [],
                             "gap_route": "possible_new_capability"}]}
        with PublicationFixture() as f:
            from tailoring import capability_taxonomy
            taxonomy_path = Path(capability_taxonomy.TAXONOMY_PATH)
            registry_before = f.real_registry.read_bytes()
            taxonomy_before = taxonomy_path.read_bytes()
            audit = gaps.audit_corpus_resolution(corpus=corpus("BigFix"))
            bootstrap = gaps.plan_bulk_technology_bootstrap(audit, seed=seed)
            closure = gaps.build_capability_closure_matrix(audit, top_n=1, bootstrap_plan=bootstrap)
            preview = gaps.preview_capability_closure(audit, closure)
            self.assertEqual(f.real_registry.read_bytes(), registry_before)
            self.assertEqual(taxonomy_path.read_bytes(), taxonomy_before)
            f.network_guard.assert_not_called()
            f.model_guard.assert_not_called()
        curve = {row["stage"]: row for row in preview["coverage_curve"]}
        self.assertEqual(curve["current_production"]["overall_percent"], 0.0)
        self.assertEqual(curve["identity_only"]["overall_percent"], 0.0)
        self.assertEqual(curve["safe_existing_capability_relationships"]["overall_percent"], 0.0)
        self.assertEqual(curve["research_dependent_new_capabilities"]["overall_percent"], 100.0)
        self.assertEqual(preview["new_capability_scenario"]["newly_scorable_requirements"], 1)
        self.assertFalse(preview["scoring_semantics_changed"])
        self.assertEqual(preview["production_mutations"], 0)

    def test_new_capability_phrase_collateral_blocks_hypothetical_resolution(self):
        with PublicationFixture():
            audit = gaps.audit_corpus_resolution(corpus=corpus(
                "distributed systems",
                "Web platforms, application hosting, or distributed systems",
            ))
            bootstrap = gaps.plan_bulk_technology_bootstrap(audit, seed={"entries": []})
            closure = gaps.build_capability_closure_matrix(audit, top_n=2, bootstrap_plan=bootstrap)
            draft = next(item for item in closure["possible_new_capability_drafts"]
                         if item["proposed_capability_id"] == "systems.distributed_systems")
            preview = gaps.preview_capability_closure(audit, closure)
        self.assertFalse(draft["scenario_preview_eligible"])
        self.assertEqual(len(draft["potential_collateral_requirements"]), 1)
        self.assertEqual(preview["new_capability_scenario"]["newly_scorable_requirements"], 0)
        self.assertTrue(preview["blocked_capability_scenarios"])
        self.assertEqual(preview["false_positive_collateral_matches"], [])


class LocalProposalCompatibilityTests(unittest.TestCase):
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
        self.assertIn("Build corpus-driven capability closure matrix", source)
        self.assertIn("Identity", source)
        self.assertIn("Relationship", source)
        self.assertIn("Capability", source)
        self.assertIn("Job Match Health", source)
        self.assertIn("Taxonomy Knowledge", source)
        self.assertIn("evidence-match coverage", source)
        self.assertIn("Top true Job Match evidence gaps", source)
        self.assertIn("True no-evidence gap triage", source)
        self.assertIn("Top 20 fixes by expected Job Match quality impact", source)
        self.assertIn("Score-eligibility policy review", source)
        self.assertIn("Top taxonomy-maintenance priorities", source)
        self.assertNotIn("resolved/scorable", source)

    def test_populated_overview_separates_job_match_health_from_taxonomy_knowledge(self):
        from taxonomy_discovery import bulk_candidate_operations_ui as ui
        from tests.test_tqd3_bulk_candidate_operations import BulkFakeStreamlit
        with PublicationFixture():
            audit = gaps.audit_corpus_resolution(corpus=corpus("React", "C#", "BigFix"))
            queue = gaps.build_gap_resolution_queue(audit)
        st = BulkFakeStreamlit()
        st.session_state["tqd3_corpus_gap_audit"] = audit
        st.session_state["tqd3_gap_resolution_queue"] = queue
        with patch.dict(sys.modules, {"streamlit": st}):
            ui.render_bulk_candidate_operations()
        rendered = " ".join(str(args) for _, args in st.messages)
        self.assertIn("Job Match Health", rendered)
        self.assertIn("Taxonomy Knowledge", rendered)
        self.assertIn("positive grounded evidence matches", rendered)
        self.assertIn("True no-evidence gap triage", rendered)
        self.assertIn("Primary reason counts", rendered)
        self.assertIn("Score-eligibility policy review", rendered)
        self.assertIn("taxonomy resolved", rendered)
        self.assertNotIn("resolved/scorable", rendered)


if __name__ == "__main__":
    unittest.main()
