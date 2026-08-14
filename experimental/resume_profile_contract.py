"""Strict resume-profile contract validation for the Codex POC.

The contract mirrors RESUME_PROFILE_PROMPT exactly. Validation is fail-closed:
no missing fields are filled, no extra fields are ignored, and values are not
coerced into the requested types.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TOP_LEVEL_FIELDS = {
    "name",
    "contact",
    "summary",
    "education",
    "projects",
    "experience",
    "skills",
}
CONTACT_FIELDS = {
    "email",
    "phone",
    "linkedin",
    "github",
    "portfolio",
}
EDUCATION_FIELDS = {
    "school",
    "degree",
    "graduation_date",
    "courses",
}
PROJECT_FIELDS = {
    "title",
    "date",
    "bullets",
}
EXPERIENCE_FIELDS = {
    "title",
    "company",
    "date",
    "bullets",
}
SKILL_FIELDS = {
    "languages",
    "frameworks",
    "tools",
    "concepts",
    "platforms",
}


class ResumeProfileContractError(RuntimeError):
    """Raised when a candidate profile violates the existing resume schema."""


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResumeProfileContractError(f"{path} must be an object.")
    return value


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    path: str,
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)

    if not missing and not unexpected:
        return

    details: list[str] = []
    if missing:
        details.append("missing fields: " + ", ".join(missing))
    if unexpected:
        details.append("unexpected fields: " + ", ".join(unexpected))

    raise ResumeProfileContractError(
        f"{path} does not match the required contract ("
        + "; ".join(details)
        + ")."
    )


def _require_string(value: Any, path: str) -> None:
    if not isinstance(value, str):
        raise ResumeProfileContractError(f"{path} must be a string.")


def _require_string_list(value: Any, path: str) -> None:
    if not isinstance(value, list):
        raise ResumeProfileContractError(
            f"{path} must be a list of strings."
        )
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ResumeProfileContractError(
                f"{path}[{index}] must be a string."
            )


def _validate_record_list(
    value: Any,
    *,
    path: str,
    fields: set[str],
    scalar_fields: tuple[str, ...],
    list_fields: tuple[str, ...],
) -> None:
    if not isinstance(value, list):
        raise ResumeProfileContractError(
            f"{path} must be a list of objects."
        )

    for index, raw_item in enumerate(value):
        item_path = f"{path}[{index}]"
        item = _require_dict(raw_item, item_path)
        _require_exact_keys(item, fields, item_path)

        for field in scalar_fields:
            _require_string(item[field], f"{item_path}.{field}")

        for field in list_fields:
            _require_string_list(item[field], f"{item_path}.{field}")


def validate_resume_profile_contract(
    candidate: Any,
) -> dict[str, Any]:
    """Validate and return a deep copy of the exact resume-profile contract."""
    profile = _require_dict(candidate, "resume_profile")
    _require_exact_keys(
        profile,
        TOP_LEVEL_FIELDS,
        "resume_profile",
    )

    _require_string(profile["name"], "resume_profile.name")
    _require_string(profile["summary"], "resume_profile.summary")

    contact = _require_dict(
        profile["contact"],
        "resume_profile.contact",
    )
    _require_exact_keys(
        contact,
        CONTACT_FIELDS,
        "resume_profile.contact",
    )
    for field in sorted(CONTACT_FIELDS):
        _require_string(
            contact[field],
            f"resume_profile.contact.{field}",
        )

    _validate_record_list(
        profile["education"],
        path="resume_profile.education",
        fields=EDUCATION_FIELDS,
        scalar_fields=(
            "school",
            "degree",
            "graduation_date",
        ),
        list_fields=("courses",),
    )
    _validate_record_list(
        profile["projects"],
        path="resume_profile.projects",
        fields=PROJECT_FIELDS,
        scalar_fields=("title", "date"),
        list_fields=("bullets",),
    )
    _validate_record_list(
        profile["experience"],
        path="resume_profile.experience",
        fields=EXPERIENCE_FIELDS,
        scalar_fields=("title", "company", "date"),
        list_fields=("bullets",),
    )

    skills = _require_dict(
        profile["skills"],
        "resume_profile.skills",
    )
    _require_exact_keys(
        skills,
        SKILL_FIELDS,
        "resume_profile.skills",
    )
    for field in sorted(SKILL_FIELDS):
        _require_string_list(
            skills[field],
            f"resume_profile.skills.{field}",
        )

    return deepcopy(profile)
