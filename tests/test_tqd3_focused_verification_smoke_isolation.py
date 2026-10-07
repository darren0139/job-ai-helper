from __future__ import annotations

import unittest
from unittest.mock import patch

from taxonomy_discovery.focused_verification import (
    interpret_focused_verification,
)
from taxonomy_discovery.focused_verification_targets import (
    build_focused_verification_target,
)
from taxonomy_discovery.technology_registry import TechnologyRegistry


class TQD3FocusedVerificationSmokeIsolationTests(unittest.TestCase):
    def _cpp_result(self) -> dict:
        target = build_focused_verification_target(
            {
                "bucket": "confirmed",
                "candidate_id": "cpp-smoke-test",
                "canonical_name": "C++",
                "taxonomy_capabilities": ["language.modern_cpp"],
            }
        )
        return {
            "provider_request_id": "persisted-cpp-smoke-test",
            "target_id": target["target_id"],
            "candidate_id": target["candidate_id"],
            "target": target,
            "raw_provider_response": {
                "results": [
                    {
                        "title": "ISO C++",
                        "url": "https://www.iso.org/standard/68564.html",
                        "content": (
                            "C++ is a general purpose programming language."
                        ),
                    }
                ]
            },
        }

    def test_isolated_unpublished_registry_keeps_relationship_contract(self):
        unpublished = TechnologyRegistry(
            version="technology-registry-test-unpublished",
            entries=(),
        )
        with patch(
            "taxonomy_discovery.focused_verification.get_default_registry",
            return_value=unpublished,
        ):
            result = interpret_focused_verification(self._cpp_result())

        self.assertEqual(
            result["outcome"],
            "verified_registry_relationship",
        )
        self.assertEqual(
            result["relationship_evidence"]["basis"],
            "exact_internal_taxonomy",
        )

    def test_published_cpp_registry_correctly_returns_no_change(self):
        published = TechnologyRegistry(
            version="technology-registry-test-published",
            entries=(
                {
                    "technology_id": "focused.cpp.test",
                    "label": "C++",
                    "aliases": [
                        "C++",
                        "C++ programming language",
                    ],
                    "kind": "language",
                    "capability_relationships": [
                        {
                            "relationship_type": "maps_to_capability",
                            "status": "approved",
                            "capability_id": "language.modern_cpp",
                        }
                    ],
                },
            ),
        )
        with patch(
            "taxonomy_discovery.focused_verification.get_default_registry",
            return_value=published,
        ):
            result = interpret_focused_verification(self._cpp_result())

        self.assertEqual(result["outcome"], "no_change")
        self.assertEqual(
            result["existing_registry_knowledge"]["status"],
            "resolved",
        )
        self.assertIsNone(result["proposed_capability_id"])


if __name__ == "__main__":
    unittest.main()
