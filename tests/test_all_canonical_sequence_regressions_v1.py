from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from resume_builder.docx_projects_skills_replacer import (
    generate_tailored_resume_copy_fit_one_page,
    resolve_effective_fitting_bullet_ceiling,
    resolve_fitting_bullet_allocation_mode,
)
from tailoring.deterministic_bullet_allocation import (
    BULLET_ALLOCATION_MODE_ADAPTIVE,
    BULLET_ALLOCATION_MODE_ALL_CANONICAL,
    BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
    build_deterministic_bullet_allocation,
)
from tailoring.stable_tailoring_ranking import (
    _collect_supported_skill_candidates,
    _normalise_skill_key,
    build_deterministic_skills_result,
)
from tailoring.tailoring_generation_fingerprint import (
    build_tailoring_input_fingerprint,
    stable_content_fingerprint,
)


PROJECT_COUNTS = (6, 3, 4, 3)


def _project_pair(project_index: int, bullet_count: int) -> tuple[dict, dict]:
    title = f"Project {project_index}"
    bullets = [
        f"Implemented canonical capability {project_index}.{bullet_index}."
        for bullet_index in range(1, bullet_count + 1)
    ]
    candidate = {
        "title": title,
        "display_title": title,
        "evidence_library_evidence": {
            "bullets": bullets,
            "tools": [f"Tool {project_index}"],
            "skills": [],
        },
    }
    ranking = {
        "project_id": f"project_{project_index}",
        "title": title,
        "display_title": title,
        "final_score": 40,
        "requirement_matches": [],
    }
    return candidate, ranking


def _all_canonical_projects() -> dict:
    pairs = [
        _project_pair(index, count)
        for index, count in enumerate(PROJECT_COUNTS, start=1)
    ]
    allocation = build_deterministic_bullet_allocation(
        selected_pairs=pairs,
        max_bullets_per_project=4,
        allocation_mode=BULLET_ALLOCATION_MODE_ALL_CANONICAL,
    )
    projects = []
    for (candidate, _), plan in zip(pairs, allocation["projects"]):
        projects.append(
            {
                "title": candidate["title"],
                "display_title": candidate["display_title"],
                "draft_bullets": list(plan["allocated_blueprint_bullets"]),
                "compact_bullets": [],
                "allocated_bullet_count": plan["allocated_bullet_count"],
                "allocated_bullet_ids": list(plan["allocated_bullet_ids"]),
            }
        )
    return {
        "recommended_projects": projects,
        "deterministic_rule_debug": {
            "bullet_allocation": allocation,
        },
    }


def _requirements() -> dict:
    return {
        "canonical_requirements": [
            {
                "requirement_id": "req_quality",
                "text": "Quality assurance and testing",
                "importance": "core",
            }
        ]
    }


def _skills_evidence(*, tools: list[str]) -> list[dict]:
    return [
        {
            "id": 1,
            "category": "Project",
            "title": "Job AI Helper",
            "description": "Built deterministic verification workflows.",
            "skills": [],
            "tools": list(tools),
            "updated_at": "2026-08-12T00:00:00",
        }
    ]


class AllCanonicalFitHandoffTests(unittest.TestCase):
    def test_effective_capacity_comes_from_frozen_all_canonical_payload(self) -> None:
        projects = _all_canonical_projects()

        self.assertEqual(
            resolve_effective_fitting_bullet_ceiling(
                projects,
                configured_max_bullets_per_project=4,
            ),
            6,
        )
        self.assertEqual(
            resolve_fitting_bullet_allocation_mode(
                projects,
                fallback_mode=BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
            ),
            BULLET_ALLOCATION_MODE_ALL_CANONICAL,
        )

    def test_adaptive_and_prefer_available_keep_configured_ceiling(self) -> None:
        for mode in (
            BULLET_ALLOCATION_MODE_ADAPTIVE,
            BULLET_ALLOCATION_MODE_PREFER_AVAILABLE,
        ):
            projects = _all_canonical_projects()
            projects["deterministic_rule_debug"]["bullet_allocation"][
                "allocation_mode"
            ] = mode
            self.assertEqual(
                resolve_effective_fitting_bullet_ceiling(
                    projects,
                    configured_max_bullets_per_project=4,
                ),
                4,
            )

    def _run_fitter(
        self,
        *,
        overflow_full_payload: bool,
        projects: dict | None = None,
    ) -> tuple[dict, list[int]]:
        projects = projects or _all_canonical_projects()
        rendered_counts: dict[str, int] = {}
        observed_counts: list[int] = []

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.docx"
            source.write_bytes(b"source")
            render_index = 0

            def fake_generate(**kwargs):
                nonlocal render_index
                render_index += 1
                count = sum(
                    len(project.get("draft_bullets") or [])
                    for project in (
                        (kwargs.get("tailored_projects") or {}).get(
                            "recommended_projects",
                            [],
                        )
                        or []
                    )
                )
                observed_counts.append(count)
                path = root / f"candidate_{render_index}.docx"
                path.write_bytes(b"docx")
                rendered_counts[path.stem] = count
                return path

            def fake_convert(paths):
                converted = {}
                for docx_path in paths:
                    docx_path = Path(docx_path)
                    pdf_path = root / f"{docx_path.stem}.pdf"
                    pdf_path.write_bytes(b"pdf")
                    converted[str(docx_path.resolve())] = pdf_path
                return converted, {
                    "batch_process_count": 1,
                    "fallback_process_count": 0,
                }

            def fake_page_count(pdf_path):
                count = rendered_counts[Path(pdf_path).stem]
                return 2 if overflow_full_payload and count == 16 else 1

            with (
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
                    return_value={
                        "page_fill_ratio": 0.8,
                        "estimated_unused_page_ratio": 0.2,
                        "last_page_fill_ratio": 0.8,
                        "overflow_ratio": 0.0,
                        "occupied_page_units": 0.8,
                        "measurement_method": "test",
                    },
                ),
            ):
                result = generate_tailored_resume_copy_fit_one_page(
                    saved_resume_docx_path=source,
                    tailored_projects=projects,
                    max_projects=4,
                    max_bullets_per_project=4,
                    page_density_mode="none",
                    generation_id="sequence-regression",
                )

        return result, observed_counts

    def test_first_full_render_receives_all_16_and_keeps_them_when_fit(self) -> None:
        result, observed_counts = self._run_fitter(
            overflow_full_payload=False,
        )

        self.assertEqual(observed_counts[0], 16)
        self.assertEqual(result["attempts"][0]["attempt_type"], "full")
        self.assertEqual(result["attempts"][0]["bullet_count"], 16)
        self.assertEqual(
            [
                len(project["draft_bullets"])
                for project in result["tailored_projects_used"][
                    "recommended_projects"
                ]
            ],
            list(PROJECT_COUNTS),
        )

    def test_intervening_skills_only_sequence_still_first_renders_16(self) -> None:
        first_combined = _all_canonical_projects()
        allocation_identity = deepcopy(
            first_combined["deterministic_rule_debug"]["bullet_allocation"]
        )
        build_deterministic_skills_result(
            raw_result={"notes": ["intervening skills-only call"]},
            resume_profile={"skills": {"tools": ["Python"]}},
            evidence_items=_skills_evidence(
                tools=["GitHub", "Python unittest"],
            ),
            stable_analysis=_requirements(),
            selected_projects_result=first_combined,
        )
        second_combined = _all_canonical_projects()

        self.assertEqual(
            first_combined["deterministic_rule_debug"]["bullet_allocation"],
            allocation_identity,
        )
        self.assertEqual(
            second_combined["deterministic_rule_debug"]["bullet_allocation"],
            allocation_identity,
        )
        result, observed_counts = self._run_fitter(
            overflow_full_payload=False,
            projects=second_combined,
        )
        self.assertEqual(observed_counts[0], 16)
        self.assertEqual(result["attempts"][0]["bullet_count"], 16)

    def test_reduction_occurs_only_after_recorded_overflowing_full_render(self) -> None:
        result, observed_counts = self._run_fitter(
            overflow_full_payload=True,
        )

        first = result["attempts"][0]
        self.assertEqual(first["attempt_type"], "full")
        self.assertEqual(first["bullet_count"], 16)
        self.assertEqual(first["page_count"], 2)
        self.assertEqual(observed_counts[0], 16)
        self.assertTrue(
            any(
                attempt.get("bullet_count", 16) < 16
                for attempt in result["attempts"][1:]
            )
        )


class GenerationSequenceIdentityTests(unittest.TestCase):
    def test_intervening_skills_identity_does_not_change_combined_cache_key(self) -> None:
        report = {
            "resume_profile": {"skills": {"tools": ["Python"]}},
            "jd_profile": {"required_skills": ["testing"]},
            "raw_jd_text": "Testing",
            "stable_analysis": {
                **_requirements(),
                "input_fingerprint": "stable-input",
                "scoring_version": "stable-version",
                "capability_taxonomy_version": "taxonomy-version",
            },
        }
        evidence = _skills_evidence(
            tools=["GitHub", "Python unittest"],
        )
        settings = {
            "max_projects": 4,
            "max_bullets": 4,
            "bullet_allocation_mode": (
                BULLET_ALLOCATION_MODE_ALL_CANONICAL
            ),
        }
        common = {
            "report": report,
            "evidence_items": evidence,
            "generation_settings": settings,
            "model_id": "test-model",
        }
        combined_before = build_tailoring_input_fingerprint(
            generation_kind="projects_skills",
            **common,
        )
        skills_only = build_tailoring_input_fingerprint(
            generation_kind="skills",
            **common,
        )
        combined_after = build_tailoring_input_fingerprint(
            generation_kind="projects_skills",
            **common,
        )

        self.assertEqual(combined_before, combined_after)
        self.assertNotEqual(combined_before, skills_only)

    def test_skills_only_does_not_mutate_all_canonical_project_identity(self) -> None:
        projects = _all_canonical_projects()
        before = stable_content_fingerprint(projects)
        allocation_before = deepcopy(
            projects["deterministic_rule_debug"]["bullet_allocation"]
        )

        build_deterministic_skills_result(
            raw_result={"notes": ["first model wording"]},
            resume_profile={"skills": {"tools": ["Python"]}},
            evidence_items=_skills_evidence(
                tools=["GitHub", "Python unittest"],
            ),
            stable_analysis=_requirements(),
            selected_projects_result=projects,
        )

        self.assertEqual(stable_content_fingerprint(projects), before)
        self.assertEqual(
            projects["deterministic_rule_debug"]["bullet_allocation"],
            allocation_before,
        )

    def test_identical_project_payload_has_identical_deterministic_skills(self) -> None:
        kwargs = {
            "resume_profile": {"skills": {"tools": ["Python"]}},
            "evidence_items": _skills_evidence(
                tools=["GitHub", "Python unittest"],
            ),
            "stable_analysis": _requirements(),
            "selected_projects_result": _all_canonical_projects(),
        }
        skills_only = build_deterministic_skills_result(
            raw_result={"notes": ["skills-only model wording"]},
            **kwargs,
        )
        combined = build_deterministic_skills_result(
            raw_result={"notes": ["combined model wording changed"]},
            **kwargs,
        )

        self.assertEqual(skills_only["skill_lines"], combined["skill_lines"])
        self.assertEqual(
            skills_only["skill_priorities"],
            combined["skill_priorities"],
        )

    def test_changed_project_payload_is_an_explicit_skills_input(self) -> None:
        evidence = [
            {
                "category": "Project",
                "title": "Alpha Project",
                "description": "Alpha evidence",
                "skills": [],
                "tools": ["Alpha Tool"],
            },
            {
                "category": "Project",
                "title": "Beta Project",
                "description": "Beta evidence",
                "skills": [],
                "tools": ["Beta Tool"],
            },
        ]
        common = {
            "raw_result": {},
            "resume_profile": {"skills": {}},
            "evidence_items": evidence,
            "stable_analysis": _requirements(),
            "max_items": 1,
        }
        alpha = build_deterministic_skills_result(
            selected_projects_result={
                "recommended_projects": [{"title": "Alpha Project"}],
            },
            **common,
        )
        beta = build_deterministic_skills_result(
            selected_projects_result={
                "recommended_projects": [{"title": "Beta Project"}],
            },
            **common,
        )

        self.assertEqual(alpha["skill_lines"][0]["items"], ["Alpha Tool"])
        self.assertEqual(beta["skill_lines"][0]["items"], ["Beta Tool"])

    def test_evidence_edit_invalidates_dependent_generation_not_history(self) -> None:
        report = {
            "resume_profile": {"skills": {"tools": ["Python"]}},
            "jd_profile": {"required_skills": ["testing"]},
            "raw_jd_text": "Testing",
            "stable_analysis": {
                **_requirements(),
                "input_fingerprint": "stable-input",
                "scoring_version": "stable-version",
                "capability_taxonomy_version": "taxonomy-version",
            },
        }
        settings = {
            "max_projects": 4,
            "max_bullets": 4,
            "bullet_allocation_mode": (
                BULLET_ALLOCATION_MODE_ALL_CANONICAL
            ),
        }
        before_evidence = _skills_evidence(tools=["GitHub"])
        after_evidence = _skills_evidence(
            tools=["GitHub", "Python unittest"],
        )
        historical = {
            "generation_id": "historical",
            "projects": _all_canonical_projects(),
            "skills": {"skill_lines": []},
        }
        historical_before = deepcopy(historical)

        before = build_tailoring_input_fingerprint(
            report=report,
            evidence_items=before_evidence,
            generation_settings=settings,
            generation_kind="projects_skills",
            model_id="test-model",
        )
        after = build_tailoring_input_fingerprint(
            report=report,
            evidence_items=after_evidence,
            generation_settings=settings,
            generation_kind="projects_skills",
            model_id="test-model",
        )

        self.assertNotEqual(before, after)
        self.assertEqual(historical, historical_before)

    def test_python_unittest_is_ingested_but_top_n_can_exclude_it(self) -> None:
        evidence = _skills_evidence(
            tools=["GitHub", "Python unittest"],
        )
        selected = {"recommended_projects": [{"title": "Job AI Helper"}]}
        candidates = _collect_supported_skill_candidates(
            resume_profile={
                "skills": {"tools": ["GitHub", "Python unittest"]},
            },
            evidence_items=evidence,
            selected_project_identity_index={},
            raw_result={},
        )
        unittest_key = _normalise_skill_key("Python unittest")
        self.assertIn(unittest_key, candidates)
        self.assertIn("evidence_library.tool", candidates[unittest_key]["sources"])

        result = build_deterministic_skills_result(
            raw_result={},
            resume_profile={
                "skills": {"tools": ["GitHub", "Python unittest"]},
            },
            evidence_items=evidence,
            stable_analysis=_requirements(),
            selected_projects_result=selected,
            max_items=1,
        )
        ranking = result["deterministic_skill_ranking"]
        unittest_row = next(
            row for row in ranking if row["skill_key"] == unittest_key
        )

        self.assertEqual(unittest_row["evidence_strength"], 5)
        self.assertTrue(unittest_row["selected_project_support"])
        self.assertNotIn(
            "Python unittest",
            [
                item
                for line in result["skill_lines"]
                for item in line["items"]
            ],
        )
        self.assertEqual(result["skill_lines"][0]["items"], ["GitHub"])


if __name__ == "__main__":
    unittest.main()
