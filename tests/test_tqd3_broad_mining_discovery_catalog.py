from __future__ import annotations

import unittest

from taxonomy_discovery.broad_mining_discovery_catalog import (
    CATALOG_OTHER_DISCOVERY,
    CATALOG_READY_TO_VERIFY,
    CATALOG_SUGGESTED,
    build_discovery_catalog,
    find_discovery_exact,
)


class BroadMiningDiscoveryCatalogTests(
    unittest.TestCase
):
    def _summary(self) -> dict:
        return {
            "items": [
                {
                    "candidate_id": "c-python",
                    "canonical_name": "Python",
                    "bucket": "needs_verification",
                    "friendly_reason":
                        "Evidence incomplete.",
                    "taxonomy_capabilities": [],
                    "supporting_sources": 3,
                    "current_review": "unreviewed",
                },
                {
                    "candidate_id": "c-django",
                    "canonical_name": "Django",
                    "bucket": "other_discoveries",
                    "friendly_reason":
                        "Not prioritized yet.",
                    "taxonomy_capabilities": [],
                    "supporting_sources": 1,
                    "current_review": "unreviewed",
                },
                {
                    "candidate_id": "c-cpp",
                    "canonical_name": "C++",
                    "bucket": "confirmed",
                    "friendly_reason":
                        "Known capability, registry gap.",
                    "taxonomy_capabilities": [
                        "language.modern_cpp"
                    ],
                    "supporting_sources": 3,
                    "current_review":
                        "research_further",
                },
            ]
        }

    def test_all_discoveries_are_retained(
        self,
    ) -> None:
        catalog = build_discovery_catalog(
            self._summary()
        )
        self.assertEqual(
            catalog["count"],
            3,
        )
        statuses = {
            row["canonical_name"]:
                row["catalog_status"]
            for row in catalog["items"]
        }
        self.assertEqual(
            statuses["Django"],
            CATALOG_OTHER_DISCOVERY,
        )
        self.assertEqual(
            statuses["Python"],
            CATALOG_SUGGESTED,
        )
        self.assertEqual(
            statuses["C++"],
            CATALOG_READY_TO_VERIFY,
        )

    def test_other_discovery_is_exactly_findable(
        self,
    ) -> None:
        catalog = build_discovery_catalog(
            self._summary()
        )
        hits = find_discovery_exact(
            "django",
            catalog,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(
            hits[0]["canonical_name"],
            "Django",
        )

    def test_lookup_is_exact_not_fuzzy(
        self,
    ) -> None:
        catalog = build_discovery_catalog(
            self._summary()
        )
        self.assertEqual(
            find_discovery_exact(
                "Django framework",
                catalog,
            ),
            [],
        )

    def test_catalog_never_implies_scoring(
        self,
    ) -> None:
        catalog = build_discovery_catalog(
            self._summary()
        )
        self.assertTrue(
            catalog["governance"][
                "recognition_only"
            ]
        )
        self.assertFalse(
            catalog["governance"][
                "scoring_influence"
            ]
        )
        self.assertFalse(
            catalog["governance"][
                "automatic_verification"
            ]
        )


if __name__ == "__main__":
    unittest.main()
