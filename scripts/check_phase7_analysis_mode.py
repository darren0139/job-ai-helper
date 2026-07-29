from __future__ import annotations

from analysis_stability.analysis_cache_mode import (
    ANALYSIS_CACHE_MODE_OPTIONS,
    resolve_analysis_cache_mode,
)


def main() -> int:
    passed = True
    for mode in ANALYSIS_CACHE_MODE_OPTIONS:
        reuse, force_fresh = resolve_analysis_cache_mode(mode)
        exclusive = bool(reuse) != bool(force_fresh)
        passed = passed and exclusive
        print(
            f"{mode}: reuse={reuse}, "
            f"force_fresh={force_fresh}, exclusive={exclusive}"
        )

    print(
        "PHASE 7 ANALYSIS MODE SMOKE TEST:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
