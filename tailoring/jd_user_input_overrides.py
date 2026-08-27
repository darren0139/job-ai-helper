"""Deterministic Application Session JD metadata and requirement overrides.

The helpers in this module intentionally operate only on an already-produced
analysis report.  They neither call a model nor perform persistence or Chroma
work.  A user may explicitly mark an exact JD requirement as preferred when a
source JD's section structure is ambiguous.  A non-matching user entry is an
application-local supplemental preferred requirement.  Neither case changes
the shared JD or creates résumé evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from analysis_stability import build_stable_analysis
from analysis_stability.stable_evidence_scoring import (
    build_deterministic_keyword_match,
    canonicalise_requirements,
    compute_deterministic_alignment,
)


JD_USER_OVERRIDE_POLICY_VERSION = "application-session-jd-user-overrides-v2"
PREFERRED_REQUIREMENTS_LABEL = "Preferred / bonus / optional JD requirements"
PREFERRED_REQUIREMENTS_HELP = (
    "Add preferred, bonus, or optional requirements for this application. "
    "Matching JD requirements are marked preferred; new entries are added "
    "only to this application."
)
_MATCH_POLICY = "normalized_whole_requirement_exact"
_APPLICATION_LOCAL_REQUIREMENT_SOURCE = (
    "application_user_input.preferred_requirement"
)
_SOURCE_REQUIREMENT_FIELDS = (
    "deal_breakers",
    "required_skills",
    "responsibilities",
    "soft_skills",
    "tools_technologies",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _requirement_key(value: Any) -> str:
    """Normalise presentation only; never infer semantic equivalence."""
    text = _clean(value).casefold()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^[\-*•]+\s*", "", text)
    text = re.sub(r"^\d+[.)]\s*", "", text)
    return text.strip(" \t\r\n.;,:")


def requirement_override_key(value: Any) -> str:
    """Return the v2 exact whole-requirement key for cross-flow callers."""
    return _requirement_key(value)


def normalise_requirement_override_lines(
    value: str | list[str] | tuple[str, ...] | None,
) -> list[str]:
    """Return de-duplicated, one-full-requirement-per-line overrides."""
    if value is None:
        raw_items: list[Any] = []
    elif isinstance(value, str):
        raw_items = value.splitlines()
    else:
        raw_items = list(value)

    result: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        text = _clean(raw_item)
        text = re.sub(r"^[\-*•]+\s*", "", text)
        text = re.sub(r"^\d+[.)]\s*", "", text).strip()
        key = _requirement_key(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def preferred_requirement_override_cache_identity(
    preferred_requirements: str | list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    """Return order-independent semantic inputs for analysis-cache identity."""
    return {
        "policy_version": JD_USER_OVERRIDE_POLICY_VERSION,
        "match_policy": _MATCH_POLICY,
        "preferred_requirement_override_keys": sorted(
            {
                key
                for item in normalise_requirement_override_lines(
                    preferred_requirements
                )
                if (key := _requirement_key(item))
            }
        ),
    }


def apply_preferred_requirement_overrides_to_profile(
    jd_profile: dict[str, Any] | None,
    preferred_requirements: str | list[str] | tuple[str, ...] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Move exact profile requirements to preferred without fuzzy deletion."""
    profile = deepcopy(jd_profile or {})
    overrides = normalise_requirement_override_lines(preferred_requirements)
    override_by_key = {_requirement_key(item): item for item in overrides}
    matched_source_items: list[dict[str, str]] = []
    matched_keys: set[str] = set()

    for field_name in _SOURCE_REQUIREMENT_FIELDS:
        current = profile.get(field_name, []) or []
        if not isinstance(current, list):
            continue
        kept: list[Any] = []
        for item in current:
            key = _requirement_key(item)
            if key and key in override_by_key:
                matched_keys.add(key)
                matched_source_items.append(
                    {"field": field_name, "text": _clean(item)}
                )
                continue
            kept.append(item)
        profile[field_name] = kept

    preferred = profile.get("preferred_skills", []) or []
    preferred_values = preferred if isinstance(preferred, list) else []
    preferred_output: list[Any] = []
    preferred_seen: set[str] = set()
    for item in [*preferred_values, *overrides]:
        key = _requirement_key(item)
        if not key or key in preferred_seen:
            continue
        preferred_seen.add(key)
        preferred_output.append(item)
    profile["preferred_skills"] = preferred_output

    unmatched = [
        item for item in overrides if _requirement_key(item) not in matched_keys
    ]
    profile["user_requirement_importance_overrides"] = {
        **preferred_requirement_override_cache_identity(overrides),
        "preferred": deepcopy(overrides),
    }
    return profile, {
        **preferred_requirement_override_cache_identity(overrides),
        "preferred_requirement_overrides": deepcopy(overrides),
        "matched_source_items": matched_source_items,
        "matched_override_count": len(matched_keys),
        "unmatched_preferred_overrides": unmatched,
    }


def _restore_original_metadata(
    report: dict[str, Any], profile: dict[str, Any]
) -> dict[str, str]:
    """Restore extracted labels before applying replacement display metadata."""
    prior_inputs = (report.get("meta") or {}).get("jd_user_inputs") or {}
    original = prior_inputs.get("original_extracted_metadata") or {}
    values = {
        "company": _clean(
            original["company"] if "company" in original else profile.get("company")
        ),
        "job_title": _clean(
            original["job_title"]
            if "job_title" in original
            else profile.get("job_title")
        ),
        "location": _clean(
            original["location"] if "location" in original else profile.get("location")
        ),
    }
    profile.update(values)
    return values


def _original_extracted_profile(report: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable pre-override JD profile from a reused report."""
    prior_inputs = (report.get("meta") or {}).get("jd_user_inputs") or {}
    original = prior_inputs.get("original_extracted_jd_profile")
    if isinstance(original, dict) and original:
        return deepcopy(original)
    return deepcopy(report.get("jd_profile") or {})


def canonical_jd_profile_for_application_session(
    report: dict[str, Any],
) -> dict[str, Any]:
    """Return the extracted JD profile permitted to enter shared JD storage.

    Application Session metadata, preferred-importance corrections, and their
    provenance belong to the report only.  They must never become a shared
    canonical JD version merely because this application happens to reuse its
    raw posting text.
    """
    profile = _original_extracted_profile(report)
    profile.pop("user_requirement_importance_overrides", None)
    return profile


def _rebuild_stable_analysis(
    report: dict[str, Any],
    profile: dict[str, Any],
    *,
    raw_jd_text: str,
    raw_resume_text: str,
    keyword_match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_stable_analysis(
        jd_profile=profile,
        keyword_match=deepcopy(
            keyword_match
            if isinstance(keyword_match, dict)
            else report.get("keyword_match") or {}
        ),
        raw_jd_text=_clean(raw_jd_text),
        raw_resume_text=_clean(raw_resume_text),
        resume_profile=deepcopy(report.get("resume_profile") or {}),
        bullet_quality_score=(report.get("bullets") or {}).get(
            "bullet_quality_avg", 0
        ),
        structure_score=(report.get("structure") or {}).get("structure_score", 0),
    )


def _apply_canonical_preferred_overrides(
    stable_analysis: dict[str, Any],
    preferred_requirements: list[str],
) -> tuple[dict[str, Any], list[str], list[dict[str, str]]]:
    """Apply exact user preference to matching canonical rows.

    Stable canonicalisation can split one full JD requirement into atomic
    requirement rows.  The user supplies a whole requirement, so a match may
    be against either the row's display text or its immutable parent text.
    This is still an exact normalised comparison: it never uses similarity or
    partial-token matching.
    """
    stable = deepcopy(stable_analysis or {})
    rows = deepcopy(stable.get("canonical_requirements", []) or [])
    override_by_key = {
        key: item
        for item in preferred_requirements
        if (key := _requirement_key(item))
    }
    matched_keys: set[str] = set()
    matched_rows: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_keys = {
            key
            for value in (
                row.get("text") or row.get("requirement_text"),
                row.get("parent_text"),
                *(row.get("variants") or []),
            )
            if (key := _requirement_key(value))
        }
        row_override_keys = row_keys & set(override_by_key)
        if not row_override_keys:
            continue
        row["importance"] = "preferred"
        row["importance_source"] = "user_override"
        row["user_importance_override"] = {
            "policy_version": JD_USER_OVERRIDE_POLICY_VERSION,
            "importance": "preferred",
            "match_policy": _MATCH_POLICY,
            "scope": "application_local",
        }
        matched_keys.update(row_override_keys)
        matched_rows.append(
            {
                "requirement_id": _clean(row.get("requirement_id")),
                "text": _clean(row.get("text")),
                "parent_text": _clean(row.get("parent_text")),
            }
        )

    stable["canonical_requirements"] = rows
    # The caller appends any supplemental rows before calculating the single
    # effective application-local score.
    return (
        stable,
        [
            item
            for item in preferred_requirements
            if _requirement_key(item) in matched_keys
        ],
        matched_rows,
    )


def apply_preferred_requirement_overrides_to_canonical_rows(
    canonical_requirements: list[dict[str, Any]] | None,
    preferred_requirements: str | list[str] | tuple[str, ...] | None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    """Apply the v2 exact-match rule to an already canonicalised scope.

    This is the shared, deliberately narrow boundary for Application Sessions
    and Tailor Resume.  It changes only effective application-local
    importance; it never changes a shared JD profile or raw JD text.
    """
    stable, matches, matched_rows = _apply_canonical_preferred_overrides(
        {"canonical_requirements": deepcopy(canonical_requirements or [])},
        normalise_requirement_override_lines(preferred_requirements),
    )
    return (
        deepcopy(stable.get("canonical_requirements") or []),
        matches,
        matched_rows,
    )


def tag_application_local_supplemental_requirement_row(
    row: dict[str, Any],
    requirement: str,
) -> dict[str, Any]:
    """Attach v2 application-local provenance to one scored requirement row."""
    output = deepcopy(row)
    sources = list(output.get("sources") or [])
    if _APPLICATION_LOCAL_REQUIREMENT_SOURCE not in sources:
        sources.append(_APPLICATION_LOCAL_REQUIREMENT_SOURCE)
    output.update(
        {
            "importance": "preferred",
            "importance_source": "user_supplied",
            "sources": sources,
            "application_requirement_scope": "application_local",
            "canonical_shared": False,
            "application_requirement_key": _requirement_key(requirement),
            "user_supplied_requirement": _clean(requirement),
            "user_importance_override": {
                "policy_version": JD_USER_OVERRIDE_POLICY_VERSION,
                "importance": "preferred",
                "match_policy": _MATCH_POLICY,
                "scope": "application_local",
                "provenance": "user_supplied",
            },
        }
    )
    return output


def application_local_supplemental_canonical_requirements(
    supplemental_requirements: str | list[str] | tuple[str, ...] | None,
) -> list[dict[str, Any]]:
    """Build v2 supplemental requirement rows without changing a shared JD.

    Raw JD text is intentionally empty here.  The shared scorer's normal raw
    JD precedence therefore cannot discard an application-local input before
    it becomes part of the effective requirement scope.
    """
    rows: list[dict[str, Any]] = []
    for requirement in normalise_requirement_override_lines(
        supplemental_requirements
    ):
        canonical = canonicalise_requirements(
            jd_profile={"preferred_skills": [requirement]},
            raw_jd_text="",
        )
        rows.extend(
            tag_application_local_supplemental_requirement_row(row, requirement)
            for row in canonical.get("requirements", []) or []
            if isinstance(row, dict)
        )
    return rows


def build_effective_application_local_requirement_scope(
    canonical_requirements: list[dict[str, Any]] | None,
    preferred_requirements: str | list[str] | tuple[str, ...] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the one effective v2 JD scope used only by the current flow.

    The returned supplemental rows are canonicalised deterministically but
    deliberately remain outside the shared JD profile, raw JD, and library
    identity.  Callers that score a résumé may replace these unscored rows
    with equivalently identified scored rows before calculating alignment.
    """
    overrides = sorted(
        normalise_requirement_override_lines(preferred_requirements),
        key=_requirement_key,
    )
    rows, canonical_matches, matched_rows = (
        apply_preferred_requirement_overrides_to_canonical_rows(
            canonical_requirements,
            overrides,
        )
    )
    canonical_match_keys = {
        _requirement_key(item)
        for item in canonical_matches
        if _requirement_key(item)
    }
    supplements = [
        item
        for item in overrides
        if _requirement_key(item) not in canonical_match_keys
    ]
    supplemental_rows = application_local_supplemental_canonical_requirements(
        supplements
    )
    covered_supplement_keys = {
        _requirement_key(row.get("user_supplied_requirement"))
        for row in supplemental_rows
        if isinstance(row, dict)
        and _clean(row.get("application_requirement_scope"))
        == "application_local"
    }
    expected_supplement_keys = {
        _requirement_key(item) for item in supplements if _requirement_key(item)
    }
    if covered_supplement_keys != expected_supplement_keys:
        raise ValueError(
            "Application-local preferred requirements could not be added to "
            "the effective canonical requirement scope."
        )
    return [*rows, *supplemental_rows], {
        "policy_version": JD_USER_OVERRIDE_POLICY_VERSION,
        "match_policy": _MATCH_POLICY,
        "preferred_requirement_overrides": deepcopy(overrides),
        "override_identity": preferred_requirement_override_cache_identity(
            overrides
        ),
        "canonical_preferred_matches": deepcopy(canonical_matches),
        "matched_canonical_requirement_rows": deepcopy(matched_rows),
        "supplemental_preferred_requirements": deepcopy(supplements),
        "unmatched_preferred_overrides": [],
    }


def _application_local_supplemental_rows(
    report: dict[str, Any],
    supplemental_requirements: list[str],
    *,
    raw_resume_text: str,
) -> list[dict[str, Any]]:
    """Score one explicit supplemental requirement at a time.

    This deliberately reuses the stable scorer for each requirement, but with
    no raw JD text.  It keeps supplemental entries out of the immutable raw
    JD/profile while retaining ordinary deterministic evidence, validation,
    taxonomy-cap, and scoring semantics.  Processing each input separately
    prevents cross-entry similarity merging.
    """
    rows: list[dict[str, Any]] = []
    for requirement in supplemental_requirements:
        supplemental_canonicalisation = canonicalise_requirements(
            jd_profile={"preferred_skills": [requirement]},
            raw_jd_text="",
        )
        supplemental_keyword_match = build_deterministic_keyword_match(
            requirements=deepcopy(
                supplemental_canonicalisation.get("requirements") or []
            ),
            acronym_map=deepcopy(
                supplemental_canonicalisation.get("acronym_map") or {}
            ),
            resume_profile=deepcopy(report.get("resume_profile") or {}),
            raw_resume_text=raw_resume_text,
        )
        supplemental_analysis = _rebuild_stable_analysis(
            report,
            {"preferred_skills": [requirement]},
            raw_jd_text="",
            raw_resume_text=raw_resume_text,
            keyword_match=supplemental_keyword_match,
        )
        for source_row in (
            supplemental_analysis.get("canonical_requirements", []) or []
        ):
            if not isinstance(source_row, dict):
                continue
            rows.append(
                tag_application_local_supplemental_requirement_row(
                    source_row,
                    requirement,
                )
            )
    return rows


def effective_stable_input_fingerprint(
    base_fingerprint: str, preferred_requirements: list[str]
) -> str:
    payload = {
        "base_stable_input_fingerprint": _clean(base_fingerprint),
        "override_identity": preferred_requirement_override_cache_identity(
            preferred_requirements
        ),
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _had_prior_override(report: dict[str, Any]) -> bool:
    prior_inputs = (report.get("meta") or {}).get("jd_user_inputs") or {}
    if normalise_requirement_override_lines(
        prior_inputs.get("preferred_requirement_overrides")
    ):
        return True
    return bool(
        (report.get("stable_analysis") or {}).get(
            "jd_user_override_policy_version"
        )
    )


def apply_application_session_jd_user_inputs(
    report: dict[str, Any],
    *,
    raw_jd_text: str,
    raw_resume_text: str,
    company: str = "",
    job_title: str = "",
    location: str = "",
    source_url: str = "",
    preferred_requirements: str | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Apply deterministic user inputs to an already-produced report.

    The result is a deep copy.  Metadata is display/persistence context; only
    exact preferred overrides alter the deterministic requirement importance.
    Removing a prior override rebuilds the normal stable analysis so a derived
    preferred classification can never linger in a reused report.
    """
    output = deepcopy(report or {})
    original_profile = _original_extracted_profile(output)
    original_metadata = _restore_original_metadata(output, original_profile)
    had_prior_override = _had_prior_override(output)
    # Input order is presentation-only.  Persisted effective requirements and
    # derived stable results must match the order-independent cache identity.
    canonical_input_order = sorted(
        normalise_requirement_override_lines(preferred_requirements),
        key=_requirement_key,
    )
    profile, diagnostics = apply_preferred_requirement_overrides_to_profile(
        original_profile, canonical_input_order
    )
    overrides = diagnostics["preferred_requirement_overrides"]

    if _clean(company):
        profile["company"] = _clean(company)
    if _clean(job_title):
        profile["job_title"] = _clean(job_title)
    if _clean(location):
        profile["location"] = _clean(location)
    output["jd_profile"] = profile
    output["raw_jd_text"] = _clean(raw_jd_text)

    canonical_matches: list[str] = []
    matched_canonical_rows: list[dict[str, str]] = []
    supplemental_requirements: list[str] = []
    if overrides or had_prior_override:
        rebuilt = _rebuild_stable_analysis(
            output,
            profile,
            raw_jd_text=raw_jd_text,
            raw_resume_text=raw_resume_text,
        )
        if overrides:
            base_fingerprint = _clean(rebuilt.get("input_fingerprint"))
            (
                overridden_rows,
                canonical_matches,
                matched_canonical_rows,
            ) = apply_preferred_requirement_overrides_to_canonical_rows(
                rebuilt.get("canonical_requirements") or [],
                overrides,
            )
            rebuilt["canonical_requirements"] = overridden_rows
            canonical_match_keys = {
                _requirement_key(item)
                for item in canonical_matches
                if _requirement_key(item)
            }
            supplemental_requirements = [
                item
                for item in overrides
                if _requirement_key(item) not in canonical_match_keys
            ]
            supplemental_rows = _application_local_supplemental_rows(
                output,
                supplemental_requirements,
                raw_resume_text=raw_resume_text,
            )
            covered_supplement_keys = {
                _requirement_key(row.get("user_supplied_requirement"))
                for row in supplemental_rows
                if isinstance(row, dict)
                and _clean(row.get("application_requirement_scope"))
                == "application_local"
            }
            expected_supplement_keys = {
                _requirement_key(item)
                for item in supplemental_requirements
                if _requirement_key(item)
            }
            if covered_supplement_keys != expected_supplement_keys:
                raise ValueError(
                    "Application-local preferred requirements could not be "
                    "added to the effective stable-analysis scope."
                )
            rebuilt["canonical_requirements"] = [
                *(rebuilt.get("canonical_requirements", []) or []),
                *supplemental_rows,
            ]
            rebuilt.setdefault("canonicalisation_debug", {})[
                "application_local_supplemental_requirements"
            ] = [
                {
                    "text": _clean(item),
                    "application_requirement_key": _requirement_key(item),
                    "source": _APPLICATION_LOCAL_REQUIREMENT_SOURCE,
                }
                for item in supplemental_requirements
            ]
            rebuilt.update(
                compute_deterministic_alignment(
                    rebuilt["canonical_requirements"],
                    bullet_quality_score=(output.get("bullets") or {}).get(
                        "bullet_quality_avg", 0
                    ),
                    structure_score=(output.get("structure") or {}).get(
                        "structure_score", 0
                    ),
                )
            )
            rebuilt["base_stable_input_fingerprint"] = base_fingerprint
            rebuilt["input_fingerprint"] = effective_stable_input_fingerprint(
                base_fingerprint, overrides
            )
            rebuilt["jd_user_override_policy_version"] = (
                JD_USER_OVERRIDE_POLICY_VERSION
            )
        output["stable_analysis"] = rebuilt

    output.setdefault("meta", {})["jd_user_inputs"] = {
        "policy_version": JD_USER_OVERRIDE_POLICY_VERSION,
        "company": _clean(company),
        "job_title": _clean(job_title),
        "location": _clean(location),
        "source_url": _clean(source_url),
        "preferred_requirement_overrides": deepcopy(overrides),
        "override_identity": preferred_requirement_override_cache_identity(
            overrides
        ),
        "original_extracted_metadata": original_metadata,
        "original_extracted_jd_profile": deepcopy(original_profile),
        "matched_source_items": deepcopy(diagnostics["matched_source_items"]),
        "matched_canonical_requirement_rows": matched_canonical_rows,
        # Every well-formed input is either an exact canonical reclassification
        # or an accepted application-local supplemental requirement.
        "unmatched_preferred_overrides": [],
        "canonical_preferred_matches": deepcopy(canonical_matches),
        "supplemental_preferred_requirements": deepcopy(
            supplemental_requirements
        ),
        "match_policy": _MATCH_POLICY,
    }
    return output
