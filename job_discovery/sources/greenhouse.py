from __future__ import annotations

from typing import Any

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.text_utils import html_to_text
from .base import JobSource


class GreenhouseSource(JobSource):
    source_name = "greenhouse"
    display_name = "Greenhouse"

    def __init__(self, board: str, *, company_name: str = "", client: JsonHttpClient | None = None) -> None:
        self.board = str(board).strip()
        self.company_name = str(company_name).strip() or self.board
        self.client = client or JsonHttpClient()

    @property
    def run_key(self) -> str:
        return f"greenhouse:{self.board}"

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        self.fetch_complete = False
        if not self.board:
            return []
        data = self.client.get_json(
            f"https://api.greenhouse.io/v1/boards/{self.board}/jobs",
            params={"content": "true"},
        )
        results = data.get("jobs", []) if isinstance(data, dict) else []
        jobs: list[NormalizedJob] = []
        truncated = False
        for raw in results if isinstance(results, list) else []:
            if not isinstance(raw, dict):
                continue
            source_id = str(raw.get("id") or "").strip()
            title = str(raw.get("title") or "").strip()
            description = html_to_text(raw.get("content"))
            location_obj = raw.get("location") or {}
            location = (
                str(location_obj.get("name") or "").strip()
                if isinstance(location_obj, dict)
                else str(location_obj or "").strip()
            )
            if not source_id or not title or not description:
                continue
            company = str(raw.get("company_name") or self.company_name).strip()
            if spec.singapore_only and location and "singapore" not in location.lower():
                continue
            jobs.append(
                NormalizedJob(
                    source=self.source_name,
                    source_job_id=f"{self.board}:{source_id}",
                    source_platform="greenhouse",
                    title=title,
                    company=company,
                    description=description,
                    location=location,
                    source_url=str(raw.get("absolute_url") or "").strip(),
                    apply_url=str(raw.get("absolute_url") or "").strip(),
                    posted_at=str(raw.get("first_published") or raw.get("updated_at") or ""),
                    expires_at=str(raw.get("application_deadline") or ""),
                    raw_payload=raw,
                )
            )
            if len(jobs) >= spec.limit_per_source:
                truncated = True
                break
        self.fetch_complete = not truncated
        return jobs
