"""Pure helpers for Phase 9F Application Session preview selection."""

from __future__ import annotations

from typing import Any, Callable


def _clean_generation_id(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def phase9f_preview_generation_candidates(
    *,
    session_generation_id: Any,
    durable_generation_id: Any,
) -> list[tuple[str, str]]:
    """Return preview candidates in UI-selection-first recovery order."""
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    for source, raw_id in (
        ("session", session_generation_id),
        ("durable_execution", durable_generation_id),
    ):
        generation_id = _clean_generation_id(raw_id)
        if not generation_id or generation_id in seen:
            continue
        candidates.append((source, generation_id))
        seen.add(generation_id)

    return candidates


def resolve_phase9f_preview_generation(
    *,
    session_generation_id: Any,
    durable_generation_id: Any,
    generation_loader: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    """Resolve the first available generation without mutating any state."""
    for source, generation_id in phase9f_preview_generation_candidates(
        session_generation_id=session_generation_id,
        durable_generation_id=durable_generation_id,
    ):
        generation = generation_loader(generation_id)
        if isinstance(generation, dict):
            return {
                "source": source,
                "generation_id": generation_id,
                "generation": generation,
            }

    return {
        "source": "",
        "generation_id": "",
        "generation": None,
    }
