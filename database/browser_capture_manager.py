"""Persistent inbox for deterministic browser JD captures.

The browser extension stores clean captures here before any LLM extraction or
canonical JD-library write occurs. This keeps browser collection separate from
Job AI Helper's existing JD-analysis and identity/versioning pipeline.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalise_capture_text(value: str) -> str:
    return "\n".join(
        line.strip()
        for line in str(value or "").replace("\r\n", "\n").split("\n")
        if line.strip()
    )


_TRACKING_QUERY_KEYS = {
    "gh_src",
    "lipi",
    "midsig",
    "midtoken",
    "refid",
    "trackingid",
    "trk",
    "trkemail",
}


def _linkedin_job_id(parsed: Any) -> str:
    host = str(parsed.hostname or "").lower()
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        return ""

    direct_match = re.search(
        r"/jobs/view/[^/?#]*?(\d{5,})/?$",
        str(parsed.path or ""),
        re.IGNORECASE,
    )
    if direct_match:
        return direct_match.group(1)

    for key, query_value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):
        if key.strip().lower() != "currentjobid":
            continue
        candidate = str(query_value or "").strip()
        if re.fullmatch(r"\d{5,}", candidate):
            return candidate

    return ""


def canonicalize_browser_source_url(value: str) -> str:
    """Return a deterministic job URL while preserving job-identifying params."""
    raw = str(value or "").strip()
    if not raw:
        return ""

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return raw

    linkedin_job_id = _linkedin_job_id(parsed)
    if linkedin_job_id:
        return f"https://www.linkedin.com/jobs/view/{linkedin_job_id}"

    filtered_query = []
    for key, query_value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):
        lowered = key.strip().lower()
        if lowered.startswith("utm_"):
            continue
        if lowered in _TRACKING_QUERY_KEYS:
            continue
        filtered_query.append((key, query_value))

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def _capture_hash(source_url: str, jd_text: str) -> str:
    canonical_url = canonicalize_browser_source_url(source_url)
    material = f"{canonical_url}\n{_normalise_capture_text(jd_text)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    columns = {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
        )


def init_browser_capture_schema() -> None:
    connection = _connect()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS browser_job_captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                source_url TEXT NOT NULL,
                document_title TEXT,
                source_host TEXT,
                site_adapter TEXT,
                job_title TEXT,
                company TEXT,
                location TEXT,
                jd_text TEXT NOT NULL,
                raw_page_text TEXT,
                headings_json TEXT,
                extraction_strategy TEXT,
                extraction_confidence TEXT,
                captured_at TEXT,
                first_received_at TEXT NOT NULL,
                last_received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                posting_notes_json TEXT,
                discarded_tracking_tags_json TEXT
            )
            """
        )
        _ensure_column(
            connection,
            "browser_job_captures",
            "posting_notes_json",
            "TEXT",
        )
        _ensure_column(
            connection,
            "browser_job_captures",
            "discarded_tracking_tags_json",
            "TEXT",
        )
        _ensure_column(
            connection,
            "browser_job_captures",
            "canonical_source_url",
            "TEXT",
        )

        existing_urls = connection.execute(
            """
            SELECT id, source_url, canonical_source_url
            FROM browser_job_captures
            """
        ).fetchall()
        canonical_updates = []
        for row in existing_urls:
            canonical_url = canonicalize_browser_source_url(
                str(row["source_url"] or "")
            )
            if str(row["canonical_source_url"] or "") != canonical_url:
                canonical_updates.append((canonical_url, int(row["id"])))
        if canonical_updates:
            connection.executemany(
                """
                UPDATE browser_job_captures
                SET canonical_source_url = ?
                WHERE id = ?
                """,
                canonical_updates,
            )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_browser_job_captures_status_received
            ON browser_job_captures(status, last_received_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_browser_job_captures_canonical_status
            ON browser_job_captures(
                canonical_source_url,
                status,
                last_received_at DESC
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def _validated_capture(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Browser capture must be a JSON object.")

    source = payload.get("source")
    capture = payload.get("capture")
    job = payload.get("job")

    if not isinstance(source, dict) or not isinstance(capture, dict) or not isinstance(job, dict):
        raise ValueError("Browser capture must contain source, capture, and job objects.")

    source_url = str(source.get("url") or "").strip()
    jd_text = str(job.get("jd_text") or "").strip()

    if not source_url:
        raise ValueError("Browser capture source.url cannot be empty.")
    if not source_url.startswith(("http://", "https://")):
        raise ValueError("Browser capture source.url must be HTTP(S).")
    if not jd_text:
        raise ValueError("Browser capture job.jd_text cannot be empty.")

    raw_page_text = str(capture.get("raw_visible_text") or "")
    if len(jd_text) > 250_000 or len(raw_page_text) > 1_000_000:
        raise ValueError("Browser capture is larger than the local POC limit.")

    headings = capture.get("headings")
    if not isinstance(headings, list):
        headings = []

    posting_notes = job.get("posting_notes")
    if not isinstance(posting_notes, list):
        posting_notes = []

    discarded_tracking_tags = job.get("discarded_tracking_tags")
    if not isinstance(discarded_tracking_tags, list):
        discarded_tracking_tags = []

    return {
        "source_url": source_url,
        "document_title": str(source.get("document_title") or "").strip(),
        "source_host": str(source.get("host") or "").strip(),
        "site_adapter": str(source.get("site_adapter") or "").strip(),
        "job_title": str(job.get("job_title") or "").strip(),
        "company": str(job.get("company") or "").strip(),
        "location": str(job.get("location") or "").strip(),
        "jd_text": jd_text,
        "raw_page_text": raw_page_text,
        "headings": [str(item).strip() for item in headings if str(item).strip()],
        "posting_notes": [
            str(item).strip()
            for item in posting_notes
            if str(item).strip()
        ],
        "discarded_tracking_tags": [
            str(item).strip()
            for item in discarded_tracking_tags
            if str(item).strip()
        ],
        "extraction_strategy": str(job.get("cleaning_strategy") or "").strip(),
        "extraction_confidence": str(job.get("cleaning_confidence") or "").strip(),
        "captured_at": str(source.get("captured_at") or "").strip(),
        "payload": payload,
    }


def save_browser_job_capture(payload: dict[str, Any]) -> dict[str, Any]:
    """Save or refresh one exact browser capture without analyzing it."""
    item = _validated_capture(payload)
    init_browser_capture_schema()

    canonical_source_url = canonicalize_browser_source_url(
        item["source_url"]
    )
    digest = _capture_hash(canonical_source_url, item["jd_text"])
    now = _now()

    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO browser_job_captures (
                capture_hash,
                status,
                source_url,
                canonical_source_url,
                document_title,
                source_host,
                site_adapter,
                job_title,
                company,
                location,
                jd_text,
                raw_page_text,
                headings_json,
                extraction_strategy,
                extraction_confidence,
                captured_at,
                first_received_at,
                last_received_at,
                payload_json,
                posting_notes_json,
                discarded_tracking_tags_json
            )
            VALUES (?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(capture_hash) DO UPDATE SET
                canonical_source_url = excluded.canonical_source_url,
                document_title = excluded.document_title,
                source_host = excluded.source_host,
                site_adapter = excluded.site_adapter,
                job_title = excluded.job_title,
                company = excluded.company,
                location = excluded.location,
                raw_page_text = excluded.raw_page_text,
                headings_json = excluded.headings_json,
                extraction_strategy = excluded.extraction_strategy,
                extraction_confidence = excluded.extraction_confidence,
                captured_at = excluded.captured_at,
                status = 'pending',
                last_received_at = excluded.last_received_at,
                payload_json = excluded.payload_json,
                posting_notes_json = excluded.posting_notes_json,
                discarded_tracking_tags_json = excluded.discarded_tracking_tags_json
            """,
            (
                digest,
                item["source_url"],
                canonical_source_url,
                item["document_title"],
                item["source_host"],
                item["site_adapter"],
                item["job_title"],
                item["company"],
                item["location"],
                item["jd_text"],
                item["raw_page_text"],
                json.dumps(item["headings"], ensure_ascii=False),
                item["extraction_strategy"],
                item["extraction_confidence"],
                item["captured_at"],
                now,
                now,
                json.dumps(item["payload"], ensure_ascii=False),
                json.dumps(item["posting_notes"], ensure_ascii=False),
                json.dumps(
                    item["discarded_tracking_tags"],
                    ensure_ascii=False,
                ),
            ),
        )

        connection.execute(
            """
            UPDATE browser_job_captures
            SET status = 'superseded',
                last_received_at = ?
            WHERE canonical_source_url = ?
              AND capture_hash <> ?
              AND status = 'pending'
            """,
            (now, canonical_source_url, digest),
        )
        connection.commit()

        row = connection.execute(
            """
            SELECT *
            FROM browser_job_captures
            WHERE capture_hash = ?
            """,
            (digest,),
        ).fetchone()
    finally:
        connection.close()

    return dict(row) if row is not None else {}


def clear_pending_browser_job_captures() -> int:
    """Hide all pending browser captures while preserving local history."""
    init_browser_capture_schema()
    now = _now()

    connection = _connect()
    try:
        cursor = connection.execute(
            """
            UPDATE browser_job_captures
            SET status = 'cleared',
                last_received_at = ?
            WHERE status = 'pending'
            """,
            (now,),
        )
        connection.commit()
        return max(0, int(cursor.rowcount or 0))
    finally:
        connection.close()


def list_browser_job_captures(
    *,
    limit: int = 20,
    status: str | None = None,
) -> list[dict[str, Any]]:
    init_browser_capture_schema()
    safe_limit = max(1, min(int(limit), 100))

    connection = _connect()
    try:
        if status:
            rows = connection.execute(
                """
                SELECT *
                FROM browser_job_captures
                WHERE status = ?
                ORDER BY last_received_at DESC, id DESC
                LIMIT ?
                """,
                (status, safe_limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM browser_job_captures
                ORDER BY last_received_at DESC, id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    finally:
        connection.close()

    return [dict(row) for row in rows]


def get_browser_job_capture(capture_id: int) -> dict[str, Any] | None:
    init_browser_capture_schema()
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM browser_job_captures WHERE id = ?",
            (int(capture_id),),
        ).fetchone()
    finally:
        connection.close()

    return dict(row) if row is not None else None
