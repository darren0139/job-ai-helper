from __future__ import annotations

import unittest
from pathlib import Path

from tailoring.capability_taxonomy import get_default_taxonomy
from taxonomy_discovery.focused_verification_targets import (
    RELATIONSHIP_FOLLOWUP_VERSION,
    TARGET_REGISTRY_RELATIONSHIP,
    build_relationship_followup_target,
)


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "taxonomy_discovery" / "focused_verification_ui.py"


class TQD3RelationshipFollowupTests(unittest.TestCase):
    def _source_target(self) -> dict:
        return {
            "target_version":
                "tqd3-focused-verification-targets-v1.0.0",
            "target_id":
                "tqd3verify_96b54e4ce6265b5d99201ab9",
            "candidate_id":
                "tqdmincand_79d4cbe046dbca1c0f66",
            "canonical_name":
                "Apache ActiveMQ",
            "route":
                "technology_identity",
            "taxonomy_capability_ids": [],
            "source_summary": {
                "supporting_sources": 2,
            },
            "governance": {
                "generated_from_confirmed_candidate": True,
            },
        }

    def test_followup_targets_existing_capability_without_approval(self):
        taxonomy = get_default_taxonomy()
        self.assertIn(
            "realtime.messaging_streaming",
            taxonomy.by_id(),
        )

        target = build_relationship_followup_target(
            source_target=self._source_target(),
            capability_id="realtime.messaging_streaming",
        )

        self.assertEqual(
            target["relationship_followup_version"],
            RELATIONSHIP_FOLLOWUP_VERSION,
        )
        self.assertEqual(
            target["route"],
            TARGET_REGISTRY_RELATIONSHIP,
        )
        self.assertEqual(
            target["taxonomy_capability_ids"],
            ["realtime.messaging_streaming"],
        )
        self.assertEqual(
            target["followup_of_target_id"],
            self._source_target()["target_id"],
        )
        self.assertTrue(
            target["governance"][
                "generated_from_verified_identity"
            ]
        )
        self.assertFalse(
            target["governance"]["selection_is_approval"]
        )
        self.assertEqual(
            target["governance"]["registry_mutations"],
            0,
        )
        self.assertEqual(
            target["governance"]["taxonomy_mutations"],
            0,
        )
        self.assertFalse(
            target["governance"]["scoring_influence"]
        )

    def test_followup_target_is_deterministic(self):
        one = build_relationship_followup_target(
            source_target=self._source_target(),
            capability_id="realtime.messaging_streaming",
        )
        two = build_relationship_followup_target(
            source_target=self._source_target(),
            capability_id="realtime.messaging_streaming",
        )
        self.assertEqual(
            one["target_id"],
            two["target_id"],
        )

    def test_unknown_capability_fails_closed(self):
        with self.assertRaises(ValueError):
            build_relationship_followup_target(
                source_target=self._source_target(),
                capability_id="not.a.real.capability",
            )

    def test_ui_exposes_explicit_relationship_research(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn(
            "Research selected capability relationship",
            source,
        )
        self.assertIn(
            "Selecting a capability below creates a focused research target",
            source,
        )
        self.assertIn(
            "followup_of_target_id",
            source,
        )
        self.assertIn(
            "generated_from_verified_identity",
            source,
        )
        self.assertIn(
            "explicit_execution=True",
            source,
        )


if __name__ == "__main__":
    unittest.main()
