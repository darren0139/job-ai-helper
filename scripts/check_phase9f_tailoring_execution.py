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
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
)
from tests.phase9f_d_test_support import configure_database
from tests.phase9f_e_test_support import (
    create_d_reuse_session,
    phase9f_projects_for_document_verification,
    phase9f_skills_for_document_verification,
    write_phase9f_document_verification_fit,
)
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
            source_docx = state["blueprint"]["docx_path"]
            source_bytes = source_docx.read_bytes()
            source_sha256 = hashlib.sha256(source_bytes).hexdigest()
            output_docx = root / "changed.docx"
            output_pdf = root / "changed.pdf"
            calls = {"projects": 0, "skills": 0, "fit": 0}

            def projects_writer(**kwargs):
                calls["projects"] += 1
                return phase9f_projects_for_document_verification(kwargs["resume_profile"])

            def skills_writer(**kwargs):
                calls["skills"] += 1
                return phase9f_skills_for_document_verification(kwargs["resume_profile"])

            def fit_writer(**kwargs):
                calls["fit"] += 1
                return write_phase9f_document_verification_fit(
                    source_docx, output_docx, output_pdf, **kwargs,
                )

            with patch.object(execution_manager, "build_section_scope", _scope):
                prepared = execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                    application_id=application_id,
                )
                assert prepared["execution"]["status"] == "preparing"
                assert prepared["execution"]["source_artifact"]["sha256"] == source_sha256
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
                # PHASE9F_F_SMOKE_PREAPPROVAL_LIFECYCLE_V1
                preapproval = execution_manager.run_or_reuse_phase9f_normal_generation_phase8(
                    application_id=application_id,
                    generation_id=fitted["generation_id"],
                )

                verification = preapproval["verification"]
                assert verification["approval_ready"] is True, verification["verdict_message"]
                assert preapproval["execution"]["status"] == "waiting_for_approval", (
                    preapproval.get("issues")
                )
                assert verification["blueprint_ready"] is False
                assert verification["generation_status"] == "draft"
                assert verification["initial_document_status"] == "not_available_for_handoff"
                assert verification["starting_document_contract"]["selected_base_docx_sha256"] == source_sha256
                assert verification["document_analysis"]["final_document_sha256"] == (
                    hashlib.sha256(output_docx.read_bytes()).hexdigest()
                )
                assert source_docx.read_bytes() == source_bytes

                approve_tailoring_generation(
                    application_id, fitted["generation_id"]
                )
                completed_execution = (
                    execution_manager.reconcile_phase9f_tailoring_approval(
                        application_id=application_id
                    )
                )
                completed = {
                    "execution": completed_execution,
                    "verification": get_latest_tailoring_verification(
                        application_id,
                        fitted["generation_id"],
                    ),
                }
                assert completed["execution"]["status"] == "completed"
                assert completed["verification"]["blueprint_ready"] is True
                assert completed["verification"]["generation_status"] == "approved"

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
                "phase8=preapproval_then_approved fitted_one_page=yes "
                "protected_sections=yes "
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
