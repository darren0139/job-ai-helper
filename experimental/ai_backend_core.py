from __future__ import annotations

import os
from typing import Literal

AIBackendName = Literal["api", "codex"]
RouteName = Literal["analysis", "chat"]

AI_BACKEND_API: AIBackendName = "api"
AI_BACKEND_CODEX: AIBackendName = "codex"

AI_BACKEND_OPTIONS: dict[str, AIBackendName] = {
    "API (existing)": AI_BACKEND_API,
    "Codex (Local / Experimental)": AI_BACKEND_CODEX,
}


def resolve_ai_backend(value: object) -> AIBackendName:
    cleaned = str(value or "").strip().lower()
    aliases: dict[str, AIBackendName] = {
        "": AI_BACKEND_API,
        "api": AI_BACKEND_API,
        "api (existing)": AI_BACKEND_API,
        "codex": AI_BACKEND_CODEX,
        "codex (local / experimental)": AI_BACKEND_CODEX,
    }
    try:
        return aliases[cleaned]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported AI backend {value!r}. Expected 'api' or 'codex'."
        ) from exc


_DEFAULT_BACKEND = resolve_ai_backend(
    os.getenv("AI_BACKEND", AI_BACKEND_API)
)

_RUNTIME_BACKENDS: dict[RouteName, AIBackendName] = {
    "analysis": resolve_ai_backend(
        os.getenv("ANALYSIS_AI_BACKEND", _DEFAULT_BACKEND)
    ),
    "chat": resolve_ai_backend(
        os.getenv("CHAT_AI_BACKEND", _DEFAULT_BACKEND)
    ),
}


def get_ai_backend_options() -> dict[str, AIBackendName]:
    return dict(AI_BACKEND_OPTIONS)


def set_runtime_ai_backend(
    backend_or_label: object,
    *,
    route: RouteName = "analysis",
) -> AIBackendName:
    if route not in _RUNTIME_BACKENDS:
        raise ValueError(f"Unknown AI backend route: {route!r}.")
    resolved = resolve_ai_backend(backend_or_label)
    _RUNTIME_BACKENDS[route] = resolved
    return resolved


def get_active_ai_backend(
    route: RouteName = "analysis",
) -> AIBackendName:
    if route not in _RUNTIME_BACKENDS:
        raise ValueError(f"Unknown AI backend route: {route!r}.")
    return _RUNTIME_BACKENDS[route]
