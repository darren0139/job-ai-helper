"""Temporary SQLite fixtures for focused Phase 9F-D tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from database import db_manager, jd_library_manager, tailoring_version_manager
from database.global_blueprint_manager import (
    init_global_blueprint_registry,
    list_active_global_blueprints_read_only,
)
from database.global_master_resume_manager import (
    get_current_global_master_resume,
    get_global_master_resume_artifact,
    init_global_master_resume_registry,
)
from tailoring.phase9f_jd_intake import build_saved_exact_jd_snapshot
from tailoring.phase9f_starting_source_ranking import (
    rank_starting_resume_sources,
)
from tailoring.phase9f_tailoring_intensity import (
    recommend_tailoring_intensity,
)
from tests.test_phase9f_starting_source_ranking import (
    JD_PROFILE,
    JD_TEXT,
    make_base,
    make_blueprint,
    make_exact_jd,
)


def configure_database(path: Path) -> None:
    db_manager.DB_PATH = path
    jd_library_manager.DB_PATH = path
    tailoring_version_manager.DB_PATH = path


def insert_base_resume(
    database_path: Path,
    *,
    strong: bool,
) -> dict[str, Any]:
    configure_database(database_path)
    init_global_master_resume_registry()
    row, artifact = make_base(strong=strong)
    connection = tailoring_version_manager._connect()
    try:
        connection.execute(
            """
            INSERT INTO global_master_resume_versions (
                master_version_id, master_version_fingerprint,
                master_content_fingerprint, format_version,
                content_policy_version, version_policy_version,
                version_number, predecessor_master_version_id,
                predecessor_master_version_fingerprint, artifact_sha256,
                artifact_type, artifact_size_bytes, original_filename,
                media_type, resume_text_sha256, resume_text_char_count,
                resume_text, structured_profile_fingerprint,
                structured_profile_json, semantic_identity_json,
                version_identity_json, extraction_provenance_json,
                master_snapshot_json, display_name, created_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                row["master_version_id"],
                row["master_version_fingerprint"],
                row["master_content_fingerprint"],
                row["format_version"],
                row["content_policy_version"],
                row["version_policy_version"],
                row["version_number"],
                row["artifact_sha256"],
                row["artifact_type"],
                row["artifact_size_bytes"],
                row["original_filename"],
                row["media_type"],
                row["resume_text_sha256"],
                row["resume_text_char_count"],
                row["resume_text"],
                row["structured_profile_fingerprint"],
                json.dumps(row["structured_profile"]),
                json.dumps(row["semantic_identity"]),
                json.dumps(row["version_identity"]),
                json.dumps({"model_call_count": 0}),
                json.dumps(row["master_snapshot"]),
                row["display_name"],
                row["created_at"],
            ),
        )
        connection.execute(
            """
            INSERT INTO global_master_resume_artifacts (
                artifact_id, master_version_id, artifact_kind, media_type,
                filename, sha256, byte_size, authoritative, artifact_bytes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact["artifact_id"],
                artifact["master_version_id"],
                artifact["artifact_kind"],
                artifact["media_type"],
                artifact["filename"],
                artifact["sha256"],
                artifact["byte_size"],
                1,
                artifact["artifact_bytes"],
                artifact["created_at"],
            ),
        )
        connection.execute(
            """
            INSERT INTO global_master_resume_state (
                singleton_id, current_master_version_id,
                current_master_version_fingerprint, updated_at
            ) VALUES (1, ?, ?, ?)
            """,
            (
                row["master_version_id"],
                row["master_version_fingerprint"],
                row["created_at"],
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return row


def insert_blueprint(
    database_path: Path,
    *,
    strong: bool,
    role_family_id: str = "ai_fullstack_software_engineering",
    marker: str = "phase9fd",
) -> dict[str, Any]:
    configure_database(database_path)
    init_global_blueprint_registry()
    row = make_blueprint(
        strong=strong,
        role_family_id=role_family_id,
        role_family_label=(
            "AI & Full-Stack Software Engineering"
            if role_family_id == "ai_fullstack_software_engineering"
            else "Different Role Family"
        ),
        marker=marker,
    )
    evaluation = row["semantic_identity"]["evaluation"]
    connection = tailoring_version_manager._connect()
    try:
        connection.execute(
            """
            INSERT INTO global_blueprint_versions (
                blueprint_id, blueprint_fingerprint, phase9d_version,
                fingerprint_policy_version, role_family_id,
                role_family_label, version_number, status, candidate_id,
                candidate_fingerprint, evaluation_id,
                evaluation_fingerprint, phase9b_version, phase9c_version,
                phase9c_policy_version, evidence_link_version,
                scoring_version, taxonomy_version, semantic_identity_json,
                blueprint_snapshot_json, display_name, notes, created_at,
                activated_at, superseded_at, superseded_by_blueprint_id,
                metadata_updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, '', ?, ?, NULL, NULL, ?
            )
            """,
            (
                row["blueprint_id"],
                row["blueprint_fingerprint"],
                row["phase9d_version"],
                row["fingerprint_policy_version"],
                row["role_family_id"],
                row["role_family_label"],
                row["version_number"],
                row["candidate_id"],
                row["candidate_fingerprint"],
                row["evaluation_id"],
                row["evaluation_fingerprint"],
                row["semantic_identity"]["candidate"]["phase9b_version"],
                evaluation["phase9c_version"],
                evaluation["policy_version"],
                evaluation["evidence_link_version"],
                evaluation["scoring_version"],
                evaluation["taxonomy_version"],
                json.dumps(row["semantic_identity"]),
                json.dumps(row["blueprint_snapshot"]),
                row["display_name"],
                row["created_at"],
                row["created_at"],
                row["created_at"],
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return row


def save_exact_jd(database_path: Path) -> dict[str, Any]:
    configure_database(database_path)
    jd_library_manager.init_jd_library()
    receipt = jd_library_manager.save_job_description_to_library(
        raw_text=JD_TEXT,
        jd_profile=copy.deepcopy(JD_PROFILE),
        title=JD_PROFILE["job_title"],
        company=JD_PROFILE["company"],
        location=JD_PROFILE["location"],
    )
    exact = jd_library_manager.get_exact_job_description_version(
        receipt["job_description_id"],
        receipt["source_version_id"],
    )
    if exact is None:
        raise AssertionError("Synthetic exact JD was not persisted.")
    return build_saved_exact_jd_snapshot(exact)


def build_scope(
    database_path: Path,
    *,
    phase9f_a_snapshot: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    configure_database(database_path)
    exact_jd = phase9f_a_snapshot or make_exact_jd()
    base = get_current_global_master_resume()
    artifact = (
        get_global_master_resume_artifact(base["master_version_id"])
        if base
        else None
    )
    blueprints = list_active_global_blueprints_read_only()
    ranking = rank_starting_resume_sources(
        exact_jd=exact_jd,
        current_base_resume=base,
        current_base_artifact=artifact,
        global_blueprints=blueprints,
    )
    recommendation = recommend_tailoring_intensity(
        ranking,
        expected_ranking_input_fingerprint=ranking[
            "ranking_input_fingerprint"
        ],
    )
    return ranking, recommendation
