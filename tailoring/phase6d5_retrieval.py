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

    base = {
        "retrieval_version": RETRIEVAL_VERSION,
        "requested_mode": mode,
        "shadow_only": True,
        "influences_scoring": False,
        "query": query,
        "top_k": top_k,
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

        # Efficient hybrid mode: call the embedding API only when exact
        # matching and lexical retrieval both failed to return candidates.
        should_use_vector = (
            mode == "vector"
            or (
                mode == "hybrid"
                and not lexical_rows
            )
        )

        if should_use_vector:
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
