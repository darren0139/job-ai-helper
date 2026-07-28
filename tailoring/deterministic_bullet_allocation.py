
"""
Phase 6B.2 deterministic bullet-budget allocation.

Python selects the exact canonical Evidence Library bullets and the exact
per-project bullet counts before the writing model runs. The model may preserve
or lightly rewrite those allocated bullets and may produce one-to-one compact
alternatives, but it does not decide the budget.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import Any

from tailoring.stable_tailoring_ranking import (
    build_bullet_evidence_priorities,
)


BULLET_ALLOCATION_VERSION = (
    "phase6b2-deterministic-bullet-allocation-v2"
)

_MATCH_STRENGTH = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}
_REQUIRED_IMPORTANCE = {
    "core",
    "deal_breaker",
    "required",
}

_STRONG_MATCH_LABELS = {"direct", "transferable"}

_STRONG_OWNERSHIP_VERBS = {
    "automated",
    "built",
    "configured",
    "created",
    "deployed",
    "designed",
    "developed",
    "implemented",
    "integrated",
    "led",
    "optimised",
    "optimized",
    "programmed",
    "scripted",
    "secured",
    "tested",
    "validated",
}
_GENERIC_SUPPORT_VERBS = {
    "assisted",
    "collaborated",
    "contributed",
    "helped",
    "participated",
    "supported",
    "worked",
}
_SOFT_NAMED_TERMS = {
    "collaboration",
    "communication",
    "leadership",
    "problem solving",
    "team collaboration",
    "team coordination",
    "teamwork",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item)
        key = text.lower()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


def _normalise_key(value: Any) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _stable_bullet_id(
    project_id: str,
    project_title: str,
    bullet_text: str,
) -> str:
    payload = "\n".join(
        (
            _normalise_key(project_id),
            _normalise_key(project_title),
            _normalise_key(bullet_text),
        )
    )
    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:12]
    return f"bullet_{digest}"


def _token_set(value: Any) -> set[str]:
    return {
        token
        for token in _normalise_key(value).split()
        if len(token) >= 3
    }


def _jaccard(
    left: set[str],
    right: set[str],
) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def _canonical_bullets(
    candidate: dict[str, Any],
) -> list[str]:
    evidence = (
        candidate.get("evidence_library_evidence")
        or {}
    )
    if not isinstance(evidence, dict):
        return []
    return _clean_string_list(
        evidence.get("bullets", [])
    )



def _candidate_named_terms(
    candidate: dict[str, Any],
) -> set[str]:
    evidence = (
        candidate.get("evidence_library_evidence")
        or {}
    )
    if not isinstance(evidence, dict):
        return set()

    values = [
        *(evidence.get("tools", []) or []),
        *(evidence.get("skills", []) or []),
    ]
    return {
        term
        for value in values
        if (term := _normalise_key(value))
        and term not in _SOFT_NAMED_TERMS
    }


def _bullet_quality_metrics(
    bullet: str,
    named_terms: set[str],
) -> dict[str, int]:
    bullet_key = _normalise_key(bullet)
    words = bullet_key.split()
    first_word = words[0] if words else ""

    named_term_count = sum(
        1
        for term in named_terms
        if f" {term} " in f" {bullet_key} "
    )

    if first_word in _STRONG_OWNERSHIP_VERBS:
        ownership_score = 2
    elif first_word in _GENERIC_SUPPORT_VERBS:
        ownership_score = 0
    elif first_word:
        ownership_score = 1
    else:
        ownership_score = 0

    return {
        "named_technical_term_count": named_term_count,
        "ownership_score": ownership_score,
    }


def _project_identity(
    candidate: dict[str, Any],
    ranking_row: dict[str, Any],
) -> tuple[str, str]:
    project_id = _clean_text(
        ranking_row.get("project_id")
    )
    title = _clean_text(
        candidate.get("title")
        or candidate.get("display_title")
    )
    if project_id:
        return project_id, title
    digest = hashlib.sha256(
        _normalise_key(title).encode("utf-8")
    ).hexdigest()[:12]
    return f"project_{digest}", title


def _match_by_id(
    ranking_row: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    for raw_match in (
        ranking_row.get("requirement_matches", [])
        or []
    ):
        if not isinstance(raw_match, dict):
            continue
        requirement_id = _clean_text(
            raw_match.get("requirement_id")
        )
        if requirement_id:
            matches[requirement_id] = raw_match
    return matches


def _build_project_state(
    *,
    candidate: dict[str, Any],
    ranking_row: dict[str, Any],
    project_order: int,
    max_bullets_per_project: int,
) -> dict[str, Any]:
    project_id, title = _project_identity(
        candidate,
        ranking_row,
    )
    bullets = _canonical_bullets(candidate)
    priorities = build_bullet_evidence_priorities(
        bullets=bullets,
        ranking_row=ranking_row,
    )
    priorities_by_index = {
        int(row.get("bullet_index", -1)): row
        for row in priorities
        if isinstance(row, dict)
    }
    matches = _match_by_id(ranking_row)
    named_terms = _candidate_named_terms(candidate)

    records: list[dict[str, Any]] = []
    for index, bullet in enumerate(bullets):
        priority = priorities_by_index.get(
            index,
            {},
        )
        supported_ids = {
            _clean_text(requirement_id)
            for requirement_id in (
                priority.get(
                    "supported_requirement_ids",
                    [],
                )
                or []
            )
            if _clean_text(requirement_id)
        }

        strong_supported_ids = {
            requirement_id
            for requirement_id in supported_ids
            if str(
                matches.get(
                    requirement_id,
                    {},
                ).get("match_label", "none")
            ).lower()
            in _STRONG_MATCH_LABELS
        }
        weak_supported_ids = {
            requirement_id
            for requirement_id in supported_ids
            if str(
                matches.get(
                    requirement_id,
                    {},
                ).get("match_label", "none")
            ).lower()
            == "weak"
        }
        direct_ids = {
            requirement_id
            for requirement_id in strong_supported_ids
            if str(
                matches.get(
                    requirement_id,
                    {},
                ).get("match_label", "none")
            ).lower()
            == "direct"
        }
        required_core_ids = {
            requirement_id
            for requirement_id in strong_supported_ids
            if str(
                matches.get(
                    requirement_id,
                    {},
                ).get("importance", "")
            ).lower()
            in _REQUIRED_IMPORTANCE
        }
        protected_ids = {
            _clean_text(requirement_id)
            for requirement_id in (
                priority.get(
                    "protected_requirement_ids",
                    [],
                )
                or []
            )
            if _clean_text(requirement_id)
        }
        strong_unique_required_core_count = sum(
            1
            for requirement_id in required_core_ids
            if requirement_id in protected_ids
        )
        strong_evidence_value = (
            sum(
                float(
                    matches.get(
                        requirement_id,
                        {},
                    ).get("coverage_points", 0.0)
                    or 0.0
                )
                for requirement_id in strong_supported_ids
            )
            + 5.0 * strong_unique_required_core_count
        )
        weak_evidence_value = sum(
            float(
                matches.get(
                    requirement_id,
                    {},
                ).get("coverage_points", 0.0)
                or 0.0
            )
            for requirement_id in weak_supported_ids
        )
        quality = _bullet_quality_metrics(
            bullet,
            named_terms,
        )

        records.append(
            {
                "bullet_index": index,
                "bullet_id": _stable_bullet_id(
                    project_id,
                    title,
                    bullet,
                ),
                "bullet_text": bullet,
                "tokens": _token_set(bullet),
                # Strong matches own allocation coverage. Weak matches
                # remain diagnostic and act only as a late tie-break.
                "supported_requirement_ids": (
                    sorted(strong_supported_ids)
                ),
                "all_supported_requirement_ids": (
                    sorted(supported_ids)
                ),
                "weak_supported_requirement_ids": (
                    sorted(weak_supported_ids)
                ),
                "direct_requirement_ids": (
                    sorted(direct_ids)
                ),
                "required_core_requirement_ids": (
                    sorted(required_core_ids)
                ),
                "evidence_value": round(
                    strong_evidence_value,
                    4,
                ),
                "weak_evidence_value": round(
                    weak_evidence_value,
                    4,
                ),
                "diagnostic_evidence_value": float(
                    priority.get(
                        "evidence_value",
                        0.0,
                    )
                    or 0.0
                ),
                "named_technical_term_count": quality[
                    "named_technical_term_count"
                ],
                "ownership_score": quality[
                    "ownership_score"
                ],
                "unique_required_core_count": (
                    strong_unique_required_core_count
                ),
                "evidence_priority": int(
                    priority.get(
                        "evidence_priority",
                        index + 1,
                    )
                    or index + 1
                ),
            }
        )

    capacity = min(
        max(1, int(max_bullets_per_project)),
        len(records),
    )
    requires_synthesis = not records
    if requires_synthesis:
        capacity = 1

    return {
        "project_id": project_id,
        "title": title,
        "display_title": _clean_text(
            candidate.get("display_title")
            or title
        ),
        "project_order": int(project_order),
        "project_fit_score": int(
            ranking_row.get("final_score", 0)
            or 0
        ),
        "candidate": candidate,
        "ranking_row": ranking_row,
        "records": records,
        "capacity": capacity,
        "requires_synthesis": requires_synthesis,
        "selected": [],
    }


def _selected_requirement_ids(
    state: dict[str, Any],
) -> set[str]:
    found: set[str] = set()
    for record in state.get("selected", []):
        found.update(
            record.get(
                "supported_requirement_ids",
                [],
            )
            or []
        )
    return found


def _record_distinctness(
    record: dict[str, Any],
    state: dict[str, Any],
) -> float:
    selected = state.get("selected", []) or []
    if not selected:
        return 1.0
    maximum_overlap = max(
        _jaccard(
            record.get("tokens", set()),
            item.get("tokens", set()),
        )
        for item in selected
    )
    return round(
        max(0.0, 1.0 - maximum_overlap),
        6,
    )


def _record_metrics(
    *,
    record: dict[str, Any],
    state: dict[str, Any],
    globally_covered: set[str],
) -> dict[str, Any]:
    supported = set(
        record.get(
            "supported_requirement_ids",
            [],
        )
        or []
    )
    direct = set(
        record.get(
            "direct_requirement_ids",
            [],
        )
        or []
    )
    required_core = set(
        record.get(
            "required_core_requirement_ids",
            [],
        )
        or []
    )
    project_covered = _selected_requirement_ids(
        state
    )

    return {
        "uncovered_required_core": len(
            required_core - globally_covered
        ),
        "uncovered_direct": len(
            direct - globally_covered
        ),
        "uncovered_any": len(
            supported - globally_covered
        ),
        "new_within_project": len(
            supported - project_covered
        ),
        "distinctness": _record_distinctness(
            record,
            state,
        ),
        "selected_count": len(
            state.get("selected", [])
        ),
    }


def _initial_record_key(
    record: dict[str, Any],
    state: dict[str, Any],
) -> tuple[Any, ...]:
    return (
        int(
            record.get(
                "unique_required_core_count",
                0,
            )
            or 0
        ),
        len(
            record.get(
                "direct_requirement_ids",
                [],
            )
            or []
        ),
        len(
            record.get(
                "required_core_requirement_ids",
                [],
            )
            or []
        ),
        int(
            record.get(
                "named_technical_term_count",
                0,
            )
            or 0
        ),
        int(
            record.get(
                "ownership_score",
                0,
            )
            or 0
        ),
        float(
            record.get(
                "evidence_value",
                0.0,
            )
            or 0.0
        ),
        float(
            record.get(
                "weak_evidence_value",
                0.0,
            )
            or 0.0
        ),
        int(
            state.get(
                "project_fit_score",
                0,
            )
            or 0
        ),
        -int(
            record.get(
                "evidence_priority",
                999,
            )
            or 999
        ),
        -int(
            record.get(
                "bullet_index",
                0,
            )
            or 0
        ),
    )


def _marginal_record_key(
    *,
    record: dict[str, Any],
    state: dict[str, Any],
    globally_covered: set[str],
) -> tuple[Any, ...]:
    metrics = _record_metrics(
        record=record,
        state=state,
        globally_covered=globally_covered,
    )
    return (
        metrics["uncovered_required_core"],
        metrics["uncovered_direct"],
        metrics["uncovered_any"],
        metrics["new_within_project"],
        -metrics["selected_count"],
        int(
            record.get(
                "unique_required_core_count",
                0,
            )
            or 0
        ),
        int(
            record.get(
                "named_technical_term_count",
                0,
            )
            or 0
        ),
        int(
            record.get(
                "ownership_score",
                0,
            )
            or 0
        ),
        float(
            record.get(
                "evidence_value",
                0.0,
            )
            or 0.0
        ),
        float(
            record.get(
                "weak_evidence_value",
                0.0,
            )
            or 0.0
        ),
        metrics["distinctness"],
        int(
            state.get(
                "project_fit_score",
                0,
            )
            or 0
        ),
        -int(
            record.get(
                "evidence_priority",
                999,
            )
            or 999
        ),
        -int(
            state.get(
                "project_order",
                0,
            )
            or 0
        ),
        -int(
            record.get(
                "bullet_index",
                0,
            )
            or 0
        ),
    )


def _remaining_records(
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    selected_ids = {
        item.get("bullet_id")
        for item in state.get("selected", [])
    }
    return [
        record
        for record in state.get("records", [])
        if record.get("bullet_id")
        not in selected_ids
    ]


def _select_record(
    *,
    state: dict[str, Any],
    record: dict[str, Any],
    reason: str,
    trace: list[dict[str, Any]],
) -> None:
    state["selected"].append(record)
    trace.append(
        {
            "project_id": state["project_id"],
            "project_title": state["title"],
            "bullet_id": record["bullet_id"],
            "bullet_text": record["bullet_text"],
            "reason": reason,
            "allocated_count_after": len(
                state["selected"]
            ),
        }
    )


def _global_covered(
    states: list[dict[str, Any]],
) -> set[str]:
    found: set[str] = set()
    for state in states:
        found.update(
            _selected_requirement_ids(state)
        )
    return found


def _best_remaining_choice(
    states: list[dict[str, Any]],
    globally_covered: set[str],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
] | None:
    choices: list[
        tuple[
            tuple[Any, ...],
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
        ]
    ] = []

    for state in states:
        if len(state["selected"]) >= int(
            state["capacity"]
        ):
            continue

        for record in _remaining_records(state):
            metrics = _record_metrics(
                record=record,
                state=state,
                globally_covered=globally_covered,
            )
            key = _marginal_record_key(
                record=record,
                state=state,
                globally_covered=globally_covered,
            )
            choices.append(
                (
                    key,
                    state,
                    record,
                    metrics,
                )
            )

    if not choices:
        return None

    choices.sort(
        key=lambda item: item[0],
        reverse=True,
    )
    _, state, record, metrics = choices[0]
    return state, record, metrics



def _best_expansion_choice(
    states: list[dict[str, Any]],
    globally_covered: set[str],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    str,
] | None:
    choices: list[
        tuple[
            tuple[Any, ...],
            dict[str, Any],
            dict[str, Any],
            str,
        ]
    ] = []

    for state in states:
        if len(state["selected"]) >= int(
            state["capacity"]
        ):
            continue

        for record in _remaining_records(state):
            metrics = _record_metrics(
                record=record,
                state=state,
                globally_covered=globally_covered,
            )
            reason = _expansion_reason(
                record=record,
                state=state,
                metrics=metrics,
            )
            if reason is None:
                continue
            choices.append(
                (
                    _marginal_record_key(
                        record=record,
                        state=state,
                        globally_covered=globally_covered,
                    ),
                    state,
                    record,
                    reason,
                )
            )

    if not choices:
        return None

    choices.sort(
        key=lambda item: item[0],
        reverse=True,
    )
    _, state, record, reason = choices[0]
    return state, record, reason


def _expansion_reason(
    *,
    record: dict[str, Any],
    state: dict[str, Any],
    metrics: dict[str, Any],
) -> str | None:
    if metrics["uncovered_required_core"] > 0:
        return "new_required_or_core_requirement"
    if metrics["uncovered_direct"] > 0:
        return "new_direct_requirement"
    if (
        metrics["uncovered_any"] > 0
        and float(
            record.get(
                "evidence_value",
                0.0,
            )
            or 0.0
        )
        > 0.0
    ):
        return "new_supported_requirement"
    if (
        int(
            state.get(
                "project_fit_score",
                0,
            )
            or 0
        )
        >= 70
        and metrics["distinctness"] >= 0.75
        and float(
            record.get(
                "evidence_value",
                0.0,
            )
            or 0.0
        )
        >= 8.0
    ):
        return "high_value_distinct_project_evidence"
    return None


def build_deterministic_bullet_allocation(
    *,
    selected_pairs: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
        ]
    ],
    max_bullets_per_project: int,
) -> dict[str, Any]:
    """
    Allocate exact canonical bullets across selected projects.

    Every selected project receives at least one target slot. Python first fills
    a balanced baseline of roughly two bullets per project, then expands beyond
    that baseline only when another bullet adds uncovered requirement evidence
    or unusually strong distinct evidence.
    """
    maximum = max(
        1,
        int(max_bullets_per_project),
    )
    states = [
        _build_project_state(
            candidate=candidate,
            ranking_row=ranking_row,
            project_order=index,
            max_bullets_per_project=maximum,
        )
        for index, (
            candidate,
            ranking_row,
        ) in enumerate(selected_pairs)
    ]

    trace: list[dict[str, Any]] = []

    # Minimum coverage: one bullet/target slot for every selected project.
    for state in states:
        records = state["records"]
        if not records:
            trace.append(
                {
                    "project_id": state["project_id"],
                    "project_title": state["title"],
                    "bullet_id": "",
                    "bullet_text": "",
                    "reason": "synthesis_slot_no_canonical_bullet",
                    "allocated_count_after": 1,
                }
            )
            continue

        first = max(
            records,
            key=lambda record: (
                _initial_record_key(
                    record,
                    state,
                ),
                record["bullet_id"],
            ),
        )
        _select_record(
            state=state,
            record=first,
            reason="minimum_project_coverage",
            trace=trace,
        )

    total_capacity = sum(
        int(state["capacity"])
        for state in states
    )
    target_count = sum(
        max(
            1,
            len(state["selected"]),
        )
        for state in states
    )
    base_budget = min(
        total_capacity,
        max(
            len(states),
            len(states) * 2,
        ),
    )

    # Fill the baseline budget using marginal requirement value and a stable
    # balance preference when evidence value is otherwise comparable.
    while target_count < base_budget:
        choice = _best_remaining_choice(
            states,
            _global_covered(states),
        )
        if choice is None:
            break

        state, record, _ = choice
        _select_record(
            state=state,
            record=record,
            reason="baseline_budget",
            trace=trace,
        )
        target_count += 1

    # Add evidence-justified expansion slots. This is what permits outcomes
    # such as 3/3/2, 3/3/3, or a fourth bullet when the configured maximum is 4.
    while target_count < total_capacity:
        choice = _best_expansion_choice(
            states,
            _global_covered(states),
        )
        if choice is None:
            break

        state, record, reason = choice
        _select_record(
            state=state,
            record=record,
            reason=reason,
            trace=trace,
        )
        target_count += 1

    project_plans: list[dict[str, Any]] = []
    for state in states:
        selected_records = sorted(
            state["selected"],
            key=lambda record: (
                int(
                    record.get(
                        "evidence_priority",
                        999,
                    )
                    or 999
                ),
                int(
                    record.get(
                        "bullet_index",
                        0,
                    )
                    or 0
                ),
                record.get("bullet_id", ""),
            ),
        )
        allocated_bullets = [
            record["bullet_text"]
            for record in selected_records
        ]
        allocated_ids = [
            record["bullet_id"]
            for record in selected_records
        ]
        allocated_count = (
            len(allocated_bullets)
            if allocated_bullets
            else 1
        )

        project_plans.append(
            {
                "project_id": state["project_id"],
                "title": state["title"],
                "display_title": state[
                    "display_title"
                ],
                "project_order": state[
                    "project_order"
                ],
                "project_fit_score": state[
                    "project_fit_score"
                ],
                "canonical_bullet_count": len(
                    state["records"]
                ),
                "max_bullets_per_project": maximum,
                "allocated_bullet_count": (
                    allocated_count
                ),
                "allocated_blueprint_bullets": (
                    allocated_bullets
                ),
                "allocated_bullet_ids": (
                    allocated_ids
                ),
                "requires_synthesis": bool(
                    state["requires_synthesis"]
                ),
                "allocation_version": (
                    BULLET_ALLOCATION_VERSION
                ),
            }
        )

    return {
        "allocation_version": (
            BULLET_ALLOCATION_VERSION
        ),
        "max_bullets_per_project": maximum,
        "selected_project_count": len(states),
        "base_bullet_budget": base_budget,
        "total_available_slots": total_capacity,
        "total_allocated_bullets": sum(
            int(
                plan[
                    "allocated_bullet_count"
                ]
            )
            for plan in project_plans
        ),
        "projects": project_plans,
        "selection_trace": trace,
    }


def _allocation_lookup_key(
    project_id: Any,
    title: Any,
) -> str:
    cleaned_id = _clean_text(project_id)
    if cleaned_id:
        return f"id:{cleaned_id}"
    return f"title:{_normalise_key(title)}"


def apply_bullet_allocation_to_selected_pairs(
    *,
    selected_pairs: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
        ]
    ],
    allocation: dict[str, Any],
) -> list[
    tuple[
        dict[str, Any],
        dict[str, Any],
    ]
]:
    """
    Return safe candidate copies exposing only Python-allocated canonical bullets
    to the writing stage.
    """
    plans = {
        _allocation_lookup_key(
            plan.get("project_id"),
            plan.get("title"),
        ): plan
        for plan in (
            allocation.get("projects", [])
            or []
        )
        if isinstance(plan, dict)
    }

    prepared: list[
        tuple[
            dict[str, Any],
            dict[str, Any],
        ]
    ] = []
    for candidate, ranking_row in selected_pairs:
        project_id, title = _project_identity(
            candidate,
            ranking_row,
        )
        plan = plans.get(
            _allocation_lookup_key(
                project_id,
                title,
            ),
            {},
        )

        candidate_copy = deepcopy(candidate)
        candidate_copy[
            "_phase6b2_bullet_allocation"
        ] = deepcopy(plan)

        allocated = _clean_string_list(
            plan.get(
                "allocated_blueprint_bullets",
                [],
            )
        )
        if allocated:
            evidence = deepcopy(
                candidate_copy.get(
                    "evidence_library_evidence"
                )
                or {}
            )
            evidence["bullets"] = allocated
            evidence["description"] = "\n".join(
                allocated
            )
            candidate_copy[
                "evidence_library_evidence"
            ] = evidence

        prepared.append(
            (
                candidate_copy,
                deepcopy(ranking_row),
            )
        )

    return prepared


def enforce_writer_plan_allocation(
    *,
    writer_plan: dict[str, Any] | None,
    allocation_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Make writer output obey the Python allocation exactly.

    Missing/mismatched full bullets fall back to the allocated canonical wording.
    Compact bullets are accepted only when they preserve the exact count.
    """
    plan = deepcopy(
        writer_plan
        if isinstance(writer_plan, dict)
        else {}
    )
    allocation_plan = (
        allocation_plan
        if isinstance(
            allocation_plan,
            dict,
        )
        else {}
    )
    allocated = _clean_string_list(
        allocation_plan.get(
            "allocated_blueprint_bullets",
            [],
        )
    )
    target_count = max(
        1,
        int(
            allocation_plan.get(
                "allocated_bullet_count",
                len(allocated) or 1,
            )
            or len(allocated)
            or 1
        ),
    )

    if allocated:
        plan[
            "selected_blueprint_bullets"
        ] = list(allocated)

        drafts = _clean_string_list(
            plan.get("draft_bullets", [])
        )
        rewrite_reason = _clean_text(
            plan.get("rewrite_reason", "")
        )

        if len(drafts) != len(allocated):
            plan["draft_bullets"] = list(
                allocated
            )
            plan["rewritten_bullets"] = []
            fallback_note = (
                "Python restored the exact Phase 6B.2 allocated "
                "canonical bullets because the writer returned a "
                "different bullet count."
            )
            plan["rewrite_reason"] = (
                f"{rewrite_reason} {fallback_note}"
            ).strip()
        elif not rewrite_reason:
            # No approved rewrite reason means exact canonical wording wins.
            plan["draft_bullets"] = list(
                allocated
            )
            plan["rewritten_bullets"] = []

        compact = _clean_string_list(
            plan.get("compact_bullets", [])
        )
        if len(compact) != len(allocated):
            plan["compact_bullets"] = []
    else:
        for field in (
            "selected_blueprint_bullets",
            "rewritten_bullets",
            "draft_bullets",
            "compact_bullets",
        ):
            values = _clean_string_list(
                plan.get(field, [])
            )
            plan[field] = values[
                :target_count
            ]

    plan["allocated_bullet_count"] = (
        target_count
    )
    plan["bullet_allocation_version"] = (
        BULLET_ALLOCATION_VERSION
    )
    return plan
