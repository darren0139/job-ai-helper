"""Presentation helpers for discovered-job locations."""

from __future__ import annotations

import re
from typing import Any

_SG_POSTAL_RE = re.compile(r"^\d{6}$")


def is_singapore_postal_code(value: Any) -> bool:
    return bool(_SG_POSTAL_RE.fullmatch(str(value or "").strip()))


def format_singapore_postal_location(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if is_singapore_postal_code(text):
        return f"Singapore {text}"
    return text


def display_job_location(job: dict[str, Any] | None) -> str:
    if not isinstance(job, dict):
        return ""

    raw_location = str(job.get("location") or "").strip()
    source = str(job.get("source") or "").strip().casefold()

    if source == "mycareersfuture":
        return format_singapore_postal_location(raw_location)

    return raw_location
