"""GitHub Copilot SDK rewrite provider.

This adapter is intentionally text-only:
- no Job AI tools are exposed;
- no repository/file/shell tools are exposed;
- no automatic retry;
- no automatic fallback to another provider.
"""
from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor

from .base import (
    GITHUB_COPILOT_PROVIDER,
    RewriteContract,
    RewriteResult,
)


_SYSTEM_RULES = """You are a resume wording polisher.

You do NOT decide:
- evidence eligibility
- evidence strength
- JD score
- whether the rewrite is safe to apply

Those decisions are made deterministically by Job AI Helper.

Rules:
- Use ONLY the exact allowed evidence supplied below.
- Do not invent metrics, technologies, responsibilities, outcomes, scope, or impact.
- Preserve supported concepts needed for the target requirement.
- Prefer concise resume wording.
- Return JSON only.
"""


def _prompt(contract: RewriteContract) -> str:
    return f"""{_SYSTEM_RULES}

CURRENT BULLET
{contract.current_bullet}

VERIFIED GROUNDED BASELINE
{contract.grounded_baseline}

TARGET JD REQUIREMENT
{contract.target_requirement}

EXACT ALLOWED EVIDENCE
Evidence ID: {contract.evidence_id}
{contract.evidence_record.get("text", "")}

MAXIMUM SUPPORTED MATCH
{contract.required_ceiling}

TASK
Polish the VERIFIED GROUNDED BASELINE into one concise resume bullet.
Do not use any fact outside the exact allowed evidence row.

Return exactly this JSON shape:
{{
  "candidate_bullet": "...",
  "evidence_ids": ["{contract.evidence_id}"]
}}
"""


def _extract_text(response) -> str:
    if response is None:
        raise RuntimeError(
            "GitHub Copilot went idle without returning an assistant message."
        )
    data = getattr(response, "data", None)
    content = getattr(data, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    for attribute in ("content", "text", "message"):
        value = getattr(response, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    rendered = str(response).strip()
    if rendered:
        return rendered
    raise RuntimeError("GitHub Copilot returned an empty response.")


def _parse_json_object(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError("GitHub Copilot returned no JSON object.")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("GitHub Copilot returned a non-object JSON value.")
    return value


def _run_blocking(factory):
    """Run an async SDK call from normal Streamlit code.

    Streamlit normally has no running asyncio loop in the script thread. The
    thread fallback keeps this safe if that changes.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(factory())).result()


class GitHubCopilotRewriteProvider:
    provider_id = GITHUB_COPILOT_PROVIDER
    display_name = "GitHub Copilot"

    def __init__(self, *, model: str = "auto") -> None:
        self.model = str(model or "auto").strip() or "auto"

    async def _polish_async(self, contract: RewriteContract) -> RewriteResult:
        try:
            from copilot import CopilotClient
        except ImportError as exc:
            raise RuntimeError(
                "github-copilot-sdk is not installed. Install the project's "
                "requirements and retry."
            ) from exc

        async with CopilotClient() as client:
            async with await client.create_session(
                model=self.model,
                available_tools=[],
                enable_session_store=False,
            ) as session:
                response = await session.send_and_wait(_prompt(contract))

        raw = _extract_text(response)
        payload = _parse_json_object(raw)
        candidate = str(payload.get("candidate_bullet") or "").strip()
        evidence_ids = payload.get("evidence_ids")

        if not candidate:
            raise ValueError("GitHub Copilot returned no candidate_bullet.")
        if not isinstance(evidence_ids, list):
            raise ValueError("GitHub Copilot returned malformed evidence_ids.")

        return RewriteResult(
            candidate_bullet=candidate,
            evidence_ids=[str(value) for value in evidence_ids],
            provider_id=self.provider_id,
            model=self.model,
            call_count=1,
            metadata={"raw_response": raw},
        )

    def polish(self, contract: RewriteContract) -> RewriteResult:
        return _run_blocking(lambda: self._polish_async(contract))
