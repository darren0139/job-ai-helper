"""Offline, governed scope/origin fixtures; no live research or production DBs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from taxonomy_discovery import governed_research as research
from taxonomy_discovery.capability_sufficiency import evaluate_capability_support, escalation_plan, extract_support
from taxonomy_discovery.source_authority import capability_source_governance
from taxonomy_discovery.tavily_research import build_tavily_search_request
from tests.test_tqd3_taxonomy_evolution import candidate
from tests.tqd3_publication_fixture_support import PublicationFixture

SUBJECT = "crystalline computing protocols"


def complete_text(subject=SUBJECT):
    return (f"{subject} is an engineering practice for coordinating bounded compute protocols. "
            "It includes protocol coordination and state synchronization. "
            "Engineers implement protocol coordination within a bounded context. "
            "It excludes generic tool usage, which does not prove this practice. "
            "Documented protocol configuration and validated synchronization tests demonstrate implementation evidence.")


class SufficiencyV2Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = PublicationFixture()
        self.fixture.__enter__()
        self.addCleanup(self.fixture.__exit__, None, None, None)
        self.path = self.fixture.tmp / "sufficiency-authority.json"
        self.rules = {"version": "test-v2", "authoritative_definition_sources": [{"domain": "normative.example"}],
                      "reviewed_capability_sources": [self.rule("one.example", "owner-one"),
                         self.rule("two.example", "owner-two"), self.rule("mirror.example", "owner-one")]}
        self.save_rules()
        self.item = candidate(SUBJECT, "capability_gap")

    @staticmethod
    def rule(domain, origin, kind="strong_technical"):
        return {"domain": domain, "path_prefixes": ["/guide"], "kind": kind, "origin_id": origin,
                "reviewed_by": "fixture-reviewer", "reviewed_at": "2026-10-09"}

    def save_rules(self):
        self.path.write_text(json.dumps(self.rules), encoding="utf-8")

    def source(self, domain="normative.example", text=None, full=True, path="/guide"):
        value = text or complete_text() + "\n\nPublisher notes: " + domain
        if text is None and domain == "two.example":
            value = value.replace("engineering practice", "engineering discipline").replace(
                "and state synchronization", "alongside state synchronization").replace(
                "Engineers implement", "Engineers maintain")
        row = {"url": f"https://{domain}{path}", "content": value,
               "raw_content": value if full else None, "authoritative": True}
        return {"evidence": row}

    def evaluate(self, sources, **kwargs):
        return evaluate_capability_support(SUBJECT, sources, candidate=self.item,
            overlap=kwargs.get("overlap", {"exact_matches": [], "high_overlap_candidates": []}),
            atomicity=kwargs.get("atomicity", {"atomicity_status": "coherent_capability_concept"}), known=kwargs.get("known", {}),
            authority_registry_path=self.path)

    def test_normative_single_source_complete_support_is_review_only(self):
        result = self.evaluate([self.source()])
        self.assertEqual(result["outcome"], "eligible_for_human_review")
        self.assertEqual(result["support_path"], "normative")
        self.assertTrue(all(f["evidence"] for f in result["fields"].values()))
        self.assertFalse(result["automatic_approval"])
        self.assertFalse(result["automatic_publication"])

    def test_two_independent_reviewed_sources_converge(self):
        result = self.evaluate([self.source("one.example"), self.source("two.example")])
        self.assertTrue(result["eligible_for_human_review"])
        self.assertEqual(result["independent_governed_origins"], 2)
        self.assertEqual(result["support_path"], "independent_convergence")

    def test_same_owner_urls_and_mirrors_are_one_origin(self):
        for sources in ([self.source("one.example"), self.source("one.example", path="/guide/second")],
                        [self.source("one.example"), self.source("mirror.example")]):
            result = self.evaluate(sources)
            self.assertEqual(result["independent_governed_origins"], 1)
            self.assertFalse(result["eligible_for_human_review"])

    def test_identical_syndicated_text_is_not_independent(self):
        result = self.evaluate([self.source("one.example", text=complete_text()),
                                self.source("two.example", text=complete_text())])
        self.assertEqual(result["independent_governed_origins"], 1)
        self.assertFalse(result["eligible_for_human_review"])

    def test_one_strong_plus_independent_corroboration(self):
        self.rules["reviewed_capability_sources"][1]["kind"] = "corroborating"
        self.save_rules()
        result = self.evaluate([self.source("one.example"), self.source("two.example")])
        self.assertEqual(result["support_path"], "independent_corroboration")
        self.assertTrue(result["eligible_for_human_review"])

    def test_subject_bound_paragraph_and_one_heading_body(self):
        for text in (complete_text(), "# " + SUBJECT + "\n\n" + complete_text().replace(SUBJECT, "This practice")):
            result = self.evaluate([self.source(text=text)])
            self.assertTrue(result["eligible_for_human_review"])
            self.assertTrue(all(row["paragraph_fingerprint"] for row in result["fields"]["boundaries"]["evidence"]))

    def test_unrelated_paragraph_and_omitted_passages_do_not_supply_predicates(self):
        base = complete_text().split("Documented")[0]
        for separator in ("\n\n", " [...] "):
            result = self.evaluate([self.source(text=base + separator + "Documented payment configuration and validated billing tests demonstrate evidence.")])
            self.assertIn("EVIDENCE_PREDICATES_MISSING", result["missing_evidence"])
            self.assertFalse(result["eligible_for_human_review"])

    def test_negation_and_qualifiers_preserved(self):
        result = self.evaluate([self.source(text=complete_text() + f" Using Python alone does not prove {SUBJECT}.")])
        self.assertTrue(result["eligible_for_human_review"])
        self.assertIn("does not prove", result["fields"]["exclusions"]["evidence"][0]["text"])
        self.assertIn("within a bounded context", result["fields"]["responsibilities"]["evidence"][0]["text"])

    def test_missing_boundary_blocks_even_with_definition(self):
        result = self.evaluate([self.source(text=f"{SUBJECT} is an engineering practice for compute protocols.")])
        self.assertIn("BOUNDARY_MISSING", result["missing_evidence"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_missing_predicates_blocks(self):
        result = self.evaluate([self.source(text=complete_text().split("Documented")[0])])
        self.assertIn("EVIDENCE_PREDICATES_MISSING", result["missing_evidence"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_unresolved_conflicting_sources_block(self):
        text = f"{SUBJECT} is not an engineering practice for coordinating bounded compute protocols. " + complete_text()
        result = self.evaluate([self.source("one.example"), self.source("two.example", text=text)])
        self.assertIn("Contradictory governed source semantics", result["conflicts"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_adjacent_inclusion_exclusion_conflict_blocks(self):
        text = complete_text().replace("It includes protocol coordination and state synchronization.",
            "It does not include protocol coordination.")
        result = self.evaluate([self.source("one.example"), self.source("two.example", text=text)])
        self.assertIn("Contradictory governed source semantics", result["conflicts"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_existing_taxonomy_overlap_is_authoritative(self):
        result = self.evaluate([self.source()], overlap={"exact_matches": ["backend.api_development"], "high_overlap_candidates": []})
        self.assertFalse(result["eligible_for_human_review"])
        self.assertIn("DISTINCTNESS_UNCERTAIN", result["missing_evidence"])

    def test_uncertain_candidate_scope_fails_closed(self):
        result = self.evaluate([self.source()], atomicity={"atomicity_status": "uncertain"})
        self.assertFalse(result["eligible_for_human_review"])
        self.assertIn("Candidate atomicity / coherence unresolved", result["conflicts"])

    def test_technology_usage_or_identity_cannot_prove_capability(self):
        result = self.evaluate([self.source(text=complete_text() + f" Using Python alone proves {SUBJECT}.")])
        self.assertFalse(result["eligible_for_human_review"])
        self.assertIn("Unsafe broader implication from technology use", result["conflicts"])
        result = self.evaluate([self.source()], known={"technology_id": "python"})
        self.assertFalse(result["eligible_for_human_review"])

    def test_search_snippets_and_unreviewed_vendor_fail_closed(self):
        for source in (self.source(full=False), self.source("unreviewed.example")):
            result = self.evaluate([source])
            self.assertFalse(result["eligible_for_human_review"])
            self.assertEqual(result["independent_governed_origins"], 0)

    def test_document_scope_boundary_not_domain_trust(self):
        self.assertFalse(capability_source_governance("https://one.example/guide-spoof", SUBJECT, registry_path=self.path)["governed"])
        self.assertFalse(capability_source_governance("https://evilone.example/guide", SUBJECT, registry_path=self.path)["governed"])

    def test_targeted_missing_predicate_escalation(self):
        result = self.evaluate([self.source(text=complete_text().split("Documented")[0])])
        plan = escalation_plan(SUBJECT, result)
        self.assertEqual(plan["chosen_deficiency"], "EVIDENCE_PREDICATES_MISSING")
        self.assertIn("project artifacts", plan["query"])
        self.assertEqual(plan["call_budget"], 1)
        self.assertEqual(escalation_plan(SUBJECT, result, research_round=3)["call_budget"], 0)

    def test_authority_lead_is_only_a_plan_primary_must_be_retrieved(self):
        result = self.evaluate([self.source("one.example", text=complete_text() + " See NIST SP 800-144 for guidance.", full=False)])
        plan = escalation_plan(SUBJECT, result)
        self.assertIn("NIST SP 800-144", plan["query"])
        self.assertEqual(plan["planned_domains"], ["nist.gov"])
        self.assertTrue(plan["primary_source_must_be_retrieved"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_native_interpretation_persistence_escalation_and_no_auto_draft(self):
        from database.taxonomy_discovery_review_manager import list_governed_research_results
        plan = research.research_plan([self.item], selected_candidate_ids=[self.item["candidate_id"]], authority_registry_path=self.path)
        provider = Mock(return_value={"request_id": "fake-v2", "results": [self.source()["evidence"]]})
        receipt = research.execute_plan(plan, [self.item], explicit_execution=True, transport=provider,
            db_path=self.fixture.tmp / "research.sqlite", authority_registry_path=self.path)
        self.assertFalse(receipt["failures"])
        result = receipt["results"][0]
        self.assertTrue(result["proposal_eligible"])
        rows = list_governed_research_results(db_path=self.fixture.tmp / "research.sqlite")
        self.assertIsNone(rows[0]["draft"])
        self.assertFalse(result["approval"])
        self.assertEqual(result["next_research_plan"]["call_budget"], 0)
        with self.assertRaisesRegex(ValueError, "human review"):
            research.research_plan([self.item], selected_candidate_ids=[self.item["candidate_id"]],
                previous_result=result, research_round=1, authority_registry_path=self.path)
        provider.assert_called_once()
        self.fixture.network_guard.assert_not_called()
        self.fixture.model_guard.assert_not_called()

    def test_scope_drift_not_source_count(self):
        text = complete_text().replace("coordinating bounded compute protocols", "visualizing medical imaging radiographs")
        result = self.evaluate([self.source("one.example"), self.source("two.example", text=text)])
        self.assertIn("Candidate scope drift / definition convergence unresolved", result["conflicts"])
        self.assertFalse(result["eligible_for_human_review"])

    def test_capability_adapter_requests_document_text(self):
        payload = build_tavily_search_request({"target_id": "fake-v2", "tavily_eligible": True,
            "research_question": "definition", "search_query": "bounded definition", "research_profile": "capability_support_bundle_v2"})
        self.assertEqual(payload["include_raw_content"], "text")

    def test_five_saved_calibration_results_different_diagnostics_not_forced_pass(self):
        cases = json.loads((Path(__file__).with_name("fixtures") / "tqd3_sufficiency_v2_calibration.json").read_text(encoding="utf-8"))["cases"]
        diagnostics = {}
        for case in cases:
            item = candidate(case["subject"], "capability_gap")
            target = research.research_plan([item], selected_candidate_ids=[item["candidate_id"]])["targets"][0]
            result = research.interpret(target, {"raw_provider_evidence": deepcopy(case["raw_provider_evidence"])})
            bundle = result["support_bundle"]
            self.assertFalse(result["proposal_eligible"])
            self.assertEqual(bundle["outcome"], "research_more")
            self.assertTrue(bundle["missing_evidence"])
            diagnostics[case["subject"]] = sum(len(v["tentative_evidence"]) for v in bundle["fields"].values())
        self.assertGreater(diagnostics["microservices architecture"], 0)
        self.assertGreater(diagnostics["cloud security"], 0)
        self.assertGreater(diagnostics["network access control"], 0)
        self.assertEqual(diagnostics["data analysis and insights"], 0)
        self.assertGreater(len(set(diagnostics.values())), 1)

    def test_capability_budget_prevents_provider_retry(self):
        plan = research.research_plan([self.item], selected_candidate_ids=[self.item["candidate_id"]], authority_registry_path=self.path)
        provider = Mock(side_effect=TimeoutError("bounded fake timeout"))
        receipt = research.execute_plan(plan, [self.item], explicit_execution=True, transport=provider,
            db_path=self.fixture.tmp / "timeout.sqlite", authority_registry_path=self.path)
        provider.assert_called_once()
        self.assertTrue(receipt["failures"])

    def test_native_bulk_escalation_uses_missing_evidence_and_version_refresh(self):
        from taxonomy_discovery.bulk_candidate_operations import prepare_bulk_plan
        from database.taxonomy_discovery_review_manager import list_governed_research_results
        from taxonomy_discovery.corpus_expansion import fingerprint
        plan = research.research_plan([self.item], selected_candidate_ids=[self.item["candidate_id"]], authority_registry_path=self.path)
        receipt = research.execute_plan(plan, [self.item], explicit_execution=True,
            transport=Mock(return_value={"request_id": "missing-predicate", "results": [self.source(text=complete_text().split("Documented")[0])["evidence"]]}),
            db_path=self.fixture.tmp / "followup.sqlite", authority_registry_path=self.path)
        self.assertFalse(receipt["failures"])
        result = receipt["results"][0]
        saved = list_governed_research_results(db_path=self.fixture.tmp / "followup.sqlite")
        followup = prepare_bulk_plan([self.item], selected_candidate_ids=[self.item["candidate_id"]], saved_rows=saved,
            publications=[], authority_registry_path=self.path)
        target = followup["execution_targets"][0]["single_candidate_plan"]["targets"][0]
        self.assertEqual(target["escalation_plan"]["chosen_deficiency"], "EVIDENCE_PREDICATES_MISSING")
        self.assertIn("project artifacts", target["search_query"])
        old = deepcopy(result)
        old["interpretation_version"] = "historical-interpretation"
        old.pop("research_result_id"); old.pop("result_fingerprint")
        old["result_fingerprint"] = fingerprint(old)
        old["research_result_id"] = "tqd3h1_" + old["result_fingerprint"][:24]
        with self.assertRaisesRegex(ValueError, "interpretation changed"):
            research.validate_result(old)
        refreshed = research.re_evaluate_saved_evidence(old, explicit_execution=True)
        self.assertEqual(refreshed["research"]["raw_provider_evidence"], old["research"]["raw_provider_evidence"])
        self.assertEqual(refreshed["provider_request_id"], old["provider_request_id"])
        self.assertEqual(refreshed["interpretation_version"], research.INTERPRETATION_VERSION)


if __name__ == "__main__":
    unittest.main()
