"""Deterministic project-heading presentation policy.

Canonical evidence stores semantic fields. This module alone turns those fields
into visible separators such as pipes or legacy parentheses.
"""

from __future__ import annotations

import re
from typing import Any

PROJECT_HEADER_LAYOUTS = ("auto", "stacked", "inline")
PROJECT_METADATA_STYLES = ("pipes", "parentheses")
DEFAULT_PROJECT_HEADER_LAYOUT = "auto"
DEFAULT_PROJECT_METADATA_STYLE = "pipes"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    result: list[str] = []
    seen: set[str] = set()
    for raw in value or []:
        item = _clean(raw)
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def normalise_project_header_layout(value: Any) -> str:
    layout = _clean(value).lower() or DEFAULT_PROJECT_HEADER_LAYOUT
    return layout if layout in PROJECT_HEADER_LAYOUTS else DEFAULT_PROJECT_HEADER_LAYOUT


def normalise_project_metadata_style(value: Any) -> str:
    style = _clean(value).lower() or DEFAULT_PROJECT_METADATA_STYLE
    return style if style in PROJECT_METADATA_STYLES else DEFAULT_PROJECT_METADATA_STYLE


def _looks_like_context(value: str) -> bool:
    text = _clean(value).casefold()
    return bool(
        re.match(r"^team\s+of\s+\d+\b", text)
        or text in {"solo", "solo project", "individual project", "team project", "individual"}
        or text.startswith("published on ")
        or text.startswith("released on ")
        or text.startswith("available on ")
    )


def split_legacy_project_title(value: Any) -> dict[str, Any]:
    """Conservatively split a simple trailing ``(...)`` legacy project label."""
    text = _clean(value)
    result = {
        "title": text,
        "resume_header_tools": [],
        "resume_header_context": [],
        "legacy_metadata_found": False,
    }
    match = re.match(r"^(?P<title>.+?)\s*\((?P<body>[^()]*)\)\s*$", text)
    if match is None:
        return result
    title = _clean(match.group("title"))
    parts = [_clean(part) for part in match.group("body").split(",")]
    parts = [part for part in parts if part]
    if not title or not parts:
        return result
    tools: list[str] = []
    context: list[str] = []
    for part in parts:
        (context if _looks_like_context(part) else tools).append(part)
    return {
        "title": title,
        "resume_header_tools": _clean_list(tools),
        "resume_header_context": _clean_list(context),
        "legacy_metadata_found": True,
    }


def _semantic_parts(project: dict[str, Any]) -> dict[str, Any]:
    raw_title = (
        project.get("title")
        or project.get("project_name")
        or project.get("name")
        or project.get("display_title")
        or "Untitled Project"
    )
    parsed = split_legacy_project_title(raw_title)
    title = _clean(parsed["title"]) or "Untitled Project"
    subtitle = _clean(project.get("subtitle"))
    header_tools = _clean_list(project.get("resume_header_tools"))
    if not header_tools:
        header_tools = _clean_list(parsed.get("resume_header_tools"))
    if not header_tools:
        header_tools = _clean_list(
            project.get("canonical_tools")
            or project.get("tools")
            or project.get("technologies")
            or project.get("tech_stack")
        )
    context = _clean_list(project.get("resume_header_context"))
    if not context:
        context = _clean_list(parsed.get("resume_header_context"))
    return {
        "title": title,
        "subtitle": subtitle,
        "resume_header_tools": header_tools,
        "resume_header_context": context,
    }


def build_project_title(project: dict[str, Any]) -> str:
    parts = _semantic_parts(project)
    return (
        f"{parts['title']} — {parts['subtitle']}"
        if parts["subtitle"]
        else parts["title"]
    )


def project_metadata_groups(project: dict[str, Any]) -> list[str]:
    parts = _semantic_parts(project)
    groups: list[str] = []
    if parts["resume_header_tools"]:
        groups.append(", ".join(parts["resume_header_tools"]))
    groups.extend(parts["resume_header_context"])
    return _clean_list(groups)


def format_project_metadata(project: dict[str, Any], *, style: str = "pipes") -> str:
    groups = project_metadata_groups(project)
    if not groups:
        return ""
    if normalise_project_metadata_style(style) == "parentheses":
        return "(" + ", ".join(groups) + ")"
    return " | ".join(groups)


def inline_project_header(project: dict[str, Any], *, style: str = "pipes") -> str:
    title = build_project_title(project)
    metadata = format_project_metadata(project, style=style)
    if not metadata:
        return title
    if normalise_project_metadata_style(style) == "parentheses":
        return f"{title} {metadata}"
    return f"{title} | {metadata}"


def project_evidence_preview(item: dict[str, Any], *, style: str = "pipes") -> str:
    return inline_project_header(item, style=style)
