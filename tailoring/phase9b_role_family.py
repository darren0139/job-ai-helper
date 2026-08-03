"""Canonical role-family helpers for Phase 9B and later blueprint phases."""

from __future__ import annotations

import re
from typing import Any


CUSTOM_ROLE_FAMILY_LABEL = "Custom role family…"

ROLE_FAMILY_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "ai_fullstack_software_engineering",
        "label": "AI & Full-Stack Software Engineering",
        "short_label": "AI & Full-Stack",
    },
    {
        "id": "ai_machine_learning_engineering",
        "label": "AI & Machine Learning Engineering",
        "short_label": "AI & ML",
    },
    {
        "id": "backend_cloud_software_engineering",
        "label": "Backend & Cloud Software Engineering",
        "short_label": "Backend & Cloud",
    },
    {
        "id": "frontend_software_engineering",
        "label": "Frontend Software Engineering",
        "short_label": "Frontend",
    },
    {
        "id": "game_operations_configuration_qa",
        "label": "Game Operations, Configuration & QA",
        "short_label": "Game Operations & QA",
    },
    {
        "id": "game_development_engine_programming",
        "label": "Game Development & Engine Programming",
        "short_label": "Game Development & Engine",
    },
    {
        "id": "embedded_firmware_engineering",
        "label": "Embedded & Firmware Engineering",
        "short_label": "Embedded & Firmware",
    },
    {
        "id": "robotics_software_engineering",
        "label": "Robotics Software Engineering",
        "short_label": "Robotics Software",
    },
    {
        "id": "data_engineering_analytics",
        "label": "Data Engineering & Analytics",
        "short_label": "Data Engineering",
    },
    {
        "id": "network_infrastructure_engineering",
        "label": "Network & Infrastructure Engineering",
        "short_label": "Network & Infrastructure",
    },
    {
        "id": "general_software_engineering",
        "label": "General Software Engineering",
        "short_label": "Software Engineering",
    },
)


_GENERIC_JOB_HEADINGS = {
    "key responsibilities",
    "responsibilities",
    "requirements",
    "preferred qualifications",
    "qualifications",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    return " ".join(text.split())


def role_family_labels() -> list[str]:
    return [str(row["label"]) for row in ROLE_FAMILY_CATALOG]


def role_family_record_by_label(label: str) -> dict[str, Any] | None:
    cleaned = _clean(label)
    for row in ROLE_FAMILY_CATALOG:
        if str(row["label"]) == cleaned:
            return dict(row)
    return None


def role_family_record_by_id(role_family_id: str) -> dict[str, Any] | None:
    cleaned = _clean(role_family_id)
    for row in ROLE_FAMILY_CATALOG:
        if str(row["id"]) == cleaned:
            return dict(row)
    return None


def canonical_role_family_id(label: str) -> str:
    record = role_family_record_by_label(label)
    if record is not None:
        return str(record["id"])
    normalised = _normalise(label)
    slug = re.sub(r"[^a-z0-9]+", "_", normalised).strip("_")
    return f"custom_{slug}" if slug else "custom_unspecified"


def short_role_family_label(label: str) -> str:
    record = role_family_record_by_label(label)
    if record is not None:
        return str(record["short_label"])
    cleaned = _clean(label)
    return cleaned or "General"


def _source_job_title(baseline_report: dict[str, Any]) -> str:
    profile = baseline_report.get("jd_profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    return _clean(
        profile.get("job_title")
        or profile.get("role")
        or profile.get("title")
    )


def _source_company(baseline_report: dict[str, Any]) -> str:
    profile = baseline_report.get("jd_profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    return _clean(
        profile.get("company")
        or profile.get("company_name")
        or profile.get("employer")
    )


def source_job_metadata(
    baseline_report: dict[str, Any],
) -> dict[str, str]:
    return {
        "job_title": _source_job_title(baseline_report),
        "company": _source_company(baseline_report),
    }


def suggest_role_family(
    baseline_report: dict[str, Any],
) -> dict[str, Any]:
    """Suggest one stable family from the source job title.

    The result is deterministic and intentionally conservative. The user may
    override it in the Phase 9B form.
    """
    title = _source_job_title(baseline_report)
    text = _normalise(title)
    tokens = set(text.split())

    def has(*terms: str) -> bool:
        return all(_normalise(term) in text for term in terms)

    def any_token(*terms: str) -> bool:
        return any(_normalise(term) in tokens for term in terms)

    label = "General Software Engineering"
    confidence = "low"
    matched_terms: list[str] = []

    if (
        (has("configuration") and any_token("qa", "quality"))
        or (has("game") and any_token("operations", "qa", "configuration"))
        or has("live operations")
    ):
        label = "Game Operations, Configuration & QA"
        confidence = "high"
        matched_terms = [
            term
            for term in ("game", "operations", "configuration", "qa")
            if _normalise(term) in text
        ]
    elif (
        any_token("ai", "llm")
        and (
            has("full stack")
            or has("fullstack")
            or any_token("frontend", "backend")
        )
    ):
        label = "AI & Full-Stack Software Engineering"
        confidence = "high"
        matched_terms = [
            term
            for term in ("ai", "llm", "full stack", "fullstack", "frontend", "backend")
            if _normalise(term) in text
        ]
    elif (
        any_token("ai", "ml", "llm")
        or has("machine learning")
        or has("artificial intelligence")
    ):
        label = "AI & Machine Learning Engineering"
        confidence = "medium"
        matched_terms = [
            term
            for term in ("ai", "ml", "llm", "machine learning")
            if _normalise(term) in text
        ]
    elif (
        any_token("backend", "cloud", "platform", "infrastructure")
        and not any_token("network", "networking")
    ):
        label = "Backend & Cloud Software Engineering"
        confidence = "medium"
        matched_terms = [
            term
            for term in ("backend", "cloud", "platform", "infrastructure")
            if _normalise(term) in text
        ]
    elif any_token("frontend", "ui", "ux") or has("front end"):
        label = "Frontend Software Engineering"
        confidence = "medium"
        matched_terms = [
            term
            for term in ("frontend", "front end", "ui", "ux")
            if _normalise(term) in text
        ]
    elif any_token("robotics", "robot", "autonomy"):
        label = "Robotics Software Engineering"
        confidence = "high"
        matched_terms = [
            term
            for term in ("robotics", "robot", "autonomy")
            if _normalise(term) in text
        ]
    elif any_token("embedded", "firmware", "microcontroller", "iot"):
        label = "Embedded & Firmware Engineering"
        confidence = "high"
        matched_terms = [
            term
            for term in ("embedded", "firmware", "microcontroller", "iot")
            if _normalise(term) in text
        ]
    elif (
        has("game")
        or any_token("unity", "unreal", "graphics", "engine")
    ):
        label = "Game Development & Engine Programming"
        confidence = "medium"
        matched_terms = [
            term
            for term in ("game", "unity", "unreal", "graphics", "engine")
            if _normalise(term) in text
        ]
    elif any_token("data", "analytics", "etl"):
        label = "Data Engineering & Analytics"
        confidence = "medium"
        matched_terms = [
            term
            for term in ("data", "analytics", "etl")
            if _normalise(term) in text
        ]
    elif any_token("network", "networking", "systems"):
        label = "Network & Infrastructure Engineering"
        confidence = "medium"
        matched_terms = [
            term
            for term in ("network", "networking", "systems")
            if _normalise(term) in text
        ]

    record = role_family_record_by_label(label)
    assert record is not None
    return {
        "role_family_id": str(record["id"]),
        "role_family": str(record["label"]),
        "confidence": confidence,
        "matched_terms": matched_terms,
        "source_job_title": title,
        "suggestion_method": "deterministic_title_rules_v1",
    }


def build_default_candidate_name(
    *,
    application_id: int,
    generation_id: str,
    role_family: str,
) -> str:
    short_label = short_role_family_label(role_family)
    generation_short = _clean(generation_id)[:8] or "unknown"
    return (
        f"{short_label} — App {int(application_id)} — "
        f"{generation_short}"
    )


def _project_titles(
    generation_state: dict[str, Any],
) -> list[str]:
    fit_result = generation_state.get("fit_result")
    if not isinstance(fit_result, dict):
        fit_result = {}
    projects = fit_result.get("tailored_projects_used")
    if not isinstance(projects, dict):
        projects = generation_state.get("projects")
    if not isinstance(projects, dict):
        return []

    titles: list[str] = []
    for project in projects.get("recommended_projects", []) or []:
        if not isinstance(project, dict):
            continue
        title = _clean(
            project.get("display_title")
            or project.get("title")
        )
        if title and title not in titles:
            titles.append(title)
    return titles


def build_default_candidate_notes(
    *,
    application_id: int,
    generation_state: dict[str, Any],
    verification: dict[str, Any],
    baseline_report: dict[str, Any],
    role_family: str,
) -> str:
    """Build optional, editable human context without any model call."""
    job = source_job_metadata(baseline_report)
    title = job["job_title"] or "the source role"
    company_suffix = f" at {job['company']}" if job["company"] else ""
    generation_short = _clean(
        generation_state.get("generation_id")
    )[:8]
    comparison = verification.get("comparison") or {}
    before_score = int(comparison.get("before_score", 0) or 0)
    after_score = int(comparison.get("after_score", 0) or 0)
    page_count = int(
        (generation_state.get("fit_result") or {}).get("page_count", 0)
        or 0
    )
    claim_reviews = int(
        (verification.get("claim_lineage") or {}).get(
            "claim_review_required_count",
            0,
        )
        or 0
    )
    projects = _project_titles(generation_state)
    project_clause = (
        f" Final project evidence: {', '.join(projects[:4])}."
        if projects
        else ""
    )
    return _clean(
        f"Promoted from Application {int(application_id)}: {title}"
        f"{company_suffix}. Approved {page_count or 1}-page generation "
        f"{generation_short or 'unknown'} improved deterministic alignment "
        f"from {before_score} to {after_score} with {claim_reviews} "
        f"claim-review risk(s).{project_clause} Intended for Phase 9C "
        f"cross-JD evaluation within {role_family}."
    )


def compact_requirement_summary(
    verification: dict[str, Any],
) -> list[dict[str, Any]]:
    after = verification.get("after_stable_analysis") or {}
    rows: list[dict[str, Any]] = []
    for requirement in after.get("canonical_requirements", []) or []:
        if not isinstance(requirement, dict):
            continue
        text = _clean(requirement.get("text"))
        if _normalise(text) in _GENERIC_JOB_HEADINGS:
            continue
        rows.append(
            {
                "requirement_id": _clean(
                    requirement.get("requirement_id")
                ),
                "text": text,
                "importance": _clean(
                    requirement.get("importance")
                ),
                "match_label": _clean(
                    requirement.get("match_label")
                ).lower()
                or "none",
                "evidence_strength": int(
                    requirement.get("evidence_strength", 0) or 0
                ),
                "capability_id": _clean(
                    requirement.get("capability_id")
                ),
            }
        )
    return rows
