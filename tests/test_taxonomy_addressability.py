"""Offline semantic-accounting regressions; no production knowledge writes."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import unittest

from taxonomy_discovery import taxonomy_addressability as address, maintenance_service as maintenance
from taxonomy_discovery import gap_reduction_assistant as assistant, corpus_gap_resolution as gaps
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


class AddressabilityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = gaps.load_capability_closure_profiles()["profiles"]

    def classify(self, text, routes=()):
        return address.classify({"text": text}, set(routes), self.profiles)

    def test_vague_requires_documented_whole_phrase_reason(self):
        status, reason, _ = self.classify("strong technical background")
        self.assertEqual(status, address.NOT_ADDRESSABLE)
        self.assertIn("VAGUE_TECHNICAL_SCOPE", reason)
        self.assertEqual(self.classify("knowledge of modern technologies")[0], address.NOT_ADDRESSABLE)

    def test_concrete_difficult_activity_is_never_excluded_as_vague(self):
        for text in ("network access control", "microservices architecture", "strong technical background in Kubernetes",
                     "data persistence and search using MongoDB"):
            self.assertNotEqual(self.classify(text)[0], address.NOT_ADDRESSABLE)

    def test_bounded_native_gap_has_complete_review_only_contract(self):
        status, _, proof = self.classify("knowledge of network access control")
        self.assertEqual(status, address.GAP)
        self.assertEqual(len(proof["gap_contract"]), 12)
        self.assertFalse(proof["gap_contract"]["authority_or_publication_claim"])
        self.assertTrue(proof["gap_contract"]["negative_boundary_to_research"])

    def test_identity_and_relationship_routes_do_not_establish_taxonomy_gap(self):
        for text, route in (("Python", maintenance.IDENTITY_GAP), ("MongoDB", maintenance.RELATIONSHIP_GAP),
                            ("Experience with Node.js", maintenance.RELATIONSHIP_GAP)):
            self.assertEqual(self.classify(text, [route])[0], address.UNDETERMINED)

    def test_parser_dependency_cannot_hide_true_bounded_gap(self):
        status, _, proof = self.classify("network access control", [maintenance.PARSING_PROBLEM, maintenance.IDENTITY_GAP])
        self.assertEqual(status, address.GAP)
        self.assertTrue(proof["gap_contract"]["not_primary_parser_or_decomposition"])

    def test_known_capability_is_separate_from_relationship_blocker(self):
        status, _, proof = self.classify("React", [maintenance.RELATIONSHIP_GAP])
        self.assertEqual(status, address.SUPPORTED)
        self.assertEqual(proof["native_resolution"]["decision"]["capability_id"], "frontend.ui_development")

    def test_distributed_and_mixed_scope_need_review_not_name_based_gap(self):
        for text in ("Familiarity with distributed systems", "Web platforms, application hosting, or distributed systems",
                     "Knowledge of microservices architecture", "network access control or packet analysis"):
            self.assertEqual(self.classify(text)[0], address.UNDETERMINED)

    def test_lexical_taxonomy_overlap_does_not_imply_equivalence(self):
        self.assertEqual(self.classify("database persistence administration with MongoDB")[0], address.UNDETERMINED)


class ManualTriageV2Tests(unittest.TestCase):
    def triage(self, text, routes=(), **extra):
        return address.manual_triage({"text": text, **extra}, set(routes))

    def test_public_service_motivation_is_not_technical_activity(self):
        text = "\u200bPublic Service Spirit: You care deeply about the public good and understand the responsibility of working on critical national infrastructure that impacts millions of lives daily"
        t = self.triage(text)
        self.assertEqual(t["decision"], address.NOT_ADDRESSABLE)
        self.assertEqual(t["reason_code"], "SUBJECTIVE_OR_MOTIVATIONAL")
        self.assertTrue(all(t["non_addressable_contract"].values()))

    def test_future_employer_product_context_not_capability(self):
        self.assertEqual(self.triage("You will be at the forefront of developing the Next Generation Traffic Light Control System")["decision"], address.NOT_ADDRESSABLE)
        self.assertIsNone(self.triage("You will be at the forefront of developing the Next Generation Network Security System")["decision"])

    def test_whole_culture_values_statement_can_be_non_addressable(self):
        t = self.triage("You share our values of integrity and respect")
        self.assertEqual(t["reason_code"], "CULTURE_OR_VALUES")
        self.assertEqual(t["decision"], address.NOT_ADDRESSABLE)
        self.assertIsNone(self.triage("You share our values of integrity and implement access controls")["decision"])

    def test_continuous_learning_is_not_implementation(self):
        text = "Continuous Learning: You will constantly explore new technologies, system architectures, and security practices"
        self.assertEqual(self.triage(text)["decision"], address.NOT_ADDRESSABLE)
        self.assertIsNone(self.triage(text + " and implement security-by-design")["decision"])

    def test_technical_protection_including_identity_and_mixed_behaviour(self):
        for text in ("distributed systems", "microservices architecture", "network access control", "Python", "SQL", "AWS", "Azure",
            "manage MongoDB persistence and search", "security-by-design", "critical-infrastructure security", "Implement backend APIs",
            "database design", "write SQL queries", "database administration", "configure network admission policies",
            "You take pride in ensuring that the software governing our roads is failsafe",
            "You believe that code isn't done until it is thoroughly tested and documented"):
            with self.subTest(text=text):
                self.assertNotEqual(self.triage(text)["decision"], address.NOT_ADDRESSABLE)

    def test_dependency_and_parent_scope_protect_against_false_exclusion(self):
        text = "Ability to learn new software and technologies quickly"
        for route in (maintenance.IDENTITY_GAP, maintenance.RELATIONSHIP_GAP, maintenance.PARSING_PROBLEM, "NEEDS_DECOMPOSITION_OR_MIXED_SCOPE"):
            self.assertIsNone(self.triage(text, [route])["decision"])
        self.assertIsNone(self.triage(text, source_provenance=[{"raw_parent_text": text + " and implement Python services"}])["decision"])

    def test_complete_cross_functional_scope_reuses_existing_capability(self):
        text = "You will work closely with fellow engineers, policy officers, UX designers, cybersecurity specialists, and various partner agencies"
        t = self.triage(text)
        self.assertEqual(t["decision"], address.SUPPORTED)
        self.assertEqual(t["capability_id"], "collaboration.cross_functional")
        self.assertGreaterEqual(len(t["functions"]), 2)
        for addition in (" to implement secure API services", " and write unit tests"):
            self.assertIsNone(self.triage(text + addition)["decision"])
        self.assertIsNone(self.triage("Work closely with software engineers and engineers")["decision"])

    def test_deterministic_rules_do_not_use_requirement_ids(self):
        text = "You share our values of integrity and respect"
        self.assertEqual(self.triage(text, requirement_id="a"), self.triage(text, requirement_id="b"))

    def test_native_sentence_grounding_keeps_sibling_technical_requirement_separate(self):
        text = "Ability to learn new software and technologies quickly"
        parent = text + ". Implement secure APIs."
        provenance = [{"raw_parent_text": parent, "grounding": {"kind": "explicit_raw_section", "span_id": "fixture-span",
            "sentence_index": 1, "sentence_text": text}}]
        t = self.triage(text, source_provenance=provenance)
        self.assertEqual(t["decision"], address.NOT_ADDRESSABLE)
        self.assertEqual(t["native_sentence_scope"]["sentence_text"], text)
        self.assertIsNone(self.triage("Implement secure APIs", source_provenance=[{"raw_parent_text": parent,
            "grounding": {"kind": "explicit_raw_section", "span_id": "fixture-span", "sentence_index": 2,
                "sentence_text": "Implement secure APIs"}}])["decision"])


class AddressabilityAccountingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.fixture = self.stack.enter_context(PublicationFixture())
        self.snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus("network access control", "Python", "microservices architecture"),
            explicit_execution=True, review_db_path=self.fixture.tmp / "reviews.sqlite")

    def test_plan_determinism_raw_metrics_and_no_writes(self):
        files = [Path(f) for f in ("taxonomy/capability_taxonomy_v1.json", "taxonomy/technology_registry_v1.json",
            "analysis_stability/stable_evidence_scoring.py", "tailoring/production_requirement_resolver.py", "tailoring/phase6d6_structured_matching.py")]
        before = [p.read_bytes() for p in files]
        source = deepcopy(self.snapshot)
        plan = assistant.build_plan(self.snapshot, review_db_path=self.fixture.tmp / "reviews.sqlite")
        result = plan["taxonomy_addressability"]
        report = assistant.markdown_report(plan)
        self.assertIn("## Taxonomy addressability", report)
        self.assertIn(address.UNDETERMINED, report)
        self.assertEqual(result, assistant.build_plan(self.snapshot, review_db_path=self.fixture.tmp / "reviews.sqlite")["taxonomy_addressability"])
        self.assertEqual(source, self.snapshot)
        self.assertEqual(result["raw_summary"], source["audit"]["summary"])
        self.assertEqual(sum(s["count"] for s in result["summary"].values()), len(result["rows"]))
        self.assertTrue(all(r["primary_blocker"] == maintenance.CAPABILITY_GAP
            for r in result["rows"] if r["semantic_addressability"] == address.GAP))
        self.assertEqual(before, [p.read_bytes() for p in files])
        self.fixture.model_guard.assert_not_called(); self.fixture.network_guard.assert_not_called()

    def test_283_rows_once_even_with_overlapping_blockers(self):
        source = deepcopy(self.snapshot)
        template = deepcopy(source["audit"]["requirements"][0])
        raw = deepcopy(source["audit"]["corpus"]["jobs"][0]["baseline_stable_analysis"]["canonical_requirements"][0])
        rows, canon = [], []
        for n in range(283):
            rid = "fixture_req_" + str(n)
            row = {**deepcopy(template), "job_id": 1, "requirement_id": rid}
            rows.append(row); canon.append({**deepcopy(raw), "requirement_id": rid, "text": "Unbounded technical scope " + str(n), "atomic_focus": "Unbounded technical scope " + str(n)})
        source["audit"]["summary"]["taxonomy_unresolved_requirements"] = 283
        source["audit"]["requirements"] = rows
        source["audit"]["queue"] = []
        source["audit"]["corpus"]["jobs"][0]["baseline_stable_analysis"]["canonical_requirements"] = canon
        source["audit"]["corpus"]["jobs"] = source["audit"]["corpus"]["jobs"][:1]
        linked = [{"requirements": rows, "fix_layer": layer, "boundary_state": maintenance.NEEDS_DECOMPOSITION, "candidate": None}
                  for layer in (maintenance.IDENTITY_GAP, maintenance.PARSING_PROBLEM)]
        result = address.project(source, rows, linked)
        self.assertEqual(result["unique_unresolved_requirements"], 283)
        self.assertEqual(result["semantic_count_total"], 283)
        self.assertEqual(result["summary"][address.UNDETERMINED]["count"], 283)
        self.assertEqual(len({(r["job_id"], r["requirement_id"]) for r in result["rows"]}), 283)
        self.assertTrue(all(maintenance.IDENTITY_GAP in r["secondary_blockers"] for r in result["rows"]))
        self.assertGreater(sum(result["blocker_association_counts"].values()), 283)
        self.assertTrue(all(r["semantic_addressability"] in address.STATUSES for r in result["rows"]))

    def test_missing_or_duplicate_unresolved_rows_fail_closed(self):
        rows = self.snapshot["audit"]["requirements"]
        with self.assertRaisesRegex(ValueError, "complete unique"):
            address.project(self.snapshot, rows[:1], [])
        with self.assertRaisesRegex(ValueError, "complete unique"):
            address.project(self.snapshot, rows + [rows[0]], [])

    def test_mongodb_real_persistence_shape_is_undetermined(self):
        text = "Hands-on experience managing data persistence and search layers using MongoDB, Redis, Elasticsearch, or comparable NoSQL and search engines"
        status, reason, _ = address.classify({"text": text}, {maintenance.RELATIONSHIP_GAP}, gaps.load_capability_closure_profiles()["profiles"])
        self.assertEqual(status, address.UNDETERMINED)
        self.assertIn("review scope", reason)


if __name__ == "__main__":
    unittest.main()
