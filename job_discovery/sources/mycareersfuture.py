from __future__ import annotations

from typing import Any

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.text_utils import join_sections, list_text, matches_query
from .base import JobSource


class MyCareersFutureSource(JobSource):
    """MyCareersFuture website JSON adapter.

    MCF does not publish this website endpoint as a stable third-party developer
    API. Keep it isolated here so endpoint/schema changes cannot leak into the
    rest of Job AI Helper.
    """

    source_name = "mycareersfuture"
    display_name = "MyCareersFuture"
    BASE_URL = "https://api.mycareersfuture.gov.sg/v2/jobs"

    def __init__(self, *, client: JsonHttpClient | None = None, delay_seconds: float = 1.5) -> None:
        self.client = client or JsonHttpClient()
        self.delay_seconds = float(delay_seconds)

    @staticmethod
    def _company(raw: dict[str, Any]) -> str:
        posted = raw.get("postedCompany") or raw.get("company") or {}
        if isinstance(posted, dict):
            return str(posted.get("name") or posted.get("companyName") or "").strip()
        return str(posted or "").strip()

    @staticmethod
    def _location(raw: dict[str, Any]) -> str:
        direct = str(raw.get("addressFormatted") or raw.get("location") or "").strip()
        if direct:
            return direct
        address = raw.get("address") or {}
        if isinstance(address, dict):
            return str(
                address.get("location")
                or address.get("addressFormatted")
                or address.get("postalCode")
                or ""
            ).strip()
        return "Singapore"

    @staticmethod
    def _salary(raw: dict[str, Any]) -> tuple[float | None, float | None, str, str]:
        salary = raw.get("salary") or {}
        if not isinstance(salary, dict):
            return None, None, "SGD", ""

        def number(value: Any) -> float | None:
            try:
                return float(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                return None

        currency = str(salary.get("currency") or salary.get("currencyCode") or "SGD")
        period = list_text(salary.get("type") or salary.get("period") or salary.get("salaryType"))
        return number(salary.get("minimum")), number(salary.get("maximum")), currency, period

    @classmethod
    def normalize(cls, raw: dict[str, Any]) -> NormalizedJob | None:
        source_id = str(raw.get("uuid") or raw.get("id") or "").strip()
        title = str(raw.get("title") or raw.get("jobTitle") or "").strip()
        if not source_id or not title:
            return None

        company = cls._company(raw)
        location = cls._location(raw) or "Singapore"
        description = join_sections(
            [
                ("", raw.get("description") or raw.get("jobDescription")),
                ("Responsibilities", raw.get("responsibilities")),
                ("Requirements", raw.get("requirements")),
            ]
        )
        if not description:
            return None

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        posted_at = str(
            metadata.get("createdAt")
            or raw.get("postedDate")
            or raw.get("createdAt")
            or ""
        )
        expires_at = str(
            raw.get("expiryDate")
            or raw.get("closingDate")
            or metadata.get("expiryDate")
            or ""
        )
        employment = list_text(raw.get("employmentTypes") or raw.get("employmentType"))
        seniority = list_text(raw.get("positionLevels") or raw.get("positionLevel"))
        salary_min, salary_max, currency, period = cls._salary(raw)
        external = str(raw.get("externalLink") or "").strip()
        source_url = external or f"https://www.mycareersfuture.gov.sg/job/{source_id}"

        return NormalizedJob(
            source=cls.source_name,
            source_job_id=source_id,
            source_platform="mcf",
            title=title,
            company=company or "Unknown Company",
            description=description,
            location=location,
            source_url=source_url,
            apply_url=external,
            posted_at=posted_at,
            expires_at=expires_at,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            employment_type=employment,
            seniority=seniority,
            raw_payload=raw,
        )

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        page_size = max(1, min(int(spec.page_size), 100))
        jobs: list[NormalizedJob] = []
        seen: set[str] = set()

        for page in range(max(1, int(spec.max_pages))):
            data = self.client.get_json(
                self.BASE_URL,
                params={
                    "search": spec.query.strip(),
                    "limit": page_size,
                    "page": page,
                },
                headers={
                    "Origin": "https://www.mycareersfuture.gov.sg",
                    "Referer": "https://www.mycareersfuture.gov.sg/",
                },
            )
            results = data.get("results", []) if isinstance(data, dict) else []
            if not isinstance(results, list) or not results:
                break

            for raw in results:
                if not isinstance(raw, dict):
                    continue
                job = self.normalize(raw)
                if job is None or job.source_job_id in seen:
                    continue
                if not matches_query(spec.query, job.title, job.company, job.description):
                    continue
                seen.add(job.source_job_id)
                jobs.append(job)
                if len(jobs) >= spec.limit_per_source:
                    return jobs

            if len(results) < page_size:
                break
            self.client.pause(self.delay_seconds)

        return jobs
