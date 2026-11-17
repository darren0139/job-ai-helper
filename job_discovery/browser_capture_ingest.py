"""Promote supported browser captures into the existing Job Finder index."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlsplit

from database.browser_capture_manager import canonicalize_browser_source_url
from database.job_discovery_manager import upsert_discovered_jobs
from job_discovery.models import NormalizedJob


_SUPPORTED = {
    "fastjobs": {"fastjobs.sg", "www.fastjobs.sg"},
    "workjio": {"workjio.com", "www.workjio.com"},
}


def _source_job_id(source: str, canonical_url: str) -> str:
    parsed = urlsplit(canonical_url)
    path = str(parsed.path or "")

    if source == "fastjobs":
        match = re.search(
            r"/singapore-job-ad/(\d+)(?:/|$)",
            path,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)

    parts = [part for part in path.split("/") if part]
    if source == "workjio" and len(parts) >= 2 and parts[-2].casefold() == "jobs":
        return parts[-1]
    if parts:
        return parts[-1]

    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:20]


def _host_allowed(source: str, url: str) -> bool:
    try:
        host = str(urlsplit(url).hostname or "").casefold()
    except ValueError:
        return False
    return host in _SUPPORTED.get(source, set())


def normalized_browser_discovery_job(
    payload: dict[str, Any],
    saved_capture: dict[str, Any],
) -> NormalizedJob | None:
    source_payload = payload.get("source")
    job_payload = payload.get("job")
    if not isinstance(source_payload, dict) or not isinstance(job_payload, dict):
        return None

    source = str(source_payload.get("site_adapter") or "").strip().casefold()
    if source not in _SUPPORTED:
        return None

    source_url = canonicalize_browser_source_url(
        str(source_payload.get("url") or "")
    )
    if not source_url or not _host_allowed(source, source_url):
        return None

    title = str(job_payload.get("job_title") or "").strip()
    description = str(job_payload.get("jd_text") or "").strip()
    if not title or len(description) < 120:
        return None

    return NormalizedJob(
        source=source,
        source_job_id=_source_job_id(source, source_url),
        source_platform="browser_extension",
        title=title,
        company=str(job_payload.get("company") or "").strip() or "Unknown Company",
        description=description,
        location=str(job_payload.get("location") or "").strip() or "Singapore",
        source_url=source_url,
        apply_url=source_url,
        employment_type=str(job_payload.get("employment_type") or "").strip(),
        raw_payload={
            "provenance": "browser_extension_capture",
            "browser_capture_id": saved_capture.get("id"),
            "browser_capture_hash": str(
                saved_capture.get("capture_hash") or ""
            ).strip(),
            "site_adapter": source,
            "site_adapter_version": str(
                source_payload.get("site_adapter_version") or ""
            ).strip(),
            "captured_at": str(source_payload.get("captured_at") or "").strip(),
            "capture_payload": payload,
        },
    )


def ingest_browser_capture_to_job_finder(
    payload: dict[str, Any],
    saved_capture: dict[str, Any],
) -> dict[str, Any]:
    job = normalized_browser_discovery_job(payload, saved_capture)
    if job is None:
        return {
            "status": "not_applicable",
            "source": str(
                (payload.get("source") or {}).get("site_adapter") or ""
            ).strip(),
        }

    stats = upsert_discovered_jobs(
        [job],
        source_scope=f"browser:{job.source}",
    )
    return {
        "status": "indexed",
        "source": job.source,
        "source_job_id": job.source_job_id,
        "source_url": job.source_url,
        "stats": stats,
    }
