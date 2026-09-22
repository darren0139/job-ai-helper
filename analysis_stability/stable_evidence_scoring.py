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

from analysis_stability.evidence_support import (
    classify_verified_evidence_support,
)
from tailoring.capability_taxonomy import evaluate_evidence, get_default_taxonomy
from tailoring.phase6d_stable_scoring_adapter import (
    apply_taxonomy_caps_to_requirements,
)
from tailoring.phase6d6_structured_matching import (
    apply_structured_requirement_matches,
)

SCORING_VERSION = "stable-evidence-v1.7-phase6d12"
CAPABILITY_EVIDENCE_RESELECTION_POLICY_VERSION = "capability-single-row-reselection-v1"
NON_REQUIREMENT_FILTER_VERSION = "canonical-non-requirement-filter-v2"
JD_SEMANTIC_ELIGIBILITY_VERSION = "jd-semantic-eligibility-v1.1"
CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION = (
    "jd-atomic-requirement-decomposition-v1"
)

MATCH_VALUES = {
    "direct": 1.0,
    "transferable": 0.55,
    "weak": 0.20,
    "none": 0.0,
}

# Weak deterministic evidence must show more than a single generic-token
# collision. Keep the direct keyword builder aligned with the existing weak
# fallback gate so a one-token overlap cannot bypass the conservative policy.
_DETERMINISTIC_WEAK_MIN_SCORE = 0.28
_DETERMINISTIC_WEAK_MIN_COVERAGE = 0.25
_DETERMINISTIC_WEAK_MIN_OVERLAP = 2

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


def _normalise_requirement_surface(value: Any) -> str:
    """Repair unambiguous presentation joins before deterministic tokenisation.

    This is deliberately narrower than a general spelling corrector.  It only
    separates sentence punctuation and well-known punctuation-adjacent technical
    tokens that otherwise make a raw-JD fact impossible to ground.  It does not
    add aliases, infer capabilities, or perform fuzzy matching.
    """
    text = _clean_text(value)
    if not text:
        return ""

    # A missing space after ordinary terminal punctuation is layout damage, not
    # a semantic variation (for example: "use cases.You will...").
    text = re.sub(r"(?<=[.!?])(?=[A-Z])", " ", text)

    # Repair the exact discourse-preamble join observed in the dConstruct PDF
    # extraction. This is intentionally narrow: it restores a missing layout
    # space in "At the same time" without becoming a general word splitter.
    text = re.sub(r"(?i)\bAtthe(?=\s+same\s+time\b)", "At the", text)

    # Keep C/C++, C++, C# and F# intact while separating an adjoining ordinary
    # word.  The surrounding boundaries prevent generic substring matching.
    text = re.sub(
        r"(?i)(C/C\+\+|C\+\+|C#|F#)(?=[a-z])",
        r"\1 ",
        text,
    )
    text = re.sub(
        r"(?<=[a-z])(?=(?:C/C\+\+|C\+\+|C#|F#)\b)",
        " ",
        text,
    )
    # A verb joined to an ordinary requirement object is another unambiguous
    # line-wrap/OCR seam.  Restrict this to grammatical action/object pairs so
    # it cannot become a broad dictionary-based word splitter.
    text = re.sub(
        r"(?i)\b(integrat(?:e|ing)|develop(?:ing)?|build(?:ing)?|"
        r"test(?:ing)?|deploy(?:ing)?)(functionality|features|services|"
        r"applications|software)\b",
        r"\1 \2",
        text,
    )
    # This catches a common OCR/layout join without treating arbitrary words
    # containing "and" as separate requirements.
    text = re.sub(r"(?<=[A-Z])and/or\b", " and/or", text)
    return _clean_text(text)


def _normalise_basic(value: Any) -> str:
    text = _normalise_requirement_surface(value).lower()
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


def _importance_sensitive_fuzzy_merge_is_unsafe(
    left_text: str,
    left_importance: str,
    right_text: str,
    right_importance: str,
    acronym_map: dict[str, str],
) -> bool:
    """Block fuzzy merges that would collapse materially different scope.

    Exact duplicates may still take the strongest importance. For fuzzy
    matches, however, a high-containment score can hide that one row carries
    several extra capabilities. If the rows have different importance and one
    token set is materially broader, keep both rows so stronger importance
    cannot be transferred onto broader wording.
    """
    if _importance_rank(left_importance) == _importance_rank(right_importance):
        return False

    left_tokens = set(_tokenise(left_text, acronym_map))
    right_tokens = set(_tokenise(right_text, acronym_map))
    if not left_tokens or not right_tokens:
        return False

    overlap = len(left_tokens & right_tokens)
    left_coverage = overlap / len(left_tokens)
    right_coverage = overlap / len(right_tokens)
    narrower_coverage = max(left_coverage, right_coverage)
    broader_coverage = min(left_coverage, right_coverage)

    return (
        narrower_coverage >= 0.90
        and broader_coverage <= 0.75
        and abs(len(left_tokens) - len(right_tokens)) >= 2
    )


def _classify_raw_importance(text: str, default: str = "core") -> str:
    normalised = _normalise_basic(text)

    if any(hint in normalised for hint in _PREFERRED_HINTS):
        return "preferred"

    if any(hint in normalised for hint in _REQUIRED_HINTS):
        return "required"

    return default



_RAW_SECTION_HEADINGS = {
    "responsibilities": frozenset(
        {
            "about the role",
            "job description",
            "role description",
            "role overview",
            "position overview",
            "overview",
            "key responsibilities",
            "responsibilities",
            "job responsibilities",
            "role responsibilities",
            "duties",
            "key duties",
            "duties and responsibilities",
            "responsibilities and duties",
            "what you will do",
            "what you ll do",
            "what youll do",
        }
    ),
    "requirements": frozenset(
        {
            "job requirements",
            "requirements",
            "requirements and skills",
            "role requirements",
            "candidate requirements",
            "minimum requirements",
            "required qualifications",
            "required skills",
            "minimum qualifications",
            "qualifications",
            "skills and experience",
            "what we are looking for",
            "what we re looking for",
            "what were looking for",
        }
    ),
    "core": frozenset(
        {
            "core requirements",
        }
    ),
    "preferred": frozenset(
        {
            "preferred",
            "preferred qualifications",
            "preferred requirements",
            "preferred skills",
            "bonus requirements and skills",
            "optional skills",
            "desired qualifications",
            "desired skills",
            "nice to have",
            "nice to haves",
            "bonus qualifications",
            "additional qualifications",
        }
    ),
    "stop": frozenset(
        {
            "about us",
            "about the company",
            "company overview",
            "benefits",
            "what we offer",
            "compensation",
            "salary",
            "equal opportunity employer",
            "how to apply",
            "application process",
        }
    ),
}


def _normalise_jd_section_heading(value: Any) -> str:
    """Return a punctuation-insensitive exact key for a possible JD heading."""
    text = _clean_text(value)
    text = re.sub(
        r"^\s*(?:[-*•]+|\d+[.)])\s*",
        "",
        text,
    )
    text = re.sub(r"[\s:;.\-–—]+$", "", text)
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _raw_section_for_heading(value: Any) -> str:
    """Return the controlled section type for an exact heading, or empty."""
    heading = _normalise_jd_section_heading(value)
    if not heading:
        return ""

    for section, headings in _RAW_SECTION_HEADINGS.items():
        if heading in headings:
            return section

    return ""


def _raw_jd_section_heading_rows(
    raw_jd_text: str,
) -> list[dict[str, str]]:
    """Collect recognised section markers for deterministic diagnostics."""
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for raw_line in raw_jd_text.splitlines():
        value = _clean_text(raw_line).strip("-•* \t")
        section = _raw_section_for_heading(value)
        if not section:
            continue

        key = (section, _normalise_jd_section_heading(value))
        if key in seen:
            continue
        seen.add(key)

        rows.append(
            {
                "text": value,
                "section": section,
                "source": "raw_jd",
            }
        )

    return rows


def classify_jd_statement_semantics(
    value: Any,
    *,
    source: str = "",
    importance: str = "",
) -> dict[str, Any]:
    """Classify whether one JD statement is evidence-bearing for the candidate.

    This is deliberately conservative: only narrow, high-confidence role-context
    and future-training statements are excluded. Ordinary qualifications and
    demonstrable responsibilities remain evidence-bearing.
    """
    surface = _normalise_requirement_surface(value).strip(" ,;:.-")
    normalised = _normalise_basic(surface)
    source_value = _clean_text(source).casefold()

    metadata = {
        "semantic_type": "candidate_requirement",
        "evidence_eligible": True,
        "score_eligible": True,
        "tailoring_eligible": True,
        "eligibility_rule": "eligible_candidate_requirement",
        "semantic_eligibility_version": JD_SEMANTIC_ELIGIBILITY_VERSION,
    }
    if not normalised:
        return metadata

    role_context_patterns = (
        re.compile(
            r"^(?:at\s+the\s+same\s+time[, ]+)?"
            r"(?:(?:you|the candidate)\s+will\s+(?:be\s+)?)?"
            r"work(?:ing)?\s+alongside\s+(?:industry\s+)?experts$",
            re.IGNORECASE,
        ),
    )
    if any(pattern.match(surface) for pattern in role_context_patterns):
        return {
            **metadata,
            "semantic_type": "role_context",
            "evidence_eligible": False,
            "score_eligible": False,
            "tailoring_eligible": False,
            "eligibility_rule": "role_context_working_environment",
        }

    training_patterns = (
        re.compile(
            r"^(?:at\s+the\s+same\s+time[, ]+)?"
            r"(?:(?:you|the candidate)\s+will\s+(?:be\s+)?)?"
            r"familiari[sz]ed\s+with\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:(?:you|the candidate)\s+will\s+)?"
            r"(?:learn|be\s+trained(?:\s+(?:in|on))?|receive\s+training|"
            r"gain\s+exposure\s+to|be\s+exposed\s+to)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:(?:you|the candidate)\s+will\s+have\s+)?"
            r"(?:the\s+)?opportunity\s+to\s+(?:learn|gain\s+exposure)\b",
            re.IGNORECASE,
        ),
    )
    if any(pattern.match(surface) for pattern in training_patterns):
        return {
            **metadata,
            "semantic_type": "training_outcome",
            "evidence_eligible": False,
            "score_eligible": False,
            "tailoring_eligible": False,
            "eligibility_rule": "training_outcome_future_learning",
        }

    role_source = (
        "responsibilities" in source_value
        or "unheaded_explicit_role_obligation" in source_value
    )
    explicit_role_surface = bool(
        re.search(
            r"\b(?:you|the candidate|successful applicant)\s+will\b|"
            r"\bwho\s+will\b|\bresponsible\s+for\b",
            surface,
            flags=re.IGNORECASE,
        )
    )
    if role_source or explicit_role_surface:
        metadata.update(
            {
                "semantic_type": "role_responsibility",
                "eligibility_rule": "eligible_role_responsibility",
            }
        )
    return metadata


def _semantic_metadata_for_exclusion(
    value: Any,
    reason: str,
    *,
    source: str = "",
    importance: str = "",
) -> dict[str, Any]:
    metadata = classify_jd_statement_semantics(
        value,
        source=source,
        importance=importance,
    )
    if not metadata["score_eligible"]:
        return metadata

    semantic_type = "company_context"
    if reason in {
        "candidate_screening_process",
        "employment_terms_notice",
        "application_status_notice",
        "role_summary_context",
    }:
        semantic_type = "role_context"

    return {
        **metadata,
        "semantic_type": semantic_type,
        "evidence_eligible": False,
        "score_eligible": False,
        "tailoring_eligible": False,
        "eligibility_rule": reason or "non_evidence_bearing_context",
    }


def requirement_is_score_eligible(requirement: dict[str, Any]) -> bool:
    """Return score eligibility, including deterministic legacy-row fallback."""
    if not isinstance(requirement, dict):
        return False
    if "score_eligible" in requirement:
        return bool(requirement.get("score_eligible"))
    source = " ".join(
        _clean_text(item) for item in requirement.get("sources", []) or []
    )
    metadata = classify_jd_statement_semantics(
        requirement.get("atomic_focus")
        or requirement.get("text")
        or requirement.get("parent_text"),
        source=source,
        importance=_clean_text(requirement.get("importance")),
    )
    return bool(metadata["score_eligible"])


def requirement_is_tailoring_eligible(requirement: dict[str, Any]) -> bool:
    """Return tailoring eligibility, including deterministic legacy-row fallback."""
    if not isinstance(requirement, dict):
        return False
    if "tailoring_eligible" in requirement:
        return bool(requirement.get("tailoring_eligible"))
    source = " ".join(
        _clean_text(item) for item in requirement.get("sources", []) or []
    )
    metadata = classify_jd_statement_semantics(
        requirement.get("atomic_focus")
        or requirement.get("text")
        or requirement.get("parent_text"),
        source=source,
        importance=_clean_text(requirement.get("importance")),
    )
    return bool(metadata["tailoring_eligible"])


def _classify_non_requirement_row(value: Any) -> str:
    """Return a deterministic exclusion reason for non-evidence-bearing JD text."""
    surface = _clean_text(value)
    text = _normalise_basic(value)
    if not text:
        return ""

    semantic = classify_jd_statement_semantics(surface)
    if not semantic["score_eligible"]:
        return _clean_text(semantic.get("eligibility_rule"))

    if re.search(
        r"\bwe(?:['’]d| would)\s+love\s+to\s+(?:hear|meet)\b",
        surface,
        flags=re.IGNORECASE,
    ):
        return "recruiting_call_to_action"

    if re.match(
        r"^\s*(?:excited|interested)\s+about\b",
        surface,
        flags=re.IGNORECASE,
    ):
        return "recruiting_call_to_action"

    if (
        re.match(
            r"^\s*we(?:['’]re| are)\s+seeking\b",
            surface,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\bto\s+join\b.*\b(?:team|company|organisation|organization)\b",
            surface,
            flags=re.IGNORECASE,
        )
    ):
        return "recruiting_role_intro"

    if re.match(
        r"^\s*we(?:['’]re| are)\s+looking\s+for\b",
        surface,
        flags=re.IGNORECASE,
    ):
        return "recruiting_role_intro"

    if re.match(
        r"^\s*this\s+is\s+(?:an?\s+)?[^.!?]{0,160}\brole\b",
        surface,
        flags=re.IGNORECASE,
    ):
        return "role_summary_context"

    if re.fullmatch(r"#li[- ]?[a-z0-9-]+", text):
        return "recruiter_tracking_tag"

    if (
        ("applicant" in text or "applicants" in text)
        and ("updated" in text or "notified" in text)
        and "status" in text
        and ("application" in text or "applications" in text)
        and ("closing" in text or "advertisement" in text)
    ):
        return "application_status_notice"

    if (
        "shortlisting process" in text
        and (
            "medical declaration" in text
            or "further assessment" in text
            or "undergo further assessment" in text
        )
    ):
        return "candidate_screening_process"

    if (
        ("new hire" in text or "new hires" in text)
        and "contract" in text
        and (
            "permanent tenure" in text
            or "first instance" in text
            or "appointed" in text
        )
    ):
        return "employment_terms_notice"

    return ""


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

        # A final "x and y" item is an ordinary list continuation only when
        # a preceding top-level comma already established list structure.
        final_parts = re.split(r"\s+and\s+", parts[-1], maxsplit=1, flags=re.I)
        if (
            len(final_parts) == 2
            and all(len(_tokenise(part)) >= 1 for part in final_parts)
        ):
            parts[-1:] = [part.strip(" ,;.-") for part in final_parts]

    return parts


_EXAMPLE_OR_ALTERNATIVE_INTRODUCER = re.compile(
    r"\b(?:including(?:\s+but\s+not\s+limited\s+to)?|"
    r"such\s+as|for\s+example|e\.?\s*g\.?|especially|"
    r"one\s+or\s+more\s+of)\b",
    re.IGNORECASE,
)


def _preserves_coherent_parent(value: str) -> bool:
    """Return whether a top-level example list remains one requirement.

    An example marker nested inside one member of an independently addressable
    compound requirement (for example, ``live handling (including bugs)``)
    must not suppress decomposition of the surrounding compound parent.
    """
    for match in _EXAMPLE_OR_ALTERNATIVE_INTRODUCER.finditer(value):
        depth = 0
        for character in value[: match.start()]:
            if character == "(":
                depth += 1
            elif character == ")" and depth:
                depth -= 1
        if depth:
            continue

        introducer = _normalise_basic(match.group(0))
        if introducer == "one or more of":
            return True

        # A preceding top-level comma establishes a larger independent list.
        # Its later example parent remains coherent, but the whole compound
        # requirement must still be decomposed at the independently scored
        # list boundary.
        prefix = value[: match.start()].strip(" ,;:.-")
        if len(_split_top_level_commas(prefix)) > 1:
            continue
        return True
    return False


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



_SAFE_SECOND_CLAUSE_PREFIXES = (
    "ability to ",
    "comfortable ",
    "communicate ",
    "coordinate ",
    "develop ",
    "deploy ",
    "exposure to ",
    "familiarity with ",
    "investigate ",
    "knowledge of ",
    "maintain ",
    "proficiency in ",
    "resolve ",
    "support ",
    "verify ",
    "write ",
)


def _split_safe_independent_and_pair(value: str) -> list[str]:
    parts = re.split(
        r"\s+and\s+",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(parts) != 2:
        return []

    first = parts[0].strip(" ,;.-")
    second = parts[1].strip(" ,;.-")
    second_normalised = _normalise_basic(second)

    if not any(
        second_normalised.startswith(prefix)
        for prefix in _SAFE_SECOND_CLAUSE_PREFIXES
    ):
        return []

    if len(_tokenise(first)) < 2 or len(_tokenise(second)) < 2:
        return []

    return [first, second]


def _split_shared_head_and_list(value: str) -> list[str]:
    # Keep OR alternatives together until group-level ANY scoring is added.
    if re.search(r"(?:,\s*or\s+|\s+or\s+)", value, flags=re.IGNORECASE):
        return []

    # Example and alternative introducers describe a single competency.  The
    # current scorer has no ANY/one-or-more arithmetic, so preserve the parent
    # rather than converting examples into separately mandatory requirements.
    if _preserves_coherent_parent(value):
        return []

    # A foundation is one coherent competency even when it names several
    # constituent disciplines.  It is not equivalent to a list of separately
    # addressable tools or skills, so preserve it as one canonical requirement.
    # This is deliberately structural rather than subject-specific.
    if re.match(
        r"^(?:(?:good|strong|solid|working|basic)\s+)?foundation\s+in\s+",
        value,
        flags=re.IGNORECASE,
    ):
        return []

    match = re.match(
        r"^(?P<head>"
        r"(?:experience|familiarity|knowledge|proficiency|skills?|"
        r"(?:good|strong|solid|working|basic)\s+foundation|"
        r"understand(?:ing)?\s+concepts|comfortable)"
        r"\s+(?:using|with|in|of)\s+"
        r")(?P<tail>.+)$",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    items = _split_top_level_commas(match.group("tail"))
    if len(items) < 2:
        return []

    head = match.group("head").strip()
    return [
        f"{head} {item}".strip()
        for item in items
        if len(_tokenise(item)) >= 1
    ]

def _split_non_preference_clause(
    value: str,
    importance: str,
    parent_text: str,
) -> list[dict[str, Any]]:
    """Split clear compound clauses into stable, atomic requirements."""
    group_id = _stable_id("grp", _normalise_basic(parent_text))

    if _preserves_coherent_parent(value):
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

    shared_head_parts = _split_shared_head_and_list(value)
    if shared_head_parts:
        return [
            _clause_record(
                text=part,
                importance=importance,
                parent_text=parent_text,
                focus_text=part,
                atomic_group_id=group_id,
                is_atomic=True,
            )
            for part in shared_head_parts
        ]

    paired_parts = _split_safe_independent_and_pair(value)
    if paired_parts:
        return [
            _clause_record(
                text=part,
                importance=importance,
                parent_text=parent_text,
                focus_text=part,
                atomic_group_id=group_id,
                is_atomic=True,
            )
            for part in paired_parts
        ]

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
        r"^(?P<head>.+?)\s+from\s+(?P<tail>.+)$",
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


def _split_single_requirement_clause(
    text: str,
    default_importance: str,
) -> list[dict[str, Any]]:
    """Split one requirement sentence into conservative atomic clauses."""
    value = _normalise_requirement_surface(text)
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


def _split_requirement_sentences(value: str) -> list[str]:
    """Split only explicit sentence boundaries; keep abbreviations untouched."""
    text = _normalise_requirement_surface(value)
    if not text:
        return []

    parts = [
        part.strip(" ,;:.-")
        # ``e.g.`` and ``i.e.`` are inline introducers, not sentence endings.
        # Keeping them intact also lets the coherent-example guard preserve the
        # full competency instead of treating the examples as a second row.
        for part in re.split(
            r"(?<![Ee]\.[Gg]\.)(?<![Ii]\.[Ee]\.)(?<=[.!?])\s+(?=[A-Z])",
            text,
        )
        if part.strip(" ,;:.-")
    ]
    return parts or [text]


def _split_requirement_clauses(
    text: str,
    default_importance: str,
) -> list[dict[str, Any]]:
    """Split raw/profile wording by explicit sentence and safe clause seams."""
    records: list[dict[str, Any]] = []
    for sentence in _split_requirement_sentences(text):
        records.extend(
            _split_single_requirement_clause(
                sentence,
                default_importance,
            )
        )
    return records


def _strip_inline_jd_heading(value: str) -> str:
    """Remove a presentation-only inline Job Description marker if present."""
    return re.sub(
        r"^(?:job|role|position)\s+description\s*:\s*",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()


def _introductory_list_kind(value: str) -> str:
    """Return a controlled kind for a multiline example/alternative list."""
    text = _normalise_requirement_surface(value)
    if not text or not re.search(r":\s*$", text):
        return ""

    if re.search(r"\bone\s+or\s+more\s+of\s*:\s*$", text, re.I):
        return "one_or_more_of"

    if re.search(
        r"\b(?:including(?:\s+but\s+not\s+limited\s+to)?|"
        r"such\s+as|for\s+example|e\.?\s*g\.?|especially)\s*:\s*$",
        text,
        re.I,
    ):
        return "example_list"

    return ""


def _looks_like_introductory_list_item(value: str) -> bool:
    """Conservatively recognise a short item under an explicit list introducer."""
    text = _normalise_requirement_surface(value).strip(" ,;:.-")
    tokens = _tokenise(text)
    if not tokens or len(tokens) > 9:
        return False
    if re.search(r"[.!?;:]$", text):
        return False

    if re.match(
        r"^(?:we|you|(?:the\s+)?candidate|successful applicant|"
        r"experience|strong|solid|good|working|proficiency|knowledge|"
        r"familiarity|ability|comfortable|build|develop|design|implement|"
        r"work|collaborate|maintain|write|support|diagnose|help|assess|"
        r"protect|coordinate|investigate|deploy|containerize|containerise|"
        r"diploma|degree|bachelor|excellent|interest|exposure)\b",
        text,
        re.I,
    ):
        return False

    return True


def _open_introductory_list_header(
    spans: list[dict[str, Any]],
    *,
    section: str,
    block_index: int,
) -> dict[str, Any] | None:
    """Find the active introducer immediately preceding short list items."""
    for span in reversed(spans):
        if span.get("section") != section or span.get("block_index") != block_index:
            break

        kind = _introductory_list_kind(_clean_text(span.get("text", "")))
        if kind:
            return span

        if not _looks_like_introductory_list_item(
            _clean_text(span.get("text", ""))
        ):
            break

    return None


def _coalesce_one_or_more_alternative_lists(
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep explicit multiline example/alternative lists as one requirement."""
    coalesced: list[dict[str, Any]] = []
    index = 0
    while index < len(spans):
        header = spans[index]
        header_text = _clean_text(header.get("text", ""))
        list_kind = _introductory_list_kind(header_text)
        if not list_kind:
            coalesced.append(header)
            index += 1
            continue

        item_index = index + 1
        item_spans: list[dict[str, Any]] = []
        while item_index < len(spans):
            item = spans[item_index]
            if (
                item.get("section") != header.get("section")
                or item.get("block_index") != header.get("block_index")
                or not _looks_like_introductory_list_item(
                    _clean_text(item.get("text", ""))
                )
            ):
                break
            item_spans.append(item)
            item_index += 1

        if not item_spans:
            coalesced.append(header)
            index += 1
            continue

        list_items = [_clean_text(item["text"]) for item in item_spans]
        text = f"{header_text} " + " ; ".join(list_items)
        raw_text = "\n".join(
            [_clean_text(header.get("raw_text", header_text))]
            + [
                _clean_text(item.get("raw_text", item["text"]))
                for item in item_spans
            ]
        )
        coalesced.append(
            {
                **header,
                "span_id": _stable_id(
                    "jdspan",
                    f"{header['line_index']}|{_normalise_basic(text)}",
                ),
                "text": text,
                "raw_text": raw_text,
                "is_bullet": False,
                "alternative_list": {
                    "kind": list_kind,
                    "items": list_items,
                    "item_span_ids": [item["span_id"] for item in item_spans],
                },
            }
        )
        index = item_index

    return coalesced


def _raw_jd_content_spans(raw_jd_text: str) -> list[dict[str, Any]]:
    """Return deterministic, non-heading raw-JD spans with section context."""
    spans: list[dict[str, Any]] = []
    active_section = ""
    pending: dict[str, Any] | None = None
    block_index = 0

    def flush_pending() -> None:
        nonlocal pending
        if not pending:
            return
        spans.append(
            {
                "span_id": _stable_id(
                    "jdspan",
                    f"{pending['line_index']}|{_normalise_basic(pending['text'])}",
                ),
                "text": pending["text"],
                "raw_text": pending["raw_text"],
                "line_index": pending["line_index"],
                "section": pending["section"],
                "is_bullet": pending["is_bullet"],
                "block_index": pending["block_index"],
            }
        )
        pending = None

    def is_strong_grammatical_continuation(
        previous: str,
        current: str,
    ) -> bool:
        if re.match(r"^(?:and|or|with|for|to|in|of|using)\b", current, re.I):
            return True
        return bool(re.search(r"\b(?:with|using|for|to|in|of)$", previous, re.I))

    def is_unambiguous_continuation(previous: str, current: str) -> bool:
        if re.search(r"[.!?;:]$", previous):
            return False
        if is_strong_grammatical_continuation(previous, current):
            return True
        if current[:1].islower():
            return True
        return False

    for line_index, raw_line in enumerate(raw_jd_text.splitlines(), start=1):
        original = _clean_text(raw_line).strip("-•* \t")
        value = _normalise_requirement_surface(original)
        if not value:
            flush_pending()
            block_index += 1
            continue

        section = _raw_section_for_heading(value)
        if section:
            flush_pending()
            block_index += 1
            active_section = "" if section == "stop" else section
            continue

        value = _strip_inline_jd_heading(value)
        if not value:
            flush_pending()
            block_index += 1
            continue

        is_bullet = bool(re.match(r"^\s*(?:[-*•]+|\d+[.)])\s*", raw_line))
        intro_header = _open_introductory_list_header(
            spans,
            section=active_section,
            block_index=block_index,
        )
        preserve_list_boundary = bool(
            intro_header
            and _looks_like_introductory_list_item(value)
            and not is_strong_grammatical_continuation(
                pending["text"] if pending else "",
                value,
            )
        )
        if (
            pending
            and not is_bullet
            and not preserve_list_boundary
            and pending["section"] == active_section
            and is_unambiguous_continuation(pending["text"], value)
        ):
            pending["text"] = _normalise_requirement_surface(
                f"{pending['text']} {value}"
            )
            pending["raw_text"] = _clean_text(
                f"{pending['raw_text']} {original}"
            )
            continue

        flush_pending()
        pending = {
            "text": value,
            "raw_text": original,
            "line_index": line_index,
            "section": active_section,
            "is_bullet": is_bullet,
            "block_index": block_index,
        }

    flush_pending()

    return _coalesce_one_or_more_alternative_lists(spans)


def _raw_jd_requirement_rows(
    raw_jd_text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract direct rows from explicit sections and retain raw grounding spans."""
    rows: list[dict[str, Any]] = []
    spans = _raw_jd_content_spans(raw_jd_text)
    unheaded_exclusions: list[dict[str, Any]] = []

    for span in spans:
        active_section = _clean_text(span.get("section", ""))
        value = _clean_text(span.get("text", ""))

        # Inside an explicitly recognised requirement section, short technical
        # entries such as "C++" are real requirements.  The section marker is
        # already consumed above, so require a meaningful token rather than a
        # presentation-length threshold.
        if active_section and _tokenise(value):
            default_importance = {
                "responsibilities": "core",
                "requirements": "required",
                "core": "core",
                "preferred": "preferred",
            }[active_section]
            # A raw span can contain several independently punctuated sentences.
            # Importance cues such as "plus" or "must" are local to the sentence
            # that contains them; do not let one sentence reclassify its neighbours.
            for sentence_index, sentence in enumerate(
                _split_requirement_sentences(value),
                start=1,
            ):
                sentence_importance = _classify_raw_importance(
                    sentence,
                    default_importance,
                )
                has_explicit_preference_transition = bool(
                    re.search(
                        r"\b(preferably|ideally|nice[- ]to[- ]have|"
                        r"would be preferred)\b",
                        sentence,
                        flags=re.IGNORECASE,
                    )
                )
                split_default_importance = (
                    default_importance
                    if has_explicit_preference_transition
                    else sentence_importance
                )

                for clause in _split_single_requirement_clause(
                    sentence,
                    split_default_importance,
                ):
                    grounding = {
                        "kind": "explicit_raw_section",
                        "span_id": span["span_id"],
                        "line_index": span["line_index"],
                        "section": active_section,
                        "sentence_index": sentence_index,
                        "sentence_text": sentence,
                    }
                    alternative_list = span.get("alternative_list") or {}
                    if alternative_list:
                        grounding.update(
                            {
                                "list_structure": alternative_list.get("kind", ""),
                                "list_item_span_ids": alternative_list.get(
                                    "item_span_ids",
                                    [],
                                ),
                                "list_item_count": len(
                                    alternative_list.get("items", [])
                                ),
                            }
                        )
                    rows.append(
                        {
                            **clause,
                            "importance": clause["importance"],
                            "source": f"raw_jd.{active_section}",
                            # Keep the source spelling only as provenance.  The
                            # canonical display/ID continues to use the repaired
                            # deterministic surface in ``clause['parent_text']``.
                            "raw_parent_text": _clean_text(
                                span.get("raw_text", clause["parent_text"])
                            ).strip(" ,;:-"),
                            "source_parent_instance": (
                                f"raw|{span['span_id']}|"
                                f"{_normalise_basic(clause['parent_text'])}"
                            ),
                            "grounding": grounding,
                        }
                    )
            continue

        # Unheaded prose is admissible only when a sentence independently
        # establishes an applicant obligation or explicit qualification.  This
        # remains true even if formal sections occur later in the same JD.
        role_rows, diagnostics = _unheaded_role_rows(span)
        rows.extend(role_rows)
        unheaded_exclusions.extend(diagnostics)

    return rows, spans, unheaded_exclusions


_UNHEADED_CONTEXTUAL_PATTERNS = (
    re.compile(r"\bworking alongside (?:industry )?experts\b", re.I),
    re.compile(r"\bjoin(?:ing)? (?:a|our|the) team\b", re.I),
    re.compile(r"\babout (?:the )?(?:company|organisation|organization|role)\b", re.I),
    re.compile(r"\bwe(?:'re| are) (?:a|an|the)\b", re.I),
)

_RECRUITING_CALL_TO_ACTION_PATTERNS = (
    re.compile(r"\bapply\s+(?:now|today|here)\b", re.I),
    re.compile(r"\bwe(?:'d| would)\s+love\s+to\s+(?:hear|meet)\b", re.I),
    re.compile(r"^\s*(?:excited|interested)\s+about\b", re.I),
    re.compile(r"^\s*join(?:ing)?\b.*\bteam\b", re.I),
    re.compile(r"\bwe(?:'re| are)\s+seeking\b", re.I),
)

_UNHEADED_OBLIGATION_PATTERNS = (
    re.compile(r"\b(?:you|candidate|successful applicant)\s+(?:will|must|should)\b", re.I),
    re.compile(r"\bwho\s+will\b", re.I),
    re.compile(r"\bresponsible\s+for\b", re.I),
    re.compile(r"\b(?:must|required|minimum)\b", re.I),
    re.compile(
        r"^(?:(?:strong|good|solid|working)\s+)?"
        r"(?:experience|familiarity|knowledge|proficiency|ability|skills?)\b",
        re.I,
    ),
)


_EXPLICIT_APPLICANT_OBLIGATION_PATTERN = re.compile(
    r"\b(?:you|(?:the\s+)?candidate|successful applicant)\s+"
    r"(?:will|must|should)\b|"
    r"\bwho\s+will\b|\bresponsible\s+for\b|"
    r"\b(?:candidate|successful applicant)\s+must\b",
    re.I,
)


def _unheaded_span_status(span: dict[str, Any]) -> tuple[bool, str]:
    """Classify unheaded prose without treating company context as a requirement."""
    text = _clean_text(span.get("text", ""))
    if (
        any(pattern.search(text) for pattern in _RECRUITING_CALL_TO_ACTION_PATTERNS)
        and not _EXPLICIT_APPLICANT_OBLIGATION_PATTERN.search(text)
    ):
        return False, "recruiting_call_to_action"
    if any(pattern.search(text) for pattern in _UNHEADED_CONTEXTUAL_PATTERNS):
        return False, "contextual_company_or_team_prose"
    if any(pattern.search(text) for pattern in _UNHEADED_OBLIGATION_PATTERNS):
        return True, "explicit_role_or_qualification_marker"
    return False, "ambiguous_unheaded_prose"


def _unheaded_obligation_content(sentence: str) -> str:
    """Remove only an explicit applicant-obligation wrapper from one sentence."""
    value = _normalise_requirement_surface(sentence).strip(" ,;:.-")
    if not value:
        return ""

    patterns = (
        # Employer introductions often establish the applicant obligation via
        # "who will".  The role/company preamble is context, not the
        # requirement itself.
        r"^.*?\bwho\s+will\s+(?:be\s+)?(?P<content>.+)$",
        # A short discourse preamble (for example, "At the same time") does
        # not weaken an otherwise explicit applicant obligation.
        r"^.*?\b(?:you|(?:the\s+)?candidate|successful applicant)\s+will\s+(?:be\s+)?"
        r"(?P<content>.+)$",
        r"^(?:you|(?:the\s+)?candidate|successful applicant)\s+(?:must|should)\s+"
        r"(?P<content>.+)$",
        r"^(?:you|(?:the\s+)?candidate|successful applicant)\s+(?:are|is)\s+"
        r"responsible\s+for\s+(?P<content>.+)$",
        r"^responsible\s+for\s+(?P<content>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group("content")).strip(" ,;:.-")

    if re.match(
        r"^(?:(?:strong|good|solid|working)\s+)?"
        r"(?:experience|familiarity|knowledge|proficiency|ability|skills?)\b",
        value,
        flags=re.IGNORECASE,
    ):
        return value
    return ""


def _is_explicit_unheaded_qualification(sentence: str) -> bool:
    return bool(
        re.match(
            r"^(?:(?:strong|good|solid|working)\s+)?"
            r"(?:experience|familiarity|knowledge|proficiency|ability|skills?)\b",
            _normalise_requirement_surface(sentence),
            flags=re.IGNORECASE,
        )
    )


def _unheaded_role_importance(sentence: str) -> str:
    """Keep role-obligation prose core unless it explicitly elevates priority."""
    if _is_explicit_unheaded_qualification(sentence):
        return _classify_raw_importance(sentence, "core")
    if re.search(
        r"\b(?:must|required|minimum|essential|mandatory)\b",
        sentence,
        flags=re.IGNORECASE,
    ):
        return "required"
    return "core"


def _unheaded_role_rows(
    span: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Admit explicit role obligations sentence-by-sentence from raw JD text."""
    rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    parent_text = _clean_text(
        span.get("raw_text", span.get("text", ""))
    ).strip(" ,;:-")
    sentences = _split_requirement_sentences(_clean_text(span.get("text", "")))
    # All admitted clauses from one raw span share the source parent's bounded
    # scoring allocation. Excluded contextual sentences never enter this group.
    group_id = _stable_id("grp", _normalise_basic(parent_text))
    parent_instance = (
        f"raw|{span.get('span_id', '')}|"
        f"{_normalise_basic(parent_text)}"
    )

    for sentence_index, sentence in enumerate(sentences, start=1):
        sentence_span = {**span, "text": sentence}
        eligible, reason = _unheaded_span_status(sentence_span)
        if not eligible:
            semantic = _semantic_metadata_for_exclusion(sentence, reason)
            diagnostics.append(
                {
                    "text": sentence,
                    "span_id": span.get("span_id", ""),
                    "line_index": span.get("line_index", 0),
                    "sentence_index": sentence_index,
                    "reason": reason,
                    **semantic,
                }
            )
            continue

        content = _unheaded_obligation_content(sentence)
        minimum_tokens = 1 if _is_explicit_unheaded_qualification(sentence) else 2
        if len(_tokenise(content)) < minimum_tokens:
            diagnostics.append(
                {
                    "text": sentence,
                    "span_id": span.get("span_id", ""),
                    "line_index": span.get("line_index", 0),
                    "sentence_index": sentence_index,
                    "reason": "explicit_role_marker_without_admissible_content",
                }
            )
            continue

        exclusion_reason = _classify_non_requirement_row(content)
        if exclusion_reason:
            semantic = _semantic_metadata_for_exclusion(
                content,
                exclusion_reason,
                source="raw_jd.unheaded_explicit_role_obligation",
                importance=_unheaded_role_importance(sentence),
            )
            diagnostics.append(
                {
                    "text": sentence,
                    "span_id": span.get("span_id", ""),
                    "line_index": span.get("line_index", 0),
                    "sentence_index": sentence_index,
                    "reason": f"non_requirement_{exclusion_reason}",
                    **semantic,
                }
            )
            continue

        for clause in _split_single_requirement_clause(
            content,
            _unheaded_role_importance(sentence),
        ):
            clause["parent_text"] = parent_text
            clause["atomic_group_id"] = group_id
            rows.append(
                {
                    **clause,
                    "source": "raw_jd.unheaded_explicit_role_obligation",
                    "raw_parent_text": _clean_text(
                        span.get("raw_text", parent_text)
                    ).strip(" ,;:-"),
                    "source_parent_instance": parent_instance,
                    "grounding": {
                        "kind": "unheaded_explicit_role_obligation",
                        "admission_method": "explicit_role_obligation_sentence",
                        "span_id": span.get("span_id", ""),
                        "line_index": span.get("line_index", 0),
                        "sentence_index": sentence_index,
                        "sentence_text": sentence,
                        "section": "",
                    },
                }
            )

    return rows, diagnostics


def _ordered_token_coverage(required: list[str], available: list[str]) -> float:
    """Return ordered coverage for one raw span without fuzzy synonym matching."""
    if not required:
        return 0.0
    cursor = 0
    matched = 0
    for token in required:
        while cursor < len(available) and available[cursor] != token:
            cursor += 1
        if cursor == len(available):
            break
        matched += 1
        cursor += 1
    return matched / len(required)


def _ground_profile_requirement_to_raw_span(
    value: str,
    spans: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Ground one structured row to exactly one admissible raw-JD span."""
    profile_text = _normalise_requirement_surface(value)
    profile_normalised = _normalise_basic(profile_text)
    profile_tokens = _tokenise(profile_text)
    diagnostics: list[dict[str, Any]] = []
    if len(profile_tokens) < 2:
        return None, diagnostics

    candidates: list[tuple[int, float, int, dict[str, Any], str]] = []
    for span in spans:
        span_text = _clean_text(span.get("text", ""))
        if not span_text:
            continue
        if not span.get("section"):
            eligible, reason = _unheaded_span_status(span)
            if not eligible:
                diagnostics.append(
                    {
                        "text": profile_text,
                        "span_id": span.get("span_id", ""),
                        "line_index": span.get("line_index", 0),
                        "reason": reason,
                    }
                )
                continue

        span_normalised = _normalise_basic(span_text)
        span_tokens = _tokenise(span_text)
        exact = bool(
            profile_normalised
            and profile_normalised in span_normalised
        )
        coverage = _ordered_token_coverage(profile_tokens, span_tokens)
        if not exact and coverage < 1.0:
            continue

        candidates.append(
            (
                1 if exact else 0,
                coverage,
                -int(span.get("line_index", 0)),
                span,
                "normalised_substring" if exact else "ordered_token_coverage",
            )
        )

    if not candidates:
        return None, diagnostics

    _, coverage, _, span, method = max(candidates, key=lambda item: item[:3])
    return {
        "kind": "profile_grounded_to_raw_jd",
        "span_id": span.get("span_id", ""),
        "line_index": span.get("line_index", 0),
        "section": span.get("section", ""),
        "method": method,
        "token_coverage": round(coverage, 6),
    }, diagnostics


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


def deterministic_evidence_coverage_metrics(
    requirement_text: str,
    candidate_text: str,
    acronym_map: dict[str, str] | None = None,
) -> tuple[float, int]:
    """Expose deterministic requirement coverage for evidence selectors."""
    return _coverage_metrics(
        requirement_text,
        candidate_text,
        acronym_map,
    )


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
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_rows, raw_spans, unheaded_raw_exclusions = _raw_jd_requirement_rows(
        raw_jd_text
    )
    rows.extend(raw_rows)
    rejected_unheaded: list[dict[str, Any]] = []
    grounded_profile_count = 0
    ungrounded_profile_rows: list[dict[str, Any]] = []

    field_specs = (
        ("deal_breakers", "deal_breaker"),
        ("required_skills", "required"),
        ("responsibilities", "core"),
        ("soft_skills", "core"),
        ("preferred_skills", "preferred"),
        ("tools_technologies", "core"),
    )

    for field_name, default_importance in field_specs:
        for profile_index, raw_value in enumerate(
            jd_profile.get(field_name, []) or []
        ):
            value = _clean_text(raw_value)
            if not value:
                continue
            if _raw_section_for_heading(value):
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
                grounding, rejected = _ground_profile_requirement_to_raw_span(
                    clause["text"],
                    raw_spans,
                )
                rejected_unheaded.extend(rejected)
                if grounding:
                    # An explicit section is already canonicalised directly
                    # from its raw wording.  Do not let an LLM profile add a
                    # differently phrased second allocation for that same
                    # authoritative span.
                    if grounding.get("section"):
                        continue
                    grounded_profile_count += 1
                    rows.append(
                        {
                            **clause,
                            "source": f"jd_profile.{field_name}",
                            "profile_field": field_name,
                            "source_parent_instance": (
                                f"profile|{field_name}|{profile_index}|"
                                f"{_normalise_basic(clause['parent_text'])}"
                            ),
                            "grounding": grounding,
                        }
                    )
                elif not raw_spans:
                    # Existing stored/profile-only inputs have no raw text to
                    # validate.  Keep the legacy compatibility path explicit
                    # in provenance; all current JD intake paths provide raw
                    # text and therefore use the stricter grounded path.
                    rows.append(
                        {
                            **clause,
                            "source": f"jd_profile.{field_name}",
                            "profile_field": field_name,
                            "source_parent_instance": (
                                f"profile|{field_name}|{profile_index}|"
                                f"{_normalise_basic(clause['parent_text'])}"
                            ),
                            "grounding": {
                                "kind": "legacy_profile_only_raw_unavailable",
                            },
                        }
                    )
                else:
                    ungrounded_profile_rows.append(
                        {
                            "text": clause["text"],
                            "source": f"jd_profile.{field_name}",
                            "reason": "not_grounded_to_admissible_raw_jd_span",
                        }
                    )

    return rows, {
        "raw_span_count": len(raw_spans),
        "grounded_profile_requirement_count": grounded_profile_count,
        "ungrounded_profile_requirements": ungrounded_profile_rows,
        "rejected_unheaded_spans": rejected_unheaded,
        "unheaded_raw_exclusions": unheaded_raw_exclusions,
    }


def canonicalise_requirements(
    jd_profile: dict[str, Any],
    raw_jd_text: str = "",
) -> dict[str, Any]:
    """Build stable atomic requirement rows from the raw JD/profile."""
    source_rows, decomposition_debug = _requirement_sources(
        jd_profile,
        raw_jd_text,
    )
    filtered_section_headings = _raw_jd_section_heading_rows(raw_jd_text)
    filtered_non_requirement_rows: list[dict[str, str]] = []

    clean_source_rows: list[dict[str, Any]] = []
    seen_filtered = {
        (
            row.get("section", ""),
            _normalise_jd_section_heading(row.get("text", "")),
            row.get("source", ""),
        )
        for row in filtered_section_headings
    }

    for source_row in source_rows:
        section = _raw_section_for_heading(source_row.get("text", ""))
        if section:
            diagnostic = {
                "text": _clean_text(source_row.get("text", "")),
                "section": section,
                "source": _clean_text(source_row.get("source", "")),
            }
            key = (
                diagnostic["section"],
                _normalise_jd_section_heading(diagnostic["text"]),
                diagnostic["source"],
            )
            if key not in seen_filtered:
                seen_filtered.add(key)
                filtered_section_headings.append(diagnostic)
            continue

        exclusion_reason = _classify_non_requirement_row(
            source_row.get("text", "")
        )
        if exclusion_reason:
            semantic = _semantic_metadata_for_exclusion(
                source_row.get("text", ""),
                exclusion_reason,
                source=_clean_text(source_row.get("source", "")),
                importance=_clean_text(source_row.get("importance", "")),
            )
            filtered_non_requirement_rows.append(
                {
                    "text": _clean_text(source_row.get("text", "")),
                    "reason": exclusion_reason,
                    "source": _clean_text(source_row.get("source", "")),
                    **semantic,
                }
            )
            continue

        clean_source_rows.append(source_row)

    source_rows = clean_source_rows
    text_values = [row["text"] for row in source_rows]
    text_values.append(raw_jd_text)
    acronym_map = learn_acronym_map(text_values)

    # Source parent provenance is intentionally descriptive.  The scorer still
    # derives group fractions dynamically from the canonical rows below.
    occurrence_focuses: dict[str, set[str]] = {}
    for source_row in source_rows:
        occurrence_base = _clean_text(
            source_row.get("source_parent_instance", "")
        ) or "|".join(
            (
                _clean_text(source_row.get("source", "")),
                _clean_text(source_row.get("profile_field", "")),
                _normalise_basic(source_row.get("parent_text", source_row["text"])),
            )
        )
        source_row["parent_occurrence_id"] = _stable_id(
            "srcgrp",
            occurrence_base,
        )
        occurrence_focuses.setdefault(
            source_row["parent_occurrence_id"],
            set(),
        ).add(
            _canonical_key(
                source_row.get("atomic_focus", source_row["text"]),
                acronym_map,
            )
        )

    for source_row in source_rows:
        focus_count = len(
            occurrence_focuses.get(source_row["parent_occurrence_id"], set())
        )
        source_row["source_group_fraction"] = round(
            1.0 / max(1, focus_count),
            6,
        )

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
            importance_sensitive_scope_mismatch = (
                not exact_key
                and _importance_sensitive_fuzzy_merge_is_unsafe(
                    text,
                    source_row["importance"],
                    existing["text"],
                    existing["importance"],
                    acronym_map,
                )
            )
            threshold_met = (
                exact_key
                or (
                    not importance_sensitive_scope_mismatch
                    and similarity >= (0.94 if either_atomic else 0.86)
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
                    "scoring_parent_occurrence_id": source_row[
                        "parent_occurrence_id"
                    ],
                    "source_provenance": [
                        {
                            "parent_occurrence_id": source_row[
                                "parent_occurrence_id"
                            ],
                            "parent_text": source_row.get("parent_text", text),
                            "raw_parent_text": source_row.get(
                                "raw_parent_text",
                                source_row.get("parent_text", text),
                            ),
                            "source": source_row["source"],
                            "profile_field": source_row.get("profile_field", ""),
                            "source_group_fraction": source_row[
                                "source_group_fraction"
                            ],
                            "grounding": source_row.get("grounding", {}),
                            "contributes_scoring_allocation": True,
                        }
                    ],
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
        existing.setdefault("source_provenance", []).append(
            {
                "parent_occurrence_id": source_row["parent_occurrence_id"],
                "parent_text": source_row.get("parent_text", text),
                "raw_parent_text": source_row.get(
                    "raw_parent_text",
                    source_row.get("parent_text", text),
                ),
                "source": source_row["source"],
                "profile_field": source_row.get("profile_field", ""),
                "source_group_fraction": source_row["source_group_fraction"],
                "grounding": source_row.get("grounding", {}),
                "contributes_scoring_allocation": False,
            }
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
        semantic = classify_jd_statement_semantics(
            row.get("atomic_focus") or row.get("text"),
            source=" ".join(row.get("sources", []) or []),
            importance=_clean_text(row.get("importance")),
        )
        # Non-evidence-bearing statements were filtered before canonical merging.
        # Keep eligibility explicit on survivors so importance never doubles as
        # a semantic-type flag downstream.
        row.update(semantic)

    return {
        "requirements": canonical_rows,
        "acronym_map": acronym_map,
        "merge_debug": merge_debug,
        "filtered_section_headings": filtered_section_headings,
        "filtered_non_requirement_rows": filtered_non_requirement_rows,
        "non_requirement_filter_version": NON_REQUIREMENT_FILTER_VERSION,
        "semantic_eligibility_version": JD_SEMANTIC_ELIGIBILITY_VERSION,
        "canonical_requirement_decomposition_version": (
            CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION
        ),
        "decomposition_debug": decomposition_debug,
    }


def build_resume_evidence_index(
    resume_profile: dict[str, Any] | None,
    raw_resume_text: str = "",
) -> list[dict[str, str]]:
    """Build stable, source-labelled evidence rows from the current résumé."""
    profile = resume_profile or {}
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    structured_texts: set[str] = set()

    def add(section: str, text: Any, source: str) -> None:
        cleaned = _clean_text(text)
        if not cleaned:
            return
        normalised = _normalise_basic(cleaned)

        if section == "raw_text":
            if any(
                normalised == structured
                or (
                    len(normalised) >= 8
                    and normalised in structured
                )
                for structured in structured_texts
            ):
                return
        else:
            structured_texts.add(normalised)

        key = (section, normalised)
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


def _deterministic_weak_evidence_is_sufficient(
    *,
    score: float,
    focus_coverage: float,
    overlap_count: int,
) -> bool:
    """Return whether lexical evidence is sufficient for weak credit."""
    return bool(
        score >= _DETERMINISTIC_WEAK_MIN_SCORE
        and focus_coverage >= _DETERMINISTIC_WEAK_MIN_COVERAGE
        and overlap_count >= _DETERMINISTIC_WEAK_MIN_OVERLAP
    )


def build_deterministic_keyword_match(
    *,
    requirements: list[dict[str, Any]],
    acronym_map: dict[str, str],
    resume_profile: dict[str, Any] | None,
    raw_resume_text: str = "",
) -> dict[str, list[dict[str, Any]]]:
    """Build conservative zero-cost keyword rows from the complete résumé."""
    evidence_index = build_resume_evidence_index(
        resume_profile,
        raw_resume_text,
    )
    present: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        focus = _clean_text(
            requirement.get("atomic_focus")
            or requirement.get("text")
        )
        best, similarity, coverage, overlap = _best_resume_evidence(
            requirement,
            "",
            evidence_index,
            acronym_map,
        )
        matched_skill = bool(best and best.get("section") == "skills")
        label = classify_verified_evidence_support(
            coverage=coverage,
            best_similarity=similarity,
            strong_evidence_count=(1 if similarity >= 0.72 else 0),
            has_matched_skills=matched_skill,
        )
        if best is None or overlap <= 0:
            label = "none"
        elif (
            label == "weak"
            and not _deterministic_weak_evidence_is_sufficient(
                score=similarity,
                focus_coverage=coverage,
                overlap_count=overlap,
            )
        ):
            label = "none"
        if label == "none":
            missing.append({"keyword": focus})
            continue
        present.append(
            {
                "keyword": focus,
                "matched_resume_term": best.get("text", ""),
                "match_type": label,
                "evidence_type": label,
                "found_in": best.get("section", ""),
                "match_reason": (
                    "Deterministic full-snapshot evidence support using the "
                    "shared stable evidence thresholds."
                ),
                "evidence_similarity": f"{similarity:.3f}",
            }
        )
    return {"present": present, "missing": missing}



_CREDENTIAL_REQUIREMENT_CUES = (
    "degree",
    "bachelor",
    "master",
    "phd",
    "doctorate",
    "diploma",
    "education",
    "academic",
    "qualification",
    "certification",
    "certified",
    "graduate",
    "university",
    "college",
)


def _evidence_source_is_requirement_compatible(
    requirement: dict[str, Any],
    row: dict[str, str],
) -> bool:
    """Reject source/claim combinations that lexical overlap cannot prove.

    Degree headings can prove education/credential requirements, but a degree
    title containing a generic word such as \"design\" is not evidence of
    practical design/implementation experience. Explicit course rows remain
    eligible for subject-matter requirements.
    """
    if row.get("section") != "education":
        return True

    source = _clean_text(row.get("source"))
    if ".courses[" in source:
        return True

    focus = _normalise_basic(
        requirement.get("atomic_focus")
        or requirement.get("text")
        or ""
    )
    focus_tokens = set(focus.split())
    return any(cue in focus_tokens for cue in _CREDENTIAL_REQUIREMENT_CUES)




_LABEL_ORDER_FOR_RESELECTION = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}


def _single_row_taxonomy_evidence_text(row: dict[str, Any]) -> str:
    return "\n".join(
        _clean_text(item.get("text", ""))
        for item in row.get("evidence", []) or []
        if isinstance(item, dict) and _clean_text(item.get("text", ""))
    )


def _apply_capability_single_row_reselection(
    rows: list[dict[str, Any]],
    *,
    evidence_index: list[dict[str, str]],
    acronym_map: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Repair taxonomy-caused under-credit with one stronger compatible row.

    This policy never promotes a preliminary ``none`` match, never combines
    evidence rows, and never exceeds the preliminary match label. It only runs
    for capabilities that explicitly opt in through the taxonomy.
    """
    taxonomy = get_default_taxonomy()
    capabilities = taxonomy.by_id()
    output = deepcopy(rows)
    audit_rows: list[dict[str, Any]] = []

    for row in output:
        preliminary_label = _clean_text(row.get("match_label")).lower()
        preliminary_rank = _LABEL_ORDER_FOR_RESELECTION.get(
            preliminary_label,
            0,
        )
        if preliminary_rank <= 0:
            continue

        original_evidence_text = _single_row_taxonomy_evidence_text(row)
        original_decision = evaluate_evidence(
            row,
            original_evidence_text,
            taxonomy,
        )
        capability_id = _clean_text(original_decision.get("capability_id"))
        taxonomy_label = _clean_text(
            original_decision.get("label")
        ).lower()

        if not capability_id or taxonomy_label not in _LABEL_ORDER_FOR_RESELECTION:
            continue

        capability = capabilities.get(capability_id) or {}
        if capability.get("allow_stronger_single_row_reselection") is not True:
            continue

        original_taxonomy_rank = _LABEL_ORDER_FOR_RESELECTION[taxonomy_label]
        if original_taxonomy_rank >= preliminary_rank:
            continue

        baseline_final_rank = min(
            preliminary_rank,
            original_taxonomy_rank,
        )
        best_final_rank = baseline_final_rank
        selected_row: dict[str, str] | None = None
        selected_decision: dict[str, Any] | None = None
        selected_coverage = 0.0
        selected_overlap = 0

        focus = _clean_text(
            row.get("atomic_focus") or row.get("text")
        )

        for evidence_row in evidence_index:
            if not _evidence_source_is_requirement_compatible(
                row,
                evidence_row,
            ):
                continue

            decision = evaluate_evidence(
                row,
                str(evidence_row.get("text") or ""),
                taxonomy,
            )
            if _clean_text(decision.get("capability_id")) != capability_id:
                continue

            candidate_taxonomy_label = _clean_text(
                decision.get("label")
            ).lower()
            candidate_taxonomy_rank = _LABEL_ORDER_FOR_RESELECTION.get(
                candidate_taxonomy_label,
                0,
            )
            candidate_final_rank = min(
                preliminary_rank,
                candidate_taxonomy_rank,
            )
            if candidate_final_rank <= best_final_rank:
                continue

            coverage, overlap = deterministic_evidence_coverage_metrics(
                focus,
                str(evidence_row.get("text") or ""),
                acronym_map,
            )
            best_final_rank = candidate_final_rank
            selected_row = evidence_row
            selected_decision = decision
            selected_coverage = coverage
            selected_overlap = overlap

            if candidate_final_rank == preliminary_rank:
                break

        if selected_row is None or selected_decision is None:
            continue

        original_evidence = [
            deepcopy(item)
            for item in row.get("evidence", []) or []
            if isinstance(item, dict)
        ]
        selected_evidence = {
            **deepcopy(selected_row),
            "reason": (
                "One existing resume row independently supports the same "
                "recognised capability more strongly after the originally "
                "linked evidence would have been taxonomy-capped; evidence "
                "rows were not combined."
            ),
            "evidence_similarity": f"{selected_coverage:.3f}",
        }
        row["evidence"] = [selected_evidence]
        row["capability_evidence_reselection"] = {
            "policy_version": CAPABILITY_EVIDENCE_RESELECTION_POLICY_VERSION,
            "status": "stronger_single_row_selected",
            "capability_id": capability_id,
            "preliminary_match_ceiling": preliminary_label,
            "original_taxonomy_label": taxonomy_label,
            "selected_taxonomy_label": _clean_text(
                selected_decision.get("label")
            ).lower(),
            "original_evidence": original_evidence,
            "selected_evidence_id": _clean_text(
                selected_row.get("evidence_id")
            ),
            "selected_evidence_source": _clean_text(
                selected_row.get("source")
            ),
            "selected_requirement_coverage": round(
                selected_coverage,
                6,
            ),
            "selected_requirement_overlap_count": selected_overlap,
            "combined_evidence_rows": False,
        }
        audit_rows.append(
            {
                "requirement_id": _clean_text(
                    row.get("requirement_id")
                ),
                **deepcopy(row["capability_evidence_reselection"]),
            }
        )

    return output, audit_rows


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
        if not _evidence_source_is_requirement_compatible(
            requirement,
            row,
        ):
            continue

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
    if best is None or not _deterministic_weak_evidence_is_sufficient(
        score=score,
        focus_coverage=focus_coverage,
        overlap_count=overlap_count,
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

                if (
                    reference is not None
                    and match_label == "weak"
                    and evidence_index
                    and not _deterministic_weak_evidence_is_sufficient(
                        score=evidence_score,
                        focus_coverage=evidence_coverage,
                        overlap_count=evidence_overlap,
                    )
                ):
                    warnings.append(
                        {
                            "requirement_id": requirement["requirement_id"],
                            "code": "insufficient_weak_evidence_context",
                            "message": (
                                "Weak credit was removed because the actual "
                                "resume evidence did not overlap enough of the "
                                "requirement under the shared deterministic "
                                "weak-evidence thresholds."
                            ),
                        }
                    )
                    match_label = "none"
                    reference = None

                if reference is not None:
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
        if requirement_is_score_eligible(row)
        and _clean_text(row.get("importance")).lower() in accepted_importance
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
    scoring_rows = [
        row for row in linked_requirements if requirement_is_score_eligible(row)
    ]
    excluded_non_scoring_count = len(linked_requirements) - len(scoring_rows)

    required_score, _, required_denominator = _weighted_coverage(
        scoring_rows,
        {"deal_breaker", "required", "core"},
    )
    preferred_score, _, preferred_denominator = _weighted_coverage(
        scoring_rows,
        {"preferred"},
    )

    evidence_values = [
        min(5, max(0, int(row.get("evidence_strength", 0))))
        for row in scoring_rows
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
        for row in scoring_rows
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
        "requirement_count": len(scoring_rows),
        "excluded_non_scoring_requirement_count": excluded_non_scoring_count,
        "requirement_group_count": len(group_ids),
        "credited_requirement_count": sum(
            1
            for row in scoring_rows
            if row.get("match_label") != "none"
        ),
        "direct_requirement_count": sum(
            1
            for row in scoring_rows
            if row.get("match_label") == "direct"
        ),
        "transferable_requirement_count": sum(
            1
            for row in scoring_rows
            if row.get("match_label") == "transferable"
        ),
        "weak_requirement_count": sum(
            1
            for row in scoring_rows
            if row.get("match_label") == "weak"
        ),
        "required_core_requirement_count": sum(
            1
            for row in scoring_rows
            if row.get("importance") in {"deal_breaker", "required", "core"}
        ),
        "preferred_requirement_count": sum(
            1
            for row in scoring_rows
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
    retrieval_mode_override: str | None = None,
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

    structured_linked, structured_warnings = (
        apply_structured_requirement_matches(
            linked,
            resume_profile=resume_profile,
            raw_resume_text=raw_resume_text,
        )
    )

    validated, validation_warnings = validate_linked_matches(
        structured_linked
    )

    evidence_index = build_resume_evidence_index(
        resume_profile,
        raw_resume_text,
    )
    reselected, evidence_reselection_audit = (
        _apply_capability_single_row_reselection(
            validated,
            evidence_index=evidence_index,
            acronym_map=canonical["acronym_map"],
        )
    )

    taxonomy_version = get_default_taxonomy().version
    taxonomy_validated = apply_taxonomy_caps_to_requirements(
        reselected,
        retrieval_mode_override=retrieval_mode_override,
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
        "capability_evidence_reselection": {
            "policy_version": CAPABILITY_EVIDENCE_RESELECTION_POLICY_VERSION,
            "selection_count": len(evidence_reselection_audit),
            "audit": evidence_reselection_audit,
        },
        "canonicalisation_debug": {
            "acronym_map": canonical["acronym_map"],
            "merged_requirements": canonical["merge_debug"],
            "filtered_section_headings": canonical.get(
                "filtered_section_headings",
                [],
            ),
            "filtered_section_heading_count": len(
                canonical.get("filtered_section_headings", [])
            ),
            "filtered_non_requirement_rows": canonical.get(
                "filtered_non_requirement_rows",
                [],
            ),
            "filtered_non_requirement_count": len(
                canonical.get("filtered_non_requirement_rows", [])
            ),
            "non_requirement_filter_version": canonical.get(
                "non_requirement_filter_version",
                NON_REQUIREMENT_FILTER_VERSION,
            ),
            "semantic_eligibility_version": canonical.get(
                "semantic_eligibility_version",
                JD_SEMANTIC_ELIGIBILITY_VERSION,
            ),
            "canonical_requirement_decomposition_version": canonical.get(
                "canonical_requirement_decomposition_version",
                CANONICAL_REQUIREMENT_DECOMPOSITION_VERSION,
            ),
            "decomposition": canonical.get("decomposition_debug", {}),
            "atomic_requirement_count": sum(
                1
                for row in taxonomy_validated
                if row.get("is_atomic")
            ),
        },
        "validation_warnings": (
            link_warnings
            + structured_warnings
            + validation_warnings
            + taxonomy_warnings
        ),
        **score,
    }
