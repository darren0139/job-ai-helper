"""Bounded document recovery using offline persisted excerpts and synthetic boundaries."""
import json
from pathlib import Path
import unittest
from taxonomy_discovery.capability_sufficiency import extract_support, subject_blocks

FIXTURE = Path(__file__).with_name("fixtures") / "tqd3_saved_nist_document_excerpts.json"


class DocumentSupportExtractionTests(unittest.TestCase):
    def support(self, text, subject="cloud security"):
        return extract_support(subject, {"url": "https://fixture.example/guide", "raw_content": text})[0]

    def test_saved_equivalent_grammatical_phrase_recovers_flattened_sentence(self):
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["excerpts"]
        exact = rows[-1]["text"]
        filler = "Unrelated introductory material about logistics. " * 80
        result = self.support(filler + exact + " " + filler)
        self.assertEqual(result["responsibilities"][0]["text"], exact)
        self.assertTrue(result["evidence_predicates"])
        self.assertFalse(result["definition"])
        self.assertFalse(result["exclusions"])

    def test_variants_are_grammatical_not_semantic_synonyms(self):
        result = self.support("Coordination of protocols is an engineering practice.", "protocols coordination")
        self.assertTrue(result["definition"])
        for text in ("Security protects payment data.", "Security staff assess cloud costs.",
                     "Cloud usage is convenient.", "Cloud Security Alliance includes members."):
            self.assertFalse(any(self.support(text).values()))

    def test_flattened_neighbours_do_not_inherit_subject(self):
        filler = "Unrelated introductory material about logistics. " * 80
        result = self.support(filler + "Cloud security is an engineering practice. "
                              "Documented billing configuration and validated tests demonstrate evidence.")
        self.assertTrue(result["definition"])
        self.assertFalse(result["evidence_predicates"])

    def test_heading_inheritance_is_one_body_and_stops_at_next_heading(self):
        text = ("# Cloud security\n\nThis practice is an engineering practice.\n\n"
                "# Billing\n\nDocumented billing configuration and validated tests demonstrate evidence.")
        result = self.support(text)
        self.assertTrue(result["definition"])
        self.assertFalse(result["evidence_predicates"])

    def test_negation_and_exclusions_survive_sentence_recovery(self):
        filler = "Unrelated introductory material about logistics. " * 80
        sentence = "Cloud security excludes generic cloud usage, which does not prove implementation."
        result = self.support(filler + sentence)
        self.assertEqual(result["exclusions"][0]["text"], sentence)
        self.assertFalse(result["evidence_predicates"])

    def test_predicates_require_observable_implementation(self):
        for text in ("Cloud security requires evidence.", "Cloud security uses cloud services.",
                     "Cloud security logs alone do not demonstrate implementation."):
            self.assertFalse(self.support(text)["evidence_predicates"])
        self.assertTrue(self.support("Cloud security configuration was implemented and validated through tests.")["evidence_predicates"])

    def test_saved_800144_scope_is_not_a_capability_definition(self):
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["excerpts"]
        for row in rows[:-1]:
            self.assertFalse(self.support(row["text"])["definition"])

    def test_reference_lists_and_oversized_unsplittable_text_fail_closed(self):
        filler = "Unrelated introductory material about logistics. " * 80
        for reference in ("[ABC11] Cloud security implementation guide.",
                          "References: Cloud security configuration implemented and validated."):
            self.assertFalse(any(self.support(filler + reference).values()))
        self.assertEqual(list(subject_blocks("cloud security", "cloud security " + "word " * 700)), [])
