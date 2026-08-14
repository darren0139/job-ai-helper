from __future__ import annotations

import json
import os
import re
import tempfile
import time
from contextvars import ContextVar
from copy import deepcopy
from typing import Any, Literal

RouteName = Literal["analysis", "chat"]
SDK_DEFAULT_MODEL_LABEL = "sdk-configured-default"


class CodexLLMBackendError(RuntimeError):
    pass


_LAST_CODEX_CALL_METADATA: ContextVar[dict[str, Any] | None] = ContextVar(
    "last_codex_llm_backend_metadata",
    default=None,
)


def get_last_codex_call_metadata() -> dict[str, Any] | None:
    metadata = _LAST_CODEX_CALL_METADATA.get()
    return deepcopy(metadata) if metadata is not None else None


def _resolve_codex_model(
    *,
    route: RouteName,
    explicit_model: str | None,
) -> str | None:
    if explicit_model and explicit_model.strip():
        return explicit_model.strip()
    route_key = (
        "CODEX_ANALYSIS_MODEL"
        if route == "analysis"
        else "CODEX_CHAT_MODEL"
    )
    return (
        os.getenv(route_key, "").strip()
        or os.getenv("CODEX_MODEL", "").strip()
        or None
    )


def _operation_slug(operation: str) -> str:
    cleaned = re.sub(
        r"[^a-z0-9]+",
        "-",
        str(operation or "").strip().lower(),
    ).strip("-")
    return cleaned or "llm"


def _build_prompt(
    system: str,
    user: str,
    *,
    expect_json: bool,
) -> str:
    output_rule = (
        "Return only one valid JSON object. Do not use Markdown fences and "
        "do not include explanatory prose outside the JSON object."
        if expect_json
        else "Return only the requested answer text."
    )
    return (
        "You are being used as a local semantic-AI backend for one isolated "
        "application request. Do not inspect files, run commands, call tools, "
        "or modify anything. Use only the prompt content supplied below.\n\n"
        f"SYSTEM INSTRUCTIONS:\n{system.strip()}\n\n"
        f"USER REQUEST:\n{user.strip()}\n\n"
        f"OUTPUT REQUIREMENT:\n{output_rule}"
    )


def _strip_markdown_fence(raw: str) -> str:
    stripped = str(raw or "").strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        return stripped[7:-3].strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped[3:-3].strip()
    return stripped


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = _strip_markdown_fence(raw)
    start = cleaned.find("{")
    try:
        if start >= 0:
            parsed, _ = json.JSONDecoder().raw_decode(cleaned, start)
        else:
            parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise CodexLLMBackendError(
            "Codex returned invalid JSON; no API fallback was attempted."
        ) from exc
    if not isinstance(parsed, dict):
        raise CodexLLMBackendError(
            "Codex JSON output must be one top-level object."
        )
    return parsed


def _invoke_codex(
    system: str,
    user: str,
    *,
    route: RouteName,
    model: str | None,
    operation: str,
    expect_json: bool,
) -> str:
    try:
        from openai_codex import Codex, Sandbox
    except ImportError as exc:
        raise CodexLLMBackendError(
            "The Codex backend is selected but openai-codex is not installed."
        ) from exc

    selected_model = _resolve_codex_model(
        route=route,
        explicit_model=model,
    )
    prompt = _build_prompt(
        system,
        user,
        expect_json=expect_json,
    )

    started_at = time.perf_counter()
    try:
        prefix = f"codex-{_operation_slug(operation)}-"
        with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
            with Codex() as codex:
                thread_kwargs: dict[str, Any] = {
                    "cwd": temp_dir,
                    "sandbox": Sandbox.read_only,
                    "ephemeral": True,
                }
                if selected_model:
                    thread_kwargs["model"] = selected_model
                thread = codex.thread_start(**thread_kwargs)
                result = thread.run(
                    prompt,
                    sandbox=Sandbox.read_only,
                )
                raw = str(
                    getattr(result, "final_response", "") or ""
                ).strip()
    except Exception as exc:
        raise CodexLLMBackendError(
            f"Codex SDK invocation failed: {exc}"
        ) from exc

    _LAST_CODEX_CALL_METADATA.set(
        {
            "backend": "codex",
            "runtime": "openai-codex Python SDK",
            "route": route,
            "operation": operation,
            "model": selected_model or SDK_DEFAULT_MODEL_LABEL,
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
            "output_length": len(raw),
            "api_call": False,
        }
    )

    if not raw:
        raise CodexLLMBackendError(
            "Codex returned no visible response text."
        )
    return raw


def ask_json_with_codex(
    system: str,
    user: str,
    *,
    route: RouteName = "analysis",
    model: str | None = None,
    operation: str = "json",
) -> dict[str, Any]:
    raw = _invoke_codex(
        system,
        user,
        route=route,
        model=model,
        operation=operation,
        expect_json=True,
    )
    return _parse_json_object(raw)


def ask_text_with_codex(
    system: str,
    user: str,
    *,
    route: RouteName = "analysis",
    model: str | None = None,
    operation: str = "text",
) -> str:
    return _invoke_codex(
        system,
        user,
        route=route,
        model=model,
        operation=operation,
        expect_json=False,
    ).strip()
