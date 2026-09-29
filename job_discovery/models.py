from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchSpec:
    query: str = ""
    singapore_only: bool = True
    max_pages: int = 3
    page_size: int = 100
    limit_per_source: int = 500


@dataclass(frozen=True, slots=True)
class NormalizedJob:
    source: str
    source_job_id: str
    title: str
    company: str
    description: str
    location: str = ""
    source_platform: str = ""
    source_url: str = ""
    apply_url: str = ""
    posted_at: str = ""
    expires_at: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    salary_period: str = ""
    employment_type: str = ""
    seniority: str = ""
    experience_years_min: float | None = None
    experience_years_max: float | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "NormalizedJob":
        if not self.source.strip():
            raise ValueError("NormalizedJob.source cannot be empty.")
        if not self.source_job_id.strip():
            raise ValueError("NormalizedJob.source_job_id cannot be empty.")
        if not self.title.strip():
            raise ValueError("NormalizedJob.title cannot be empty.")
        if not self.description.strip():
            raise ValueError("NormalizedJob.description cannot be empty.")
        return self

    @property
    def content_hash(self) -> str:
        material = {
            key: value
            for key, value in asdict(self).items()
            if key != "raw_payload"
        }
        material["raw_payload"] = self.raw_payload
        encoded = json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_record(self) -> dict[str, Any]:
        result = asdict(self)
        result["content_hash"] = self.content_hash
        return result
