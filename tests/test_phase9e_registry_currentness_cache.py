from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.phase9e_blueprint_selection_ui import (
    _tailoring_base_resolution_identity,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE9E_UI = ROOT / "tailoring" / "phase9e_blueprint_selection_ui.py"
APP = ROOT / "app.py"


class Phase9ERegistryCurrentnessCacheTests(unittest.TestCase):
    def test_scoring_identity_is_not_changed(self):
        self.assertEqual(
            SCORING_VERSION,
            "stable-evidence-v1.10-phase6d16",
        )

    def test_registry_version_changes_resolution_identity(self):
        with patch(
            "tailoring.phase9e_blueprint_selection_ui.get_default_taxonomy",
            return_value=SimpleNamespace(version="taxonomy-v1"),
        ), patch(
            "tailoring.phase9e_blueprint_selection_ui.get_default_registry",
            return_value=SimpleNamespace(version="registry-v1.1"),
        ):
            before = _tailoring_base_resolution_identity()

        with patch(
            "tailoring.phase9e_blueprint_selection_ui.get_default_taxonomy",
            return_value=SimpleNamespace(version="taxonomy-v1"),
        ), patch(
            "tailoring.phase9e_blueprint_selection_ui.get_default_registry",
            return_value=SimpleNamespace(version="registry-v1.2"),
        ):
            after = _tailoring_base_resolution_identity()

        self.assertNotEqual(before, after)
        self.assertEqual(before["technology_registry_version"], "registry-v1.1")
        self.assertEqual(after["technology_registry_version"], "registry-v1.2")
        self.assertEqual(before["scoring_version"], after["scoring_version"])

    def test_cached_recommendation_receives_resolution_identity(self):
        source = PHASE9E_UI.read_text(encoding="utf-8")
        self.assertIn("resolution_identity: dict[str, str],", source)
        self.assertIn(
            "resolution_identity = _tailoring_base_resolution_identity()",
            source,
        )
        self.assertIn(
            "base_resume_starting_snapshot,\n            resolution_identity,",
            source,
        )

    def test_tailoring_base_displays_registry_provenance(self):
        source = PHASE9E_UI.read_text(encoding="utf-8")
        self.assertIn("Resolver context · ", source)
        self.assertIn("technology_registry_version", source)

    def test_application_analysis_displays_currentness(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn("Deterministic resolver context · ", source)
        self.assertIn('"stable_analysis_currentness"', source)
        self.assertIn("Currentness · ", source)


if __name__ == "__main__":
    unittest.main()
