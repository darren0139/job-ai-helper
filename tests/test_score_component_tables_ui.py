"""Tests for read-only component tables and deterministic exports."""
from __future__ import annotations

import csv
import io
import json
import unittest
from zipfile import ZipFile

from tailoring.score_component_tables_ui import (
    build_component_tables, component_exports, component_zip, summary_card_csv,
)


def _sample():
    # Independent synthetic 20-row representation of the user's 16/100 example.
    # No résumé evidence, live DB data, network or scorer calls.
    weights = [4] + [3] * 8 + [1] * 6
    importance = ["required"] + ["core"] * 14 + ["preferred"] * 5
    rows, breakdown_rows = [], []
    credited = {1, 2, 15, 16}  # two core and two preferred: four equal native strengths
    for i, imp in enumerate(importance):
        preferred = imp == "preferred"
        weight = 1 if preferred else weights[i]
        ref = (10 * weight / 5) if preferred else (80 * weight / 34)
        value = .55 if i in credited else 0.0
        evidence = 1.5 if i in credited else 0.0
        cov = ref * value
        current = round(cov,6) + evidence
        rows.append({
            "requirement_id": f"req_{i:02d}", "requirement": f"Synthetic requirement {i}",
            "importance": imp, "match_label": "transferable" if value else "none",
            "match_value": value, "effective_weight": weight,
            "coverage_max_final_points": ref, "evidence_max_final_points": .5,
            "max_final_points": ref + .5, "current_final_points": current,
            "gap_to_max": max(0, ref + .5 - current),
        })
        breakdown_rows.append({
            "requirement_id": f"req_{i:02d}", "requirement": f"Synthetic requirement {i}",
            "match_label": "transferable" if value else "none",
            "evidence_strength": 3 if value else 0,
            "overall_evidence_points": evidence,
        })
    required_earned = 80 * (3 * .55 + 3 * .55) / 34
    preferred_earned = 10 * (1 * .55 + 1 * .55) / 5
    sub = required_earned + preferred_earned + 6
    receipt = {
        "version": "phase8-score-receipt-v2-jd-map", "stored_scorer_score": 16,
        "subtotal_before_rounding": sub, "maximum_score": 100,
        "jd_requirements": rows,
        "components": [
            {"kind":"required_core", "label":"Required/Core coverage", "score": required_earned/.8,"weight":.8,"weighted_points":required_earned},
            {"kind":"preferred", "label":"Preferred coverage", "score":22,"weight":.1,"weighted_points":preferred_earned},
            {"kind":"evidence", "label":"Evidence strength", "score":60,"weight":.1,"weighted_points":6.},
        ],
        "pools": [
            {"kind": "required_core", "denominator_display": "34.000 raw weight"},
            {"kind": "preferred", "denominator_display": "5.000 raw weight"},
            {"kind": "evidence", "denominator_display": "5 × 20 = 100 evidence units"},
        ],
        "score_parity": True, "component_subtotal_parity": True,
        "requirement_subtotal_parity": True, "maximum_score_parity": True,
        "jd_requirement_max_total_parity": True,
    }
    breakdown = {"requirements": breakdown_rows, "explainability_version": "phase8-score-explainability-v1"}
    return receipt, breakdown


class ScoreComponentTablesTests(unittest.TestCase):
    def test_groups_and_native_components(self):
        receipt, breakdown = _sample()
        result = build_component_tables(receipt, breakdown=breakdown)
        self.assertEqual((len(result["required_core"]), len(result["preferred"])), (15, 5))
        self.assertAlmostEqual(sum(r["coverage_earned_points"] for r in result["required_core"]), 7.76470588235294)
        self.assertAlmostEqual(sum(r["coverage_earned_points"] for r in result["preferred"]), 2.2)
        self.assertEqual(result["evidence_detail"], "native_proportional_allocation")
        self.assertAlmostEqual(sum(r["evidence_earned_points"] for r in result["evidence_strength"]), 6.)
        self.assertAlmostEqual(result["overall"][3]["earned_points"], 15.96470588235294)
        self.assertEqual(result["overall"][4]["earned_points"], 16)

    def test_reference_allocation_is_not_hard_earned_ceiling(self):
        receipt, breakdown = _sample()
        tables = build_component_tables(receipt, breakdown=breakdown)
        # Nominal reference 2.5 and earned 2.6 in the two preferred cases.
        self.assertEqual(tables["over_allocation_reference_ids"], ["req_15", "req_16"])
        self.assertAlmostEqual(receipt["jd_requirements"][15]["current_final_points"], 2.6)
        self.assertAlmostEqual(tables["preferred"][0]["coverage_earned_points"], 1.1)
        self.assertAlmostEqual(tables["evidence_strength"][15]["evidence_earned_points"], 1.5)

    def test_fails_closed_on_missing_parity_or_score(self):
        receipt, breakdown = _sample()
        receipt["requirement_subtotal_parity"] = False
        with self.assertRaises(ValueError): build_component_tables(receipt, breakdown=breakdown)
        receipt["requirement_subtotal_parity"] = True
        receipt["stored_scorer_score"] = 80
        with self.assertRaises(ValueError): build_component_tables(receipt, breakdown=breakdown)
        receipt["stored_scorer_score"] = 16
        receipt["components"][0]["weighted_points"] = 10
        with self.assertRaises(ValueError): build_component_tables(receipt, breakdown=breakdown)

    def test_invalid_importance_and_unrecognized_floats_fail(self):
        receipt, breakdown = _sample()
        receipt["jd_requirements"][0]["importance"] = "unclassified"
        with self.assertRaises(ValueError): build_component_tables(receipt, breakdown=breakdown)
        receipt, breakdown = _sample()
        receipt["jd_requirements"][0]["match_value"] = float("nan")
        with self.assertRaises(ValueError): build_component_tables(receipt, breakdown=breakdown)

    def test_without_native_evidence_allocation_only_aggregate(self):
        receipt, _ = _sample()
        tables = build_component_tables(receipt)
        self.assertEqual(tables["evidence_detail"], "aggregate_only")
        self.assertEqual(len(tables["evidence_strength"]), 1)
        self.assertEqual(tables["evidence_strength"][0]["evidence_earned_points"], 6.)

    def test_csv_and_deterministic_zip_roundtrip(self):
        receipt, breakdown = _sample()
        tables = build_component_tables(receipt, breakdown=breakdown, origin="test")
        files = component_exports(tables, legacy_csv="a,b\nx,y\n")
        self.assertEqual(len(files), 6)
        raw = csv.DictReader(io.StringIO(files["preferred.csv"].decode("utf-8-sig")))
        rows = list(raw)
        self.assertEqual(len(rows), 5)
        self.assertAlmostEqual(float(rows[0]["coverage_earned_points"]), 1.1)
        self.assertEqual(files["legacy_score_map.csv"].decode("utf-8-sig"), "a,b\nx,y\n")
        payload = component_zip(files)
        self.assertEqual(payload, component_zip(files))
        with ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(sorted(archive.namelist()), sorted(files))
            self.assertEqual(json.loads(archive.read("manifest.json"))["stored_score"], 16)
            self.assertEqual(archive.read("overall.csv"), files["overall.csv"])

    def test_summary_card_does_not_invent_weighted_points(self):
        content = summary_card_csv({"deterministic_alignment_score": 12,
                                    "required_core_coverage_score": 5,
                                    "preferred_coverage_score": 18,
                                    "evidence_strength_score": 67}).decode("utf-8-sig")
        self.assertIn("Job Match,12,/100",content)
        self.assertIn("Preferred coverage,18,%",content)
        self.assertNotIn("weighted_points", content)


if __name__ == "__main__":
    unittest.main()
