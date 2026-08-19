"""Temporary-database and exact-artifact fixtures for Phase 9F-E tests."""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import fitz

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.application_resume_result_manager import (
    init_application_resume_results,
)
from database.global_master_resume_manager import (
    commit_prepared_global_master_resume,
    init_global_master_resume_registry,
)
from database.global_blueprint_manager import init_global_blueprint_registry
from database.phase9f_application_confirmation_manager import (
    confirm_phase9f_application_session,
)
from database.tailoring_generation_control import (
    approve_tailoring_generation,
    get_tailoring_generation,
    record_generation_metadata,
)
from database.tailoring_verification_manager import (
    save_tailoring_verification,
)
from database.tailoring_version_manager import (
    save_application_tailoring_generation,
)
from tailoring.phase8_verification import build_phase8_verification
from tailoring.phase9f_master_resume import (
    build_prepared_master_resume_snapshot,
    inspect_master_resume_upload,
)
from tests.phase9f_d_test_support import (
    build_scope,
    configure_database,
    insert_blueprint,
    save_exact_jd,
)
from tests.test_phase9f_starting_source_ranking import (
    make_exact_jd,
    resume_profile,
    resume_text,
    write_resume_artifacts,
)


def one_page_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    try:
        page = document.new_page(width=612, height=792)
        inserted = page.insert_textbox(
            fitz.Rect(40, 40, 572, 752),
            text,
            fontsize=7,
        )
        if inserted < 0:
            raise AssertionError("The synthetic résumé did not fit one page.")
        return document.tobytes()
    finally:
        document.close()


def insert_authoritative_pdf_base(database_path: Path) -> dict[str, Any]:
    configure_database(database_path)
    init_global_master_resume_registry()
    profile = resume_profile(strong=True, marker="BaseE")
    pdf_bytes = one_page_pdf_bytes(resume_text(profile))
    inspection = inspect_master_resume_upload(
        filename="base-resume.pdf",
        content=pdf_bytes,
    )
    prepared = build_prepared_master_resume_snapshot(
        inspection=inspection,
        structured_profile=profile,
        extraction_provenance={
            "method": "phase9f_e_test_frozen_profile",
            "call_count": 0,
            "embedding_call_count": 0,
        },
        current_master=None,
        preparation_mode="phase9f_e_test",
    )
    return commit_prepared_global_master_resume(
        prepared,
        display_name="Authoritative Base Resume",
        actor_label="Phase 9F-E test",
    )["master"]


def _source_report(candidate: dict[str, Any], exact_jd: dict[str, Any]) -> dict[str, Any]:
    snapshot = candidate["candidate_analysis_snapshot"]
    return {
        "resume_profile": copy.deepcopy(snapshot["resume_profile_snapshot"]),
        "raw_resume_text": str(snapshot["resume_text_snapshot"]),
        "jd_profile": copy.deepcopy(snapshot["jd_profile_snapshot"]),
        "raw_jd_text": str(exact_jd["raw_text"]),
        "keyword_match": copy.deepcopy(snapshot["keyword_match_snapshot"]),
        "stable_analysis": copy.deepcopy(snapshot["stable_analysis_snapshot"]),
        "bullets": {},
        "structure": {},
        "overall_score": int(candidate["deterministic_alignment_score"]),
        "summary": "Phase 9F-E source fixture",
    }


def _sections(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    projects = {
        "recommended_projects": [
            {
                **copy.deepcopy(row),
                "display_title": row.get("title"),
                "period": row.get("date"),
                "draft_bullets": copy.deepcopy(row.get("bullets") or []),
            }
            for row in profile.get("projects", []) or []
        ]
    }
    skills = {
        "skill_lines": [
            {"category": category, "items": copy.deepcopy(values)}
            for category, values in (profile.get("skills") or {}).items()
        ]
    }
    return projects, skills


def make_executable_blueprint(
    database_path: Path,
    *,
    exact_jd: dict[str, Any],
    artifact_root: Path,
) -> dict[str, Any]:
    configure_database(database_path)
    blueprint = insert_blueprint(
        database_path,
        strong=True,
        marker="phase9fe",
    )
    ranking, _ = build_scope(
        database_path,
        phase9f_a_snapshot=exact_jd,
    )
    candidate = next(
        row
        for row in ranking["ranked_candidates"]
        if row["source_type"] == "global_blueprint"
        and row["source_id"] == blueprint["blueprint_id"]
    )
    report = _source_report(candidate, exact_jd)
    connection = db_manager._connect()
    try:
        connection.row_factory = sqlite3.Row
        source_application_id = db_manager.insert_application_session_with_connection(
            connection,
            resume_filename="phase9f-e-source.docx",
            report=report,
            created_at="2026-08-17T00:00:00",
        )
        persisted = jd_library_manager.get_exact_job_description_version(
            int(exact_jd["library_jd_id"]),
            str(exact_jd["source_version_id"]),
        )
        if persisted is None:
            raise AssertionError("The exact source JD fixture is missing.")
        jd_library_manager.link_exact_job_description_with_connection(
            connection,
            application_id=source_application_id,
            persisted_exact_jd=persisted,
            linked_at="2026-08-17T00:00:00",
        )
        connection.commit()
    finally:
        connection.close()

    profile = report["resume_profile"]
    docx_path, pdf_path = write_resume_artifacts(
        artifact_root,
        str(report["raw_resume_text"]),
    )
    generation_id = "phase9f-e-approved-source"
    projects, skills = _sections(profile)
    fit = {
        "generation_id": generation_id,
        "fit_one_page": True,
        "page_count": 1,
        "docx_path": str(docx_path),
        "pdf_path": str(pdf_path),
        "tailored_projects_used": copy.deepcopy(projects),
        "tailored_skills_used": copy.deepcopy(skills),
    }
    save_application_tailoring_generation(
        application_id=source_application_id,
        generation_id=generation_id,
        projects=projects,
        skills=skills,
        fit_result=fit,
        docx_path=docx_path,
        generation_settings={"fixture": "phase9f-e"},
    )
    record_generation_metadata(
        application_id=source_application_id,
        generation_id=generation_id,
        generation_kind="combined",
    )
    approve_tailoring_generation(source_application_id, generation_id)
    generation = get_tailoring_generation(
        source_application_id, generation_id
    )
    phase8 = build_phase8_verification(
        baseline_report=report,
        generation_state=generation,
        raw_jd_text=str(exact_jd["raw_text"]),
    )
    verification = save_tailoring_verification(
        application_id=source_application_id,
        generation_id=generation_id,
        result=phase8,
    )

    blueprint_snapshot = copy.deepcopy(blueprint["blueprint_snapshot"])
    blueprint_snapshot["phase9b_candidate_semantic_snapshot"] = {
        "candidate_id": blueprint["candidate_id"],
        "candidate_fingerprint": blueprint["candidate_fingerprint"],
        "source_application_id": source_application_id,
        "source_generation_id": generation_id,
        "source_verification_id": verification["verification_id"],
        "source_verification_fingerprint": verification[
            "verification_fingerprint"
        ],
        "fit_result": copy.deepcopy(fit),
    }
    connection = tailoring_version_manager._connect()
    try:
        connection.execute(
            """
            UPDATE global_blueprint_versions
            SET blueprint_snapshot_json=? WHERE blueprint_id=?
            """,
            (
                json.dumps(blueprint_snapshot, ensure_ascii=False),
                blueprint["blueprint_id"],
            ),
        )
        connection.commit()
    finally:
        connection.close()

    init_application_resume_results()
    hash_result_id = f"phase9f-e-source-hashes-{blueprint['blueprint_id'][:8]}"
    hash_result_fingerprint = hashlib.sha256(
        hash_result_id.encode("utf-8")
    ).hexdigest()
    connection = tailoring_version_manager._connect()
    try:
        connection.execute(
            """
            INSERT INTO application_resume_results (
                application_result_id, application_id, format_version,
                identity_policy_version, result_fingerprint,
                generation_mode, initial_status, content_changed, editable,
                phase9e_decision_id, phase9e_decision_fingerprint,
                workflow_action, workflow_action_fingerprint, blueprint_id,
                blueprint_fingerprint, blueprint_version,
                starting_snapshot_fingerprint, source_application_id,
                source_generation_id, source_verification_id,
                source_verification_fingerprint, semantic_identity_json,
                result_snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hash_result_id,
                source_application_id,
                "phase9f-e-test-source-hash-record-v1",
                "phase9f-e-test-source-hash-record-identity-v1",
                hash_result_fingerprint,
                "test_approved_source_hash_record",
                "reused_approved",
                "test-decision",
                "test-decision-fingerprint",
                "test-source-hash-record",
                hash_result_fingerprint,
                blueprint["blueprint_id"],
                blueprint["blueprint_fingerprint"],
                int(blueprint["version_number"]),
                "test-starting-snapshot",
                source_application_id,
                generation_id,
                verification["verification_id"],
                verification["verification_fingerprint"],
                "{}",
                "{}",
                "2026-08-17T00:00:00",
            ),
        )
        for kind, path, mime in (
            (
                "docx",
                docx_path,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            ("pdf", pdf_path, "application/pdf"),
        ):
            content = path.read_bytes()
            connection.execute(
                """
                INSERT INTO application_resume_result_artifacts (
                    application_result_id, artifact_kind, artifact_sha256,
                    artifact_size, mime_type, provenance_mode,
                    provenance_label, original_bytes_available,
                    is_original_approved_artifact, source_path,
                    materialized_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?)
                """,
                (
                    hash_result_id,
                    kind,
                    hashlib.sha256(content).hexdigest(),
                    len(content),
                    mime,
                    "test_original_approved_artifact",
                    "Phase 9F-E test authoritative artifact",
                    str(path),
                    str(path),
                    "2026-08-17T00:00:00",
                ),
            )
        connection.commit()
    finally:
        connection.close()
    return {
        **blueprint,
        "blueprint_snapshot": blueprint_snapshot,
        "source_application_id": source_application_id,
        "source_generation_id": generation_id,
        "source_verification": verification,
        "docx_path": docx_path,
        "pdf_path": pdf_path,
    }


def create_d_reuse_session(
    database_path: Path,
    *,
    source_type: str,
    artifact_root: Path,
    confirmed_intensity: str = "reuse",
) -> dict[str, Any]:
    configure_database(database_path)
    db_manager.init_db()
    original_jd = make_exact_jd()
    persisted_jd = save_exact_jd(database_path)
    blueprint = None
    base = None
    if source_type == "global_blueprint":
        base = insert_authoritative_pdf_base(database_path)
        blueprint = make_executable_blueprint(
            database_path,
            exact_jd=persisted_jd,
            artifact_root=artifact_root,
        )
    elif source_type == "base_resume":
        base = insert_authoritative_pdf_base(database_path)
    else:
        raise ValueError("Unsupported Phase 9F-E test source type.")

    init_global_blueprint_registry()
    ranking, recommendation = build_scope(
        database_path,
        phase9f_a_snapshot=original_jd,
    )
    selected = next(
        row
        for row in ranking["ranked_candidates"]
        if row["source_type"] == source_type
    )
    created = confirm_phase9f_application_session(
        phase9f_a_snapshot=original_jd,
        persisted_exact_jd_snapshot=persisted_jd,
        ranking_result=ranking,
        phase9f_c_recommendation=recommendation,
        confirmed_normalized_source_fingerprint=selected[
            "normalized_source_fingerprint"
        ],
        confirmed_intensity=confirmed_intensity,
        application_intent_id=f"phase9f-e-{source_type}",
    )
    return {
        "application_id": created["confirmation"]["application_id"],
        "confirmation": created["confirmation"],
        "ranking": ranking,
        "recommendation": recommendation,
        "blueprint": blueprint,
        "base": base,
        "persisted_jd": persisted_jd,
    }
