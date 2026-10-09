"""Focused zero-network tests for the TQ-D3 research-readiness gate."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from taxonomy_discovery import bulk_candidate_operations as bulk
from taxonomy_discovery import governed_research as research
from taxonomy_discovery import research_readiness as readiness
from taxonomy_discovery.source_authority import (
    FIRST_PARTY_OTHER,
    PRIMARY_OFFICIAL,
    SECONDARY,
    classify_candidate_source_url,
    load_source_authority_registry,
)
from taxonomy_discovery.corpus_expansion import fingerprint
from tests.test_tqd3_taxonomy_evolution import candidate


REPO_ROOT = Path(__file__).resolve().parents[1]
NO_IDENTITY_COHORT = REPO_ROOT / "tests/fixtures/tqd3_readiness_no_identity_cohort.json"


class RegistryReadinessTests(unittest.TestCase):
    def test_every_registry_entry_is_audited_deterministically_and_versioned(self):
        first = readiness.audit_technology_registry()
        second = readiness.audit_technology_registry()
        self.assertEqual(first, second)
        self.assertEqual(first["technology_count"], len(first["entries"]))
        self.assertEqual(first["technology_count"], 28)
        self.assertTrue(first["audit_fingerprint"])
        self.assertTrue(all(row["authority_rules_fingerprint"] for row in first["entries"]))
        self.assertEqual(first["network_calls"], 0)
        self.assertEqual(first["model_calls"], 0)
        self.assertEqual(first["production_writes"], 0)

    def test_mapped_technology_is_resolved_and_relationship_missing_authority_blocks_paid_research(self):
        rows = {row["technology_id"]: row for row in readiness.audit_technology_registry()["entries"]}
        self.assertEqual(rows["react"]["research_readiness"], readiness.ALREADY_RESOLVED)
        self.assertEqual(rows["react"]["capability_id"], "frontend.ui_development")
        with tempfile.TemporaryDirectory() as tmp:
            rules = Path(tmp) / "rules.json"
            rules.write_text(json.dumps({"version": "empty", "technology_domains": []}), encoding="utf-8")
            known = readiness.audit_candidate(candidate("C#", "technology_relationship"),
                                              queue_state="known_identity_missing_relationship",
                                              authority_registry_path=rules)
        self.assertEqual(known["research_readiness"], readiness.BLOCKED_NOISE_OR_INSUFFICIENT)
        self.assertFalse(known["paid_research_eligible"])

    def test_microservices_non_owned_concept_fails_safe_without_invented_authority(self):
        rows = {row["technology_id"]: row for row in readiness.audit_technology_registry()["entries"]}
        row = rows["microservices"]
        self.assertEqual(row["research_readiness"], readiness.MANUAL_REVIEW)
        self.assertEqual(row["official_domains"], [])
        self.assertEqual(row["blocker_reason"], "non_owned_concept_has_no_single_official_authority")


class AuthorityAndEvidenceTests(unittest.TestCase):
    def test_authority_registry_version_and_fingerprint_are_explicit_currentness_inputs(self):
        rules = load_source_authority_registry()
        self.assertEqual(rules["version"], "source-authority-registry-v1.5")
        original = fingerprint(rules)
        changed = deepcopy(rules)
        changed["technology_domains"][0]["official_domains"].append("example.invalid")
        self.assertNotEqual(fingerprint(changed), original)

    def test_benchmark_official_domains_are_subject_specific(self):
        benchmark = readiness.load_benchmark()
        self.assertGreaterEqual(len(benchmark["technologies"]), 22)
        self.assertEqual(len(benchmark["route_cases"]), 10)
        self.assertEqual({row["case"] for row in benchmark["route_cases"]}, {
            "known_mapped_technology", "known_unmapped_relationship", "unknown_concrete_identity",
            "vendor_owned_product", "foundation_owned_open_source", "compound_multi_technology",
            "generic_architecture_concept", "possible_new_capability", "resolver_issue",
            "administrative_noise",
        })
        for case in benchmark["technologies"]:
            with self.subTest(case=case["technology"]):
                official = classify_candidate_source_url(
                    {"canonical_name": case["technology"]}, case["official_url"])
                unrelated = classify_candidate_source_url(
                    {"canonical_name": case["technology"]}, case["unrelated_url"])
                self.assertEqual(official["authority"], PRIMARY_OFFICIAL)
                self.assertNotEqual(unrelated["authority"], PRIMARY_OFFICIAL)

    def test_benchmark_route_cases_match_deterministic_readiness(self):
        for case in readiness.load_benchmark()["route_cases"]:
            with self.subTest(case=case["case"]):
                source_route = case["route"] if case["route"] in {
                    "technology_identity", "technology_relationship"
                } else "capability_gap"
                item = candidate(case["candidate"], source_route)
                if item["candidate_route"] != case["route"]:
                    item["candidate_route"] = case["route"]
                    item.pop("candidate_id")
                    item.pop("candidate_fingerprint")
                    item["candidate_fingerprint"] = fingerprint(item)
                    item["candidate_id"] = "tqd3taxgap_" + item["candidate_fingerprint"][:24]
                queue_state = (
                    "resolved_locally" if case["expected"] == readiness.ALREADY_RESOLVED
                    else "local_review_required" if case["expected"] == readiness.LOCAL_REVIEW_REQUIRED
                    else "blocked" if case["expected"] == readiness.BLOCKED_NOISE_OR_INSUFFICIENT
                    else "external_research_required"
                )
                actual = readiness.audit_candidate(item, queue_state=queue_state)
                self.assertEqual(actual["research_readiness"], case["expected"])
                self.assertTrue(actual["requires_human_review"])
                self.assertFalse(actual["automatic_approval"])
                self.assertFalse(actual["automatic_publication"])

    def test_node_dotnet_keycloak_and_safe_subdomains(self):
        cases = (
            ("Node.js", "https://nodejs.org/en/docs/"),
            (".NET", "https://dotnet.microsoft.com/en-us/learn/dotnet/what-is-dotnet"),
            ("Keycloak", "https://www.keycloak.org/docs/latest/"),
            ("Node.js", "https://docs.nodejs.org/api/"),
        )
        for subject, url in cases:
            with self.subTest(subject=subject, url=url):
                self.assertEqual(classify_candidate_source_url({"canonical_name": subject}, url)["authority"],
                                 PRIMARY_OFFICIAL)

    def test_microsoft_path_scopes_do_not_over_authorize_other_products(self):
        self.assertEqual(classify_candidate_source_url(
            {"canonical_name": "C#"}, "https://learn.microsoft.com/en-us/dotnet/csharp/")["authority"], PRIMARY_OFFICIAL)
        self.assertEqual(classify_candidate_source_url(
            {"canonical_name": "C#"}, "https://learn.microsoft.com/en-us/mem/configmgr/")["authority"],
            FIRST_PARTY_OTHER)
        self.assertEqual(classify_candidate_source_url(
            {"canonical_name": ".NET"}, "https://learn.microsoft.com/en-us/mem/configmgr/")["authority"],
            FIRST_PARTY_OTHER)
        self.assertEqual(classify_candidate_source_url(
            {"canonical_name": "Microsoft SCCM"}, "https://learn.microsoft.com/en-us/dotnet/csharp/")["authority"],
            FIRST_PARTY_OTHER)

    def test_secondary_source_remains_secondary(self):
        row = classify_candidate_source_url({"canonical_name": "Node.js"}, "https://medium.com/example")
        self.assertEqual(row["authority"], SECONDARY)

    def test_live_shaped_raw_evidence_is_reclassified_without_mutation(self):
        saved = [{"result": {
            "research_result_id": "tqd3h1_9636ff27e6fb20143b8313f8",
            "provider_request_id": "persisted-node-request",
            "research": {"target": {"subject": "Node.js"}, "evidence_fingerprint": "raw-node",
                         "raw_provider_evidence": {"results": [{"url": "https://nodejs.org/en/blog/events/nodejs-interactive-2026"}]}},
            "sources": [{"source_class": "secondary_supporting"}],
        }}, {"result": {
            "research_result_id": "tqd3h1_57954e717c922eba41ec5c33",
            "provider_request_id": "persisted-dotnet-request",
            "research": {"target": {"subject": ".NET"}, "evidence_fingerprint": "raw-dotnet",
                         "raw_provider_evidence": {"results": [{"url": "https://dotnet.microsoft.com/en-us/learn/dotnet/what-is-dotnet"}]}},
            "sources": [{"source_class": "authoritative_supporting"}],
        }}, {"result": {
            "research_result_id": "historical-keycloak",
            "provider_request_id": "persisted-keycloak-request",
            "research": {"target": {"subject": "Keycloak"}, "evidence_fingerprint": "raw-keycloak",
                         "raw_provider_evidence": {"results": [{"url": "https://www.keycloak.org/docs/latest/"}]}},
            "sources": [{"source_class": "secondary_supporting"}],
        }}]
        frozen = deepcopy(saved)
        audited = readiness.audit_saved_research_evidence(saved)
        self.assertEqual(saved, frozen)
        self.assertTrue(all(row["first_party_source_count_after"] == 1 for row in audited))
        self.assertTrue(all(row["history_mutated"] is False for row in audited))

    def test_node_dotnet_and_keycloak_reinterpretation_does_not_infer_relationships(self):
        cases = (
            ("Node.js", "https://nodejs.org/en/blog/events/nodejs-interactive-2026",
             "Join the Node.js community event.", False),
            (".NET", "https://dotnet.microsoft.com/en-us/learn/dotnet/what-is-dotnet",
             ".NET is a free and open-source application platform supported by Microsoft.", True),
            ("Keycloak", "https://www.keycloak.org/docs/latest/",
             "Keycloak provides customizable user interfaces for login and account management.", True),
        )
        for subject, url, content, identity_verified in cases:
            with self.subTest(subject=subject):
                item = candidate(subject, "technology_relationship")
                target = research.research_plan(
                    [item], selected_candidate_ids=[item["candidate_id"]]
                )["targets"][0]
                interpreted = research.interpret(target, {"raw_provider_evidence": {
                    "results": [{"url": url, "content": content}],
                }})
                self.assertEqual(interpreted["identity_finding"]["verified"], identity_verified)
                self.assertFalse(interpreted["relationship_finding"]["verified"])
                self.assertEqual(interpreted["recommended_next_action"], "research_more")
                self.assertTrue(interpreted["conflicts_blockers"])


class QueryAndQueueReadinessTests(unittest.TestCase):
    def test_relationship_route_requires_current_production_identity(self):
        item = candidate("UnknownNovelTool", "technology_identity")
        item["candidate_route"] = "technology_relationship"
        item.pop("candidate_id"); item.pop("candidate_fingerprint")
        item["candidate_fingerprint"] = fingerprint(item)
        item["candidate_id"] = "tqd3taxgap_" + item["candidate_fingerprint"][:24]
        audit = readiness.audit_candidate(item, queue_state="external_research_required")
        self.assertEqual(audit["research_readiness"], readiness.BLOCKED_NOISE_OR_INSUFFICIENT)
        self.assertEqual(audit["blocker_reason"], "relationship_research_requires_current_production_technology_id")
        with self.assertRaisesRegex(ValueError, "route-aware readiness"):
            research.research_plan([item], selected_candidate_ids=[item["candidate_id"]])

    def test_candidate_wording_inherits_authority_from_one_recognized_atomic_identity(self):
        item = candidate("Experience with Node.js", "technology_relationship")
        audit = readiness.audit_candidate(item, queue_state="known_identity_missing_relationship")
        self.assertEqual(audit["technology_id"], "node.js")
        self.assertEqual(audit["detected_technology_ids"], ["node.js"])
        self.assertEqual(audit["authority_inherited_from"], "technology_id=node.js")
        self.assertTrue(audit["authority_covered"])
        self.assertEqual(audit["research_readiness"], readiness.RELATIONSHIP_RESEARCH_READY)

    def test_unknown_concrete_identity_is_ready_without_auto_approving_authority(self):
        item = candidate("Experience with Microsoft SCCM", "technology_identity")
        audit = readiness.audit_candidate(item, queue_state="external_research_required")
        self.assertFalse(audit["known_identity"])
        self.assertFalse(audit["authority_covered"])
        self.assertTrue(audit["candidate_text_authority_hints"])
        self.assertEqual(audit["authority_state"], "candidate_evidence_only_not_governed")
        self.assertEqual(audit["research_readiness"], readiness.IDENTITY_RESEARCH_READY)
        self.assertTrue(audit["paid_research_eligible"])
        self.assertEqual(audit["query_strategy"]["include_domains"], [])
        self.assertFalse(audit["query_strategy"]["discovered_domains_are_governed"])

    def test_compound_parent_never_inherits_one_childs_readiness(self):
        item = candidate("Node.js and UnknownNovelTool", "technology_relationship")
        audit = readiness.audit_candidate(item, queue_state="known_identity_missing_relationship")
        self.assertEqual(audit["decomposition_status"], "compound_requires_decomposition")
        self.assertEqual(audit["research_readiness"], readiness.NEEDS_DECOMPOSITION)
        self.assertFalse(audit["paid_research_eligible"])

    def test_known_identity_uses_neutral_bounded_official_query_strategy(self):
        expected = {
            "C#": ["official C# documentation overview", "official C# what is",
                   "official C# documentation use cases architecture usage"],
            "MongoDB": ["official MongoDB documentation overview", "official MongoDB what is",
                        "official MongoDB documentation use cases architecture usage"],
        }
        for subject, queries in expected.items():
            with self.subTest(subject=subject):
                item = candidate(subject, "technology_relationship")
                plan = research.research_plan([item], selected_candidate_ids=[item["candidate_id"]])
                target = plan["targets"][0]
                self.assertEqual(target["questions"], queries)
                self.assertEqual(target["query_strategy"]["maximum_queries"], 3)
                self.assertTrue(target["known_identity_skips_rediscovery"])
                self.assertNotIn("capability", " ".join(queries).lower())
                follow_up = research.research_plan([item], selected_candidate_ids=[item["candidate_id"]], research_round=1)
                self.assertEqual(follow_up["targets"][0]["search_query"], queries[1])

    def test_only_ready_candidates_enter_paid_batch_and_blocked_uses_no_budget(self):
        relationship = candidate("C#", "technology_relationship")
        identity = candidate("UnknownNovelTool", "technology_identity")
        capability = candidate("distributed systems", "capability_gap")
        blocked = candidate("only shortlisted candidates will be notified", "capability_gap")
        transport = Mock(side_effect=AssertionError("planning must not execute"))
        plan = bulk.prepare_bulk_plan([relationship, identity, capability, blocked],
            selected_candidate_ids=[relationship["candidate_id"], identity["candidate_id"],
                                    capability["candidate_id"], blocked["candidate_id"]],
            saved_rows=[], publications=[])
        transport.assert_not_called()
        self.assertEqual(plan["external_candidates_required"], 3)
        self.assertEqual(plan["ready_external_candidates"], 3)
        self.assertEqual(plan["blocked_by_readiness"], 0)
        self.assertEqual({row["research_readiness"] for row in plan["execution_targets"]}, {
            readiness.RELATIONSHIP_RESEARCH_READY,
            readiness.IDENTITY_RESEARCH_READY,
            readiness.CAPABILITY_RESEARCH_READY,
        })
        self.assertEqual(plan["planned_tavily_calls"], 3)
        self.assertEqual({row["research_purpose"] for row in plan["execution_targets"]}, {
            "Research capability relationship",
            "Verify technology identity",
            "Research capability definition and boundaries",
        })
        self.assertEqual(plan["network_calls_during_preview"], 0)
        self.assertEqual(plan["model_calls_during_preview"], 0)

    def test_identity_compounds_capability_resolver_and_noise_are_route_aware(self):
        compound = readiness.audit_candidate(
            candidate("Python and SQL is expected", "technology_identity"),
            queue_state="external_research_required",
        )
        capability = readiness.audit_candidate(
            candidate("distributed systems", "capability_gap"),
            queue_state="external_research_required",
        )
        resolver = readiness.audit_candidate(
            candidate("software system level integration", "capability_gap"),
            queue_state="local_review_required",
        )
        noise = readiness.audit_candidate(
            candidate("only shortlisted candidates will be notified", "capability_gap"),
            queue_state="blocked",
        )
        self.assertEqual(compound["research_readiness"], readiness.NEEDS_DECOMPOSITION)
        self.assertEqual(compound["identity_hypotheses"], ["Python", "SQL"])
        self.assertEqual(capability["research_readiness"], readiness.CAPABILITY_RESEARCH_READY)
        self.assertFalse(capability["known_identity"])
        self.assertEqual(resolver["research_readiness"], readiness.LOCAL_REVIEW_REQUIRED)
        self.assertEqual(noise["research_readiness"], readiness.BLOCKED_NOISE_OR_INSUFFICIENT)
        self.assertFalse(noise["paid_research_eligible"])

    def test_generic_identity_prose_and_acronyms_remain_blocked(self):
        for text in ("experience with CI", "strong communication and stakeholder skills"):
            with self.subTest(text=text):
                item = candidate(text, "technology_identity")
                item["candidate_route"] = "technology_identity"
                audit = readiness.audit_candidate(item, queue_state="external_research_required")
                self.assertEqual(audit["research_readiness"], readiness.BLOCKED_NOISE_OR_INSUFFICIENT)
                self.assertFalse(audit["paid_research_eligible"])

    def test_real_no_identity_cohort_routes_conservatively_without_calls_or_mutation(self):
        taxonomy_path = REPO_ROOT / "taxonomy/capability_taxonomy_v1.json"
        registry_path = REPO_ROOT / "taxonomy/technology_registry_v1.json"
        before = (taxonomy_path.read_bytes(), registry_path.read_bytes())
        payload = json.loads(NO_IDENTITY_COHORT.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["candidates"]), 47)
        self.assertEqual(len({row["candidate_id"] for row in payload["candidates"]}), 47)
        network = Mock(side_effect=AssertionError("readiness audit must remain offline"))
        with patch("socket.socket.connect", network):
            queue = bulk.build_candidate_queue(
                payload["candidates"], saved_rows=[], publications=[], include_hidden=True
            )
        network.assert_not_called()
        audited = {
            row["candidate_id"]: row for row in queue["research_readiness"]["candidates"]
        }
        prior_no_identity = [
            audited[row["candidate_id"]]
            for row in queue["rows"]
            if row["external_research_required"] and not audited[row["candidate_id"]]["known_identity"]
        ]
        self.assertEqual(len(prior_no_identity), 47)
        self.assertEqual(Counter(row["research_readiness"] for row in prior_no_identity), Counter({
            readiness.IDENTITY_RESEARCH_READY: 11,
            readiness.CAPABILITY_RESEARCH_READY: 13,
            readiness.NEEDS_DECOMPOSITION: 22,
            readiness.BLOCKED_NOISE_OR_INSUFFICIENT: 1,
        }))
        self.assertEqual((taxonomy_path.read_bytes(), registry_path.read_bytes()), before)

    def test_identity_discovery_persists_candidate_evidence_without_mapping_or_authority_approval(self):
        item = candidate("UnknownNovelTool", "technology_identity")
        target = research.research_plan([item], selected_candidate_ids=[item["candidate_id"]])["targets"][0]
        interpreted = research.interpret(target, {"raw_provider_evidence": {"results": [{
            "url": "https://unknown.example/docs",
            "content": "UnknownNovelTool is a backend API development tool maintained by Example Project.",
        }]}})
        discovery = interpreted["authority_discovery"]
        self.assertEqual(discovery["candidate_domains"], ["unknown.example"])
        self.assertFalse(discovery["discovered_domains_are_governed"])
        self.assertTrue(discovery["human_review_required"])
        self.assertFalse(interpreted["relationship_finding"]["verified"])
        self.assertEqual(interpreted["relationship_finding"]["supported_existing_capability_ids"], [])
        self.assertEqual(interpreted["recommended_next_action"], "technology_identity_proposal")

    def test_decomposition_and_current_cache_are_excluded(self):
        compound = candidate("Node.js and UnknownNovelTool", "technology_relationship")
        compound_audit = readiness.audit_candidate(compound, queue_state="partial_resolution_decomposition_required")
        cached_audit = readiness.audit_candidate(candidate("MongoDB", "technology_relationship"),
                                                 queue_state="research_current_cached")
        self.assertEqual(compound_audit["research_readiness"], readiness.NEEDS_DECOMPOSITION)
        self.assertFalse(compound_audit["paid_research_eligible"])
        self.assertEqual(cached_audit["research_readiness"], readiness.CACHED_CURRENT)
        self.assertFalse(cached_audit["paid_research_eligible"])

    def test_readiness_does_not_change_scoring_or_approve_relationships(self):
        taxonomy = Path("taxonomy/capability_taxonomy_v1.json").read_bytes()
        registry = Path("taxonomy/technology_registry_v1.json").read_bytes()
        report = readiness.audit_technology_registry()
        self.assertEqual(Path("taxonomy/capability_taxonomy_v1.json").read_bytes(), taxonomy)
        self.assertEqual(Path("taxonomy/technology_registry_v1.json").read_bytes(), registry)
        self.assertFalse(any("approval" in row for row in report["entries"]))
        self.assertFalse(any("score" in row for row in report["entries"]))


if __name__ == "__main__":
    unittest.main()
