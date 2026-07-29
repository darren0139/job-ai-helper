"""Deterministic cleanup for structured résumé extraction.

The LLM may shorten a project heading such as
"QueryAI (React, Team of 4)" to "QueryAI".  That is harmless for semantic
matching, but it is not acceptable as the canonical source title.  This module
recovers exact project headings from the raw résumé text and reconciles only
unique, conservative matches.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


RESUME_PROFILE_STABILITY_VERSION = "resume-profile-title-stability-v1"

_SECTION_HEADINGS = {
    "PROJECTS",
    "PROJECT EXPERIENCE",
    "ACADEMIC PROJECTS",
    "PERSONAL PROJECTS",
}
_STOP_HEADINGS = {
    "EDUCATION",
    "WORK EXPERIENCE",
    "EXPERIENCE",
    "EMPLOYMENT",
    "SKILLS",
    "TECHNICAL SKILLS",
    "CERTIFICATIONS",
    "ACHIEVEMENTS",
    "AWARDS",
    "SUMMARY",
    "PROFILE",
}

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept(?:ember)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_RANGE_AT_END = re.compile(
    rf"\s+(?P<date>{_MONTH}\s+\d{{4}}\s*[-–—]\s*"
    rf"(?:{_MONTH}\s+\d{{4}}|Present|Current|Now))\s*$",
    flags=re.IGNORECASE,
)
_DATE_ONLY = re.compile(
    rf"^(?:{_MONTH}\s+\d{{4}}\s*[-–—]\s*"
    rf"(?:{_MONTH}\s+\d{{4}}|Present|Current|Now))$",
    flags=re.IGNORECASE,
)
_BULLET_PREFIX = re.compile(r"^\s*(?:[•▪◦●*]|[-–—]\s+)")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("–", "-").replace("—", "-").replace("‑", "-")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _base_title(value: Any) -> str:
    original = _clean(value)
    text = original
    while text:
        updated = re.sub(
            r"\s*(?:\([^()]*\)|\[[^\[\]]*\])\s*$",
            "",
            text,
        ).strip()
        if updated == text:
            break
        text = updated
    return _normalise(text or original)


def extract_raw_project_headings(resume_text: str) -> list[dict[str, str]]:
    """Extract conservative project-title candidates from the Projects section."""
    lines = [
        _clean(line)
        for line in str(resume_text or "").replace("\r\n", "\n").split("\n")
    ]
    lines = [line for line in lines if line]

    start_index: int | None = None
    for index, line in enumerate(lines):
        if line.upper().rstrip(":") in _SECTION_HEADINGS:
            start_index = index + 1
            break

    if start_index is None:
        return []

    section: list[str] = []
    for line in lines[start_index:]:
        heading = line.upper().rstrip(":")
        if heading in _STOP_HEADINGS:
            break
        section.append(line)

    candidates: list[dict[str, str]] = []
    index = 0
    while index < len(section):
        line = section[index]
        if _BULLET_PREFIX.match(line):
            index += 1
            continue

        title = ""
        period = ""
        matched = _DATE_RANGE_AT_END.search(line)
        if matched:
            period = _clean(matched.group("date"))
            title = _clean(line[: matched.start()])
        elif (
            index + 1 < len(section)
            and _DATE_ONLY.fullmatch(section[index + 1])
        ):
            title = _clean(line)
            period = _clean(section[index + 1])
            index += 1

        if (
            title
            and 2 <= len(title) <= 180
            and not title.endswith((".", ";"))
            and title.upper().rstrip(":") not in _STOP_HEADINGS
        ):
            candidates.append(
                {
                    "title": title,
                    "period": period,
                    "exact_key": _normalise(title),
                    "base_key": _base_title(title),
                }
            )
        index += 1

    # Preserve order while removing exact duplicates.
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        key = (item["exact_key"], item["period"].lower())
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def stabilise_resume_profile_project_titles(
    profile: dict[str, Any],
    raw_resume_text: str,
) -> dict[str, Any]:
    """Restore exact raw project headings when the match is unique and safe."""
    result = deepcopy(profile if isinstance(profile, dict) else {})
    projects = result.get("projects")
    if not isinstance(projects, list):
        return result

    candidates = extract_raw_project_headings(raw_resume_text)
    if not candidates:
        return result

    by_exact: dict[str, list[dict[str, str]]] = {}
    by_base: dict[str, list[dict[str, str]]] = {}
    for item in candidates:
        by_exact.setdefault(item["exact_key"], []).append(item)
        by_base.setdefault(item["base_key"], []).append(item)

    extracted_base_counts: dict[str, int] = {}
    for project in projects:
        if not isinstance(project, dict):
            continue
        base = _base_title(project.get("title"))
        if base:
            extracted_base_counts[base] = extracted_base_counts.get(base, 0) + 1

    for project in projects:
        if not isinstance(project, dict):
            continue

        current_title = _clean(project.get("title"))
        if not current_title:
            continue

        exact_matches = by_exact.get(_normalise(current_title), [])
        selected: dict[str, str] | None = None
        if len(exact_matches) == 1:
            selected = exact_matches[0]
        else:
            base = _base_title(current_title)
            base_matches = by_base.get(base, [])
            if (
                base
                and len(base_matches) == 1
                and extracted_base_counts.get(base, 0) == 1
            ):
                selected = base_matches[0]

        if selected is not None:
            project["title"] = selected["title"]
            if not _clean(project.get("date")) and selected.get("period"):
                project["date"] = selected["period"]

    return result
