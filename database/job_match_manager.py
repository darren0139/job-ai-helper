"""SQLite persistence for evidence-grounded Job Finder match snapshots."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("data/applications.db")


def _connect(db_path=None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_job_match_schema(db_path=None) -> None:
    connection = _connect(db_path)
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
    db_path=None,
) -> dict[str, Any] | None:
    init_job_match_schema(db_path)
    connection = _connect(db_path)
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


def list_latest_compatible_job_match_snapshots(
    *,
    match_version: str,
    scoring_version: str,
    taxonomy_version: str,
    read_only: bool = False,
) -> list[dict[str, Any]]:
    """Return one latest compatible Job Match snapshot per discovered job.

    A job may have multiple snapshots because its evidence fingerprint changed.
    Taxonomy discovery must not count historical snapshots from the same job as
    independent market observations.
    """
    if read_only:
        connection = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
    else:
        init_job_match_schema()
        connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT current.*
            FROM job_match_snapshots AS current
            JOIN (
                SELECT discovered_job_id, MAX(id) AS latest_id
                FROM job_match_snapshots
                WHERE match_version = ?
                  AND scoring_version = ?
                  AND taxonomy_version = ?
                GROUP BY discovered_job_id
            ) AS latest
              ON latest.latest_id = current.id
            ORDER BY current.discovered_job_id ASC, current.id ASC
            """,
            (
                str(match_version or ""),
                str(scoring_version or ""),
                str(taxonomy_version or ""),
            ),
        ).fetchall()
        return [
            decoded
            for decoded in (_decode_row(row) for row in rows)
            if decoded is not None
        ]
    finally:
        connection.close()


def list_latest_job_match_corpus_snapshots(*, db_path=None):
    """Read one frozen snapshot per job, retaining its pinned historical versions.

    Original JD text is recoverable only while the stored job has the same
    content hash. Never substitute a changed current JD for historical input.
    """
    path = Path(db_path or DB_PATH).resolve()
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "job_match_snapshots" not in tables:
            raise ValueError("Saved Job Match snapshots unavailable")
        jobs_available = "discovered_jobs" in tables and {"id", "content_hash", "description"}.issubset(
            {row[1] for row in connection.execute("PRAGMA table_info(discovered_jobs)")})
        rows = connection.execute("""SELECT s.* FROM job_match_snapshots s
            JOIN (SELECT discovered_job_id, MAX(id) latest_id FROM job_match_snapshots GROUP BY discovered_job_id) latest
            ON s.id=latest.latest_id ORDER BY s.discovered_job_id""").fetchall()
        output = []
        for row in rows:
            snapshot = _decode_row(row)
            original = None
            if jobs_available:
                original = connection.execute("SELECT description FROM discovered_jobs WHERE id=? AND content_hash=?",
                    (snapshot["discovered_job_id"], snapshot["job_content_hash"])).fetchone()
            snapshot["raw_jd_text"] = original[0] if original else None
            snapshot["raw_jd_provenance"] = "stored_job_matching_snapshot_hash" if original else "unavailable"
            output.append(snapshot)
        return output
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
    db_path=None,
) -> dict[str, Any]:
    init_job_match_schema(db_path)
    connection = _connect(db_path)
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
        db_path=db_path,
    )
    if snapshot is None:
        raise RuntimeError("Job match snapshot was not readable after save.")
    return snapshot
