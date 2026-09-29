from __future__ import annotations

from abc import ABC, abstractmethod

from job_discovery.models import NormalizedJob, SearchSpec


class JobSource(ABC):
    source_name: str
    display_name: str
    # True only when the most recent fetch covered the full relevant source scope.
    # The pipeline uses this to decide whether absence is meaningful enough to mark removed.
    fetch_complete: bool = False

    @abstractmethod
    def fetch(self, spec: SearchSpec) -> list[NormalizedJob]:
        raise NotImplementedError

    @property
    def run_key(self) -> str:
        return self.source_name
