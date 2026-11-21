"""Structural atomic-list guard regression tests for current (non-419) JD extraction."""
from __future__ import annotations
import unittest
from analysis_stability import stable_evidence_scoring as scorer


class AtomicModifierCoalescingV13(unittest.TestCase):
    def _rows(self, text: str) -> list[dict]:
        return scorer._split_requirement_clauses(text, "core")

    def test_dynamic_responsive_interface_remains_meaningful(self) -> None:
        text = "Proficiency in building dynamic, responsive user interfaces using React.js and the modern JavaScript/TypeScript ecosystem"
        parts = [r["text"] for r in self._rows(text)]
        self.assertIn("Proficiency in building dynamic, responsive user interfaces using React.js", parts)
        self.assertNotIn("Proficiency in building dynamic", parts)
        self.assertNotIn("Proficiency in responsive user interfaces using React.js", parts)
        self.assertEqual(len(parts), 2)

    def test_complex_distributed_shared_object_is_not_truncated(self) -> None:
        text = "Familiarity with common design patterns, writing scalable code, and successfully integrating services within complex, distributed systems"
        parts = [r["text"] for r in self._rows(text)]
        self.assertEqual(len(parts), 3)
        self.assertIn("Familiarity with successfully integrating services within complex, distributed systems", parts)
        self.assertNotIn("Familiarity with distributed systems", parts)
        self.assertTrue(all(not p.endswith(" complex") for p in parts))

    def test_static_dynamic_manual_review_preserves_shared_noun(self) -> None:
        text = "Experience in performing penetration testing, secure code review, static, dynamic and manual source code review"
        parts = [r["text"] for r in self._rows(text)]
        self.assertEqual(len(parts), 3)
        self.assertIn("Experience in static, dynamic, manual source code review", parts)
        self.assertNotIn("Experience in static", parts)
        self.assertNotIn("Experience in dynamic", parts)

    def test_unrelated_competency_list_still_splits(self) -> None:
        text = "Experience in Python, Java, SQL"
        parts = [r["text"] for r in self._rows(text)]
        self.assertEqual(parts, ["Experience in Python", "Experience in Java", "Experience in SQL"])

    def test_example_alternatives_remain_coherent(self) -> None:
        text = "Experience with frameworks such as React, Vue, or Angular"
        parts = [r["text"] for r in self._rows(text)]
        self.assertEqual(parts, [text])

    def test_historical_419_scope_retains_prior_fragments(self) -> None:
        text = "Experience in performing penetration testing, secure code review, static, dynamic and manual source code review"
        tok = scorer._REVIEW419_LEGACY_PARSER.set(True)
        try:
            parts = [r["text"] for r in self._rows(text)]
        finally:
            scorer._REVIEW419_LEGACY_PARSER.reset(tok)
        self.assertIn("Experience in static", parts)
        self.assertIn("Experience in dynamic", parts)

    def test_full_jd_original_lineage_preserved(self) -> None:
        raw = "Requirements\n• Proficiency in building dynamic, responsive user interfaces using React.js and the modern JavaScript/TypeScript ecosystem"
        rows = scorer.canonicalise_requirements({}, raw)["requirements"]
        self.assertTrue(rows)
        self.assertTrue(all("raw_jd.requirements" in r.get("sources", []) for r in rows))
        self.assertTrue(all(r.get("source_provenance") for r in rows))


if __name__ == "__main__":
    unittest.main()
