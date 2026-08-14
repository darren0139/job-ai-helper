"""Fail-closed official Codex SDK adapter for the JD-profile extraction POC.

This module deliberately has no production call sites. It invokes the local
Codex Python SDK with a read-only sandbox and validates JSON before returning
it. The returned dictionary has the same shape as ``analyzer.extract_jd_profile``.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any

from experimental.codex_llm_backend import (
    CodexLLMBackendError,
    get_last_codex_call_metadata,
)
from llm import ask_json
from prompts import JD_PROFILE_PROMPT


JD_PROFILE_SCALAR_FIELDS = (
    "job_title", "company", "location", "experience_level",
)
JD_PROFILE_LIST_FIELDS = (
    "required_skills", "preferred_skills", "tools_technologies",
    "responsibilities", "soft_skills", "buzzwords", "deal_breakers",
)
JD_PROFILE_FIELDS = JD_PROFILE_SCALAR_FIELDS + JD_PROFILE_LIST_FIELDS
SDK_DEFAULT_MODEL_LABEL = "sdk-configured-default"


class CodexJDExtractionError(RuntimeError):
    """Raised when a Codex SDK extraction cannot produce a valid profile."""


@dataclass(frozen=True)
class CodexInvocationMetadata:
    """Non-sensitive metadata for one local Codex SDK invocation."""

    runtime: str
    model: str
    elapsed_seconds: float
    output_length: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexJDExtractionResult:
    """Validated profile and invocation metadata for evaluation use."""

    profile: dict[str, Any]
    metadata: CodexInvocationMetadata


_LAST_METADATA: ContextVar[CodexInvocationMetadata | None] = ContextVar(
    "last_codex_jd_extraction_metadata", default=None,
)


def get_last_codex_jd_extraction_metadata() -> dict[str, Any] | None:
    """Return metadata from the current context's most recent POC invocation."""
    metadata = _LAST_METADATA.get()
    return metadata.to_dict() if metadata is not None else None


def validate_jd_profile_contract(candidate: Any) -> dict[str, Any]:
    """Reject data that is not the existing exact JD-profile contract.

    Empty scalar/list values remain valid because the current production prompt
    uses them for absent information. This function repairs nothing: invalid
    model output is rejected rather than accepted or silently coerced.
    """
    if not isinstance(candidate, dict):
        raise CodexJDExtractionError("Codex output must be a JSON object.")

    expected, actual = set(JD_PROFILE_FIELDS), set(candidate)
    missing, unexpected = sorted(expected - actual), sorted(actual - expected)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected fields: {', '.join(unexpected)}")
        raise CodexJDExtractionError(
            "JD profile does not match the required contract ("
            + "; ".join(details) + ")."
        )

    profile: dict[str, Any] = {}
    for field in JD_PROFILE_SCALAR_FIELDS:
        value = candidate[field]
        if not isinstance(value, str):
            raise CodexJDExtractionError(f"JD field {field!r} must be a string.")
        profile[field] = value
    for field in JD_PROFILE_LIST_FIELDS:
        value = candidate[field]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise CodexJDExtractionError(
                f"JD field {field!r} must be a list of strings."
            )
        profile[field] = list(value)
    return profile




def _build_system_prompt() -> str:
    return (
        "You are performing one isolated data-extraction operation. Do not "
        "inspect files, run commands, call tools, score alignment, or modify "
        "anything. Use only the job-description text supplied in the user "
        "message.\n\n"
        "POC field clarification: experience_level is for an explicitly stated "
        "seniority classification such as Intern, Entry Level, Junior, Mid-Level, "
        "Senior, Lead, or Manager. Do not put a minimum-years requirement such "
        "as 'Minimum 1 year of experience' in experience_level; keep that "
        "requirement in the appropriate skills/deal-breakers fields. If no "
        "seniority classification is explicit, use an empty string.\n\n"
        f"{JD_PROFILE_PROMPT.strip()}"
    )

def extract_job_description_with_codex_result(
    jd_text: str, *, model: str | None = None,
) -> CodexJDExtractionResult:
    if not isinstance(jd_text, str) or not jd_text.strip():
        raise ValueError("jd_text must be a non-empty string.")

    user = f"JOB DESCRIPTION TEXT:\n\n{jd_text}"

    try:
        parsed = ask_json(
            _build_system_prompt(),
            user,
            route="analysis",
            model=model,
            backend="codex",
            operation="jd-extraction",
        )
    except CodexLLMBackendError as exc:
        if "invalid JSON" in str(exc):
            raise CodexJDExtractionError(
                "Codex returned invalid or missing JSON; profile was rejected."
            ) from exc
        raise CodexJDExtractionError(
            f"Codex SDK invocation failed: {exc}"
        ) from exc
    except Exception as exc:
        raise CodexJDExtractionError(
            f"Codex SDK invocation failed: {exc}"
        ) from exc

    raw_metadata = get_last_codex_call_metadata() or {}
    metadata = CodexInvocationMetadata(
        runtime=str(
            raw_metadata.get("runtime", "openai-codex Python SDK")
        ),
        model=str(
            raw_metadata.get(
                "model",
                model or SDK_DEFAULT_MODEL_LABEL,
            )
        ),
        elapsed_seconds=float(
            raw_metadata.get("elapsed_seconds", 0.0) or 0.0
        ),
        output_length=int(
            raw_metadata.get("output_length", 0) or 0
        ),
    )
    _LAST_METADATA.set(metadata)

    return CodexJDExtractionResult(
        profile=validate_jd_profile_contract(parsed),
        metadata=metadata,
    )

def extract_job_description_with_codex(
    jd_text: str, *, model: str | None = None,
) -> dict[str, Any]:
    """Return only a validated profile compatible with ``extract_jd_profile``."""
    return extract_job_description_with_codex_result(jd_text, model=model).profile
