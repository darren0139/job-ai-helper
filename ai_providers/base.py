"""Provider-neutral contracts for evidence-grounded resume rewrites."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


CONFIGURED_LLM_PROVIDER = "configured_llm"
GITHUB_COPILOT_PROVIDER = "github_copilot"


@dataclass(frozen=True)
class RewriteContract:
    """One exact-evidence-row rewrite request.

    Providers may propose wording only. They do not control requirement identity,
    project identity, scoring, verification, or Apply.
    """

    target_requirement_id: str
    project_id: str
    bullet_index: int
    current_bullet: str
    grounded_baseline: str
    target_requirement: str
    evidence_id: str
    evidence_record: dict[str, Any]
    required_ceiling: str


@dataclass(frozen=True)
class RewriteResult:
    candidate_bullet: str
    evidence_ids: list[str]
    provider_id: str
    model: str
    call_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class RewriteProvider(Protocol):
    provider_id: str
    display_name: str

    def polish(self, contract: RewriteContract) -> RewriteResult:
        ...
