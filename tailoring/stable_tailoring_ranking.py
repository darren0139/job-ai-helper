"""
tailoring/stable_tailoring_ranking.py

Phase 6B.1 deterministic evidence-mapping and ranking helpers.

The language model may identify semantic links between a project and canonical
JD requirements, but Python owns all numeric scoring, ranking, near-tie
resolution, complementary project-set selection, skill priority calculation,
and stable ordering.

The helpers are intentionally domain-generic. They consume the canonical
requirements produced by Phase 6A.1C rather than maintaining role-specific
alias tables.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable

from tailoring.project_identity import (
    PROJECT_IDENTITY_VERSION,
    build_selected_project_identity_index,
    match_evidence_project_to_selected,
)

from tailoring.phase6d_ranking_adapter import (
    match_requirement_to_candidate,
    taxonomy_evidence_anchors,
)


PROJECT_RANKING_VERSION = "phase6b1-project-ranking-v4"
SKILL_RANKING_VERSION = "phase6b1-skill-ranking-v4"
EVIDENCE_MAPPING_VERSION = "phase6d-capability-taxonomy-evidence-mapping-v1"
NEAR_TIE_MARGIN = 5

_MATCH_VALUES = {
    "none": 0.0,
    "weak": 0.25,
    "transferable": 0.55,
    "direct": 1.0,
}

_MATCH_ORDER = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}

_IMPORTANCE_POINTS = {
    "core": 36.0,
    "deal_breaker": 36.0,
    "required": 30.0,
    "preferred": 12.0,
}

_SUBJECTIVE_CUES = {
    "passion",
    "passionate",
    "enthusiasm",
    "enthusiastic",
    "interest",
    "interested",
    "motivated",
    "motivation",
    "eager",
    "committed",
    "commitment",
    "willing",
    "enjoy",
    "enjoys",
}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "being",
    "both",
    "by",
    "for",
    "from",
    "good",
    "having",
    "in",
    "including",
    "into",
    "minimum",
    "of",
    "on",
    "or",
    "other",
    "preferably",
    "recent",
    "related",
    "the",
    "their",
    "to",
    "with",
    "within",
    "work",
    "works",
}

# These terms constrain one-word Skills matching only. The Phase 6D taxonomy
# remains the owner for recognised capabilities; this list keeps a generic
# skill such as ``data`` from receiving the same priority as Kotlin merely
# because the JD contains ``data structures and algorithms``. It is not used
# to erase a literal multi-token JD requirement from project evidence scoring.
_GENERIC_SKILL_RANKING_TOKENS = {
    "app",
    "applicate",
    "base",
    "code",
    "develop",
    "experience",
    "foundation",
    "general",
    "high",
    "implement",
    "integrate",
    "large",
    "project",
    "solution",
    "software",
    "strong",
    "system",
    "technical",
    "understand",
}

# A single explicit language or platform name can establish direct skill
# relevance even when the JD expresses it inside a broader sentence.  This is
# an evidence-selection rule, not an alias expansion: the exact token must
# appear in both the requirement and the one evidence record/skill being used.
_EXPLICIT_TECHNICAL_TOKENS = {
    "android",
    "c",
    "c++",
    "c#",
    "cuda",
    "java",
    "javascript",
    "kotlin",
    "python",
    "rust",
    "sql",
    "typescript",
}

# Some real JDs omit a space immediately after a punctuation-bearing language
# token (for example ``C++programming``).  Split only a closed set of exact
# technical tokens at a letter boundary.  This preserves an explicit token
# already present in the source text; it is neither an alias expansion nor a
# generic substring match.
_PUNCTUATION_ADJACENT_TECHNICAL_TOKEN = re.compile(
    r"(?<![a-z0-9+#])(c\+\+|c#|f#)(?=[a-z])",
    flags=re.IGNORECASE,
)

# Match the shared stable scorer's direct-evidence boundary for a concrete
# evidence row while requiring more than one overlapping token. A single
# generic word is consequently insufficient for direct project relevance.
_SINGLE_RECORD_DIRECT_COVERAGE = 0.55

_SOFT_SKILL_LINE_TERMS = {
    "attention to detail",
    "communication",
    "cross functional collaboration",
    "cross-functional collaboration",
    "leadership",
    "problem solving",
    "team collaboration",
    "team coordination",
    "teamwork",
    "written communication",
    "verbal communication",
}

_CATEGORY_ORDER = {
    "game & engine": 0,
    "programming": 1,
    "ai & data": 2,
    "backend & database": 3,
    "web & app": 4,
    "tools": 5,
}

_PROGRAMMING_LANGUAGE_KEYS = {
    "c",
    "c++",
    "c#",
    "css",
    "go",
    "html",
    "java",
    "javascript",
    "kotlin",
    "python",
    "rust",
    "sql",
    "typescript",
}

_GAME_ENGINE_HINTS = {
    "c#",
    "custom game engine",
    "fmod",
    "game engine development",
    "game systems",
    "gameplay scripting",
    "player progression",
    "unity",
    "unity editor",
    "unity engine",
    "unreal",
    "unreal engine",
}

_AI_DATA_HINTS = {
    "ai application development",
    "chroma",
    "chromadb",
    "data analysis",
    "data cleaning",
    "document parsing",
    "llm",
    "litellm",
    "machine learning",
    "openai api",
    "prompt engineering",
    "rag",
    "resume analysis",
}

_BACKEND_HINTS = {
    "access control",
    "api",
    "authentication workflows",
    "backend integration",
    "cloud computing",
    "database design",
    "minio",
    "postgresql",
    "postgrest",
    "restful api",
    "restful apis",
    "row-level security",
    "row level security",
    "rls",
    "sqlite",
    "supabase",
}

_WEB_APP_HINTS = {
    "android development",
    "android frontend development",
    "android studio",
    "coil",
    "frontend development",
    "jetpack compose",
    "mobile app development",
    "react",
    "spring boot",
    "streamlit",
    "streamlit development",
    "ui implementation",
}

_TOOL_HINTS = {
    "docker",
    "git",
    "github",
    "visual studio",
    "visual studio code",
}


# Phase 6B.1 evidence concepts. These are generic capability families rather
# than role-specific aliases. They are used to validate or replace an LLM's
# proposed project-to-requirement links with evidence-grounded Python rules.
_EVIDENCE_CONCEPT_ANCHORS = taxonomy_evidence_anchors()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise_key(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("row-level", "row level")
    text = text.replace("cross-functional", "cross functional")
    text = _PUNCTUATION_ADJACENT_TECHNICAL_TOKEN.sub(r"\1 ", text)
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _normalise_skill_key(value: Any) -> str:
    key = _normalise_key(value)
    aliases = {
        "unity editor": "unity",
        "unity engine": "unity",
        "c++ programming": "c++",
        "c# programming": "c#",
        "python programming": "python",
        "github": "github",
        "row level security rls": "row level security",
    }
    return aliases.get(key, key)


def _stem_token(token: str) -> str:
    token = token.lower().strip()
    if token in {"game", "games", "gaming"}:
        return "game"
    if token in {"industry", "industries"}:
        return "industry"
    if len(token) <= 3:
        return token

    replacements = (
        ("isation", "ise"),
        ("ization", "ize"),
        ("ational", "ate"),
        ("fulness", "ful"),
        ("iveness", "ive"),
        ("ments", "ment"),
        ("ation", "ate"),
        ("ities", "ity"),
        ("ingly", ""),
        ("edly", ""),
        ("ing", ""),
        ("ied", "y"),
        ("ies", "y"),
        ("ed", ""),
        ("es", ""),
        ("s", ""),
    )

    for suffix, replacement in replacements:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)] + replacement

    return token


def _tokens(value: Any, *, remove_stopwords: bool = True) -> set[str]:
    normalised = _normalise_key(value)
    found: set[str] = set()

    for raw_token in normalised.split():
        raw_token = raw_token.strip(".")
        token = _stem_token(raw_token)
        if not token:
            continue
        if remove_stopwords and token in _STOPWORDS:
            continue
        found.add(token)

    return found


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "\n".join(_normalise_key(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _candidate_project_key(candidate: dict[str, Any]) -> str:
    return _normalise_key(candidate.get("title") or candidate.get("display_title"))


def _candidate_text_parts(candidate: dict[str, Any]) -> list[tuple[str, str, str]]:
    parts: list[tuple[str, str, str]] = []
    title = _clean_text(candidate.get("display_title") or candidate.get("title"))
    if title:
        parts.append(("title", "combined", title))

    for source_key, source_name in (
        ("resume_evidence", "resume"),
        ("evidence_library_evidence", "evidence_library"),
    ):
        evidence = candidate.get(source_key) or {}
        if not isinstance(evidence, dict):
            continue

        for field in ("description", "impact"):
            text = _clean_text(evidence.get(field))
            if text:
                parts.append((field, source_name, text))

        for field in ("bullets", "skills", "tools"):
            raw_values = evidence.get(field, []) or []
            if not isinstance(raw_values, list):
                continue
            for value in raw_values:
                text = _clean_text(value)
                if text:
                    parts.append((field[:-1] if field.endswith("s") else field, source_name, text))

    return parts


def build_candidate_evidence_profile(
    project_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic, versionable project/evidence profile."""
    projects: list[dict[str, Any]] = []

    for candidate in sorted(
        project_candidates,
        key=lambda item: _candidate_project_key(item),
    ):
        title = _clean_text(candidate.get("display_title") or candidate.get("title"))
        project_id = _stable_id("project", title)
        records: list[dict[str, Any]] = []

        for index, (kind, source, text) in enumerate(_candidate_text_parts(candidate), start=1):
            records.append(
                {
                    "evidence_id": _stable_id(
                        "evidence",
                        project_id,
                        source,
                        kind,
                        index,
                        text,
                    ),
                    "source": source,
                    "kind": kind,
                    "text": text,
                }
            )

        projects.append(
            {
                "project_id": project_id,
                "title": title,
                "project_key": _candidate_project_key(candidate),
                "currently_in_resume": bool(candidate.get("currently_in_resume")),
                "in_evidence_library": bool(candidate.get("in_evidence_library")),
                "period": _clean_text(candidate.get("period")),
                "evidence_records": records,
            }
        )

    fingerprint_payload = json.dumps(projects, sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()

    return {
        "profile_version": "phase6b-candidate-profile-v1",
        "fingerprint": fingerprint,
        "projects": projects,
    }


def _requirement_index(stable_analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    requirements = stable_analysis.get("canonical_requirements", []) or []
    return {
        _clean_text(item.get("requirement_id")): item
        for item in requirements
        if isinstance(item, dict) and _clean_text(item.get("requirement_id"))
    }


def _requirement_match_text(requirement: dict[str, Any]) -> str:
    values: list[str] = [
        _clean_text(requirement.get("text")),
        _clean_text(requirement.get("atomic_focus")),
        _clean_text(requirement.get("parent_text")),
    ]
    values.extend(
        _clean_text(value)
        for value in requirement.get("variants", []) or []
    )
    return " ".join(value for value in values if value)


def _phrase_requirement_score(phrase: str, requirement: dict[str, Any]) -> float:
    phrase_key = _normalise_key(phrase)
    requirement_text = _clean_text(requirement.get("text"))
    requirement_key = _normalise_key(requirement_text)

    if not phrase_key or not requirement_key:
        return 0.0

    if phrase_key == requirement_key:
        return 1.0

    if requirement_key in phrase_key or phrase_key in requirement_key:
        shorter = min(len(_tokens(phrase_key)), len(_tokens(requirement_key)))
        longer = max(len(_tokens(phrase_key)), len(_tokens(requirement_key)))
        if shorter and shorter / max(1, longer) >= 0.45:
            return 0.94

    phrase_tokens = _tokens(phrase_key)
    requirement_tokens = _tokens(_requirement_match_text(requirement))
    focus_tokens = _tokens(requirement.get("atomic_focus") or requirement_text)

    if not phrase_tokens or not requirement_tokens:
        return 0.0

    overlap = phrase_tokens & requirement_tokens
    coverage = len(overlap) / max(1, len(focus_tokens or requirement_tokens))
    precision = len(overlap) / max(1, len(phrase_tokens))
    jaccard = len(overlap) / max(1, len(phrase_tokens | requirement_tokens))

    focus_overlap = len(phrase_tokens & focus_tokens)
    focus_needed = 1 if len(focus_tokens) <= 1 else math.ceil(len(focus_tokens) * 0.6)

    if focus_tokens and focus_overlap < focus_needed:
        # Generic teamwork may provide weak evidence towards a more specific
        # cross-functional requirement, but it must never be upgraded beyond weak.
        requirement_normalised = _normalise_key(requirement_text)
        collaboration_terms = {"collaborate", "collaboration", "team", "coordinate"}
        if (
            "cross functional" in requirement_normalised
            and phrase_tokens & {_stem_token(term) for term in collaboration_terms}
        ):
            return 0.46
        return 0.0

    return round(coverage * 0.55 + precision * 0.25 + jaccard * 0.20, 6)


def _best_requirement_for_phrase(
    phrase: str,
    requirements: dict[str, dict[str, Any]],
) -> tuple[str | None, float]:
    best_id: str | None = None
    best_score = 0.0

    for requirement_id, requirement in requirements.items():
        score = _phrase_requirement_score(phrase, requirement)
        if score > best_score or (
            score == best_score and best_id is not None and requirement_id < best_id
        ):
            best_id = requirement_id
            best_score = score

    if best_score < 0.44:
        return None, best_score

    return best_id, best_score


def _evidence_corpus(candidate: dict[str, Any]) -> str:
    return "\n".join(text for _, _, text in _candidate_text_parts(candidate))


def _contains_explicit_subjective_evidence(
    requirement: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    requirement_tokens_all = _tokens(
        requirement.get("text"),
        remove_stopwords=False,
    )
    explicit_only = bool(requirement.get("explicit_only_requirement")) or bool(
        requirement_tokens_all
        & {_stem_token(token) for token in _SUBJECTIVE_CUES}
    )

    if not explicit_only:
        return True

    evidence_tokens = _tokens(_evidence_corpus(candidate), remove_stopwords=False)
    if not evidence_tokens & {_stem_token(token) for token in _SUBJECTIVE_CUES}:
        return False

    requirement_tokens = _tokens(requirement.get("text")) - {
        _stem_token(token) for token in _SUBJECTIVE_CUES
    }
    if not requirement_tokens:
        return True

    return bool(evidence_tokens & requirement_tokens)


def _normalise_match_label(value: Any) -> str:
    label = _normalise_key(value).replace(" ", "_")
    if label in _MATCH_VALUES:
        return label
    if label in {"equivalent", "exact"}:
        return "direct"
    if label in {"partial", "related"}:
        return "transferable"
    return "none"


def _merge_match(
    destination: dict[str, dict[str, Any]],
    candidate_match: dict[str, Any],
) -> None:
    requirement_id = _clean_text(candidate_match.get("requirement_id"))
    if not requirement_id:
        return

    current = destination.get(requirement_id)
    new_label = _normalise_match_label(candidate_match.get("match_label"))

    if current is None or _MATCH_ORDER[new_label] > _MATCH_ORDER[current["match_label"]]:
        destination[requirement_id] = candidate_match
        return

    if current and _MATCH_ORDER[new_label] == _MATCH_ORDER[current["match_label"]]:
        existing_ids = set(current.get("evidence_ids", []) or [])
        current["evidence_ids"] = sorted(
            existing_ids | set(candidate_match.get("evidence_ids", []) or [])
        )
        current["evidence_snippets"] = sorted(
            set(current.get("evidence_snippets", []) or [])
            | set(candidate_match.get("evidence_snippets", []) or [])
        )


def _evidence_records_by_project(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["project_key"]: item
        for item in profile.get("projects", []) or []
        if isinstance(item, dict) and item.get("project_key")
    }


def _snippet_evidence_ids(
    snippets: Iterable[Any],
    project_profile: dict[str, Any],
) -> tuple[list[str], list[str]]:
    records = project_profile.get("evidence_records", []) or []
    matched_ids: set[str] = set()
    clean_snippets: list[str] = []

    for raw_snippet in snippets:
        snippet = _clean_text(raw_snippet)
        if not snippet:
            continue
        clean_snippets.append(snippet)
        snippet_key = _normalise_key(snippet)
        snippet_tokens = _tokens(snippet)

        for record in records:
            text = _clean_text(record.get("text"))
            text_key = _normalise_key(text)
            if not text_key:
                continue
            if snippet_key in text_key or text_key in snippet_key:
                matched_ids.add(_clean_text(record.get("evidence_id")))
                continue
            record_tokens = _tokens(text)
            if snippet_tokens and len(snippet_tokens & record_tokens) / max(1, len(snippet_tokens)) >= 0.7:
                matched_ids.add(_clean_text(record.get("evidence_id")))

    return sorted(value for value in matched_ids if value), clean_snippets


def _fallback_evidence_supports_requirement(
    requirement: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[bool, bool]:
    """Return ``(supported, generic_collaboration_only)``.

    Phase 6D owns recognised capability semantics. The generic lexical overlap
    fallback is retained only for requirements that the taxonomy does not yet
    recognise, preserving backward compatibility for uncommon role wording.
    """
    decision = match_requirement_to_candidate(
        requirement=requirement,
        candidate_evidence_text=_evidence_corpus(candidate),
    )
    label = decision.get("label")

    if label is not None:
        generic_collaboration_only = bool(
            decision.get("capability_id")
            == "collaboration.cross_functional"
            and label == "weak"
        )
        return label != "none", generic_collaboration_only

    requirement_focus = _tokens(
        requirement.get("atomic_focus") or requirement.get("text")
    )
    evidence_tokens = _tokens(_evidence_corpus(candidate))

    if not evidence_tokens:
        return False, False

    overlap = evidence_tokens & requirement_focus
    coverage = len(overlap) / max(1, len(requirement_focus))
    return coverage >= 0.5, False


def _concept_text_key(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("row-level", "row level")
    text = text.replace("cross-functional", "cross functional")
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    return " ".join(text.split())


def _text_contains_any(text: str, phrases: Iterable[str]) -> bool:
    text_key = _concept_text_key(text)
    if not text_key:
        return False
    text_tokens = {_stem_token(token) for token in text_key.split()}

    for phrase in phrases:
        phrase_key = _concept_text_key(phrase)
        if not phrase_key:
            continue
        raw_tokens = phrase_key.split()
        if len(raw_tokens) == 1:
            if _stem_token(raw_tokens[0]) in text_tokens:
                return True
        elif f" {phrase_key} " in f" {text_key} ":
            return True
    return False


def _record_matches_concept(record: dict[str, Any], concept: str) -> bool:
    return _text_contains_any(
        _clean_text(record.get("text")),
        _EVIDENCE_CONCEPT_ANCHORS.get(concept, set()),
    )


def _records_for_concepts(
    project_profile: dict[str, Any],
    *concepts: str,
) -> list[dict[str, Any]]:
    records = project_profile.get("evidence_records", []) or []
    matched: list[dict[str, Any]] = []
    for record in records:
        if any(_record_matches_concept(record, concept) for concept in concepts):
            matched.append(record)
    return matched


def _deterministic_family_match(
    *,
    requirement: dict[str, Any],
    candidate: dict[str, Any],
    project_profile: dict[str, Any],
) -> tuple[str | None, list[str], list[str], dict[str, Any]]:
    """Return the Phase 6D taxonomy-owned evidence decision.

    A ``None`` label means the taxonomy does not recognise the requirement. In
    that case the caller must use the constrained single-record fallback below.
    A ``none`` label means the capability is recognised but this project's
    evidence does not support it, so any LLM proposal for the requirement must
    be discarded.
    """
    decision = match_requirement_to_candidate(
        requirement=requirement,
        candidate_evidence_text=_evidence_corpus(candidate),
    )

    label = decision.get("label")
    capability_id = decision.get("capability_id")
    requirement_text = _normalise_key(requirement.get("text"))

    if label is None:
        return None, [], [], {
            "family": None,
            "capability_id": None,
            "taxonomy_version": decision.get("taxonomy_version"),
            "rule": "unrecognised_capability",
            "requirement_text": requirement_text,
        }

    concepts = tuple(decision.get("concepts", []) or [])
    records = (
        _records_for_concepts(project_profile, *concepts)
        if concepts
        else []
    )

    if label != "none" and not records:
        # Use concrete project evidence rather than an LLM-generated phrase.
        records = [
            record
            for record in project_profile.get("evidence_records", []) or []
            if record.get("kind")
            in {"bullet", "impact", "skill", "tool", "title"}
        ][:3]

    evidence_ids = sorted(
        _clean_text(record.get("evidence_id"))
        for record in records
        if _clean_text(record.get("evidence_id"))
    )
    snippets = sorted(
        {
            _clean_text(record.get("text"))
            for record in records
            if _clean_text(record.get("text"))
        }
    )

    return label, evidence_ids, snippets, {
        # Keep ``family`` for backward-compatible debug consumers while making
        # the stable capability ID explicit.
        "family": capability_id,
        "capability_id": capability_id,
        "taxonomy_version": decision.get("taxonomy_version"),
        "rule": decision.get("reason"),
        "recognised": True,
        "requirement_text": requirement_text,
        "does_not_prove": list(
            decision.get("does_not_prove", []) or []
        ),
    }


def _specific_requirement_tokens(requirement: dict[str, Any]) -> set[str]:
    """Return explicit requirement tokens for an unrecognised fallback.

    This deliberately works from the requirement's explicit text only and
    follows the stable scorer by ignoring the experience preamble. It does not
    infer synonyms or combine evidence rows. Terms such as ``data`` remain
    when they are part of a multi-token requirement; the one-record coverage
    threshold below prevents them from independently creating strong support.
    """
    return _tokens(
        requirement.get("atomic_focus") or requirement.get("text")
    ) - {"experience"}


def _unrecognised_single_record_match(
    *,
    requirement: dict[str, Any],
    project_profile: dict[str, Any],
) -> tuple[str, list[str], list[str], dict[str, Any]]:
    """Select the strongest explicit match from one project evidence record.

    Phase 6D owns recognised-capability decisions.  For an unrecognised JD
    requirement, this fallback is intentionally conservative: one concrete
    project record must establish the relationship.  Aggregating fragments
    from separate rows would manufacture support and would let generic words
    inflate a project rank.
    """
    requirement_tokens = _specific_requirement_tokens(requirement)
    requirement_id = _clean_text(requirement.get("requirement_id"))
    if not requirement_tokens:
        return "none", [], [], {
            "family": None,
            "capability_id": None,
            "rule": "unrecognised_no_specific_requirement_tokens",
            "recognised": False,
            "requirement_id": requirement_id,
            "specific_requirement_tokens": [],
        }

    kind_priority = {
        "bullet": 5,
        "impact": 4,
        "description": 3,
        "skill": 2,
        "tool": 1,
    }
    candidates: list[tuple[str, float, int, int, str, dict[str, Any], set[str]]] = []

    for record in project_profile.get("evidence_records", []) or []:
        if not isinstance(record, dict):
            continue
        kind = _clean_text(record.get("kind"))
        if kind not in kind_priority:
            continue

        evidence_tokens = _tokens(record.get("text"))
        overlap = requirement_tokens & evidence_tokens
        if not overlap:
            continue

        coverage = len(overlap) / len(requirement_tokens)
        if (
            coverage >= _SINGLE_RECORD_DIRECT_COVERAGE
            and len(overlap) >= 2
        ) or coverage == 1.0:
            label = "direct"
        elif overlap & _EXPLICIT_TECHNICAL_TOKENS:
            # A single explicit language/platform token is meaningful, but it
            # does not establish unsupported companion claims in the same JD
            # sentence, so it is transferable rather than direct.
            label = "transferable"
        elif len(overlap) >= 2 and coverage >= 0.6:
            label = "transferable"
        elif coverage >= 0.5:
            label = "weak"
        else:
            continue

        evidence_id = _clean_text(record.get("evidence_id"))
        candidates.append(
            (
                label,
                coverage,
                len(overlap),
                kind_priority[kind],
                evidence_id,
                record,
                overlap,
            )
        )

    if not candidates:
        return "none", [], [], {
            "family": None,
            "capability_id": None,
            "rule": "unrecognised_no_single_record_support",
            "recognised": False,
            "requirement_id": requirement_id,
            "specific_requirement_tokens": sorted(requirement_tokens),
        }

    # Sort every component explicitly so selection never depends on input or
    # hash-map order.  The final evidence ID is a stable lexical tie-breaker.
    candidates.sort(
        key=lambda item: (
            -_MATCH_ORDER[item[0]],
            -item[1],
            -item[2],
            -item[3],
            item[4],
        )
    )
    label, coverage, _, _, _, record, overlap = candidates[0]
    evidence_id = _clean_text(record.get("evidence_id"))
    snippet = _clean_text(record.get("text"))
    return label, ([evidence_id] if evidence_id else []), ([snippet] if snippet else []), {
        "family": None,
        "capability_id": None,
        "rule": "unrecognised_single_record_specific_evidence",
        "recognised": False,
        "requirement_id": requirement_id,
        "specific_requirement_tokens": sorted(requirement_tokens),
        "matched_specific_tokens": sorted(overlap),
        "single_record_coverage": round(coverage, 4),
        "evidence_kind": _clean_text(record.get("kind")),
    }


def _apply_deterministic_requirement_overrides(
    *,
    matches: dict[str, dict[str, Any]],
    candidate: dict[str, Any],
    project_profile: dict[str, Any],
    requirements: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    debug: list[dict[str, Any]] = []

    for requirement_id, requirement in requirements.items():
        label, evidence_ids, snippets, rule_debug = _deterministic_family_match(
            requirement=requirement,
            candidate=candidate,
            project_profile=project_profile,
        )
        if label is None:
            previous = matches.pop(requirement_id, None)
            (
                fallback_label,
                fallback_evidence_ids,
                fallback_snippets,
                fallback_debug,
            ) = _unrecognised_single_record_match(
                requirement=requirement,
                project_profile=project_profile,
            )
            debug.append(
                {
                    "action": "deterministic_unrecognised_requirement_selection",
                    "requirement_id": requirement_id,
                    "previous_label": (
                        previous.get("match_label")
                        if isinstance(previous, dict)
                        else "none"
                    ),
                    "final_label": fallback_label,
                    **fallback_debug,
                }
            )
            if fallback_label != "none":
                matches[requirement_id] = {
                    "requirement_id": requirement_id,
                    "match_label": fallback_label,
                    "evidence_ids": fallback_evidence_ids,
                    "evidence_snippets": fallback_snippets,
                    "source": "python_unrecognised_single_record_evidence",
                    "mapping_similarity": fallback_debug.get(
                        "single_record_coverage", 0.0
                    ),
                    "evidence_mapping_version": EVIDENCE_MAPPING_VERSION,
                    "capability_id": None,
                    "capability_taxonomy_version": fallback_debug.get(
                        "taxonomy_version"
                    ),
                    "capability_does_not_prove": [],
                }
            continue

        previous = matches.pop(requirement_id, None)
        debug.append(
            {
                "action": "deterministic_requirement_override",
                "requirement_id": requirement_id,
                "previous_label": (
                    previous.get("match_label") if isinstance(previous, dict) else "none"
                ),
                "final_label": label,
                **rule_debug,
            }
        )

        if label == "none":
            continue

        matches[requirement_id] = {
            "requirement_id": requirement_id,
            "match_label": label,
            "evidence_ids": evidence_ids,
            "evidence_snippets": snippets,
            "source": "python_phase6d_capability_taxonomy",
            "mapping_similarity": 1.0,
            "evidence_mapping_version": EVIDENCE_MAPPING_VERSION,
            "capability_id": rule_debug.get("capability_id"),
            "capability_taxonomy_version": rule_debug.get(
                "taxonomy_version"
            ),
            "capability_does_not_prove": list(
                rule_debug.get("does_not_prove", []) or []
            ),
        }

    return debug


def _bullet_supports_requirement_match(
    bullet: str,
    match: dict[str, Any],
) -> bool:
    """Return whether one bullet carries the matched requirement capability."""
    requirement = {
        "text": match.get("requirement_text", ""),
        "atomic_focus": match.get("requirement_text", ""),
        "importance": match.get("importance", "required"),
    }
    decision = match_requirement_to_candidate(
        requirement=requirement,
        candidate_evidence_text=bullet,
    )

    # For recognised capabilities, the taxonomy owns the decision. Weak support
    # still counts as support for bullet-priority purposes, but its lower match
    # value already limits the numeric coverage it contributes.
    if decision.get("label") is not None:
        return decision.get("label") != "none"

    # Unrecognised requirements retain the prior evidence-snippet overlap
    # fallback so Phase 6D can be expanded incrementally.
    bullet_tokens = _tokens(bullet)
    bullet_key = _normalise_key(bullet)
    for snippet in match.get("evidence_snippets", []) or []:
        snippet_text = _clean_text(snippet)
        if not snippet_text:
            continue
        snippet_key = _normalise_key(snippet_text)
        snippet_tokens = _tokens(snippet_text)
        if snippet_key in bullet_key or bullet_key in snippet_key:
            return True
        if (
            len(bullet_tokens & snippet_tokens)
            / max(1, len(snippet_tokens))
            >= 0.55
        ):
            return True
    return False


def build_bullet_evidence_priorities(
    *,
    bullets: list[str],
    ranking_row: dict[str, Any],
) -> list[dict[str, Any]]:
    """Rank selected bullets by the canonical requirements they preserve.

    Phase 6B.1 only emits this metadata. The one-page fitter can consume it in
    Phase 6C to avoid deleting the sole bullet carrying unique requirement value.
    """
    clean_bullets = [_clean_text(bullet) for bullet in bullets if _clean_text(bullet)]
    matches = ranking_row.get("requirement_matches", []) or []
    rows: list[dict[str, Any]] = []

    support_by_requirement: dict[str, list[int]] = defaultdict(list)
    raw_support: list[set[str]] = []

    for index, bullet in enumerate(clean_bullets):
        supported = {
            _clean_text(match.get("requirement_id"))
            for match in matches
            if _clean_text(match.get("requirement_id"))
            and _bullet_supports_requirement_match(bullet, match)
        }
        raw_support.append(supported)
        for requirement_id in supported:
            support_by_requirement[requirement_id].append(index)

    for index, bullet in enumerate(clean_bullets):
        supported = raw_support[index]
        # Protection and allocation are deliberately separate:
        # a unique weak evidence bullet may remain protected during Phase 6C
        # fitting, but weak evidence receives no Phase 6B.2 unique-core bonus.
        protected_ids = sorted(
            requirement_id
            for requirement_id in supported
            if len(support_by_requirement.get(requirement_id, [])) == 1
        )
        evidence_value = 0.0
        required_core_unique = 0
        for match in matches:
            requirement_id = _clean_text(match.get("requirement_id"))
            if requirement_id not in supported:
                continue
            points = float(match.get("coverage_points", 0.0) or 0.0)
            evidence_value += points
            if (
                requirement_id in protected_ids
                and match.get("importance")
                in {"core", "deal_breaker", "required"}
                and str(match.get("match_label", "none")).lower()
                in {"direct", "transferable"}
            ):
                required_core_unique += 1
                evidence_value += 5.0

        rows.append(
            {
                "bullet_index": index,
                "bullet_text": bullet,
                "supported_requirement_ids": sorted(supported),
                "protected_requirement_ids": protected_ids,
                "unique_required_core_count": required_core_unique,
                "evidence_value": round(evidence_value, 4),
                "protect_during_fitting": bool(protected_ids),
            }
        )

    ranked_indexes = sorted(
        range(len(rows)),
        key=lambda idx: (
            rows[idx]["evidence_value"],
            rows[idx]["unique_required_core_count"],
            -rows[idx]["bullet_index"],
        ),
        reverse=True,
    )
    for priority, index in enumerate(ranked_indexes, start=1):
        rows[index]["evidence_priority"] = priority

    return rows


def _extract_requirement_matches(
    *,
    row: dict[str, Any],
    candidate: dict[str, Any],
    project_profile: dict[str, Any],
    requirements: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matches: dict[str, dict[str, Any]] = {}
    debug: list[dict[str, Any]] = []

    for raw_match in row.get("requirement_matches", []) or []:
        if not isinstance(raw_match, dict):
            continue

        requirement_id = _clean_text(raw_match.get("requirement_id"))
        requirement = requirements.get(requirement_id)
        if requirement is None:
            debug.append(
                {
                    "action": "discard_unknown_requirement_id",
                    "requirement_id": requirement_id,
                }
            )
            continue

        label = _normalise_match_label(raw_match.get("match_label"))
        if label == "none":
            continue

        if not _contains_explicit_subjective_evidence(requirement, candidate):
            debug.append(
                {
                    "action": "discard_subjective_without_explicit_evidence",
                    "requirement_id": requirement_id,
                }
            )
            continue

        evidence_ids, snippets = _snippet_evidence_ids(
            raw_match.get("evidence_snippets", []) or [],
            project_profile,
        )

        # A direct match must cite actual candidate evidence. Transferable and
        # weak links may fall back to the candidate corpus because their labels
        # already communicate uncertainty.
        if label == "direct" and not evidence_ids:
            label = "transferable"
            debug.append(
                {
                    "action": "downgrade_direct_without_verifiable_evidence",
                    "requirement_id": requirement_id,
                }
            )

        _merge_match(
            matches,
            {
                "requirement_id": requirement_id,
                "match_label": label,
                "evidence_ids": evidence_ids,
                "evidence_snippets": snippets,
                "source": "explicit_requirement_id",
                "mapping_similarity": 1.0,
            },
        )

    # Backward-compatible fallback for Phase 5/early Phase 6 output.
    fallback_lists = (
        ("matched_jd_requirements", "direct"),
        ("transferable_jd_requirements", "transferable"),
    )

    for field, default_label in fallback_lists:
        for raw_phrase in row.get(field, []) or []:
            phrase = _clean_text(raw_phrase)
            if not phrase:
                continue

            requirement_id, similarity = _best_requirement_for_phrase(phrase, requirements)
            if requirement_id is None:
                debug.append(
                    {
                        "action": "unmapped_requirement_phrase",
                        "field": field,
                        "phrase": phrase,
                        "similarity": round(similarity, 3),
                    }
                )
                continue

            requirement = requirements[requirement_id]
            if not _contains_explicit_subjective_evidence(requirement, candidate):
                debug.append(
                    {
                        "action": "discard_subjective_phrase_without_explicit_evidence",
                        "phrase": phrase,
                        "requirement_id": requirement_id,
                    }
                )
                continue

            supported, generic_collaboration_only = (
                _fallback_evidence_supports_requirement(
                    requirement,
                    candidate,
                )
            )
            if not supported:
                debug.append(
                    {
                        "action": "discard_unanchored_fallback_match",
                        "phrase": phrase,
                        "requirement_id": requirement_id,
                    }
                )
                continue

            label = default_label
            requirement_text = _normalise_key(requirement.get("text"))
            phrase_key = _normalise_key(phrase)

            if generic_collaboration_only or (
                "cross functional" in requirement_text
                and "cross functional" not in phrase_key
            ):
                label = "weak"

            _merge_match(
                matches,
                {
                    "requirement_id": requirement_id,
                    "match_label": label,
                    "evidence_ids": [
                        record.get("evidence_id")
                        for record in project_profile.get("evidence_records", []) or []
                        if record.get("kind") in {"bullet", "impact", "skill", "tool"}
                    ][:4],
                    "evidence_snippets": [phrase],
                    "source": field,
                    "mapping_similarity": round(similarity, 3),
                },
            )

    debug.extend(
        _apply_deterministic_requirement_overrides(
            matches=matches,
            candidate=candidate,
            project_profile=project_profile,
            requirements=requirements,
        )
    )

    ordered = sorted(
        matches.values(),
        key=lambda item: item["requirement_id"],
    )
    return ordered, debug


def _candidate_support_score(candidate: dict[str, Any]) -> tuple[int, dict[str, int]]:
    library = candidate.get("evidence_library_evidence") or {}
    resume = candidate.get("resume_evidence") or {}

    library_bullets = library.get("bullets", []) or []
    resume_bullets = resume.get("bullets", []) or []
    tools = library.get("tools", []) or []
    skills = library.get("skills", []) or []
    impact = _clean_text(library.get("impact"))

    evidence_completeness = min(8, len(library_bullets) * 2)
    evidence_completeness += min(3, len(tools) // 2)
    evidence_completeness += min(3, len(skills) // 2)
    evidence_completeness += 2 if impact else 0
    evidence_completeness += 1 if resume_bullets else 0
    evidence_completeness = min(15, evidence_completeness)

    scope_text = _normalise_key(
        " ".join(
            [
                _clean_text(candidate.get("title")),
                impact,
                *[_clean_text(value) for value in library_bullets],
            ]
        )
    )
    scope = 0
    if any(term in scope_text for term in ("published", "released", "deployed", "production")):
        scope += 3
    if re.search(r"\bteam of \d+\b|\b\d+ person\b|\b\d+-person\b", scope_text):
        scope += 2
    if any(term in scope_text for term in ("led ", "owned ", "built ", "implemented ", "developed ")):
        scope += 2
    if impact:
        scope += 1
    scope = min(8, scope)

    return evidence_completeness + scope, {
        "evidence_completeness": evidence_completeness,
        "impact_scope": scope,
    }


def _coverage_points(
    matches: list[dict[str, Any]],
    requirements: dict[str, dict[str, Any]],
) -> tuple[float, dict[str, float]]:
    total = 0.0
    by_requirement: dict[str, float] = {}

    for match in matches:
        requirement_id = match.get("requirement_id")
        requirement = requirements.get(requirement_id)
        if requirement is None:
            continue

        importance = _normalise_key(requirement.get("importance"))
        base = _IMPORTANCE_POINTS.get(importance, _IMPORTANCE_POINTS["required"])
        group_fraction = float(requirement.get("group_weight_fraction", 1.0) or 1.0)
        label_value = _MATCH_VALUES.get(match.get("match_label", "none"), 0.0)
        points = base * group_fraction * label_value
        by_requirement[requirement_id] = round(points, 4)
        total += points

    return total, by_requirement


def _project_ranking_explanation(
    matches: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Build a user-facing reason from the final Python-owned evidence map."""
    if not matches:
        return (
            "No direct canonical JD requirement is supported by this project's "
            "concrete résumé or Evidence Library evidence.",
            {
                "source": "python_deterministic_requirement_evidence",
                "matched_requirement_ids": [],
                "capability_ids": [],
                "evidence_ids": [],
            },
        )

    ordered = sorted(
        matches,
        key=lambda match: (
            -_MATCH_ORDER.get(match.get("match_label", "none"), 0),
            -_IMPORTANCE_POINTS.get(
                _normalise_key(match.get("importance")),
                _IMPORTANCE_POINTS["required"],
            ),
            _clean_text(match.get("requirement_id")),
        ),
    )
    primary = ordered[0]
    label = _clean_text(primary.get("match_label")).capitalize() or "Evidence-grounded"
    requirement_text = _clean_text(primary.get("requirement_text"))
    snippet = _clean_text((primary.get("evidence_snippets") or [""])[0])
    capability_id = _clean_text(primary.get("capability_id"))
    source = _clean_text(primary.get("source"))

    reason = f"{label} match to JD requirement “{requirement_text}”"
    if snippet:
        reason += f": “{snippet}”"
    if capability_id:
        reason += f". Capability relationship: {capability_id}."
    elif source == "python_unrecognised_single_record_evidence":
        reason += ". Relationship established by one explicit project evidence record."
    else:
        reason += "."

    return reason, {
        "source": "python_deterministic_requirement_evidence",
        "matched_requirement_ids": [
            _clean_text(match.get("requirement_id"))
            for match in ordered
            if _clean_text(match.get("requirement_id"))
        ],
        "capability_ids": sorted(
            {
                _clean_text(match.get("capability_id"))
                for match in ordered
                if _clean_text(match.get("capability_id"))
            }
        ),
        "evidence_ids": sorted(
            {
                _clean_text(evidence_id)
                for match in ordered
                for evidence_id in match.get("evidence_ids", []) or []
                if _clean_text(evidence_id)
            }
        ),
        "primary_requirement_id": _clean_text(primary.get("requirement_id")),
        "primary_match_label": _clean_text(primary.get("match_label")),
    }


def _ranking_tiebreak_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    matches = row.get("requirement_matches", []) or []
    direct_core = sum(
        1
        for match in matches
        if match.get("match_label") == "direct"
        and match.get("importance") in {"core", "deal_breaker", "required"}
    )
    core_coverage = sum(
        1
        for match in matches
        if match.get("importance") in {"core", "deal_breaker", "required"}
    )
    unique_evidence = len(
        {
            evidence_id
            for match in matches
            for evidence_id in match.get("evidence_ids", []) or []
            if evidence_id
        }
    )

    # Alphabetical title is inverted by callers that sort descending, so use a
    # deterministic negative-code tuple rather than relying on insertion order.
    title_key = _normalise_key(row.get("display_title") or row.get("title"))
    inverse_title = tuple(-ord(character) for character in title_key)

    return (
        direct_core,
        core_coverage,
        int(bool(row.get("currently_in_resume"))),
        unique_evidence,
        int(row.get("support_score", 0) or 0),
        inverse_title,
    )


def _sort_rows_with_near_ties(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    numeric = sorted(
        rows,
        key=lambda row: (
            int(row.get("final_score", 0) or 0),
            _normalise_key(row.get("display_title") or row.get("title")),
        ),
        reverse=True,
    )
    output: list[dict[str, Any]] = []
    index = 0

    while index < len(numeric):
        anchor_score = int(numeric[index].get("final_score", 0) or 0)
        cluster: list[dict[str, Any]] = []

        while index < len(numeric):
            score = int(numeric[index].get("final_score", 0) or 0)
            if anchor_score - score > NEAR_TIE_MARGIN:
                break
            cluster.append(numeric[index])
            index += 1

        cluster.sort(
            key=lambda row: (
                _ranking_tiebreak_tuple(row),
                int(row.get("final_score", 0) or 0),
            ),
            reverse=True,
        )
        output.extend(cluster)

    return output


def rank_projects_deterministically(
    *,
    ranked_rows: list[dict[str, Any]],
    project_candidates: list[dict[str, Any]],
    stable_analysis: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Replace AI numeric ranking with fixed requirement-linked Python scores."""
    requirements = _requirement_index(stable_analysis)
    if not requirements:
        raise ValueError(
            "Phase 6B.1 requires stable_analysis.canonical_requirements. "
            "Run Phase 6A.1C analysis before tailoring."
        )

    candidate_by_key = {
        _candidate_project_key(candidate): candidate
        for candidate in project_candidates
        if _candidate_project_key(candidate)
    }
    profile = build_candidate_evidence_profile(project_candidates)
    profile_by_key = _evidence_records_by_project(profile)

    output: list[dict[str, Any]] = []
    debug_rows: list[dict[str, Any]] = []

    for original_row in ranked_rows:
        row = deepcopy(original_row)
        key = _normalise_key(row.get("title") or row.get("display_title"))
        candidate = candidate_by_key.get(key)
        project_profile = profile_by_key.get(key)

        if candidate is None or project_profile is None:
            continue

        matches, mapping_debug = _extract_requirement_matches(
            row=row,
            candidate=candidate,
            project_profile=project_profile,
            requirements=requirements,
        )

        coverage, coverage_by_requirement = _coverage_points(matches, requirements)
        support_score, support_components = _candidate_support_score(candidate)

        # Relevance dominates. Evidence quality can improve a relevant project,
        # but cannot make an unrelated project win.
        deterministic_score = 0
        if coverage > 0:
            deterministic_score = min(100, round(coverage * 2.0 + support_score))

        enriched_matches: list[dict[str, Any]] = []
        for match in matches:
            requirement = requirements.get(match["requirement_id"], {})
            enriched_matches.append(
                {
                    **match,
                    "requirement_text": _clean_text(requirement.get("text")),
                    "importance": _normalise_key(requirement.get("importance")),
                    "group_weight_fraction": float(
                        requirement.get("group_weight_fraction", 1.0) or 1.0
                    ),
                    "coverage_points": coverage_by_requirement.get(
                        match["requirement_id"], 0.0
                    ),
                }
            )

        ranking_reason, explanation_debug = _project_ranking_explanation(
            enriched_matches
        )

        row.update(
            {
                "project_id": project_profile["project_id"],
                "candidate_profile_fingerprint": profile["fingerprint"],
                "requirement_matches": enriched_matches,
                "deterministic_coverage_score": round(coverage, 4),
                "support_score": support_score,
                "support_components": support_components,
                "ai_diagnostic_final_score": int(row.get("final_score", 0) or 0),
                "final_score": deterministic_score,
                "relevance_score": round(min(5.0, coverage / 6.0), 2),
                "reason": ranking_reason,
                "ranking_explanation": explanation_debug,
                "ranking_version": PROJECT_RANKING_VERSION,
                "ranking_owner": "python_deterministic_evidence_mapping",
                "mapping_debug": mapping_debug,
            }
        )

        # Keep the legacy text lists for the existing bullet-writing/UI shape,
        # but derive them from canonical requirement rows.
        row["matched_jd_requirements"] = [
            match["requirement_text"]
            for match in enriched_matches
            if match["match_label"] == "direct"
        ]
        row["transferable_jd_requirements"] = [
            match["requirement_text"]
            for match in enriched_matches
            if match["match_label"] in {"transferable", "weak"}
        ]

        output.append(row)
        debug_rows.append(
            {
                "project_id": project_profile["project_id"],
                "title": project_profile["title"],
                "deterministic_score": deterministic_score,
                "coverage_score": round(coverage, 4),
                "support_score": support_score,
                "requirement_matches": enriched_matches,
                "ranking_explanation": explanation_debug,
                "mapping_debug": mapping_debug,
            }
        )

    # Stable near-tie ordering. Rows within five points use evidence-linked
    # tie-breakers rather than the AI's small numeric fluctuations.
    output = _sort_rows_with_near_ties(output)

    return output, {
        "ranking_version": PROJECT_RANKING_VERSION,
        "near_tie_margin": NEAR_TIE_MARGIN,
        "evidence_mapping_version": EVIDENCE_MAPPING_VERSION,
        "candidate_profile": profile,
        "projects": debug_rows,
    }


def select_complementary_projects(
    *,
    ranked_rows: list[dict[str, Any]],
    selected_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Greedily select a stable project set with unique-coverage bonuses."""
    remaining = [deepcopy(row) for row in ranked_rows]
    selected: list[dict[str, Any]] = []
    covered_requirements: set[str] = set()
    selection_debug: list[dict[str, Any]] = []

    while remaining and len(selected) < selected_count:
        candidates: list[tuple[dict[str, Any], float, float, float]] = []

        for row in remaining:
            matches = row.get("requirement_matches", []) or []
            unique_points = sum(
                float(match.get("coverage_points", 0.0) or 0.0)
                for match in matches
                if match.get("requirement_id") not in covered_requirements
            )
            overlap_points = sum(
                float(match.get("coverage_points", 0.0) or 0.0)
                for match in matches
                if match.get("requirement_id") in covered_requirements
            )
            unique_bonus = min(12.0, unique_points * 0.35)
            overlap_penalty = min(6.0, overlap_points * 0.12)
            selection_score = float(row.get("final_score", 0) or 0) + unique_bonus - overlap_penalty
            candidates.append((row, selection_score, unique_bonus, overlap_penalty))

        best_numeric = max(item[1] for item in candidates)
        near_tied = [
            item
            for item in candidates
            if best_numeric - item[1] <= NEAR_TIE_MARGIN
        ]
        near_tied.sort(
            key=lambda item: (
                sum(
                    1
                    for match in item[0].get("requirement_matches", []) or []
                    if match.get("match_label") == "direct"
                    and match.get("importance") in {"core", "deal_breaker", "required"}
                ),
                sum(
                    1
                    for match in item[0].get("requirement_matches", []) or []
                    if match.get("requirement_id") not in covered_requirements
                    and match.get("importance") in {"core", "deal_breaker", "required"}
                ),
                _ranking_tiebreak_tuple(item[0]),
                item[1],
            ),
            reverse=True,
        )

        chosen, selection_score, unique_bonus, overlap_penalty = near_tied[0]
        chosen["selection_score"] = round(selection_score, 4)
        chosen["unique_coverage_bonus"] = round(unique_bonus, 4)
        chosen["overlap_penalty"] = round(overlap_penalty, 4)
        chosen["selection_rank"] = len(selected) + 1
        selected.append(chosen)

        newly_covered = {
            match.get("requirement_id")
            for match in chosen.get("requirement_matches", []) or []
            if match.get("requirement_id")
        }
        covered_requirements.update(newly_covered)

        selection_debug.append(
            {
                "selection_rank": len(selected),
                "project_id": chosen.get("project_id"),
                "title": chosen.get("display_title") or chosen.get("title"),
                "base_score": chosen.get("final_score", 0),
                "selection_score": round(selection_score, 4),
                "unique_coverage_bonus": round(unique_bonus, 4),
                "overlap_penalty": round(overlap_penalty, 4),
                "covered_requirement_ids_after_selection": sorted(covered_requirements),
                "near_tied_project_ids": [
                    item[0].get("project_id") for item in near_tied
                ],
            }
        )

        chosen_id = chosen.get("project_id")
        remaining = [row for row in remaining if row.get("project_id") != chosen_id]

    selected_ids = {row.get("project_id") for row in selected}
    final_order = selected + [
        row for row in ranked_rows if row.get("project_id") not in selected_ids
    ]

    return final_order, selection_debug


def _collect_supported_skill_candidates(
    *,
    resume_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    selected_project_identity_index: dict[str, Any],
    raw_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    # AI skill lines are retained elsewhere as diagnostics, but they do not
    # control the canonical display spelling or category. This keeps the final
    # Skills section stable across equivalent generations.

    def add(
        value: Any,
        *,
        source: str,
        category_hint: str = "",
        selected_project: bool = False,
        selected_project_match_method: str = "",
    ) -> None:
        display = _clean_text(value)
        key = _normalise_skill_key(display)
        if not key or key in _SOFT_SKILL_LINE_TERMS:
            return

        row = candidates.setdefault(
            key,
            {
                "skill": display,
                "skill_key": key,
                "sources": set(),
                "category_hints": [],
                "selected_project_support": False,
                "selected_project_support_methods": set(),
                "resume_support": False,
                "evidence_titles": set(),
            },
        )
        row["sources"].add(source)

        # Equivalent skill identities may come from both the frozen resume
        # snapshot and the current Evidence Library. Keep one deterministic
        # identity, but prefer the user's current Evidence Library spelling for
        # new tailoring output (for example GitHub Actions (CI)).
        if source.startswith("evidence_library"):
            row["skill"] = display

        if category_hint:
            row["category_hints"].append(category_hint)
        if selected_project:
            row["selected_project_support"] = True
            if selected_project_match_method:
                row["selected_project_support_methods"].add(
                    selected_project_match_method
                )
        if source.startswith("resume"):
            row["resume_support"] = True

    resume_skills = resume_profile.get("skills", {}) or {}
    if isinstance(resume_skills, dict):
        for group, values in resume_skills.items():
            for value in values or []:
                add(value, source=f"resume.{group}", category_hint=group)

    for item in evidence_items:
        if not isinstance(item, dict):
            continue

        title = _clean_text(item.get("title"))
        selected, selected_match_method = (
            match_evidence_project_to_selected(
                item,
                selected_project_identity_index,
            )
        )

        for value in item.get("skills", []) or []:
            add(
                value,
                source="evidence_library.skill",
                category_hint="skill",
                selected_project=selected,
                selected_project_match_method=selected_match_method,
            )
            key = _normalise_skill_key(value)
            if key in candidates and title:
                candidates[key]["evidence_titles"].add(title)

        for value in item.get("tools", []) or []:
            add(
                value,
                source="evidence_library.tool",
                category_hint="tool",
                selected_project=selected,
                selected_project_match_method=selected_match_method,
            )
            key = _normalise_skill_key(value)
            if key in candidates and title:
                candidates[key]["evidence_titles"].add(title)

    return candidates


def _skill_category(skill: str, hints: list[str]) -> str:
    key = _normalise_skill_key(skill)
    hint_text = " ".join(_normalise_key(value) for value in hints)

    if key in _GAME_ENGINE_HINTS or any(term in key for term in ("game ", "gameplay", "unity", "unreal", "fmod")):
        return "Game & Engine"
    if key in _AI_DATA_HINTS or any(term in key for term in ("machine learning", "rag", "llm", "data ", "openai")):
        return "AI & Data"
    if key in _BACKEND_HINTS or any(term in key for term in ("database", "backend", "postgres", "supabase", "security", "api")):
        return "Backend & Database"
    if key in _WEB_APP_HINTS or any(term in key for term in ("android", "frontend", "react", "web ", "mobile")):
        return "Web & App"
    if key in _PROGRAMMING_LANGUAGE_KEYS or "language" in hint_text or "languages" in hint_text:
        return "Programming"
    if key in _TOOL_HINTS or "tool" in hint_text or "tools" in hint_text:
        return "Tools"
    if "framework" in hint_text:
        return "Web & App"
    if "platform" in hint_text and any(term in key for term in ("unity", "unreal")):
        return "Game & Engine"
    if "concept" in hint_text:
        return "Backend & Database" if any(term in key for term in ("api", "cloud", "database")) else "Tools"
    return "Tools"


def _skill_requirement_relevance(
    skill: str,
    requirements: dict[str, dict[str, Any]],
) -> tuple[int, bool, bool, list[str], list[dict[str, Any]]]:
    """Score one evidence-supported skill against canonical JD requirements.

    Recognised requirements remain wholly owned by the Phase 6D taxonomy. For
    unrecognised requirements, only explicit non-generic tokens may establish
    relevance; a skill such as ``data`` cannot become highly relevant merely
    because a JD says ``data structures and algorithms``.
    """
    key = _normalise_skill_key(skill)
    skill_tokens = _tokens(key)
    required_match = False
    preferred_match = False
    matched_ids: list[str] = []
    details: list[dict[str, Any]] = []
    best = 0

    for requirement_id, requirement in requirements.items():
        importance = _normalise_key(requirement.get("importance"))
        decision = match_requirement_to_candidate(
            requirement=requirement,
            candidate_evidence_text=skill,
        )
        taxonomy_label = decision.get("label")

        if taxonomy_label is not None:
            label = _normalise_match_label(taxonomy_label)
            if label == "direct":
                relevance = 5 if importance in {"core", "deal_breaker", "required"} else 4
            elif label == "transferable":
                relevance = 4 if importance in {"core", "deal_breaker", "required"} else 3
            elif label == "weak":
                relevance = 2 if importance in {"core", "deal_breaker", "required"} else 1
            else:
                continue
            strategy = "phase6d_capability_taxonomy"
            capability_id = _clean_text(decision.get("capability_id"))
            overlap = 1.0
        else:
            requirement_tokens = _specific_requirement_tokens(requirement)
            specific_skill_tokens = skill_tokens - _GENERIC_SKILL_RANKING_TOKENS
            overlap_tokens = specific_skill_tokens & requirement_tokens
            if not specific_skill_tokens or not overlap_tokens:
                continue

            overlap = len(overlap_tokens) / len(specific_skill_tokens)
            exact_technical = bool(
                overlap_tokens & _EXPLICIT_TECHNICAL_TOKENS
            )
            if specific_skill_tokens <= requirement_tokens and (
                len(specific_skill_tokens) >= 2 or exact_technical
            ):
                label = "direct"
                relevance = 5 if importance in {"core", "deal_breaker", "required"} else 4
            elif len(overlap_tokens) >= 2 and overlap >= 0.75:
                label = "transferable"
                relevance = 4 if importance in {"core", "deal_breaker", "required"} else 3
            elif overlap >= 0.75 and len(specific_skill_tokens) >= 2:
                label = "weak"
                relevance = 2 if importance in {"core", "deal_breaker", "required"} else 1
            else:
                continue
            strategy = "unrecognised_explicit_skill_tokens"
            capability_id = ""

        best = max(best, relevance)
        matched_ids.append(requirement_id)
        details.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": _clean_text(requirement.get("text")),
                "match_label": label,
                "strategy": strategy,
                "capability_id": capability_id,
                "overlap": round(overlap, 4),
            }
        )
        # Weak evidence remains explainable, but does not make a candidate a
        # primary required/preferred skill by itself.
        if (
            label in {"direct", "transferable"}
            and importance in {"core", "deal_breaker", "required"}
        ):
            required_match = True
        elif label in {"direct", "transferable"} and importance == "preferred":
            preferred_match = True

    return (
        best,
        required_match,
        preferred_match,
        sorted(set(matched_ids)),
        sorted(
            details,
            key=lambda item: (
                -_MATCH_ORDER.get(item["match_label"], 0),
                item["requirement_id"],
                item["strategy"],
            ),
        ),
    )


def _skill_ranking_explanation(
    *,
    skill: str,
    match_details: list[dict[str, Any]],
    resume_support: bool,
    selected_project_support: bool,
) -> str:
    if match_details:
        primary = match_details[0]
        label = _clean_text(primary.get("match_label")).capitalize()
        reason = (
            f"{label} match to canonical JD requirement “{_clean_text(primary.get('requirement_text'))}” "
            f"through the evidence-supported skill “{_clean_text(skill)}”."
        )
        capability_id = _clean_text(primary.get("capability_id"))
        if capability_id:
            reason += f" Capability relationship: {capability_id}."
        return reason
    if selected_project_support:
        return (
            "No direct canonical JD requirement match; retained because the "
            "skill is supported by a Python-selected project."
        )
    if resume_support:
        return (
            "No direct canonical JD requirement match; retained because the "
            "skill is supported by the frozen résumé profile."
        )
    return "No direct canonical JD requirement match or supporting résumé evidence."


def build_deterministic_skills_result(
    *,
    raw_result: dict[str, Any],
    resume_profile: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    stable_analysis: dict[str, Any],
    selected_projects_result: dict[str, Any] | None = None,
    max_items: int = 20,
) -> dict[str, Any]:
    """Build stable Skills lines and Python-owned priority metadata."""
    requirements = _requirement_index(stable_analysis)
    if not requirements:
        raise ValueError(
            "Phase 6B Skills ranking requires stable_analysis.canonical_requirements."
        )

    selected_projects = [
        project
        for project in (
            (selected_projects_result or {}).get(
                "recommended_projects",
                [],
            )
            or []
        )
        if isinstance(project, dict)
    ]
    selected_project_identity_index = (
        build_selected_project_identity_index(
            selected_projects=selected_projects,
            evidence_items=evidence_items,
        )
    )

    candidates = _collect_supported_skill_candidates(
        resume_profile=resume_profile,
        evidence_items=evidence_items,
        selected_project_identity_index=(
            selected_project_identity_index
        ),
        raw_result=raw_result,
    )

    rows: list[dict[str, Any]] = []

    for candidate in candidates.values():
        (
            relevance,
            required_match,
            preferred_match,
            requirement_ids,
            match_details,
        ) = _skill_requirement_relevance(candidate["skill"], requirements)

        source_count = len(candidate["sources"])
        evidence_strength = min(
            5,
            1
            + min(2, source_count)
            + (1 if candidate["resume_support"] else 0)
            + (1 if candidate["selected_project_support"] else 0),
        )

        if relevance == 0:
            relevance = 3 if candidate["selected_project_support"] else 2 if candidate["resume_support"] else 1

        priority_score = (
            relevance * 12
            + evidence_strength * 6
            + (8 if candidate["selected_project_support"] else 0)
            + (3 if candidate["resume_support"] else 0)
        )

        rows.append(
            {
                "skill": candidate["skill"],
                "skill_key": candidate["skill_key"],
                "category": _skill_category(candidate["skill"], candidate["category_hints"]),
                "jd_relevance": relevance,
                "evidence_strength": evidence_strength,
                "required_match": required_match,
                "preferred_match": preferred_match,
                "matched_requirement_ids": requirement_ids,
                "requirement_match_details": match_details,
                "matched_capability_ids": sorted(
                    {
                        _clean_text(item.get("capability_id"))
                        for item in match_details
                        if _clean_text(item.get("capability_id"))
                    }
                ),
                "selected_project_support": candidate["selected_project_support"],
                "selected_project_support_methods": sorted(
                    candidate["selected_project_support_methods"]
                ),
                "resume_support": candidate["resume_support"],
                "evidence_titles": sorted(candidate["evidence_titles"]),
                "deterministic_priority_score": priority_score,
                "reason": _skill_ranking_explanation(
                    skill=candidate["skill"],
                    match_details=match_details,
                    resume_support=candidate["resume_support"],
                    selected_project_support=candidate["selected_project_support"],
                ),
                "ranking_version": SKILL_RANKING_VERSION,
            }
        )

    rows.sort(
        key=lambda row: (
            row["deterministic_priority_score"],
            int(row["required_match"]),
            int(row["preferred_match"]),
            int(row["selected_project_support"]),
            int(row["resume_support"]),
            -_CATEGORY_ORDER.get(row["category"].lower(), 99),
            tuple(-ord(character) for character in _normalise_key(row["skill"])),
        ),
        reverse=True,
    )

    primary_rows = [
        row
        for row in rows
        if row["selected_project_support"]
        or row["required_match"]
        or row["preferred_match"]
    ]
    secondary_rows = [row for row in rows if row not in primary_rows]
    selected_rows = (primary_rows + secondary_rows)[: max(1, max_items)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected_rows:
        grouped[row["category"]].append(row)

    skill_lines: list[dict[str, Any]] = []
    for category in sorted(
        grouped,
        key=lambda value: (_CATEGORY_ORDER.get(value.lower(), 99), value.lower()),
    ):
        category_rows = sorted(
            grouped[category],
            key=lambda row: (
                -row["deterministic_priority_score"],
                _normalise_key(row["skill"]),
            ),
        )
        skill_lines.append(
            {
                "category": category,
                "items": [row["skill"] for row in category_rows],
            }
        )

    result = deepcopy(raw_result or {})
    result["skill_lines"] = skill_lines
    result["skill_priorities"] = selected_rows
    result["deterministic_skill_ranking"] = rows
    result["skill_ranking_version"] = SKILL_RANKING_VERSION
    result["skill_selection_owner"] = "python_canonical_supported_evidence_pool"
    result["project_identity_version"] = PROJECT_IDENTITY_VERSION
    result["selected_project_identity_debug"] = (
        selected_project_identity_index["debug"]
    )
    result.setdefault("notes", [])
    result["notes"] = [
        *[_clean_text(value) for value in result.get("notes", []) or [] if _clean_text(value)],
        (
            "Python selected and ordered supported Skills using canonical JD "
            "requirements and the selected project set; AI numeric priorities "
            "were not used."
        ),
    ]
    return result
