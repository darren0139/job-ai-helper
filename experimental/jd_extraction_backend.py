'''Explicit JD-extraction backend dispatch for the isolated Codex POC.

The existing API path remains the default. Codex is opt-in and local-only.
A Codex failure is propagated to the caller; this module never silently
falls back to the API because doing so could unexpectedly consume API credits.
'''

from __future__ import annotations

import os
from typing import Any


JD_EXTRACTION_BACKEND_API = "api"
JD_EXTRACTION_BACKEND_CODEX = "codex"

JD_EXTRACTION_BACKEND_OPTIONS = {
    "API (existing)": JD_EXTRACTION_BACKEND_API,
    "Codex (Local / Experimental)": JD_EXTRACTION_BACKEND_CODEX,
}


def normalise_jd_extraction_backend(value: object) -> str:
    '''Return the canonical backend name or reject an unsupported value.'''
    cleaned = str(value or "").strip().lower()

    aliases = {
        "": JD_EXTRACTION_BACKEND_API,
        "api": JD_EXTRACTION_BACKEND_API,
        "api (existing)": JD_EXTRACTION_BACKEND_API,
        "codex": JD_EXTRACTION_BACKEND_CODEX,
        "codex (local / experimental)": JD_EXTRACTION_BACKEND_CODEX,
    }

    try:
        return aliases[cleaned]
    except KeyError as exc:
        allowed = ", ".join(sorted({JD_EXTRACTION_BACKEND_API, JD_EXTRACTION_BACKEND_CODEX}))
        raise ValueError(
            f"Unsupported JD extraction backend {value!r}. Expected one of: {allowed}."
        ) from exc


def get_configured_jd_extraction_backend() -> str:
    '''Resolve the local default from JD_EXTRACTION_BACKEND, defaulting to API.'''
    return normalise_jd_extraction_backend(
        os.getenv("JD_EXTRACTION_BACKEND", JD_EXTRACTION_BACKEND_API)
    )


def extract_jd_profile_with_backend(
    jd_text: str,
    *,
    backend: str | None = None,
) -> dict[str, Any]:
    '''Extract one JD profile using the explicitly selected backend.

    API:
        Calls the unchanged production ``analyzer.extract_jd_profile`` path.

    Codex:
        Calls the isolated ``experimental.codex_jd_extraction`` adapter.
        ``CODEX_JD_MODEL`` is optional; when unset, the SDK-configured default
        is used.

    There is intentionally no automatic fallback between backends.
    '''
    selected = normalise_jd_extraction_backend(
        backend if backend is not None else get_configured_jd_extraction_backend()
    )

    if selected == JD_EXTRACTION_BACKEND_API:
        from analyzer import extract_jd_profile

        return extract_jd_profile(jd_text)

    from experimental.codex_jd_extraction import (
        extract_job_description_with_codex,
    )

    codex_model = os.getenv("CODEX_JD_MODEL", "").strip() or None
    return extract_job_description_with_codex(
        jd_text,
        model=codex_model,
    )
