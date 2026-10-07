from __future__ import annotations

import unittest

from taxonomy_discovery.broad_mining_review_assist import (
    TAXONOMY_COVERAGE_VERSION,
    build_broad_mining_review_suggestion,
    find_exact_capability_taxonomy_coverage,
)


def _candidate(
    name: str,
    *,
    sources: int = 2,
    primary: int = 0,
    secondary: int = 1,
    unclassified: int = 1,
) -> dict:
    return {
        "candidate_id":
            "tqdmincand_taxonomy_test",
        "canonical_name": name,
        "status": "possible_new_technology",
        "entity_type": "programming language",
        "supporting_source_urls": [
            f"https://example{i}.com"
            for i in range(sources)
        ],
        "source_authority": {
            "counts": {
                "primary_official": primary,
                "first_party_other_technology":
                    0,
                "secondary": secondary,
                "unclassified": unclassified,
            }
        },
    }


class BroadMiningTaxonomyAwareReviewTests(
    unittest.TestCase
):
    def test_cpp_exactly_matches_existing_capability(
        self,
    ) -> None:
        coverage = (
            find_exact_capability_taxonomy_coverage(
                "C++"
            )
        )
        self.assertEqual(
            coverage["coverage_version"],
            TAXONOMY_COVERAGE_VERSION,
        )
        self.assertTrue(
            coverage["matched"]
        )
        self.assertIn(
            "language.modern_cpp",
            coverage["capability_ids"],
        )

    def test_cpp_is_high_confidence_registry_gap(
        self,
    ) -> None:
        suggestion = (
            build_broad_mining_review_suggestion(
                _candidate("C++")
            )
        )
        self.assertEqual(
            suggestion["suggested_decision"],
            "research_further",
        )
        self.assertEqual(
            suggestion["confidence"],
            "high",
        )
        self.assertEqual(
            suggestion["reason_code"],
            "exact_capability_taxonomy_coverage",
        )
        self.assertTrue(
            suggestion["signals"][
                "taxonomy_coverage"
            ]["matched"]
        )

    def test_taxonomy_coverage_does_not_rewrite_registry_status(
        self,
    ) -> None:
        suggestion = (
            build_broad_mining_review_suggestion(
                _candidate("C++")
            )
        )
        self.assertEqual(
            suggestion["signals"][
                "candidate_status"
            ],
            "possible_new_technology",
        )

    def test_unknown_name_still_uses_external_evidence(
        self,
    ) -> None:
        suggestion = (
            build_broad_mining_review_suggestion(
                _candidate(
                    "DefinitelyNotInTaxonomyXYZ",
                    primary=0,
                    secondary=0,
                    unclassified=2,
                )
            )
        )
        self.assertFalse(
            suggestion["signals"][
                "taxonomy_coverage"
            ]["matched"]
        )
        self.assertEqual(
            suggestion["suggested_decision"],
            "defer",
        )

    def test_taxonomy_matching_is_exact_only(
        self,
    ) -> None:
        coverage = (
            find_exact_capability_taxonomy_coverage(
                "C++ framework"
            )
        )
        self.assertFalse(
            coverage["matched"]
        )


if __name__ == "__main__":
    unittest.main()
