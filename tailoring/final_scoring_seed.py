"""Canonical frozen Phase 8 scoring seed shared with Phase 9C."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable

from analysis_stability.stable_evidence_scoring import (
    MATCH_VALUES,
    SCORING_VERSION,
    compute_deterministic_alignment,
)

FINAL_SCORING_SEED_VERSION = "phase8-final-scoring-seed-v1"

_SCORING_ROW_FIELDS = (
    "requirement_id",
    "text",
    "importance",
    "atomic_group_id",
    "group_weight_fraction",
    "match_label",
    "match_value",
    "evidence_strength",
    "capability_id",
)

_AGGREGATE_FIELDS = (
    "deterministic_alignment_score",
    "alignment_band",
    "required_core_coverage_score",
    "preferred_coverage_score",
    "evidence_strength_score",
    "credited_requirement_count",
    "direct_requirement_count",
    "transferable_requirement_count",
    "weak_requirement_count",
    "required_core_requirement_count",
    "preferred_requirement_count",
    "boundary_status",
    "score_weights",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def canonical_scoring_rows(
    source: dict[str, Any] | Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_rows = (
        source.get("canonical_requirements", []) or []
        if isinstance(source, dict)
        else source
    )
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        row = {
            field: deepcopy(raw.get(field))
            for field in _SCORING_ROW_FIELDS
        }
        row["requirement_id"] = _clean(row.get("requirement_id"))
        row["text"] = _clean(row.get("text"))
        row["importance"] = _clean(row.get("importance"))
        row["atomic_group_id"] = _clean(row.get("atomic_group_id"))

        # match_label is the canonical scoring identity. Derive the numeric
        # value from the production table instead of trusting a missing,
        # None, stale, or contradictory serialized match_value.
        label = _clean(row.get("match_label")).lower() or "none"
        if label not in MATCH_VALUES:
            raise ValueError(
                "Final scoring row contains an invalid match label: "
                f"{label!r}."
            )
        row["match_label"] = label
        row["match_value"] = float(MATCH_VALUES[label])

        row["capability_id"] = _clean(row.get("capability_id"))
        row["evidence_strength"] = int(row.get("evidence_strength", 0) or 0)
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (row["requirement_id"], row["text"]),
    )


def score_final_scoring_rows(
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    return compute_deterministic_alignment(
        [deepcopy(row) for row in rows if isinstance(row, dict)]
    )


def build_final_scoring_seed(
    analysis: dict[str, Any],
) -> dict[str, Any]:
    rows = canonical_scoring_rows(analysis)
    aggregate = score_final_scoring_rows(rows)
    return {
        "seed_version": FINAL_SCORING_SEED_VERSION,
        "scoring_version": (
            _clean(analysis.get("scoring_version")) or SCORING_VERSION
        ),
        "capability_taxonomy_version": _clean(
            analysis.get("capability_taxonomy_version")
        ),
        "canonical_requirements": rows,
        "aggregate": {
            field: deepcopy(aggregate.get(field))
            for field in _AGGREGATE_FIELDS
            if field in aggregate
        },
    }


def fingerprint_final_scoring_seed(seed: dict[str, Any]) -> str:
    if not isinstance(seed, dict) or not seed:
        raise ValueError("A final scoring seed is required.")
    return hashlib.sha256(
        _canonical_json(seed).encode("utf-8")
    ).hexdigest()


def verify_final_scoring_seed(
    seed: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    expected = _clean(fingerprint)
    if not expected:
        raise ValueError("Final scoring seed fingerprint is required.")
    actual = fingerprint_final_scoring_seed(seed)
    if actual != expected:
        raise ValueError("Final scoring seed fingerprint mismatch.")
    rows = canonical_scoring_rows(
        seed.get("canonical_requirements", []) or []
    )
    reproduced = score_final_scoring_rows(rows)
    stored = seed.get("aggregate") or {}
    stored_score = int(
        stored.get("deterministic_alignment_score", 0) or 0
    )
    if reproduced["deterministic_alignment_score"] != stored_score:
        raise ValueError(
            "Final scoring seed aggregate does not reproduce its stored score."
        )
    return {
        "fingerprint": actual,
        "canonical_requirements": rows,
        "aggregate": reproduced,
    }
