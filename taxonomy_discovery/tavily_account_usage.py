"""Explicit Tavily account usage lookup."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable
from urllib import error, request

TAVILY_USAGE_ENDPOINT = "https://api.tavily.com/usage"

UsageTransport = Callable[
    [str, dict[str, str], float],
    dict[str, Any],
]


class TavilyUsageError(RuntimeError):
    pass


def tavily_api_key_from_env() -> str | None:
    value = str(os.environ.get("TAVILY_API_KEY") or "").strip()
    return value or None


def _default_usage_transport(
    endpoint: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    req = request.Request(endpoint, method="GET", headers=headers)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TavilyUsageError(
            f"Tavily usage HTTP {exc.code}: {body[:500]}"
        ) from exc
    except error.URLError as exc:
        raise TavilyUsageError(
            f"Tavily usage request failed: {exc.reason}"
        ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TavilyUsageError(
            "Tavily usage returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise TavilyUsageError(
            "Tavily usage returned a non-object response"
        )
    return payload


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def normalise_tavily_account_usage(
    payload: dict[str, Any],
) -> dict[str, Any]:
    key = payload.get("key")
    account = payload.get("account")
    key = key if isinstance(key, dict) else {}
    account = account if isinstance(account, dict) else {}

    return {
        "provider": "tavily",
        "endpoint": "usage",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "key": {
            "usage": _number(key.get("usage")),
            "limit": _number(key.get("limit")),
            "search_usage": _number(key.get("search_usage")),
            "extract_usage": _number(key.get("extract_usage")),
            "crawl_usage": _number(key.get("crawl_usage")),
            "map_usage": _number(key.get("map_usage")),
            "research_usage": _number(key.get("research_usage")),
        },
        "account": {
            "current_plan": str(account.get("current_plan") or ""),
            "plan_usage": _number(account.get("plan_usage")),
            "plan_limit": _number(account.get("plan_limit")),
            "paygo_usage": _number(account.get("paygo_usage")),
            "paygo_limit": _number(account.get("paygo_limit")),
            "search_usage": _number(account.get("search_usage")),
            "extract_usage": _number(account.get("extract_usage")),
            "crawl_usage": _number(account.get("crawl_usage")),
            "map_usage": _number(account.get("map_usage")),
            "research_usage": _number(account.get("research_usage")),
        },
    }


def fetch_tavily_account_usage(
    *,
    api_key: str | None = None,
    timeout_seconds: float = 20.0,
    transport: UsageTransport | None = None,
) -> dict[str, Any]:
    key = str(api_key or tavily_api_key_from_env() or "").strip()
    if not key:
        raise TavilyUsageError("TAVILY_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    payload = (
        transport(TAVILY_USAGE_ENDPOINT, headers, timeout_seconds)
        if transport is not None
        else _default_usage_transport(
            TAVILY_USAGE_ENDPOINT,
            headers,
            timeout_seconds,
        )
    )
    if not isinstance(payload, dict):
        raise TavilyUsageError(
            "Tavily usage transport returned a non-object response"
        )
    return normalise_tavily_account_usage(payload)
