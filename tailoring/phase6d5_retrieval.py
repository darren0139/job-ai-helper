from __future__ import annotations

import os
from typing import Any

from rag.capability_taxonomy_rag import (
    lexical_retrieve,
    retrieve_taxonomy_candidates,
)

RETRIEVAL_VERSION = "phase6d5-shadow-retrieval-v1"
_ALLOWED_MODES = {"off", "lexical", "vector", "hybrid"}


def capability_rag_mode() -> str:
    mode = str(
        os.getenv(
            "CAPABILITY_RAG_MODE",
            "lexical",
        )
    ).strip().lower()

    return mode if mode in _ALLOWED_MODES else "lexical"


def capability_rag_top_k() -> int:
    try:
        value = int(
            os.getenv(
                "CAPABILITY_RAG_TOP_K",
                "5",
            )
        )
    except (TypeError, ValueError):
        value = 5

    return max(1, min(value, 10))



def capability_rag_vector_threshold() -> float:
    try:
        value = float(
            os.getenv(
                "CAPABILITY_RAG_VECTOR_THRESHOLD",
                "0.30",
            )
        )
    except (TypeError, ValueError):
        value = 0.30

    return max(0.0, min(value, 1.0))



def _requirement_text(
    requirement: dict[str, Any],
) -> str:
    parts = [
        str(requirement.get("text") or "").strip(),
        str(requirement.get("atomic_focus") or "").strip(),
    ]
    return " ".join(
        dict.fromkeys(
            part
            for part in parts
            if part
        )
    ).strip()


def _candidate_id(
    row: dict[str, Any],
) -> str:
    metadata = row.get("metadata") or {}
    return str(
        metadata.get("capability_id")
        or row.get("id")
        or ""
    ).strip()


def _merge_candidates(
    lexical_rows: list[dict[str, Any]],
    vector_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for row in lexical_rows:
        capability_id = _candidate_id(row)
        if not capability_id:
            continue

        merged.setdefault(
            capability_id,
            {
                "capability_id": capability_id,
                "lexical_score": None,
                "vector_distance": None,
                "retrieval_sources": [],
            },
        )
        merged[capability_id]["lexical_score"] = row.get("score")
        merged[capability_id]["retrieval_sources"].append("lexical")

    for row in vector_rows:
        capability_id = _candidate_id(row)
        if not capability_id:
            continue

        merged.setdefault(
            capability_id,
            {
                "capability_id": capability_id,
                "lexical_score": None,
                "vector_distance": None,
                "retrieval_sources": [],
            },
        )
        merged[capability_id]["vector_distance"] = row.get("distance")
        merged[capability_id]["retrieval_sources"].append("vector")

    rows = list(merged.values())
    for row in rows:
        row["retrieval_sources"] = list(
            dict.fromkeys(
                row["retrieval_sources"]
            )
        )

    rows.sort(
        key=lambda row: (
            -float(row.get("lexical_score") or 0.0),
            float(
                row.get("vector_distance")
                if row.get("vector_distance") is not None
                else 999999.0
            ),
            str(row.get("capability_id") or ""),
        )
    )
    return rows


def build_capability_retrieval_trace(
    requirement: dict[str, Any],
    *,
    exact_capability_id: str | None,
) -> dict[str, Any]:
    # Phase 6D.5 is shadow retrieval: candidates are diagnostics only.
    # The stable label and score remain owned by deterministic Phase 6D.4.
    mode = capability_rag_mode()
    query = _requirement_text(requirement)
    top_k = capability_rag_top_k()
    vector_threshold = capability_rag_vector_threshold()

    base = {
        "retrieval_version": RETRIEVAL_VERSION,
        "requested_mode": mode,
        "shadow_only": True,
        "influences_scoring": False,
        "query": query,
        "top_k": top_k,
        "vector_threshold": vector_threshold,
        "lexical_top_score": 0.0,
        "vector_attempted": False,
        "vector_trigger_reason": "",
        "used_modes": [],
        "status": "",
        "exact_capability_id": (
            str(exact_capability_id).strip()
            if exact_capability_id
            else None
        ),
        "candidates": [],
        "vector_fallback_reason": "",
    }

    if exact_capability_id:
        base["status"] = "not_needed_exact_match"
        return base

    if mode == "off":
        base["status"] = "disabled"
        return base

    if not query:
        base["status"] = "empty_query"
        return base

    lexical_rows: list[dict[str, Any]] = []
    vector_rows: list[dict[str, Any]] = []

    try:
        if mode in {"lexical", "hybrid"}:
            lexical_rows = lexical_retrieve(
                query,
                top_k=top_k,
            )
            base["used_modes"].append("lexical")

        lexical_top_score = (
            float(lexical_rows[0].get("score") or 0.0)
            if lexical_rows
            else 0.0
        )
        base["lexical_top_score"] = round(lexical_top_score, 6)

        ambiguous_top = False
        if len(lexical_rows) >= 2:
            first_score = float(lexical_rows[0].get("score") or 0.0)
            second_score = float(lexical_rows[1].get("score") or 0.0)
            ambiguous_top = abs(first_score - second_score) <= 0.02

        low_confidence = (
            not lexical_rows
            or lexical_top_score < vector_threshold
        )

        should_use_vector = False
        if mode == "vector":
            should_use_vector = True
            base["vector_trigger_reason"] = "vector_mode"
        elif mode == "hybrid" and low_confidence:
            should_use_vector = True
            base["vector_trigger_reason"] = "low_lexical_confidence"
        elif mode == "hybrid" and ambiguous_top:
            should_use_vector = True
            base["vector_trigger_reason"] = "ambiguous_lexical_tie"

        if should_use_vector:
            base["vector_attempted"] = True
            try:
                vector_rows = retrieve_taxonomy_candidates(
                    query,
                    top_k=top_k,
                    use_embeddings=True,
                )
                base["used_modes"].append("vector")
            except Exception as exc:
                base["vector_fallback_reason"] = (
                    f"{type(exc).__name__}: {exc}"
                )

                if mode == "vector":
                    lexical_rows = lexical_retrieve(
                        query,
                        top_k=top_k,
                    )
                    base["used_modes"].append(
                        "lexical_fallback"
                    )

        base["candidates"] = _merge_candidates(
            lexical_rows,
            vector_rows,
        )
        base["status"] = (
            "candidates_retrieved"
            if base["candidates"]
            else "no_candidates"
        )
        return base

    except Exception as exc:
        base["status"] = "retrieval_error"
        base["vector_fallback_reason"] = (
            f"{type(exc).__name__}: {exc}"
        )
        return base
