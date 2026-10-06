"""Deterministic helpers for Job Finder view-state caching."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


VIEW_PERFORMANCE_VERSION = "job-finder-view-performance-v1"


def match_state_cache_key(
    jobs: Iterable[dict[str, Any]],
    *,
    evidence_fingerprint: str,
    versions: dict[str, Any] | None = None,
) -> str:
    payload = {
        "version": VIEW_PERFORMANCE_VERSION,
        "evidence_fingerprint": str(evidence_fingerprint or ""),
        "versions": {
            str(key): str(value or "")
            for key, value in sorted((versions or {}).items())
        },
        "jobs": [
            [
                int(job.get("id", 0) or 0),
                str(job.get("content_hash") or ""),
            ]
            for job in jobs
            if isinstance(job, dict)
            and int(job.get("id", 0) or 0) > 0
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def clamp_page(
    page: int,
    total_pages: int,
) -> int:
    safe_total = max(1, int(total_pages or 1))
    return min(max(1, int(page or 1)), safe_total)
