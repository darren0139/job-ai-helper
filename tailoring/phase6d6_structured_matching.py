"""Phase 6D.6 deterministic matching for structured résumé facts.

This module fixes a narrow but important stability problem: an LLM may sometimes
miss facts that already exist in structured résumé fields, such as programming
languages or education. Phase 6D.6 verifies those facts locally and
deterministically.

It does not consume Phase 6D.5 RAG candidates and does not allow RAG to affect
scoring.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import Any

STRUCTURED_MATCH_VERSION = "phase6d6-structured-match-v1.2"

_LABEL_ORDER = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}
_MATCH_VALUES = {
    "none": 0.0,
    "weak": 0.20,
    "transferable": 0.55,
    "direct": 1.0,
}

_SUBJECTIVE_CUES = re.compile(
    r"\b(?:passion|passionate|enthusiasm|enthusiastic|interest|interested|"
    r"motivated|motivation|eager|willingness|enjoy|love|curious|curiosity)\b",
    flags=re.IGNORECASE,
)

_PROGRAMMING_LIST = re.compile(
    r"\b(?:experience\s+)?(?:programming|coding|proficiency)\s+"
    r"(?:in|with)\s+(?P<tail>.+)$",
    flags=re.IGNORECASE,
)

_EXACT_SKILL_REQUIREMENT = re.compile(
    r"^(?:experience|proficiency|familiarity|knowledge|skill|skills|"
    r"competence|competency)\s+(?:using|with|in|of)\s+(?P<tail>.+)$",
    flags=re.IGNORECASE,
)

_EDUCATION_LEVEL = re.compile(
    r"\b(?:diploma|degree|bachelor|bachelors|master|masters|phd|doctorate)\b",
    flags=re.IGNORECASE,
)

_CERTIFICATION_REQUIREMENT = re.compile(
    r"\b(?:certifications?|certified|certificates?)\b",
    flags=re.IGNORECASE,
)

_TRAILING_QUALIFIERS = re.compile(
    r"\s+(?:is|are|would\s+be|will\s+be)\s+"
    r"(?:required|preferred|advantageous|a\s+plus)\b.*$",
    flags=re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise(value: Any) -> str:
    text = _clean(value).lower()
    text = (
        text.replace("–", "-")
        .replace("—", "-")
        .replace("‑", "-")
        .replace("&", " and ")
    )
    text = re.sub(r"[^a-z0-9+#.-]+", " ", text)
    text = " ".join(text.split()).strip(" .,-")

    aliases = {
        "restful api": "rest api",
        "restful apis": "rest api",
        "rest api": "rest api",
        "rest apis": "rest api",
        "postgres": "postgresql",
        "amazon web services": "aws",
        "google cloud platform": "gcp",
        "google cloud": "gcp",
        "row-level security": "row level security",
        "rls": "row level security",
        "relational databases": "relational database",
        "cloud platforms": "cloud platform",
    }
    return aliases.get(text, text)


def _stable_evidence_id(section: str, text: str) -> str:
    material = f"{section}|{_normalise(text)}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"ev_{digest}"


def _structured_rows(
    resume_profile: dict[str, Any] | None,
) -> list[dict[str, str]]:
    profile = resume_profile or {}
    rows: list[dict[str, str]] = []

    skills = profile.get("skills", {}) or {}
    if isinstance(skills, dict):
        for category, values in skills.items():
            for index, value in enumerate(values or []):
                text = _clean(value)
                if not text:
                    continue
                rows.append(
                    {
                        "section": "skills",
                        "category": str(category),
                        "text": text,
                        "normalised": _normalise(text),
                        "source": f"resume_profile.skills.{category}[{index}]",
                    }
                )

    for index, item in enumerate(profile.get("education", []) or []):
        if not isinstance(item, dict):
            continue
        degree = _clean(item.get("degree"))
        school = _clean(item.get("school"))
        text = " — ".join(part for part in (degree, school) if part)
        if text:
            rows.append(
                {
                    "section": "education",
                    "category": "education",
                    "text": text,
                    "normalised": _normalise(text),
                    "source": f"resume_profile.education[{index}]",
                }
            )

    for index, item in enumerate(profile.get("certifications", []) or []):
        if isinstance(item, dict):
            name = _clean(item.get("name") or item.get("title"))
            issuer = _clean(item.get("issuer"))
            text = " — ".join(part for part in (name, issuer) if part)
        else:
            text = _clean(item)
        if text:
            text = f"Certification: {text}"
            rows.append(
                {
                    "section": "certification",
                    "category": "certification",
                    "text": text,
                    "normalised": _normalise(text),
                    "source": f"resume_profile.certifications[{index}]",
                }
            )

    return rows


def _derived_skill_keys(rows: list[dict[str, str]]) -> set[str]:
    keys = {
        row["normalised"]
        for row in rows
        if row.get("normalised")
    }

    relational_products = {
        "postgresql",
        "mysql",
        "sqlite",
        "mariadb",
        "oracle database",
        "microsoft sql server",
        "sql server",
    }
    cloud_products = {
        "aws",
        "azure",
        "gcp",
    }

    if keys & relational_products:
        keys.add("relational database")
    if keys & cloud_products:
        keys.add("cloud platform")

    return keys


def _split_alternatives(tail: str) -> tuple[list[str], str]:
    value = _TRAILING_QUALIFIERS.sub("", _clean(tail)).strip(" .;:")
    value = re.sub(
        r"^(?:one\s+or\s+more\s+of|any\s+of|languages?\s+such\s+as)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )

    group_mode = "any" if re.search(r"\bor\b", value, flags=re.IGNORECASE) else "all"
    parts = re.split(r"\s*,\s*|\s+\bor\b\s+|\s+\band\b\s+", value, flags=re.IGNORECASE)

    cleaned: list[str] = []
    for part in parts:
        item = _clean(part).strip(" .;:")
        item = re.sub(
            r"^(?:or|and)\s+",
            "",
            item,
            flags=re.IGNORECASE,
        )
        if not item:
            continue
        if re.search(r"\brelated\s+field\b", item, flags=re.IGNORECASE):
            continue
        if len(item) > 60:
            continue
        cleaned.append(item)

    return list(dict.fromkeys(cleaned)), group_mode


def _evidence_reference(row: dict[str, str], reason: str) -> dict[str, str]:
    return {
        "evidence_id": _stable_evidence_id(
            row.get("section", ""),
            row.get("text", ""),
        ),
        "section": row.get("section", ""),
        "text": row.get("text", ""),
        "source": row.get("source", ""),
        "reason": reason,
        "evidence_similarity": "1.000",
    }


def _match_collaborative_system_integration(
    requirement_text: str,
    resume_profile: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Link independently evidenced integration work as transferable only."""
    requirement = _normalise(requirement_text)
    integration = re.compile(r"\b(?:integrat(?:e|ed|es|ing|ion)|end to end)\b")
    collaboration = re.compile(r"\b(?:collaborat\w*|team|teams|work closely)\b")
    system_context = re.compile(
        r"\b(?:systems?|software|applications?|code|engine|workflows?)\b"
    )
    integration_action = re.compile(
        r"\b(?:collaborat\w*|work closely)\b.{0,180}\b"
        r"(?:integrat(?:e|ed|es|ing|ion)|end to end)\b|"
        r"\b(?:support|perform|deliver|execute)\b.{0,140}\b"
        r"(?:systems?|software) integration\b"
    )
    if not (
        integration_action.search(requirement)
        and collaboration.search(requirement)
        and system_context.search(requirement)
    ):
        return None

    profile = resume_profile or {}
    for section in ("projects", "experience"):
        for item_index, item in enumerate(profile.get(section, []) or []):
            if not isinstance(item, dict):
                continue
            for bullet_index, bullet in enumerate(item.get("bullets", []) or []):
                text = _clean(bullet)
                normalised = _normalise(text)
                if not (
                    integration.search(normalised)
                    and collaboration.search(normalised)
                    and system_context.search(normalised)
                ):
                    continue
                evidence_row = {
                    "section": section,
                    "text": text,
                    "source": (
                        f"resume_profile.{section}[{item_index}]"
                        f".bullets[{bullet_index}]"
                    ),
                }
                return {
                    "kind": "collaborative_system_integration_transfer",
                    "group_mode": "behavioral_transfer",
                    "required_terms": ["collaboration", "system integration"],
                    "matched_terms": ["collaboration", "system integration"],
                    "matched_keyword": "collaborative system integration",
                    "match_label": "transferable",
                    "evidence": _evidence_reference(
                        evidence_row,
                        (
                            "A project or experience bullet explicitly records "
                            "collaborative system-integration work. The domain is "
                            "different, so the evidence remains transferable."
                        ),
                    ),
                }
    return None


def _match_programming_languages(
    requirement_text: str,
    rows: list[dict[str, str]],
) -> dict[str, Any] | None:
    match = _PROGRAMMING_LIST.search(requirement_text)
    if not match:
        return None

    alternatives, group_mode = _split_alternatives(match.group("tail"))
    if not 1 <= len(alternatives) <= 10:
        return None

    language_rows = [
        row
        for row in rows
        if _normalise(row.get("category")) in {
            "language",
            "languages",
            "programming language",
            "programming languages",
        }
    ]
    row_by_key = {
        row["normalised"]: row
        for row in language_rows
        if row.get("normalised")
    }

    required_keys = [_normalise(item) for item in alternatives]
    matched_keys = [key for key in required_keys if key in row_by_key]

    supported = (
        bool(matched_keys)
        if group_mode == "any"
        else bool(required_keys) and len(matched_keys) == len(required_keys)
    )
    if not supported:
        return None

    matched_rows = [row_by_key[key] for key in matched_keys]
    evidence_text = ", ".join(row["text"] for row in matched_rows)
    evidence_row = {
        "section": "skills",
        "text": evidence_text,
        "source": ", ".join(row["source"] for row in matched_rows),
    }

    return {
        "kind": "programming_language_group",
        "group_mode": group_mode,
        "required_terms": alternatives,
        "matched_terms": [row["text"] for row in matched_rows],
        "matched_keyword": ", ".join(alternatives),
        "evidence": _evidence_reference(
            evidence_row,
            (
                "The structured résumé language list deterministically satisfies "
                f"this {group_mode.upper()} programming-language requirement."
            ),
        ),
    }


def _match_exact_structured_skill(
    requirement_text: str,
    rows: list[dict[str, str]],
) -> dict[str, Any] | None:
    match = _EXACT_SKILL_REQUIREMENT.match(_clean(requirement_text))
    if not match:
        return None

    alternatives, group_mode = _split_alternatives(match.group("tail"))
    if len(alternatives) != 1:
        return None

    required = alternatives[0]
    required_key = _normalise(required)
    keys = _derived_skill_keys(rows)
    if required_key not in keys:
        return None

    evidence_row = next(
        (
            row
            for row in rows
            if row.get("normalised") == required_key
        ),
        None,
    )

    if evidence_row is None and required_key == "relational database":
        evidence_row = next(
            (
                row
                for row in rows
                if row.get("normalised")
                in {
                    "postgresql",
                    "mysql",
                    "sqlite",
                    "mariadb",
                    "oracle database",
                    "microsoft sql server",
                    "sql server",
                }
            ),
            None,
        )

    if evidence_row is None and required_key == "cloud platform":
        evidence_row = next(
            (
                row
                for row in rows
                if row.get("normalised") in {"aws", "azure", "gcp"}
            ),
            None,
        )

    if evidence_row is None:
        return None

    return {
        "kind": "exact_structured_skill",
        "group_mode": group_mode,
        "required_terms": [required],
        "matched_terms": [evidence_row["text"]],
        "matched_keyword": required,
        "evidence": _evidence_reference(
            evidence_row,
            "The requirement exactly matches a structured résumé skill.",
        ),
    }


def _education_fields(requirement_text: str) -> list[str]:
    match = re.search(r"\bin\s+(?P<tail>.+)$", requirement_text, flags=re.IGNORECASE)
    if not match:
        return []

    fields, _ = _split_alternatives(match.group("tail"))
    result: list[str] = []
    for field in fields:
        field = re.sub(
            r"^(?:computer\s+science\s+or\s+)?",
            lambda found: found.group(0),
            field,
            flags=re.IGNORECASE,
        )
        key = _normalise(field)
        if key and len(key) >= 3:
            result.append(field)
    return result


def _match_education(
    requirement_text: str,
    rows: list[dict[str, str]],
) -> dict[str, Any] | None:
    if not _EDUCATION_LEVEL.search(requirement_text):
        return None

    education_rows = [
        row
        for row in rows
        if row.get("section") == "education"
    ]
    if not education_rows:
        return None

    fields = _education_fields(requirement_text)
    if not fields:
        return None

    for row in education_rows:
        value = row.get("normalised", "")
        matched_fields = [
            field
            for field in fields
            if _normalise(field) in value
        ]
        if not matched_fields:
            continue

        return {
            "kind": "education_qualification",
            "group_mode": "any",
            "required_terms": fields,
            "matched_terms": matched_fields,
            "matched_keyword": matched_fields[0],
            "evidence": _evidence_reference(
                row,
                (
                    "The structured résumé education record contains an accepted "
                    "qualification field from the requirement."
                ),
            ),
        }

    return None


def _match_certification(
    requirement_text: str,
    rows: list[dict[str, str]],
) -> dict[str, Any] | None:
    if not _CERTIFICATION_REQUIREMENT.search(requirement_text):
        return None

    certification_rows = [
        row for row in rows if row.get("section") == "certification"
    ]
    if not certification_rows:
        return None

    generic = {
        "a", "an", "and", "are", "advantage", "advantageous", "certificate",
        "certificates", "certification", "certifications", "certified", "cloud",
        "equivalent", "following", "foundation", "from", "in", "industry", "is",
        "mandatory", "not", "of", "or", "possession", "preferred", "relevant",
        "skills", "the", "would",
    }
    requirement_key = _normalise(requirement_text)
    required_tokens = {
        token for token in requirement_key.split()
        if token not in generic and len(token) >= 3
    }
    if not required_tokens:
        return None

    for row in certification_rows:
        evidence_tokens = set(str(row.get("normalised") or "").split())
        overlap = sorted(required_tokens & evidence_tokens)
        if not overlap:
            continue
        return {
            "kind": "explicit_certification",
            "group_mode": "any",
            "required_terms": sorted(required_tokens),
            "matched_terms": overlap,
            "matched_keyword": overlap[0],
            "evidence": _evidence_reference(
                row,
                "A structured Certification evidence item explicitly names an accepted certification term.",
            ),
        }
    return None


def structured_match_requirement(
    requirement: dict[str, Any],
    *,
    resume_profile: dict[str, Any] | None,
    raw_resume_text: str = "",
) -> dict[str, Any] | None:
    """Return a conservative deterministic decision or None.

    `raw_resume_text` is accepted for API stability, but Phase 6D.6 deliberately
    relies on structured résumé fields for score-changing decisions.
    """
    del raw_resume_text

    focus = _clean(
        requirement.get("atomic_focus")
        or requirement.get("text")
    )
    if not focus or _SUBJECTIVE_CUES.search(focus):
        return None

    rows = _structured_rows(resume_profile)

    integration_decision = None
    if _LABEL_ORDER.get(str(requirement.get("match_label") or "none").lower(), 0) == 0:
        integration_decision = _match_collaborative_system_integration(
            focus,
            resume_profile,
        )
    if integration_decision is not None:
        return {
            "structured_match_version": STRUCTURED_MATCH_VERSION,
            **integration_decision,
        }

    for matcher in (
        _match_programming_languages,
        _match_certification,
        _match_education,
        _match_exact_structured_skill,
    ):
        decision = matcher(focus, rows)
        if decision is not None:
            return {
                "structured_match_version": STRUCTURED_MATCH_VERSION,
                **decision,
            }

    return None


def technology_requirement_structure(requirement: dict[str, Any]) -> dict[str, Any]:
    """Expose native components for identity diagnostics, never scoring children.

    Research-mining children are not admissible here. Reuse scorer decomposition
    and structured alternatives; hold tails those parsers cannot bound safely.
    """
    from analysis_stability.stable_evidence_scoring import (
        _split_single_requirement_clause, _is_bounded_named_term,
        requirement_is_score_eligible, _classify_non_requirement_row, _preserves_coherent_parent,
    )
    text = _clean(requirement.get("atomic_focus") or requirement.get("text"))
    result = {"components": [], "mode": None, "source": "native_structure_unavailable",
              "parent_weight_preserved": True, "scoring_children_created": False}
    if not text or not requirement_is_score_eligible(requirement) or _classify_non_requirement_row(text):
        return result
    clauses = _split_single_requirement_clause(text, requirement.get("importance") or "core")
    if len(clauses) > 1 and all(c["is_atomic"] for c in clauses):
        return {**result, "components": clauses, "mode": "all", "source": "native_jd_decomposition"}
    terms = requirement.get("structured_match_required_terms") or []
    mode = requirement.get("structured_match_group_mode")
    source = "native_structured_match"
    if not terms:
        if _preserves_coherent_parent(text):
            return {**result, "source": "native_coherent_example_or_alternative_parent"}
        match = _PROGRAMMING_LIST.search(text)
        if match:
            terms, mode = _split_alternatives(match.group("tail"))
            source = "native_structured_alternatives"
    # No head extraction, substring scan, guessed parentheses or mixed activities.
    # A single capital letter in an explicit native list remains an unresolved
    # component unless the exact production registry independently recognizes it.
    bounded = lambda t: _is_bounded_named_term(t) or bool(re.fullmatch(r"[A-Z]", t))
    if 2 <= len(terms) <= 10 and mode in {"any", "all"} and all(bounded(t) for t in terms):
        return {**result, "components": [{"text": t, "atomic_focus": t,
            "parent_text": text, "importance": requirement.get("importance"),
            "atomic_group_id": requirement.get("atomic_group_id"), "is_atomic": True} for t in terms],
            "mode": mode, "source": source}
    return result


def apply_structured_requirement_matches(
    requirements: list[dict[str, Any]],
    *,
    resume_profile: dict[str, Any] | None,
    raw_resume_text: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply only independently verified upgrades.

    This stage never reads Phase 6D.5 retrieval candidates.
    """
    output: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for requirement in requirements:
        row = deepcopy(requirement)
        row["structured_match_version"] = STRUCTURED_MATCH_VERSION

        decision = structured_match_requirement(
            row,
            resume_profile=resume_profile,
            raw_resume_text=raw_resume_text,
        )

        if decision is None:
            row["structured_match_status"] = "not_applicable"
            output.append(row)
            continue

        row["structured_match_kind"] = decision["kind"]
        row["structured_match_group_mode"] = decision["group_mode"]
        row["structured_match_required_terms"] = decision["required_terms"]
        row["structured_match_matched_terms"] = decision["matched_terms"]

        decision_label = str(decision.get("match_label") or "direct").lower()
        current_label = str(row.get("match_label") or "none").lower()
        if _LABEL_ORDER.get(current_label, 0) >= _LABEL_ORDER[decision_label]:
            row["structured_match_status"] = f"confirmed_existing_{current_label}"
            output.append(row)
            continue

        row["match_label"] = decision_label
        row["match_value"] = _MATCH_VALUES[decision_label]
        row["evidence_strength"] = {
            "weak": 2,
            "transferable": 3,
            "direct": 5,
        }[decision_label]
        row["evidence"] = [decision["evidence"]]
        row["matched_keyword"] = decision["matched_keyword"]
        row["match_similarity"] = 1.0
        row["match_coverage"] = 1.0
        row["match_overlap_count"] = max(
            1,
            len(decision["matched_terms"]),
        )
        row["match_source"] = "structured_resume_profile"
        row["structured_match_status"] = "applied"

        warnings.append(
            {
                "requirement_id": row.get("requirement_id", ""),
                "code": "structured_resume_match_applied",
                "message": (
                    "Phase 6D.6 replaced an unstable AI-derived result with a "
                    "deterministic match from structured résumé fields."
                ),
            }
        )
        output.append(row)

    return output, warnings
