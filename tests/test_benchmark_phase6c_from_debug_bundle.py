from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts import benchmark_phase6c_from_debug_bundle as benchmark


def _settings() -> dict[str, object]:
    return {
        "max_projects": 11,
        "fit_effective_max_bullets": 6,
        "spacing_mode": "paragraph_spacing",
        "project_spacing_pt": 10,
        "after_projects_spacing_pt": 10,
        "blank_lines_between_projects": 1,
        "blank_lines_after_projects": 1,
        "add_spacing_before_first_project": False,
        "use_compact_before_delete": False,
        "prefer_balanced_bullets": False,
        "allow_skills_compaction": False,
        "lock_projects": False,
        "lock_skills": False,
        "minimum_total_skills": 8,
        "page_density_mode": "balanced",
        "allow_margin_compaction": False,
    }


def _bundle(source_sha256: str) -> dict[str, object]:
    return {
        "tailored_projects_result": {
            "recommended_projects": [
                {
                    "project_id": "project-a",
                    "draft_bullets": ["Kept exact project bullet."],
                    "bullet_evidence_priorities": [
                        {
                            "bullet_index": 0,
                            "bullet_text": "Kept exact project bullet.",
                            "supported_requirement_ids": ["req-a"],
                        }
                    ],
                }
            ]
        },
        "tailored_skills_result": {
            "skill_lines": [{"category": "Tools", "items": ["Python"]}]
        },
        "fitting_settings": _settings(),
        "source_docx_sha256": source_sha256,
        "source_docx_byte_size": len(b"original-source"),
    }


class BenchmarkPhase6CFromDebugBundleTests(unittest.TestCase):
    def test_fitter_authored_snapshot_is_preferred_and_replayable(self) -> None:
        bundle = _bundle("a" * 64)
        bundle["one_page_fitting_result"] = {
            "fitting_input_snapshot": {
                "snapshot_version": "phase6c-fitting-input-snapshot-v2",
                "fitting_search_algorithm_version": (
                    "phase6c-bounded-coarse-exact-fitting-v1"
                ),
                "source_artifact": {
                    "artifact_type": "docx",
                    "sha256": "b" * 64,
                    "byte_size": len(b"original-source"),
                },
                "caller_input": {
                    "projects": {
                        "recommended_projects": [{"title": "Snapshot project"}]
                    },
                    "skills": {"skill_lines": []},
                },
                "fitter_invocation": {
                    **{
                        key: value
                        for key, value in _settings().items()
                        if key != "fit_effective_max_bullets"
                    },
                    "max_bullets_per_project": 6,
                    "project_header_layout": "auto",
                    "project_metadata_style": "pipes",
                },
            }
        }

        extracted = benchmark.extract_benchmark_input(bundle)

        self.assertEqual(
            extracted.projects["recommended_projects"][0]["title"],
            "Snapshot project",
        )
        self.assertEqual(extracted.source_docx_sha256, "b" * 64)
        self.assertEqual(
            extracted.fields_used["fit_settings"],
            "one_page_fitting_result.fitting_input_snapshot.fitter_invocation",
        )

    def test_extract_uses_explicit_bundle_fields_without_defaulting(self) -> None:
        bundle = _bundle("a" * 64)

        extracted = benchmark.extract_benchmark_input(bundle)

        self.assertEqual(
            extracted.fit_settings["max_bullets_per_project"], 6
        )
        self.assertEqual(
            extracted.fields_used,
            {
                "projects": "tailored_projects_result",
                "skills": "tailored_skills_result",
                "fit_settings": "fitting_settings",
                "source_docx_sha256": "source_docx_sha256",
                "source_docx_byte_size": "source_docx_byte_size",
            },
        )
        extracted.projects["recommended_projects"][0]["draft_bullets"].append(
            "mutated copy"
        )
        self.assertEqual(
            bundle["tailored_projects_result"]["recommended_projects"][0][
                "draft_bullets"
            ],
            ["Kept exact project bullet."],
        )

    def test_missing_settings_and_source_metadata_refuse_to_run(self) -> None:
        bundle = _bundle("a" * 64)
        bundle.pop("fitting_settings")
        bundle.pop("source_docx_sha256")

        with self.assertRaisesRegex(
            benchmark.BenchmarkInputError,
            r"recorded fitting settings[\s\S]*source DOCX SHA-256 metadata",
        ):
            benchmark.extract_benchmark_input(bundle)

    def test_source_hash_mismatch_refuses_before_fitter_is_called(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "original.docx"
            source.write_bytes(b"original-source")
            extracted = benchmark.extract_benchmark_input(_bundle("b" * 64))
            fitter_calls: list[dict[str, object]] = []

            def unexpected_fitter(**kwargs: object) -> dict[str, object]:
                fitter_calls.append(dict(kwargs))
                return {}

            with self.assertRaisesRegex(
                benchmark.BenchmarkInputError,
                "does not match",
            ):
                benchmark.run_fitter_benchmark(
                    extracted, source, fitter=unexpected_fitter
                )
            self.assertEqual(fitter_calls, [])

    def test_runner_uses_none_application_id_and_restores_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "original.docx"
            source.write_bytes(b"original-source")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            raw_bundle = _bundle(source_hash)
            extracted = benchmark.extract_benchmark_input(raw_bundle)
            original_projects = deepcopy(extracted.projects)
            original_skills = deepcopy(extracted.skills)
            calls: list[dict[str, object]] = []

            def fake_fitter(**kwargs: object) -> dict[str, object]:
                calls.append(dict(kwargs))
                kwargs["tailored_projects"]["recommended_projects"][0][
                    "draft_bullets"
                ].clear()
                return {
                    "page_count": 1,
                    "fit_one_page": True,
                    "fit_status": "verified_one_page",
                    "tailored_projects_used": kwargs["tailored_projects"],
                    "tailored_skills_used": kwargs["tailored_skills"],
                }

            result = benchmark.run_fitter_benchmark(
                extracted, source, fitter=fake_fitter
            )

        self.assertEqual(result["page_count"], 1)
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0]["application_id"])
        self.assertIsNone(calls[0]["generation_id"])
        self.assertEqual(calls[0]["max_bullets_per_project"], 6)
        self.assertEqual(extracted.projects, original_projects)
        self.assertEqual(extracted.skills, original_skills)

    def test_summary_reports_required_performance_fields_and_bullet_text(self) -> None:
        extracted = benchmark.extract_benchmark_input(_bundle("a" * 64))
        result = {
            "attempts": [{"attempt_type": "initial", "page_count": 3}],
            "page_count": 1,
            "page_fill_ratio": 0.958,
            "fit_one_page": True,
            "fit_status": "verified_one_page",
            "tailored_projects_used": extracted.projects,
            "tailored_skills_used": extracted.skills,
            "fitting_elapsed_seconds": 1.0,
            "candidate_generation_elapsed_seconds": 0.1,
            "render_elapsed_seconds": 0.9,
            "libreoffice_elapsed_seconds": 0.8,
            "reduction_candidates_rendered": 18,
            "candidate_states_rendered": 19,
            "libreoffice_process_count": 4,
            "render_cache_hits": 2,
            "render_cache_misses": 19,
            "coarse_render_count": 5,
            "exact_render_count": 4,
            "local_refinement_render_count": 3,
            "restoration_candidates_rendered": 2,
            "render_budget_used": 19,
            "render_budget": 96,
        }

        summary = benchmark.build_summary(extracted, result)

        self.assertIn("initial pages: 3", summary)
        self.assertIn("cache hits/misses: 2/19", summary)
        self.assertIn("project=project-a", summary)
        self.assertIn("text=Kept exact project bullet.", summary)


if __name__ == "__main__":
    unittest.main()
