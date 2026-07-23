"""
Stable identifiers and near-duplicate detection for job descriptions.

This module is provider-independent and does not call ChromaDB. It produces:
- a source version ID for the exact normalized posting text;
- a canonical job ID for stable company/title/location identity;
- token-shingle similarity for near-duplicate checks.

Recommended Chroma metadata:
    canonical_jd_id
    source_version_id
    company_normalized
    title_normalized
    location_normalized
    posted_at
    first_seen_at
    last_seen_at
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


_WHITESPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w+#./-]+", re.UNICODE)
_TRACKING_RE = re.compile(
    r"\b(?:job id|requisition id|reference id|posting id)\s*[:#-]?\s*[\w-]+\b",
    re.IGNORECASE,
)


def normalize_field(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.casefold()
    text = _TRACKING_RE.sub(" ", text)
    text = _NON_WORD_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_jd_text(value: str) -> str:
    lines = [
        normalize_field(line)
        for line in str(value or "").splitlines()
    ]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _sha256_id(prefix: str, value: str, length: int = 20) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:length]}"


def source_version_id(raw_jd_text: str) -> str:
    return _sha256_id("jdv", normalize_jd_text(raw_jd_text))


def canonical_job_id(
    *,
    company: str,
    title: str,
    location: str = "",
) -> str:
    identity = "|".join(
        (
            normalize_field(company),
            normalize_field(title),
            normalize_field(location),
        )
    )
    return _sha256_id("jd", identity)


def word_tokens(text: str) -> set[str]:
    return set(normalize_jd_text(text).replace("\n", " ").split())


def word_shingles(text: str, size: int = 3) -> set[str]:
    words = normalize_jd_text(text).replace("\n", " ").split()
    if not words:
        return set()
    if len(words) < size:
        return {" ".join(words)}
    return {
        " ".join(words[index : index + size])
        for index in range(len(words) - size + 1)
    }


def jaccard_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


@dataclass(frozen=True)
class JobIdentity:
    canonical_jd_id: str
    source_version_id: str
    company_normalized: str
    title_normalized: str
    location_normalized: str


def build_job_identity(
    *,
    company: str,
    title: str,
    location: str,
    raw_jd_text: str,
) -> JobIdentity:
    return JobIdentity(
        canonical_jd_id=canonical_job_id(
            company=company,
            title=title,
            location=location,
        ),
        source_version_id=source_version_id(raw_jd_text),
        company_normalized=normalize_field(company),
        title_normalized=normalize_field(title),
        location_normalized=normalize_field(location),
    )


def is_probable_near_duplicate(
    *,
    existing_company: str,
    existing_title: str,
    existing_location: str,
    existing_text: str,
    candidate_company: str,
    candidate_title: str,
    candidate_location: str,
    candidate_text: str,
    minimum_text_similarity: float = 0.82,
) -> bool:
    same_identity = (
        normalize_field(existing_company) == normalize_field(candidate_company)
        and normalize_field(existing_title) == normalize_field(candidate_title)
        and (
            not normalize_field(existing_location)
            or not normalize_field(candidate_location)
            or normalize_field(existing_location)
            == normalize_field(candidate_location)
        )
    )
    if not same_identity:
        return False

    shingle_similarity = jaccard_similarity(
        word_shingles(existing_text),
        word_shingles(candidate_text),
    )
    token_similarity = jaccard_similarity(
        word_tokens(existing_text),
        word_tokens(candidate_text),
    )

    # Word shingles are strict about local order, while token overlap tolerates
    # harmless reordering such as "configuration and QA" versus
    # "QA and configuration". Requiring the stronger of the two keeps the
    # decision deterministic without treating unrelated roles as duplicates.
    similarity = max(shingle_similarity, token_similarity)
    return similarity >= minimum_text_similarity
