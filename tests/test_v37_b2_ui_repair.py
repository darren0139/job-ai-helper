"""B2 regression tests: same-page widget keys and truthful Phase 8 banners."""
from __future__ import annotations

from contextlib import nullcontext
import unittest
from unittest.mock import patch

from tailoring.initial_analysis_explainer_ui import render_analysis_receipt
from tailoring.initial_score_breakdown_ui import render_initial_score_math
from tailoring.phase8_verification_ui import _phase8_score_banner


class _Column:
    def metric(self, *args, **kwargs):
        pass


class _StreamlitStub:
    def __init__(self):
        self.keys = set()

    def _register(self, key):
        if key in self.keys:
            raise AssertionError("Duplicate widget key: " + str(key))
        self.keys.add(key)

    def columns(self, count):
        return [_Column() for _ in range(count)]

    def expander(self, *args, **kwargs):
        return nullcontext()

    def checkbox(self, label, *, key, **kwargs):
        self._register(key)
        return False

    def download_button(self, label, *args, key, **kwargs):
        self._register(key)

    def caption(self, *args, **kwargs):
        pass

    def markdown(self, *args, **kwargs):
        pass

    def write(self, *args, **kwargs):
        pass

    def code(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        raise AssertionError("Unexpected unavailable receipt")


class SamePageWidgetKeys(unittest.TestCase):
    def test_document_initial_and_legacy_history_have_distinct_controls(self):
        # Both views can reference the same underlying saved native score.
        native = {"deterministic_alignment_score": 93,
                  "required_core_coverage_score": 92,
                  "preferred_coverage_score": 55,
                  "evidence_strength_score": 89,
                  "input_fingerprint": "same-saved-native-fingerprint"}
        view = {"stable_analysis": native, "currentness": "Saved",
                "provenance": "SAME_NATIVE_SOURCE", "identity": {"application_id": 123},
                "requirements": [], "contribution_status": "available"}
        receipt = {"stored_scorer_score": 93, "components": [],
                   "subtotal_before_rounding": 93.0, "maximum_score": 100.0,
                   "jd_requirements": [], "pools": []}
        st = _StreamlitStub()

        def fake_components(st_obj, receipt_obj, *, key_prefix, **kwargs):
            for category in ("required_core", "preferred", "evidence_strength", "overall"):
                st_obj.download_button("CSV", b"", key=f"{key_prefix}_{category}_score_csv")
            st_obj.download_button("ZIP", b"", key=f"{key_prefix}_score_component_zip")
            return True

        def fake_table(st_obj, rows, *, key, **kwargs):
            st_obj._register(key)

        with (patch("tailoring.initial_score_breakdown_ui.initial_score_math", return_value=receipt),
              patch("tailoring.score_component_tables_ui.render_component_tables", side_effect=fake_components),
              patch("tailoring.session_table_ui_v2.render_session_table", side_effect=fake_table)):
            render_analysis_receipt(st, view, show_taxonomy=False,
                                    widget_namespace="application_initial_123")
            render_analysis_receipt(st, view, show_taxonomy=False,
                                    widget_namespace="historical_discovery_match")
        # Five score-export controls plus advanced, table and diagnostics, twice.
        self.assertEqual(len(st.keys), 16)

    def test_direct_presenter_passes_scoped_keys_to_component_export(self):
        view = {"provenance": "SAVED", "stable_analysis": {}}
        receipt = {"stored_scorer_score": 88, "components": [],
                   "subtotal_before_rounding": 88.0, "maximum_score": 100.0,
                   "jd_requirements": [], "pools": []}
        prefixes = []
        st = _StreamlitStub()
        with (patch("tailoring.initial_score_breakdown_ui.initial_score_math", return_value=receipt),
              patch("tailoring.score_component_tables_ui.render_component_tables",
                    side_effect=lambda *args, **kw: prefixes.append(kw["key_prefix"]))):
            render_initial_score_math(st, view, key_prefix="a")
            render_initial_score_math(st, view, key_prefix="b")
        self.assertEqual(prefixes, ["a", "b"])
        self.assertIn("a_advanced_map_v1", st.keys)
        self.assertIn("b_advanced_map_v1", st.keys)


class Phase8Banner(unittest.TestCase):
    @staticmethod
    def make(before, after, *, verdict="maintained", hard=None, valid=True):
        return {"verdict": verdict,
                "verdict_message": "The deterministic score was maintained without losing required/core evidence.",
                "comparison_valid": valid,
                "comparison": {"before_score": before, "after_score": after,
                               "score_delta": after - before,
                               "important_regressions": [] if hard is None else hard,
                               "canonical_requirement_ids_stable": True}}

    def test_decline_no_hard_regression_is_not_maintained(self):
        kind, message = _phase8_score_banner(self.make(93, 88))
        self.assertEqual(kind, "warning")
        self.assertIn("93 to 88", message)
        self.assertIn("-5", message)
        self.assertIn("Required/Core", message)
        self.assertNotIn("score was maintained", message)

    def test_tie(self):
        kind, message = _phase8_score_banner(self.make(88, 88))
        self.assertEqual(kind, "info")
        self.assertIn("maintained", message)

    def test_improved(self):
        r = self.make(88, 93, verdict="improved")
        r["verdict_message"] = "Improved without hard losses."
        self.assertEqual(_phase8_score_banner(r), ("success", "Improved without hard losses."))

    def test_hard_regression_overrides_positive_score(self):
        r = self.make(88, 93, verdict="regression_detected", hard=[{"requirement_id": "core1"}])
        kind, message = _phase8_score_banner(r)
        self.assertEqual(kind, "warning")
        self.assertIn("Required/Core", message)

    def test_required_core_unverified_does_not_claim_preservation(self):
        r = self.make(93, 88)
        del r["comparison"]["important_regressions"]
        kind, message = _phase8_score_banner(r)
        self.assertEqual(kind, "warning")
        self.assertIn("separate verification", message)

    def test_nonfinite_and_mismatched_verdict_are_warnings(self):
        r = self.make(93, 88)
        r["comparison"]["after_score"] = float("nan")
        self.assertIn("inconsistent", _phase8_score_banner(r)[1])
        r = self.make(88, 93, verdict="maintained")
        self.assertIn("disagrees", _phase8_score_banner(r)[1])

    def test_incomparable_and_inconsistent_scores(self):
        r = self.make(93, 88, valid=False)
        self.assertEqual(_phase8_score_banner(r)[0], "warning")
        self.assertIn("unavailable", _phase8_score_banner(r)[1])
        r = self.make(93, 88)
        r["comparison"]["score_delta"] = 0
        self.assertIn("inconsistent", _phase8_score_banner(r)[1])


if __name__ == "__main__":
    unittest.main()
