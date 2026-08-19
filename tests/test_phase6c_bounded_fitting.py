from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest
from unittest.mock import patch

from resume_builder.docx_projects_skills_replacer import (
    FIT_RENDER_BUDGET,
    convert_docx_batch_to_pdf_if_possible,
    generate_tailored_resume_copy_fit_one_page,
)
from resume_builder.fitting_render_optimizer import (
    PHASE6C1_OPTIMIZATION_VERSION,
    build_render_state_fingerprint,
)
from resume_builder.fitting_provenance import (
    PHASE6C_SEARCH_ALGORITHM_VERSION,
)


def _projects(*, bullet_counts: tuple[int, ...] = (50, 6, 5, 5)) -> dict:
    projects = []
    for project_index, bullet_count in enumerate(bullet_counts, start=1):
        bullets = [
            (
                f"Project {project_index} protected unique requirement evidence."
                if bullet_index == 0
                else (
                    f"Project {project_index} truthful lower-priority "
                    f"evidence bullet {bullet_index}."
                )
            )
            for bullet_index in range(bullet_count)
        ]
        metadata = [
            {
                "bullet_index": bullet_index,
                "supported_requirement_ids": (
                    [f"req_protected_{project_index}"]
                    if bullet_index == 0
                    else []
                ),
                "protected_requirement_ids": (
                    [f"req_protected_{project_index}"]
                    if bullet_index == 0
                    else []
                ),
                "unique_required_core_count": 1 if bullet_index == 0 else 0,
                "evidence_value": 10.0 if bullet_index == 0 else 0.1,
                "protect_during_fitting": bullet_index == 0,
                "evidence_priority": bullet_index + 1,
            }
            for bullet_index in range(bullet_count)
        ]
        projects.append(
            {
                "title": f"Project {project_index}",
                "display_title": f"Project {project_index}",
                "priority": "medium",
                "project_fit_score": 20,
                "draft_bullets": bullets,
                "compact_bullets": [],
                "bullet_evidence_priorities": metadata,
            }
        )
    return {"recommended_projects": projects}


class BoundedPhase6CFittingTests(unittest.TestCase):
    def _run_fit(
        self,
        *,
        projects: dict | None = None,
        fit_threshold: int = 15,
        page_density_mode: str = "none",
        lock_projects: bool = False,
        render_budget: int | None = None,
        restoration_friendly: bool = False,
    ) -> tuple[dict, list[int]]:
        projects = deepcopy(projects or _projects())
        observed_bullet_counts: list[int] = []

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.docx"
            source.write_bytes(b"phase6c-bounded-source")
            candidate_counts: dict[str, int] = {}
            candidate_bullets: dict[str, list[str]] = {}
            sequence = 0

            def fake_generate(**kwargs):
                nonlocal sequence
                sequence += 1
                count = sum(
                    len(project.get("draft_bullets", []) or [])
                    for project in (
                        (kwargs.get("tailored_projects") or {}).get(
                            "recommended_projects", []
                        )
                        or []
                    )
                )
                observed_bullet_counts.append(count)
                output = root / f"candidate_{sequence}.docx"
                output.write_bytes(b"docx")
                candidate_counts[output.stem] = count
                candidate_bullets[output.stem] = [
                    bullet
                    for project in (
                        (kwargs.get("tailored_projects") or {}).get(
                            "recommended_projects", []
                        )
                        or []
                    )
                    for bullet in project.get("draft_bullets", []) or []
                ]
                return output

            def fake_convert(paths):
                results = {}
                for raw_path in paths:
                    path = Path(raw_path)
                    pdf = root / f"{path.stem}.pdf"
                    pdf.write_bytes(b"pdf")
                    results[str(path.resolve())] = pdf
                return results, {
                    "batch_process_count": 1,
                    "fallback_process_count": 0,
                    "timed_out": False,
                }

            def fake_page_count(pdf_path):
                count = candidate_counts[Path(pdf_path).stem]
                if (
                    restoration_friendly
                    and count == fit_threshold + 1
                    and any(
                        "Project 1 truthful lower-priority evidence bullet"
                        in bullet
                        for bullet in candidate_bullets[Path(pdf_path).stem]
                    )
                ):
                    return 1
                if count <= fit_threshold:
                    return 1
                return 3 if count >= 40 else 2

            def fake_fill(pdf_path):
                count = candidate_counts[Path(pdf_path).stem]
                one_page = count <= fit_threshold
                return {
                    "page_fill_ratio": 0.84 if one_page else None,
                    "estimated_unused_page_ratio": 0.16 if one_page else None,
                    "last_page_fill_ratio": 0.6,
                    "overflow_ratio": 0.0 if one_page else 1.2,
                    "occupied_page_units": 0.84 if one_page else 2.2,
                    "measurement_method": "phase6c-bounded-test",
                }

            patches = (
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "source_docx_signature",
                    return_value="source-signature",
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "generate_tailored_resume_copy",
                    side_effect=fake_generate,
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "convert_docx_batch_to_pdf_if_possible",
                    side_effect=fake_convert,
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "count_pdf_pages",
                    side_effect=fake_page_count,
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "measure_pdf_page_fill",
                    side_effect=fake_fill,
                ),
            )
            with ExitStack() as stack:
                for replacement in patches:
                    stack.enter_context(replacement)
                if render_budget is None:
                    result = generate_tailored_resume_copy_fit_one_page(
                        saved_resume_docx_path=source,
                        tailored_projects=projects,
                        max_projects=4,
                        max_bullets_per_project=66,
                        page_density_mode=page_density_mode,
                        lock_projects=lock_projects,
                        generation_id="bounded-test",
                    )
                else:
                    with patch(
                        "resume_builder.docx_projects_skills_replacer."
                        "FIT_RENDER_BUDGET",
                        render_budget,
                    ):
                        result = generate_tailored_resume_copy_fit_one_page(
                            saved_resume_docx_path=source,
                            tailored_projects=projects,
                            max_projects=4,
                            max_bullets_per_project=66,
                            page_density_mode=page_density_mode,
                            lock_projects=lock_projects,
                            generation_id="bounded-test",
                        )

        return result, observed_bullet_counts

    def test_heavily_overfull_input_is_verified_and_bounded(self) -> None:
        result, observed = self._run_fit()

        self.assertEqual(observed[0], 66)
        self.assertTrue(result["fit_one_page"])
        self.assertEqual(result["fit_status"], "verified_one_page")
        self.assertEqual(result["page_count"], 1)
        self.assertLessEqual(result["candidate_states_rendered"], 100)
        self.assertLess(result["candidate_states_rendered"], FIT_RENDER_BUDGET + 1)
        self.assertGreater(result["coarse_render_count"], 0)
        self.assertGreater(result["exact_render_count"], 0)
        self.assertLess(
            result["candidate_states_rendered"],
            sum(range(1, 63)),
        )
        self.assertIn("fitting_elapsed_seconds", result)
        self.assertIn("render_elapsed_seconds", result)
        self.assertIn("libreoffice_elapsed_seconds", result)
        self.assertIn("candidate_generation_elapsed_seconds", result)
        self.assertEqual(
            result["fitting_search_algorithm_version"],
            PHASE6C_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            result["fitting_optimization_version"],
            PHASE6C1_OPTIMIZATION_VERSION,
        )
        snapshot = result["fitting_input_snapshot"]
        self.assertEqual(
            snapshot["fitting_search_algorithm_version"],
            PHASE6C_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            snapshot["fitter_invocation"]["minimum_total_skills"],
            8,
        )

    def test_unique_protected_evidence_remains_until_lower_tier_is_exhausted(self) -> None:
        result, _ = self._run_fit()

        retained = {
            bullet
            for project in result["tailored_projects_used"]["recommended_projects"]
            for bullet in project["draft_bullets"]
            if "protected unique requirement evidence" in bullet
        }
        self.assertEqual(len(retained), 4)
        self.assertGreater(
            sum(
                len(project["draft_bullets"])
                for project in result["tailored_projects_used"]["recommended_projects"]
            ),
            4,
        )

    def test_bounded_fit_is_deterministic_and_keeps_project_lock(self) -> None:
        first, _ = self._run_fit()
        second, _ = self._run_fit()
        self.assertEqual(
            first["tailored_projects_used"],
            second["tailored_projects_used"],
        )

        locked_source = _projects()
        locked, _ = self._run_fit(
            projects=locked_source,
            lock_projects=True,
        )
        self.assertFalse(locked["fit_one_page"])
        self.assertEqual(locked["fit_status"], "unable_to_fit")
        self.assertEqual(
            sum(
                len(project["draft_bullets"])
                for project in locked["tailored_projects_used"]["recommended_projects"]
            ),
            66,
        )

    def test_restoration_remains_bounded(self) -> None:
        result, _ = self._run_fit(
            fit_threshold=4,
            page_density_mode="balanced",
            restoration_friendly=True,
        )

        self.assertTrue(result["fit_one_page"])
        self.assertGreaterEqual(result["restored_change_count"], 1)
        self.assertLessEqual(
            result["restoration_candidates_rendered"],
            8,
        )

    def test_render_budget_exhaustion_fails_closed(self) -> None:
        result, _ = self._run_fit(render_budget=1)

        self.assertFalse(result["fit_one_page"])
        self.assertEqual(result["fit_status"], "search_exhausted")
        self.assertTrue(result["render_budget_exhausted"])
        self.assertEqual(result["page_count"], 3)

    def test_unavailable_page_count_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.docx"
            source.write_bytes(b"source")
            candidate = root / "candidate.docx"
            candidate.write_bytes(b"docx")
            pdf = root / "candidate.pdf"
            pdf.write_bytes(b"pdf")

            with (
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "source_docx_signature",
                    return_value="source-signature",
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "generate_tailored_resume_copy",
                    return_value=candidate,
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "convert_docx_batch_to_pdf_if_possible",
                    return_value=(
                        {str(candidate.resolve()): pdf},
                        {
                            "batch_process_count": 1,
                            "fallback_process_count": 0,
                            "timed_out": False,
                        },
                    ),
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "count_pdf_pages",
                    return_value=None,
                ),
            ):
                result = generate_tailored_resume_copy_fit_one_page(
                    saved_resume_docx_path=source,
                    tailored_projects=_projects(bullet_counts=(2,)),
                    max_projects=1,
                    max_bullets_per_project=2,
                    page_density_mode="none",
                )

        self.assertFalse(result["fit_one_page"])
        self.assertEqual(result["fit_status"], "verification_failed")
        self.assertIsNone(result["page_count"])

    def test_render_state_fingerprint_ignores_timing_diagnostics(self) -> None:
        common = {
            "source_signature": "source",
            "projects_state": _projects(bullet_counts=(2,)),
            "skills_state": None,
        }
        first = build_render_state_fingerprint(
            **common,
            layout_options={"spacing_mode": "paragraph_spacing"},
        )
        second = build_render_state_fingerprint(
            **common,
            layout_options={
                "spacing_mode": "paragraph_spacing",
            },
        )
        self.assertEqual(first, second)

    def test_render_state_fingerprint_ignores_search_provenance(self) -> None:
        old_projects = _projects(bullet_counts=(2,))
        bounded_projects = deepcopy(old_projects)
        old_projects["recommended_projects"][0][
            "fitting_search_algorithm_version"
        ] = "phase6c-exhaustive-tiered-render-search-v1"
        bounded_projects["recommended_projects"][0][
            "fitting_search_algorithm_version"
        ] = PHASE6C_SEARCH_ALGORITHM_VERSION

        common = {
            "source_signature": "source",
            "skills_state": None,
            "layout_options": {"spacing_mode": "paragraph_spacing"},
        }
        self.assertEqual(
            build_render_state_fingerprint(
                **common,
                projects_state=old_projects,
            ),
            build_render_state_fingerprint(
                **common,
                projects_state=bounded_projects,
            ),
        )

    def test_libreoffice_batch_timeout_returns_no_verified_render(self) -> None:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.docx"
            source.write_bytes(b"source")
            with (
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "_find_libreoffice_executable",
                    return_value="soffice",
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "subprocess.run",
                    side_effect=subprocess.TimeoutExpired("soffice", 1),
                ),
            ):
                converted, diagnostics = convert_docx_batch_to_pdf_if_possible(
                    [source]
                )

        self.assertTrue(diagnostics["timed_out"])
        self.assertTrue(all(path is None for path in converted.values()))
        self.assertEqual(diagnostics["fallback_process_count"], 0)

    def test_timed_out_render_fails_the_fit_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.docx"
            source.write_bytes(b"source")
            candidate = root / "candidate.docx"
            candidate.write_bytes(b"docx")

            with (
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "source_docx_signature",
                    return_value="source-signature",
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "generate_tailored_resume_copy",
                    return_value=candidate,
                ),
                patch(
                    "resume_builder.docx_projects_skills_replacer."
                    "convert_docx_batch_to_pdf_if_possible",
                    return_value=(
                        {str(candidate.resolve()): None},
                        {
                            "batch_process_count": 1,
                            "fallback_process_count": 0,
                            "timed_out": True,
                        },
                    ),
                ),
            ):
                result = generate_tailored_resume_copy_fit_one_page(
                    saved_resume_docx_path=source,
                    tailored_projects=_projects(bullet_counts=(2,)),
                    max_projects=1,
                    max_bullets_per_project=2,
                    page_density_mode="none",
                )

        self.assertFalse(result["fit_one_page"])
        self.assertEqual(result["fit_status"], "verification_failed")
        self.assertEqual(result["libreoffice_timeout_count"], 1)
        self.assertEqual(result["libreoffice_fallback_processes"], 0)


if __name__ == "__main__":
    unittest.main()
