from __future__ import annotations

import re

from job_discovery.http_client import JsonHttpClient
from job_discovery.models import NormalizedJob, SearchSpec
from job_discovery.public_html import deterministic_id, visible_lines
from job_discovery.text_utils import matches_query
from .base import JobSource


class StaffieSource(JobSource):
    """Staffie's public weekly shift samples."""

    source_name = "staffie"
    display_name = "Staffie shifts"
    fetch_complete = False
    BASE_URL = "https://staffie.app/"
    _SHIFT_RE = re.compile(
        r"^(?P<role>.+?)\s*·\s*S\$(?P<rate>\d+(?:\.\d+)?)/hr"
        r"\s*·\s*(?P<count>\d+)\s+shifts?$",
        re.IGNORECASE,
    )
    _VENUE_DESCRIPTOR_RE = re.compile(
        r"^(?P<kind>.+?)\s+at\s+(?P<location>.+)$",
        re.IGNORECASE,
    )

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @classmethod
    def parse_public_shifts(cls, html: str) -> list[NormalizedJob]:
        lines = visible_lines(html)
        in_section = False
        previous_line = ""
        venue = ""
        descriptor = ""
        location = "Singapore"
        jobs: list[NormalizedJob] = []

        for line in lines:
            lowered = line.casefold()
            if lowered == "new shifts this week":
                in_section = True
                previous_line = ""
                continue
            if not in_section:
                continue
            if lowered.startswith("book these and more"):
                break

            descriptor_match = cls._VENUE_DESCRIPTOR_RE.match(line)
            if descriptor_match and previous_line:
                venue = previous_line
                descriptor = line
                location = descriptor_match.group("location").strip()
                previous_line = line
                continue

            shift_match = cls._SHIFT_RE.match(line)
            if shift_match and venue:
                role = shift_match.group("role").strip()
                rate = float(shift_match.group("rate"))
                count = int(shift_match.group("count"))
                description = "\n".join(
                    [
                        f"Venue: {venue}",
                        descriptor,
                        f"Role: {role}",
                        f"Advertised rate: S${rate:g}/hr",
                        f"Public landing-page availability: {count} shifts",
                    ]
                )
                jobs.append(
                    NormalizedJob(
                        source=cls.source_name,
                        source_job_id=deterministic_id(
                            venue,
                            role,
                            location,
                            f"{rate:g}",
                        ),
                        source_platform="staffie",
                        title=role,
                        company=venue,
                        description=description,
                        location=location,
                        source_url=cls.BASE_URL,
                        apply_url=cls.BASE_URL,
                        salary_min=rate,
                        salary_max=rate,
                        salary_currency="SGD",
                        salary_period="hour",
                        employment_type="Gig / Shift",
                        raw_payload={
                            "venue": venue,
                            "descriptor": descriptor,
                            "role": role,
                            "rate": rate,
                            "shift_count": count,
                            "adapter": "staffie-public-sample-v1",
                        },
                    ).validate()
                )
                previous_line = line
                continue

            previous_line = line
        return jobs

    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        jobs = self.parse_public_shifts(self.client.get_text(self.BASE_URL))
        return [
            job
            for job in jobs
            if matches_query(
                spec.query,
                job.title,
                job.company,
                job.description,
                job.location,
            )
        ][: spec.limit_per_source]
