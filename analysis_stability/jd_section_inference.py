"""Generic deterministic JD section inference from local document structure.

Company-agnostic and conservative:
- exact known headings remain authoritative;
- unknown headings are inferred only from a coherent child list/run;
- ambiguous custom sections become boundaries, not scoring sections;
- ordinary unheaded prose keeps the existing conservative rules.
"""

from __future__ import annotations

import re
from typing import Any

JD_STRUCTURE_INFERENCE_VERSION = "jd-structure-inference-v1.0.3"

_BULLET_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s+")

_TASK_VERB_RE = re.compile(
    r"^(?:you\s+will\s+)?"
    r"(?:collaborate|perform|analy[sz]e|troubleshoot|generate|contribute|"
    r"keep|design|build|maintain|implement|test|develop|create|support|"
    r"manage|lead|write|review|deploy|monitor|coordinate|investigate|"
    r"deliver|own|partner|drive|ensure|participate|prepare|document|"
    r"integrate|configure|operate|research|evaluate|improve)\b",
    re.IGNORECASE,
)

_QUALIFICATION_RE = re.compile(
    r"\b(?:experience|knowledge|familiar(?:ity|\s+with)?|proficien(?:cy|t)|"
    r"ability|skills?|degree|diploma|bachelor|master(?:'s)?|"
    r"candidate(?:s)?\s+with|team\s+player|attention\s+to\s+detail|"
    r"problem[- ]solving|critical\s+thinking|analytical|"
    r"comfortable\s+(?:using|with)|required|preferred|advantage|"
    r"desired|must\b|should\b|qualification)\b",
    re.IGNORECASE,
)

_EMPLOYER_OFFER_RE = re.compile(
    r"\b(?:competitive\s+(?:salary|remuneration|compensation)|"
    r"remuneration|compensation|benefits?|perks?|insurance|"
    r"paid\s+time\s+off|pto\b|annual\s+leave|parental\s+leave|"
    r"wellness|wellbeing|retirement|stock\s+options?|equity|"
    r"employee\s+assistance|safe\s+space|diverse\s+perspectives|"
    r"unique\s+contributions|meaningful\s+work|"
    r"(?:fun|inclusive|supportive|collaborative|flexible)\s+workplace|"
    r"environment\s+where\s+you\s+will|work[- ]life\s+balance|"
    r"learning\s+allowance|staff\s+discount)\b",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _strip_bullet(value: Any) -> tuple[str, bool]:
    raw = str(value or "").strip()
    marked = bool(_BULLET_RE.match(raw))
    return _clean(_BULLET_RE.sub("", raw)), marked


def _tokens(value: Any) -> list[str]:
    return re.findall(r"[A-Za-z0-9+#.]+", _clean(value))


def _heading_shape(value: Any) -> bool:
    """Return whether a line is structurally plausible as a custom heading.

    Generic inference is a fallback. False negatives are safer than stealing a
    real requirement, list introducer, or wrapped continuation from the
    existing deterministic parser.
    """
    text, marked = _strip_bullet(value)
    if marked or not text:
        return False

    tokens = _tokens(text)
    if not (2 <= len(tokens) <= 12) or len(text) > 110:
        return False

    first_alpha = next((char for char in text if char.isalpha()), "")
    if first_alpha and not first_alpha.isupper():
        return False

    if re.search(r"[.!?;]\s*$", text):
        return False

    return True

def _signals(value: Any) -> dict[str, int]:
    text = _clean(value).strip(" ,;:.-")
    return {
        "responsibilities": 1 if _TASK_VERB_RE.search(text) else 0,
        "requirements": 1 if _QUALIFICATION_RE.search(text) else 0,
        "stop": 1 if _EMPLOYER_OFFER_RE.search(text) else 0,
    }


def _has_signal(value: Any) -> bool:
    return any(_signals(value).values())


def _following_items(
    lines: list[str],
    heading_index: int,
    *,
    max_items: int = 10,
) -> tuple[list[str], bool]:
    items: list[str] = []
    saw_marked = False
    started = False

    for raw in lines[heading_index + 1:]:
        if len(items) >= max_items:
            break
        if not str(raw or "").strip():
            if started:
                break
            continue

        text, marked = _strip_bullet(raw)
        if not text:
            continue

        if marked:
            saw_marked = True
            started = True
            items.append(text)
            continue

        if saw_marked:
            break

        if _heading_shape(raw) and not _has_signal(text):
            break

        if len(text) > 260 or len(_tokens(text)) > 42:
            break

        started = True
        items.append(text)

    minimum = 2 if saw_marked else 3
    if len(items) < minimum:
        return [], saw_marked
    return items, saw_marked


def infer_semantic_list_heading(
    raw_lines: list[str],
    heading_index: int,
) -> dict[str, Any]:
    if heading_index < 0 or heading_index >= len(raw_lines):
        return {
            "is_heading_candidate": False,
            "section": "",
            "reason": "out_of_range",
        }

    raw_heading = _clean(raw_lines[heading_index])
    if not _heading_shape(raw_heading):
        return {
            "is_heading_candidate": False,
            "section": "",
            "reason": "not_heading_shape",
        }

    heading = raw_heading.strip("-•* \t")

    heading_signals = _signals(heading)
    if (
        heading_signals["responsibilities"]
        or heading_signals["requirements"]
    ):
        return {
            "is_heading_candidate": False,
            "section": "",
            "reason": "requirement_like_line",
        }

    items, marked = _following_items(raw_lines, heading_index)
    if not items:
        return {
            "is_heading_candidate": False,
            "section": "",
            "reason": "no_coherent_following_list",
        }

    scores = {"responsibilities": 0, "requirements": 0, "stop": 0}
    item_debug = []
    for item in items:
        signals = _signals(item)
        for key in scores:
            scores[key] += signals[key]
        item_debug.append({"text": item, **signals})

    ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    winner, winner_score = ordered[0]
    runner_up = ordered[1][1]
    minimum_score = 2 if marked else 3
    minimum_ratio = 0.50 if marked else 0.60

    dominant = (
        winner_score >= minimum_score
        and winner_score / max(1, len(items)) >= minimum_ratio
        and winner_score > runner_up
    )

    if not dominant:
        return {
            "is_heading_candidate": True,
            "section": "",
            "heading": heading,
            "reason": "ambiguous_child_semantics",
            "marked_list": marked,
            "item_count": len(items),
            "scores": scores,
            "items": item_debug,
        }

    return {
        "is_heading_candidate": True,
        "section": winner,
        "heading": heading,
        "reason": "dominant_child_list_semantics",
        "marked_list": marked,
        "item_count": len(items),
        "scores": scores,
        "items": item_debug,
    }

