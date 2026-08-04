"""Persistence for immutable Phase 9C evaluations."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import datetime
from typing import Any

from database import tailoring_version_manager as base_manager
from tailoring.phase9c_blueprint_evaluation import PHASE9C_VERSION


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def init_blueprint_evaluation_registry() -> None:
    connection = _connect()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS blueprint_cross_jd_evaluations (
                evaluation_fingerprint TEXT PRIMARY KEY,
                evaluation_id TEXT NOT NULL UNIQUE,
                candidate_id TEXT NOT NULL,
                role_family_id TEXT NOT NULL,
                phase9c_version TEXT NOT NULL,
                semantic_identity_json TEXT NOT NULL,
                evaluation_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_blueprint_cross_jd_candidate
            ON blueprint_cross_jd_evaluations (
                candidate_id,
                created_at DESC
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def get_blueprint_evaluation(
    evaluation_fingerprint: str,
) -> dict[str, Any] | None:
    init_blueprint_evaluation_registry()
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT evaluation_json
            FROM blueprint_cross_jd_evaluations
            WHERE evaluation_fingerprint = ?
            LIMIT 1
            """,
            (str(evaluation_fingerprint),),
        ).fetchone()
        return json.loads(str(row["evaluation_json"])) if row is not None else None
    finally:
        connection.close()


def get_blueprint_evaluation_by_id(
    evaluation_id: str,
) -> dict[str, Any] | None:
    init_blueprint_evaluation_registry()
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT evaluation_json
            FROM blueprint_cross_jd_evaluations
            WHERE evaluation_id = ?
            LIMIT 1
            """,
            (str(evaluation_id),),
        ).fetchone()
        return json.loads(str(row["evaluation_json"])) if row is not None else None
    finally:
        connection.close()


def list_blueprint_evaluations(
    *,
    candidate_id: str | None = None,
    role_family_id: str | None = None,
) -> list[dict[str, Any]]:
    """List persisted evaluations, including historical policy versions."""
    init_blueprint_evaluation_registry()
    connection = _connect()
    try:
        clauses: list[str] = []
        values: list[Any] = []
        if candidate_id:
            clauses.append("candidate_id = ?")
            values.append(str(candidate_id))
        if role_family_id:
            clauses.append("role_family_id = ?")
            values.append(str(role_family_id))
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        rows = connection.execute(
            f"""
            SELECT evaluation_json
            FROM blueprint_cross_jd_evaluations
            {where}
            ORDER BY created_at DESC, evaluation_id DESC
            """,
            values,
        ).fetchall()
        return [json.loads(str(row["evaluation_json"])) for row in rows]
    finally:
        connection.close()


def save_or_reuse_blueprint_evaluation(
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Persist once and return the exact stored evaluation on every reuse."""
    fingerprint = str(evaluation.get("evaluation_fingerprint") or "").strip()
    semantic_identity = evaluation.get("semantic_identity")
    if not fingerprint or not isinstance(semantic_identity, dict):
        raise ValueError("A complete Phase 9C fingerprint and semantic identity are required.")
    if str(evaluation.get("phase9c_version") or "") != PHASE9C_VERSION:
        raise ValueError(f"Expected {PHASE9C_VERSION}.")

    init_blueprint_evaluation_registry()
    connection = _connect()
    try:
        existing = connection.execute(
            """
            SELECT semantic_identity_json, evaluation_json
            FROM blueprint_cross_jd_evaluations
            WHERE evaluation_fingerprint = ?
            LIMIT 1
            """,
            (fingerprint,),
        ).fetchone()
        expected_identity_json = _canonical_json(semantic_identity)
        if existing is not None:
            if str(existing["semantic_identity_json"]) != expected_identity_json:
                raise RuntimeError(
                    "Phase 9C fingerprint collision: the complete selected scope differs."
                )
            return {
                "cache_status": "hit",
                "evaluation": json.loads(str(existing["evaluation_json"])),
            }

        stored = deepcopy(evaluation)
        stored["evaluation_id"] = fingerprint[:32]
        stored["created_at"] = datetime.now().isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO blueprint_cross_jd_evaluations (
                evaluation_fingerprint,
                evaluation_id,
                candidate_id,
                role_family_id,
                phase9c_version,
                semantic_identity_json,
                evaluation_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fingerprint,
                stored["evaluation_id"],
                str((stored.get("candidate_scope") or {}).get("candidate_id") or ""),
                str((stored.get("candidate_scope") or {}).get("role_family_id") or ""),
                PHASE9C_VERSION,
                expected_identity_json,
                _canonical_json(stored),
                stored["created_at"],
            ),
        )
        connection.commit()
        return {"cache_status": "miss", "evaluation": stored}
    finally:
        connection.close()
