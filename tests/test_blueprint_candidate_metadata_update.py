from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base
from database.blueprint_candidate_manager import (
    get_blueprint_candidate,
    list_blueprint_candidates,
    save_blueprint_candidate,
)


def snapshot(*, name: str, notes: str):
    return {
        "candidate_fingerprint": "fingerprint-a",
        "source_application_id": 94,
        "source_generation_id": "generation-94",
        "role_family": "AI & Full-Stack Software Engineering",
        "role_family_id": "ai_fullstack_software_engineering",
        "candidate_name": name,
        "notes": notes,
        "candidate_metadata": {
            "candidate_name_source": "user_edited",
            "notes_source": "user_edited",
        },
        "status": "candidate",
        "projects": {},
        "skills": {},
        "resume_profile_snapshot": {},
    }


class BlueprintCandidateMetadataUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = base.DB_PATH
        base.DB_PATH = Path(self.temp.name) / "applications.db"

    def tearDown(self):
        base.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_exact_candidate_updates_only_mutable_metadata(self):
        first = save_blueprint_candidate(
            snapshot(name="Original name", notes="Original notes")
        )
        second = save_blueprint_candidate(
            snapshot(name="Better name", notes="Corrected notes")
        )

        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(
            second["cache_status"],
            "hit_metadata_updated",
        )
        self.assertEqual(
            first["candidate_id"],
            second["candidate_id"],
        )
        self.assertEqual(len(list_blueprint_candidates()), 1)

        stored = get_blueprint_candidate(first["candidate_id"])
        self.assertEqual(stored["candidate_name"], "Better name")
        self.assertEqual(stored["notes"], "Corrected notes")
        self.assertEqual(
            stored["candidate_fingerprint"],
            "fingerprint-a",
        )

    def test_unchanged_exact_candidate_is_plain_cache_hit(self):
        first = save_blueprint_candidate(
            snapshot(name="Candidate", notes="Notes")
        )
        second = save_blueprint_candidate(
            snapshot(name="Candidate", notes="Notes")
        )
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")


if __name__ == "__main__":
    unittest.main()
