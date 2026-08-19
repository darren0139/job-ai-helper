from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from resume_builder.docx_projects_skills_replacer import (
    DEFAULT_MINIMUM_TOTAL_SKILLS,
    generate_tailored_resume_copy_fit_one_page,
    prepare_fitting_input_snapshot,
)
from resume_builder.evidence_aware_fitting import PHASE6C_FITTING_VERSION
from resume_builder.fitting_provenance import (
    PHASE6C_SEARCH_ALGORITHM_VERSION,
    fitting_input_fingerprint,
)


def _projects() -> dict:
    return {
        "recommended_projects": [
            {
                "title": "Project One",
                "display_title": "Project One",
                "period": "2026",
                "priority": "high",
                "project_fit_score": 9,
                "matched_jd_requirements": ["req-a"],
                "transferable_jd_requirements": ["req-b"],
                "draft_bullets": ["First bullet", "Second bullet", "Third bullet"],
                "compact_bullets": ["First compact", "Second compact", "Third compact"],
                "bullet_evidence_priorities": [
                    {
                        "bullet_index": 0,
                        "bullet_text": "First bullet",
                        "supported_requirement_ids": ["req-a"],
                        "protected_requirement_ids": ["req-a"],
                        "unique_required_core_count": 1,
                        "evidence_value": 4.0,
                        "protect_during_fitting": True,
                        "evidence_priority": 10,
                    },
                    {
                        "bullet_index": 1,
                        "bullet_text": "Second bullet",
                        "supported_requirement_ids": [],
                        "protected_requirement_ids": [],
                        "unique_required_core_count": 0,
                        "evidence_value": 0.5,
                        "protect_during_fitting": False,
                        "evidence_priority": 1,
                    },
                    {
                        "bullet_index": 2,
                        "bullet_text": "Third bullet",
                        "supported_requirement_ids": [],
                        "protected_requirement_ids": [],
                        "unique_required_core_count": 0,
                        "evidence_value": 0.2,
                        "protect_during_fitting": False,
                        "evidence_priority": 2,
                    },
                ],
                "debug_timestamp": "2026-08-19T01:02:03Z",
            },
            {
                "title": "Project Two",
                "draft_bullets": ["Unrendered after max-project truncation"],
                "bullet_evidence_priorities": [{"bullet_index": 0}],
            },
        ],
        "deterministic_rule_debug": {
            "generated_at": "2026-08-19T01:02:03Z",
            "bullet_allocation": {"allocation_mode": "adaptive"},
        },
    }


def _skills() -> dict:
    return {
        "skill_lines": [{"category": "Tools", "items": ["Python", "SQL"]}],
        "skill_priorities": [
            {
                "skill": "Python",
                "jd_relevance": 5,
                "evidence_strength": 5,
                "required_match": True,
                "preferred_match": False,
            }
        ],
        "debug_timestamp": "2026-08-19T01:02:03Z",
    }


class FittingInputSnapshotTests(unittest.TestCase):
    def _prepare(
        self,
        *,
        projects: dict | None = None,
        skills: dict | None = None,
        max_projects: int = 1,
        max_bullets: int = 1,
    ):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.docx"
            source.write_bytes(b"snapshot-source")
            return prepare_fitting_input_snapshot(
                saved_resume_docx_path=source,
                tailored_projects=deepcopy(projects or _projects()),
                tailored_skills=deepcopy(skills or _skills()),
                max_projects=max_projects,
                max_bullets_per_project=max_bullets,
                spacing_mode="paragraph_spacing",
                project_spacing_pt=10,
                after_projects_spacing_pt=10,
                blank_lines_between_projects=1,
                blank_lines_after_projects=1,
                add_spacing_before_first_project=False,
                use_compact_before_delete=True,
                prefer_balanced_bullets=False,
                allow_skills_compaction=True,
                lock_projects=False,
                lock_skills=False,
                minimum_total_skills=DEFAULT_MINIMUM_TOTAL_SKILLS,
                page_density_mode="balanced",
                allow_margin_compaction=False,
                project_header_layout="auto",
                project_metadata_style="pipes",
                source_artifact_identity=None,
            )

    def test_caller_and_prepared_boundaries_preserve_expected_content(self) -> None:
        snapshot = self._prepare().fitting_input_snapshot

        caller_projects = snapshot["caller_input"]["projects"][
            "recommended_projects"
        ]
        prepared_projects = snapshot["prepared_initial_state"]["projects"][
            "recommended_projects"
        ]
        self.assertEqual(len(caller_projects), 2)
        self.assertEqual(len(caller_projects[0]["draft_bullets"]), 3)
        self.assertEqual(len(prepared_projects), 1)
        self.assertEqual(prepared_projects[0]["draft_bullets"], ["First bullet"])
        self.assertEqual(
            prepared_projects[0]["bullet_evidence_priorities"][0][
                "protected_requirement_ids"
            ],
            ["req-a"],
        )

    def test_source_display_fallback_exists_only_in_prepared_state(self) -> None:
        projects = _projects()
        projects["recommended_projects"][0].pop("display_title")
        projects["recommended_projects"][0].pop("period")

        def fallback(_source: object, incoming: dict) -> dict:
            enriched = deepcopy(incoming)
            enriched["recommended_projects"][0]["subtitle"] = "Source subtitle"
            enriched["recommended_projects"][0]["resume_header_tools"] = ["Python"]
            enriched["recommended_projects"][0]["display_title"] = "Project One — Source subtitle"
            return enriched

        with patch(
            "resume_builder.docx_projects_skills_replacer."
            "apply_source_project_display_fallbacks",
            side_effect=fallback,
        ):
            snapshot = self._prepare(projects=projects).fitting_input_snapshot

        caller = snapshot["caller_input"]["projects"]["recommended_projects"][0]
        prepared = snapshot["prepared_initial_state"]["projects"][
            "recommended_projects"
        ][0]
        self.assertNotIn("subtitle", caller)
        self.assertEqual(prepared["subtitle"], "Source subtitle")
        self.assertEqual(prepared["resume_header_tools"], ["Python"])

    def test_debug_timestamps_do_not_change_identity_but_semantic_inputs_do(self) -> None:
        baseline = self._prepare().fitting_input_snapshot
        debug_changed_projects = _projects()
        debug_changed_skills = _skills()
        debug_changed_projects["recommended_projects"][0]["debug_timestamp"] = "later"
        debug_changed_projects["deterministic_rule_debug"]["generated_at"] = "later"
        debug_changed_skills["debug_timestamp"] = "later"
        debug_changed = self._prepare(
            projects=debug_changed_projects,
            skills=debug_changed_skills,
        ).fitting_input_snapshot
        self.assertEqual(
            baseline["fitting_input_fingerprint"],
            debug_changed["fitting_input_fingerprint"],
        )

        bullet_changed_projects = _projects()
        bullet_changed_projects["recommended_projects"][0]["draft_bullets"][0] = (
            "Changed semantic bullet"
        )
        bullet_changed = self._prepare(projects=bullet_changed_projects).fitting_input_snapshot
        self.assertNotEqual(
            baseline["fitting_input_fingerprint"],
            bullet_changed["fitting_input_fingerprint"],
        )

        protection_changed_projects = _projects()
        protection_changed_projects["recommended_projects"][0][
            "bullet_evidence_priorities"
        ][0]["protect_during_fitting"] = False
        protection_changed = self._prepare(
            projects=protection_changed_projects
        ).fitting_input_snapshot
        self.assertNotEqual(
            baseline["fitting_input_fingerprint"],
            protection_changed["fitting_input_fingerprint"],
        )

    def test_snapshot_carries_policy_search_and_explicit_minimum_skills(self) -> None:
        snapshot = self._prepare().fitting_input_snapshot
        invocation = snapshot["fitter_invocation"]
        self.assertEqual(snapshot["fitting_policy_version"], PHASE6C_FITTING_VERSION)
        self.assertEqual(
            snapshot["fitting_search_algorithm_version"],
            PHASE6C_SEARCH_ALGORITHM_VERSION,
        )
        self.assertEqual(
            invocation["minimum_total_skills"],
            DEFAULT_MINIMUM_TOTAL_SKILLS,
        )
        self.assertEqual(invocation["max_projects"], 1)
        self.assertEqual(invocation["max_bullets_per_project"], 1)
        self.assertEqual(invocation["requested_max_projects"], 1)
        self.assertEqual(invocation["requested_max_bullets_per_project"], 1)
        self.assertEqual(
            invocation["prepared_payload_max_bullets_per_project"], 1
        )
        self.assertEqual(invocation["project_header_layout"], "stacked")
        self.assertEqual(invocation["requested_project_header_layout"], "auto")
        self.assertEqual(invocation["project_metadata_style"], "pipes")
        self.assertEqual(
            snapshot["source_artifact"]["sha256"],
            hashlib.sha256(b"snapshot-source").hexdigest(),
        )
        self.assertEqual(
            snapshot["source_artifact"]["byte_size"], len(b"snapshot-source")
        )

    def test_named_fingerprint_covers_policy_search_settings_source_and_input(self) -> None:
        baseline = self._prepare().fitting_input_snapshot
        baseline_fingerprint = baseline["fitting_input_fingerprint"]
        variants = []

        policy_changed = deepcopy(baseline)
        policy_changed["fitting_policy_version"] = "test-policy-v2"
        variants.append(policy_changed)

        search_changed = deepcopy(baseline)
        search_changed["fitting_search_algorithm_version"] = "test-search-v2"
        variants.append(search_changed)

        settings_changed = deepcopy(baseline)
        settings_changed["fitter_invocation"]["project_spacing_pt"] = 9
        variants.append(settings_changed)

        source_changed = deepcopy(baseline)
        source_changed["source_artifact"]["sha256"] = "0" * 64
        variants.append(source_changed)

        input_changed = deepcopy(baseline)
        input_changed["caller_input"]["projects"]["recommended_projects"][0][
            "draft_bullets"
        ][0] = "Changed caller input"
        variants.append(input_changed)

        for variant in variants:
            self.assertNotEqual(
                fitting_input_fingerprint(variant),
                baseline_fingerprint,
            )

    def test_returned_non_one_page_result_carries_snapshot(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.docx"
            source.write_bytes(b"snapshot-source")
            output = root / "candidate.docx"
            output.write_bytes(b"docx")
            pdf = root / "candidate.pdf"
            pdf.write_bytes(b"pdf")
            with patch(
                "resume_builder.docx_projects_skills_replacer."
                "generate_tailored_resume_copy",
                return_value=output,
            ), patch(
                "resume_builder.docx_projects_skills_replacer."
                "convert_docx_batch_to_pdf_if_possible",
                return_value=(
                    {str(output.resolve()): pdf},
                    {
                        "batch_process_count": 1,
                        "fallback_process_count": 0,
                        "timed_out": False,
                    },
                ),
            ), patch(
                "resume_builder.docx_projects_skills_replacer.count_pdf_pages",
                return_value=2,
            ), patch(
                "resume_builder.docx_projects_skills_replacer.measure_pdf_page_fill",
                return_value={"measurement_method": "test"},
            ):
                result = generate_tailored_resume_copy_fit_one_page(
                    saved_resume_docx_path=source,
                    tailored_projects={
                        "recommended_projects": [
                            {"title": "Only", "draft_bullets": ["Only bullet"]}
                        ]
                    },
                    lock_projects=True,
                )
        self.assertFalse(result["fit_one_page"])
        self.assertIn("fitting_input_snapshot", result)
        self.assertIn("fitting_input_fingerprint", result)
        invocation = result["fitting_input_snapshot"]["fitter_invocation"]
        # The caller omitted this setting; the direct fitter's default must
        # nevertheless be durable and replayable.
        self.assertEqual(
            invocation["minimum_total_skills"], DEFAULT_MINIMUM_TOTAL_SKILLS
        )
        self.assertEqual(invocation["max_projects"], 999999)
        self.assertEqual(invocation["max_bullets_per_project"], 999999)
        self.assertEqual(invocation["requested_max_projects"], 3)
        self.assertEqual(invocation["requested_max_bullets_per_project"], 3)


if __name__ == "__main__":
    unittest.main()
