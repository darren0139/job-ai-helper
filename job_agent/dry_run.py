"""Read-only SQLite adapter and CLI for the Stage 0 simulated review queue.

Usage (repository root): python -m job_agent.dry_run --db data/applications.db
No schema migration, database write, HTTP request, browser action or model call.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .planner import plan_jobs


def _read_only_connection(path: str | Path) -> sqlite3.Connection:
    db = Path(path).expanduser().resolve(strict=True)
    if not db.is_file():
        raise FileNotFoundError(f"Not a database file: {db}")
    connection = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def read_job_finder_states(
    db_path: str | Path,
    *,
    evidence_fingerprint: str,
    versions: Mapping[str, str],
    max_jobs: int = 250,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, Any]]]:
    """Read persisted jobs, current-or-stale snapshots and enabled hide rules.

    Reads summary-only snapshot fields. A missing snapshot is "none"; an
    incompatible snapshot is "stale". All connections are mode=ro.
    """
    if not isinstance(max_jobs, int) or not 1 <= max_jobs <= 5000:
        raise ValueError("max_jobs must be an integer from 1 to 5000")
    conn = _read_only_connection(db_path)
    try:
        if not _table_exists(conn, "discovered_jobs"):
            raise ValueError("discovered_jobs table is not available")
        jobs = [dict(r) for r in conn.execute(
            # Prioritize potentially actionable records before bounded sampling;
            # preserve last_seen_at/id order within each lifecycle category.
            # The planner still independently checks actual expiry timestamps.
            "SELECT * FROM discovered_jobs "
            "ORDER BY CASE WHEN LOWER(TRIM(COALESCE(lifecycle_status, ''))) "
            "IN ('', 'active') THEN 0 ELSE 1 END, "
            "last_seen_at DESC, id DESC LIMIT ?",
            (max_jobs,),
        ).fetchall()]
        hidden = []
        if _table_exists(conn, "job_discovery_hide_rules"):
            hidden = [dict(r) for r in conn.execute(
                "SELECT * FROM job_discovery_hide_rules WHERE enabled = 1 ORDER BY id ASC"
            ).fetchall()]
        states: dict[int, dict[str, Any]] = {int(j["id"]): {"status": "none"} for j in jobs}
        if not jobs or not _table_exists(conn, "job_match_snapshots"):
            return jobs, states, hidden
        for start in range(0, len(jobs), 700):
            chunk = jobs[start:start + 700]
            ids = [int(j["id"]) for j in chunk]
            placeholders = ",".join("?" for _ in ids)
            snapshots = conn.execute(
                "SELECT id,discovered_job_id,job_content_hash,evidence_fingerprint,"
                "match_version,scoring_version,taxonomy_version,summary_json "
                f"FROM job_match_snapshots WHERE discovered_job_id IN ({placeholders}) "
                "ORDER BY id DESC",
                ids,
            ).fetchall()
            by_job = {int(job["id"]): job for job in chunk}
            for row in snapshots:
                snap = dict(row)
                jid = int(snap["discovered_job_id"])
                if states[jid].get("status") == "current":
                    continue
                try:
                    snap["summary"] = json.loads(snap.pop("summary_json") or "{}")
                except (ValueError, TypeError):
                    snap["summary"] = {}
                if not isinstance(snap["summary"], dict):
                    snap["summary"] = {}
                job = by_job[jid]
                identity_matches = all((
                    str(snap.get(field) or "") == str(expected or "")
                    for field, expected in (
                        ("job_content_hash", job.get("content_hash")),
                        ("evidence_fingerprint", evidence_fingerprint),
                        ("match_version", versions.get("match_version")),
                        ("scoring_version", versions.get("scoring_version")),
                        ("taxonomy_version", versions.get("taxonomy_version")),
                    )
                ))
                if identity_matches:
                    states[jid] = {"status": "current", "snapshot": snap}
                elif states[jid]["status"] == "none":
                    states[jid] = {"status": "stale"}
        return jobs, states, hidden
    finally:
        conn.close()


def current_profile_identity(db_path: str | Path) -> tuple[str, int, dict[str, str]]:
    """Reuse canonical Profile & Evidence fingerprint and version contract.

    Specifically selects the existing read_only=True evidence query; never
    calls the regular profile-library schema-creating code path.
    """
    from database.user_profile_manager import get_all_evidence_items_for_snapshot
    from job_discovery.matching import build_profile_evidence_context, current_match_versions

    evidence = get_all_evidence_items_for_snapshot(read_only=True, db_path=db_path)
    context = build_profile_evidence_context(evidence)
    return (
        str(context.get("evidence_fingerprint") or ""),
        int(context.get("evidence_item_count") or 0),
        current_match_versions(),
    )


def build_read_only_plan(
    db_path: str | Path,
    *,
    max_jobs: int = 250,
    max_candidates: int = 25,
    now_utc: datetime | None = None,
    ranking_sort_key: Callable[..., tuple[Any, ...]] | None = None,
) -> dict[str, Any]:
    fingerprint, evidence_count, versions = current_profile_identity(db_path)
    jobs, states, hide_rules = read_job_finder_states(
        db_path,
        evidence_fingerprint=fingerprint,
        versions=versions,
        max_jobs=max_jobs,
    )
    return plan_jobs(
        jobs,
        states,
        evidence_fingerprint=fingerprint,
        evidence_item_count=evidence_count,
        versions=versions,
        hide_rules=hide_rules,
        max_candidates=max_candidates,
        now_utc=now_utc,
        ranking_sort_key=ranking_sort_key,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 0 dry-run job review queue (read-only).")
    parser.add_argument("--db", default="data/applications.db", help="Existing SQLite file; read-only")
    parser.add_argument("--max-jobs", type=int, default=250)
    parser.add_argument("--max-candidates", type=int, default=25)
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout, no file writes")
    args = parser.parse_args(argv)
    try:
        plan = build_read_only_plan(
            args.db, max_jobs=args.max_jobs, max_candidates=args.max_candidates
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"[FAILED] Stage 0 read-only plan: {exc}\n")
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print("[DRY_RUN] No database writes, browsing, model calls, or applications")
        print("[COUNTS] " + " ".join(f"{k}={v}" for k, v in plan["counts"].items()))
        for row in plan["rows"]:
            if row["status"] != "review_candidate":
                continue
            score = row["deterministic_alignment_score"]
            print(
                f"[REVIEW] job_id={row['discovered_job_id']} "
                f"source={row['source']} company={row['company']!r} "
                f"title={row['title']!r} alignment={score}"
            )
        print("[NOTE] Ranking eligible does not mean suitable to apply; review required.")
        print("[NOTE] Pass --json to inspect hold/reject reason codes (may include job URLs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
