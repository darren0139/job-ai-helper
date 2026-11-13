"""V2.2: independent gerund responsibility vs wrapped continuation.

Read-only; no score version bump, DB mutation or reviewed manifest modification.
"""
from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    _REVIEW419_LEGACY_PARSER,
    _raw_jd_content_spans,
    canonicalise_requirements,
)
from tests.test_phase9f_ncs_419_compatibility_v2 import NCS_JD


class NCSV22LineBoundaryTests(unittest.TestCase):
    @staticmethod
    def _compact():
        return "\n".join(s for s in NCS_JD.splitlines() if s.strip()) + "\n"

    def test_single_newline_scope_equals_original_twelve_with_same_ids_and_importance(self):
        def rows(text):
            return canonicalise_requirements({}, text)["requirements"]
        original = rows(NCS_JD)
        compact = rows(self._compact())
        self.assertEqual(12, len(original))
        self.assertEqual(12, len(compact))
        self.assertEqual(
            [(x["requirement_id"], x["importance"]) for x in original],
            [(x["requirement_id"], x["importance"]) for x in compact],
        )
        self.assertTrue(any(x["text"].startswith("Execute unit") for x in compact))
        self.assertTrue(any(x["text"].startswith("Using configuration") for x in compact))
        self.assertFalse(any("testing Using configuration" in x["text"] for x in compact))

    def test_compact_has_separate_independent_responsibility_spans(self):
        spans = _raw_jd_content_spans(self._compact())
        for prefix in (
            "Execute unit, integration, system and user acceptance testing",
            "Using configuration management, integration and build automation tools",
            "Identify opportunities and suggest recommendations",
        ):
            found = [x for x in spans if x["text"].startswith(prefix)]
            self.assertEqual(1, len(found), prefix)
            self.assertEqual("responsibilities", found[0]["section"])
        self.assertFalse(_REVIEW419_LEGACY_PARSER.get())

    def test_lowercase_wrapped_using_continues_previous_responsibility(self):
        source = (
            "Responsibilities\n"
            "Develop and maintain robust software applications\n"
            "using configuration tools to deploy them reliably\n"
        )
        spans = _raw_jd_content_spans(source)
        self.assertEqual(1, len(spans))
        self.assertIn("applications using configuration tools", spans[0]["text"])

    def test_incomplete_previous_clause_still_joins_uppercase_using(self):
        source = (
            "Responsibilities\n"
            "Develop and maintain applications with\n"
            "Using configuration tools to deploy services\n"
        )
        spans = _raw_jd_content_spans(source)
        self.assertEqual(1, len(spans))
        self.assertIn("with Using configuration", spans[0]["text"])


if __name__ == "__main__":
    unittest.main()
