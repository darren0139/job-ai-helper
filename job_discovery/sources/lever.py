from __future__ import annotations

from typing import Any

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.text_utils import html_to_text, join_sections
from .base import JobSource


class LeverSource(JobSource):
    source_name = "lever"
    display_name = "Lever"

    def __init__(self, site: str, *, company_name: str = "", client: JsonHttpClient | None = None) -> None:
        self.site = str(site).strip()
        self.company_name = str(company_name).strip() or self.site
        self.client = client or JsonHttpClient()

    @property
    def run_key(self) -> str:
        return f"lever:{self.site}"

    @staticmethod
    def _list_content(raw: dict[str, Any]) -> str:
        sections: list[tuple[str, Any]] = []
        for item in raw.get("lists", []) or []:
            if not isinstance(item, dict):
                continue
            sections.append((str(item.get("text") or ""), item.get("content")))
        return join_sections(sections)

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        self.fetch_complete = False
        if not self.site:
            return []
        jobs: list[NormalizedJob] = []
        skip = 0
        page_size = max(1, min(spec.page_size, 100))
        for _ in range(max(1, spec.max_pages)):
            data = self.client.get_json(
                f"https://api.lever.co/v0/postings/{self.site}",
                params={"mode": "json", "skip": skip, "limit": page_size},
            )
            if not isinstance(data, list) or not data:
                self.fetch_complete = True
                break
            for raw in data:
                if not isinstance(raw, dict):
                    continue
                source_id = str(raw.get("id") or "").strip()
                title = str(raw.get("text") or raw.get("title") or "").strip()
                categories = raw.get("categories") or {}
                location = (
                    str(categories.get("location") or "").strip()
                    if isinstance(categories, dict)
                    else ""
                )
                description = join_sections(
                    [
                        ("", raw.get("descriptionPlain") or html_to_text(raw.get("description"))),
                        ("", self._list_content(raw)),
                        ("Additional information", raw.get("additionalPlain") or html_to_text(raw.get("additional"))),
                    ]
                )
                if not source_id or not title or not description:
                    continue
                if spec.singapore_only and location and "singapore" not in location.lower():
                    continue
                salary = raw.get("salaryRange") or {}
                jobs.append(
                    NormalizedJob(
                        source=self.source_name,
                        source_job_id=f"{self.site}:{source_id}",
                        source_platform="lever",
                        title=title,
                        company=self.company_name,
                        description=description,
                        location=location,
                        source_url=str(raw.get("hostedUrl") or raw.get("applyUrl") or ""),
                        apply_url=str(raw.get("applyUrl") or ""),
                        posted_at=str(raw.get("createdAt") or ""),
                        salary_min=salary.get("min") if isinstance(salary, dict) else None,
                        salary_max=salary.get("max") if isinstance(salary, dict) else None,
                        salary_currency=str(salary.get("currency") or "") if isinstance(salary, dict) else "",
                        salary_period=str(salary.get("interval") or "") if isinstance(salary, dict) else "",
                        employment_type=str(categories.get("commitment") or "") if isinstance(categories, dict) else "",
                        raw_payload=raw,
                    )
                )
                if len(jobs) >= spec.limit_per_source:
                    self.fetch_complete = False
                    return jobs
            if len(data) < page_size:
                self.fetch_complete = True
                break
            skip += page_size
            self.client.pause(0.5)
        return jobs
