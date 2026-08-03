from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import tailoring_version_manager as base
from database.blueprint_candidate_manager import (
    archive_blueprint_candidate,
    get_blueprint_candidate,
    list_blueprint_candidates,
    save_blueprint_candidate,
)


def snapshot(
    *,
    application_id: int,
    fingerprint: str,
    name: str,
):
    return {
        "candidate_fingerprint": fingerprint,
        "source_application_id": application_id,
        "source_generation_id": f"generation-{application_id}",
        "role_family": "AI Engineering",
        "candidate_name": name,
        "status": "candidate",
        "projects": {},
        "skills": {},
    }


class BlueprintCandidateManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = base.DB_PATH
        base.DB_PATH = Path(self.temp.name) / "applications.db"

    def tearDown(self):
        base.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_exact_candidate_is_reused_and_registry_is_global(self):
        first = save_blueprint_candidate(
            snapshot(
                application_id=1,
                fingerprint="fingerprint-a",
                name="Candidate A",
            )
        )
        second = save_blueprint_candidate(
            snapshot(
                application_id=1,
                fingerprint="fingerprint-a",
                name="Candidate A",
            )
        )
        save_blueprint_candidate(
            snapshot(
                application_id=2,
                fingerprint="fingerprint-b",
                name="Candidate B",
            )
        )

        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(second["cache_status"], "hit")
        self.assertEqual(
            first["candidate_id"],
            second["candidate_id"],
        )
        self.assertEqual(len(list_blueprint_candidates()), 2)

    def test_archive_retains_snapshot_but_hides_by_default(self):
        saved = save_blueprint_candidate(
            snapshot(
                application_id=3,
                fingerprint="fingerprint-c",
                name="Candidate C",
            )
        )
        self.assertTrue(
            archive_blueprint_candidate(saved["candidate_id"])
        )
        self.assertEqual(list_blueprint_candidates(), [])
        archived = get_blueprint_candidate(saved["candidate_id"])
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(
            len(
                list_blueprint_candidates(
                    include_archived=True
                )
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
