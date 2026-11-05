"""Pure, deterministic review-candidate planner for existing Job Finder data.

No filesystem, network, browser, SQLite, LLM, or subprocess effects.
This is NOT an application/submit authorization or a proof of applicant fit.
"""

from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from job_discovery.hide_filters import matching_hide_rules
RANKING_VERSION = "job-match-ranking-v1"  # Pin; native integration checks this version.


PLANNER_VERSION = "autonomous-job-agent-stage0-v1"
# These are *review-only* destinations; an action policy will be required in Stage 1.
APPROVED_HOST_SUFFIXES = (
    "mycareersfuture.gov.sg",
    "careers.gov.sg",
    "greenhouse.io",
    "greenhouse.com",
    "grnh.se",
    "lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "workable.com",
    "myworkdayjobs.com",
)


def _string(value: Any) -> str:
    return str(value or "").strip()


def _positive_id(value: Any) -> int:
    try:
        v = int(value)
        return v if v > 0 else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def _safe_https_url(value: Any, approved_hosts: tuple[str, ...]) -> tuple[str, str]:
    """Return (canonical URL, reason). Reject ambiguous or unapproved origins."""
    raw = _string(value)
    if not raw or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        return "", "missing_or_invalid_url"
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return "", "invalid_url"
    if (
        parsed.scheme.lower() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or "\\" in raw
    ):
        return "", "unsafe_url"
    host = host.lower().rstrip(".")
    if not host.isascii() or any(x not in "abcdefghijklmnopqrstuvwxyz0123456789-." for x in host):
        return "", "unsafe_url"
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return "", "unsafe_url"
    if (
        host == "localhost"
        or "." not in host
        or ".." in host
        or not any(host == root or host.endswith("." + root) for root in approved_hosts)
    ):
        return "", "unapproved_destination"
    authority = host if port is None else host + ":443"
    normalized = urlunsplit(("https", authority, parsed.path or "/", parsed.query, ""))
    return normalized, ""


def _url_for_job(job: Mapping[str, Any], approved_hosts: tuple[str, ...]) -> tuple[str, str]:
    # Prefer the actual application URL only if its destination is approved.
    # A safe source URL is a review page, not necessarily an application form.
    apply_url = _string(job.get("apply_url"))
    source_url = _string(job.get("source_url"))
    if apply_url:
        approved, reason = _safe_https_url(apply_url, approved_hosts)
        if approved:
            return approved, ""
        if source_url:
            fallback, _ = _safe_https_url(source_url, approved_hosts)
            if fallback:
                return fallback, "apply_destination_unapproved_using_source"
        return "", reason
    if source_url:
        return _safe_https_url(source_url, approved_hosts)
    return "", "missing_or_invalid_url"


def _expired(value: Any, now: datetime) -> bool:
    raw = _string(value)
    if not raw:
        return False
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False  # Unknown expiry is not evidence of expiration.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc) < now


def _identical_snapshot(
    job: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    evidence_fingerprint: str,
    versions: Mapping[str, str],
) -> bool:
    """Fail closed unless all persisted match identity components agree."""
    snapshot = state.get("snapshot")
    if state.get("status") != "current" or not isinstance(snapshot, dict):
        return False
    expected = {
        "discovered_job_id": _positive_id(job.get("id")),
        "job_content_hash": _string(job.get("content_hash")),
        "evidence_fingerprint": _string(evidence_fingerprint),
        "match_version": _string(versions.get("match_version")),
        "scoring_version": _string(versions.get("scoring_version")),
        "taxonomy_version": _string(versions.get("taxonomy_version")),
    }
    if any(not value for value in expected.values()):
        return False
    for name, value in expected.items():
        if name == "discovered_job_id":
            if _positive_id(snapshot.get(name)) != value:
                return False
        elif _string(snapshot.get(name)) != value:
            return False
    return True


def _draft_row(job: Mapping[str, Any], id_value: int) -> dict[str, Any]:
    return {
        "discovered_job_id": id_value,
        "source": _string(job.get("source")),
        "source_job_id": _string(job.get("source_job_id")),
        "company": _string(job.get("company")),
        "title": _string(job.get("title")),
        "status": "hold",
        "reason_codes": [],
        "review_url": "",
        "deterministic_alignment_score": None,
        "important_gap_count": None,
        "match_snapshot_id": None,
    }


def plan_jobs(
    jobs: Iterable[dict[str, Any]],
    match_states: Mapping[int, dict[str, Any]],
    *,
    evidence_fingerprint: str,
    versions: Mapping[str, str],
    evidence_item_count: int,
    hide_rules: Iterable[dict[str, Any]] = (),
    max_candidates: int = 25,
    now_utc: datetime | None = None,
    approved_hosts: tuple[str, ...] = APPROVED_HOST_SUFFIXES,
    ranking_sort_key: Callable[..., tuple[Any, ...]] | None = None,
) -> dict[str, Any]:
    """Simulate a stable, fail-closed job review queue with no side effects.

    `ranking_eligible` measures taxonomy/score reliability, not candidate fit.
    No application tasks are persisted, executed, or approved by this output.
    """
    if not isinstance(max_candidates, int) or not 0 <= max_candidates <= 1000:
        raise ValueError("max_candidates must be an integer from 0 to 1000")
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)
    rules = tuple(hide_rules)
    if ranking_sort_key is None:
        # Actual execution reuses the native Job Finder ranker. Tests can
        # inject a trivial key without loading the entire scorer package.
        from job_discovery.match_ranking import RANKING_VERSION as native_version, best_match_sort_key
        if native_version != RANKING_VERSION:
            raise ValueError("Native Job Finder ranking contract changed")
        ranking_sort_key = best_match_sort_key
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_identities: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()
    rank_keys: dict[int, tuple[Any, ...]] = {}

    for job in jobs:
        if not isinstance(job, dict):
            continue
        jid = _positive_id(job.get("id"))
        row = _draft_row(job, jid)
        reasons = row["reason_codes"]
        source_identity = (_string(job.get("source")).casefold(), _string(job.get("source_job_id")).casefold())
        if jid == 0 or not all(source_identity) or not row["title"]:
            row["status"] = "reject"
            reasons.append("invalid_job_identity")
            rows.append(row)
            continue
        if jid in seen_ids or source_identity in seen_identities:
            row["status"] = "skip"
            reasons.append("duplicate_job_identity")
            rows.append(row)
            continue
        seen_ids.add(jid)
        seen_identities.add(source_identity)

        lifecycle = _string(job.get("lifecycle_status")).lower()
        if lifecycle not in {"", "active"}:
            reasons.append("job_not_active")
        if _expired(job.get("expires_at"), now):
            reasons.append("job_expired")
        if not _string(job.get("content_hash")) or len(_string(job.get("description"))) < 100:
            reasons.append("insufficient_job_content")
        if matching_hide_rules(job, rules):
            reasons.append("hidden_by_job_finder_rule")

        url, url_warning = _url_for_job(job, approved_hosts)
        row["review_url"] = url
        if not url:
            reasons.append(url_warning)
        if url_warning and url:
            reasons.append(url_warning)

        if evidence_item_count <= 0 or not evidence_fingerprint:
            reasons.append("no_current_evidence")
        state = match_states.get(jid) or {}
        status = _string(state.get("status")).lower()
        if status != "current":
            reasons.append("match_" + (status if status in {"stale", "none"} else "not_current"))
        elif not _identical_snapshot(job, state, evidence_fingerprint=evidence_fingerprint, versions=versions):
            reasons.append("snapshot_identity_mismatch")
        else:
            snap = state["snapshot"]
            summary = snap.get("summary") if isinstance(snap.get("summary"), dict) else {}
            row["match_snapshot_id"] = _positive_id(snap.get("id")) or None
            row["deterministic_alignment_score"] = summary.get("deterministic_alignment_score")
            row["important_gap_count"] = summary.get("important_gap_count")
            if summary.get("ranking_eligible") is not True:
                reasons.append("ranking_not_eligible")
            if _string(summary.get("ranking_version")) != RANKING_VERSION:
                reasons.append("ranking_version_mismatch")
            if not reasons or reasons == ["apply_destination_unapproved_using_source"]:
                rank_keys[jid] = ranking_sort_key(
                    snap,
                    discovered_job_id=jid,
                )
                row["status"] = "review_candidate"

        if row["status"] == "review_candidate" and url in seen_urls:
            row["status"] = "skip"
            rank_keys.pop(jid, None)
            reasons.append("duplicate_review_url")
        if row["status"] == "review_candidate":
            seen_urls.add(url)
        if row["status"] not in {"review_candidate", "skip"}:
            if any(code in {"missing_or_invalid_url", "invalid_url", "unsafe_url", "unapproved_destination", "invalid_job_identity"} for code in reasons):
                row["status"] = "reject"
            else:
                row["status"] = "hold"
        rows.append(row)

    # Candidate ordering reuses the existing Job Finder Best Match sort key.
    candidates = sorted(
        (row for row in rows if row["status"] == "review_candidate"),
        key=lambda row: rank_keys[row["discovered_job_id"]],
        reverse=True,
    )
    for candidate in candidates[max_candidates:]:
        candidate["status"] = "hold"
        candidate["reason_codes"].append("review_queue_limit")
    kept = candidates[:max_candidates]
    held = [row for row in rows if row["status"] == "hold"]
    rejected = [row for row in rows if row["status"] == "reject"]
    skipped = [row for row in rows if row["status"] == "skip"]
    counts = {"review_candidate": len(kept), "hold": len(held), "reject": len(rejected), "skip": len(skipped)}
    return {
        "planner_version": PLANNER_VERSION,
        "dry_run": True,
        "no_application_actions": True,
        "as_of_utc": now.isoformat(),
        "counts": counts,
        "rows": kept + held + rejected + skipped,
        "warnings": [
            "Ranking eligibility does not establish applicant suitability.",
            "Review candidates are NOT approved application tasks.",
            "Stage 0 does not check already-submitted applications across the application tracker.",
        ],
    }
