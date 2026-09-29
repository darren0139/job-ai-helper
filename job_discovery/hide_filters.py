"""Pure, deterministic hide-rule evaluation for Job Finder.

This module deliberately does not access SQLite or Streamlit. Rules are loaded by the
persistence layer and evaluated here so behavior is easy to test and reuse.
"""
from __future__ import annotations

from typing import Any, Iterable


RULE_TYPE_LABELS = {
    "job": "Individual job",
    "company": "Company equals",
    "title_keyword": "Title contains",
    "description_keyword": "Description contains",
    "seniority_keyword": "Seniority contains",
    "employment_type_keyword": "Employment type contains",
    "experience_min_above": "Minimum experience greater than",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def job_identity(job: dict[str, Any]) -> str:
    source = str(job.get("source") or "").strip()
    source_job_id = str(job.get("source_job_id") or "").strip()
    return f"{source}::{source_job_id}"


def _enabled(rule: dict[str, Any]) -> bool:
    value = rule.get("enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def rule_matches_job(job: dict[str, Any], rule: dict[str, Any]) -> bool:
    if not _enabled(rule):
        return False

    rule_type = str(rule.get("rule_type") or "").strip().lower()
    normalized_value = _text(rule.get("normalized_value") or rule.get("value"))
    if not normalized_value:
        return False

    if rule_type == "job":
        return _text(job_identity(job)) == normalized_value
    if rule_type == "company":
        return _text(job.get("company")) == normalized_value
    if rule_type == "title_keyword":
        return normalized_value in _text(job.get("title"))
    if rule_type == "description_keyword":
        return normalized_value in _text(job.get("description"))
    if rule_type == "seniority_keyword":
        return normalized_value in _text(job.get("seniority"))
    if rule_type == "employment_type_keyword":
        return normalized_value in _text(job.get("employment_type"))
    if rule_type == "experience_min_above":
        minimum = job.get("experience_years_min")
        if minimum is None:
            return False
        try:
            return float(minimum) > float(normalized_value)
        except (TypeError, ValueError):
            return False
    return False


def matching_hide_rules(
    job: dict[str, Any],
    rules: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [dict(rule) for rule in rules if rule_matches_job(job, rule)]


def rule_description(rule: dict[str, Any]) -> str:
    rule_type = str(rule.get("rule_type") or "").strip().lower()
    label = RULE_TYPE_LABELS.get(rule_type, rule_type or "Rule")
    value = str(rule.get("value") or "").strip()
    friendly = str(rule.get("label") or "").strip()
    if rule_type == "job" and friendly:
        return f"{label}: {friendly}"
    if rule_type == "experience_min_above":
        return f"{label}: {value} years"
    return f"{label}: {value}"


def partition_hidden_jobs(
    jobs: Iterable[dict[str, Any]],
    rules: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rules_list = [dict(rule) for rule in rules]
    visible: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    for original in jobs:
        job = dict(original)
        matches = matching_hide_rules(job, rules_list)
        if matches:
            job["_hide_reasons"] = [rule_description(rule) for rule in matches]
            hidden.append(job)
        else:
            visible.append(job)
    return visible, hidden
