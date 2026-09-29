from __future__ import annotations

import json
from typing import Any

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.text_utils import html_to_text, join_sections
from .base import JobSource


class SmartRecruitersSource(JobSource):
    source_name = "smartrecruiters"
    display_name = "SmartRecruiters"

    def __init__(self, company_identifier: str, *, company_name: str = "", client: JsonHttpClient | None = None) -> None:
        self.company_identifier = str(company_identifier).strip()
        self.company_name = str(company_name).strip() or self.company_identifier
        self.client = client or JsonHttpClient()
        self.detail_fetched_count = 0
        self.detail_reused_count = 0
        self.listing_count = 0

    @property
    def run_key(self) -> str:
        return f"smartrecruiters:{self.company_identifier}"

    @staticmethod
    def _location(raw: dict[str, Any]) -> str:
        location = raw.get("location") or {}
        if not isinstance(location, dict):
            return str(location or "").strip()
        parts = [
            str(location.get("city") or "").strip(),
            str(location.get("region") or "").strip(),
            str(location.get("country") or location.get("countryCode") or "").strip(),
        ]
        return ", ".join(part for part in parts if part)

    @staticmethod
    def _raw_payload(row: dict[str, Any]) -> dict[str, Any]:
        raw = row.get("raw_payload_json")
        if isinstance(raw, dict):
            return dict(raw)
        try:
            parsed = json.loads(str(raw or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def _known_job(cls, row: dict[str, Any]) -> NormalizedJob | None:
        try:
            return NormalizedJob(
                source=str(row.get("source") or ""),
                source_job_id=str(row.get("source_job_id") or ""),
                title=str(row.get("title") or ""),
                company=str(row.get("company") or ""),
                description=str(row.get("description") or ""),
                location=str(row.get("location") or ""),
                source_platform=str(row.get("source_platform") or ""),
                source_url=str(row.get("source_url") or ""),
                apply_url=str(row.get("apply_url") or ""),
                posted_at=str(row.get("posted_at") or ""),
                expires_at=str(row.get("expires_at") or ""),
                salary_min=row.get("salary_min"),
                salary_max=row.get("salary_max"),
                salary_currency=str(row.get("salary_currency") or ""),
                salary_period=str(row.get("salary_period") or ""),
                employment_type=str(row.get("employment_type") or ""),
                seniority=str(row.get("seniority") or ""),
                experience_years_min=row.get("experience_years_min"),
                experience_years_max=row.get("experience_years_max"),
                raw_payload=cls._raw_payload(row),
            ).validate()
        except (TypeError, ValueError):
            return None

    @classmethod
    def _summary_matches_known(cls, summary: dict[str, Any], row: dict[str, Any]) -> bool:
        """Conservatively decide whether stored detail can be reused.

        SmartRecruiters' list endpoint already exposes posting identity, title,
        release date, location, company and employment metadata. The public API
        requires a posting to be re-posted for content updates, so a stable
        summary is a useful incremental-refresh signal. Force full refresh is
        always available when the user wants every detail endpoint re-read.
        """
        if not row:
            return False
        raw = cls._raw_payload(row)

        checks: list[tuple[str, str]] = []
        checks.append((str(summary.get("name") or "").strip(), str(row.get("title") or "").strip()))
        checks.append((str(summary.get("releasedDate") or "").strip(), str(row.get("posted_at") or "").strip()))
        checks.append((cls._location(summary), str(row.get("location") or "").strip()))

        summary_company = summary.get("company") or {}
        if isinstance(summary_company, dict):
            checks.append((str(summary_company.get("name") or "").strip(), str(row.get("company") or "").strip()))

        summary_employment = summary.get("typeOfEmployment") or {}
        if isinstance(summary_employment, dict):
            checks.append((str(summary_employment.get("label") or "").strip(), str(row.get("employment_type") or "").strip()))

        summary_job_ad = str(summary.get("jobAdId") or "").strip()
        raw_job_ad = str(raw.get("jobAdId") or "").strip()
        if summary_job_ad and raw_job_ad:
            checks.append((summary_job_ad, raw_job_ad))

        compared = 0
        for current, known in checks:
            if not current or not known:
                continue
            compared += 1
            if current.casefold() != known.casefold():
                return False
        return compared >= 2

    def _normalize_detail(self, detail: dict[str, Any], summary: dict[str, Any], posting_id: str) -> NormalizedJob | None:
        title = str(detail.get("name") or summary.get("name") or "").strip()
        location = self._location(detail) or self._location(summary)
        job_ad = detail.get("jobAd") or {}
        if not isinstance(job_ad, dict):
            job_ad = {}
        sections = job_ad.get("sections") or {}
        if not isinstance(sections, dict):
            sections = {}
        description = join_sections(
            [
                ("", sections.get("companyDescription")),
                ("Job description", sections.get("jobDescription")),
                ("Qualifications", sections.get("qualifications")),
                ("Additional information", sections.get("additionalInformation")),
            ]
        )
        if not description:
            description = html_to_text(detail.get("description"))
        if not title or not description:
            return None
        if location and "singapore" not in location.lower() and ", sg" not in location.lower():
            return None
        company = detail.get("company") or {}
        company_name = (
            str(company.get("name") or "").strip()
            if isinstance(company, dict)
            else ""
        ) or self.company_name
        employment = detail.get("typeOfEmployment") or {}
        employment_label = (
            str(employment.get("label") or "").strip()
            if isinstance(employment, dict)
            else ""
        )
        return NormalizedJob(
            source=self.source_name,
            source_job_id=f"{self.company_identifier}:{posting_id}",
            source_platform="smartrecruiters",
            title=title,
            company=company_name,
            description=description,
            location=location,
            source_url=str(job_ad.get("jobUrl") or "").strip() or str(detail.get("ref") or "").strip(),
            apply_url=str(detail.get("applyUrl") or summary.get("applyUrl") or "").strip(),
            posted_at=str(detail.get("releasedDate") or summary.get("releasedDate") or ""),
            employment_type=employment_label,
            raw_payload=detail,
        )

    def fetch(
        self,
        spec: SearchSpec,
        *,
        known_jobs: dict[str, dict[str, Any]] | None = None,
        force_detail_refresh: bool = False,
    ) -> list[NormalizedJob]:
        self.fetch_complete = False
        self.detail_fetched_count = 0
        self.detail_reused_count = 0
        self.listing_count = 0
        if not self.company_identifier:
            return []

        known_jobs = known_jobs or {}
        base = f"https://api.smartrecruiters.com/v1/companies/{self.company_identifier}/postings"
        page_size = max(1, min(spec.page_size, 100))
        offset = 0
        candidates: list[dict[str, Any]] = []
        pagination_complete = False

        for _ in range(max(1, spec.max_pages)):
            data = self.client.get_json(
                base,
                params={
                    "q": None,
                    "limit": page_size,
                    "offset": offset,
                    "country": "sg" if spec.singapore_only else None,
                    "destination": "PUBLIC",
                },
            )
            content = data.get("content", []) if isinstance(data, dict) else []
            if not isinstance(content, list) or not content:
                pagination_complete = True
                break
            candidates.extend(item for item in content if isinstance(item, dict))
            if len(content) < page_size:
                pagination_complete = True
                break
            offset += page_size

        self.listing_count = len(candidates)
        jobs: list[NormalizedJob] = []
        for summary in candidates[: spec.limit_per_source]:
            posting_id = str(summary.get("id") or summary.get("uuid") or "").strip()
            if not posting_id:
                continue
            source_job_id = f"{self.company_identifier}:{posting_id}"
            known = known_jobs.get(source_job_id)
            if (
                not force_detail_refresh
                and known is not None
                and self._summary_matches_known(summary, known)
            ):
                reused = self._known_job(known)
                if reused is not None:
                    jobs.append(reused)
                    self.detail_reused_count += 1
                    continue

            detail = self.client.get_json(f"{base}/{posting_id}")
            self.detail_fetched_count += 1
            if not isinstance(detail, dict):
                continue
            normalized = self._normalize_detail(detail, summary, posting_id)
            if normalized is not None:
                jobs.append(normalized)

        self.fetch_complete = pagination_complete and len(candidates) <= spec.limit_per_source
        return jobs
