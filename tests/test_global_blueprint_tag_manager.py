from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base_manager
import database.global_blueprint_manager as global_blueprint_manager_module
import database.phase9f_exact_verified_reuse_manager as exact_reuse_module
from database.global_blueprint_manager import (
    VARIANT_INTENT_CREATE_NEW,
    approve_persisted_phase9c_evaluation,
)
from database.global_blueprint_tag_manager import (
    create_blueprint_tag,
    get_blueprint_lane_tags,
    init_global_blueprint_tag_registry,
    list_blueprint_tag_events,
    list_blueprint_tags,
    set_blueprint_lane_tags,
    update_blueprint_tag,
)
from tests.phase9d_test_support import (
    persist_non_provisional_evaluation,
    seed_phase9d_database,
)


OVERRIDE = {
    "accepted": True,
    "reason": "Tag metadata test provisional acknowledgement.",
}


class GlobalBlueprintTagManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.old_path = base_manager.DB_PATH
        self.old_artifact_roots = (
            global_blueprint_manager_module.BLUEPRINT_ARTIFACT_ROOT,
            exact_reuse_module.BLUEPRINT_ARTIFACT_ROOT,
        )
        artifact_root = Path(self.temporary.name) / "blueprint-artifacts"
        global_blueprint_manager_module.BLUEPRINT_ARTIFACT_ROOT = artifact_root
        exact_reuse_module.BLUEPRINT_ARTIFACT_ROOT = artifact_root
        self.database_path = Path(self.temporary.name) / "tag-manager.sqlite"
        self.state = seed_phase9d_database(self.database_path)

    def tearDown(self) -> None:
        base_manager.DB_PATH = self.old_path
        (
            global_blueprint_manager_module.BLUEPRINT_ARTIFACT_ROOT,
            exact_reuse_module.BLUEPRINT_ARTIFACT_ROOT,
        ) = self.old_artifact_roots
        self.temporary.cleanup()

    def _create_two_lanes(self):
        provisional = self.state["provisional_evaluation"]
        primary = approve_persisted_phase9c_evaluation(
            evaluation_id=provisional["evaluation_id"],
            evaluation_fingerprint=provisional["evaluation_fingerprint"],
            provisional_override=OVERRIDE,
            actor_label="Tag test",
        )["blueprint"]
        non_provisional = persist_non_provisional_evaluation(self.state)
        backend = approve_persisted_phase9c_evaluation(
            evaluation_id=non_provisional["evaluation_id"],
            evaluation_fingerprint=non_provisional["evaluation_fingerprint"],
            variant_intent=VARIANT_INTENT_CREATE_NEW,
            variant_label="Backend / AI",
            actor_label="Tag test",
        )["blueprint"]
        return primary, backend

    def test_system_tags_seed_and_existing_lanes_backfill(self):
        primary, backend = self._create_two_lanes()
        init_global_blueprint_tag_registry()

        tags = list_blueprint_tags()
        self.assertIn("Backend", {row["label"] for row in tags})
        self.assertIn("AI", {row["label"] for row in tags})

        primary_tags = get_blueprint_lane_tags(
            role_family_id=primary["role_family_id"],
            variant_id=primary["variant_id"],
        )
        self.assertEqual(
            [row["tag_id"] for row in primary_tags],
            ["generalist"],
        )
        backend_tags = get_blueprint_lane_tags(
            role_family_id=backend["role_family_id"],
            variant_id=backend["variant_id"],
        )
        self.assertEqual(
            {row["tag_id"] for row in backend_tags},
            {"backend", "ai"},
        )

    def test_lane_tags_are_mutable_metadata_not_blueprint_versions(self):
        _, backend = self._create_two_lanes()
        init_global_blueprint_tag_registry()

        updated = set_blueprint_lane_tags(
            role_family_id=backend["role_family_id"],
            variant_id=backend["variant_id"],
            tag_ids=["backend", "ai", "data"],
            actor_label="Tag editor",
        )
        self.assertEqual(
            [row["tag_id"] for row in updated],
            ["backend", "ai", "data"],
        )
        reloaded = get_blueprint_lane_tags(
            role_family_id=backend["role_family_id"],
            variant_id=backend["variant_id"],
        )
        self.assertEqual(
            [row["tag_id"] for row in reloaded],
            ["backend", "ai", "data"],
        )
        self.assertIn(
            "lane_tags_updated",
            {event["event_type"] for event in list_blueprint_tag_events()},
        )

    def test_custom_tag_can_be_created_assigned_and_renamed(self):
        _, backend = self._create_two_lanes()
        init_global_blueprint_tag_registry()

        security = create_blueprint_tag(
            label="Security",
            category="Technical domain",
            aliases="secure systems, application security",
            actor_label="Tag editor",
        )
        self.assertFalse(security["is_system"])

        set_blueprint_lane_tags(
            role_family_id=backend["role_family_id"],
            variant_id=backend["variant_id"],
            tag_ids=["backend", "ai", security["tag_id"]],
            actor_label="Tag editor",
        )
        renamed = update_blueprint_tag(
            tag_id=security["tag_id"],
            label="Platform Security",
            category="Technical domain",
            description="Security-focused platform work.",
            aliases="security, secure systems",
            is_active=True,
            actor_label="Tag editor",
        )
        self.assertEqual(renamed["label"], "Platform Security")

        labels = [
            row["label"]
            for row in get_blueprint_lane_tags(
                role_family_id=backend["role_family_id"],
                variant_id=backend["variant_id"],
            )
        ]
        self.assertIn("Platform Security", labels)

        with self.assertRaisesRegex(ValueError, "Remove this tag"):
            update_blueprint_tag(
                tag_id=security["tag_id"],
                label="Platform Security",
                category="Technical domain",
                description="",
                aliases="security",
                is_active=False,
                actor_label="Tag editor",
            )


if __name__ == "__main__":
    unittest.main()
