from __future__ import annotations

import json
import unittest
from pathlib import Path

from analysis_stability.stable_evidence_scoring import (
    build_deterministic_keyword_match,
    build_stable_analysis,
    canonicalise_requirements,
    requirement_is_score_eligible,
)
from job_discovery.matching import build_profile_evidence_context


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "ci_fixtures"
    / "tqd2_7_3_2_real_job_regressions_v1.json"
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


class TQD2732RealJobRegressionTests(unittest.TestCase):
    """Real-snapshot characterization before JD-structure integration.

    Gemini is a permanent evidence-recovery invariant.

    ST Engineering and TESCOM Maintenance intentionally characterize known
    pre-merge behavior. If JD-structure integration changes those tests, inspect
    the semantic diff first; do not blindly update the expected values.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.context = build_profile_evidence_context(
            cls.fixture["common_evidence_items"]
        )
        cls.results: dict[str, dict] = {}

    @classmethod
    def _analyze(cls, fixture_key: str) -> dict:
        if fixture_key in cls.results:
            return cls.results[fixture_key]

        case = cls.fixture["fixtures"][fixture_key]
        raw_jd_text = case["raw_jd_text"]
        jd_profile = case["jd_profile"]

        canonical = canonicalise_requirements(
            jd_profile=jd_profile,
            raw_jd_text=raw_jd_text,
        )
        keyword_match = build_deterministic_keyword_match(
            requirements=canonical.get("requirements", []) or [],
            acronym_map=canonical.get("acronym_map", {}) or {},
            resume_profile=cls.context["resume_profile"],
            raw_resume_text=cls.context["raw_resume_text"],
        )
        result = build_stable_analysis(
            jd_profile=jd_profile,
            keyword_match=keyword_match,
            raw_jd_text=raw_jd_text,
            raw_resume_text=cls.context["raw_resume_text"],
            resume_profile=cls.context["resume_profile"],
            bullet_quality_score=0,
            structure_score=0,
        )
        cls.results[fixture_key] = result
        return result

    @staticmethod
    def _eligible_rows(result: dict) -> list[dict]:
        return [
            row
            for row in result.get("canonical_requirements", []) or []
            if isinstance(row, dict) and requirement_is_score_eligible(row)
        ]

    def test_gemini_capability_none_recovery_survives(self) -> None:
        case = self.fixture["fixtures"]["gemini"]
        baseline = case["baseline"]
        result = self._analyze("gemini")
        rows = self._eligible_rows(result)

        qa_rows = [
            row
            for row in rows
            if _clean(row.get("atomic_focus") or row.get("text"))
            == baseline["qa_requirement"]
        ]
        self.assertEqual(len(qa_rows), 1)
        qa = qa_rows[0]
        self.assertEqual(qa.get("capability_id"), baseline["qa_capability_id"])
        self.assertEqual(qa.get("match_label"), baseline["qa_expected_label"])
        self.assertEqual(qa.get("match_source"), baseline["qa_expected_source"])
        self.assertEqual(len(qa.get("evidence", []) or []), 1)
        self.assertIn(
            baseline["qa_evidence_contains"],
            str(qa["evidence"][0].get("text") or ""),
        )
        recovery = qa.get("capability_none_recovery") or {}
        self.assertEqual(recovery.get("status"), "recovered_from_none")
        self.assertFalse(bool(recovery.get("combined_evidence_rows")))

        cpp_rows = [
            row
            for row in rows
            if baseline["cpp_requirement_contains"]
            in _clean(row.get("atomic_focus") or row.get("text"))
        ]
        self.assertEqual(len(cpp_rows), 1)
        cpp = cpp_rows[0]
        self.assertEqual(cpp.get("capability_id"), baseline["cpp_capability_id"])
        self.assertEqual(cpp.get("match_label"), baseline["cpp_expected_label"])
        self.assertEqual(cpp.get("match_source"), baseline["cpp_expected_source"])
        self.assertGreater(result.get("deterministic_alignment_score", 0), 0)

    def test_st_engineering_premerge_structure_characterization(self) -> None:
        case = self.fixture["fixtures"]["st_engineering"]
        baseline = case["baseline"]
        result = self._analyze("st_engineering")
        rows = self._eligible_rows(result)
        texts = [
            _clean(row.get("atomic_focus") or row.get("text"))
            for row in rows
        ]

        # This is a characterization of the current problem, not the desired
        # final behavior. The JD-structure branch is expected to invalidate
        # some/all of these assertions; inspect that diff before updating them.
        self.assertEqual(
            result.get("deterministic_alignment_score"),
            baseline["deterministic_alignment_score"],
        )
        self.assertEqual(len(rows), baseline["requirement_count"])
        self.assertNotIn(baseline["known_missing_requirement"], texts)
        self.assertIn(baseline["known_included_non_requirement"], texts)

    def test_maintenance_atomic_split_and_zero_overlap_weak_recovery_is_blocked(
        self,
    ) -> None:
        case = self.fixture["fixtures"]["tescom_maintenance"]
        baseline = case["baseline"]
        result = self._analyze("tescom_maintenance")
        rows = self._eligible_rows(result)
        texts = [
            _clean(row.get("atomic_focus") or row.get("text"))
            for row in rows
        ]

        # Known decomposition issue captured before JD-structure integration.
        self.assertIn(baseline["bad_atomic_child_1"], texts)
        self.assertIn(baseline["bad_atomic_child_2"], texts)

        # D2.7.3.2.2 resolves the pre-merge policy review: a weak
        # capability proxy at zero deterministic requirement/evidence overlap
        # must remain none.
        questionable = [
            row
            for row in rows
            if _clean(row.get("atomic_focus") or row.get("text"))
            == baseline["questionable_requirement"]
        ]
        self.assertEqual(len(questionable), 1)
        row = questionable[0]
        self.assertEqual(
            row.get("capability_id"),
            baseline["questionable_capability_id"],
        )
        self.assertEqual(row.get("match_label"), "none")
        self.assertNotEqual(
            row.get("match_source"),
            "capability_none_recovery",
        )
        self.assertEqual(row.get("evidence", []) or [], [])


if __name__ == "__main__":
    unittest.main()
