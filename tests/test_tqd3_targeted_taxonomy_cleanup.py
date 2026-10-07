"""Focused offline tests for the final targeted taxonomy cleanup review."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from job_discovery.matching import _default_stable_builder, build_profile_evidence_context
from taxonomy_discovery import corpus_gap_resolution as gaps
from taxonomy_discovery.regression_corpus import build_regression_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


TARGET_REQUIREMENTS = (
    "SQL",
    "Knowledge of network access control",
    "Ansible",
    "BigFix",
    "Knowledge of deployment and management like BigFix",
    "Familiarity with distributed systems",
    "Web platforms, application hosting, or distributed systems",
)


def frozen_corpus():
    evidence = [{
        "id": 1,
        "category": "Project",
        "title": "Infrastructure controls",
        "description": (
            "Implemented network access control and wrote optimized SQL queries. "
            "Automated infrastructure configuration with Ansible playbooks."
        ),
        "skills": ["SQL", "Ansible"],
        "tools": [],
    }]
    context = build_profile_evidence_context(evidence)
    raw_jd = "Requirements\n" + "\n".join(f"- {text}" for text in TARGET_REQUIREMENTS)
    profile = {"required_skills": list(TARGET_REQUIREMENTS)}
    stable = _default_stable_builder(raw_jd_text=raw_jd, jd_profile=profile, context=context)
    snapshot = {
        "id": 10,
        "discovered_job_id": 1,
        "job_content_hash": "targeted-taxonomy-fixture",
        "evidence_fingerprint": context["evidence_fingerprint"],
        "raw_jd_text": raw_jd,
        "jd_profile": profile,
        "evidence_snapshot": evidence,
        "stable_analysis": stable,
    }
    return build_regression_corpus([snapshot])


def insufficient_bigfix_research():
    return [{
        "result": {
            "research_result_id": "cached-bigfix",
            "provider_request_id": "provider-bigfix",
            "candidate_route": "technology_identity",
            "candidate": {"normalized_cluster": "bigfix"},
            "authoritative_evidence_summary": [],
            "quality_diagnostics": {"primary_definitions": 0},
            "recommended_next_action": "research_more",
            "conflicts_blockers": ["No affirmative subject-specific first-party definition"],
        },
        "review": {"decision": "undecided"},
    }]


class TargetedTaxonomyCleanupTests(unittest.TestCase):
    def _report(self):
        corpus = frozen_corpus()
        audit = gaps.audit_corpus_resolution(corpus=corpus)
        report = gaps.build_targeted_taxonomy_cleanup(
            audit,
            saved_research_rows=insufficient_bigfix_research(),
        )
        return corpus, audit, report

    def test_exact_target_dispositions_and_existing_capability_boundaries(self):
        with PublicationFixture() as fixture:
            _, _, report = self._report()
        by_name = {row["candidate"]: row for row in report["targeted_items"]}
        self.assertEqual(report["disposition_counts"], {
            "A": 0, "B": 3, "C": 0, "D": 2, "E": 0, "F": 0,
        })
        self.assertEqual(by_name["SQL"]["disposition"], "B")
        self.assertEqual(
            by_name["SQL"]["relationship_decision"],
            "contextual_only_after_capability_approval",
        )
        self.assertEqual(by_name["network access control"]["disposition"], "B")
        self.assertEqual(by_name["Ansible"]["disposition"], "B")
        self.assertEqual(by_name["HCL BigFix"]["disposition"], "D")
        self.assertFalse(
            by_name["HCL BigFix"]["cached_research"]["governed_authoritative_definition_available"]
        )
        self.assertEqual(by_name["distributed systems"]["disposition"], "D")
        self.assertEqual(by_name["distributed systems"]["review_readiness"], "NOT READY")
        self.assertTrue(all(row["approval"] is False for row in report["targeted_items"]))
        self.assertEqual(report["production_mutations"], 0)
        fixture.network_guard.assert_not_called()
        fixture.model_guard.assert_not_called()

    def test_capability_definitions_are_bounded_and_relationships_stay_separate(self):
        with PublicationFixture():
            _, _, report = self._report()
        by_name = {row["candidate"]: row for row in report["targeted_items"]}
        sql = by_name["SQL"]["proposed_capability"]
        network = by_name["network access control"]["proposed_capability"]
        ansible = by_name["Ansible"]["proposed_capability"]
        self.assertEqual(sql["capability_id"], "database.sql_querying")
        self.assertIn("Schema design alone", sql["does_not_prove"])
        self.assertEqual(network["capability_id"], "network.access_control")
        self.assertIn("Database role policy", network["does_not_prove"])
        self.assertEqual(ansible["capability_id"], "devops.infrastructure_automation")
        self.assertIn("Manual system configuration", ansible["does_not_prove"])
        for draft in report["human_review_ready_proposals"]:
            self.assertFalse(draft["approval"])
            self.assertFalse(draft["publication"])

    def test_distributed_systems_collision_remains_blocked(self):
        with PublicationFixture():
            _, _, report = self._report()
        distributed = next(
            row for row in report["targeted_items"]
            if row["candidate"] == "distributed systems"
        )
        self.assertIn(
            "Web platforms, application hosting, or distributed systems",
            [row["requirement_text"] for row in distributed["potential_collateral_requirements"]],
        )
        self.assertIn("Known compound phrase collision remains unresolved", distributed["review_blockers"])
        self.assertIsNone(distributed["proposed_capability"])

    def test_active_cap_audit_distinguishes_collision_and_negative_controls(self):
        false_rejection = gaps._cap_boundary_classification({
            "requirement_text": "(c) Front-end frameworks such as React, Node.js, or Angular 2",
            "match_label": "none",
            "current_resolution": {"capability_id": "language.modern_cpp"},
        })
        genuine_c = gaps._cap_boundary_classification({
            "requirement_text": "Knowledge in C (C++ is considered a plus), Java, C#, Visual Basic",
            "match_label": "none",
            "current_resolution": {"capability_id": "language.modern_cpp"},
        })
        security_testing = gaps._cap_boundary_classification({
            "requirement_text": "Experience in performing penetration testing",
            "match_label": "weak",
            "current_resolution": {"capability_id": "quality.qa_testing"},
        })
        self.assertTrue(false_rejection["false_rejection"])
        self.assertEqual(false_rejection["classification"], "resolver_boundary_issue")
        self.assertFalse(genuine_c["false_rejection"])
        self.assertEqual(genuine_c["classification"], "expected_semantic_protection")
        self.assertEqual(security_testing["classification"], "resolver_boundary_issue")
        self.assertFalse(security_testing["false_rejection"])

    def test_integrated_preview_is_temporary_offline_and_does_not_add_relationships(self):
        with PublicationFixture() as fixture:
            taxonomy_before = Path(gaps.TAXONOMY_PATH).read_bytes()
            registry_before = fixture.real_registry.read_bytes()
            corpus, audit, report = self._report()
            original = deepcopy(corpus)
            preview = gaps.preview_targeted_taxonomy_cleanup(audit, report)
            self.assertEqual(corpus, original)
            self.assertEqual(Path(gaps.TAXONOMY_PATH).read_bytes(), taxonomy_before)
            self.assertEqual(fixture.real_registry.read_bytes(), registry_before)
            fixture.network_guard.assert_not_called()
            fixture.model_guard.assert_not_called()
        self.assertEqual(preview["baseline_metrics"]["jobs"], 1)
        self.assertEqual(preview["temporary_metrics"]["jobs"], 1)
        self.assertEqual(
            preview["temporary_metrics"]["stored_requirements"],
            preview["baseline_metrics"]["stored_requirements"],
        )
        self.assertFalse(preview["production_taxonomy_mutated"])
        self.assertFalse(preview["production_registry_mutated"])
        self.assertFalse(preview["scoring_formula_changed"])
        self.assertFalse(preview["global_thresholds_changed"])
        self.assertFalse(preview["approval"])
        self.assertFalse(preview["publication"])
        self.assertEqual(preview["network_calls"], 0)
        self.assertEqual(preview["model_calls"], 0)
        # Bare identities remain unmapped because relationship review is separate.
        self.assertFalse(any(
            (row.get("after") or {}).get("resolution_source") == "technology_registry"
            for row in preview["requirement_changes"]
        ))

    def test_ui_requires_explicit_execution_and_reuses_maintenance_workflow(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "taxonomy_discovery"
            / "bulk_candidate_operations_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Run targeted cleanup + 30-job temporary replay", source)
        self.assertIn("build_targeted_taxonomy_cleanup", source)
        self.assertIn("preview_targeted_taxonomy_cleanup", source)
        self.assertIn("Targeted evidence, cap audit, G boundaries", source)


if __name__ == "__main__":
    unittest.main()
