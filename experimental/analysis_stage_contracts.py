"""Validation helpers for the staged Codex analysis POC.

These validators mirror the observable final outputs of analyzer.py. They are
strict about required fields, primitive types, enum values, score ranges, and
verbatim bullet preservation where the prompt requires it. They deliberately
do not try to judge subjective model quality.
"""

from __future__ import annotations

from typing import Any


class AnalysisStageContractError(RuntimeError):
    """Raised when one analysis stage violates its observable contract."""


def _dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalysisStageContractError(f"{path} must be an object.")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise AnalysisStageContractError(f"{path} must be a list.")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise AnalysisStageContractError(f"{path} must be a string.")
    return value


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise AnalysisStageContractError(f"{path} must be a boolean.")
    return value


def _score(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalysisStageContractError(
            f"{path} must be an integer from 0 to 100."
        )
    if not 0 <= value <= 100:
        raise AnalysisStageContractError(
            f"{path} must be between 0 and 100."
        )
    return value


def _require_keys(
    value: dict[str, Any],
    required: set[str],
    path: str,
) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise AnalysisStageContractError(
            f"{path} missing fields: {', '.join(missing)}."
        )


def _string_list(value: Any, path: str) -> list[str]:
    items = _list(value, path)
    for index, item in enumerate(items):
        _string(item, f"{path}[{index}]")
    return list(items)


def validate_keyword_result(candidate: Any) -> dict[str, Any]:
    result = _dict(candidate, "keyword")
    _require_keys(
        result,
        {"present", "missing", "keyword_match_score"},
        "keyword",
    )

    for index, raw in enumerate(_list(result["present"], "keyword.present")):
        item = _dict(raw, f"keyword.present[{index}]")
        _require_keys(
            item,
            {
                "keyword",
                "category",
                "importance",
                "found_in",
                "matched_resume_term",
                "match_type",
                "evidence_type",
                "match_reason",
            },
            f"keyword.present[{index}]",
        )
        for key in (
            "keyword",
            "matched_resume_term",
            "match_reason",
        ):
            _string(item[key], f"keyword.present[{index}].{key}")

        if item["category"] not in {
            "language",
            "framework",
            "tool",
            "concept",
            "soft_skill",
            "buzzword",
        }:
            raise AnalysisStageContractError(
                f"keyword.present[{index}].category is invalid."
            )
        if item["importance"] not in {"required", "preferred"}:
            raise AnalysisStageContractError(
                f"keyword.present[{index}].importance is invalid."
            )
        if item["found_in"] not in {
            "summary",
            "projects",
            "experience",
            "education",
            "skills",
            "raw_text",
        }:
            raise AnalysisStageContractError(
                f"keyword.present[{index}].found_in is invalid."
            )
        if item["match_type"] not in {
            "exact",
            "case_insensitive",
            "equivalent",
            "partial",
        }:
            raise AnalysisStageContractError(
                f"keyword.present[{index}].match_type is invalid."
            )
        if item["evidence_type"] not in {
            "direct",
            "transferable",
        }:
            raise AnalysisStageContractError(
                f"keyword.present[{index}].evidence_type is invalid."
            )

    for index, raw in enumerate(_list(result["missing"], "keyword.missing")):
        item = _dict(raw, f"keyword.missing[{index}]")
        _require_keys(
            item,
            {
                "keyword",
                "category",
                "importance",
                "suggested_section",
                "alternative_sections",
                "why_it_matters",
                "missing_reason",
            },
            f"keyword.missing[{index}]",
        )
        for key in (
            "keyword",
            "why_it_matters",
            "missing_reason",
        ):
            _string(item[key], f"keyword.missing[{index}].{key}")

        if item["category"] not in {
            "language",
            "framework",
            "tool",
            "concept",
            "soft_skill",
            "buzzword",
        }:
            raise AnalysisStageContractError(
                f"keyword.missing[{index}].category is invalid."
            )
        if item["importance"] not in {"required", "preferred"}:
            raise AnalysisStageContractError(
                f"keyword.missing[{index}].importance is invalid."
            )
        if item["suggested_section"] not in {
            "skills",
            "projects",
            "experience",
            "education",
        }:
            raise AnalysisStageContractError(
                f"keyword.missing[{index}].suggested_section is invalid."
            )
        alternatives = _string_list(
            item["alternative_sections"],
            f"keyword.missing[{index}].alternative_sections",
        )
        if any(
            value not in {
                "skills",
                "projects",
                "experience",
                "education",
                "summary",
            }
            for value in alternatives
        ):
            raise AnalysisStageContractError(
                f"keyword.missing[{index}].alternative_sections contains "
                "an invalid section."
            )

    _score(
        result["keyword_match_score"],
        "keyword.keyword_match_score",
    )
    return result


def validate_bullets_result(
    candidate: Any,
    *,
    expected_bullets: list[str] | None = None,
) -> dict[str, Any]:
    result = _dict(candidate, "bullets")
    _require_keys(
        result,
        {"bullets", "bullet_quality_avg"},
        "bullets",
    )

    actual_bullets: list[str] = []
    for index, raw in enumerate(_list(result["bullets"], "bullets.bullets")):
        item = _dict(raw, f"bullets.bullets[{index}]")
        _require_keys(
            item,
            {
                "source",
                "parent_title",
                "bullet_text",
                "has_action_verb",
                "has_specific_technology",
                "has_result_or_scope",
                "has_numeric_metric",
                "grammar_or_tense_issue",
                "level",
                "what_is_missing",
            },
            f"bullets.bullets[{index}]",
        )
        if item["source"] not in {"projects", "experience"}:
            raise AnalysisStageContractError(
                f"bullets.bullets[{index}].source is invalid."
            )
        for key in (
            "parent_title",
            "bullet_text",
            "grammar_or_tense_issue",
            "what_is_missing",
        ):
            _string(item[key], f"bullets.bullets[{index}].{key}")
        for key in (
            "has_action_verb",
            "has_specific_technology",
            "has_result_or_scope",
            "has_numeric_metric",
        ):
            _bool(item[key], f"bullets.bullets[{index}].{key}")
        if item["level"] not in {
            "L1_OK",
            "L2_BETTER",
            "L3_BEST",
        }:
            raise AnalysisStageContractError(
                f"bullets.bullets[{index}].level is invalid."
            )
        actual_bullets.append(item["bullet_text"])

    _score(
        result["bullet_quality_avg"],
        "bullets.bullet_quality_avg",
    )

    if expected_bullets is not None:
        if sorted(actual_bullets) != sorted(expected_bullets):
            raise AnalysisStageContractError(
                "bullets.bullet_text values must preserve every source bullet "
                "verbatim exactly once."
            )

    return result


def validate_jargon_result(candidate: Any) -> dict[str, Any]:
    result = _dict(candidate, "jargon")
    _require_keys(
        result,
        {
            "flags",
            "jargon_score",
            "role_appropriate_terms_removed_from_flags",
        },
        "jargon",
    )

    for index, raw in enumerate(_list(result["flags"], "jargon.flags")):
        item = _dict(raw, f"jargon.flags[{index}]")
        _require_keys(
            item,
            {
                "bullet_text",
                "term_used",
                "suggested_translation",
                "severity",
            },
            f"jargon.flags[{index}]",
        )
        for key in (
            "bullet_text",
            "term_used",
            "suggested_translation",
        ):
            _string(item[key], f"jargon.flags[{index}].{key}")
        if item["severity"] not in {
            "low",
            "medium",
            "high",
        }:
            raise AnalysisStageContractError(
                f"jargon.flags[{index}].severity is invalid."
            )

    _score(result["jargon_score"], "jargon.jargon_score")
    _string_list(
        result["role_appropriate_terms_removed_from_flags"],
        "jargon.role_appropriate_terms_removed_from_flags",
    )
    return result


def validate_structure_result(
    candidate: Any,
    *,
    actual_page_count: int | None,
) -> dict[str, Any]:
    result = _dict(candidate, "structure")
    _require_keys(
        result,
        {
            "page_count_estimate",
            "single_column_likely",
            "section_headings_present",
            "section_headings_missing",
            "three_thirds",
            "ats_red_flags",
            "structure_score",
        },
        "structure",
    )

    page_count = result["page_count_estimate"]
    if isinstance(page_count, bool) or not isinstance(page_count, int):
        raise AnalysisStageContractError(
            "structure.page_count_estimate must be an integer."
        )
    if page_count < 1:
        raise AnalysisStageContractError(
            "structure.page_count_estimate must be at least 1."
        )

    if (
        actual_page_count is not None
        and page_count != actual_page_count
    ):
        raise AnalysisStageContractError(
            "analyzer.py must preserve the supplied rendered page count."
        )

    _bool(
        result["single_column_likely"],
        "structure.single_column_likely",
    )
    _string_list(
        result["section_headings_present"],
        "structure.section_headings_present",
    )
    _string_list(
        result["section_headings_missing"],
        "structure.section_headings_missing",
    )

    thirds = _dict(
        result["three_thirds"],
        "structure.three_thirds",
    )
    required_thirds = {
        "top_third_has_name",
        "top_third_has_contact",
        "top_third_has_summary_or_featured",
        "middle_third_has_projects_or_experience",
        "bottom_third_has_skills_keywords",
    }
    _require_keys(
        thirds,
        required_thirds,
        "structure.three_thirds",
    )
    for key in required_thirds:
        _bool(
            thirds[key],
            f"structure.three_thirds.{key}",
        )

    for index, raw in enumerate(
        _list(result["ats_red_flags"], "structure.ats_red_flags")
    ):
        item = _dict(raw, f"structure.ats_red_flags[{index}]")
        _require_keys(
            item,
            {"issue", "evidence"},
            f"structure.ats_red_flags[{index}]",
        )
        _string(
            item["issue"],
            f"structure.ats_red_flags[{index}].issue",
        )
        _string(
            item["evidence"],
            f"structure.ats_red_flags[{index}].evidence",
        )

    _score(
        result["structure_score"],
        "structure.structure_score",
    )

    if actual_page_count is not None:
        if result.get("page_count_source") != "rendered_document":
            raise AnalysisStageContractError(
                "structure.page_count_source must be 'rendered_document' "
                "when analyzer.py receives an actual page count."
            )

    return result


def validate_degree_result(candidate: Any) -> dict[str, Any]:
    result = _dict(candidate, "degree")
    _require_keys(
        result,
        {
            "student_degree",
            "jd_title",
            "title_on_suggested_list",
            "matched_against",
            "fit_commentary",
            "degree_alignment_score",
        },
        "degree",
    )
    for key in (
        "student_degree",
        "jd_title",
        "matched_against",
        "fit_commentary",
    ):
        _string(result[key], f"degree.{key}")
    _bool(
        result["title_on_suggested_list"],
        "degree.title_on_suggested_list",
    )
    _score(
        result["degree_alignment_score"],
        "degree.degree_alignment_score",
    )
    return result


def validate_summary_result(candidate: Any) -> str:
    text = _string(candidate, "summary").strip()
    if not text:
        raise AnalysisStageContractError(
            "summary must not be empty."
        )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]
    bullets = [
        line
        for line in lines
        if line.startswith(("- ", "* "))
    ]
    if len(lines) != 3 or len(bullets) != 3:
        raise AnalysisStageContractError(
            "summary must contain exactly 3 non-empty Markdown bullet lines."
        )
    return text
