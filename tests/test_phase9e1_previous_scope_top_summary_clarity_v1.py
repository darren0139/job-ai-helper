from __future__ import annotations
import unittest
from pathlib import Path
from tailoring.phase9e1_workflow_ui import build_application_workflow_overview

ROOT=Path(__file__).resolve().parents[1]

def decision():
    return {
        "decision_id":"current",
        "decision_fingerprint":"current-fingerprint",
        "scope_activation_status":"active",
        "current_scope_status":"current",
        "recommended_tailoring":"full_regeneration",
        "selection":{"selected_source":"original_resume"},
        "starting_snapshot":{"source_fidelity":"persisted_profile_only"},
        "semantic_identity":{"role_family_classification":{
            "role_family_label":"Game Operations, Configuration & QA",
            "confidence":"high",
        }},
    }

class PreviousScopeTopSummaryClarityTests(unittest.TestCase):
    def test_previous_scope_summary(self):
        o=build_application_workflow_overview(
            application_id=95,
            application_record={"job_title":"Associate, Configuration & QA","company":"Garena"},
            baseline_report={},
            exact_jd={"source_version_id":"jdv-95"},
            current_decision=decision(),
            current_result=None,
            legacy_approved_generation={
                "generation_id":"6967cd3d",
                "status":"approved",
                "phase9e_decision_fingerprint":"old-fingerprint",
                "fit_result":{"page_count":1},
            },
            legacy_verification={"verification_id":"phase8-old"},
        )
        self.assertTrue(o["previous_scope_approved"])
        self.assertEqual(o["current_result"],"Approved · 1 page · Previous Tailoring Base")
        self.assertEqual(o["phase9e_status"],"Active · replacement not started")
        self.assertIn("Start a new résumé from the current Tailoring Base",o["next_action"])
        self.assertNotIn("advance the Blueprint Lifecycle",o["next_action"])

    def test_current_scope_stays_normal(self):
        o=build_application_workflow_overview(
            application_id=92,application_record={},baseline_report={},
            exact_jd={"source_version_id":"jdv-92"},current_decision=decision(),
            current_result=None,
            legacy_approved_generation={
                "generation_id":"current","status":"approved",
                "phase9e_decision_fingerprint":"current-fingerprint",
                "fit_result":{"page_count":1},
            },
            legacy_verification={"verification_id":"phase8-current"},
        )
        self.assertFalse(o["previous_scope_approved"])
        self.assertIn("Phase 8 verified",o["current_result"])
        self.assertEqual(o["phase9e_status"],"Active")

    def test_top_result_copy(self):
        t=(ROOT/"tailoring/phase9e1_workflow_ui.py").read_text(encoding="utf-8")
        self.assertIn("This is still the approved application result, but it belongs to a previous Tailoring Base.",t)
        self.assertIn('"Previously verified"',t)
        self.assertIn("Current-scope tailoring and fitting stay blocked until you ",t)

if __name__=="__main__":
    unittest.main()
