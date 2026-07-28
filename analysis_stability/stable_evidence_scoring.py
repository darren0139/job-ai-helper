"""
Generic, deterministic requirement canonicalisation and evidence-linked scoring.

This module deliberately contains no role-specific aliases such as QA, cloud,
networking, game development, or DevOps. It learns acronym expansions from the
current JD text/profile and uses generic lexical normalisation plus fixed scoring
rules.

The AI may still extract the JD and match rows, but this module owns:
- canonical requirement IDs;
- deduplication;
- evidence-linked match labels;
- validation;
- deterministic scoring;
- alignment bands and tie margins.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import Any

from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.phase6d_stable_scoring_adapter import (
    apply_taxonomy_caps_to_requirements,
)

SCORING_VERSION = "stable-evidence-v1.2-phase6d"

MATCH_VALUES = {
    "direct": 1.0,
    "transferable": 0.55,
    "weak": 0.20,
    "none": 0.0,
}

IMPORTANCE_WEIGHTS = {
    "deal_breaker": 5.0,
    "required": 4.0,
    "core": 3.0,
    "preferred": 1.0,
}

BAND_BOUNDARIES = (
    (80, "strong alignment"),
    (65, "moderate alignment"),
    (50, "partial alignment"),
    (0, "weak alignment"),
)

GENERIC_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "being", "by", "for",
    "from", "good", "have", "having", "in", "including", "is", "it",
    "of", "on", "or", "our", "perform", "the", "their", "this", "to", "using",
    "with", "within", "work", "working", "experience",
}

_REQUIRED_HINTS = (
    "must",
    "required",
    "minimum",
    "need",
    "needs",
    "essential",
    "mandatory",
)

_PREFERRED_HINTS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "plus",
    "advantage",
    "familiarity",
    "ideally",
)

_MATCH_TYPE_MAP = {
    "exact": "direct",
    "equivalent": "direct",
    "direct": "direct",
    "strong": "direct",
    "partial": "transferable",
    "transferable": "transferable",
    "related": "weak",
    "weak": "weak",
    "none": "none",
    "missing": "none",
    "unsupported": "none",
}


# Subjective motivation or disposition claims cannot be inferred merely from
# education, projects, tools, or employment in the same domain. They need an
# explicit statement in the current resume, such as "passionate about games"
# or "strong interest in cybersecurity".
_SUBJECTIVE_CUE_PATTERNS = (
    re.compile(r"\bpassion(?:ate|ately)?\b", re.IGNORECASE),
    re.compile(r"\benthusias(?:m|tic|tically)\b", re.IGNORECASE),
    re.compile(r"\binterest(?:ed)?\b", re.IGNORECASE),
    re.compile(r"\bmotivat(?:e|ed|ion|ional)\b", re.IGNORECASE),
    re.compile(r"\beager(?:ness)?\b", re.IGNORECASE),
    re.compile(r"\bcommit(?:ted|ment)\b", re.IGNORECASE),
    re.compile(r"\bwilling(?:ness)?\b", re.IGNORECASE),
    re.compile(r"\benjoy(?:s|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\blove(?:s|d|ing)?\b", re.IGNORECASE),
    re.compile(r"\bcurios(?:ity|ous)\b", re.IGNORECASE),
    re.compile(r"\bdesire(?:s|d)?\b", re.IGNORECASE),
    re.compile(r"\bkeen\b", re.IGNORECASE),
)

_SUBJECTIVE_CUE_TOKEN_SOURCE = (
    "passion passionate enthusiasm enthusiastic interest interested "
    "motivation motivated eager eagerness committed commitment willing "
    "willingness enjoy enjoys enjoyed love loves loved curious curiosity "
    "desire desired keen strong personal demonstrated about toward towards"
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise_basic(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9+#.-]+", " ", text)
    return " ".join(text.split())


def _simple_stem(token: str) -> str:
    if len(token) <= 4:
        return token

    # Keep common verb forms aligned without a domain-specific vocabulary.
    # Example: collaborate / collaborated -> collabor.
    if token.endswith("ated") and len(token) >= 8:
        return token[:-4]
    if token.endswith("ate") and len(token) >= 7:
        return token[:-3]

    for suffix in ("isations", "izations", "ation", "ments", "ment", "ingly", "edly", "ing", "ers", "ies", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            root = token[: -len(suffix)]
            if suffix == "ies":
                return root + "y"
            return root

    return token


def _tokenise(value: Any, acronym_map: dict[str, str] | None = None) -> list[str]:
    text = _normalise_basic(value)

    if acronym_map:
        expanded: list[str] = []
        for token in text.split():
            expansion = acronym_map.get(token)
            if expansion:
                expanded.extend(_normalise_basic(expansion).split())
            else:
                expanded.append(token)
        tokens = expanded
    else:
        tokens = text.split()

    return [
        _simple_stem(token)
        for token in tokens
        if token and token not in GENERIC_STOPWORDS
    ]


def _contains_subjective_cue(value: Any) -> bool:
    text = _clean_text(value)
    return any(pattern.search(text) for pattern in _SUBJECTIVE_CUE_PATTERNS)


def _is_explicit_only_subjective_requirement(
    requirement: dict[str, Any],
) -> bool:
    focus = requirement.get("atomic_focus") or requirement.get("text", "")
    return _contains_subjective_cue(focus)


def _subjective_domain_tokens(
    value: Any,
    acronym_map: dict[str, str] | None = None,
) -> set[str]:
    cue_tokens = set(_tokenise(_SUBJECTIVE_CUE_TOKEN_SOURCE, acronym_map))
    return {
        token
        for token in _tokenise(value, acronym_map)
        if token not in cue_tokens
    }


def _explicit_subjective_evidence_supported(
    requirement: dict[str, Any],
    candidate_text: Any,
    acronym_map: dict[str, str],
) -> bool:
    """Return True only for an explicit motivation statement in the same domain."""
    candidate = _clean_text(candidate_text)
    if not _contains_subjective_cue(candidate):
        return False

    focus = requirement.get("atomic_focus") or requirement.get("text", "")
    required_domain = _subjective_domain_tokens(focus, acronym_map)
    if not required_domain:
        return True

    candidate_domain = _subjective_domain_tokens(candidate, acronym_map)
    return bool(required_domain & candidate_domain)


def _find_explicit_subjective_evidence(
    requirement: dict[str, Any],
    evidence_index: list[dict[str, str]],
    acronym_map: dict[str, str],
) -> dict[str, str] | None:
    for row in evidence_index:
        if _explicit_subjective_evidence_supported(
            requirement,
            row.get("text", ""),
            acronym_map,
        ):
            return {
                **row,
                "reason": (
                    "The current resume explicitly states the motivation or "
                    "interest required by this subjective requirement."
                ),
                "evidence_similarity": "1.000",
            }
    return None


def _canonical_key(value: Any, acronym_map: dict[str, str] | None = None) -> str:
    tokens = _tokenise(value, acronym_map)
    return " ".join(sorted(dict.fromkeys(tokens)))


def _stable_id(prefix: str, canonical_key: str) -> str:
    digest = hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def learn_acronym_map(text_values: list[str]) -> dict[str, str]:
    """
    Learn aliases from the current input instead of hard-coding a domain.

    Examples learned generically:
      "continuous integration (CI)" -> ci => continuous integration
      "service-level agreement (SLA)" -> sla => service-level agreement
    """
    acronym_map: dict[str, str] = {}

    for raw_value in text_values:
        value = _clean_text(raw_value)
        if not value:
            continue

        for match in re.finditer(
            r"([A-Za-z][A-Za-z0-9 +/&.-]{2,80}?)\s*\(([A-Z][A-Z0-9/&+-]{1,9})\)",
            value,
        ):
            phrase = _clean_text(match.group(1))
            phrase = re.split(r"[.;:]\s*", phrase)[-1].strip()
            acronym = _normalise_basic(match.group(2))

            phrase_words = [
                word
                for word in _normalise_basic(phrase).split()
                if word not in GENERIC_STOPWORDS
            ]

            if acronym and len(phrase_words) >= 2:
                acronym_map[acronym] = " ".join(phrase_words)

    # Infer an acronym only when the acronym itself appears in the corpus and
    # its letters match a multi-word phrase from the same corpus.
    corpus_normalised = " ".join(_normalise_basic(value) for value in text_values)
    uppercase_tokens = {
        token.lower()
        for value in text_values
        for token in re.findall(r"\b[A-Z][A-Z0-9]{1,8}\b", value)
    }

    phrases: list[str] = []
    for value in text_values:
        for chunk in re.split(r"[,;:.()\n]+", value):
            words = [
                word
                for word in _normalise_basic(chunk).split()
                if word not in GENERIC_STOPWORDS
            ]
            if 2 <= len(words) <= 8:
                phrases.append(" ".join(words))

    for acronym in uppercase_tokens:
        if acronym in acronym_map:
            continue

        for phrase in phrases:
            initials = "".join(word[0] for word in phrase.split() if word)
            if initials == acronym and re.search(rf"\b{re.escape(acronym)}\b", corpus_normalised):
                acronym_map[acronym] = phrase
                break

    return acronym_map


def _token_similarity(
    left: Any,
    right: Any,
    acronym_map: dict[str, str] | None = None,
) -> float:
    left_tokens = set(_tokenise(left, acronym_map))
    right_tokens = set(_tokenise(right, acronym_map))

    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = intersection / union

    containment = max(
        intersection / len(left_tokens),
        intersection / len(right_tokens),
    )

    return max(jaccard, containment * 0.92)


def _importance_rank(value: str) -> int:
    order = {
        "preferred": 1,
        "core": 2,
        "required": 3,
        "deal_breaker": 4,
    }
    return order.get(value, 0)


def _classify_raw_importance(text: str, default: str = "core") -> str:
    normalised = _normalise_basic(text)

    if any(hint in normalised for hint in _PREFERRED_HINTS):
        return "preferred"

    if any(hint in normalised for hint in _REQUIRED_HINTS):
        return "required"

    return default



_RAW_RESPONSIBILITY_HEADINGS = {
    "job description",
    "responsibilities",
    "job responsibilities",
    "what you will do",
    "what youll do",
    "duties",
}

_RAW_REQUIREMENT_HEADINGS = {
    "job requirements",
    "requirements",
    "qualifications",
    "minimum qualifications",
    "what we are looking for",
    "what were looking for",
}



def _split_top_level_commas(value: str) -> list[str]:
    """Split a comma list without breaking text inside parentheses."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for character in value:
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1

        if character == "," and depth == 0:
            part = "".join(current).strip(" ,;.-")
            if part:
                parts.append(part)
            current = []
            continue

        current.append(character)

    final = "".join(current).strip(" ,;.-")
    if final:
        parts.append(final)

    if len(parts) >= 2:
        parts[-1] = re.sub(
            r"^(?:and|or)\s+",
            "",
            parts[-1],
            flags=re.IGNORECASE,
        ).strip()

    return parts


def _context_label_from_head(head: str) -> str:
    """Return a short generic subject context for enumerated child clauses."""
    cleaned = _clean_text(head).strip(" ,;:.-")
    preposition_parts = re.split(
        r"\b(?:of|for)\b",
        cleaned,
        flags=re.IGNORECASE,
    )

    if len(preposition_parts) > 1:
        candidate = preposition_parts[-1].strip(" ,;:.-")
        candidate = re.sub(
            r"^(?:the|a|an)\s+",
            "",
            candidate,
            flags=re.IGNORECASE,
        )
        if 1 <= len(_tokenise(candidate)) <= 7:
            return candidate

    return ""


def _clause_record(
    *,
    text: str,
    importance: str,
    parent_text: str,
    focus_text: str | None = None,
    atomic_group_id: str = "",
    is_atomic: bool = False,
) -> dict[str, Any]:
    cleaned = _clean_text(text).strip(" ,;:.-")
    focus = _clean_text(focus_text or cleaned).strip(" ,;:.-")
    group_id = atomic_group_id or _stable_id(
        "grp",
        _normalise_basic(parent_text or cleaned),
    )

    return {
        "text": cleaned,
        "importance": importance,
        "parent_text": _clean_text(parent_text or cleaned),
        "atomic_focus": focus,
        "atomic_group_id": group_id,
        "is_atomic": bool(is_atomic),
    }


def _split_non_preference_clause(
    value: str,
    importance: str,
    parent_text: str,
) -> list[dict[str, Any]]:
    """Split clear compound clauses into stable, atomic requirements."""
    group_id = _stable_id("grp", _normalise_basic(parent_text))

    for connector in (" along with ", " as well as "):
        if connector in value.lower():
            parts = re.split(
                re.escape(connector),
                value,
                maxsplit=1,
                flags=re.IGNORECASE,
            )
            cleaned = [part.strip(" ,;.-") for part in parts]
            if all(len(_tokenise(part)) >= 3 for part in cleaned):
                return [
                    _clause_record(
                        text=part,
                        importance=importance,
                        parent_text=parent_text,
                        focus_text=part,
                        atomic_group_id=group_id,
                        is_atomic=True,
                    )
                    for part in cleaned
                    if part
                ]

    knowledge_match = re.match(
        r"^(?P<first>.+?)\s+with\s+"
        r"(?P<second>(?:basic|strong|working|solid|good|deep|broad)\s+knowledge\b.+)$",
        value,
        flags=re.IGNORECASE,
    )
    if knowledge_match:
        parts = [
            knowledge_match.group("first").strip(" ,;.-"),
            knowledge_match.group("second").strip(" ,;.-"),
        ]
        if all(len(_tokenise(part)) >= 2 for part in parts):
            return [
                _clause_record(
                    text=part,
                    importance=importance,
                    parent_text=parent_text,
                    focus_text=part,
                    atomic_group_id=group_id,
                    is_atomic=True,
                )
                for part in parts
            ]

    enumeration = re.match(
        r"^(?P<head>.+?)\s+(?:from|including|such as)\s+(?P<tail>.+)$",
        value,
        flags=re.IGNORECASE,
    )
    if enumeration:
        head = enumeration.group("head").strip(" ,;:.-")
        tail = enumeration.group("tail").strip(" ,;:.-")
        items = _split_top_level_commas(tail)

        if len(items) >= 3:
            context = _context_label_from_head(head)
            records = [
                _clause_record(
                    text=head,
                    importance=importance,
                    parent_text=parent_text,
                    focus_text=head,
                    atomic_group_id=group_id,
                    is_atomic=True,
                )
            ]

            for item in items:
                main = item
                nested = ""
                nested_match = re.match(
                    r"^(?P<main>.+?)\s*\(\s*including\s+(?P<nested>.+?)\s*\)$",
                    item,
                    flags=re.IGNORECASE,
                )
                if nested_match:
                    main = nested_match.group("main").strip(" ,;.-")
                    nested = nested_match.group("nested").strip(" ,;.-")

                display = f"{context} {main}".strip() if context else main
                records.append(
                    _clause_record(
                        text=display,
                        importance=importance,
                        parent_text=parent_text,
                        focus_text=main,
                        atomic_group_id=group_id,
                        is_atomic=True,
                    )
                )

                if nested:
                    parent_action = ""
                    main_tokens = _normalise_basic(main).split()
                    if main_tokens and main_tokens[-1] in {
                        "handling",
                        "management",
                        "monitoring",
                        "evaluation",
                        "maintenance",
                        "support",
                        "coordination",
                    }:
                        parent_action = main_tokens[-1]

                    nested_display = " ".join(
                        part
                        for part in (context, nested, parent_action)
                        if part
                    )
                    records.append(
                        _clause_record(
                            text=nested_display,
                            importance=importance,
                            parent_text=parent_text,
                            focus_text=nested,
                            atomic_group_id=group_id,
                            is_atomic=True,
                        )
                    )

            return records

    return [
        _clause_record(
            text=value,
            importance=importance,
            parent_text=parent_text,
            focus_text=value,
            atomic_group_id=group_id,
            is_atomic=False,
        )
    ]


def _split_requirement_clauses(
    text: str,
    default_importance: str,
) -> list[dict[str, Any]]:
    """Split preference, paired-skill and enumerated clauses deterministically."""
    value = _clean_text(text)
    if not value:
        return []

    parent_text = value
    preference_match = re.search(
        r"\b(preferably|ideally|nice[- ]to[- ]have|would be preferred)\b",
        value,
        flags=re.IGNORECASE,
    )

    if preference_match:
        before = value[: preference_match.start()].strip(" ,;.-")
        after = value[preference_match.end() :].strip(" ,;.-")
        after_normalised = _normalise_basic(after)
        context_only = after_normalised.startswith(
            ("within ", "in ", "at ", "from ", "for ", "with ")
        )

        if before and after and not context_only and len(_tokenise(after)) >= 3:
            records = _split_non_preference_clause(
                before,
                default_importance,
                parent_text,
            )
            records.extend(
                _split_non_preference_clause(
                    after,
                    "preferred",
                    parent_text,
                )
            )
            return records

    return _split_non_preference_clause(
        value,
        default_importance,
        parent_text,
    )


def _raw_jd_requirement_rows(raw_jd_text: str) -> list[dict[str, Any]]:
    """Extract stable atomic requirement rows from explicit JD sections."""
    rows: list[dict[str, Any]] = []
    active_section = ""

    for raw_line in raw_jd_text.splitlines():
        value = _clean_text(raw_line).strip("-•* \t")
        if not value:
            continue

        heading = _normalise_basic(value).rstrip(":")
        if heading in _RAW_RESPONSIBILITY_HEADINGS:
            active_section = "responsibilities"
            continue
        if heading in _RAW_REQUIREMENT_HEADINGS:
            active_section = "requirements"
            continue

        if not active_section or len(value) < 12:
            continue

        default_importance = (
            "core" if active_section == "responsibilities" else "required"
        )

        for clause in _split_requirement_clauses(
            value,
            default_importance,
        ):
            rows.append(
                {
                    **clause,
                    "importance": _classify_raw_importance(
                        clause["text"],
                        clause["importance"],
                    ),
                    "source": f"raw_jd.{active_section}",
                }
            )

    return rows


def _coverage_metrics(
    requirement_text: str,
    candidate_text: str,
    acronym_map: dict[str, str] | None = None,
) -> tuple[float, int]:
    required_tokens = set(_tokenise(requirement_text, acronym_map))
    candidate_tokens = set(_tokenise(candidate_text, acronym_map))

    if not required_tokens or not candidate_tokens:
        return 0.0, 0

    intersection = required_tokens & candidate_tokens
    return len(intersection) / len(required_tokens), len(intersection)


def _negative_reason_segments(reason: str) -> list[str]:
    value = _clean_text(reason)
    if not value:
        return []

    segments: list[str] = []
    pattern = re.compile(
        r"\b(?:but|however|although|yet|without|"
        r"does\s+not|do\s+not|did\s+not|cannot|can't|"
        r"not\s+explicitly|not\s+specified|not\s+stated|"
        r"not\s+identified|not\s+established|no\s+explicit|"
        r"no\s+evidence)\b",
        flags=re.IGNORECASE,
    )

    for match in pattern.finditer(value):
        tail = value[match.start() :]
        tail = re.split(r"[.;]", tail, maxsplit=1)[0]
        if tail:
            segments.append(tail)

    return segments


def _reason_limits_requirement(
    reason: str,
    requirement_focus: str,
    acronym_map: dict[str, str] | None = None,
) -> bool:
    focus_tokens = set(_tokenise(requirement_focus, acronym_map))
    if not focus_tokens:
        return False

    for segment in _negative_reason_segments(reason):
        segment_tokens = set(_tokenise(segment, acronym_map))
        overlap = focus_tokens & segment_tokens
        if overlap and (
            len(overlap) >= 2
            or len(overlap) / len(focus_tokens) >= 0.25
        ):
            return True

    return False


def _requirement_sources(
    jd_profile: dict[str, Any],
    raw_jd_text: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    raw_rows = _raw_jd_requirement_rows(raw_jd_text)
    rows.extend(raw_rows)

    field_specs = (
        ("deal_breakers", "deal_breaker"),
        ("required_skills", "required"),
        ("responsibilities", "core"),
        ("soft_skills", "core"),
        ("preferred_skills", "preferred"),
        ("tools_technologies", "core"),
    )

    for field_name, default_importance in field_specs:
        for raw_value in jd_profile.get(field_name, []) or []:
            value = _clean_text(raw_value)
            if not value:
                continue

            importance = default_importance
            if field_name in {
                "responsibilities",
                "soft_skills",
                "tools_technologies",
            }:
                importance = _classify_raw_importance(
                    value,
                    default_importance,
                )

            for clause in _split_requirement_clauses(
                value,
                importance,
            ):
                if raw_rows:
                    continue

                rows.append(
                    {
                        **clause,
                        "source": f"jd_profile.{field_name}",
                    }
                )

    if not rows:
        for line in raw_jd_text.splitlines():
            value = _clean_text(line).strip("-•* ")
            if len(value) < 20:
                continue
            for clause in _split_requirement_clauses(
                value,
                _classify_raw_importance(value, "core"),
            ):
                rows.append(
                    {
                        **clause,
                        "source": "raw_jd_fallback",
                    }
                )

    return rows


def canonicalise_requirements(
    jd_profile: dict[str, Any],
    raw_jd_text: str = "",
) -> dict[str, Any]:
    """Build stable atomic requirement rows from the raw JD/profile."""
    source_rows = _requirement_sources(jd_profile, raw_jd_text)
    text_values = [row["text"] for row in source_rows]
    text_values.append(raw_jd_text)
    acronym_map = learn_acronym_map(text_values)

    canonical_rows: list[dict[str, Any]] = []
    merge_debug: list[dict[str, Any]] = []

    for source_row in source_rows:
        text = source_row["text"]
        key = _canonical_key(text, acronym_map)
        focus_key = _canonical_key(
            source_row.get("atomic_focus", text),
            acronym_map,
        )
        if not key:
            continue

        best_index: int | None = None
        best_similarity = 0.0

        for index, existing in enumerate(canonical_rows):
            exact_key = key == existing["canonical_key"]
            same_group_different_focus = (
                source_row.get("atomic_group_id")
                and source_row.get("atomic_group_id")
                == existing.get("atomic_group_id")
                and focus_key != existing.get("atomic_focus_key")
            )
            if same_group_different_focus and not exact_key:
                continue

            similarity = _token_similarity(
                text,
                existing["text"],
                acronym_map,
            )
            focus_similarity = _token_similarity(
                source_row.get("atomic_focus", text),
                existing.get("atomic_focus", existing["text"]),
                acronym_map,
            )

            either_atomic = bool(
                source_row.get("is_atomic")
                or existing.get("is_atomic")
            )
            threshold_met = (
                exact_key
                or (
                    similarity >= (0.94 if either_atomic else 0.86)
                    and focus_similarity >= (0.90 if either_atomic else 0.80)
                )
            )

            if threshold_met:
                if exact_key:
                    similarity = 1.0
                if similarity > best_similarity:
                    best_index = index
                    best_similarity = similarity

        if best_index is None:
            canonical_rows.append(
                {
                    "requirement_id": _stable_id("req", key),
                    "text": text,
                    "canonical_key": key,
                    "importance": source_row["importance"],
                    "sources": [source_row["source"]],
                    "variants": [text],
                    "parent_text": source_row.get("parent_text", text),
                    "atomic_focus": source_row.get("atomic_focus", text),
                    "atomic_focus_key": focus_key,
                    "atomic_group_id": source_row.get(
                        "atomic_group_id",
                        _stable_id("grp", key),
                    ),
                    "is_atomic": bool(source_row.get("is_atomic")),
                }
            )
            continue

        existing = canonical_rows[best_index]
        existing["sources"] = list(
            dict.fromkeys(existing["sources"] + [source_row["source"]])
        )
        existing["variants"] = list(
            dict.fromkeys(existing["variants"] + [text])
        )

        if _importance_rank(source_row["importance"]) > _importance_rank(
            existing["importance"]
        ):
            existing["importance"] = source_row["importance"]

        merge_debug.append(
            {
                "kept_requirement_id": existing["requirement_id"],
                "kept_text": existing["text"],
                "merged_text": text,
                "similarity": round(best_similarity, 3),
            }
        )

    group_counts: dict[str, int] = {}
    for row in canonical_rows:
        group_id = row.get("atomic_group_id") or row["requirement_id"]
        group_counts[group_id] = group_counts.get(group_id, 0) + 1

    for row in canonical_rows:
        group_id = row.get("atomic_group_id") or row["requirement_id"]
        row["group_weight_fraction"] = round(
            1.0 / group_counts[group_id],
            6,
        )

    return {
        "requirements": canonical_rows,
        "acronym_map": acronym_map,
        "merge_debug": merge_debug,
    }


def build_resume_evidence_index(
    resume_profile: dict[str, Any] | None,
    raw_resume_text: str = "",
) -> list[dict[str, str]]:
    """Build stable, source-labelled evidence rows from the current résumé."""
    profile = resume_profile or {}
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(section: str, text: Any, source: str) -> None:
        cleaned = _clean_text(text)
        if not cleaned:
            return
        key = (section, _normalise_basic(cleaned))
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "evidence_id": _stable_id(
                    "ev",
                    f"{section}|{_normalise_basic(cleaned)}",
                ),
                "section": section,
                "text": cleaned,
                "source": source,
            }
        )

    for index, education in enumerate(profile.get("education", []) or []):
        if not isinstance(education, dict):
            continue
        add(
            "education",
            " — ".join(
                part
                for part in (
                    _clean_text(education.get("degree")),
                    _clean_text(education.get("school")),
                    _clean_text(education.get("graduation_date")),
                )
                if part
            ),
            f"resume_profile.education[{index}]",
        )
        for course_index, course in enumerate(education.get("courses", []) or []):
            add(
                "education",
                course,
                f"resume_profile.education[{index}].courses[{course_index}]",
            )

    for field_name in ("projects", "experience"):
        for index, item in enumerate(profile.get(field_name, []) or []):
            if not isinstance(item, dict):
                continue
            heading = " — ".join(
                part
                for part in (
                    _clean_text(item.get("title")),
                    _clean_text(item.get("company")),
                    _clean_text(item.get("date")),
                )
                if part
            )
            add(
                field_name,
                heading,
                f"resume_profile.{field_name}[{index}]",
            )
            for bullet_index, bullet in enumerate(item.get("bullets", []) or []):
                add(
                    field_name,
                    bullet,
                    f"resume_profile.{field_name}[{index}].bullets[{bullet_index}]",
                )

    skills = profile.get("skills", {}) or {}
    if isinstance(skills, dict):
        for category, values in skills.items():
            for index, value in enumerate(values or []):
                add(
                    "skills",
                    value,
                    f"resume_profile.skills.{category}[{index}]",
                )

    for index, line in enumerate(raw_resume_text.splitlines()):
        cleaned = _clean_text(line).strip("-•* \t")
        if len(cleaned) >= 8:
            add("raw_text", cleaned, f"raw_resume_text[{index}]")

    return rows


def _best_resume_evidence(
    requirement: dict[str, Any],
    matched_term: str,
    evidence_index: list[dict[str, str]],
    acronym_map: dict[str, str],
) -> tuple[dict[str, str] | None, float, float, int]:
    best: dict[str, str] | None = None
    best_score = 0.0
    best_focus_coverage = 0.0
    best_overlap_count = 0
    focus = requirement.get("atomic_focus") or requirement.get("text", "")

    for row in evidence_index:
        term_similarity = _token_similarity(
            matched_term,
            row.get("text", ""),
            acronym_map,
        ) if matched_term else 0.0
        requirement_similarity = _token_similarity(
            focus,
            row.get("text", ""),
            acronym_map,
        )
        focus_coverage, overlap_count = _coverage_metrics(
            focus,
            row.get("text", ""),
            acronym_map,
        )
        score = max(
            term_similarity,
            requirement_similarity * 0.85,
            focus_coverage * 0.90,
        )

        if score > best_score:
            best = row
            best_score = score
            best_focus_coverage = focus_coverage
            best_overlap_count = overlap_count

    return best, best_score, best_focus_coverage, best_overlap_count


def _fallback_weak_evidence(
    requirement: dict[str, Any],
    evidence_index: list[dict[str, str]],
    acronym_map: dict[str, str],
) -> dict[str, str] | None:
    best, score, focus_coverage, overlap_count = _best_resume_evidence(
        requirement,
        "",
        evidence_index,
        acronym_map,
    )
    if (
        best is None
        or score < 0.28
        or focus_coverage < 0.25
        or overlap_count < 2
    ):
        return None

    return {
        **best,
        "reason": (
            "The current résumé contains a lexically related but incomplete "
            "piece of evidence, so only weak credit was assigned."
        ),
        "evidence_similarity": f"{score:.3f}",
    }

def _normalise_match_label(row: dict[str, Any]) -> str:
    raw_match = _normalise_basic(row.get("match_type"))
    raw_evidence_type = _normalise_basic(row.get("evidence_type"))

    label = _MATCH_TYPE_MAP.get(raw_match, "")
    if not label:
        label = _MATCH_TYPE_MAP.get(raw_evidence_type, "")

    if label == "direct" and raw_evidence_type == "transferable":
        return "transferable"

    return label or "none"


def _evidence_reference(row: dict[str, Any]) -> dict[str, str] | None:
    found_in = _clean_text(row.get("found_in"))
    matched_term = _clean_text(row.get("matched_resume_term"))
    reason = _clean_text(row.get("match_reason"))

    if not matched_term:
        return None

    identity_text = f"{found_in}|{matched_term}"
    evidence_id = _stable_id(
        "ev",
        _normalise_basic(identity_text),
    )

    return {
        "evidence_id": evidence_id,
        "section": found_in,
        "text": matched_term,
        "reason": reason,
    }



def _best_keyword_row(
    requirement: dict[str, Any],
    keyword_rows: list[dict[str, Any]],
    acronym_map: dict[str, str],
) -> tuple[dict[str, Any] | None, float, float, int]:
    best_row: dict[str, Any] | None = None
    best_score = 0.0
    best_coverage = 0.0
    best_overlap = 0
    focus = requirement.get("atomic_focus") or requirement.get("text", "")

    for row in keyword_rows:
        if not isinstance(row, dict):
            continue

        keyword = row.get("keyword", "")
        coverage, overlap_count = _coverage_metrics(
            focus,
            keyword,
            acronym_map,
        )
        focus_tokens = set(_tokenise(focus, acronym_map))
        keyword_tokens = set(_tokenise(keyword, acronym_map))
        precision = (
            len(focus_tokens & keyword_tokens) / len(keyword_tokens)
            if keyword_tokens
            else 0.0
        )
        score = coverage * 0.78 + min(precision, 1.0) * 0.22

        if score > best_score:
            best_row = row
            best_score = score
            best_coverage = coverage
            best_overlap = overlap_count

    return best_row, best_score, best_coverage, best_overlap


def link_requirement_matches(
    requirements: list[dict[str, Any]],
    keyword_match: dict[str, Any],
    acronym_map: dict[str, str],
    *,
    resume_profile: dict[str, Any] | None = None,
    raw_resume_text: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Link canonical requirements conservatively to current-résumé evidence."""
    present_rows = [
        row
        for row in keyword_match.get("present", []) or []
        if isinstance(row, dict)
    ]
    missing_rows = [
        row
        for row in keyword_match.get("missing", []) or []
        if isinstance(row, dict)
    ]
    evidence_index = build_resume_evidence_index(
        resume_profile,
        raw_resume_text,
    )

    linked_rows: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for requirement in requirements:
        explicit_only = _is_explicit_only_subjective_requirement(requirement)
        present_row, present_score, present_coverage, present_overlap = _best_keyword_row(
            requirement,
            present_rows,
            acronym_map,
        )
        missing_row, missing_score, missing_coverage, missing_overlap = _best_keyword_row(
            requirement,
            missing_rows,
            acronym_map,
        )

        selected_row: dict[str, Any] | None = None
        selected_source = "unmatched"
        selected_score = 0.0
        selected_coverage = 0.0
        selected_overlap = 0

        present_qualified = bool(
            present_row
            and _reason_limits_requirement(
                _clean_text(present_row.get("match_reason")),
                requirement.get("atomic_focus") or requirement["text"],
                acronym_map,
            )
        )

        if present_row is not None and (
            present_score >= 0.48
            or present_coverage >= 0.50
        ):
            selected_row = present_row
            selected_source = "present"
            selected_score = present_score
            selected_coverage = present_coverage
            selected_overlap = present_overlap

        if missing_row is not None and (
            missing_score >= 0.48
            or missing_coverage >= 0.50
        ) and (
            selected_row is None
            or missing_score > selected_score + 0.05
            or (
                present_qualified
                and missing_coverage >= 0.70
                and missing_score >= selected_score - 0.05
            )
        ):
            selected_row = missing_row
            selected_source = "missing"
            selected_score = missing_score
            selected_coverage = missing_coverage
            selected_overlap = missing_overlap

        match_label = "none"
        evidence: list[dict[str, str]] = []
        focus = requirement.get("atomic_focus") or requirement["text"]

        if selected_source == "present" and selected_row is not None:
            match_label = _normalise_match_label(selected_row)
            matched_term = _clean_text(selected_row.get("matched_resume_term"))
            reason = _clean_text(selected_row.get("match_reason"))

            best_evidence, evidence_score, evidence_coverage, evidence_overlap = _best_resume_evidence(
                requirement,
                matched_term,
                evidence_index,
                acronym_map,
            )

            if best_evidence is not None and (
                evidence_score >= 0.18
                or evidence_coverage >= 0.20
                or not evidence_index
            ):
                reference = {
                    **best_evidence,
                    "reason": reason,
                    "evidence_similarity": f"{evidence_score:.3f}",
                }
            elif matched_term and not evidence_index:
                reference = _evidence_reference(selected_row)
                evidence_coverage, evidence_overlap = _coverage_metrics(
                    focus,
                    matched_term,
                    acronym_map,
                )
                evidence_score = _token_similarity(
                    focus,
                    matched_term,
                    acronym_map,
                )
                if reference is not None:
                    reference["evidence_similarity"] = f"{evidence_score:.3f}"
            else:
                reference = None

            reason_limited = _reason_limits_requirement(
                reason,
                focus,
                acronym_map,
            )

            if explicit_only and reference is not None:
                explicit_candidate = " ".join(
                    (
                        matched_term,
                        reference.get("text", ""),
                    )
                )
                if _explicit_subjective_evidence_supported(
                    requirement,
                    explicit_candidate,
                    acronym_map,
                ):
                    # Subjective motivation is binary for scoring: explicitly
                    # stated in the same domain, or unsupported. Related work
                    # alone does not receive transferable or weak credit.
                    match_label = "direct"
                else:
                    match_label = "none"
                    reference = None
                    warnings.append(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "code": "subjective_requirement_requires_explicit_evidence",
                            "message": (
                                "Related education, projects, or employment do not "
                                "prove this subjective motivation requirement. An "
                                "explicit resume statement is required."
                            ),
                        }
                    )

            if reference is None:
                if match_label != "none":
                    warnings.append(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "code": "positive_match_not_found_in_resume_profile",
                            "message": (
                                "The claimed match could not be tied to the current "
                                "résumé profile and was downgraded to none."
                            ),
                        }
                    )
                match_label = "none"
            else:
                atomic = bool(requirement.get("is_atomic"))

                if explicit_only:
                    # Explicit-only requirements were already resolved above.
                    pass
                elif reason_limited and match_label in {"direct", "transferable"}:
                    match_label = "weak" if (evidence_coverage >= 0.35 or not evidence_index) else "none"
                    warnings.append(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "code": "qualified_evidence_capped",
                            "message": (
                                "The match explanation limits this atomic claim, "
                                "so it received weak or no credit."
                            ),
                        }
                    )

                # A compound upstream row may be labelled partial because another
                # clause is unsupported. Once split, a fully covered atomic child
                # can receive direct credit when its own evidence is explicit.
                if (
                    not explicit_only
                    and atomic
                    and match_label == "transferable"
                    and not reason_limited
                    and selected_coverage >= 0.90
                    and (evidence_coverage >= 0.20 or evidence_score >= 0.45)
                ):
                    match_label = "direct"
                    warnings.append(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "code": "atomic_clause_promoted",
                            "message": (
                                "The compound match fully and explicitly supports "
                                "this atomic clause, so it received direct credit."
                            ),
                        }
                    )

                if not explicit_only and match_label == "direct":
                    minimum_keyword_coverage = 0.72 if atomic else 0.45
                    if selected_coverage < minimum_keyword_coverage:
                        match_label = "none"
                        warnings.append(
                            {
                                "requirement_id": requirement["requirement_id"],
                                "code": "partial_phrase_not_atomic_proof",
                                "message": (
                                    "The matched keyword covered only part of the "
                                    "requirement and could not prove the full claim."
                                ),
                            }
                        )
                    elif evidence_coverage < 0.08 and evidence_score < 0.08:
                        match_label = "weak"
                        warnings.append(
                            {
                                "requirement_id": requirement["requirement_id"],
                                "code": "low_evidence_overlap_capped",
                                "message": (
                                    "The résumé evidence had too little overlap for "
                                    "direct credit, so the label was capped at weak."
                                ),
                            }
                        )

                elif not explicit_only and match_label == "transferable":
                    minimum_keyword_coverage = 0.55 if atomic else 0.35
                    if selected_coverage < minimum_keyword_coverage:
                        match_label = "none"
                        warnings.append(
                            {
                                "requirement_id": requirement["requirement_id"],
                                "code": "insufficient_atomic_coverage",
                                "message": (
                                    "The transferable keyword did not cover enough "
                                    "of the atomic requirement."
                                ),
                            }
                        )
                    elif evidence_overlap < 1:
                        match_label = "weak"

                evidence.append(reference)

        if explicit_only and match_label == "none":
            explicit_evidence = _find_explicit_subjective_evidence(
                requirement,
                evidence_index,
                acronym_map,
            )
            if explicit_evidence is not None:
                match_label = "direct"
                evidence = [explicit_evidence]
                selected_source = "explicit_resume_evidence"
                warnings.append(
                    {
                        "requirement_id": requirement["requirement_id"],
                        "code": "explicit_subjective_evidence_found",
                        "message": (
                            "An explicit motivation or interest statement was found "
                            "in the current resume and received direct credit."
                        ),
                    }
                )
            else:
                evidence = []

        elif selected_source in {"missing", "unmatched"} or match_label == "none":
            fallback = _fallback_weak_evidence(
                requirement,
                evidence_index,
                acronym_map,
            )
            if fallback is not None:
                match_label = "weak"
                evidence = [fallback]
                warnings.append(
                    {
                        "requirement_id": requirement["requirement_id"],
                        "code": "deterministic_weak_fallback",
                        "message": (
                            "A stable, incomplete résumé overlap was found, so "
                            "weak credit was assigned consistently."
                        ),
                    }
                )

        evidence_strength = 0
        if evidence:
            if match_label == "direct":
                evidence_strength = 5 if evidence[0].get("reason") else 4
            elif match_label == "transferable":
                evidence_strength = 3
            elif match_label == "weak":
                evidence_strength = 2

        linked_rows.append(
            {
                **deepcopy(requirement),
                "explicit_only_requirement": explicit_only,
                "match_label": match_label,
                "match_value": MATCH_VALUES[match_label],
                "evidence_strength": evidence_strength,
                "evidence": evidence,
                "matched_keyword": (
                    _clean_text(selected_row.get("keyword"))
                    if selected_row is not None
                    else ""
                ),
                "match_similarity": round(selected_score, 3),
                "match_coverage": round(selected_coverage, 3),
                "match_overlap_count": selected_overlap,
                "match_source": selected_source,
            }
        )

    return linked_rows, warnings

def validate_linked_matches(
    linked_requirements: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply generic consistency checks without role-specific assumptions."""
    validated = deepcopy(linked_requirements)
    warnings: list[dict[str, Any]] = []

    seen_ids: set[str] = set()

    for row in validated:
        requirement_id = _clean_text(row.get("requirement_id"))

        if requirement_id in seen_ids:
            warnings.append(
                {
                    "requirement_id": requirement_id,
                    "code": "duplicate_requirement_id",
                    "message": "Duplicate requirement ID detected.",
                }
            )
        seen_ids.add(requirement_id)

        label = _clean_text(row.get("match_label")).lower()
        if label not in MATCH_VALUES:
            row["match_label"] = "none"
            row["match_value"] = 0.0
            warnings.append(
                {
                    "requirement_id": requirement_id,
                    "code": "invalid_match_label",
                    "message": "Invalid match label was downgraded to none.",
                }
            )
            label = "none"

        evidence = row.get("evidence", []) or []
        if label != "none" and not evidence:
            row["match_label"] = "none"
            row["match_value"] = 0.0
            row["evidence_strength"] = 0
            warnings.append(
                {
                    "requirement_id": requirement_id,
                    "code": "missing_evidence",
                    "message": "Positive match was downgraded because no evidence was linked.",
                }
            )

        if label == "none":
            row["evidence_strength"] = 0

    return validated, warnings



def _weighted_coverage(
    rows: list[dict[str, Any]],
    accepted_importance: set[str],
) -> tuple[float, float, float]:
    numerator = 0.0
    denominator = 0.0

    eligible_rows = [
        row
        for row in rows
        if _clean_text(row.get("importance")).lower() in accepted_importance
    ]
    group_counts: dict[str, int] = {}
    for row in eligible_rows:
        group_id = _clean_text(
            row.get("atomic_group_id") or row.get("requirement_id")
        )
        group_counts[group_id] = group_counts.get(group_id, 0) + 1

    for row in eligible_rows:
        importance = _clean_text(row.get("importance")).lower()
        group_id = _clean_text(
            row.get("atomic_group_id") or row.get("requirement_id")
        )
        group_fraction = 1.0 / max(1, group_counts.get(group_id, 1))
        weight = IMPORTANCE_WEIGHTS.get(importance, 0.0) * group_fraction
        numerator += weight * float(row.get("match_value", 0.0))
        denominator += weight

    score = 100.0 * numerator / denominator if denominator else 0.0
    return score, numerator, denominator

def _alignment_band(score: int) -> str:
    for boundary, label in BAND_BOUNDARIES:
        if score >= boundary:
            return label
    return "weak alignment"


def _boundary_margin(score: int, margin: int = 3) -> dict[str, Any]:
    boundaries = [50, 65, 80]
    nearest = min(boundaries, key=lambda boundary: abs(score - boundary))

    return {
        "margin_points": margin,
        "nearest_boundary": nearest,
        "is_borderline": abs(score - nearest) <= margin,
    }



def compute_deterministic_alignment(
    linked_requirements: list[dict[str, Any]],
    *,
    bullet_quality_score: int | float = 0,
    structure_score: int | float = 0,
) -> dict[str, Any]:
    """Compute role alignment without mixing in document-quality scores."""
    required_score, _, required_denominator = _weighted_coverage(
        linked_requirements,
        {"deal_breaker", "required", "core"},
    )
    preferred_score, _, preferred_denominator = _weighted_coverage(
        linked_requirements,
        {"preferred"},
    )

    evidence_values = [
        min(5, max(0, int(row.get("evidence_strength", 0))))
        for row in linked_requirements
        if row.get("match_label") != "none"
    ]
    evidence_score = (
        round(100 * sum(evidence_values) / (5 * len(evidence_values)))
        if evidence_values
        else 0
    )

    bullet_score = max(0.0, min(100.0, float(bullet_quality_score or 0)))
    structure = max(0.0, min(100.0, float(structure_score or 0)))

    if preferred_denominator:
        required_weight = 0.80
        preferred_weight = 0.10
    else:
        required_weight = 0.90
        preferred_weight = 0.0

    overall = round(
        required_score * required_weight
        + preferred_score * preferred_weight
        + evidence_score * 0.10
    )
    overall = int(max(0, min(100, overall)))

    group_ids = {
        row.get("atomic_group_id") or row.get("requirement_id")
        for row in linked_requirements
    }

    return {
        "deterministic_alignment_score": overall,
        "alignment_band": _alignment_band(overall),
        "required_core_coverage_score": round(required_score),
        "preferred_coverage_score": round(preferred_score),
        "evidence_strength_score": evidence_score,
        "bullet_quality_component": round(bullet_score),
        "structure_component": round(structure),
        "score_weights": {
            "required_core_coverage": required_weight,
            "preferred_coverage": preferred_weight,
            "evidence_strength": 0.10,
            "bullet_quality": 0.0,
            "structure": 0.0,
        },
        "quality_components_excluded_from_role_alignment": True,
        "requirement_count": len(linked_requirements),
        "requirement_group_count": len(group_ids),
        "credited_requirement_count": sum(
            1
            for row in linked_requirements
            if row.get("match_label") != "none"
        ),
        "direct_requirement_count": sum(
            1
            for row in linked_requirements
            if row.get("match_label") == "direct"
        ),
        "transferable_requirement_count": sum(
            1
            for row in linked_requirements
            if row.get("match_label") == "transferable"
        ),
        "weak_requirement_count": sum(
            1
            for row in linked_requirements
            if row.get("match_label") == "weak"
        ),
        "required_core_requirement_count": sum(
            1
            for row in linked_requirements
            if row.get("importance") in {"deal_breaker", "required", "core"}
        ),
        "preferred_requirement_count": sum(
            1
            for row in linked_requirements
            if row.get("importance") == "preferred"
        ),
        "boundary_status": _boundary_margin(overall),
        "score_interpretation": (
            "Deterministic résumé-to-JD role-alignment estimate based only on "
            "requirement coverage and credited evidence. Document quality is "
            "reported separately and is not part of this score."
        ),
    }


def build_stable_analysis(
    *,
    jd_profile: dict[str, Any],
    keyword_match: dict[str, Any],
    raw_jd_text: str = "",
    raw_resume_text: str = "",
    resume_profile: dict[str, Any] | None = None,
    bullet_quality_score: int | float = 0,
    structure_score: int | float = 0,
) -> dict[str, Any]:
    """Build the complete Phase 6A.1C stable-analysis payload."""
    canonical = canonicalise_requirements(
        jd_profile=jd_profile,
        raw_jd_text=raw_jd_text,
    )

    linked, link_warnings = link_requirement_matches(
        requirements=canonical["requirements"],
        keyword_match=keyword_match,
        acronym_map=canonical["acronym_map"],
        resume_profile=resume_profile,
        raw_resume_text=raw_resume_text,
    )

    validated, validation_warnings = validate_linked_matches(linked)

    taxonomy_version = get_default_taxonomy().version
    taxonomy_validated = apply_taxonomy_caps_to_requirements(
        validated
    )
    taxonomy_warnings: list[dict[str, Any]] = []
    for row in taxonomy_validated:
        for warning in row.pop("validation_warnings", []) or []:
            taxonomy_warnings.append(
                {
                    "requirement_id": row.get("requirement_id", ""),
                    **warning,
                }
            )

    score = compute_deterministic_alignment(
        taxonomy_validated,
        bullet_quality_score=bullet_quality_score,
        structure_score=structure_score,
    )

    input_material = "\n---INPUT-PART---\n".join(
        (
            _normalise_basic(raw_resume_text),
            _normalise_basic(raw_jd_text),
            taxonomy_version,
            SCORING_VERSION,
        )
    )

    return {
        "scoring_version": SCORING_VERSION,
        "capability_taxonomy_version": taxonomy_version,
        "input_fingerprint": hashlib.sha256(
            input_material.encode("utf-8")
        ).hexdigest(),
        "canonical_requirements": taxonomy_validated,
        "canonicalisation_debug": {
            "acronym_map": canonical["acronym_map"],
            "merged_requirements": canonical["merge_debug"],
            "atomic_requirement_count": sum(
                1
                for row in taxonomy_validated
                if row.get("is_atomic")
            ),
        },
        "validation_warnings": (
            link_warnings
            + validation_warnings
            + taxonomy_warnings
        ),
        **score,
    }

