"""Read-only provenance resolution for Phase 9F-B Blueprint inspection."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

from database import tailoring_version_manager as base_manager


PHASE9F_B_PROVENANCE_DEBUG_VERSION = (
    "phase9f-blueprint-provenance-debug-v1"
)


class Phase9FBProvenanceError(ValueError):
    """A Blueprint's immutable provenance could not be resolved safely."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _read_only_connection(
    database_path: str | Path | None = None,
) -> sqlite3.Connection:
    path = Path(database_path or base_manager.DB_PATH).resolve()
    if not path.is_file():
        raise Phase9FBProvenanceError(
            "The local provenance database is unavailable."
        )
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _compact_score_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    score = candidate.get("score_summary") or {}
    return {
        "original_resume_score": score.get("original_resume_score"),
        "approved_tailored_score": score.get("approved_tailored_score"),
        "evidence_potential_score": score.get("evidence_potential_score"),
    }


def _source_scope_row(evaluation: dict[str, Any]) -> dict[str, Any]:
    source_rows = [
        row
        for row in evaluation.get("per_jd_results", []) or []
        if isinstance(row, dict) and row.get("is_source_jd") is True
    ]
    if len(source_rows) == 1:
        return source_rows[0]
    selected = [
        row
        for row in evaluation.get("selected_jd_scope", []) or []
        if isinstance(row, dict)
    ]
    return selected[0] if len(selected) == 1 else {}


def _compact_artifact_hash_records(
    connection: sqlite3.Connection,
    *,
    blueprint: dict[str, Any],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    required = {
        "application_resume_results",
        "application_resume_result_artifacts",
    }
    if not all(_table_exists(connection, table) for table in required):
        return []
    rows = connection.execute(
        """
        SELECT
            result.application_result_id,
            result.result_fingerprint,
            artifact.artifact_kind,
            artifact.artifact_sha256,
            artifact.artifact_size,
            artifact.provenance_mode,
            artifact.source_path,
            artifact.materialized_path
        FROM application_resume_results AS result
        JOIN application_resume_result_artifacts AS artifact
          ON artifact.application_result_id = result.application_result_id
        WHERE result.blueprint_id = ?
          AND result.blueprint_fingerprint = ?
          AND result.blueprint_version = ?
          AND result.source_application_id = ?
          AND result.source_generation_id = ?
          AND result.source_verification_id = ?
          AND result.source_verification_fingerprint = ?
          AND artifact.is_original_approved_artifact = 1
          AND artifact.provenance_mode = 'original_approved_artifact'
        ORDER BY result.application_result_id, artifact.artifact_kind
        """,
        (
            _clean(blueprint.get("blueprint_id")),
            _clean(blueprint.get("blueprint_fingerprint")),
            int(blueprint.get("version_number") or 0),
            int(candidate.get("source_application_id") or 0),
            _clean(candidate.get("source_generation_id")),
            _clean(candidate.get("source_verification_id")),
            _clean(candidate.get("source_verification_fingerprint")),
        ),
    ).fetchall()
    return [
        {
            "application_result_id": _clean(row["application_result_id"]),
            "result_fingerprint": _clean(row["result_fingerprint"]),
            "artifact_kind": _clean(row["artifact_kind"]),
            "artifact_sha256": _clean(row["artifact_sha256"]),
            "artifact_size": int(row["artifact_size"]),
            "provenance_mode": _clean(row["provenance_mode"]),
            "source_path": str(row["source_path"] or ""),
            "materialized_path": str(row["materialized_path"] or ""),
        }
        for row in rows
    ]


def load_blueprint_provenance_read_only(
    blueprint: dict[str, Any],
    *,
    database_path: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve one compact immutable chain using SELECT-only SQLite access."""
    if not isinstance(blueprint, dict):
        raise Phase9FBProvenanceError("The selected Blueprint is missing.")
    snapshot = blueprint.get("blueprint_snapshot") or {}
    candidate = snapshot.get("phase9b_candidate_semantic_snapshot") or {}
    evaluation = snapshot.get("phase9c_evaluation_snapshot") or {}
    if not isinstance(candidate, dict) or not isinstance(evaluation, dict):
        raise Phase9FBProvenanceError(
            "The Phase 9D Blueprint snapshot lacks Phase 9B/9C provenance."
        )
    source_application_id = int(candidate.get("source_application_id") or 0)
    source_generation_id = _clean(candidate.get("source_generation_id"))
    source_verification_id = _clean(candidate.get("source_verification_id"))
    source_verification_fingerprint = _clean(
        candidate.get("source_verification_fingerprint")
    )
    if (
        source_application_id <= 0
        or not source_generation_id
        or not source_verification_id
        or not source_verification_fingerprint
    ):
        raise Phase9FBProvenanceError(
            "The Blueprint source Application, generation, or Phase 8 identity "
            "is incomplete."
        )

    missing: list[str] = []
    source_scope = _source_scope_row(evaluation)
    connection = _read_only_connection(database_path)
    try:
        application_row = (
            connection.execute(
                """
                SELECT id, session_name, job_title, company, overall_score,
                       created_at, updated_at
                FROM applications WHERE id = ? LIMIT 1
                """,
                (source_application_id,),
            ).fetchone()
            if _table_exists(connection, "applications")
            else None
        )
        if application_row is None:
            missing.append("source_application")
            source_application: dict[str, Any] = {
                "resolved": False,
                "application_id": source_application_id,
            }
        else:
            source_application = {
                "resolved": True,
                "application_id": int(application_row["id"]),
                "session_name": _clean(application_row["session_name"]),
                "job_title": _clean(application_row["job_title"]),
                "company": _clean(application_row["company"]),
                "historical_application_score": application_row[
                    "overall_score"
                ],
                "created_at": _clean(application_row["created_at"]),
                "updated_at": _clean(application_row["updated_at"]),
            }

        jd_row = None
        jd_tables = {
            "application_job_links",
            "job_descriptions",
            "job_description_versions",
        }
        if all(_table_exists(connection, table) for table in jd_tables):
            jd_rows = connection.execute(
                """
                SELECT
                    link.application_id,
                    link.job_description_id,
                    link.source_version_id,
                    link.linked_at,
                    jd.canonical_jd_id,
                    version.raw_text,
                    version.jd_profile_json,
                    version.created_at AS version_created_at
                FROM application_job_links AS link
                JOIN job_descriptions AS jd
                  ON jd.id = link.job_description_id
                JOIN job_description_versions AS version
                  ON version.job_description_id = link.job_description_id
                 AND version.source_version_id = link.source_version_id
                WHERE link.application_id = ?
                """,
                (source_application_id,),
            ).fetchall()
            if len(jd_rows) == 1:
                jd_row = jd_rows[0]
        if jd_row is None:
            missing.append("source_jd")
            source_jd: dict[str, Any] = {
                "resolved": False,
                "application_id": source_application_id,
            }
        else:
            raw_text = str(jd_row["raw_text"] or "")
            jd_profile = _json_object(jd_row["jd_profile_json"])
            raw_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            expected_raw_sha256 = _clean(source_scope.get("raw_jd_sha256"))
            exact_identity_match = bool(
                _clean(jd_row["source_version_id"])
                == _clean(source_scope.get("source_version_id"))
                and _clean(jd_row["canonical_jd_id"])
                == _clean(source_scope.get("canonical_jd_id"))
                and (not expected_raw_sha256 or raw_sha256 == expected_raw_sha256)
            )
            if not exact_identity_match:
                missing.append("source_jd_identity_match")
            source_jd = {
                "resolved": True,
                "exact_identity_match": exact_identity_match,
                "job_description_id": int(jd_row["job_description_id"]),
                "canonical_jd_id": _clean(jd_row["canonical_jd_id"]),
                "source_version_id": _clean(jd_row["source_version_id"]),
                "raw_jd_sha256": raw_sha256,
                "stable_input_fingerprint": _clean(
                    source_scope.get("stable_input_fingerprint")
                ),
                "canonical_requirement_fingerprint": _clean(
                    source_scope.get("canonical_requirement_fingerprint")
                ),
                "job_title": _clean(
                    jd_profile.get("job_title") or jd_profile.get("title")
                ),
                "company": _clean(
                    jd_profile.get("company")
                    or jd_profile.get("company_name")
                ),
                "linked_at": _clean(jd_row["linked_at"]),
                "version_created_at": _clean(
                    jd_row["version_created_at"]
                ),
            }

        generation_row = None
        generation_tables = {
            "application_tailoring_versions",
            "application_tailoring_generation_meta",
        }
        if all(_table_exists(connection, table) for table in generation_tables):
            generation_row = connection.execute(
                """
                SELECT
                    version.generation_id,
                    version.fit_result_json,
                    version.docx_path,
                    version.pdf_path,
                    version.created_at,
                    version.updated_at,
                    meta.status,
                    meta.approved_at,
                    meta.input_fingerprint,
                    meta.content_fingerprint
                FROM application_tailoring_versions AS version
                LEFT JOIN application_tailoring_generation_meta AS meta
                  ON meta.application_id = version.application_id
                 AND meta.generation_id = version.generation_id
                WHERE version.application_id = ?
                  AND version.generation_id = ?
                LIMIT 1
                """,
                (source_application_id, source_generation_id),
            ).fetchone()
        if generation_row is None:
            missing.append("source_generation")
            source_generation: dict[str, Any] = {
                "resolved": False,
                "application_id": source_application_id,
                "generation_id": source_generation_id,
            }
        else:
            fit_result = _json_object(generation_row["fit_result_json"])
            candidate_fit = candidate.get("fit_result") or {}
            path_identity_match = bool(
                str(generation_row["docx_path"] or "")
                == str(candidate_fit.get("docx_path") or "")
                and str(generation_row["pdf_path"] or "")
                == str(candidate_fit.get("pdf_path") or "")
            )
            fit_identity_match = bool(
                fit_result.get("fit_one_page") is True
                and int(fit_result.get("page_count") or 0) == 1
                and _clean(fit_result.get("generation_id"))
                == _clean(candidate_fit.get("generation_id"))
                and path_identity_match
            )
            approval_resolved = bool(
                _clean(generation_row["status"]) == "approved"
                or _clean(generation_row["approved_at"])
            )
            if not fit_identity_match:
                missing.append("source_fit_identity_match")
            if not approval_resolved:
                missing.append("source_generation_approval")
            source_generation = {
                "resolved": True,
                "approval_resolved": approval_resolved,
                "fit_identity_match": fit_identity_match,
                "application_id": source_application_id,
                "generation_id": _clean(generation_row["generation_id"]),
                "status": _clean(generation_row["status"]),
                "approved_at": _clean(generation_row["approved_at"]),
                "input_fingerprint": _clean(
                    generation_row["input_fingerprint"]
                ),
                "content_fingerprint": _clean(
                    generation_row["content_fingerprint"]
                ),
                "fit_generation_id": _clean(
                    fit_result.get("generation_id")
                ),
                "fit_one_page": fit_result.get("fit_one_page") is True,
                "page_count": fit_result.get("page_count"),
                "docx_path": str(generation_row["docx_path"] or ""),
                "pdf_path": str(generation_row["pdf_path"] or ""),
                "created_at": _clean(generation_row["created_at"]),
                "updated_at": _clean(generation_row["updated_at"]),
            }

        verification_row = None
        if _table_exists(connection, "application_tailoring_verifications"):
            verification_rows = connection.execute(
                """
                SELECT verification_id, generation_id, phase8_version,
                       verification_fingerprint, result_json, created_at
                FROM application_tailoring_verifications
                WHERE application_id = ?
                  AND verification_id = ?
                  AND generation_id = ?
                  AND verification_fingerprint = ?
                """,
                (
                    source_application_id,
                    source_verification_id,
                    source_generation_id,
                    source_verification_fingerprint,
                ),
            ).fetchall()
            if len(verification_rows) == 1:
                verification_row = verification_rows[0]
        if verification_row is None:
            missing.append("phase8_verification")
            phase8_verification: dict[str, Any] = {
                "resolved": False,
                "verification_id": source_verification_id,
                "verification_fingerprint": source_verification_fingerprint,
            }
        else:
            verification = _json_object(verification_row["result_json"])
            blueprint_ready = verification.get("blueprint_ready") is True
            if not blueprint_ready:
                missing.append("phase8_blueprint_ready")
            after = verification.get("after_stable_analysis") or {}
            phase8_verification = {
                "resolved": True,
                "blueprint_ready": blueprint_ready,
                "verification_id": _clean(verification_row["verification_id"]),
                "verification_fingerprint": _clean(
                    verification_row["verification_fingerprint"]
                ),
                "phase8_version": _clean(verification_row["phase8_version"]),
                "generation_id": _clean(verification_row["generation_id"]),
                "final_scoring_seed_fingerprint": _clean(
                    verification.get("final_scoring_seed_fingerprint")
                    or (candidate.get("evaluation_metadata") or {}).get(
                        "source_final_scoring_seed_fingerprint"
                    )
                ),
                "stable_analysis_input_fingerprint": _clean(
                    after.get("input_fingerprint")
                ),
                "historical_approved_score": after.get(
                    "deterministic_alignment_score"
                ),
                "created_at": _clean(verification_row["created_at"]),
            }

        candidate_row = None
        if _table_exists(connection, "global_blueprint_candidates"):
            candidate_row = connection.execute(
                """
                SELECT candidate_id, candidate_fingerprint,
                       source_application_id, source_generation_id,
                       role_family, status, snapshot_json,
                       created_at, updated_at
                FROM global_blueprint_candidates
                WHERE candidate_id = ? LIMIT 1
                """,
                (_clean(blueprint.get("candidate_id")),),
            ).fetchone()
        if candidate_row is None:
            missing.append("phase9b_candidate")
            phase9b_candidate: dict[str, Any] = {
                "resolved": False,
                "candidate_id": _clean(blueprint.get("candidate_id")),
            }
        else:
            stored_candidate = _json_object(candidate_row["snapshot_json"])
            identity_match = bool(
                _clean(candidate_row["candidate_fingerprint"])
                == _clean(blueprint.get("candidate_fingerprint"))
                == _clean(candidate.get("candidate_fingerprint"))
                and int(candidate_row["source_application_id"])
                == source_application_id
                and _clean(candidate_row["source_generation_id"])
                == source_generation_id
            )
            if not identity_match:
                missing.append("phase9b_candidate_identity_match")
            phase9b_candidate = {
                "resolved": True,
                "identity_match": identity_match,
                "candidate_id": _clean(candidate_row["candidate_id"]),
                "candidate_fingerprint": _clean(
                    candidate_row["candidate_fingerprint"]
                ),
                "phase9b_version": _clean(
                    stored_candidate.get("phase9b_version")
                ),
                "status": _clean(candidate_row["status"]),
                "role_family": _clean(candidate_row["role_family"]),
                "source_application_id": int(
                    candidate_row["source_application_id"]
                ),
                "source_generation_id": _clean(
                    candidate_row["source_generation_id"]
                ),
                "score_summary": _compact_score_summary(candidate),
                "created_at": _clean(candidate_row["created_at"]),
                "updated_at": _clean(candidate_row["updated_at"]),
            }

        evaluation_row = None
        if _table_exists(connection, "blueprint_cross_jd_evaluations"):
            evaluation_row = connection.execute(
                """
                SELECT evaluation_id, evaluation_fingerprint, candidate_id,
                       role_family_id, phase9c_version, evaluation_json,
                       created_at
                FROM blueprint_cross_jd_evaluations
                WHERE evaluation_id = ? AND evaluation_fingerprint = ?
                LIMIT 1
                """,
                (
                    _clean(blueprint.get("evaluation_id")),
                    _clean(blueprint.get("evaluation_fingerprint")),
                ),
            ).fetchone()
        if evaluation_row is None:
            missing.append("phase9c_evaluation")
            phase9c_evaluation: dict[str, Any] = {
                "resolved": False,
                "evaluation_id": _clean(blueprint.get("evaluation_id")),
            }
        else:
            stored_evaluation = _json_object(evaluation_row["evaluation_json"])
            identity_match = bool(
                _clean(evaluation_row["candidate_id"])
                == _clean(blueprint.get("candidate_id"))
                and _clean(evaluation_row["role_family_id"])
                == _clean(blueprint.get("role_family_id"))
                and _clean(stored_evaluation.get("evaluation_fingerprint"))
                == _clean(blueprint.get("evaluation_fingerprint"))
            )
            if not identity_match:
                missing.append("phase9c_evaluation_identity_match")
            aggregate = evaluation.get("aggregate_result") or {}
            source_result = _source_scope_row(evaluation)
            phase9c_evaluation = {
                "resolved": True,
                "identity_match": identity_match,
                "evaluation_id": _clean(evaluation_row["evaluation_id"]),
                "evaluation_fingerprint": _clean(
                    evaluation_row["evaluation_fingerprint"]
                ),
                "phase9c_version": _clean(evaluation_row["phase9c_version"]),
                "policy_version": _clean(
                    (evaluation.get("semantic_identity") or {})
                    .get("policy", {})
                    .get("policy_version")
                ),
                "provisional": aggregate.get("provisional") is True,
                "historical_source_score": source_result.get(
                    "deterministic_alignment_score"
                ),
                "historical_mean_score": aggregate.get("mean_score"),
                "created_at": _clean(evaluation_row["created_at"]),
            }

        artifact_hash_records = _compact_artifact_hash_records(
            connection,
            blueprint=blueprint,
            candidate=candidate,
        )
    finally:
        connection.close()

    missing = sorted(set(missing))
    semantic = blueprint.get("semantic_identity") or {}
    resume_identity = semantic.get("resume_snapshot") or {}
    lifecycle_status = _clean(blueprint.get("status"))
    availability_status = (
        _clean(blueprint.get("availability_status")) or "available"
    )
    is_reusable = bool(
        blueprint.get(
            "is_reusable",
            lifecycle_status == "active"
            and availability_status == "available",
        )
    )
    result = {
        "provenance_debug_version": PHASE9F_B_PROVENANCE_DEBUG_VERSION,
        "chain_status": "resolved" if not missing else "incomplete",
        "blueprint_identity": {
            "display_name": _clean(blueprint.get("display_name")),
            "blueprint_id": _clean(blueprint.get("blueprint_id")),
            "blueprint_fingerprint": _clean(
                blueprint.get("blueprint_fingerprint")
            ),
            "version_number": int(blueprint.get("version_number") or 0),
            "status": lifecycle_status,
            "availability_status": availability_status,
            "is_reusable": is_reusable,
            "phase9d_version": _clean(blueprint.get("phase9d_version")),
            "fingerprint_policy_version": _clean(
                blueprint.get("fingerprint_policy_version")
            ),
        },
        "blueprint_role_family": {
            "role_family_id": _clean(blueprint.get("role_family_id")),
            "role_family_label": _clean(blueprint.get("role_family_label")),
        },
        "source_application": source_application,
        "source_jd": source_jd,
        "source_resume_result_or_generation": {
            "source_generation": source_generation,
            "immutable_artifact_hash_records": artifact_hash_records,
        },
        "phase8_verification": phase8_verification,
        "phase9b_candidate": phase9b_candidate,
        "phase9c_evaluation": phase9c_evaluation,
        "phase9d_approval": {
            "blueprint_id": _clean(blueprint.get("blueprint_id")),
            "status": lifecycle_status,
            "availability_status": availability_status,
            "activated_at": _clean(blueprint.get("activated_at")),
            "created_at": _clean(blueprint.get("created_at")),
            "provisional_source": bool(
                (evaluation.get("aggregate_result") or {}).get("provisional")
            ),
        },
        "frozen_resume_snapshot": {
            "complete_snapshot_fingerprint": _clean(
                resume_identity.get("complete_snapshot_fingerprint")
            ),
            "resume_profile_snapshot_fingerprint": _clean(
                resume_identity.get("resume_profile_snapshot_fingerprint")
            ),
            "resume_text_snapshot_sha256": _clean(
                resume_identity.get("resume_text_snapshot_sha256")
            ),
            "fit_generation_id": _clean(
                (candidate.get("fit_result") or {}).get("generation_id")
            ),
            "fit_one_page": (candidate.get("fit_result") or {}).get(
                "fit_one_page"
            )
            is True,
            "page_count": (candidate.get("fit_result") or {}).get(
                "page_count"
            ),
        },
        "fingerprints": {
            "blueprint_fingerprint": _clean(
                blueprint.get("blueprint_fingerprint")
            ),
            "candidate_fingerprint": _clean(
                blueprint.get("candidate_fingerprint")
            ),
            "evaluation_fingerprint": _clean(
                blueprint.get("evaluation_fingerprint")
            ),
            "phase8_verification_fingerprint": (
                source_verification_fingerprint
            ),
            "final_scoring_seed_fingerprint": _clean(
                phase8_verification.get("final_scoring_seed_fingerprint")
            ),
            "source_jd_stable_input_fingerprint": _clean(
                source_jd.get("stable_input_fingerprint")
            ),
        },
        "missing_provenance_links": missing,
        "zero_cost_diagnostics": {
            "model_call_count": 0,
            "embedding_call_count": 0,
            "chroma_read_count": 0,
            "chroma_write_count": 0,
            "persistence_write_count": 0,
        },
    }
    return result


def compact_artifact_resolution(
    resolution: dict[str, Any] | None,
    *,
    error: str = "",
) -> dict[str, Any]:
    """Strip artifact bytes while retaining deterministic safety metadata."""
    if not isinstance(resolution, dict):
        return {
            "status": "unavailable",
            "error": _clean(error),
            "artifacts": [],
        }
    return {
        "status": "verified",
        "source_type": _clean(resolution.get("source_type")),
        "source_id": _clean(resolution.get("source_id")),
        "source_content_fingerprint": _clean(
            resolution.get("source_content_fingerprint")
        ),
        "artifacts": [
            {
                key: deepcopy(row.get(key))
                for key in (
                    "artifact_type",
                    "artifact_kind",
                    "filename",
                    "media_type",
                    "sha256",
                    "byte_size",
                    "provenance_label",
                    "verification_method",
                    "artifact_content_fingerprint",
                    "source_path",
                )
            }
            for row in resolution.get("artifacts", []) or []
            if isinstance(row, dict)
        ],
    }


def build_blueprint_provenance_debug_bundle(
    *,
    ranking_result: dict[str, Any],
    ranked_candidate: dict[str, Any],
    blueprint_provenance: dict[str, Any],
    artifact_resolution: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic, allowlisted, read-only Blueprint debug bundle."""
    exact_jd = (
        (ranking_result.get("semantic_identity") or {}).get("exact_jd") or {}
    )
    return {
        "debug_version": PHASE9F_B_PROVENANCE_DEBUG_VERSION,
        "current_phase9f_b_comparison": {
            "ranking_input_fingerprint": _clean(
                ranking_result.get("ranking_input_fingerprint")
            ),
            "ranking_fingerprint": _clean(
                ranking_result.get("ranking_fingerprint")
            ),
            "current_jd_identity": deepcopy(exact_jd),
            "rank": int(ranked_candidate.get("rank") or 0),
            "current_jd_alignment": int(
                ranked_candidate.get("deterministic_alignment_score") or 0
            ),
            "required_core_coverage": int(
                ranked_candidate.get("required_core_coverage_score") or 0
            ),
            "preferred_coverage": int(
                ranked_candidate.get("preferred_coverage_score") or 0
            ),
            "evidence_strength": int(
                ranked_candidate.get("evidence_strength_score") or 0
            ),
            "comparison_result_fingerprint": _clean(
                ranked_candidate.get("comparison_result_fingerprint")
            ),
            "score_meaning": (
                "Fresh deterministic Phase 9F-B score against the currently "
                "analysed JD."
            ),
        },
        "blueprint_identity": deepcopy(
            blueprint_provenance.get("blueprint_identity") or {}
        ),
        "blueprint_role_family": deepcopy(
            blueprint_provenance.get("blueprint_role_family") or {}
        ),
        "source_application": deepcopy(
            blueprint_provenance.get("source_application") or {}
        ),
        "source_jd": deepcopy(blueprint_provenance.get("source_jd") or {}),
        "source_resume_result_or_generation": deepcopy(
            blueprint_provenance.get("source_resume_result_or_generation")
            or {}
        ),
        "phase8_verification": deepcopy(
            blueprint_provenance.get("phase8_verification") or {}
        ),
        "phase9b_candidate": deepcopy(
            blueprint_provenance.get("phase9b_candidate") or {}
        ),
        "phase9c_evaluation": deepcopy(
            blueprint_provenance.get("phase9c_evaluation") or {}
        ),
        "phase9d_approval": deepcopy(
            blueprint_provenance.get("phase9d_approval") or {}
        ),
        "frozen_resume_snapshot": deepcopy(
            blueprint_provenance.get("frozen_resume_snapshot") or {}
        ),
        "artifact_resolution": deepcopy(artifact_resolution),
        "fingerprints": deepcopy(
            blueprint_provenance.get("fingerprints") or {}
        ),
        "missing_provenance_links": list(
            blueprint_provenance.get("missing_provenance_links") or []
        ),
        "score_labels": {
            "current_jd_alignment": (
                "Fresh deterministic Phase 9F-B score; used for ranking."
            ),
            "historical_blueprint_source_score": (
                "Historical workflow provenance only; never used for the "
                "Phase 9F-B winner."
            ),
        },
        "zero_cost_diagnostics": {
            "model_call_count": 0,
            "embedding_call_count": 0,
            "chroma_read_count": 0,
            "chroma_write_count": 0,
            "persistence_write_count": 0,
        },
    }
