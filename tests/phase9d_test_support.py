"""Temporary-database support for Phase 9D tests and smoke checks."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from database import tailoring_version_manager as base_manager
from database.blueprint_candidate_manager import init_blueprint_candidate_registry
from database.blueprint_evaluation_manager import save_or_reuse_blueprint_evaluation
from tailoring.phase9c_blueprint_evaluation import (
    evaluate_blueprint_candidate,
    fingerprint_semantic_identity,
)
from rag.jd_identity import build_job_identity


FIXTURE = Path(__file__).resolve().parents[1] / "ci_fixtures" / (
    "phase9c_application94_acceptance.json"
)


def load_phase9d_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _seed_candidate(candidate: dict[str, Any]) -> None:
    init_blueprint_candidate_registry()
    connection = base_manager._connect()
    try:
        stored = copy.deepcopy(candidate)
        stored.setdefault("status", "candidate")
        stored.setdefault("created_at", "2026-08-04T00:00:00")
        stored.setdefault("updated_at", "2026-08-04T00:00:00")
        connection.execute(
            """
            INSERT INTO global_blueprint_candidates (
                candidate_id,
                candidate_fingerprint,
                source_application_id,
                source_generation_id,
                role_family,
                candidate_name,
                status,
                snapshot_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored["candidate_id"],
                stored["candidate_fingerprint"],
                int(stored["source_application_id"]),
                stored["source_generation_id"],
                stored["role_family"],
                stored.get("candidate_name") or "Application 94 Candidate",
                stored["status"],
                json.dumps(stored, ensure_ascii=False, default=str),
                stored["created_at"],
                stored["updated_at"],
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _seed_jd_library(jds: list[dict[str, Any]]) -> None:
    connection = base_manager._connect()
    try:
        connection.executescript(
            """
            CREATE TABLE job_descriptions (
                id INTEGER PRIMARY KEY,
                application_id INTEGER,
                title TEXT,
                company TEXT,
                location TEXT,
                source_type TEXT,
                source_url TEXT,
                raw_text TEXT,
                jd_profile_json TEXT,
                canonical_jd_id TEXT,
                source_version_id TEXT,
                company_normalized TEXT,
                title_normalized TEXT,
                location_normalized TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE application_job_links (
                application_id INTEGER PRIMARY KEY,
                job_description_id INTEGER NOT NULL,
                source_version_id TEXT NOT NULL,
                linked_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        for jd in jds:
            connection.execute(
                """
                INSERT INTO job_descriptions (
                    id, application_id, title, company, location, source_type,
                    source_url, raw_text, jd_profile_json, canonical_jd_id,
                    source_version_id, first_seen_at, last_seen_at, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(jd["id"]),
                    jd.get("application_id"),
                    jd.get("title"),
                    jd.get("company"),
                    jd.get("location") or "",
                    jd.get("source_type") or "test",
                    jd.get("source_url") or "",
                    jd.get("raw_text") or "",
                    json.dumps(jd.get("jd_profile") or {}, ensure_ascii=False),
                    jd.get("canonical_jd_id") or "",
                    jd.get("source_version_id") or "",
                    "2026-08-04T00:00:00",
                    "2026-08-04T00:00:00",
                    "2026-08-04T00:00:00",
                    "2026-08-04T00:00:00",
                ),
            )
            application_ids = list(jd.get("application_ids") or [])
            if not application_ids and jd.get("application_id") is not None:
                application_ids = [jd["application_id"]]
            for application_id in application_ids:
                connection.execute(
                    """
                    INSERT INTO application_job_links (
                        application_id, job_description_id, source_version_id,
                        linked_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(application_id),
                        int(jd["id"]),
                        jd.get("source_version_id") or "",
                        "2026-08-04T00:00:00",
                        "2026-08-04T00:00:00",
                    ),
                )
        connection.commit()
    finally:
        connection.close()


def seed_phase9d_database(
    database_path: Path,
    *,
    materialise_jd_text: bool = False,
) -> dict[str, Any]:
    base_manager.DB_PATH = database_path
    fixture = load_phase9d_fixture()
    candidate = copy.deepcopy(fixture["candidate"])
    saved_jds = copy.deepcopy(fixture["saved_jds"])
    # Phase 9D approvals now require two immutable source artifact identities.
    # Keep synthetic files beside the temporary SQLite database, never in the
    # repository artifact store.
    artifact_root = database_path.parent / "phase9d-source-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    docx_path = artifact_root / "approved.docx"
    pdf_path = artifact_root / "approved.pdf"
    docx_path.write_bytes(b"synthetic approved DOCX provenance bytes")
    pdf_path.write_bytes(b"%PDF-synthetic approved PDF provenance bytes")
    candidate["fit_result"] = {
        "generation_id": candidate["source_generation_id"],
        "fit_one_page": True,
        "page_count": 1,
        "docx_path": str(docx_path),
        "pdf_path": str(pdf_path),
    }
    if materialise_jd_text:
        for jd in saved_jds:
            # A non-empty neutral raw source lets Phase 9E exercise exact raw
            # identity without changing the fixture's canonical requirements.
            raw_text = "."
            identity = build_job_identity(
                company=str(jd.get("company") or ""),
                title=str(jd.get("title") or ""),
                location=str(jd.get("location") or ""),
                raw_jd_text=raw_text,
            )
            jd["raw_text"] = raw_text
            jd["canonical_jd_id"] = identity.canonical_jd_id
            jd["source_version_id"] = identity.source_version_id
        source = next(
            jd
            for jd in saved_jds
            if int(candidate["source_application_id"])
            in {int(value) for value in jd.get("application_ids", [])}
        )
        candidate["source_jd_identity"] = {
            "canonical_jd_id": source["canonical_jd_id"],
            "source_version_id": source["source_version_id"],
            "raw_jd_sha256": hashlib.sha256(
                str(source["raw_text"]).encode("utf-8")
            ).hexdigest(),
        }
    _seed_candidate(candidate)
    _seed_jd_library(saved_jds)
    provisional = evaluate_blueprint_candidate(
        candidate=copy.deepcopy(candidate),
        selected_jds=[copy.deepcopy(saved_jds[0])],
        saved_jds_for_source_resolution=copy.deepcopy(saved_jds),
    )
    provisional = save_or_reuse_blueprint_evaluation(provisional)["evaluation"]
    return {
        "fixture": fixture,
        "candidate": candidate,
        "saved_jds": saved_jds,
        "provisional_evaluation": provisional,
    }


def persist_non_provisional_evaluation(state: dict[str, Any]) -> dict[str, Any]:
    evaluation = evaluate_blueprint_candidate(
        candidate=copy.deepcopy(state["candidate"]),
        selected_jds=copy.deepcopy(state["saved_jds"][:2]),
        saved_jds_for_source_resolution=copy.deepcopy(state["saved_jds"]),
    )
    return save_or_reuse_blueprint_evaluation(evaluation)["evaluation"]


def persist_historical_v2_evaluation(
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    historical = copy.deepcopy(evaluation)
    historical.pop("evaluation_id", None)
    historical.pop("created_at", None)
    semantic = historical["semantic_identity"]
    semantic["policy"]["policy_version"] = (
        "phase9c-same-family-explicit-scope-v2"
    )
    for row in semantic["selected_jd_scope"]:
        row.pop("stable_input_fingerprint", None)
    historical["evaluation_fingerprint"] = fingerprint_semantic_identity(
        semantic
    )
    return save_or_reuse_blueprint_evaluation(historical)["evaluation"]
