"""Rewrite-provider registry for Job AI Helper."""
from __future__ import annotations

from .base import (
    CONFIGURED_LLM_PROVIDER,
    GITHUB_COPILOT_PROVIDER,
    RewriteContract,
    RewriteProvider,
    RewriteResult,
)
from .configured_llm import ConfiguredLLMRewriteProvider
from .copilot import GitHubCopilotRewriteProvider


REWRITE_PROVIDER_OPTIONS = {
    "Current Rephrase model": CONFIGURED_LLM_PROVIDER,
    "GitHub Copilot": GITHUB_COPILOT_PROVIDER,
}


def provider_display_name(provider_id: str) -> str:
    for label, value in REWRITE_PROVIDER_OPTIONS.items():
        if value == provider_id:
            return label
    return str(provider_id or "")


def create_rewrite_provider(
    provider_id: str,
    *,
    model: str,
    ask_json_fn,
) -> RewriteProvider:
    selected = str(provider_id or CONFIGURED_LLM_PROVIDER).strip()
    if selected == CONFIGURED_LLM_PROVIDER:
        return ConfiguredLLMRewriteProvider(
            model=model,
            ask_json_fn=ask_json_fn,
        )
    if selected == GITHUB_COPILOT_PROVIDER:
        return GitHubCopilotRewriteProvider(model="auto")
    raise ValueError(f"Unknown rewrite provider: {provider_id!r}.")


__all__ = [
    "CONFIGURED_LLM_PROVIDER",
    "GITHUB_COPILOT_PROVIDER",
    "REWRITE_PROVIDER_OPTIONS",
    "RewriteContract",
    "RewriteProvider",
    "RewriteResult",
    "create_rewrite_provider",
    "provider_display_name",
]
