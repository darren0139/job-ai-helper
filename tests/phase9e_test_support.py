"""Temporary SQLite fixtures for Phase 9E tests and smoke checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from database import db_manager
from database import jd_library_manager
from database import tailoring_version_manager
from database.tailoring_generation_control import (
    approve_tailoring_generation,
    record_generation_metadata,
)
from database.tailoring_verification_manager import save_tailoring_verification
from database.tailoring_version_manager import (
    save_application_tailoring_generation,
)
from database.global_blueprint_manager import (
    approve_persisted_phase9c_evaluation,
)
from database.jd_library_manager import init_jd_library
from tests.phase9d_test_support import seed_phase9d_database
from resume_builder.immutable_snapshot_docx import (
    materialise_immutable_snapshot_docx,
)


PROVISIONAL_OVERRIDE = {
    "accepted": True,
    "reason": "Source parity is strong while more target JDs are collected.",
}


def configure_phase9e_test_database(database_path: Path) -> None:
    db_manager.DB_PATH = database_path
    jd_library_manager.DB_PATH = database_path
    tailoring_version_manager.DB_PATH = database_path


def _different_original_profile(
    blueprint_profile: dict[str, Any],
) -> dict[str, Any]:
    profile = copy.deepcopy(blueprint_profile)
    profile["projects"] = [
        {
            "title": "Original Application Project",
            "description": "A deliberately different original project.",
            "bullets": ["Maintained the original application workflow."],
            "technologies": ["OriginalTool"],
        }
    ]
    profile["skills"] = {
        "Programming": ["OriginalSkill"],
        "Tools": ["OriginalTool"],
    }
    return profile


def seed_phase9e_database(
    database_path: Path,
    *,
    different_original: bool = False,
) -> dict[str, Any]:
    configure_phase9e_test_database(database_path)
    state = seed_phase9d_database(
        database_path,
        materialise_jd_text=True,
    )
    configure_phase9e_test_database(database_path)
    db_manager.init_db()

    candidate = state["candidate"]
    blueprint_profile = copy.deepcopy(candidate["resume_profile_snapshot"])
    original_profile = (
        _different_original_profile(blueprint_profile)
        if different_original
        else copy.deepcopy(blueprint_profile)
    )
    source_jd = state["saved_jds"][0]
    report = {
        "resume_profile": original_profile,
        "jd_profile": copy.deepcopy(source_jd["jd_profile"]),
        "raw_jd_text": str(source_jd["raw_text"]),
        "keyword_match": {},
        "stable_analysis": {
            "input_fingerprint": "persisted-application-analysis",
            "scoring_version": "stable-evidence-v1.3-phase6d7",
            "capability_taxonomy_version": "phase6d-capability-taxonomy-v1.2",
        },
        "meta": {
            "analysis_cache": {
                "analysis_id": "analysis-94",
                "input_fingerprint": "analysis-input-94",
            }
        },
    }
    connection = db_manager._connect()
    try:
        connection.execute(
            """
            INSERT INTO applications (
                id, session_name, resume_filename, job_title, company, degree,
                overall_score, summary, report_json, cover_letter,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                94,
                "Phase 9E Application 94",
                "application94.docx",
                source_jd["title"],
                source_jd["company"],
                "",
                92,
                "Fixture",
                json.dumps(report, ensure_ascii=False),
                "",
                "2026-08-04T00:00:00",
                "2026-08-04T00:00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    source_artifact = database_path.parent / "phase9e-source-approved.docx"
    materialise_immutable_snapshot_docx(
        resume_text=str(candidate["resume_text_snapshot"]),
        output_path=source_artifact,
    )
    source_generation_id = str(candidate["source_generation_id"])
    source_fit = {
        "fit_one_page": True,
        "page_count": 1,
        "docx_path": str(source_artifact),
        "fit_policy_version": "phase9e-test-one-page-fit-v1",
    }
    save_application_tailoring_generation(
        application_id=94,
        generation_id=source_generation_id,
        projects={"recommended_projects": copy.deepcopy(
            blueprint_profile.get("projects") or []
        )},
        skills={"skill_lines": copy.deepcopy(
            blueprint_profile.get("skills") or {}
        )},
        fit_result=source_fit,
        docx_path=source_artifact,
        generation_settings={"fixture": "phase9e-authoritative-source"},
    )
    record_generation_metadata(
        application_id=94,
        generation_id=source_generation_id,
        generation_kind="combined",
    )
    approve_tailoring_generation(94, source_generation_id)
    source_verification = save_tailoring_verification(
        application_id=94,
        generation_id=source_generation_id,
        result={
            "generation_id": source_generation_id,
            "verification_fingerprint": str(
                candidate["source_verification_fingerprint"]
            ),
            "phase8_version": "phase8-final-verification-v1",
            "verification_mode": "zero_cost_deterministic",
            "blueprint_ready": True,
            "fit_one_page": True,
            "page_count": 1,
            "model_calls": 0,
            "embedding_calls": 0,
        },
    )

    approval = approve_persisted_phase9c_evaluation(
        evaluation_id=state["provisional_evaluation"]["evaluation_id"],
        evaluation_fingerprint=state["provisional_evaluation"][
            "evaluation_fingerprint"
        ],
        provisional_override=PROVISIONAL_OVERRIDE,
        display_name="AI & Full-Stack — Primary Blueprint",
        notes="Phase 9E fixture",
        actor_label="Phase 9E test",
    )
    init_jd_library()
    report["raw_jd_text"] = str(source_jd["raw_text"])
    connection = db_manager._connect()
    try:
        connection.execute(
            "UPDATE applications SET report_json = ? WHERE id = 94",
            (json.dumps(report, ensure_ascii=False),),
        )
        connection.commit()
    finally:
        connection.close()
    return {
        **state,
        "application_report": report,
        "original_profile": original_profile,
        "blueprint": approval["blueprint"],
        "source_generation_id": source_generation_id,
        "source_artifact_path": source_artifact,
        "source_verification": source_verification,
    }
