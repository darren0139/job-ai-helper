"""Current-version views of immutable historical Phase 9C test fixtures."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from analysis_stability.stable_evidence_scoring import (
    MATCH_VALUES,
    SCORING_VERSION,
    canonicalise_requirements,
    compute_deterministic_alignment,
)


FIXTURE = Path(__file__).resolve().parents[1] / "ci_fixtures" / (
    "phase9c_application94_acceptance.json"
)


def load_historical_phase9c_fixture() -> dict[str, Any]:
    """Load the immutable v1.4 historical fixture without modifying it."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _refresh_current_source_seed(fixture: dict[str, Any]) -> None:
    """Project the historical synthetic evidence seed onto current canonical rows.

    The checked-in fixture is immutable v1.4 provenance. Current-version tests
    model a newly promoted Phase 9B candidate by re-canonicalising the same
    saved source JD, keeping evidence labels only for requirement IDs that still
    exist. If the current parser introduces a genuinely new requirement ID,
    fail closed instead of inventing evidence for it.
    """
    candidate = fixture["candidate"]
    source_jd = fixture["saved_jds"][0]
    metadata = candidate.setdefault("evaluation_metadata", {})

    canonical = canonicalise_requirements(
        jd_profile=copy.deepcopy(source_jd.get("jd_profile") or {}),
        raw_jd_text=str(source_jd.get("raw_text") or ""),
    )
    current_rows = [
        row
        for row in canonical.get("requirements", [])
        if isinstance(row, dict) and str(row.get("requirement_id") or "").strip()
    ]

    historical_seed = metadata.get("source_jd_requirement_summary") or []
    historical_by_id = {
        str(row.get("requirement_id") or "").strip(): row
        for row in historical_seed
        if isinstance(row, dict)
        and str(row.get("requirement_id") or "").strip()
    }

    missing_seed_ids = [
        str(row["requirement_id"])
        for row in current_rows
        if str(row["requirement_id"]) not in historical_by_id
    ]
    if missing_seed_ids:
        raise RuntimeError(
            "Current Phase 9C fixture canonicalisation introduced requirement "
            "IDs with no frozen historical evidence seed: "
            + ", ".join(sorted(missing_seed_ids))
        )

    refreshed_summary: list[dict[str, Any]] = []
    linked_rows: list[dict[str, Any]] = []
    for canonical_row in current_rows:
        requirement_id = str(canonical_row["requirement_id"])
        seed = historical_by_id[requirement_id]
        label = str(seed.get("match_label") or "none").strip().lower()
        if label not in MATCH_VALUES:
            raise RuntimeError(
                "Historical Phase 9C fixture contains an unsupported match "
                f"label for {requirement_id}: {label!r}"
            )

        refreshed_summary.append(
            {
                "requirement_id": requirement_id,
                "text": str(canonical_row.get("text") or ""),
                "importance": str(canonical_row.get("importance") or ""),
                "match_label": label,
                "evidence_strength": int(seed.get("evidence_strength", 0) or 0),
                "capability_id": str(seed.get("capability_id") or ""),
            }
        )

        linked = copy.deepcopy(canonical_row)
        linked["match_label"] = label
        linked["match_value"] = MATCH_VALUES[label]
        linked["evidence_strength"] = int(seed.get("evidence_strength", 0) or 0)
        if str(seed.get("capability_id") or "").strip():
            linked["capability_id"] = str(seed.get("capability_id") or "").strip()
        linked_rows.append(linked)

    current_score = compute_deterministic_alignment(linked_rows)[
        "deterministic_alignment_score"
    ]
    current_ids = sorted(
        str(row["requirement_id"])
        for row in current_rows
    )

    candidate["canonical_requirement_ids"] = current_ids
    metadata["source_jd_requirement_summary"] = refreshed_summary
    metadata["source_jd_requirement_count"] = len(refreshed_summary)
    metadata["source_scoring_version"] = SCORING_VERSION
    candidate.setdefault("score_summary", {})["approved_tailored_score"] = (
        current_score
    )


def load_current_phase9c_fixture() -> dict[str, Any]:
    """Return a synthetic fresh candidate view for current-scoring tests.

    The committed fixture remains evidence of the historical v1.4 candidate.
    Current tests re-project its frozen evidence labels onto the current
    canonical source requirements, matching how a newly promoted Phase 9B
    candidate would carry current requirement identity and source score.
    """
    fixture = copy.deepcopy(load_historical_phase9c_fixture())
    _refresh_current_source_seed(fixture)
    return fixture
