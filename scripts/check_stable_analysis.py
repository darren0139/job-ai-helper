"""Run Phase 6A.1C deterministic stable scoring against a downloaded debug bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis_stability import build_stable_analysis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "debug_bundle",
        type=Path,
        help="Path to a full debug bundle JSON file.",
    )
    args = parser.parse_args()

    payload = json.loads(
        args.debug_bundle.read_text(encoding="utf-8")
    )
    report = payload.get("analysis_report", {}) or {}

    stable = build_stable_analysis(
        jd_profile=report.get("jd_profile", {}) or {},
        keyword_match=report.get("keyword_match", {}) or {},
        raw_jd_text=report.get("raw_jd_text", ""),
        raw_resume_text=report.get("raw_resume_text", ""),
        resume_profile=report.get("resume_profile", {}) or {},
        bullet_quality_score=(
            report.get("bullets", {}) or {}
        ).get("bullet_quality_avg", 0),
        structure_score=(
            report.get("structure", {}) or {}
        ).get("structure_score", 0),
    )

    print(
        json.dumps(
            stable,
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
