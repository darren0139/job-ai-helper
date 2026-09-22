"""SQLite persistence for evidence-grounded Job Finder match snapshots."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_job_match_schema() -> None:
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS job_match_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discovered_job_id INTEGER NOT NULL,
                job_content_hash TEXT NOT NULL,
                evidence_fingerprint TEXT NOT NULL,
                match_version TEXT NOT NULL,
                scoring_version TEXT NOT NULL,
                taxonomy_version TEXT NOT NULL,
                jd_profile_json TEXT NOT NULL,
                evidence_snapshot_json TEXT NOT NULL,
                stable_analysis_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (
                    discovered_job_id,
                    job_content_hash,
                    evidence_fingerprint,
                    match_version,
                    scoring_version,
                    taxonomy_version
                )
            );

            CREATE INDEX IF NOT EXISTS idx_job_match_snapshot_lookup
            ON job_match_snapshots(
                discovered_job_id,
                job_content_hash,
                evidence_fingerprint,
                match_version,
                scoring_version,
                taxonomy_version
            );

            CREATE INDEX IF NOT EXISTS idx_job_match_snapshot_latest
            ON job_match_snapshots(discovered_job_id, created_at DESC, id DESC);
            """
        )
        connection.commit()
    finally:
        connection.close()


def _decode_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    for source_key, target_key in (
        ("jd_profile_json", "jd_profile"),
        ("evidence_snapshot_json", "evidence_snapshot"),
        ("stable_analysis_json", "stable_analysis"),
        ("summary_json", "summary"),
    ):
        raw = item.pop(source_key, "")
        try:
            item[target_key] = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            item[target_key] = {}
    return item


def get_job_match_snapshot(
    *,
    discovered_job_id: int,
    job_content_hash: str,
    evidence_fingerprint: str,
    match_version: str,
    scoring_version: str,
    taxonomy_version: str,
) -> dict[str, Any] | None:
    init_job_match_schema()
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT *
            FROM job_match_snapshots
            WHERE discovered_job_id = ?
              AND job_content_hash = ?
              AND evidence_fingerprint = ?
              AND match_version = ?
              AND scoring_version = ?
              AND taxonomy_version = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                int(discovered_job_id),
                str(job_content_hash or ""),
                str(evidence_fingerprint or ""),
                str(match_version or ""),
                str(scoring_version or ""),
                str(taxonomy_version or ""),
            ),
        ).fetchone()
        return _decode_row(row)
    finally:
        connection.close()


def get_latest_job_match_snapshot(
    discovered_job_id: int,
) -> dict[str, Any] | None:
    init_job_match_schema()
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT *
            FROM job_match_snapshots
            WHERE discovered_job_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (int(discovered_job_id),),
        ).fetchone()
        return _decode_row(row)
    finally:
        connection.close()


def save_job_match_snapshot(
    *,
    discovered_job_id: int,
    job_content_hash: str,
    evidence_fingerprint: str,
    match_version: str,
    scoring_version: str,
    taxonomy_version: str,
    jd_profile: dict[str, Any],
    evidence_snapshot: list[dict[str, Any]],
    stable_analysis: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    init_job_match_schema()
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO job_match_snapshots (
                discovered_job_id,
                job_content_hash,
                evidence_fingerprint,
                match_version,
                scoring_version,
                taxonomy_version,
                jd_profile_json,
                evidence_snapshot_json,
                stable_analysis_json,
                summary_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                discovered_job_id,
                job_content_hash,
                evidence_fingerprint,
                match_version,
                scoring_version,
                taxonomy_version
            ) DO UPDATE SET
                jd_profile_json = excluded.jd_profile_json,
                evidence_snapshot_json = excluded.evidence_snapshot_json,
                stable_analysis_json = excluded.stable_analysis_json,
                summary_json = excluded.summary_json,
                created_at = excluded.created_at
            """,
            (
                int(discovered_job_id),
                str(job_content_hash or ""),
                str(evidence_fingerprint or ""),
                str(match_version or ""),
                str(scoring_version or ""),
                str(taxonomy_version or ""),
                json.dumps(jd_profile or {}, ensure_ascii=False, sort_keys=True, default=str),
                json.dumps(evidence_snapshot or [], ensure_ascii=False, sort_keys=True, default=str),
                json.dumps(stable_analysis or {}, ensure_ascii=False, sort_keys=True, default=str),
                json.dumps(summary or {}, ensure_ascii=False, sort_keys=True, default=str),
                _now(),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    snapshot = get_job_match_snapshot(
        discovered_job_id=discovered_job_id,
        job_content_hash=job_content_hash,
        evidence_fingerprint=evidence_fingerprint,
        match_version=match_version,
        scoring_version=scoring_version,
        taxonomy_version=taxonomy_version,
    )
    if snapshot is None:
        raise RuntimeError("Job match snapshot was not readable after save.")
    return snapshot
