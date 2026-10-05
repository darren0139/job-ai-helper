from __future__ import annotations

import re
from typing import Any


def rank_current_job_matches(jobs, *, context):
    """Sort by the existing native score; exclude stale scores, preserve tie order."""
    from job_discovery.matching import inspect_job_match
    def score(job):
        state = inspect_job_match(job, context=context)
        if state["status"] != "current":
            return -1
        return (state["snapshot"].get("summary") or {}).get("deterministic_alignment_score", 0)
    return sorted(jobs, key=score, reverse=True)


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9+#.]+", value.lower()) if len(token) >= 2]


def lexical_relevance(job: dict[str, Any], query: str) -> float:
    tokens = _tokens(str(query or ""))
    if not tokens:
        return 0.0
    title = str(job.get("title") or "").lower()
    company = str(job.get("company") or "").lower()
    description = str(job.get("description") or "").lower()
    score = 0.0
    for token in tokens:
        if token in title:
            score += 4.0
        if token in company:
            score += 1.5
        if token in description:
            score += 1.0
    if all(token in title for token in tokens):
        score += 3.0
    return score
