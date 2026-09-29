from __future__ import annotations

import unittest
from copy import deepcopy

from analysis_stability import stable_evidence_scoring as scoring
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.phase6d_stable_scoring_adapter import (
    apply_taxonomy_caps_to_requirements,
)


class CapabilitySingleRowReselectionTests(unittest.TestCase):
    def setUp(self) -> None:
        get_default_taxonomy.cache_clear()
        self.taxonomy = get_default_taxonomy()

    def tearDown(self) -> None:
        get_default_taxonomy.cache_clear()

    def _apply(
        self,
        requirement: dict,
        evidence_rows: list[dict[str, str]],
    ) -> dict:
        reselected, audit = scoring._apply_capability_single_row_reselection(
            [deepcopy(requirement)],
            evidence_index=deepcopy(evidence_rows),
            acronym_map={},
        )
        capped = apply_taxonomy_caps_to_requirements(
            reselected,
            retrieval_mode_override="off",
        )
        return {
            "row": capped[0],
            "audit": audit,
            "precap": reselected[0],
        }

    @staticmethod
    def _row(
        *,
        requirement_id: str,
        text: str,
        label: str,
        evidence_text: str,
        evidence_section: str = "skills",
    ) -> dict:
        return {
            "requirement_id": requirement_id,
            "text": text,
            "atomic_focus": text,
            "importance": "required",
            "match_label": label,
            "match_value": scoring.MATCH_VALUES[label],
            "evidence_strength": (
                5 if label == "direct"
                else 3 if label == "transferable"
                else 2 if label == "weak"
                else 0
            ),
            "evidence": (
                [
                    {
                        "evidence_id": f"ev-{requirement_id}-original",
                        "section": evidence_section,
                        "text": evidence_text,
                        "source": f"resume_profile.{evidence_section}",
                        "reason": "preliminary matcher",
                    }
                ]
                if evidence_text
                else []
            ),
        }

    @staticmethod
    def _evidence(
        evidence_id: str,
        section: str,
        text: str,
        source: str,
    ) -> dict[str, str]:
        return {
            "evidence_id": evidence_id,
            "section": section,
            "text": text,
            "source": source,
        }

    def test_taxonomy_opt_in_set_is_exact(self) -> None:
        expected = {
            "language.modern_cpp",
            "mobile.android_development",
            "graphics.opengl_vulkan",
            "systems.memory_cache_performance",
            "systems.data_oriented_programming",
            "algorithms.data_structures_algorithms",
            "integration.client_software",
            "realtime.messaging_streaming",
            "devops.containerisation",
            "devops.ci_cd",
            "devops.kubernetes",
        }
        actual = {
            item["capability_id"]
            for item in self.taxonomy.capabilities
            if item.get("allow_stronger_single_row_reselection") is True
        }
        self.assertEqual(actual, expected)

    def test_docker_reselects_one_concrete_row_but_keeps_transferable_ceiling(self) -> None:
        req = self._row(
            requirement_id="docker",
            text="Familiarity with containerization technologies (Docker, Kubernetes, etc.)",
            label="transferable",
            evidence_text="Docker",
        )
        concrete = self._evidence(
            "ev-docker-concrete",
            "experience",
            (
                "Used Python to clean datasets and containerised the "
                "data-processing workflow with Docker for consistent execution."
            ),
            "resume_profile.experience[0].bullets[2]",
        )
        result = self._apply(req, [concrete])

        self.assertEqual(result["row"]["match_label"], "transferable")
        self.assertEqual(len(result["precap"]["evidence"]), 1)
        self.assertEqual(
            result["precap"]["evidence"][0]["evidence_id"],
            "ev-docker-concrete",
        )
        self.assertEqual(len(result["audit"]), 1)
        self.assertFalse(result["audit"][0]["combined_evidence_rows"])

    def test_preliminary_none_is_never_promoted(self) -> None:
        req = self._row(
            requirement_id="docker-none",
            text="Experience with Docker",
            label="none",
            evidence_text="",
        )
        concrete = self._evidence(
            "ev-docker-concrete",
            "projects",
            "Containerised the application with Docker.",
            "resume_profile.projects[0].bullets[0]",
        )
        result = self._apply(req, [concrete])

        self.assertEqual(result["row"]["match_label"], "none")
        self.assertEqual(result["audit"], [])

    def test_non_opt_in_database_design_is_not_reselected(self) -> None:
        req = self._row(
            requirement_id="database",
            text="Experience with SQLite or PostgreSQL database design",
            label="direct",
            evidence_text="PostgreSQL",
        )
        candidate = self._evidence(
            "ev-db",
            "projects",
            "Created a database with Row-Level Security (RLS) policies for security.",
            "resume_profile.projects[0].bullets[2]",
        )
        result = self._apply(req, [candidate])

        self.assertEqual(result["row"]["match_label"], "none")
        self.assertEqual(result["audit"], [])
        self.assertEqual(result["precap"]["evidence"][0]["text"], "PostgreSQL")

    def test_dsa_astar_is_transferable_not_direct(self) -> None:
        req = self._row(
            requirement_id="dsa",
            text="Strong foundation in Data Structures/Algorithms",
            label="direct",
            evidence_text="A* Pathfinding",
            evidence_section="projects",
        )
        candidate = self._evidence(
            "ev-astar",
            "projects",
            (
                "Integrated A* pathfinding into a custom C++ engine to support "
                "efficient, dynamic navigation for enemy AI."
            ),
            "resume_profile.projects[3].bullets[0]",
        )
        result = self._apply(req, [candidate])

        self.assertEqual(result["row"]["match_label"], "transferable")
        self.assertNotEqual(result["row"]["match_label"], "direct")
        self.assertEqual(len(result["audit"]), 1)

    def test_generic_data_does_not_rescue_dsa(self) -> None:
        req = self._row(
            requirement_id="dsa-generic",
            text="Strong foundation in Data Structures/Algorithms",
            label="direct",
            evidence_text="Data",
        )
        candidate = self._evidence(
            "ev-data",
            "experience",
            "Used Python to clean datasets and prepare data for analysis.",
            "resume_profile.experience[0].bullets[0]",
        )
        result = self._apply(req, [candidate])

        self.assertEqual(result["row"]["match_label"], "none")
        self.assertEqual(result["audit"], [])

    def test_generic_engine_does_not_rescue_opengl_vulkan(self) -> None:
        req = self._row(
            requirement_id="graphics",
            text="Experience working with OpenGL and/or Vulkan",
            label="direct",
            evidence_text="custom engine",
            evidence_section="projects",
        )
        candidate = self._evidence(
            "ev-engine",
            "projects",
            "Built a custom C++ game engine and asset manager.",
            "resume_profile.projects[0].bullets[0]",
        )
        result = self._apply(req, [candidate])

        self.assertEqual(result["row"]["match_label"], "none")
        self.assertEqual(result["audit"], [])

    def test_android_requires_concrete_android_delivery_row(self) -> None:
        req = self._row(
            requirement_id="android",
            text=(
                "Experience with native mobile development for iOS and Android "
                "(React Native, Kotlin, Swift)"
            ),
            label="transferable",
            evidence_text="Kotlin",
        )
        bare = self._evidence(
            "ev-kotlin",
            "skills",
            "Kotlin",
            "resume_profile.skills.languages[0]",
        )
        concrete = self._evidence(
            "ev-android",
            "projects",
            (
                "Led frontend implementation for a GPS-based Android application "
                "using Kotlin and Jetpack Compose."
            ),
            "resume_profile.projects[2].bullets[0]",
        )
        result = self._apply(req, [bare, concrete])

        self.assertEqual(result["row"]["match_label"], "transferable")
        self.assertEqual(result["precap"]["evidence"][0]["evidence_id"], "ev-android")
        self.assertEqual(len(result["audit"]), 1)

    def test_reselection_metadata_is_exposed_on_row(self) -> None:
        req = self._row(
            requirement_id="ci",
            text="Manage and set up automated CI/CD systems",
            label="transferable",
            evidence_text="CI",
        )
        candidate = self._evidence(
            "ev-ci",
            "projects",
            (
                "Added automated unit tests and GitHub Actions CI across Ubuntu "
                "and Windows, running dependency checks and the full test suite."
            ),
            "resume_profile.projects[0].bullets[3]",
        )
        result = self._apply(req, [candidate])

        metadata = result["precap"].get("capability_evidence_reselection")
        self.assertIsInstance(metadata, dict)
        self.assertEqual(
            metadata["policy_version"],
            scoring.CAPABILITY_EVIDENCE_RESELECTION_POLICY_VERSION,
        )
        self.assertEqual(metadata["selected_evidence_id"], "ev-ci")
        self.assertFalse(metadata["combined_evidence_rows"])


if __name__ == "__main__":
    unittest.main()
