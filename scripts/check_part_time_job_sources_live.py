"""Optional live network smoke for part-time Job Finder sources."""

from __future__ import annotations

import os

from job_discovery.http_client import JobSourceError
from job_discovery.models import SearchSpec
from job_discovery.sources.fastjobs import FastJobsSource
from job_discovery.sources.staffie import StaffieSource
from job_discovery.sources.workjio import WorkJioSource


def _print_jobs(label: str, jobs) -> None:
    print(f"[PASS] {label}: {len(jobs)} row(s)")
    for job in jobs[:3]:
        print(f"  - {job.title} @ {job.company}")


def main() -> int:
    spec = SearchSpec(query="", max_pages=1, page_size=20, limit_per_source=5)
    failures = 0

    try:
        workjio_jobs = WorkJioSource(delay_seconds=0).fetch(spec)
    except JobSourceError as exc:
        message = str(exc)
        if "HTTP 429" in message or "Security Checkpoint" in message:
            print(
                "[BLOCKED] WorkJio: public page is protected by a "
                "Vercel/security checkpoint for this direct HTTP client."
            )
            print(
                "          This smoke test will not bypass the checkpoint; "
                "Job Finder will surface the source error and other sources "
                "can continue."
            )
        else:
            failures += 1
            print(f"[FAIL] WorkJio: {exc}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] WorkJio: {exc}")
    else:
        _print_jobs("WorkJio", workjio_jobs)

    try:
        staffie_jobs = StaffieSource().fetch(spec)
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Staffie: {exc}")
    else:
        _print_jobs("Staffie public sample", staffie_jobs)

    fastjobs_url = str(os.getenv("FASTJOBS_START_URL") or "").strip()
    if fastjobs_url:
        try:
            fastjobs_jobs = FastJobsSource(
                [fastjobs_url],
                delay_seconds=0,
            ).fetch(spec)
        except JobSourceError as exc:
            message = str(exc)
            if (
                "HTTP 403" in message
                or "Just a moment" in message
                or "Cloudflare" in message
                or "challenges.cloudflare.com" in message
            ):
                print(
                    "[BLOCKED] FastJobs: public page is protected by a "
                    "Cloudflare/security challenge for this direct HTTP client."
                )
                print(
                    "          This smoke test will not bypass the challenge; "
                    "use browser-assisted capture for FastJobs."
                )
            else:
                failures += 1
                print(f"[FAIL] FastJobs: {exc}")
        except Exception as exc:
            failures += 1
            print(f"[FAIL] FastJobs: {exc}")
        else:
            _print_jobs("FastJobs", fastjobs_jobs)
    else:
        print(
            "[SKIP] FastJobs: set FASTJOBS_START_URL to a public "
            "FastJobs job URL."
        )

    if failures:
        print(f"PART-TIME SOURCE LIVE SMOKE: FAIL ({failures} source error(s))")
        return 1

    print("PART-TIME SOURCE LIVE SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
