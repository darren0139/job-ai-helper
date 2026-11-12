from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from analysis_stability import reviewed_jd_exclusions
from tailoring import phase9e_blueprint_selection_ui as ui


ROOT = Path(__file__).resolve().parents[1]
PHASE9E_UI = ROOT / "tailoring" / "phase9e_blueprint_selection_ui.py"
APP = ROOT / "app.py"



class Phase9ERegistryCurrentnessCacheTests(unittest.TestCase):
    def test_scoring_identity_is_not_changed(self):
        self.assertEqual(
            SCORING_VERSION,
            "stable-evidence-v1.16-phase6d20",
        )

    def test_registry_version_changes_resolution_identity(self):
        with patch.object(ui, "get_default_registry", return_value=SimpleNamespace(version="registry-v1.1")):
            before = ui._tailoring_base_resolution_identity()

        with patch.object(ui, "get_default_registry", return_value=SimpleNamespace(version="registry-v1.2")):
            after = ui._tailoring_base_resolution_identity()

        self.assertNotEqual(before, after)
        self.assertEqual(before["technology_registry_version"], "registry-v1.1")
        self.assertEqual(after["technology_registry_version"], "registry-v1.2")
        self.assertEqual(before["scoring_version"], after["scoring_version"])

    def test_taxonomy_and_scorer_salt_cache_identity(self):
        before = ui._tailoring_base_resolution_identity()
        with patch.object(ui, "get_default_taxonomy", return_value=SimpleNamespace(version="changed")):
            self.assertNotEqual(before, ui._tailoring_base_resolution_identity())
        with patch.object(ui, "SCORING_VERSION", "changed"):
            self.assertNotEqual(before, ui._tailoring_base_resolution_identity())

    def test_cached_recommendation_receives_resolution_identity(self):
        exact_jd = {"raw_text": "Requirements\nExperience with Python."}
        scope = {"policy_identity": reviewed_jd_exclusions.MATCHING_POLICY_VERSION,
                 "effective_requirement_scope_sha256": "a" * 64}
        cached_recommendation = ui._cached_blueprint_recommendation
        cached_recommendation.clear()
        self.addCleanup(cached_recommendation.clear)

        with (
            patch.object(reviewed_jd_exclusions, "active_requirement_scope", return_value=None) as active_scope,
            patch.object(ui, "recommend_active_blueprint", side_effect=[
                {"result": "ordinary"}, {"result": "scoped"}, {"result": "changed scope"},
            ]) as recommend,
        ):
            def current_recommendation():
                identity = ui._tailoring_base_resolution_identity(exact_jd["raw_text"])
                active_scope.assert_called_with(exact_jd["raw_text"])
                return cached_recommendation(exact_jd, [], {}, None, identity)

            self.assertEqual(current_recommendation(), {"result": "ordinary"})
            self.assertEqual(current_recommendation(), {"result": "ordinary"})
            self.assertEqual(recommend.call_count, 1)

            active_scope.return_value = scope
            self.assertEqual(current_recommendation(), {"result": "scoped"})
            self.assertEqual(current_recommendation(), {"result": "scoped"})
            self.assertEqual(recommend.call_count, 2)

            active_scope.return_value = {**scope, "effective_requirement_scope_sha256": "b" * 64}
            self.assertEqual(current_recommendation(), {"result": "changed scope"})
            self.assertEqual(recommend.call_count, 3)

            active_scope.return_value = None
            self.assertEqual(current_recommendation(), {"result": "ordinary"})
            self.assertEqual(recommend.call_count, 3)

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
