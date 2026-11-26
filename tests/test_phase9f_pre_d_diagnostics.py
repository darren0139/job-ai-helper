from __future__ import annotations
from copy import deepcopy
import json
import unittest
from unittest.mock import patch, Mock
from tailoring.phase9f_pre_d_diagnostics import build_pre_d_mismatch_diagnostics
from tailoring import phase9f_application_confirmation_ui as ui


def fixture():
    a = {"raw_text": "JD", "raw_jd_sha256": "raw", "canonical_requirement_fingerprint": "req",
         "structured_profile_fingerprint": "profile-a", "source_version_id": "v1",
         "snapshot_fingerprint": "snapshot-a", "source_type": "pasted", "library_jd_id": 0,
         "job_title": "Engineer", "company": "NCS", "location": "Singapore, sg",
         "jd_profile": {"job_title": "Engineer", "location": "Singapore, sg", "required_skills": ["Python"]},
         "canonical_requirement_ids": ["r1"], "source_url": "private-url",
         "extraction_provenance": {"model_calls": ["private-ledger"]}}
    e = {"library_jd_id": 42, "source_version_id": "v1", "raw_text": "JD",
         "jd_profile": {"job_title": "Engineer", "location": "Singapore", "required_skills": ["Python"]}}
    p = deepcopy(a)
    p.update(library_jd_id=42, jd_profile=deepcopy(e["jd_profile"]), location="Singapore",
             structured_profile_fingerprint="profile-p")
    return a, e, p


class PreDDiagnosticsTests(unittest.TestCase):
    def test_report_identifies_saved_profile_difference(self):
        a,e,p = fixture()
        before = deepcopy((a,e,p))
        report = build_pre_d_mismatch_diagnostics(a,e,p,{"created_new_version": False})
        self.assertEqual(report["failed_guard_fields"], ["jd_profile"])
        self.assertTrue(report["library"]["existing_version_reused"])
        self.assertEqual(report["profile_differences"]["analyzed_vs_stored"]["location"]["left"], "Singapore, sg")
        self.assertEqual(report["profile_differences"]["stored_vs_rebuilt"], {})
        self.assertEqual((a,e,p), before)
        self.assertNotIn("private-ledger", json.dumps(report))
        self.assertNotIn("private-url", json.dumps(report))

    def test_distinguishes_reconstruction_and_requirement_difference(self):
        a,e,p = fixture()
        e["jd_profile"] = deepcopy(a["jd_profile"])
        p["canonical_requirement_fingerprint"] = "different"
        p["canonical_requirement_ids"] = ["r2"]
        report = build_pre_d_mismatch_diagnostics(a,e,p,{"created_new_version": True})
        self.assertEqual(report["profile_differences"]["analyzed_vs_stored"], {})
        self.assertIn("location", report["profile_differences"]["stored_vs_rebuilt"])
        self.assertEqual(report["failed_guard_fields"], ["canonical_requirement_fingerprint", "jd_profile"])
        self.assertEqual(report["requirement_ids"]["only_rebuilt"], ["r2"])
        self.assertFalse(report["library"]["existing_version_reused"])

    def test_original_guard_blocks_and_attaches_report(self):
        a,e,p = fixture()
        save = Mock(return_value={"job_description_id": 42, "source_version_id": "v1"})
        index = Mock()
        with patch.object(ui,"get_exact_job_description_version",return_value=e), patch.object(ui,"build_saved_exact_jd_snapshot",return_value=p):
            with self.assertRaises(ui.Phase9FDConfirmationError) as caught:
                ui.prepare_persisted_exact_jd_for_confirmation(a,save_fn=save,index_fn=index)
        self.assertEqual(caught.exception.code,"pre_d_exact_jd_mismatch")
        self.assertEqual(caught.exception.pre_d_diagnostics["failed_guard_fields"],["jd_profile"])
        save.assert_called_once()
        index.assert_not_called()

    def test_matching_snapshot_still_passes(self):
        a,e,p = fixture()
        p["jd_profile"] = deepcopy(a["jd_profile"])
        save = Mock(return_value={"job_description_id":42,"source_version_id":"v1"})
        with patch.object(ui,"get_exact_job_description_version",return_value=e), patch.object(ui,"build_saved_exact_jd_snapshot",return_value=p), patch.object(ui,"build_pre_d_mismatch_diagnostics") as diag:
            result, receipt = ui.prepare_persisted_exact_jd_for_confirmation(a,save_fn=save,index_fn=Mock())
        self.assertIs(result,p)
        self.assertTrue(receipt["exact_existing_version_reused"])
        diag.assert_not_called()

    def test_diagnostic_failure_cannot_bypass_guard(self):
        a,e,p = fixture()
        with patch.object(ui,"get_exact_job_description_version",return_value=e), patch.object(ui,"build_saved_exact_jd_snapshot",return_value=p), patch.object(ui,"build_pre_d_mismatch_diagnostics",side_effect=RuntimeError("failure")):
            with self.assertRaises(ui.Phase9FDConfirmationError) as caught:
                ui.prepare_persisted_exact_jd_for_confirmation(a,save_fn=Mock(return_value={"job_description_id":42,"source_version_id":"v1"}))
        self.assertEqual(caught.exception.code,"pre_d_exact_jd_mismatch")
        self.assertEqual(caught.exception.pre_d_diagnostics["diagnostic_error_type"],"RuntimeError")
