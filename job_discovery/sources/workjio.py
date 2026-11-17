from __future__ import annotations

import re
from urllib.parse import urlsplit

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.public_html import (
    document_title,
    extract_links,
    first_h1,
    section_lines,
    visible_lines,
)
from job_discovery.text_utils import matches_query
from .base import JobSource


class WorkJioSource(JobSource):
    """Public WorkJio part-time list/detail adapter."""

    source_name = "workjio"
    display_name = "WorkJio"
    fetch_complete = False
    BASE_URL = "https://www.workjio.com"
    LIST_URL = f"{BASE_URL}/part-time-jobs"
    _DETAIL_PATH_RE = r"^/jobs/[a-z0-9][a-z0-9-]*$"

    def __init__(
        self,
        *,
        client: JsonHttpClient | None = None,
        delay_seconds: float = 0.35,
    ) -> None:
        self.client = client or JsonHttpClient()
        self.delay_seconds = float(delay_seconds)

    @staticmethod
    def _salary(lines: list[str]) -> tuple[float | None, float | None, str]:
        for index, line in enumerate(lines):
            if line.casefold() != "salary":
                continue
            nearby = " ".join(lines[index + 1:index + 4])
            match = re.search(
                r"S\$\s*([\d,.]+)(?:\s*(?:-|–|to)\s*([\d,.]+))?",
                nearby,
                re.IGNORECASE,
            )
            if not match:
                return None, None, ""
            low = float(match.group(1).replace(",", ""))
            high = float(match.group(2).replace(",", "")) if match.group(2) else low
            lowered = nearby.casefold()
            period = (
                "hour" if "per hour" in lowered
                else "month" if "per month" in lowered
                else "day" if "per day" in lowered
                else ""
            )
            return low, high, period
        return None, None, ""

    @staticmethod
    def _value_after(lines: list[str], marker: str) -> str:
        for index, line in enumerate(lines):
            if line.casefold() == marker.casefold():
                for candidate in lines[index + 1:index + 4]:
                    if candidate.strip():
                        return candidate.strip()
        return ""

    @staticmethod
    def _company_from_title(page_title: str) -> str:
        match = re.search(
            r"\bjob at\s+(.+?),\s*Singapore\b",
            page_title,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""

    @classmethod
    def normalize_html(cls, url: str, html: str) -> NormalizedJob | None:
        if not re.search(cls._DETAIL_PATH_RE, urlsplit(url).path, re.IGNORECASE):
            return None
        lines = visible_lines(html)
        title = first_h1(html)
        if not title:
            return None
        company = cls._company_from_title(document_title(html))
        location = cls._value_after(lines, "Where")
        if not location or location.casefold() == "location not stated":
            location = "Singapore"
        salary_min, salary_max, salary_period = cls._salary(lines)
        description = "\n".join(
            section_lines(
                lines,
                start_markers=("About the role",),
                stop_markers=(
                    "Jio can write this application for you",
                    "Apply on the company website",
                    "Quick apply",
                    "More jobs like this",
                ),
            )
        ).strip()
        if len(description) < 80:
            return None
        listing_id = ""
        for line in lines:
            match = re.search(r"\bListing ID\s+(\d+)\b", line, re.IGNORECASE)
            if match:
                listing_id = match.group(1)
                break
        if not listing_id:
            listing_id = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]

        return NormalizedJob(
            source=cls.source_name,
            source_job_id=listing_id,
            source_platform="workjio",
            title=title,
            company=company or "Unknown Company",
            description=description,
            location=location,
            source_url=url,
            apply_url=url,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="SGD" if salary_min is not None else "",
            salary_period=salary_period,
            employment_type="Part-time",
            raw_payload={
                "public_url": url,
                "adapter": "workjio-public-html-v1",
            },
        ).validate()

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        # WorkJio currently exposes a dedicated public part-time index.
        # Do not probe undocumented query-parameter pagination endpoints:
        # Vercel may challenge automated requests, and a challenge should
        # remain an explicit source error rather than being treated as
        # a successful empty result.
        html = self.client.get_text(self.LIST_URL)
        detail_urls: list[str] = []
        seen: set[str] = set()

        for url, _label in extract_links(
            html,
            base_url=self.BASE_URL,
            path_pattern=self._DETAIL_PATH_RE,
        ):
            if url in seen:
                continue
            seen.add(url)
            detail_urls.append(url)
            if len(detail_urls) >= spec.limit_per_source:
                break

        jobs: list[NormalizedJob] = []
        for index, url in enumerate(detail_urls):
            normalized = self.normalize_html(url, self.client.get_text(url))
            if normalized is None:
                continue
            if matches_query(
                spec.query,
                normalized.title,
                normalized.company,
                normalized.description,
                normalized.location,
            ):
                jobs.append(normalized)
            if index + 1 < len(detail_urls):
                self.client.pause(self.delay_seconds)

        self.fetch_complete = False
        return jobs
