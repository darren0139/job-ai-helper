from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from database.global_blueprint_manager import (
    PRIMARY_BLUEPRINT_VARIANT_ID,
    PRIMARY_BLUEPRINT_VARIANT_LABEL,
    blueprint_variant_id,
    normalise_blueprint_variant_label,
)
from tailoring.phase9e_blueprint_selection import (
    PHASE9E_RECOMMENDATION_POLICY_VERSION,
    recommend_active_blueprint,
)


def _blueprint(blueprint_id: str, *, family: str, variant: str) -> dict:
    return {
        "blueprint_id": blueprint_id,
        "blueprint_fingerprint": f"{blueprint_id}-fingerprint",
        "status": "active",
        "role_family_id": family,
        "role_family_label": family.replace("_", " ").title(),
        "variant_id": variant,
        "variant_label": variant.replace("_", " ").title(),
        "version_number": 1,
        "availability_status": "available",
        "is_reusable": True,
    }


def _comparison(overall: int, required: int, evidence: int, preferred: int = 0):
    return {
        "deterministic_alignment_score": overall,
        "required_core_coverage_score": required,
        "preferred_coverage_score": preferred,
        "evidence_strength_score": evidence,
        "important_gap_count": 0,
        "deal_breaker_gap_count": 0,
    }


class Phase9EBlueprintVariantTests(unittest.TestCase):
    def test_variant_normalisation_defaults_to_primary(self):
        self.assertEqual(
            normalise_blueprint_variant_label(""),
            PRIMARY_BLUEPRINT_VARIANT_LABEL,
        )
        self.assertEqual(
            blueprint_variant_id(""),
            PRIMARY_BLUEPRINT_VARIANT_ID,
        )
        self.assertEqual(
            blueprint_variant_id("C++ / Engine Focus"),
            "cpp_engine_focus",
        )

    def test_multiple_same_family_variants_are_ranked_not_rejected(self):
        general = "general_software_engineering"
        rows = [
            _blueprint("bp-a", family=general, variant="backend"),
            _blueprint("bp-b", family=general, variant="engine"),
        ]
        scores = {
            "bp-a": _comparison(68, 70, 66),
            "bp-b": _comparison(82, 88, 80),
        }

        def fake_starting(blueprint):
            return {"source_identity": {"blueprint_id": blueprint["blueprint_id"]}}

        def fake_eval(snapshot, jd, *, preferred_requirements=None):
            del jd, preferred_requirements
            return scores[snapshot["source_identity"]["blueprint_id"]]

        with (
            patch(
                "tailoring.phase9e_blueprint_selection.validate_exact_jd_snapshot",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.suggest_role_family",
                return_value={
                    "role_family_id": general,
                    "role_family": "General Software Engineering",
                    "confidence": "low",
                    "matched_terms": [],
                    "suggestion_method": "test",
                },
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.validate_active_blueprint",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.build_blueprint_starting_snapshot",
                side_effect=fake_starting,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
                side_effect=fake_eval,
            ),
        ):
            result = recommend_active_blueprint({"jd_profile": {}}, rows)

        self.assertEqual(
            result["recommended_blueprint"]["blueprint_id"],
            "bp-b",
        )
        self.assertEqual(len(result["same_family_rankings"]), 2)

    def test_cross_family_high_score_is_diagnostic_not_auto_recommended(self):
        general = "general_software_engineering"
        rows = [
            _blueprint("same-family", family=general, variant="primary"),
            _blueprint(
                "cross-family",
                family="ai_fullstack_software_engineering",
                variant="primary",
            ),
        ]
        scores = {
            "same-family": _comparison(72, 75, 70),
            "cross-family": _comparison(96, 97, 95),
        }

        def fake_starting(blueprint):
            return {"source_identity": {"blueprint_id": blueprint["blueprint_id"]}}

        def fake_eval(snapshot, jd, *, preferred_requirements=None):
            del jd, preferred_requirements
            return scores[snapshot["source_identity"]["blueprint_id"]]

        with (
            patch(
                "tailoring.phase9e_blueprint_selection.validate_exact_jd_snapshot",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.suggest_role_family",
                return_value={
                    "role_family_id": general,
                    "role_family": "General Software Engineering",
                    "confidence": "low",
                    "matched_terms": [],
                    "suggestion_method": "test",
                },
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.validate_active_blueprint",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.build_blueprint_starting_snapshot",
                side_effect=fake_starting,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
                side_effect=fake_eval,
            ),
        ):
            result = recommend_active_blueprint({"jd_profile": {}}, rows)

        self.assertEqual(
            result["best_diagnostic_blueprint"]["blueprint_id"],
            "cross-family",
        )
        self.assertEqual(
            result["recommended_blueprint"]["blueprint_id"],
            "same-family",
        )

    def test_removed_active_blueprint_is_excluded_from_ranking(self):
        general = "general_software_engineering"
        available = _blueprint(
            "available",
            family=general,
            variant="primary",
        )
        removed = _blueprint(
            "removed",
            family=general,
            variant="engine",
        )
        removed["availability_status"] = "removed"
        removed["is_reusable"] = False
        rows = [available, removed]
        scores = {
            "available": _comparison(70, 75, 70),
            "removed": _comparison(99, 99, 99),
        }

        def fake_starting(blueprint):
            return {
                "source_identity": {
                    "blueprint_id": blueprint["blueprint_id"]
                }
            }

        def fake_eval(snapshot, jd, *, preferred_requirements=None):
            del jd, preferred_requirements
            return scores[snapshot["source_identity"]["blueprint_id"]]

        with (
            patch(
                "tailoring.phase9e_blueprint_selection.validate_exact_jd_snapshot",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.suggest_role_family",
                return_value={
                    "role_family_id": general,
                    "role_family": "General Software Engineering",
                    "confidence": "low",
                    "matched_terms": [],
                    "suggestion_method": "test",
                },
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.validate_active_blueprint",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.build_blueprint_starting_snapshot",
                side_effect=fake_starting,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
                side_effect=fake_eval,
            ),
        ):
            result = recommend_active_blueprint({"jd_profile": {}}, rows)

        self.assertEqual(
            result["recommended_blueprint"]["blueprint_id"],
            "available",
        )
        self.assertEqual(
            [row["blueprint_id"] for row in result["active_blueprints"]],
            ["available"],
        )

    def test_no_same_family_keeps_original_as_safe_recommendation(self):
        rows = [
            _blueprint(
                "cross-family",
                family="ai_fullstack_software_engineering",
                variant="primary",
            )
        ]
        with (
            patch(
                "tailoring.phase9e_blueprint_selection.validate_exact_jd_snapshot",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.suggest_role_family",
                return_value={
                    "role_family_id": "general_software_engineering",
                    "role_family": "General Software Engineering",
                    "confidence": "low",
                    "matched_terms": [],
                    "suggestion_method": "test",
                },
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.validate_active_blueprint",
                side_effect=lambda value: value,
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.build_blueprint_starting_snapshot",
                return_value={"source_identity": {"blueprint_id": "cross-family"}},
            ),
            patch(
                "tailoring.phase9e_blueprint_selection.evaluate_starting_snapshot",
                return_value=_comparison(95, 95, 95),
            ),
        ):
            result = recommend_active_blueprint({"jd_profile": {}}, rows)

        self.assertIsNone(result["recommended_blueprint"])
        self.assertEqual(result["recommended_source"], "original_resume")

    def test_schema_uses_one_active_blueprint_per_variant_lane(self):
        source = Path("database/global_blueprint_manager.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("idx_global_blueprint_one_active_variant", source)
        self.assertIn(
            "ON global_blueprint_versions (role_family_id, variant_id)",
            source,
        )
        self.assertIn(
            "DROP INDEX IF EXISTS idx_global_blueprint_one_active",
            source,
        )
        self.assertIn("idx_global_blueprint_variant_history", source)

    def test_phase9e_ui_uses_only_reusable_blueprints(self):
        source = Path(
            "tailoring/phase9e_blueprint_selection_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("list_reusable_global_blueprints()", source)
        self.assertNotIn(
            "list_global_blueprints(include_superseded=False)",
            source,
        )

    def test_variant_identity_is_carried_into_phase9e_source_identity(self):
        source = Path(
            "tailoring/phase9e_blueprint_selection.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"variant_id": _clean(blueprint.get("variant_id"))', source)
        self.assertIn(
            '"variant_label": _clean(blueprint.get("variant_label"))',
            source,
        )

    def test_recommendation_policy_is_versioned(self):
        self.assertEqual(
            PHASE9E_RECOMMENDATION_POLICY_VERSION,
            "phase9e-ranked-reusable-blueprint-variants-v3",
        )


if __name__ == "__main__":
    unittest.main()
