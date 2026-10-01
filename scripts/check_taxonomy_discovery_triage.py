from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.taxonomy_discovery_review_manager import save_review
from taxonomy_discovery.triage import (
    TRIAGE_STATUSES,
    TRIAGE_VERSION,
    build_triage_report,
)


def _candidate_text(candidate: dict) -> str:
    terms = candidate.get("observed_terms", []) or []
    if terms:
        return str(terms[0])
    return str(candidate.get("normalised_observed_text") or "")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or review deterministic TQ-D2.5 taxonomy-discovery triage. "
            "No model, Tavily, or taxonomy mutation is performed."
        )
    )
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--status",
        choices=TRIAGE_STATUSES,
        help="Filter --list output to one triage status.",
    )
    parser.add_argument("--review-candidate")
    parser.add_argument(
        "--set-status",
        choices=TRIAGE_STATUSES,
    )
    parser.add_argument("--target-capability-id")
    parser.add_argument("--notes", default="")
    parser.add_argument("--review-db")
    args = parser.parse_args()

    report = build_triage_report(review_db_path=args.review_db)

    if args.review_candidate:
        if not args.set_status:
            parser.error("--review-candidate requires --set-status")

        candidate = next(
            (
                row
                for row in report.get("candidates", []) or []
                if row.get("candidate_id") == args.review_candidate
            ),
            None,
        )
        if candidate is None:
            parser.error(
                f"Unknown candidate_id: {args.review_candidate}"
            )

        save_review(
            candidate_id=args.review_candidate,
            taxonomy_version=str(
                candidate.get("taxonomy_version")
                or report.get("taxonomy_version")
                or ""
            ),
            triage_status=args.set_status,
            target_capability_id=args.target_capability_id,
            notes=args.notes,
            db_path=args.review_db,
        )
        report = build_triage_report(review_db_path=args.review_db)

    summary = {
        "triage_version": TRIAGE_VERSION,
        "discovery_version": report.get("discovery_version"),
        "match_version": report.get("match_version"),
        "scoring_version": report.get("scoring_version"),
        "taxonomy_version": report.get("taxonomy_version"),
        "snapshot_count": report.get("snapshot_count"),
        "candidate_count": report.get("candidate_count"),
        "reviewed_candidate_count": report.get("reviewed_candidate_count"),
        "unreviewed_candidate_count": report.get(
            "unreviewed_candidate_count"
        ),
        "triage_status_counts": report.get("triage_status_counts"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.list:
        print()
        for candidate in report.get("candidates", []) or []:
            triage = candidate.get("triage", {}) or {}
            status = triage.get("status") or "unreviewed"
            if args.status and status != args.status:
                continue
            flags = ",".join(candidate.get("diagnostic_flags", []) or [])
            print(
                f"{candidate.get('candidate_id')} | {status} | "
                f"{_candidate_text(candidate)}"
            )
            if flags:
                print(f"  flags: {flags}")
            target = triage.get("target_capability_id")
            if target:
                print(f"  target: {target}")

    if args.json_path:
        destination = Path(args.json_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\njson: {destination}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
