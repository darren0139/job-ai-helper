from __future__ import annotations

import re
from typing import Any


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
