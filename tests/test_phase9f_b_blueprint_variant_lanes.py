"""Phase 9F-B ranking must honor active Phase 9D variant lanes."""
from __future__ import annotations

import copy
import unittest

from tailoring.phase9f_starting_source_ranking import (
    prepare_ranking_context,
    rank_prepared_context,
    rank_starting_resume_sources,
)
from tests.test_phase9f_starting_source_ranking import make_blueprint, make_exact_jd


FAMILY = "ai_fullstack_software_engineering"
LABEL = "AI & Full-Stack Software Engineering"


def bp(marker, lane):
    value = make_blueprint(
        strong=True,
        role_family_id=FAMILY,
        role_family_label=LABEL,
        marker=marker,
    )
    value["variant_id"] = lane
    value["variant_label"] = lane.replace("_", " ").title()
    return value


def ranked(rows):
    return rank_starting_resume_sources(
        exact_jd=make_exact_jd(),
        current_base_resume=None,
        current_base_artifact=None,
        global_blueprints=rows,
    )


class Phase9FBVariantLaneTests(unittest.TestCase):
    def test_two_distinct_same_family_lanes_are_ranked(self):
        primary = bp("variant-primary", "primary")
        specialised = bp("variant-engineering", "engine")
        result = ranked([primary, specialised])
        self.assertEqual(result["status"], "ranked")
        self.assertFalse(result["integrity_issues"])
        self.assertEqual(
            {row["source_id"] for row in result["ranked_candidates"]},
            {primary["blueprint_id"], specialised["blueprint_id"]},
        )
        self.assertEqual(len(result["ranked_candidates"]), 2)
        self.assertEqual(result["recommended_source"], result["ranked_candidates"][0])

    def test_reversed_variant_enumeration_has_identical_semantic_result(self):
        primary = bp("variant-order-primary", "primary")
        specialised = bp("variant-order-engine", "engine")
        first = ranked([primary, specialised])
        second = ranked([specialised, primary])
        self.assertEqual(first["status"], "ranked")
        self.assertEqual(first["ranking_input_fingerprint"], second["ranking_input_fingerprint"])
        self.assertEqual(first["ranking_fingerprint"], second["ranking_fingerprint"])
        self.assertEqual(
            [r["source_id"] for r in first["ranked_candidates"]],
            [r["source_id"] for r in second["ranked_candidates"]],
        )

    def test_second_active_blueprint_in_same_lane_fails_closed(self):
        first = bp("same-lane-a", "engine")
        second = bp("same-lane-b", "engine")
        result = ranked([first, second])
        self.assertEqual(result["status"], "integrity_failed")
        self.assertIsNone(result["recommended_source"])
        self.assertEqual(result["ranked_candidates"], [])
        self.assertIn(
            "multiple_active_blueprints_for_variant_lane",
            [item["code"] for item in result["integrity_issues"]],
        )

    def test_legacy_missing_lane_defaults_to_primary(self):
        old = make_blueprint(
            strong=True, role_family_id=FAMILY, role_family_label=LABEL,
            marker="legacy-no-lane",
        )
        result = ranked([old, bp("engine-modern", "engine")])
        self.assertEqual(result["status"], "ranked")
        self.assertEqual(len(result["ranked_candidates"]), 2)
        duplicate_primary = ranked([old, bp("explicit-primary", "primary")])
        self.assertEqual(duplicate_primary["status"], "integrity_failed")

    def test_invalid_second_variant_still_blocks_all_ranking(self):
        good = bp("valid-variant", "primary")
        corrupt = bp("corrupt-variant", "engine")
        corrupt["blueprint_snapshot"]["frozen_resume_snapshot"]["resume_text_snapshot"] += " changed"
        result = ranked([good, corrupt])
        self.assertEqual(result["status"], "integrity_failed")
        self.assertIsNone(result["recommended_source"])
        self.assertIn(
            "active_blueprint_frozen_content_mismatch",
            [item["code"] for item in result["integrity_issues"]],
        )

    def test_inactive_variant_excluded_and_does_not_claim_lane(self):
        inactive = bp("old-primary", "primary")
        inactive["status"] = "superseded"
        current = bp("new-primary", "primary")
        result = ranked([inactive, current])
        self.assertEqual(result["status"], "ranked")
        self.assertEqual(len(result["ranked_candidates"]), 1)
        self.assertEqual(result["ranked_candidates"][0]["source_id"], current["blueprint_id"])
        self.assertEqual(len(result["excluded_sources"]), 1)

    def test_duplicate_immutable_identity_still_fails_closed(self):
        original = bp("duplicate-source", "primary")
        result = ranked([original, copy.deepcopy(original)])
        self.assertEqual(result["status"], "integrity_failed")
        self.assertIsNone(result["recommended_source"])

    def test_prepared_context_is_read_only_and_source_stable(self):
        first = bp("no-mut-primary", "primary")
        second = bp("no-mut-special", "special")
        original = copy.deepcopy([first, second])
        context = prepare_ranking_context(
            exact_jd=make_exact_jd(),
            current_base_resume=None,
            current_base_artifact=None,
            global_blueprints=[first, second],
        )
        self.assertEqual(context["status"], "ready")
        self.assertEqual([first, second], original)
        result = rank_prepared_context(context)
        self.assertEqual(result["status"], "ranked")
        self.assertEqual([first, second], original)


if __name__ == "__main__":
    unittest.main()
