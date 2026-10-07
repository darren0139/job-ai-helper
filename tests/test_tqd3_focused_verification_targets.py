from __future__ import annotations

import unittest

from taxonomy_discovery.focused_verification_targets import (
    TARGET_REGISTRY_RELATIONSHIP,
    TARGET_TECHNOLOGY_IDENTITY,
    build_focused_verification_target,
    build_focused_verification_targets,
)


def _item(
    *,
    candidate_id: str,
    name: str,
    bucket: str = "confirmed",
    capabilities: list[str] | None = None,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "canonical_name": name,
        "candidate_status":
            "possible_new_technology",
        "bucket": bucket,
        "taxonomy_capabilities":
            capabilities or [],
        "supporting_sources": 2,
        "current_review":
            "research_further",
        "friendly_reason":
            "Selected for verification.",
    }


class FocusedVerificationTargetTests(
    unittest.TestCase
):
    def test_known_capability_routes_to_registry_relationship(
        self,
    ) -> None:
        target = (
            build_focused_verification_target(
                _item(
                    candidate_id="cpp",
                    name="C++",
                    capabilities=[
                        "language.modern_cpp"
                    ],
                )
            )
        )
        self.assertEqual(
            target["route"],
            TARGET_REGISTRY_RELATIONSHIP,
        )
        self.assertEqual(
            target[
                "taxonomy_capability_ids"
            ],
            ["language.modern_cpp"],
        )

    def test_unknown_capability_routes_to_identity(
        self,
    ) -> None:
        target = (
            build_focused_verification_target(
                _item(
                    candidate_id="python",
                    name="Python",
                )
            )
        )
        self.assertEqual(
            target["route"],
            TARGET_TECHNOLOGY_IDENTITY,
        )

    def test_only_confirmed_items_become_targets(
        self,
    ) -> None:
        report = (
            build_focused_verification_targets(
                {
                    "items": [
                        _item(
                            candidate_id="c1",
                            name="C++",
                            capabilities=[
                                "language.modern_cpp"
                            ],
                        ),
                        _item(
                            candidate_id="c2",
                            name="Django",
                            bucket=(
                                "other_discoveries"
                            ),
                        ),
                    ]
                }
            )
        )
        self.assertEqual(
            report["count"],
            1,
        )
        self.assertEqual(
            report["targets"][0][
                "canonical_name"
            ],
            "C++",
        )

    def test_target_id_is_stable(
        self,
    ) -> None:
        item = _item(
            candidate_id="stable",
            name="StableTech",
        )
        first = (
            build_focused_verification_target(
                item
            )
        )
        second = (
            build_focused_verification_target(
                item
            )
        )
        self.assertEqual(
            first["target_id"],
            second["target_id"],
        )

    def test_target_generation_is_zero_network_zero_model(
        self,
    ) -> None:
        report = (
            build_focused_verification_targets(
                {
                    "items": [
                        _item(
                            candidate_id="c1",
                            name="C++",
                            capabilities=[
                                "language.modern_cpp"
                            ],
                        )
                    ]
                }
            )
        )
        self.assertEqual(
            report["governance"][
                "network_calls"
            ],
            0,
        )
        self.assertEqual(
            report["governance"][
                "model_calls"
            ],
            0,
        )
        self.assertFalse(
            report["governance"][
                "automatic_research"
            ]
        )
        self.assertFalse(
            report["governance"][
                "scoring_influence"
            ]
        )


if __name__ == "__main__":
    unittest.main()
