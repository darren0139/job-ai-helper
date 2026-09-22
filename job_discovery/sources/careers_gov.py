from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.text_utils import join_sections, matches_query
from .base import JobSource


class CareersGovSource(JobSource):
    source_name = "careers_gov"
    display_name = "Careers@Gov"
    DATA_URL = (
        "https://raw.githubusercontent.com/opengovsg/"
        "careersgovsg-jobs-data/main/data/job-listings.json"
    )

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient(timeout=45.0)

    @staticmethod
    def _millis_to_iso(value: Any) -> str:
        try:
            if value in (None, ""):
                return ""
            number = float(value)
            if number <= 0:
                return ""
            return datetime.fromtimestamp(number / 1000.0, tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return ""

    @staticmethod
    def _url(raw: dict[str, Any]) -> str:
        platform = str(raw.get("platform") or "").strip()
        job_id = str(raw.get("jobId") or "").strip()
        posting = str(raw.get("postingNo") or "").strip()
        if platform == "workable" and posting:
            return f"https://apply.workable.com/j/{posting}"
        if platform == "greenhouse" and job_id:
            return f"https://jobs.careers.gov.sg/jobs/greenhouse/{job_id}?gh_jid={job_id}"
        if platform and job_id and posting:
            return f"https://jobs.careers.gov.sg/jobs/{platform}/{job_id}/{posting}"
        if platform and job_id:
            return f"https://jobs.careers.gov.sg/jobs/{platform}/{job_id}"
        return "https://jobs.careers.gov.sg/"

    @classmethod
    def normalize(cls, raw: dict[str, Any]) -> NormalizedJob | None:
        platform = str(raw.get("platform") or "").strip()
        job_id = str(raw.get("jobId") or "").strip()
        posting = str(raw.get("postingNo") or "").strip()
        source_id = ":".join(part for part in (platform, job_id, posting) if part)
        title = str(raw.get("jobTitle") or "").strip()
        if not source_id or not title:
            return None

        description = join_sections(
            [
                ("", raw.get("jobDescription")),
                ("Responsibilities", raw.get("jobResponsibilities")),
                ("Requirements", raw.get("jobRequirements")),
            ]
        )
        if not description:
            return None

        def number(value: Any) -> float | None:
            try:
                return float(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                return None

        return NormalizedJob(
            source=cls.source_name,
            source_job_id=source_id,
            source_platform=platform,
            title=title,
            company=str(raw.get("agency") or "Singapore Public Service").strip(),
            description=description,
            location=str(raw.get("location") or "Singapore").strip() or "Singapore",
            source_url=cls._url(raw),
            apply_url=cls._url(raw),
            posted_at=cls._millis_to_iso(raw.get("startDate")),
            expires_at=cls._millis_to_iso(raw.get("closingDate")),
            employment_type=str(raw.get("employmentType") or "").strip(),
            seniority=str(raw.get("experienceRequired") or "").strip(),
            experience_years_min=number(raw.get("experienceYearsMin")),
            experience_years_max=number(raw.get("experienceYearsMax")),
            raw_payload=raw,
        )

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        data = self.client.get_json(self.DATA_URL)
        if not isinstance(data, list):
            return []
        jobs: list[NormalizedJob] = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            job = self.normalize(raw)
            if job is None:
                continue
            if not matches_query(
                spec.query,
                job.title,
                job.company,
                job.description,
                raw.get("field"),
                raw.get("functionalArea"),
            ):
                continue
            jobs.append(job)
            if len(jobs) >= spec.limit_per_source:
                break
        return jobs
