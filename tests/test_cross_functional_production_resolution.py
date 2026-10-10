"""Permanent requirement-side scope regressions; no provider execution."""
from copy import deepcopy
from pathlib import Path
import unittest

from tailoring import capability_taxonomy as taxonomy
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
from taxonomy_discovery import corpus_gap_resolution as gaps
from taxonomy_discovery.regression_corpus import replay_current_corpus
from taxonomy_discovery.technology_identity_remediation import _records
from tests.cross_functional_resolution_validation_support import NEGATIVES, CAPABILITY_ID
from tests.test_cross_functional_resolution_validation import POSITIVES
from tests.test_taxonomy_maintenance_service import fixture_corpus
from tests.tqd3_publication_fixture_support import PublicationFixture


def grounded(text):
    return {"text": text, "atomic_focus": text, "source_provenance": [{
        "parent_text": text, "raw_parent_text": text,
        "grounding": {"kind": "explicit_raw_section", "span_id": "fixture-span",
                      "sentence_index": 1, "sentence_text": text}}]}


class CrossFunctionalProductionTests(unittest.TestCase):
    def test_both_complete_grounded_rows_use_native_rule(self):
        for text in POSITIVES:
            row = grounded(text)
            result = resolve(row)
            self.assertEqual(result["decision"]["capability_id"], CAPABILITY_ID)
            self.assertEqual(result["resolution_source"], "canonical_taxonomy")
            self.assertEqual(result["taxonomy_diagnostics"]["matched_taxonomy_rule_type"], "native_complete_scope_rule")
            self.assertEqual(taxonomy.classify_requirement(row), CAPABILITY_ID)

    def test_all_negative_boundaries_even_with_grounding(self):
        for text in NEGATIVES:
            with self.subTest(text=text):
                self.assertNotEqual(resolve(grounded(text))["decision"]["capability_id"], CAPABILITY_ID)
        for text in POSITIVES:
            for suffix in (" to build and deploy APIs", " or work alone", " and administer SQL databases"):
                self.assertNotEqual(resolve(grounded(text.rstrip(".") + suffix))["decision"]["capability_id"], CAPABILITY_ID)

    def test_missing_or_stripped_sentence_provenance_fails_closed(self):
        for text in POSITIVES:
            self.assertIsNone(resolve({"text": text})["decision"]["capability_id"])
            for field in ("kind", "span_id", "sentence_index", "sentence_text"):
                row = grounded(text)
                del row["source_provenance"][0]["grounding"][field]
                self.assertIsNone(resolve(row)["decision"]["capability_id"])

    def test_conflicting_parent_occurrence_cannot_borrow_grounding(self):
        row = grounded(POSITIVES[0])
        row["source_provenance"].append({"raw_parent_text": POSITIVES[0] + " Implement APIs."})
        self.assertIsNone(resolve(row)["decision"]["capability_id"])

    def test_native_independent_sentence_and_uncovered_parent_scope(self):
        row = grounded(POSITIVES[0])
        row["source_provenance"][0]["raw_parent_text"] = "Communication is key. " + POSITIVES[0]
        self.assertEqual(resolve(row)["decision"]["capability_id"], CAPABILITY_ID)
        row["source_provenance"][0]["parent_text"] = POSITIVES[0] + " Implement APIs."
        self.assertIsNone(resolve(row)["decision"]["capability_id"])
        row = grounded(POSITIVES[0])
        row["source_provenance"][0]["raw_parent_text"] = "Different source sentence."
        self.assertIsNone(resolve(row)["decision"]["capability_id"])

    def test_job493_unheaded_parent_scope_remains_unresolved(self):
        text = "work closely with project manager, technical lead and architect as part of the project delivery"
        row = grounded(text)
        row["source_provenance"][0].update(parent_text="You will deliver project objectives. " + text,
                                          raw_parent_text="You will deliver project objectives. " + text)
        row["source_provenance"][0]["grounding"]["kind"] = "unheaded_explicit_role_obligation"
        self.assertIsNone(resolve(row)["decision"]["capability_id"])
        self.assertIsNone(resolve({"text": text})["decision"]["capability_id"])

    def test_generic_teamwork_evidence_never_gains_direct(self):
        result = resolve(grounded(POSITIVES[0]), evidence_text="Worked with team members on a project")
        self.assertNotEqual(result["decision"]["label"], "direct")
        self.assertIn("general teamwork as direct cross-functional evidence", result["decision"]["does_not_prove"])

    def test_frozen_replay_audit_and_closure_preview_agree(self):
        root = Path(__file__).resolve().parents[1]
        paths = [root / p for p in ("taxonomy/capability_taxonomy_v1.json", "taxonomy/technology_registry_v1.json")]
        original = [p.read_bytes() for p in paths]
        with PublicationFixture() as fixture:
            corpus = fixture_corpus(*POSITIVES)
            frozen = deepcopy(corpus)
            replay = replay_current_corpus(corpus)
            audit = gaps.audit_corpus_resolution(corpus=replay)
            for row in _records(replay).values():
                self.assertEqual(row["capability_id"], CAPABILITY_ID)
            for row in audit["requirements"]:
                self.assertEqual(row["current_resolution"]["capability_id"], CAPABILITY_ID)
            from taxonomy_discovery.technology_registry import get_default_registry
            preview = gaps._preview_closure_scenario(audit, taxonomy=taxonomy.get_default_taxonomy(),
                registry=get_default_registry(), intended_keys=set())
            self.assertEqual(preview["affected_jobs"], [])
            self.assertEqual(preview["conflicts_ambiguity"], [])
            self.assertTrue(all(row["after"]["capability_id"] == CAPABILITY_ID for row in preview["rows"]))
            self.assertEqual(corpus, frozen)
            fixture.model_guard.assert_not_called(); fixture.network_guard.assert_not_called()
        self.assertEqual(original, [p.read_bytes() for p in paths])

    def test_existing_analysis_identity_invalidates_previous_resolver_generation(self):
        from analysis_stability.stable_evidence_scoring import SCORING_VERSION
        from job_discovery.matching import current_match_versions
        self.assertEqual(current_match_versions()["scoring_version"], SCORING_VERSION)
        self.assertNotEqual(SCORING_VERSION, "stable-evidence-v1.14-phase6d20")


if __name__ == "__main__":
    unittest.main()
