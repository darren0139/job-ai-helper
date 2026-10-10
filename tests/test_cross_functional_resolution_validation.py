from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import unittest

from tailoring import capability_taxonomy as taxonomy, production_requirement_resolver as resolver
from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery.regression_corpus import replay_current_corpus
from taxonomy_discovery.technology_identity_remediation import _records
from tests.cross_functional_resolution_validation_support import temporary_rule, eligible, NEGATIVES, CAPABILITY_ID
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture

POSITIVES = (
    "You will work closely with fellow engineers, policy officers, UX designers, cybersecurity specialists, and various partner agencies.",
    "Work closely with Business Analysts, Solution Architects, Product Owners and Software Engineers within an Agile environment.",
)


class CrossFunctionalRuleTests(unittest.TestCase):
    def test_both_complete_requirements_resolve_using_native_matcher(self):
        for text in POSITIVES:
            before = resolver.resolve_requirement_with_production_knowledge({"text": text})
            self.assertIsNone(before["decision"]["capability_id"])
            with temporary_rule():
                after = resolver.resolve_requirement_with_production_knowledge({"text": text})
                keyword = taxonomy.classify_requirement_diagnostics({"text": text}, taxonomy=taxonomy.get_default_taxonomy())
            self.assertEqual(after["decision"]["capability_id"], CAPABILITY_ID)
            self.assertEqual(after["resolution_source"], "canonical_taxonomy")
            self.assertEqual(keyword["capability_id"], CAPABILITY_ID)
            self.assertEqual(after["taxonomy_diagnostics"]["capability_record"]["evidence_tiers"], taxonomy.get_default_taxonomy().by_id()[CAPABILITY_ID]["evidence_tiers"])

    def test_all_negative_resolutions_unchanged(self):
        for text in NEGATIVES:
            with self.subTest(text=text):
                row = {"text": text}
                self.assertFalse(eligible(row))
                before = resolver.resolve_requirement_with_production_knowledge(row)
                with temporary_rule():
                    after = resolver.resolve_requirement_with_production_knowledge(row)
                self.assertEqual(before, after)

    def test_positive_text_cannot_leak_into_mixed_or_alternative_scope(self):
        for text in POSITIVES:
            for suffix in (" to build and deploy APIs", " or work alone", " and administer SQL databases"):
                self.assertFalse(eligible({"text": text.rstrip(".") + suffix}))

    def test_parent_scope_requires_exact_native_sentence_grounding(self):
        text = POSITIVES[0].rstrip(".")
        row = {"text": text, "source_provenance": [{"raw_parent_text": text + " and implement secure services"}]}
        with temporary_rule():
            self.assertIsNone(resolver.resolve_requirement_with_production_knowledge(row)["decision"]["capability_id"])
        row["source_provenance"][0].update(raw_parent_text=text + ". Implement secure services.",
            grounding={"kind": "explicit_raw_section", "span_id": "fixture", "sentence_index": 1, "sentence_text": text})
        self.assertTrue(eligible(row))

    def test_generic_team_evidence_does_not_become_direct(self):
        with temporary_rule():
            result = resolver.resolve_requirement_with_production_knowledge({"text": POSITIVES[0]}, evidence_text="Worked with team members on a project")
        self.assertNotEqual(result["decision"]["label"], "direct")
        self.assertIn("general teamwork as direct cross-functional evidence", result["decision"]["does_not_prove"])

    def test_other_threads_and_exception_teardown_remain_native(self):
        original = taxonomy.classify_requirement_diagnostics
        alias = resolver.classify_requirement_diagnostics
        with self.assertRaisesRegex(RuntimeError, "fixture abort"):
            with temporary_rule():
                with ThreadPoolExecutor(max_workers=1) as executor:
                    value = executor.submit(resolver.resolve_requirement_with_production_knowledge, {"text": POSITIVES[0]}).result()
                    self.assertIsNone(value["decision"]["capability_id"])
                raise RuntimeError("fixture abort")
        self.assertIs(taxonomy.classify_requirement_diagnostics, original)
        self.assertIs(resolver.classify_requirement_diagnostics, alias)

    def test_stripped_parent_provenance_cannot_bypass_frozen_scope_admission(self):
        text = "work closely with project manager, technical lead and architect as part of the project delivery"
        full = {"text": text, "source_provenance": [{"raw_parent_text": text + " and implement secure services"}]}
        with temporary_rule([full, {"text": POSITIVES[0]}]):
            self.assertIsNone(resolver.resolve_requirement_with_production_knowledge({"text": text})["decision"]["capability_id"])
            self.assertEqual(resolver.resolve_requirement_with_production_knowledge({"text": POSITIVES[0]})["decision"]["capability_id"], CAPABILITY_ID)
        # Same phrase in conflicting recorded scopes is also held for review.
        with temporary_rule([full, {"text": text}]):
            self.assertIsNone(resolver.resolve_requirement_with_production_knowledge({"text": text})["decision"]["capability_id"])

    def test_native_frozen_replay_no_knowledge_writes_or_input_mutation(self):
        files = [Path(f) for f in ("taxonomy/capability_taxonomy_v1.json", "taxonomy/technology_registry_v1.json",
            "analysis_stability/stable_evidence_scoring.py", "tailoring/capability_taxonomy.py", "tailoring/production_requirement_resolver.py")]
        contents = [p.read_bytes() for p in files]
        with PublicationFixture() as fixture:
            snapshot = maintenance.run_corpus_audit(corpus=fixture_corpus(*POSITIVES), explicit_execution=True, review_db_path=fixture.tmp / "review.sqlite")
            frozen = deepcopy(snapshot)
            with temporary_rule(_records(snapshot["audit"]["corpus"]).values()):
                replay = replay_current_corpus(snapshot["audit"]["corpus"])
            self.assertEqual(snapshot, frozen)
            self.assertTrue(all(r["capability_id"] == CAPABILITY_ID for r in _records(replay).values()))
            fixture.model_guard.assert_not_called(); fixture.network_guard.assert_not_called()
        self.assertEqual(contents, [p.read_bytes() for p in files])


if __name__ == "__main__":
    unittest.main()
