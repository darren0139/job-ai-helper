from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.phase8_score_explainability import (
    build_requirement_change_rows,
    build_score_breakdown,
    build_score_receipt,
)


def row(rid, text, importance, label, value, strength, group=""):
    return {
        "requirement_id": rid,
        "text": text,
        "importance": importance,
        "match_label": label,
        "match_value": value,
        "evidence_strength": strength,
        "atomic_group_id": group or rid,
        "evidence": [{"text": f"Evidence for {text}"}] if label != "none" else [],
    }


class Phase8ScoreExplainabilityTests(unittest.TestCase):
    def test_score_math_matches_stable_formula(self):
        analysis = {
            "deterministic_alignment_score": 73,
            "canonical_requirements": [
                row("r1", "Required direct", "required", "direct", 1.0, 5),
                row("r2", "Core transferable", "core", "transferable", 0.55, 3),
                row("r3", "Preferred weak", "preferred", "weak", 0.20, 2),
            ],
        }
        result = build_score_breakdown(analysis)
        self.assertTrue(result["score_parity"])
        self.assertEqual(result["reconstructed_score"], 73)

    def test_atomic_children_share_parent_weight(self):
        analysis = {
            "deterministic_alignment_score": 55,
            "canonical_requirements": [
                row("a", "A", "required", "direct", 1.0, 5, "group"),
                row("b", "B", "required", "none", 0.0, 0, "group"),
            ],
        }
        result = build_score_breakdown(analysis)
        required = next(c for c in result["components"] if c["key"] == "required_core_coverage")
        self.assertEqual(round(required["score"]), 50)
        self.assertEqual(
            sorted(r["group_weight_fraction"] for r in result["requirements"]),
            [0.5, 0.5],
        )
        self.assertTrue(result["score_parity"])

    def test_raw_drop_can_be_displayed_as_reconciled(self):
        before = {
            "deterministic_alignment_score": 100,
            "canonical_requirements": [
                row("sec", "Security in CI/CD", "required", "direct", 1.0, 5)
            ],
        }
        after = {
            "deterministic_alignment_score": 100,
            "canonical_requirements": [
                row("sec", "Security in CI/CD", "required", "direct", 1.0, 5)
            ],
        }
        result = {
            "before_stable_analysis": before,
            "after_stable_analysis": after,
            "raw_comparison_before_reconciliation": {
                "regressed_requirements": [
                    {"requirement_id": "sec", "before_label": "direct", "after_label": "weak"}
                ]
            },
        }
        changes = build_requirement_change_rows(result)
        self.assertEqual(changes[0]["raw_after"], "weak")
        self.assertEqual(changes[0]["verified_after"], "direct")
        self.assertTrue(changes[0]["reconciliation_applied"])

    def test_requirement_points_reconcile_to_rounded_component_total(self) -> None:
        def _score_row(
            requirement_id: str,
            text: str,
            importance: str,
            label: str,
            value: float,
            strength: int,
        ) -> dict:
            return {
                "requirement_id": requirement_id,
                "text": text,
                "importance": importance,
                "match_label": label,
                "match_value": value,
                "evidence_strength": strength,
                "atomic_group_id": requirement_id,
                "evidence": (
                    [{"text": f"Evidence for {text}"}]
                    if label != "none"
                    else []
                ),
            }

        analysis = {
            "deterministic_alignment_score": 73,
            "canonical_requirements": [
                _score_row(
                    "req_required",
                    "Required direct",
                    "required",
                    "direct",
                    1.0,
                    5,
                ),
                _score_row(
                    "req_core",
                    "Core transferable",
                    "core",
                    "transferable",
                    0.55,
                    3,
                ),
                _score_row(
                    "req_preferred",
                    "Preferred weak",
                    "preferred",
                    "weak",
                    0.20,
                    2,
                ),
            ],
        }

        breakdown = build_score_breakdown(analysis)
        requirement_total = round(
            sum(
                float(row.get("overall_point_contribution", 0.0))
                for row in breakdown["requirements"]
            ),
            5,
        )
        component_total = round(
            sum(
                float(row.get("weighted_points", 0.0))
                for row in breakdown["components"]
            ),
            5,
        )

        self.assertEqual(requirement_total, component_total)
        self.assertTrue(breakdown["score_parity"])


    def test_score_receipt_maps_jd_requirements_to_100(self) -> None:
        def receipt_row(
            requirement_id: str,
            text: str,
            importance: str,
            label: str,
            value: float,
            strength: int,
        ) -> dict:
            return {
                "requirement_id": requirement_id,
                "text": text,
                "importance": importance,
                "match_label": label,
                "match_value": value,
                "evidence_strength": strength,
                "atomic_group_id": requirement_id,
                "evidence": (
                    [{"text": f"Evidence for {text}"}]
                    if label != "none"
                    else []
                ),
            }

        analysis = {
            "deterministic_alignment_score": 73,
            "canonical_requirements": [
                receipt_row(
                    "r1", "Required direct", "required", "direct", 1.0, 5
                ),
                receipt_row(
                    "r2",
                    "Core transferable",
                    "core",
                    "transferable",
                    0.55,
                    3,
                ),
                receipt_row(
                    "r3",
                    "Preferred weak",
                    "preferred",
                    "weak",
                    0.20,
                    2,
                ),
            ],
        }

        breakdown = build_score_breakdown(analysis)
        receipt = build_score_receipt(breakdown)

        self.assertEqual(receipt["final_score"], 73)
        self.assertAlmostEqual(receipt["maximum_score"], 100.0, places=6)
        self.assertTrue(receipt["maximum_score_parity"])
        self.assertTrue(receipt["component_subtotal_parity"])
        self.assertTrue(receipt["requirement_subtotal_parity"])
        self.assertTrue(receipt["jd_requirement_max_total_parity"])
        self.assertAlmostEqual(
            receipt["jd_requirement_max_total"],
            100.0,
            places=4,
        )
        self.assertEqual(
            [round(row["max_final_points"], 2) for row in receipt["pools"]],
            [80.0, 10.0, 10.0],
        )
        self.assertEqual(len(receipt["jd_requirements"]), 3)
        self.assertAlmostEqual(
            sum(
                float(row["max_final_points"])
                for row in receipt["jd_requirements"]
            ),
            100.0,
            places=4,
        )

    def test_score_receipt_without_preferred_uses_90_plus_10(self) -> None:
        def receipt_row(
            requirement_id: str,
            text: str,
            importance: str,
            label: str,
            value: float,
            strength: int,
        ) -> dict:
            return {
                "requirement_id": requirement_id,
                "text": text,
                "importance": importance,
                "match_label": label,
                "match_value": value,
                "evidence_strength": strength,
                "atomic_group_id": requirement_id,
                "evidence": [{"text": f"Evidence for {text}"}],
            }

        analysis = {
            "deterministic_alignment_score": 81,
            "canonical_requirements": [
                receipt_row(
                    "r1", "Required direct", "required", "direct", 1.0, 5
                ),
                receipt_row(
                    "r2",
                    "Core transferable",
                    "core",
                    "transferable",
                    0.55,
                    3,
                ),
            ],
        }

        receipt = build_score_receipt(build_score_breakdown(analysis))

        self.assertAlmostEqual(receipt["maximum_score"], 100.0, places=6)
        self.assertTrue(receipt["maximum_score_parity"])
        self.assertEqual(
            [round(row["max_final_points"], 2) for row in receipt["pools"]],
            [90.0, 10.0],
        )
        self.assertAlmostEqual(
            receipt["jd_requirement_max_total"],
            100.0,
            places=4,
        )

    def test_score_receipt_ui_contract(self) -> None:
        ui = Path(
            "tailoring/phase8_score_explainability_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("How {final_score}/100 was computed", ui)
        self.assertIn("Maximum possible score", ui)
        self.assertIn("Which JD requirements make up the 100 points?", ui)
        self.assertIn("Largest current alignment opportunities", ui)
        self.assertIn("Atomic children share their parent's importance weight", ui)
        self.assertIn("not an ATS pass ", ui)
        self.assertIn("probability or hiring likelihood.", ui)


    def test_score_receipt_v5_compact_and_export_contract(self) -> None:
        ui = Path(
            "tailoring/phase8_score_explainability_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _compact_requirement_text(", ui)
        self.assertIn('"JD requirement": _compact_requirement_text(', ui)
        self.assertIn("Show full JD requirement text", ui)
        self.assertIn("Download JD score map CSV", ui)
        self.assertIn("Download printable score explanation", ui)
        self.assertIn("phase8_jd_score_map.csv", ui)
        self.assertIn("phase8_score_explanation.html", ui)

    def test_score_receipt_v5_exports_keep_full_text_and_print_css(self) -> None:
        ui = Path(
            "tailoring/phase8_score_explainability_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"canonical_jd_requirement": row.get("requirement", "")', ui)
        self.assertIn("overflow-wrap: anywhere", ui)
        self.assertIn("@media print", ui)
        self.assertIn("Phase 8 Verification JSON download", ui)


if __name__ == "__main__":
    unittest.main()
