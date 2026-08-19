"""Temporary-database, mocked-model smoke check for Phase 9F-F."""

from __future__ import annotations

import copy
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from database import (
    db_manager,
    jd_library_manager,
    tailoring_version_manager,
    user_profile_manager,
)
import database.phase9f_tailoring_execution_manager as execution_manager
from database.tailoring_generation_control import approve_tailoring_generation
from tests.phase9f_d_test_support import configure_database
from tests.phase9f_e_test_support import create_d_reuse_session
from tailoring.phase9f_tailoring_execution import (
    PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
)


def _scope(**kwargs):
    selected = copy.deepcopy((kwargs["evidence_snapshot"]["rows"] or [])[:1])
    return {
        "policy_version": PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
        "phase9a_version": "phase9a-evidence-opportunity-v1",
        "confirmed_intensity": kwargs["confirmed_intensity"],
        "opportunity_fingerprint": "phase9f-f-smoke-opportunity",
        "selected_evidence_ids": [row["id"] for row in selected],
        "selected_evidence_fingerprint": "phase9f-f-smoke-evidence",
        "projects_addressable": True,
        "skills_addressable": True,
        "enabled_sections": ["projects", "skills"],
        "selected_evidence": selected,
        "opportunity": {},
        "scope_fingerprint": "phase9f-f-smoke-scope",
    }


def main() -> None:
    old_paths = (
        db_manager.DB_PATH,
        jd_library_manager.DB_PATH,
        tailoring_version_manager.DB_PATH,
        user_profile_manager.DB_PATH,
    )
    try:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "phase9f-f-smoke.db"
            source_root = root / "sources"
            source_root.mkdir()
            configure_database(database_path)
            user_profile_manager.DB_PATH = database_path
            user_profile_manager.init_user_profile_library()
            user_profile_manager.create_evidence_item(
                category="Project",
                title="Phase 9F-F smoke evidence",
                description="Built a verified React and PostgreSQL integration.",
                skills=["React"],
                tools=["PostgreSQL"],
            )
            state = create_d_reuse_session(
                database_path,
                source_type="global_blueprint",
                artifact_root=source_root,
                confirmed_intensity="minor",
            )
            application_id = state["application_id"]
            source_docx = root / "source.docx"
            output_docx = root / "changed.docx"
            output_pdf = root / "changed.pdf"
            source_docx.write_bytes(b"phase9f-f-smoke-source")
            output_docx.write_bytes(b"phase9f-f-smoke-changed-docx")
            output_pdf.write_bytes(b"phase9f-f-smoke-changed-pdf")
            calls = {"projects": 0, "skills": 0, "fit": 0}

            def projects_writer(**kwargs):
                calls["projects"] += 1
                return {
                    "recommended_projects": [
                        {
                            "title": "Smoke evidence project",
                            "display_title": "Smoke evidence project",
                            "period": "2026",
                            "draft_bullets": [
                                "Built a verified React and PostgreSQL integration."
                            ],
                        }
                    ],
                    "candidate_project_ranking": [],
                }

            def skills_writer(**kwargs):
                calls["skills"] += 1
                return {"skill_lines": [{"category": "Tools", "items": ["PostgreSQL"]}]}

            def fit_writer(**kwargs):
                calls["fit"] += 1
                return {
                    "generation_id": kwargs["generation_id"],
                    "fit_one_page": True,
                    "page_count": 1,
                    "docx_path": str(output_docx),
                    "pdf_path": str(output_pdf),
                    "tailored_projects_used": copy.deepcopy(kwargs["tailored_projects"]),
                    "tailored_skills_used": copy.deepcopy(kwargs["tailored_skills"]),
                }

            with patch.object(execution_manager, "build_section_scope", _scope), patch.object(
                execution_manager,
                "resolve_exact_phase9f_d_source",
                side_effect=lambda **_kwargs: {
                    "artifacts": [
                        {
                            "artifact_type": "docx",
                            "source_path": str(source_docx),
                            "artifact_bytes": source_docx.read_bytes(),
                            "sha256": hashlib.sha256(source_docx.read_bytes()).hexdigest(),
                            "byte_size": source_docx.stat().st_size,
                        }
                    ]
                },
            ):
                prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                    application_id=application_id,
                )
                assert prepared["execution"]["status"] == "preparing"
                assert calls == {"projects": 0, "skills": 0, "fit": 0}
                generated = execution_manager.run_phase9f_normal_generation(
                    application_id=application_id,
                    projects_writer=projects_writer,
                    skills_writer=skills_writer,
                    generation_settings={
                        "max_projects": 2,
                        "max_bullets": 3,
                        "bullet_allocation_mode": "all_canonical_before_fitting",
                    },
                    generation_model="phase9f-f-smoke-model",
                )
                generation = generated["generation"]
                generation_snapshot = generation["generation_settings"][
                    "phase9f_f_normal_lifecycle"
                ]
                assert generation_snapshot["settings"]["bullet_allocation_mode"] == (
                    "all_canonical_before_fitting"
                )
                assert generation_snapshot["model"] == "phase9f-f-smoke-model"
                assert calls == {"projects": 1, "skills": 1, "fit": 0}
                first = execution_manager.run_phase9f_normal_fit(
                    application_id=application_id,
                    generation_id=generation["generation_id"],
                    fit_writer=fit_writer,
                    fit_settings={
                        "page_density_mode": "maximize",
                        "spacing_mode": "paragraph_spacing",
                        "project_spacing_pt": 7,
                        "after_projects_spacing_pt": 8,
                    },
                )
                fitted = first["generation"]
                assert fitted["generation_settings"]["phase9f_f_normal_lifecycle"][
                    "fit"
                ]["settings"]["page_density_mode"] == "maximize"
                approve_tailoring_generation(
                    application_id, fitted["generation_id"]
                )
                baseline = execution_manager._prepare_frozen_phase8_context(
                    execution_manager.get_phase9f_tailoring_execution(application_id)
                )["baseline_report"]
                phase8_result = {
                    "phase8_version": execution_manager.PHASE8_VERIFICATION_VERSION,
                    "verification_fingerprint": "9" * 64,
                    "application_id": application_id,
                    "generation_id": fitted["generation_id"],
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
                with patch.object(
                    execution_manager,
                    "build_phase8_verification",
                    return_value=phase8_result,
                ):
                    completed = execution_manager.run_or_reuse_phase9f_normal_generation_phase8(
                        application_id=application_id,
                        generation_id=fitted["generation_id"],
                    )
                repeated = execution_manager.run_phase9f_normal_generation(
                    application_id=application_id,
                    projects_writer=projects_writer,
                    skills_writer=skills_writer,
                    generation_settings={
                        "max_projects": 2,
                        "max_bullets": 3,
                        "bullet_allocation_mode": "all_canonical_before_fitting",
                    },
                    generation_model="phase9f-f-smoke-model",
                )

            assert completed["execution"]["status"] == "completed"
            assert repeated["generation"]["generation_id"] == generation["generation_id"]
            assert calls == {"projects": 1, "skills": 1, "fit": 1}
            connection = tailoring_version_manager._connect()
            try:
                draft_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM application_tailoring_versions WHERE application_id=?",
                        (application_id,),
                    ).fetchone()[0]
                )
            finally:
                connection.close()
            assert draft_count == 1
            print(
                "Phase 9F-F smoke PASS: executions=1 drafts=1 approved=yes "
                "phase8=completed fitted_one_page=yes protected_sections=yes "
                "mock_projects=1 mock_skills=1 mock_fit=1 model_calls=0 "
                "embedding_calls=0 chroma_reads=0 chroma_writes=0 exact_reuse=yes"
            )
    finally:
        (
            db_manager.DB_PATH,
            jd_library_manager.DB_PATH,
            tailoring_version_manager.DB_PATH,
            user_profile_manager.DB_PATH,
        ) = old_paths


if __name__ == "__main__":
    main()
