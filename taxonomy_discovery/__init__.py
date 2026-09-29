"""Deterministic capability-taxonomy discovery diagnostics.

Keep package-level observation exports lazy. Stable scoring imports the
technology-registry submodule, while observations itself imports stable-scoring
helpers. Eagerly importing observations here would therefore create a circular
import merely from importing ``taxonomy_discovery.technology_registry``.
"""

from __future__ import annotations

from typing import Any


__all__ = [
    "DISCOVERY_VERSION",
    "aggregate_unresolved_observations",
    "build_discovery_report",
    "build_taxonomy_resolution_diagnostics",
    "build_unresolved_observations",
]

_OBSERVATION_EXPORTS = frozenset(__all__)


def __getattr__(name: str) -> Any:
    if name not in _OBSERVATION_EXPORTS:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    from taxonomy_discovery import observations

    value = getattr(observations, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _OBSERVATION_EXPORTS)
