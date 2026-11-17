from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlsplit

from job_discovery.http_client import JobSourceError, JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.public_html import (
    document_title,
    extract_links,
    first_h1,
    visible_lines,
)
from job_discovery.text_utils import matches_query
from .base import JobSource


class FastJobsSource(JobSource):
    """Public FastJobs page adapter; dynamic list pages fail closed."""

    source_name = "fastjobs"
    display_name = "FastJobs"
    fetch_complete = False
    PART_TIME_URL = (
        "https://www.fastjobs.sg/singapore-jobs/"
        "all-categories-jobs/part-time-jobs/part-time-jobs-search/"
    )
    HOME_URL = "https://www.fastjobs.sg/"
    _DETAIL_RE = re.compile(
        r"/(?:[a-z]{2}/)?singapore-job-ad/(\d+)(?:/|$)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        start_urls: list[str] | None = None,
        *,
        client: JsonHttpClient | None = None,
        delay_seconds: float = 0.75,
    ) -> None:
        self.start_urls = [
            str(value or "").strip()
            for value in (start_urls or [])
            if str(value or "").strip()
        ]
        self.client = client or JsonHttpClient()
        self.delay_seconds = float(delay_seconds)

    @classmethod
    def _is_detail_url(cls, url: str) -> bool:
        return bool(cls._DETAIL_RE.search(urlsplit(str(url)).path))

    @staticmethod
    def _date(value: str, prefix: str) -> str:
        text = str(value or "").strip()
        if not text.casefold().startswith(prefix.casefold()):
            return ""
        raw = text[len(prefix):].strip()
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                pass
        return ""

    @staticmethod
    def _salary(text: str) -> tuple[float | None, float | None, str]:
        match = re.search(
            r"S\$\s*([\d,.]+)"
            r"(?:\s*(?:-|–|to)\s*S?\$?\s*([\d,.]+))?"
            r"\s*(?:/|per\s+)\s*(hour|month|day)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None, None, ""
        low = float(match.group(1).replace(",", ""))
        high = float(match.group(2).replace(",", "")) if match.group(2) else low
        return low, high, match.group(3).lower()

    @classmethod
    def normalize_html(cls, url: str, html: str) -> NormalizedJob | None:
        detail_match = cls._DETAIL_RE.search(urlsplit(url).path)
        if not detail_match:
            return None
        lines = visible_lines(html)
        title = first_h1(html)
        if not title:
            return None
        text = "\n".join(lines)
        salary_min, salary_max, salary_period = cls._salary(text)

        employment_bits = [
            label
            for label in ("Part Time", "Full Time", "Contract", "Internship")
            if re.search(rf"\b{re.escape(label)}\b", text, re.IGNORECASE)
        ]

        company = ""
        for index, line in enumerate(lines):
            if line.casefold() == "about the employer":
                for candidate in lines[index + 1:index + 7]:
                    lowered = candidate.casefold()
                    if (
                        lowered in {"image", "view employer profile"}
                        or lowered.startswith("brn/uen:")
                        or "responds in" in lowered
                    ):
                        continue
                    company = candidate
                    break
                break
        if not company:
            match = re.search(
                r"\bin Singapore\s*-\s*(.+?)\s*\|\s*FastJobs",
                document_title(html),
                re.IGNORECASE,
            )
            if match:
                company = match.group(1).strip()

        location = "Singapore"
        for line in lines[:30]:
            lowered = line.casefold()
            if (
                line != title
                and any(
                    marker in lowered
                    for marker in (" mrt", " region", ", singapore")
                )
            ):
                location = line
                break

        posted_at = ""
        expires_at = ""
        for line in lines:
            posted_at = posted_at or cls._date(line, "Last updated on")
            expires_at = expires_at or cls._date(line, "Expiring on")

        description_lines: list[str] = []
        started = False
        for line in lines:
            if line == title and not started:
                started = True
                continue
            if not started:
                continue
            lowered = line.casefold()
            if lowered in {"about the employer", "interested applicants", "how to apply"}:
                break
            if lowered.startswith("last updated on"):
                break
            if lowered in {"featured", "view all", "apply now"}:
                continue
            description_lines.append(line)
        description = "\n".join(description_lines).strip()
        if len(description) < 80:
            return None

        return NormalizedJob(
            source=cls.source_name,
            source_job_id=detail_match.group(1),
            source_platform="fastjobs",
            title=title,
            company=company or "Unknown Company",
            description=description,
            location=location,
            source_url=url,
            apply_url=url,
            posted_at=posted_at,
            expires_at=expires_at,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="SGD" if salary_min is not None else "",
            salary_period=salary_period,
            employment_type=", ".join(employment_bits),
            raw_payload={
                "public_url": url,
                "adapter": "fastjobs-public-html-v1",
            },
        ).validate()

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        seeds = self.start_urls or [self.PART_TIME_URL, self.HOME_URL]
        detail_urls: list[str] = []
        seen: set[str] = set()

        for seed in seeds:
            if self._is_detail_url(seed):
                if seed not in seen:
                    seen.add(seed)
                    detail_urls.append(seed)
                continue
            html = self.client.get_text(seed)
            for detail_url, _label in extract_links(
                html,
                base_url=seed,
                path_pattern=r"/(?:[a-z]{2}/)?singapore-job-ad/\d+",
            ):
                if detail_url in seen:
                    continue
                seen.add(detail_url)
                detail_urls.append(detail_url)
                if len(detail_urls) >= spec.limit_per_source:
                    break
            if detail_urls:
                break

        if not detail_urls:
            raise JobSourceError(
                "FastJobs exposed no public job links in the fetched listing "
                "page. Its current search cards may be client-rendered. Paste "
                "one or more FastJobs job/search URLs in Advanced source URLs "
                "or use browser capture."
            )

        jobs: list[NormalizedJob] = []
        for index, url in enumerate(detail_urls[: spec.limit_per_source]):
            normalized = self.normalize_html(url, self.client.get_text(url))
            if normalized is None:
                continue
            if matches_query(
                spec.query,
                normalized.title,
                normalized.company,
                normalized.description,
            ):
                jobs.append(normalized)
            if index + 1 < len(detail_urls):
                self.client.pause(self.delay_seconds)
        return jobs
