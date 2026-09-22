from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.text_utils import html_to_text
from .base import JobSource


class AshbySource(JobSource):
    source_name = "ashby"
    display_name = "Ashby"

    def __init__(self, board: str, *, company_name: str = "", client: JsonHttpClient | None = None) -> None:
        self.board = str(board).strip()
        self.company_name = str(company_name).strip() or self.board
        self.client = client or JsonHttpClient()

    @property
    def run_key(self) -> str:
        return f"ashby:{self.board}"

    @staticmethod
    def _salary(comp: Any) -> tuple[float | None, float | None, str, str]:
        if not isinstance(comp, dict):
            return None, None, "", ""
        for item in comp.get("summaryComponents", []) or []:
            if isinstance(item, dict) and item.get("compensationType") == "Salary":
                return (
                    item.get("minValue"),
                    item.get("maxValue"),
                    str(item.get("currencyCode") or ""),
                    str(item.get("interval") or ""),
                )
        return None, None, "", ""

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        self.fetch_complete = False
        if not self.board:
            return []
        data = self.client.get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{self.board}",
            params={"includeCompensation": "true"},
        )
        results = data.get("jobs", []) if isinstance(data, dict) else []
        jobs: list[NormalizedJob] = []
        truncated = False
        for raw in results if isinstance(results, list) else []:
            if not isinstance(raw, dict) or raw.get("isListed") is False:
                continue
            title = str(raw.get("title") or "").strip()
            description = str(raw.get("descriptionPlain") or "").strip() or html_to_text(raw.get("descriptionHtml"))
            location = str(raw.get("location") or "").strip()
            if not title or not description:
                continue
            if spec.singapore_only:
                locations = [location]
                for item in raw.get("secondaryLocations", []) or []:
                    if isinstance(item, dict):
                        locations.append(str(item.get("location") or ""))
                if any(locations) and not any("singapore" in item.lower() for item in locations):
                    continue
            job_url = str(raw.get("jobUrl") or "").strip()
            source_id = job_url.rstrip("/").split("/")[-1] if job_url else ""
            if not source_id:
                source_id = str(raw.get("id") or "").strip()
            if not source_id:
                continue
            salary_min, salary_max, currency, period = self._salary(raw.get("compensation"))
            jobs.append(
                NormalizedJob(
                    source=self.source_name,
                    source_job_id=f"{self.board}:{source_id}",
                    source_platform="ashby",
                    title=title,
                    company=self.company_name,
                    description=description,
                    location=location,
                    source_url=job_url,
                    apply_url=str(raw.get("applyUrl") or "").strip(),
                    posted_at=str(raw.get("publishedAt") or ""),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=currency,
                    salary_period=period,
                    employment_type=str(raw.get("employmentType") or ""),
                    seniority=str(raw.get("workplaceType") or ""),
                    raw_payload=raw,
                )
            )
            if len(jobs) >= spec.limit_per_source:
                truncated = True
                break
        self.fetch_complete = not truncated
        return jobs
