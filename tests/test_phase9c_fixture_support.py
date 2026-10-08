from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import canonicalise_requirements
from tests.phase9c_fixture_support import (
    _refresh_current_source_seed,
    load_current_phase9c_fixture,
    load_historical_phase9c_fixture,
)


class Phase9CFrozenChildSeedTests(unittest.TestCase):
    def test_reviewed_children_preserve_parent_provenance_and_allocation(self):
        frozen = load_historical_phase9c_fixture()
        source = frozen["saved_jds"][0]
        canonical = canonicalise_requirements(
            jd_profile=copy.deepcopy(source["jd_profile"]),
            raw_jd_text=source["raw_text"],
        )["requirements"]
        by_id = {row["requirement_id"]: row for row in canonical}
        extensions = frozen["current_source_seed_extensions"]
        self.assertEqual(
            {row["requirement_id"] for row in extensions},
            {"req_a499f2c48f82", "req_a5790b06f63b"},
        )
        parent = next(
            row for row in frozen["candidate"]["evaluation_metadata"][
                "source_jd_requirement_summary"
            ] if row["requirement_id"] == "req_ca58b0414a31"
        )
        profile = frozen["candidate"]["resume_profile_snapshot"]
        for seed in extensions:
            with self.subTest(requirement_id=seed["requirement_id"]):
                row = by_id[seed["requirement_id"]]
                for key in (
                    "text", "importance", "parent_text", "atomic_group_id",
                    "scoring_parent_occurrence_id", "group_weight_fraction", "sources",
                ):
                    self.assertEqual(row[key], seed[key], key)
                self.assertEqual(row["semantic_type"], "candidate_requirement")
                self.assertEqual(seed["historical_parent_requirement_id"], parent["requirement_id"])
                self.assertEqual(seed["parent_text"], parent["text"])
                self.assertEqual(seed["match_label"], "direct")
                self.assertEqual(seed["evidence_strength"], 5)
                self.assertEqual(seed["capability_id"], "")
                self.assertTrue(any(
                    seed["evidence_text"] in item.get("bullets", [])
                    for item in profile[seed["evidence_section"]]
                ))
                self.assertIn(seed["evidence_text"], frozen["candidate"]["resume_text_snapshot"])
                # Each named child has its own explicit support in the frozen
                # project, rather than inheriting a label merely from a parent.
                concept = "Unity" if seed["requirement_id"] == "req_a5790b06f63b" else "C#"
                self.assertIn(concept, seed["evidence_text"])
                provenance = row["source_provenance"]
                self.assertEqual(len(provenance), 1)
                self.assertEqual(provenance[0]["parent_occurrence_id"], seed["scoring_parent_occurrence_id"])
                self.assertEqual(provenance[0]["parent_text"], parent["text"])
                self.assertEqual(provenance[0]["source_group_fraction"], 0.5)
        self.assertEqual(sum(by_id[seed["requirement_id"]]["group_weight_fraction"] for seed in extensions), 1.0)

    def test_historical_candidate_and_other_evidence_are_unchanged(self):
        frozen = load_historical_phase9c_fixture()
        before = copy.deepcopy(frozen)
        current = load_current_phase9c_fixture()
        self.assertEqual(load_historical_phase9c_fixture(), before)
        self.assertEqual(frozen["candidate"]["score_summary"]["approved_tailored_score"], 92)
        self.assertEqual(current["candidate"]["score_summary"]["approved_tailored_score"], 93)
        for key in ("resume_profile_snapshot", "resume_text_snapshot", "candidate_id", "candidate_fingerprint"):
            self.assertEqual(current["candidate"][key], frozen["candidate"][key])
        self.assertEqual(current["saved_jds"], frozen["saved_jds"])
        historical = {row["requirement_id"]: row for row in frozen["candidate"]["evaluation_metadata"]["source_jd_requirement_summary"]}
        for row in current["candidate"]["evaluation_metadata"]["source_jd_requirement_summary"]:
            if row["requirement_id"] in historical:
                for key in ("importance", "match_label", "evidence_strength", "capability_id"):
                    self.assertEqual(row[key], historical[row["requirement_id"]][key])

    def test_unknown_current_id_still_fails_closed(self):
        fixture = load_historical_phase9c_fixture()
        with patch("tests.phase9c_fixture_support.canonicalise_requirements", return_value={
            "requirements": [{"requirement_id": "req_unknown_synthetic"}]
        }):
            with self.assertRaisesRegex(RuntimeError, "no frozen historical evidence seed: req_unknown_synthetic"):
                _refresh_current_source_seed(fixture)

    def test_parent_seed_does_not_automatically_supply_child_evidence(self):
        fixture = load_historical_phase9c_fixture()
        fixture["current_source_seed_extensions"] = [
            row for row in fixture["current_source_seed_extensions"]
            if row["requirement_id"] != "req_a499f2c48f82"
        ]
        with self.assertRaisesRegex(RuntimeError, "no frozen historical evidence seed: req_a499f2c48f82"):
            _refresh_current_source_seed(fixture)


if __name__ == "__main__":
    unittest.main()
