from __future__ import annotations

import io
import json
import unittest
import zipfile

from taxonomy_discovery.broad_mining_export import (
    BROAD_MINING_EXPORT_VERSION,
    build_broad_mining_candidate_summary_csv,
    build_broad_mining_debug_zip,
)


class BroadMiningExportTests(unittest.TestCase):
    def test_debug_zip_contains_expected_files(self) -> None:
        candidate_report = {
            "candidates": [
                {
                    "candidate_id": "c1",
                    "canonical_name": "ExampleTech",
                    "status": "possible_new_technology",
                    "entity_type": "platform",
                    "supporting_source_urls": [
                        "https://example.com"
                    ],
                    "source_authority": {
                        "counts": {
                            "primary_official": 1,
                            "secondary": 0,
                            "unclassified": 0,
                        }
                    },
                }
            ]
        }
        data = build_broad_mining_debug_zip(
            research_artifacts=[
                {"artifact_id": "a1"}
            ],
            raw_research=[
                {"provider_request_id": "r1"}
            ],
            candidate_report=candidate_report,
            candidate_reviews=[],
            suggestions={
                "c1": {
                    "suggested_decision":
                        "research_further",
                    "confidence": "high",
                }
            },
        )

        with zipfile.ZipFile(
            io.BytesIO(data)
        ) as archive:
            names = set(archive.namelist())
            self.assertIn(
                "candidate_report.json",
                names,
            )
            self.assertIn(
                "candidate_summary.csv",
                names,
            )
            self.assertIn(
                "raw_research.json",
                names,
            )
            manifest = json.loads(
                archive.read(
                    "export_manifest.json"
                ).decode("utf-8")
            )
            self.assertEqual(
                manifest["export_version"],
                BROAD_MINING_EXPORT_VERSION,
            )
            self.assertEqual(
                manifest["governance"][
                    "network_calls"
                ],
                0,
            )

    def test_candidate_summary_includes_review_and_suggestion(
        self,
    ) -> None:
        csv_text = (
            build_broad_mining_candidate_summary_csv(
                {
                    "candidates": [
                        {
                            "candidate_id": "c1",
                            "canonical_name":
                                "ExampleTech",
                            "status":
                                "possible_new_technology",
                            "supporting_source_urls":
                                [],
                            "source_authority": {
                                "counts": {}
                            },
                        }
                    ]
                },
                [
                    {
                        "candidate_id": "c1",
                        "decision": "defer",
                    }
                ],
                {
                    "c1": {
                        "suggested_decision":
                            "research_further",
                        "confidence": "medium",
                    }
                },
            )
        )
        self.assertIn(
            "research_further",
            csv_text,
        )
        self.assertIn("defer", csv_text)


if __name__ == "__main__":
    unittest.main()
