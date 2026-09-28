#!/usr/bin/env python3
"""Inspect TQ-D1/TQ-D2 unresolved capability observations from Job Match."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database.job_match_manager import (  # noqa: E402
    list_latest_compatible_job_match_snapshots,
)
from job_discovery.matching import current_match_versions  # noqa: E402
from taxonomy_discovery.observations import build_discovery_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate taxonomy-unresolved score-eligible canonical requirements "
            "from latest compatible Job Match snapshots."
        )
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default="",
        help="Optional path for the complete deterministic JSON report.",
    )
    args = parser.parse_args()

    versions = current_match_versions()
    snapshots = list_latest_compatible_job_match_snapshots(
        match_version=versions["match_version"],
        scoring_version=versions["scoring_version"],
        taxonomy_version=versions["taxonomy_version"],
    )
    report = build_discovery_report(
        snapshots,
        match_version=versions["match_version"],
        scoring_version=versions["scoring_version"],
        taxonomy_version=versions["taxonomy_version"],
    )

    for key in (
        "discovery_version",
        "match_version",
        "scoring_version",
        "taxonomy_version",
        "snapshot_count",
        "eligible_requirement_count",
        "resolved_requirement_count",
        "unresolved_observation_count",
        "candidate_count",
    ):
        print(f"{key}: {report[key]}")

    candidates = report.get("candidates") or []
    if not candidates:
        print("candidates: none")
    else:
        print("candidates:")
        for item in candidates:
            terms = item.get("observed_terms") or []
            display = terms[0] if terms else item.get("normalised_observed_text")
            print(
                "- "
                f"{item['candidate_id']} | "
                f"{display} | "
                f"observations={item['observation_count']} | "
                f"jobs={item['job_count']}"
            )

    if args.json_path:
        output = Path(args.json_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"json_report: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
