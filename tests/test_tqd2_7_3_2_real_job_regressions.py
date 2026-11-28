from __future__ import annotations

import json
import unittest
from pathlib import Path

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    build_deterministic_keyword_match,
    build_stable_analysis,
    canonicalise_requirements,
    requirement_is_score_eligible,
)
from job_discovery.matching import build_profile_evidence_context
from tests.b213_policy_support import ACTIVE_B219C, ROLLBACK_B219A, EXPECTED_SCORING_VERSION


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "ci_fixtures"
    / "tqd2_7_3_2_real_job_regressions_v1.json"
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


class TQD2732RealJobRegressionTests(unittest.TestCase):
    """Real-snapshot characterization of structure and recovery contracts.

    Gemini is a permanent evidence-recovery invariant.

    ST Engineering captures the approved post-integration structure result.
    TESCOM Maintenance remains a characterization of known decomposition
    behavior. Any change still requires a semantic diff before updating it.
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

    def test_st_engineering_structure_integration_characterization(self) -> None:
        case = self.fixture["fixtures"]["st_engineering"]
        baseline = case["baseline"]
        result = self._analyze("st_engineering")
        rows = self._eligible_rows(result)
        texts = [
            _clean(row.get("atomic_focus") or row.get("text"))
            for row in rows
        ]

        # The custom responsibility heading is now inferred from its coherent
        # child list, while the later employer-offer section remains excluded.
        # The historical fixture remains at 12. B2.19a legitimately removes
        # the game-QA cap from this software-testing responsibility; B2.19b
        # does not alter any row. No full implementation claim is permitted.
        self.assertEqual(baseline["deterministic_alignment_score"], 12)
        self.assertEqual(SCORING_VERSION, EXPECTED_SCORING_VERSION)
        self.assertIn(SCORING_VERSION, (ACTIVE_B219C, ROLLBACK_B219A))
        for key, expected in {
            "deterministic_alignment_score": 20,
            "required_core_coverage_score": 14,
            "preferred_coverage_score": 18,
            "evidence_strength_score": 73,
        }.items():
            self.assertEqual(result.get(key), expected, key)
        fields = ("requirement_id", "importance", "match_label", "match_value", "evidence_strength", "match_source")
        expected_rows = [('req_d8a925b5b34e', 'supporting', 'none', 0.0, 0, 'missing'),
         ('req_4731e7fdb9f1', 'supporting', 'none', 0.0, 0, 'missing'),
         ('req_26d895b9a27f', 'core', 'none', 0.0, 0, 'missing'),
         ('req_3f3b3d88b57d', 'core', 'transferable', 0.55, 3, 'capability_none_recovery'),
         ('req_dbfa330d23eb', 'core', 'none', 0.0, 0, 'missing'),
         ('req_52969cf18afc', 'core', 'none', 0.0, 0, 'missing'),
         ('req_30482086845a', 'supporting', 'none', 0.0, 0, 'missing'),
         ('req_ff55125c928e', 'supporting', 'none', 0.0, 0, 'missing'),
         ('req_cfc6614dce69', 'preferred', 'transferable', 0.55, 3, 'present'),
         ('req_c3b362e0255b', 'preferred', 'none', 0.0, 0, 'missing'),
         ('req_09f08d68e520', 'preferred', 'direct', 1.0, 5, 'capability_none_recovery'),
         ('req_67c5d07c55c1', 'preferred', 'none', 0.0, 0, 'missing'),
         ('req_73ffb410c613', 'preferred', 'none', 0.0, 0, 'missing'),
         ('req_74e080b49b36', 'supporting', 'none', 0.0, 0, 'missing'),
         ('req_ba468f2924d8', 'supporting', 'none', 0.0, 0, 'missing'),
         ('req_b57c19e5162c', 'preferred', 'none', 0.0, 0, 'missing'),
         ('req_193aa89d8bb0', 'preferred', 'none', 0.0, 0, 'missing')]
        self.assertEqual([tuple(row.get(key) for key in fields) for row in rows], expected_rows)
        testing = [row for row in rows if row.get("requirement_id") == "req_3f3b3d88b57d"]
        self.assertEqual(len(testing), 1)
        qa = testing[0]
        self.assertEqual(qa.get("capability_id"), "quality.qa_testing")
        self.assertEqual(len(qa.get("evidence") or []), 1)
        evidence = qa["evidence"][0]
        self.assertEqual(evidence.get("evidence_id"), "ev_302f4032e7e5")
        self.assertIn("Added automated unit tests and GitHub Actions CI", evidence.get("text", ""))
        recovery = qa.get("capability_none_recovery") or {}
        self.assertEqual(recovery.get("taxonomy_reason"), "software_testing_activity_bounded_to_requested_scope")
        self.assertEqual(recovery.get("recovered_label"), "transferable")
        self.assertIs(recovery.get("combined_evidence_rows"), False)
        self.assertEqual(len(rows), baseline["requirement_count"])
        self.assertIn(baseline["known_missing_requirement"], texts)
        self.assertNotIn(baseline["known_included_non_requirement"], texts)

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
