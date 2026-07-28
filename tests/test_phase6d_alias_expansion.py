from __future__ import annotations

import unittest

from tailoring.capability_taxonomy import classify_requirement


class Phase6DAliasExpansionTests(unittest.TestCase):
    def test_outage_restoration_maps_to_live_operations(self):
        capability_id = classify_requirement(
            {
                "text": (
                    "Keep player-facing services healthy after release and "
                    "restore affected systems when outages disrupt users"
                )
            }
        )
        self.assertEqual(capability_id, "operations.live")

    def test_user_scoped_policy_maps_to_database_access_control(self):
        capability_id = classify_requirement(
            {
                "text": (
                    "Protect database records through user-scoped access "
                    "policies, role checks, and restricted data access"
                )
            }
        )
        self.assertEqual(capability_id, "database.access_control")

    def test_clustered_container_workloads_map_to_kubernetes(self):
        capability_id = classify_requirement(
            {
                "text": (
                    "Orchestrate container workloads across clustered "
                    "environments using deployment manifests and ingress rules"
                )
            }
        )
        self.assertEqual(capability_id, "devops.kubernetes")

    def test_defect_reproduction_maps_to_qa_testing(self):
        capability_id = classify_requirement(
            {
                "text": (
                    "Investigate software defects, reproduce failures, "
                    "and verify fixes before release"
                )
            }
        )
        self.assertEqual(capability_id, "quality.qa_testing")

    def test_containerisation_alone_does_not_map_to_kubernetes(self):
        capability_id = classify_requirement(
            {"text": "Containerise the application with Docker Compose"}
        )
        self.assertNotEqual(capability_id, "devops.kubernetes")


if __name__ == "__main__":
    unittest.main()
