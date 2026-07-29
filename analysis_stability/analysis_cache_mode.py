from __future__ import annotations

REUSE_EXACT_ANALYSIS_MODE = "Reuse exact saved analysis"
FORCE_FRESH_ANALYSIS_MODE = "Force fresh AI analysis"

ANALYSIS_CACHE_MODE_OPTIONS = (
    REUSE_EXACT_ANALYSIS_MODE,
    FORCE_FRESH_ANALYSIS_MODE,
)


def resolve_analysis_cache_mode(mode: str) -> tuple[bool, bool]:
    """Return mutually exclusive cache flags for the selected UI mode."""
    if mode == REUSE_EXACT_ANALYSIS_MODE:
        return True, False
    if mode == FORCE_FRESH_ANALYSIS_MODE:
        return False, True
    raise ValueError(f"Unsupported analysis cache mode: {mode!r}")
