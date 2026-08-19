from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "tests" / (
    "phase9f_starting_source_ranking_streamlit_harness.py"
)


def _contains(elements, text: str) -> bool:
    return any(text in str(item.value) for item in elements)


def _button(app: AppTest, key: str):
    return next(item for item in app.button if item.key == key)


class Phase9FStartingSourceRankingStreamlitTests(unittest.TestCase):
    def test_transparency_panels_render_without_changing_ranking(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        result = app.session_state["phase9f_b_ranking_result"]
        fingerprint = result["ranking_fingerprint"]
        comparison_fingerprints = [
            row["comparison_result_fingerprint"]
            for row in result["ranked_candidates"]
        ]

        self.assertTrue(_contains(app.markdown, "Why this source ranked #1"))
        expander_labels = {item.label for item in app.expander}
        self.assertIn("Why #1 beat #2", expander_labels)
        self.assertIn("Compare requirement evidence", expander_labels)
        self.assertIn("How ranking works", expander_labels)
        self.assertTrue(
            _contains(
                app.info,
                "Role family never adds points to the canonical score",
            )
        )
        self.assertTrue(
            any(
                {
                    "Requirement ID",
                    "Requirement",
                    "Source",
                    "Match",
                    "Evidence strength",
                }.issubset(set(frame.value.columns))
                for frame in app.dataframe
            )
        )
        pairwise_frame = next(
            frame.value
            for frame in app.dataframe
            if "Favored" in frame.value.columns
        )
        for column in pairwise_frame.columns:
            if column not in {"Metric", "Favored"}:
                self.assertTrue(
                    all(isinstance(value, str) for value in pairwise_frame[column])
                )

        app.run()
        self.assertEqual(app.exception, [])
        rerun_result = app.session_state["phase9f_b_ranking_result"]
        self.assertEqual(rerun_result["ranking_fingerprint"], fingerprint)
        self.assertEqual(
            [
                row["comparison_result_fingerprint"]
                for row in rerun_result["ranked_candidates"]
            ],
            comparison_fingerprints,
        )

    def test_base_resume_inspection_marks_historical_provenance_not_applicable(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        result = app.session_state["phase9f_b_ranking_result"]
        base = next(
            row
            for row in result["ranked_candidates"]
            if row["source_type"] == "base_resume"
        )
        selector = next(
            item
            for item in app.selectbox
            if item.key == "phase9f_b_inspect_source"
        )
        selector.select(base["normalized_source_fingerprint"]).run()
        self.assertEqual(app.exception, [])
        self.assertTrue(
            any(
                item.label == "Historical Blueprint/source score"
                and str(item.value) == "Not applicable"
                for item in app.metric
            )
        )
        self.assertTrue(
            _contains(
                app.caption,
                "not applicable and was not fabricated",
            )
        )

    def test_transient_ranking_exact_reuse_and_stale_scope(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        self.assertEqual(app.exception, [])
        self.assertTrue(
            any(
                item.key == "phase9f_b_compare_sources"
                for item in app.button
            )
        )
        self.assertTrue(
            _contains(app.info, "zero-cost deterministic comparison")
        )

        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        self.assertTrue(
            _contains(app.success, "Recommended starting source")
        )
        self.assertEqual(
            sum(
                "Recommended tailoring:" in str(item.value)
                for item in app.markdown
            ),
            1,
        )
        self.assertTrue(
            any(item.label == "Current JD alignment" for item in app.metric)
        )
        result = app.session_state["phase9f_b_ranking_result"]
        result_fingerprint = result["ranking_fingerprint"]

        app.run()
        self.assertEqual(app.exception, [])
        recompute = _button(app, "phase9f_b_compare_sources")
        self.assertEqual(recompute.label, "Recompute comparison")
        self.assertTrue(
            _contains(app.success, "comparison is up to date")
        )
        self.assertEqual(
            app.session_state["phase9f_b_ranking_result"][
                "ranking_fingerprint"
            ],
            result_fingerprint,
        )
        self.assertTrue(
            _contains(app.caption, "Reused the exact transient Phase 9F-B result")
        )

        recompute.click().run()
        self.assertEqual(app.exception, [])
        self.assertEqual(
            app.session_state["phase9f_b_ranking_result"][
                "ranking_fingerprint"
            ],
            result_fingerprint,
        )
        self.assertTrue(
            _contains(app.caption, "Recomputed deterministically")
        )

        app.checkbox[0].check().run()
        self.assertEqual(app.exception, [])
        self.assertTrue(_contains(app.warning, "historical/stale"))
        self.assertTrue(
            any(
                item.key == "phase9f_b_compare_sources"
                for item in app.button
            )
        )

    def test_removed_blueprint_stales_b_and_hides_c_until_exact_scope_returns(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        before = app.session_state["phase9f_b_ranking_result"]
        before_fingerprint = before["ranking_fingerprint"]
        before_input = before["ranking_input_fingerprint"]
        before_order = [
            row["normalized_source_fingerprint"]
            for row in before["ranked_candidates"]
        ]
        before_metrics = [
            (
                row["deterministic_alignment_score"],
                row["required_core_coverage_score"],
                row["preferred_coverage_score"],
                row["evidence_strength_score"],
            )
            for row in before["ranked_candidates"]
        ]
        before_intensity = next(
            str(item.value)
            for item in app.markdown
            if "Recommended tailoring:" in str(item.value)
        )

        removed = next(
            item
            for item in app.checkbox
            if item.key == "phase9f_b_test_removed_blueprint"
        )
        removed.check().run()
        self.assertEqual(app.exception, [])
        self.assertTrue(_contains(app.warning, "historical/stale"))
        self.assertFalse(
            any(
                "Recommended tailoring:" in str(item.value)
                for item in app.markdown
            )
        )
        self.assertEqual(
            app.session_state["phase9f_b_ranking_result"][
                "ranking_fingerprint"
            ],
            before_fingerprint,
        )
        self.assertEqual(
            _button(app, "phase9f_b_compare_sources").label,
            "Compare starting resume sources",
        )

        removed = next(
            item
            for item in app.checkbox
            if item.key == "phase9f_b_test_removed_blueprint"
        )
        removed.uncheck().run()
        self.assertEqual(app.exception, [])
        self.assertEqual(
            _button(app, "phase9f_b_compare_sources").label,
            "Recompute comparison",
        )
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        restored = app.session_state["phase9f_b_ranking_result"]
        self.assertEqual(restored["ranking_input_fingerprint"], before_input)
        self.assertEqual(restored["ranking_fingerprint"], before_fingerprint)
        self.assertEqual(
            [
                row["normalized_source_fingerprint"]
                for row in restored["ranked_candidates"]
            ],
            before_order,
        )
        self.assertEqual(
            [
                (
                    row["deterministic_alignment_score"],
                    row["required_core_coverage_score"],
                    row["preferred_coverage_score"],
                    row["evidence_strength_score"],
                )
                for row in restored["ranked_candidates"]
            ],
            before_metrics,
        )
        restored_intensity = next(
            str(item.value)
            for item in app.markdown
            if "Recommended tailoring:" in str(item.value)
        )
        self.assertEqual(restored_intensity, before_intensity)

    def test_rendering_is_zero_cost_and_has_separate_download(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        for marker in (
            "MODEL_CALLS=0",
            "EMBEDDING_CALLS=0",
            "CHROMA_READS=0",
            "CHROMA_WRITES=0",
            "PERSISTENCE_WRITES=0",
        ):
            self.assertTrue(_contains(app.markdown, marker))
        download_labels = {
            item.label for item in app.get("download_button")
        }
        self.assertIn("Download Phase 9F-B ranking JSON", download_labels)
        self.assertIn("Download requirement comparison CSV", download_labels)
        self.assertTrue(
            _contains(
                app.caption,
                "already includes the deterministic transparency explanation",
            )
        )
        self.assertFalse(
            _contains(app.markdown, "Reuse / Minor / Full")
        )

    def test_ranked_candidate_preview_selection_and_downloads(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])

        selector = next(
            item
            for item in app.selectbox
            if item.key == "phase9f_b_inspect_source"
        )
        result = app.session_state["phase9f_b_ranking_result"]
        self.assertEqual(
            selector.value,
            result["recommended_source"]["normalized_source_fingerprint"],
        )
        self.assertTrue(
            _contains(app.markdown, "data:image/png;base64")
        )
        labels = {
            item.label for item in app.get("download_button")
        }
        self.assertIn("Download PDF", labels)
        self.assertIn("Download DOCX", labels)

        alternate = result["ranked_candidates"][-1][
            "normalized_source_fingerprint"
        ]
        selector.select(alternate).run()
        self.assertEqual(app.exception, [])
        selected_after = next(
            item
            for item in app.selectbox
            if item.key == "phase9f_b_inspect_source"
        )
        self.assertEqual(selected_after.value, alternate)
        self.assertTrue(
            _contains(app.markdown, "data:image/png;base64")
        )

    def test_blueprint_provenance_labels_debug_and_source_navigation(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        result = app.session_state["phase9f_b_ranking_result"]
        ranking_fingerprint = result["ranking_fingerprint"]
        selected = result["recommended_source"]

        self.assertTrue(
            any(
                item.label == "Historical Blueprint/source score"
                for item in app.metric
            )
        )
        self.assertTrue(
            _contains(
                app.caption,
                "historical Blueprint/source score is provenance",
            )
        )
        self.assertTrue(
            any(
                item.label == "Download Blueprint provenance/debug JSON"
                for item in app.get("download_button")
            )
        )
        self.assertTrue(
            any(
                item.label == "Open in Blueprint Library"
                for item in app.button
            )
        )

        source_button = next(
            item
            for item in app.button
            if item.label == "Open source Application Session"
        )
        source_button.click().run()
        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["current_application_id"], 94)
        self.assertEqual(
            app.session_state["_pending_navigation_page"],
            "Application Sessions",
        )
        self.assertEqual(
            app.session_state["phase9f_b_ranking_result"][
                "ranking_fingerprint"
            ],
            ranking_fingerprint,
        )
        self.assertEqual(
            app.session_state["phase9f_b_ranking_result"][
                "recommended_source"
            ]["source_id"],
            selected["source_id"],
        )

    def test_missing_source_application_is_disabled_and_not_guessed(self):
        app = AppTest.from_file(str(HARNESS), default_timeout=20).run()
        missing = next(
            item
            for item in app.checkbox
            if item.key == "phase9f_b_test_missing_source_application"
        )
        missing.check().run()
        _button(app, "phase9f_b_compare_sources").click().run()
        self.assertEqual(app.exception, [])
        self.assertTrue(
            any(
                item.label == "Source Application unavailable"
                and item.disabled
                for item in app.button
            )
        )
        self.assertTrue(
            _contains(app.warning, "No identity was guessed")
        )


if __name__ == "__main__":
    unittest.main()
