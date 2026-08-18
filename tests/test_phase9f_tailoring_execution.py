from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import (
    db_manager,
    jd_library_manager,
    tailoring_version_manager,
    user_profile_manager,
)
import database.phase9f_tailoring_execution_manager as execution_manager
from database.application_blueprint_manager import (
    get_current_application_blueprint_decision,
    resolve_current_phase9e_generation_context,
)
from database.global_blueprint_manager import (
    get_global_blueprint,
    remove_global_blueprint_from_reuse,
)
from database.jd_library_manager import get_exact_job_description_for_application
from database.phase9f_application_confirmation_manager import (
    get_phase9f_application_confirmation,
)
from database.tailoring_generation_control import approve_tailoring_generation
from analysis_stability import build_stable_analysis
from tailoring.phase9e_blueprint_selection import build_phase9e_keyword_match
from tailoring.phase9f_application_execution import (
    build_execution_identity as build_reuse_execution_identity,
    prepare_execution as prepare_reuse_execution,
    validate_phase9f_d_execution_scope,
    validate_reuse_execution_scope,
)
from tailoring.phase9f_tailoring_execution import (
    PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
    Phase9FFExecutionError,
    build_execution_debug_summary,
    build_frozen_evidence_snapshot,
    build_section_scope,
)
from tests.phase9f_d_test_support import configure_database
from tests.phase9f_e_test_support import create_d_reuse_session
from tests.test_phase9f_starting_source_ranking import (
    JD_PROFILE,
    JD_TEXT,
    make_exact_jd,
    resume_profile,
    resume_text,
)


class Phase9FTailoringExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database_path = self.root / "phase9f-f.db"
        self.source_root = self.root / "sources"
        self.source_root.mkdir()
        self.output_docx = self.root / "changed.docx"
        self.output_pdf = self.root / "changed.pdf"
        self.output_docx.write_bytes(b"phase9f-f-test-docx")
        self.output_pdf.write_bytes(b"phase9f-f-test-pdf")
        self.old_paths = (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
            user_profile_manager.DB_PATH,
        )
        configure_database(self.database_path)
        user_profile_manager.DB_PATH = self.database_path

    def tearDown(self) -> None:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
            user_profile_manager.DB_PATH,
        ) = self.old_paths
        self.temporary.cleanup()

    def _session(self, intensity: str = "minor", source_type: str = "global_blueprint") -> dict:
        return create_d_reuse_session(
            self.database_path,
            source_type=source_type,
            artifact_root=self.source_root,
            confirmed_intensity=intensity,
        )

    def _count(self, table: str, application_id: int) -> int:
        connection = tailoring_version_manager._connect()
        try:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists is None:
                return 0
            return int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE application_id=?",
                    (int(application_id),),
                ).fetchone()[0]
            )
        finally:
            connection.close()

    @staticmethod
    def _scope_from_snapshot(**kwargs) -> dict:
        rows = copy.deepcopy(kwargs["evidence_snapshot"]["rows"])
        selected = rows[:1]
        return {
            "policy_version": PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
            "phase9a_version": "phase9a-evidence-opportunity-v1",
            "confirmed_intensity": kwargs["confirmed_intensity"],
            "opportunity_fingerprint": "opportunity-fingerprint",
            "selected_evidence_ids": [row["id"] for row in selected],
            "selected_evidence_fingerprint": "selected-evidence-fingerprint",
            "projects_addressable": True,
            "skills_addressable": True,
            "enabled_sections": ["projects", "skills"],
            "selected_evidence": selected,
            "opportunity": {"private": "not-a-draft"},
            "scope_fingerprint": "scope-fingerprint",
        }

    def _add_evidence(self, count: int = 101) -> None:
        user_profile_manager.init_user_profile_library()
        for index in range(count):
            user_profile_manager.create_evidence_item(
                category="Project",
                title=f"Evidence {index:03d}",
                description=(
                    "Built a verified React and PostgreSQL integration "
                    f"for requirement {index}."
                ),
                period="2026",
                skills=["React", "PostgreSQL"],
                tools=["PostgREST"],
                impact="Truthful synthetic test evidence.",
            )

    def _source_bundle(self) -> dict:
        source_docx = self.root / "source.docx"
        if not source_docx.exists():
            source_docx.write_bytes(b"phase9f-f-source-docx")
        artifact_bytes = source_docx.read_bytes()
        return {
            "artifacts": [
                {
                    "artifact_type": "docx",
                    "source_path": str(source_docx),
                    "artifact_bytes": artifact_bytes,
                    "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                    "byte_size": len(artifact_bytes),
                }
            ]
        }

    def _projects_writer(self, calls: list[dict]):
        def writer(**kwargs):
            calls.append(copy.deepcopy(kwargs))
            return {
                "recommended_projects": [
                    {
                        "title": "Evidence-backed target project",
                        "display_title": "Evidence-backed target project",
                        "period": "2026",
                        "draft_bullets": [
                            "Built a verified target integration from frozen evidence."
                        ],
                    }
                ],
                "candidate_project_ranking": [],
            }

        return writer

    @staticmethod
    def _skills_writer(**kwargs) -> dict:
        return {
            "skill_lines": [
                {"category": "Evidence-backed additions", "items": ["PostgREST"]}
            ]
        }

    def _fit_writer(self, calls: list[dict]):
        def writer(**kwargs):
            calls.append(copy.deepcopy(kwargs))
            return {
                "generation_id": kwargs["generation_id"],
                "fit_one_page": True,
                "page_count": 1,
                "docx_path": str(self.output_docx),
                "pdf_path": str(self.output_pdf),
                "tailored_projects_used": copy.deepcopy(kwargs["tailored_projects"]),
                "tailored_skills_used": copy.deepcopy(kwargs["tailored_skills"]),
            }

        return writer

    @staticmethod
    def _valid_phase8_result(*, application_id: int, generation_id: str, baseline: dict) -> dict:
        """A complete existing-Phase-8 success contract for orchestration tests."""
        return {
            "phase8_version": execution_manager.PHASE8_VERIFICATION_VERSION,
            "verification_fingerprint": "f" * 64,
            "application_id": int(application_id),
            "generation_id": str(generation_id),
            "generation_status": "approved",
            "comparison_valid": True,
            "fit_one_page": True,
            "page_count": 1,
            "blueprint_ready": True,
            "verdict": "maintained",
            "before_stable_analysis": copy.deepcopy(
                baseline["stable_analysis"]
            ),
        }

    def _create_waiting_for_phase8(self) -> tuple[dict, list[dict], list[dict]]:
        """Create one approved F draft using only deterministic/local writers."""
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        fit_calls: list[dict] = []
        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            created = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                fit_writer=self._fit_writer(fit_calls),
            )
        self.assertEqual(created["execution"]["status"], "waiting_for_approval")
        approve_tailoring_generation(application_id, created["execution"]["generation_id"])
        execution = execution_manager.reconcile_phase9f_tailoring_approval(
            application_id=application_id
        )
        self.assertEqual(execution["status"], "waiting_for_phase8")
        return execution, project_calls, fit_calls

    def test_validator_extraction_preserves_reuse_scope_identity_and_errors(self) -> None:
        state = self._session("reuse")
        app_id = state["application_id"]
        confirmation = get_phase9f_application_confirmation(app_id)
        decision = get_current_application_blueprint_decision(app_id)
        exact_jd = get_exact_job_description_for_application(app_id)

        reuse_scope = validate_reuse_execution_scope(
            application_id=app_id,
            confirmation=confirmation,
            decision=decision,
            exact_jd=exact_jd,
        )
        shared_scope = validate_phase9f_d_execution_scope(
            application_id=app_id,
            confirmation=confirmation,
            decision=decision,
            exact_jd=exact_jd,
            allowed_intensities={"reuse"},
            intensity_error_code="confirmed_intensity_not_reuse",
            intensity_error_message=(
                "Phase 9F-E Reuse cannot execute a Minor or Full confirmation."
            ),
        )
        self.assertEqual(reuse_scope, shared_scope)
        self.assertEqual(
            build_reuse_execution_identity(reuse_scope),
            build_reuse_execution_identity(shared_scope),
        )
        self.assertEqual(
            prepare_reuse_execution(reuse_scope),
            prepare_reuse_execution(shared_scope),
        )
        with self.assertRaisesRegex(ValueError, "positive Application") as raised:
            validate_reuse_execution_scope(
                application_id=0,
                confirmation=confirmation,
                decision=decision,
                exact_jd=exact_jd,
            )
        self.assertEqual(raised.exception.code, "application_id_invalid")

    def test_complete_evidence_snapshot_is_sorted_allowlisted_and_over_100_rows(self) -> None:
        source = [
            {
                "id": index,
                "category": "Project",
                "title": f"Evidence {index}",
                "description": f"Verified description {index}",
                "skills": ["Python"],
                "tools": ["PostgreSQL"],
                "impact": "Test only",
                "source_type": "manual",
                "created_at": "2026-08-18T00:00:00",
                "updated_at": "2026-08-18T00:00:00",
                "secret": "must-not-be-copied",
            }
            for index in range(150, 0, -1)
        ]
        snapshot = build_frozen_evidence_snapshot(source)
        self.assertEqual(len(snapshot["rows"]), 150)
        self.assertEqual([row["id"] for row in snapshot["rows"]], list(range(1, 151)))
        self.assertNotIn("secret", snapshot["rows"][0])
        self.assertTrue(snapshot["snapshot_fingerprint"])

    def test_passive_execution_reads_do_not_create_a_database_or_schema(self) -> None:
        absent = self.root / "absent" / "phase9f-f-read-only.db"
        original = tailoring_version_manager.DB_PATH
        tailoring_version_manager.DB_PATH = absent
        try:
            self.assertIsNone(execution_manager.get_phase9f_tailoring_execution(1))
            self.assertEqual(execution_manager.list_phase9f_tailoring_execution_events(1), [])
            self.assertFalse(absent.exists())
        finally:
            tailoring_version_manager.DB_PATH = original

    def test_minor_and_full_use_only_the_positive_phase9a_subset(self) -> None:
        exact_jd = make_exact_jd()
        profile = resume_profile(strong=False, marker="phase9f-f-scope")
        requirements = exact_jd["canonicalisation"]["requirements"]
        keyword_match = build_phase9e_keyword_match(
            requirements=copy.deepcopy(requirements),
            acronym_map=copy.deepcopy(
                exact_jd["canonicalisation"].get("acronym_map") or {}
            ),
            resume_profile=copy.deepcopy(profile),
            raw_resume_text=resume_text(profile),
        )
        stable = build_stable_analysis(
            jd_profile=copy.deepcopy(JD_PROFILE),
            keyword_match=copy.deepcopy(keyword_match),
            raw_jd_text=JD_TEXT,
            raw_resume_text=resume_text(profile),
            resume_profile=copy.deepcopy(profile),
            retrieval_mode_override="lexical",
        )
        baseline = {
            "resume_profile": profile,
            "raw_resume_text": resume_text(profile),
            "jd_profile": copy.deepcopy(JD_PROFILE),
            "raw_jd_text": JD_TEXT,
            "keyword_match": keyword_match,
            "stable_analysis": stable,
            "bullets": {},
            "structure": {},
        }
        snapshot = build_frozen_evidence_snapshot(
            [
                {
                    "id": 1,
                    "category": "Project",
                    "title": "Truthful full-stack evidence",
                    "description": (
                        "Built React applications with Python backend APIs, "
                        "PostgreSQL database design, authentication workflows, "
                        "PostgREST, Row-Level Security, and secure database access."
                    ),
                    "period": "2026",
                    "skills": ["React", "PostgreSQL"],
                    "tools": ["PostgREST"],
                    "impact": "Verified test evidence",
                    "source_type": "manual",
                    "created_at": "2026-08-18T00:00:00",
                    "updated_at": "2026-08-18T00:00:00",
                },
                {
                    "id": 2,
                    "category": "Project",
                    "title": "Unrelated evidence",
                    "description": "Organised a community book exchange.",
                    "period": "2026",
                    "skills": ["Coordination"],
                    "tools": [],
                    "impact": "Verified test evidence",
                    "source_type": "manual",
                    "created_at": "2026-08-18T00:00:00",
                    "updated_at": "2026-08-18T00:00:00",
                },
            ]
        )
        minor = build_section_scope(
            application_id=1,
            baseline_report=baseline,
            evidence_snapshot=snapshot,
            confirmed_intensity="minor",
        )
        full = build_section_scope(
            application_id=1,
            baseline_report=baseline,
            evidence_snapshot=snapshot,
            confirmed_intensity="full",
        )
        self.assertEqual(minor["selected_evidence_ids"], [1])
        self.assertEqual(full["selected_evidence_ids"], [1])
        self.assertLess(len(full["selected_evidence"]), len(snapshot["rows"]))
        self.assertTrue(minor["projects_addressable"])
        self.assertTrue(full["skills_addressable"])

    def test_no_addressable_scope_is_durable_block_before_any_model_or_draft(self) -> None:
        state = self._session("full")
        app_id = state["application_id"]
        execution = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
            application_id=app_id
        )["execution"]
        self.assertEqual(execution["status"], "blocked")
        self.assertEqual(execution["current_stage"], "no_addressable_changes")
        self.assertEqual(execution["terminal_reason"], "no_addressable_changes")
        self.assertEqual(self._count("phase9f_tailoring_executions", app_id), 1)
        self.assertEqual(self._count("application_tailoring_versions", app_id), 0)
        repeated = execution_manager.execute_phase9f_tailoring(application_id=app_id)
        self.assertEqual(repeated["execution"]["execution_id"], execution["execution_id"])
        self.assertEqual(self._count("phase9f_tailoring_executions", app_id), 1)

    def test_normal_stage_adapters_prepare_then_sections_then_fit_without_bypass(self) -> None:
        """F exposes durable work to normal stages instead of auto-fitting it."""
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        fit_calls: list[dict] = []
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
            self.assertEqual(prepared["status"], "preparing")
            self.assertEqual(project_calls, [])
            self.assertEqual(self._count("application_tailoring_versions", application_id), 0)

            sections = execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
            )
            self.assertEqual(sections["execution"]["current_stage"], "build_fit_pending")
            self.assertEqual(len(project_calls), 1)
            self.assertEqual(self._count("application_tailoring_versions", application_id), 0)

            fitted = execution_manager.run_phase9f_tailoring_fit(
                application_id=application_id,
                fit_writer=self._fit_writer(fit_calls),
            )
        self.assertEqual(fitted["execution"]["status"], "waiting_for_approval")
        self.assertEqual(len(fit_calls), 1)
        self.assertEqual(self._count("application_tailoring_versions", application_id), 1)

    def test_normal_lifecycle_creates_a_b_and_reuses_exact_a(self) -> None:
        """Fresh F contexts delegate each distinct request to normal drafts."""
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        skills_calls: list[dict] = []

        def skills_writer(**kwargs):
            skills_calls.append(copy.deepcopy(kwargs))
            return self._skills_writer(**kwargs)

        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
            self.assertEqual(prepared["generation_id"], "")
            first = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=skills_writer,
                generation_settings={
                    "max_projects": 4,
                    "max_bullets": 4,
                    "bullet_allocation_mode": "all_canonical_before_fitting",
                },
                generation_model="model-a",
            )
            # Live evidence changes after initialization must not enter B.
            self._add_evidence(1)
            second = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=skills_writer,
                generation_settings={
                    "max_projects": 3,
                    "max_bullets": 3,
                    "bullet_allocation_mode": "adaptive",
                },
                generation_model="model-b",
            )
            exact = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=skills_writer,
                generation_settings={
                    "max_projects": 4,
                    "max_bullets": 4,
                    "bullet_allocation_mode": "all_canonical_before_fitting",
                },
                generation_model="model-a",
            )

        self.assertNotEqual(
            first["generation"]["generation_id"],
            second["generation"]["generation_id"],
        )
        self.assertEqual(
            exact["cache_status"], "exact_normal_generation_reused"
        )
        self.assertEqual(
            exact["generation"]["generation_id"],
            first["generation"]["generation_id"],
        )
        self.assertEqual(len(project_calls), 2)
        self.assertEqual(len(skills_calls), 2)
        self.assertEqual(len(project_calls[1]["evidence_items"]), 1)
        self.assertEqual(self._count("application_tailoring_versions", application_id), 2)

    def test_normal_full_generation_uses_complete_frozen_evidence_pool(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(2)
        project_calls: list[dict] = []
        settings = {
            "max_projects": 3,
            "max_bullets": 3,
            "bullet_allocation_mode": "adaptive",
        }
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
            self.assertEqual(len(prepared["evidence_snapshot"]["rows"]), 2)
            self.assertEqual(len(prepared["section_scope"]["selected_evidence"]), 1)

            # Live Evidence Library changes after F preparation must not alter
            # the Full generation pool.
            user_profile_manager.delete_evidence_item(2)
            generated = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings=settings,
                generation_model="model-a",
            )
            exact = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings=settings,
                generation_model="model-a",
            )

        self.assertEqual(len(project_calls), 1)
        self.assertEqual(
            [row["id"] for row in project_calls[0]["evidence_items"]],
            [1, 2],
        )
        lifecycle = generated["generation"]["generation_settings"][
            "phase9f_f_normal_lifecycle"
        ]
        self.assertEqual(
            lifecycle["evidence_pool"]["policy_version"],
            execution_manager.PHASE9F_F_NORMAL_EVIDENCE_POOL_POLICY_VERSION,
        )
        self.assertEqual(
            lifecycle["evidence_pool"]["mode"],
            "complete_frozen_snapshot",
        )
        self.assertEqual(lifecycle["evidence_pool"]["row_ids"], [1, 2])
        self.assertEqual(exact["cache_status"], "exact_normal_generation_reused")
        self.assertEqual(
            exact["generation"]["generation_id"],
            generated["generation"]["generation_id"],
        )

    def test_normal_minor_generation_keeps_phase9a_selected_evidence_pool(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(2)
        project_calls: list[dict] = []
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            generated = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_model="model-a",
            )

        self.assertEqual(len(project_calls), 1)
        self.assertEqual(
            [row["id"] for row in project_calls[0]["evidence_items"]],
            [1],
        )
        lifecycle = generated["generation"]["generation_settings"][
            "phase9f_f_normal_lifecycle"
        ]
        self.assertEqual(
            lifecycle["evidence_pool"]["policy_version"],
            execution_manager.PHASE9F_F_NORMAL_EVIDENCE_POOL_POLICY_VERSION,
        )
        self.assertEqual(
            lifecycle["evidence_pool"]["mode"],
            "phase9a_selected_evidence",
        )
        self.assertEqual(lifecycle["evidence_pool"]["row_ids"], [1])

    def test_normal_lifecycle_resumes_uncertain_skills_without_repeating_projects(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        skills_calls: list[dict] = []

        def uncertain_skills(**kwargs):
            skills_calls.append(copy.deepcopy(kwargs))
            raise RuntimeError("simulated provider disconnect")

        settings = {
            "max_projects": 3,
            "max_bullets": 3,
            "bullet_allocation_mode": "adaptive",
        }
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            with self.assertRaisesRegex(RuntimeError, "provider disconnect"):
                execution_manager.run_phase9f_normal_generation(
                    application_id=application_id,
                    projects_writer=self._projects_writer(project_calls),
                    skills_writer=uncertain_skills,
                    generation_settings=settings,
                    generation_model="model-a",
                )
            incomplete = [
                item
                for item in execution_manager.list_tailoring_generations(application_id)
                if (item.get("generation_settings") or {}).get(
                    "phase9f_f_normal_lifecycle", {}
                ).get("generation_status") == "incomplete"
            ]
            self.assertEqual(len(incomplete), 1)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                approve_tailoring_generation(
                    application_id,
                    incomplete[0]["generation_id"],
                )
            with self.assertRaisesRegex(Phase9FFExecutionError, "must complete"):
                execution_manager.run_phase9f_normal_fit(
                    application_id=application_id,
                    generation_id=incomplete[0]["generation_id"],
                    fit_writer=self._fit_writer([]),
                )
            with self.assertRaisesRegex(Phase9FFExecutionError, "Explicit acknowledgement"):
                execution_manager.run_phase9f_normal_generation(
                    application_id=application_id,
                    projects_writer=self._projects_writer(project_calls),
                    skills_writer=self._skills_writer,
                    generation_settings=settings,
                    generation_model="model-a",
                )
            completed = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings=settings,
                generation_model="model-a",
                acknowledge_uncertain_model_retry=True,
            )
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(skills_calls), 1)
        self.assertEqual(completed["generation"]["generation_id"], incomplete[0]["generation_id"])

    def test_normal_fit_clones_a_durable_fit_without_paid_generation(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        fit_calls: list[dict] = []
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            generated = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_model="model-a",
            )
            fit_a = execution_manager.run_phase9f_normal_fit(
                application_id=application_id,
                generation_id=generated["generation"]["generation_id"],
                fit_writer=self._fit_writer(fit_calls),
                fit_settings={"page_density_mode": "balanced"},
            )
            fit_b = execution_manager.run_phase9f_normal_fit(
                application_id=application_id,
                generation_id=fit_a["generation"]["generation_id"],
                fit_writer=self._fit_writer(fit_calls),
                fit_settings={"page_density_mode": "maximize"},
            )
        self.assertNotEqual(
            fit_a["generation"]["generation_id"],
            fit_b["generation"]["generation_id"],
        )
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(fit_calls), 2)

    def test_normal_phase8_requires_and_reconciles_the_selected_approved_generation(self) -> None:
        """F provenance validates the normal approved winner, never a first draft."""
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        fit_calls: list[dict] = []
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            first = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings={"max_projects": 4},
                generation_model="model-a",
            )
            second = execution_manager.run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings={"max_projects": 3},
                generation_model="model-b",
            )
            fitted = execution_manager.run_phase9f_normal_fit(
                application_id=application_id,
                generation_id=second["generation"]["generation_id"],
                fit_writer=self._fit_writer(fit_calls),
            )
            with self.assertRaisesRegex(Phase9FFExecutionError, "exact approved"):
                execution_manager.run_or_reuse_phase9f_normal_generation_phase8(
                    application_id=application_id,
                    generation_id=fitted["generation"]["generation_id"],
                )
            approve_tailoring_generation(
                application_id,
                fitted["generation"]["generation_id"],
            )
            baseline = execution_manager._prepare_frozen_phase8_context(
                execution_manager.get_phase9f_tailoring_execution(application_id)
            )["baseline_report"]
            expected = self._valid_phase8_result(
                application_id=application_id,
                generation_id=fitted["generation"]["generation_id"],
                baseline=baseline,
            )
            with patch.object(
                execution_manager,
                "build_phase8_verification",
                return_value=expected,
            ):
                completed = (
                    execution_manager.run_or_reuse_phase9f_normal_generation_phase8(
                        application_id=application_id,
                        generation_id=fitted["generation"]["generation_id"],
                    )
                )
        self.assertNotEqual(
            first["generation"]["generation_id"],
            fitted["generation"]["generation_id"],
        )
        self.assertEqual(completed["execution"]["status"], "completed")
        self.assertEqual(
            completed["execution"]["generation_id"],
            fitted["generation"]["generation_id"],
        )
        self.assertEqual(len(project_calls), 2)
        self.assertEqual(len(fit_calls), 1)

    def test_prepared_f_execution_reopens_the_normal_current_scope(self) -> None:
        """Preparation enables normal stage routing without creating a draft."""
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
        context = resolve_current_phase9e_generation_context(application_id)
        self.assertEqual(prepared["status"], "preparing")
        self.assertEqual(context["status"], "current")
        self.assertTrue(context["can_generate"])
        self.assertEqual(
            context["phase9f_f_execution"]["execution_id"],
            prepared["execution_id"],
        )
        self.assertEqual(self._count("application_tailoring_versions", application_id), 0)

    def _assert_begin_only_prepares_the_durable_scope(self, intensity: str) -> None:
        """The initial normal-flow action is deterministic and model-free."""
        state = self._session(intensity)
        application_id = state["application_id"]
        self._add_evidence(1)
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
        self.assertEqual(prepared["status"], "preparing")
        self.assertEqual(prepared["current_stage"], "source_preparation")
        self.assertEqual(
            prepared["stage_outputs"],
            {
                "policy_version": execution_manager.PHASE9F_F_STAGE_OUTPUT_POLICY_VERSION,
                "normal_lifecycle_adapter_version": (
                    execution_manager.PHASE9F_F_NORMAL_LIFECYCLE_VERSION
                ),
            },
        )
        self.assertEqual(
            self._count("application_tailoring_versions", application_id),
            0,
        )

    def test_begin_minor_only_prepares_the_durable_scope(self) -> None:
        self._assert_begin_only_prepares_the_durable_scope("minor")

    def test_begin_full_only_prepares_the_durable_scope(self) -> None:
        self._assert_begin_only_prepares_the_durable_scope("full")

    def _assert_base_f_ledger(self, intensity: str) -> None:
        state = self._session(intensity, source_type="base_resume")
        execution = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
            application_id=state["application_id"]
        )["execution"]
        self.assertEqual(execution["source_type"], "base_resume")
        self.assertEqual(execution["confirmed_intensity"], intensity)
        self.assertEqual(execution["status"], "blocked")

    def test_base_minor_remains_in_the_f_ledger_not_reuse(self) -> None:
        self._assert_base_f_ledger("minor")

    def test_base_full_remains_in_the_f_ledger_not_reuse(self) -> None:
        self._assert_base_f_ledger("full")

    def test_removed_blueprint_remains_usable_for_historical_f_preparation(self) -> None:
        state = self._session("full")
        blueprint = state["blueprint"]
        remove_global_blueprint_from_reuse(
            blueprint_id=blueprint["blueprint_id"],
            blueprint_fingerprint=blueprint["blueprint_fingerprint"],
            acknowledged=True,
            reason="Focused Phase 9F-F historical source test.",
        )
        execution = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
            application_id=state["application_id"]
        )["execution"]
        self.assertEqual(execution["source_type"], "global_blueprint")
        self.assertEqual(execution["status"], "blocked")

    def test_missing_exact_docx_fails_before_any_paid_stage(self) -> None:
        state = self._session("minor")
        app_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=Phase9FFExecutionError(
                "Synthetic source DOCX is unavailable.",
                code="source_docx_missing",
                stage="source_preparation",
            ),
        ):
            with self.assertRaisesRegex(Phase9FFExecutionError, "DOCX") as raised:
                execution_manager.execute_phase9f_tailoring(
                    application_id=app_id,
                    projects_writer=self._projects_writer(project_calls),
                )
        self.assertEqual(raised.exception.code, "source_docx_missing")
        self.assertEqual(project_calls, [])
        self.assertEqual(self._count("application_tailoring_versions", app_id), 0)

    def test_private_stage_retry_materialises_one_changed_draft_and_preserves_frozen_source(self) -> None:
        state = self._session("minor")
        app_id = state["application_id"]
        self._add_evidence()
        decision_before = copy.deepcopy(get_current_application_blueprint_decision(app_id))
        project_calls: list[dict] = []
        fit_calls: list[dict] = []

        def failing_skills(**kwargs):
            raise RuntimeError("synthetic skills failure")

        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            return_value=self._source_bundle(),
        ):
            first = execution_manager.execute_phase9f_tailoring(
                application_id=app_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=failing_skills,
                fit_writer=self._fit_writer(fit_calls),
            )
            self.assertEqual(first["execution"]["status"], "failed")
            self.assertEqual(len(project_calls), 1)
            self.assertEqual(len(project_calls[0]["evidence_items"]), 1)
            self.assertEqual(self._count("application_tailoring_versions", app_id), 0)
            self.assertEqual(
                first["execution"]["stage_outputs"]["projects"]["status"],
                "completed",
            )
            user_profile_manager.delete_evidence_item(1)

            second = execution_manager.execute_phase9f_tailoring(
                application_id=app_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                fit_writer=self._fit_writer(fit_calls),
                acknowledge_uncertain_model_retry=True,
            )

        execution = second["execution"]
        self.assertEqual(execution["status"], "waiting_for_approval")
        self.assertEqual(len(project_calls), 1, "durable project stage must be reused")
        self.assertEqual(len(fit_calls), 1)
        self.assertEqual(self._count("application_tailoring_versions", app_id), 1)
        self.assertEqual(execution["attempt_count"], 2)
        self.assertEqual(
            get_current_application_blueprint_decision(app_id), decision_before
        )
        frozen_profile = decision_before["starting_snapshot"]["resume_profile_snapshot"]
        self.assertEqual(
            frozen_profile["education"],
            get_current_application_blueprint_decision(app_id)["starting_snapshot"][
                "resume_profile_snapshot"
            ]["education"],
        )
        self.assertEqual(
            frozen_profile["experience"],
            get_current_application_blueprint_decision(app_id)["starting_snapshot"][
                "resume_profile_snapshot"
            ]["experience"],
        )
        generation = execution_manager.get_tailoring_generation(
            app_id, execution["generation_id"]
        )
        self.assertTrue(generation["content_changed"])
        self.assertEqual(
            generation["generation_settings"]["phase9f_f_execution_fingerprint"],
            execution["execution_fingerprint"],
        )

        repeated = execution_manager.execute_phase9f_tailoring(application_id=app_id)
        self.assertEqual(repeated["execution"]["generation_id"], execution["generation_id"])
        self.assertEqual(self._count("application_tailoring_versions", app_id), 1)

    def test_phase8_waits_for_existing_approval_and_never_repeats_writers(self) -> None:
        state = self._session("minor")
        app_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        fit_calls: list[dict] = []
        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            return_value=self._source_bundle(),
        ):
            created = execution_manager.execute_phase9f_tailoring(
                application_id=app_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                fit_writer=self._fit_writer(fit_calls),
            )
            with self.assertRaisesRegex(ValueError, "approved"):
                execution_manager.run_or_reuse_phase9f_tailoring_phase8(
                    application_id=app_id
                )
            approve_tailoring_generation(app_id, created["execution"]["generation_id"])
            execution_manager.reconcile_phase9f_tailoring_approval(application_id=app_id)
            baseline = execution_manager._prepare_frozen_phase8_context(
                execution_manager.get_phase9f_tailoring_execution(app_id)
            )["baseline_report"]
            phase8_result = self._valid_phase8_result(
                application_id=app_id,
                generation_id=created["execution"]["generation_id"],
                baseline=baseline,
            )
            with patch.object(
                execution_manager,
                "build_phase8_verification",
                return_value=phase8_result,
            ):
                completed = execution_manager.run_or_reuse_phase9f_tailoring_phase8(
                    application_id=app_id
                )
        self.assertEqual(completed["execution"]["status"], "completed")
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(fit_calls), 1)
        self.assertEqual(
            completed["execution"]["phase8_verification_fingerprint"], "f" * 64
        )

    def test_phase8_invalid_or_stale_results_are_retryable_without_repeating_f_stages(self) -> None:
        execution, project_calls, fit_calls = self._create_waiting_for_phase8()
        application_id = execution["application_id"]
        baseline = execution_manager._prepare_frozen_phase8_context(execution)[
            "baseline_report"
        ]
        invalid = self._valid_phase8_result(
            application_id=application_id,
            generation_id=execution["generation_id"],
            baseline=baseline,
        )
        invalid["comparison_valid"] = False
        invalid["blueprint_ready"] = False
        invalid["verdict"] = "invalid_canonical_mismatch"
        with patch.object(
            execution_manager,
            "build_phase8_verification",
            return_value=invalid,
        ):
            rejected = execution_manager.run_or_reuse_phase9f_tailoring_phase8(
                application_id=application_id
            )
        self.assertEqual(rejected["execution"]["status"], "waiting_for_phase8")
        self.assertEqual(
            rejected["execution"]["current_stage"], "phase8_verification_invalid"
        )
        self.assertIn("verification_canonical_scope_invalid", rejected["issues"])
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(fit_calls), 1)

        valid = self._valid_phase8_result(
            application_id=application_id,
            generation_id=execution["generation_id"],
            baseline=baseline,
        )
        user_profile_manager.delete_evidence_item(1)
        # This asserts that Phase 8 reconciliation never re-reads the live
        # Evidence Library after preparation froze the F evidence snapshot.
        with patch.object(
            execution_manager,
            "get_all_evidence_items_for_snapshot",
            side_effect=AssertionError("live Evidence Library must not be read"),
        ), patch.object(
            execution_manager,
            "build_phase8_verification",
            return_value=valid,
        ):
            completed = execution_manager.run_or_reuse_phase9f_tailoring_phase8(
                application_id=application_id
            )
        self.assertEqual(completed["execution"]["status"], "completed")
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(fit_calls), 1)

    def test_phase8_mismatched_saved_result_does_not_complete(self) -> None:
        execution, _project_calls, _fit_calls = self._create_waiting_for_phase8()
        baseline = execution_manager._prepare_frozen_phase8_context(execution)[
            "baseline_report"
        ]
        expected = self._valid_phase8_result(
            application_id=execution["application_id"],
            generation_id=execution["generation_id"],
            baseline=baseline,
        )
        stale = copy.deepcopy(expected)
        stale["verification_fingerprint"] = "0" * 64
        stale["generation_id"] = "another-generation"
        stale["verification_id"] = "stale-verification"
        with patch.object(
            execution_manager,
            "build_phase8_verification",
            return_value=expected,
        ), patch.object(
            execution_manager,
            "save_tailoring_verification",
            return_value=stale,
        ):
            rejected = execution_manager.run_or_reuse_phase9f_tailoring_phase8(
                application_id=execution["application_id"]
            )
        self.assertEqual(rejected["execution"]["status"], "waiting_for_phase8")
        self.assertIn("verification_fingerprint_mismatch", rejected["issues"])
        self.assertIn("verification_generation_mismatch", rejected["issues"])

    def test_source_docx_change_before_fit_fails_closed_then_resumes_without_models(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        source_docx = self.root / "source.docx"
        original_bytes = b"phase9f-f-source-docx"
        source_docx.write_bytes(original_bytes)
        project_calls: list[dict] = []
        skill_calls: list[dict] = []
        fit_calls: list[dict] = []

        def changing_skills(**kwargs):
            skill_calls.append(copy.deepcopy(kwargs))
            source_docx.write_bytes(b"tampered-after-model-stage")
            return self._skills_writer(**kwargs)

        def asserting_fit(**kwargs):
            fit_calls.append(copy.deepcopy(kwargs))
            self.assertEqual(
                Path(kwargs["saved_resume_docx_path"]).read_bytes(), original_bytes
            )
            return self._fit_writer([])(**kwargs)

        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            first = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=changing_skills,
                fit_writer=asserting_fit,
            )
            self.assertEqual(first["execution"]["status"], "failed")
            self.assertEqual(
                first["execution"]["last_error_code"], "source_docx_identity_mismatch"
            )
            self.assertEqual(len(project_calls), 1)
            self.assertEqual(len(skill_calls), 1)
            self.assertEqual(fit_calls, [])
            source_docx.write_bytes(original_bytes)
            resumed = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=lambda **kwargs: skill_calls.append(kwargs) or self._skills_writer(**kwargs),
                fit_writer=asserting_fit,
            )
        self.assertEqual(resumed["execution"]["status"], "waiting_for_approval")
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(skill_calls), 1)
        self.assertEqual(len(fit_calls), 1)

    def test_fitting_failure_reuses_both_durable_model_stages_on_fit_only_retry(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        skills_calls: list[dict] = []
        fit_calls: list[dict] = []

        def failing_fit(**_kwargs):
            fit_calls.append({"outcome": "failed"})
            raise RuntimeError("synthetic deterministic fitter failure")

        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            failed = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=lambda **kwargs: skills_calls.append(kwargs) or self._skills_writer(**kwargs),
                fit_writer=failing_fit,
            )
            self.assertEqual(failed["execution"]["status"], "failed")
            self.assertEqual(failed["execution"]["current_stage"], "fitting")
            recovered = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=lambda **kwargs: skills_calls.append(kwargs) or self._skills_writer(**kwargs),
                fit_writer=self._fit_writer(fit_calls),
            )
        self.assertEqual(recovered["execution"]["status"], "waiting_for_approval")
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(skills_calls), 1)
        self.assertEqual(len(fit_calls), 2)

    def test_removed_blueprint_executes_from_its_exact_historical_artifact(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        blueprint = state["blueprint"]
        self._add_evidence(1)
        remove_global_blueprint_from_reuse(
            blueprint_id=blueprint["blueprint_id"],
            blueprint_fingerprint=blueprint["blueprint_fingerprint"],
            acknowledged=True,
            reason="Focused Phase 9F-F execution provenance test.",
        )
        frozen_snapshot = copy.deepcopy(
            get_global_blueprint(blueprint["blueprint_id"])["blueprint_snapshot"]
        )
        project_calls: list[dict] = []
        fit_calls: list[dict] = []
        # Only the deterministic Phase 9A scope is controlled.  Exact source
        # resolution is real and must therefore work after lifecycle removal.
        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot):
            result = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                fit_writer=self._fit_writer(fit_calls),
            )
        self.assertEqual(result["execution"]["status"], "waiting_for_approval")
        self.assertEqual(result["execution"]["source_id"], blueprint["blueprint_id"])
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(fit_calls), 1)
        self.assertEqual(
            get_global_blueprint(blueprint["blueprint_id"])["blueprint_snapshot"],
            frozen_snapshot,
        )

    def test_full_execution_uses_selected_positive_scope_and_first_fit_gets_all_generated_bullets(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(2)
        project_calls: list[dict] = []
        fit_payloads: list[dict] = []

        def fit_observer(**kwargs):
            fit_payloads.append(copy.deepcopy(kwargs))
            return self._fit_writer([])(**kwargs)

        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            result = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                fit_writer=fit_observer,
                generation_settings={
                    "max_projects": 3,
                    "max_bullets": 3,
                    "bullet_allocation_mode": "all_canonical_before_fitting",
                },
            )
        self.assertEqual(result["execution"]["status"], "waiting_for_approval")
        self.assertEqual(len(result["execution"]["evidence_snapshot"]["rows"]), 2)
        self.assertEqual(len(project_calls[0]["evidence_items"]), 1)
        self.assertEqual(project_calls[0]["bullet_allocation_mode"], "all_canonical_before_fitting")
        self.assertEqual(len(fit_payloads), 1)
        self.assertEqual(
            fit_payloads[0]["tailored_projects"],
            result["execution"]["stage_outputs"]["projects"]["result"],
        )
        original = get_current_application_blueprint_decision(application_id)[
            "starting_snapshot"]["resume_profile_snapshot"]
        self.assertEqual(
            original["education"],
            get_current_application_blueprint_decision(application_id)[
                "starting_snapshot"]["resume_profile_snapshot"
            ]["education"],
        )
        self.assertEqual(
            original["experience"],
            get_current_application_blueprint_decision(application_id)[
                "starting_snapshot"]["resume_profile_snapshot"
            ]["experience"],
        )

    def test_generation_settings_and_model_bind_at_the_first_paid_stage(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
            self.assertNotIn(
                "projects_model",
                prepared["semantic_identity"]["model_policy"],
            )
            first = execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings={
                    "max_projects": 2,
                    "max_bullets": 4,
                    "bullet_allocation_mode": "adaptive",
                },
                generation_model="selected-at-action-time",
            )
            second = execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings={
                    "max_projects": 8,
                    "max_bullets": 1,
                    "bullet_allocation_mode": "all_canonical_before_fitting",
                },
                generation_model="different-later-model",
            )
        snapshot = first["execution"]["stage_outputs"]["generation_settings"]
        self.assertEqual(snapshot["settings"]["max_projects"], 2)
        self.assertEqual(snapshot["settings"]["max_bullets"], 4)
        self.assertEqual(snapshot["settings"]["bullet_allocation_mode"], "adaptive")
        self.assertEqual(snapshot["model"], "selected-at-action-time")
        self.assertEqual(first["execution"]["stage_outputs"]["projects"]["model"], "selected-at-action-time")
        self.assertEqual(first["execution"]["stage_outputs"]["skills"]["model"], "selected-at-action-time")
        self.assertEqual(project_calls[0]["max_projects"], 2)
        self.assertEqual(project_calls[0]["max_bullets_per_project"], 4)
        self.assertEqual(project_calls[0]["bullet_allocation_mode"], "adaptive")
        self.assertEqual(project_calls[0]["model"], "selected-at-action-time")
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(
            second["execution"]["stage_outputs"]["generation_settings"], snapshot
        )

    def test_legacy_pre_stage_execution_is_reused_without_identity_rewrite(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            created = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
            original_identity = copy.deepcopy(created["semantic_identity"])
            connection = tailoring_version_manager._connect()
            try:
                connection.execute(
                    """
                    UPDATE phase9f_tailoring_executions
                    SET execution_fingerprint=?, identity_policy_version=?
                    WHERE execution_id=?
                    """,
                    (
                        "legacy-pre-stage-execution-fingerprint",
                        "phase9f-tailoring-execution-identity-v2",
                        created["execution_id"],
                    ),
                )
                connection.commit()
            finally:
                connection.close()
            events_before = execution_manager.list_phase9f_tailoring_execution_events(
                application_id
            )
            resumed = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
            self.assertEqual(resumed["cache_status"], "legacy_pre_stage_reused")
            self.assertEqual(
                execution_manager.list_phase9f_tailoring_execution_events(application_id),
                events_before,
            )
            sections = execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=self._projects_writer([]),
                skills_writer=self._skills_writer,
                generation_settings={
                    "max_projects": 2,
                    "max_bullets": 3,
                    "bullet_allocation_mode": "adaptive",
                },
                generation_model="legacy-pre-stage-action-model",
            )
        self.assertEqual(sections["execution"]["status"], "running")
        connection = tailoring_version_manager._connect()
        try:
            row = connection.execute(
                "SELECT semantic_identity_json FROM phase9f_tailoring_executions WHERE application_id=?",
                (application_id,),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(json.loads(row[0]), original_identity)

    def test_fit_settings_are_bound_per_attempt_without_repeating_paid_stages(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        skills_calls: list[dict] = []
        fit_calls: list[dict] = []

        def failing_fit(**kwargs):
            fit_calls.append(copy.deepcopy(kwargs))
            raise RuntimeError("synthetic deterministic fitter failure")

        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=lambda **kwargs: skills_calls.append(copy.deepcopy(kwargs))
                or self._skills_writer(**kwargs),
                generation_settings={
                    "max_projects": 2,
                    "max_bullets": 3,
                    "bullet_allocation_mode": "prefer_available_evidence",
                },
                generation_model="fit-settings-model",
            )
            failed = execution_manager.run_phase9f_tailoring_fit(
                application_id=application_id,
                fit_writer=failing_fit,
                fit_settings={
                    "use_compact_before_delete": True,
                    "prefer_balanced_bullets": True,
                    "allow_skills_compaction": True,
                    "page_density_mode": "none",
                    "allow_margin_compaction": True,
                    "spacing_mode": "blank_line",
                    "add_spacing_before_first_project": True,
                    "blank_lines_between_projects": 2,
                    "blank_lines_after_projects": 3,
                    "project_spacing_pt": 0,
                    "after_projects_spacing_pt": 0,
                },
            )
            recovered = execution_manager.run_phase9f_tailoring_fit(
                application_id=application_id,
                fit_writer=self._fit_writer(fit_calls),
                fit_settings={
                    "use_compact_before_delete": False,
                    "prefer_balanced_bullets": False,
                    "allow_skills_compaction": False,
                    "page_density_mode": "maximize",
                    "allow_margin_compaction": False,
                    "spacing_mode": "paragraph_spacing",
                    "add_spacing_before_first_project": False,
                    "project_spacing_pt": 7,
                    "after_projects_spacing_pt": 8,
                    "blank_lines_between_projects": 0,
                    "blank_lines_after_projects": 0,
                },
            )
        self.assertEqual(failed["execution"]["status"], "failed")
        self.assertEqual(recovered["execution"]["status"], "waiting_for_approval")
        self.assertEqual(len(project_calls), 1)
        self.assertEqual(len(skills_calls), 1)
        self.assertEqual(len(fit_calls), 2)
        self.assertEqual(fit_calls[0]["page_density_mode"], "none")
        self.assertEqual(fit_calls[1]["page_density_mode"], "maximize")
        self.assertEqual(fit_calls[1]["project_spacing_pt"], 7)
        stage_outputs = recovered["execution"]["stage_outputs"]
        self.assertEqual(len(stage_outputs["fitting_attempts"]), 2)
        self.assertNotEqual(
            stage_outputs["fitting_attempts"][0]["input_fingerprint"],
            stage_outputs["fitting_attempts"][1]["input_fingerprint"],
        )
        self.assertEqual(
            stage_outputs["fitting"]["fit_settings"]["settings"]["page_density_mode"],
            "maximize",
        )

    def test_all_canonical_generation_reaches_the_first_fit_without_hidden_rewrite(self) -> None:
        state = self._session("full")
        application_id = state["application_id"]
        self._add_evidence(1)
        fit_calls: list[dict] = []

        def all_canonical_projects(**kwargs):
            return {
                "recommended_projects": [
                    {
                        "title": "Canonical evidence project",
                        "display_title": "Canonical evidence project",
                        "period": "2026",
                        "draft_bullets": [
                            f"Truthful canonical bullet {index}."
                            for index in range(1, 6)
                        ],
                    }
                ],
                "candidate_project_ranking": [],
            }

        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=all_canonical_projects,
                skills_writer=self._skills_writer,
                generation_settings={
                    "max_projects": 2,
                    "max_bullets": 1,
                    "bullet_allocation_mode": "all_canonical_before_fitting",
                },
                generation_model="app96-all-canonical-model",
            )
            execution_manager.run_phase9f_tailoring_fit(
                application_id=application_id,
                fit_writer=self._fit_writer(fit_calls),
            )
        self.assertEqual(len(fit_calls), 1)
        self.assertEqual(
            len(fit_calls[0]["tailored_projects"]["recommended_projects"][0]["draft_bullets"]),
            5,
        )
        self.assertEqual(fit_calls[0]["max_bullets_per_project"], 5)

    def test_non_all_canonical_generation_is_not_silently_converted(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        calls: list[dict] = []
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=self._projects_writer(calls),
                skills_writer=self._skills_writer,
                generation_settings={
                    "max_projects": 1,
                    "max_bullets": 2,
                    "bullet_allocation_mode": "prefer_available_evidence",
                },
                generation_model="normal-allocation-model",
            )
        self.assertEqual(calls[0]["max_projects"], 1)
        self.assertEqual(calls[0]["max_bullets_per_project"], 2)
        self.assertEqual(calls[0]["bullet_allocation_mode"], "prefer_available_evidence")

    def test_debug_summary_is_allowlisted_and_reports_actual_stage_settings(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        fit_calls: list[dict] = []
        with patch.object(
            execution_manager, "build_section_scope", self._scope_from_snapshot
        ), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            execution_manager.run_phase9f_tailoring_projects_skills(
                application_id=application_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
                generation_settings={
                    "max_projects": 2,
                    "max_bullets": 4,
                    "bullet_allocation_mode": "adaptive",
                },
                generation_model="debug-safe-model",
            )
            fitted = execution_manager.run_phase9f_tailoring_fit(
                application_id=application_id,
                fit_writer=self._fit_writer(fit_calls),
                fit_settings={"page_density_mode": "maximize"},
            )
        debug = build_execution_debug_summary(fitted["execution"])
        self.assertEqual(debug["generation_settings"]["settings"]["max_projects"], 2)
        self.assertEqual(debug["generation_settings"]["model"], "debug-safe-model")
        self.assertEqual(debug["projects_stage"]["model"], "debug-safe-model")
        self.assertEqual(
            debug["fitting"]["effective_bullet_allocation_mode"], "adaptive"
        )
        self.assertTrue(debug["fitting"]["successful_fit_settings_fingerprint"])
        self.assertNotIn("evidence_snapshot", debug)
        self.assertNotIn("source_artifact", debug)
        self.assertNotIn("semantic_identity", debug)
        self.assertNotIn("selected_evidence", repr(debug))

    def test_interrupted_projects_and_skills_require_explicit_acknowledgement(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        calls: list[dict] = []
        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                application_id=application_id
            )["execution"]
            prepared, settings_snapshot = (
                execution_manager._freeze_or_reuse_generation_settings(
                    execution=prepared,
                    generation_settings={
                        "max_projects": 2,
                        "max_bullets": 3,
                        "bullet_allocation_mode": "adaptive",
                    },
                    selected_model="focused-test-model",
                    actor_label="Focused test",
                )
            )
            execution_manager._mark_stage_requested(
                execution=prepared,
                stage="projects",
                input_fingerprint="lost-projects-response",
                actor_label="Focused test",
                settings_snapshot=settings_snapshot,
            )
            before_events = execution_manager.list_phase9f_tailoring_execution_events(
                application_id
            )
            passive = execution_manager.get_phase9f_tailoring_execution(application_id)
            self.assertEqual(passive["recovery_state"], "model_attempt_uncertain")
            self.assertEqual(passive["uncertain_stage"], "projects")
            self.assertEqual(
                execution_manager.list_phase9f_tailoring_execution_events(application_id),
                before_events,
            )
            with self.assertRaisesRegex(Phase9FFExecutionError, "Explicit acknowledgement"):
                execution_manager.execute_phase9f_tailoring(application_id=application_id)
            retried_projects = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(calls),
                skills_writer=lambda **kwargs: calls.append(kwargs) or self._skills_writer(**kwargs),
                fit_writer=self._fit_writer([]),
                acknowledge_uncertain_model_retry=True,
            )
            self.assertEqual(retried_projects["execution"]["attempt_count"], 2)

            # A separate durable Skills request without a result receives the
            # same passive uncertainty and acknowledgement treatment.
            prior = execution_manager.get_phase9f_tailoring_execution(application_id)
            outputs = copy.deepcopy(prior["stage_outputs"])
            outputs["skills"] = {
                "status": "requested",
                "input_fingerprint": "lost-skills-response",
                "attempt_number": prior["attempt_count"],
            }
            execution_manager._update_execution(
                execution_id=prior["execution_id"],
                status="running",
                current_stage="skills",
                stage_outputs=outputs,
                event_type="model_stage_requested",
                actor_label="Focused test",
                details={"stage": "skills", "input_fingerprint": "lost-skills-response"},
            )
            passive_skills = execution_manager.get_phase9f_tailoring_execution(
                application_id
            )
            self.assertEqual(passive_skills["recovery_state"], "model_attempt_uncertain")
            self.assertEqual(passive_skills["uncertain_stage"], "skills")
            with self.assertRaisesRegex(Phase9FFExecutionError, "Explicit acknowledgement"):
                execution_manager.execute_phase9f_tailoring(application_id=application_id)
            retried_skills = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=self._projects_writer(calls),
                skills_writer=lambda **kwargs: calls.append(kwargs) or self._skills_writer(**kwargs),
                fit_writer=self._fit_writer([]),
                acknowledge_uncertain_model_retry=True,
            )
        self.assertEqual(retried_skills["execution"]["attempt_count"], 3)
        events = execution_manager.list_phase9f_tailoring_execution_events(application_id)
        self.assertTrue(
            any(
                event["event_type"] == "model_stage_requested"
                and event["attempt_number"] == 1
                for event in events
            )
        )
        self.assertTrue(
            any(
                event["event_type"] == "model_stage_requested"
                and event["attempt_number"] == 2
                for event in events
            )
        )
        self.assertGreaterEqual(len(calls), 2)

    def test_semantically_unchanged_sections_create_no_draft_despite_debug_metadata(self) -> None:
        state = self._session("minor")
        application_id = state["application_id"]
        self._add_evidence(1)
        decision = get_current_application_blueprint_decision(application_id)
        source_sections = execution_manager.materialise_phase9e_starting_sections(
            decision
        )
        projects = copy.deepcopy(source_sections["projects"])
        projects["debug_trace"] = {"non_user_visible": "changed"}
        skills = copy.deepcopy(source_sections["skills"])
        skills["debug_trace"] = {"non_user_visible": "changed"}
        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "resolve_exact_phase9f_d_source",
            side_effect=lambda **_kwargs: self._source_bundle(),
        ):
            result = execution_manager.execute_phase9f_tailoring(
                application_id=application_id,
                projects_writer=lambda **_kwargs: projects,
                skills_writer=lambda **_kwargs: skills,
                fit_writer=self._fit_writer([]),
            )
        self.assertEqual(result["execution"]["status"], "blocked")
        self.assertEqual(result["execution"]["terminal_reason"], "no_semantic_content_change")
        self.assertEqual(self._count("application_tailoring_versions", application_id), 0)

    def test_unrecoverable_model_persistence_requires_explicit_retry_acknowledgement(self) -> None:
        state = self._session("minor")
        app_id = state["application_id"]
        self._add_evidence(1)
        project_calls: list[dict] = []
        with patch.object(execution_manager, "build_section_scope", self._scope_from_snapshot), patch.object(
            execution_manager,
            "_persist_stage_result",
            side_effect=RuntimeError("synthetic persistence outage"),
        ):
            first = execution_manager.execute_phase9f_tailoring(
                application_id=app_id,
                projects_writer=self._projects_writer(project_calls),
                skills_writer=self._skills_writer,
            )
            self.assertEqual(first["execution"]["last_error_code"], "model_response_unrecoverable")
            self.assertEqual(len(project_calls), 1)
            with self.assertRaisesRegex(ValueError, "Explicit acknowledgement"):
                execution_manager.execute_phase9f_tailoring(application_id=app_id)
        self.assertEqual(len(project_calls), 1)


if __name__ == "__main__":
    unittest.main()
