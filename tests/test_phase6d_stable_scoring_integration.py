from __future__ import annotations

import unittest
from unittest.mock import patch

from analysis_stability import stable_evidence_scoring as scoring
from tailoring.phase6d_stable_scoring_adapter import (
    cap_requirement_with_taxonomy,
)


class Phase6DStableScoringIntegrationTests(unittest.TestCase):
    def test_build_stable_analysis_invokes_taxonomy_and_emits_version(self):
        requirement = (
            "Ability to effectively collaborate with cross-functional teams"
        )
        evidence = "Collaborated with a team in a SCRUM environment."

        with patch.object(
            scoring,
            "apply_taxonomy_caps_to_requirements",
            wraps=scoring.apply_taxonomy_caps_to_requirements,
        ) as taxonomy_caps:
            result = scoring.build_stable_analysis(
                jd_profile={
                    "required_skills": [],
                    "responsibilities": [],
                    "soft_skills": [requirement],
                    "preferred_skills": [],
                    "deal_breakers": [],
                    "tools_technologies": [],
                },
                keyword_match={
                    "present": [
                        {
                            "keyword": "Cross-functional teams",
                            "match_type": "partial",
                            "evidence_type": "transferable",
                            "found_in": "experience",
                            "matched_resume_term": evidence,
                            "match_reason": (
                                "Team collaboration is shown, but functional "
                                "diversity is not identified."
                            ),
                        }
                    ],
                    "missing": [],
                },
                raw_jd_text=requirement,
                raw_resume_text=evidence,
            )

        taxonomy_caps.assert_called_once()
        self.assertEqual(
            result["scoring_version"],
            "stable-evidence-v1.2-phase6d",
        )
        self.assertEqual(
            result["capability_taxonomy_version"],
            "phase6d-capability-taxonomy-v1",
        )
        row = result["canonical_requirements"][0]
        self.assertEqual(
            row.get("capability_id"),
            "collaboration.cross_functional",
        )
        self.assertEqual(row["match_label"], "weak")
        self.assertIn(
            row["capability_taxonomy_cap_status"],
            {"applied", "not_needed"},
        )

    def test_adapter_caps_label_value_and_evidence_strength(self):
        requirement = {
            "text": "Ability to collaborate with cross-functional teams",
            "atomic_focus": (
                "Ability to collaborate with cross-functional teams"
            ),
            "is_atomic": True,
            "match_label": "direct",
            "match_value": 1.0,
            "evidence_strength": 5,
            "evidence": [
                {
                    "text": "Collaborated with a team in SCRUM."
                }
            ],
        }
        result = cap_requirement_with_taxonomy(requirement)
        self.assertEqual(result["match_label"], "weak")
        self.assertEqual(result["match_value"], 0.20)
        self.assertEqual(result["evidence_strength"], 2)
        self.assertEqual(
            result["capability_taxonomy_cap_status"],
            "applied",
        )

    def test_unsplit_single_capability_requirement_is_still_capped(self):
        requirement = {
            "text": (
                "Ability to collaborate with cross-functional teams"
            ),
            "atomic_focus": (
                "Ability to collaborate with cross-functional teams"
            ),
            # False here means this row was not created by clause splitting;
            # it does not mean the requirement is semantically compound.
            "is_atomic": False,
            "match_label": "transferable",
            "match_value": 0.55,
            "evidence_strength": 3,
            "evidence": [
                {
                    "text": "Collaborated with a team in SCRUM."
                }
            ],
        }
        result = cap_requirement_with_taxonomy(requirement)
        self.assertEqual(result["match_label"], "weak")
        self.assertEqual(result["match_value"], 0.20)
        self.assertEqual(result["evidence_strength"], 2)
        self.assertEqual(
            result["capability_taxonomy_cap_status"],
            "applied",
        )


if __name__ == "__main__":
    unittest.main()
