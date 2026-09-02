"""Deterministic CAR-quality retention for Phase 6C fitting.

This module does not generate or rewrite résumé claims. It only inspects
already-produced source/candidate text and blocks fitting transformations that
would drop an explicit CAR dimension already present in the source.

For fitting purposes, "C" is treated as explicit context/scope rather than
requiring a textbook problem statement. "A" is a concrete action. "R" is an
explicit functional outcome or impact signal.
"""

from __future__ import annotations

import math
import re
from typing import Any


PHASE6C_CAR_RETENTION_VERSION = "phase6c4-car-retention-v2-selective-compaction"

_ACTION_VERBS = {
    "added", "automated", "built", "collaborated", "configured", "connected",
    "contributed", "created", "deployed", "designed", "developed",
    "implemented", "improved", "integrated", "led", "managed", "migrated",
    "optimized", "optimised", "refactored", "scripted", "secured", "set",
    "streamlined", "tested", "used",
}

_RESULT_CUE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("improve", r"\bimprov(?:e|ed|es|ing)\b"),
    ("reduce", r"\breduc(?:e|ed|es|ing)\b"),
    ("increase", r"\bincreas(?:e|ed|es|ing)\b"),
    ("decrease", r"\bdecreas(?:e|ed|es|ing)\b"),
    ("enable", r"\benabl(?:e|ed|es|ing)\b"),
    ("support", r"\bsupport(?:ed|s|ing)?\b"),
    ("ensure", r"\bensur(?:e|ed|es|ing)\b"),
    ("allow", r"\ballow(?:ed|s|ing)?\b"),
    ("streamline", r"\bstreamlin(?:e|ed|es|ing)\b"),
    ("accelerate", r"\baccelerat(?:e|ed|es|ing)\b"),
    ("boost", r"\bboost(?:ed|s|ing)?\b"),
    ("centralise", r"\bcentrali[sz](?:e|ed|es|ing)\b"),
    ("automate", r"\bautomat(?:e|ed|es|ing)\b"),
    ("secure", r"\bsecur(?:e|ed|es|ing)\b"),
    ("control", r"\bcontrol(?:led|s|ling)?\b"),
    ("connect", r"\bconnect(?:ed|s|ing)?\b"),
    ("provide", r"\bprovid(?:e|ed|es|ing)\b"),
    ("deliver", r"\bdeliver(?:ed|s|ing)?\b"),
    ("complete", r"\bcomplet(?:e|ed|es|ing)\b"),
    ("publish", r"\bpublish(?:ed|es|ing)?\b"),
)

_CONTEXT_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "environment",
        r"\b(?:in|within|using|with|across|on|for)\s+"
        r"(?:a|an|the\s+)?[A-Za-z0-9+#./-]+(?:\s+[A-Za-z0-9+#./-]+){0,6}",
    ),
    (
        "team_scope",
        r"\b(?:team\s+of\s+\d+|\d+[- ]person|\d+[- ]member|"
        r"\d+[- ]person\s+team|\d+[- ]member\s+team)\b",
    ),
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _action_cues(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z]+", text.lower())
    return sorted({word for word in words if word in _ACTION_VERBS})


def _result_cues(text: str) -> list[str]:
    lowered = text.lower()
    return [
        label
        for label, pattern in _RESULT_CUE_PATTERNS
        if re.search(pattern, lowered)
    ]


def _context_cues(text: str) -> list[str]:
    lowered = text.lower()
    return [
        label
        for label, pattern in _CONTEXT_PATTERNS
        if re.search(pattern, lowered)
    ]


def analyse_car_components(text: str) -> dict[str, Any]:
    cleaned = _clean(text)
    actions = _action_cues(cleaned)
    contexts = _context_cues(cleaned)
    results = _result_cues(cleaned)
    dimensions = [
        name
        for name, present in (
            ("context", bool(contexts)),
            ("action", bool(actions)),
            ("result", bool(results)),
        )
        if present
    ]
    return {
        "text": cleaned,
        "context_present": bool(contexts),
        "action_present": bool(actions),
        "result_present": bool(results),
        "context_cues": contexts,
        "action_cues": actions,
        "result_cues": results,
        "car_dimensions": dimensions,
        "car_strength": len(dimensions),
    }


def evaluate_car_retention(
    source_bullets: list[str],
    candidate_bullet: str,
) -> dict[str, Any]:
    sources = [
        analyse_car_components(value)
        for value in source_bullets
        if _clean(value)
    ]
    candidate = analyse_car_components(candidate_bullet)

    source_dimensions = sorted(
        {
            dimension
            for source in sources
            for dimension in source["car_dimensions"]
        }
    )
    source_result_cues = sorted(
        {
            cue
            for source in sources
            for cue in source["result_cues"]
        }
    )

    missing_dimensions = [
        dimension
        for dimension in source_dimensions
        if dimension not in candidate["car_dimensions"]
    ]

    source_action_count = sum(
        1 for source in sources if source["action_present"]
    )
    candidate_action_count = len(candidate["action_cues"])

    minimum_result_cues = (
        max(1, int(math.ceil(len(source_result_cues) * 0.5)))
        if source_result_cues
        else 0
    )
    retained_result_cues = sorted(
        set(source_result_cues) & set(candidate["result_cues"])
    )
    result_count_ok = (
        len(retained_result_cues) >= minimum_result_cues
    )
    action_count_ok = bool(
        candidate["action_present"]
        and candidate_action_count >= min(source_action_count, len(sources))
    )

    preserves_minimum = bool(
        sources
        and action_count_ok
        and not missing_dimensions
        and result_count_ok
    )

    reasons: list[str] = []
    if not candidate["action_present"]:
        reasons.append("candidate_lost_action_dimension")
    elif not action_count_ok:
        reasons.append("candidate_lost_source_action_count")
    for dimension in missing_dimensions:
        reasons.append(f"candidate_lost_{dimension}_dimension")
    if not result_count_ok:
        reasons.append("candidate_lost_too_many_result_signals")

    return {
        "policy_version": PHASE6C_CAR_RETENTION_VERSION,
        "preserves_minimum": preserves_minimum,
        "source_dimensions": source_dimensions,
        "source_result_cues": source_result_cues,
        "source_result_signal_count": len(source_result_cues),
        "minimum_result_signal_count": minimum_result_cues,
        "retained_result_cues": retained_result_cues,
        "candidate": candidate,
        "reasons": reasons,
    }


def car_transform_preserves_minimum(
    source_bullet: str,
    candidate_bullet: str,
) -> bool:
    if _clean(source_bullet) == _clean(candidate_bullet):
        return True
    return bool(
        evaluate_car_retention(
            [source_bullet],
            candidate_bullet,
        )["preserves_minimum"]
    )


def build_compaction_car_debug(
    full_bullets: list[str],
    requested_compact_bullets: list[str],
    applied_bullets: list[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    rejected_indexes: list[int] = []
    applied_compact_indexes: list[int] = []

    for index, full in enumerate(full_bullets):
        requested = (
            requested_compact_bullets[index]
            if index < len(requested_compact_bullets)
            else full
        )
        applied = (
            applied_bullets[index]
            if index < len(applied_bullets)
            else full
        )
        requested_evaluation = evaluate_car_retention(
            [full],
            requested,
        )
        requested_changed = _clean(requested) != _clean(full)
        applied_changed = _clean(applied) != _clean(full)

        if requested_changed and not requested_evaluation["preserves_minimum"]:
            rejected_indexes.append(index)
        if applied_changed:
            applied_compact_indexes.append(index)

        rows.append(
            {
                "bullet_index": index,
                "requested_compact_changed": requested_changed,
                "requested_compact_preserves_car": bool(
                    requested_evaluation["preserves_minimum"]
                ),
                "applied_compact_changed": applied_changed,
                "source_dimensions": requested_evaluation["source_dimensions"],
                "source_result_cues": requested_evaluation["source_result_cues"],
                "candidate_result_cues": requested_evaluation["candidate"][
                    "result_cues"
                ],
                "reasons": requested_evaluation["reasons"],
            }
        )

    return {
        "policy_version": PHASE6C_CAR_RETENTION_VERSION,
        "requested_compact_rejected_indexes": rejected_indexes,
        "applied_compact_indexes": applied_compact_indexes,
        "rows": rows,
    }
