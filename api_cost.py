from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = PROJECT_ROOT / "config" / "model_benchmark_catalog.json"


@lru_cache(maxsize=1)
def load_price_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {
            "models": {},
            "updated_at": None,
            "currency": "USD",
            "unit": "per_1m_tokens",
        }
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def clear_price_catalog_cache() -> None:
    load_price_catalog.cache_clear()


def _usage_number(usage: Any, *keys: str) -> int:
    if not isinstance(usage, dict):
        return 0
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    for nested_key in (
        "prompt_tokens_details",
        "input_tokens_details",
        "completion_tokens_details",
        "output_tokens_details",
    ):
        nested = usage.get(nested_key)
        if not isinstance(nested, dict):
            continue
        for key in keys:
            value = nested.get(key)
            if isinstance(value, (int, float)):
                return int(value)
    return 0


def normalise_usage(metadata: dict[str, Any]) -> dict[str, int]:
    usage = metadata.get("usage") or {}
    input_tokens = _usage_number(
        usage, "prompt_tokens", "input_tokens"
    )
    output_tokens = _usage_number(
        usage, "completion_tokens", "output_tokens"
    )
    cached_tokens = _usage_number(
        usage,
        "cached_tokens",
        "cached_input_tokens",
        "cache_read_input_tokens",
    )
    if cached_tokens > input_tokens:
        cached_tokens = 0
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "uncached_input_tokens": max(0, input_tokens - cached_tokens),
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _candidate_model_ids(metadata: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for raw in (
        metadata.get("requested_model"),
        metadata.get("response_model"),
    ):
        model = str(raw or "").strip()
        if not model:
            continue
        values.append(model)
        if "/" not in model:
            values.append(f"openai/{model}")
    return list(dict.fromkeys(values))


def resolve_pricing(
    metadata: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    models = load_price_catalog().get("models", {}) or {}
    for model_id in _candidate_model_ids(metadata):
        pricing = models.get(model_id)
        if isinstance(pricing, dict):
            return model_id, pricing
    return None, None


def estimate_call_cost(metadata: dict[str, Any]) -> float | None:
    _, pricing = resolve_pricing(metadata)
    if not pricing:
        return None
    usage = normalise_usage(metadata)
    input_rate = float(pricing.get("input", 0.0) or 0.0)
    cached_rate = float(
        pricing.get("cached_input", input_rate) or input_rate
    )
    output_rate = float(pricing.get("output", 0.0) or 0.0)
    cost = (
        usage["uncached_input_tokens"] * input_rate
        + usage["cached_input_tokens"] * cached_rate
        + usage["output_tokens"] * output_rate
    ) / 1_000_000
    return round(cost, 8)


def summarise_api_calls(
    calls: list[dict[str, Any]],
) -> dict[str, Any]:
    total_input = 0
    total_cached = 0
    total_output = 0
    total_elapsed = 0.0
    total_cost = 0.0
    unknown = 0
    rows: list[dict[str, Any]] = []

    for call in calls:
        if not isinstance(call, dict):
            continue
        usage = normalise_usage(call)
        pricing_model, _ = resolve_pricing(call)
        cost = estimate_call_cost(call)

        total_input += usage["input_tokens"]
        total_cached += usage["cached_input_tokens"]
        total_output += usage["output_tokens"]
        total_elapsed += float(call.get("elapsed_seconds", 0.0) or 0.0)

        if cost is None:
            unknown += 1
        else:
            total_cost += cost

        rows.append(
            {
                **call,
                "pricing_model": pricing_model,
                "normalised_usage": usage,
                "estimated_cost_usd": cost,
            }
        )

    catalog = load_price_catalog()
    return {
        "currency": str(catalog.get("currency", "USD") or "USD"),
        "price_catalog_updated_at": catalog.get("updated_at"),
        "price_unit": catalog.get("unit", "per_1m_tokens"),
        "call_count": len(rows),
        "input_tokens": total_input,
        "cached_input_tokens": total_cached,
        "uncached_input_tokens": max(0, total_input - total_cached),
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "elapsed_seconds": round(total_elapsed, 3),
        "estimated_total_cost_usd": round(total_cost, 8),
        "unknown_cost_call_count": unknown,
        "cost_estimate_complete": unknown == 0,
        "tracked_actions": sorted(
            {
                str(row.get("action") or "").strip()
                for row in rows
                if str(row.get("action") or "").strip()
            }
        ),
        "calls": rows,
    }


def summarise_api_calls_by_action(
    calls: list[dict[str, Any]],
    *,
    action_order: list[str] | None = None,
    action_labels: dict[str, str] | None = None,
    zero_actions: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    # Aggregate the existing per-call ledger into one row per app action.
    grouped: dict[str, list[dict[str, Any]]] = {}

    for call in calls:
        if not isinstance(call, dict):
            continue

        action = str(
            call.get("action") or "unlabelled"
        ).strip() or "unlabelled"

        grouped.setdefault(action, []).append(call)

    labels = action_labels or {}
    rows: list[dict[str, Any]] = []

    for action, action_calls in grouped.items():
        summary = summarise_api_calls(action_calls)
        rows.append(
            {
                "action": action,
                "label": labels.get(
                    action,
                    action.replace("_", " ").title(),
                ),
                "note": "",
                "call_count": summary["call_count"],
                "input_tokens": summary["input_tokens"],
                "cached_input_tokens": summary["cached_input_tokens"],
                "output_tokens": summary["output_tokens"],
                "total_tokens": summary["total_tokens"],
                "elapsed_seconds": summary["elapsed_seconds"],
                "estimated_total_cost_usd": (
                    summary["estimated_total_cost_usd"]
                ),
                "unknown_cost_call_count": (
                    summary["unknown_cost_call_count"]
                ),
                "cost_estimate_complete": (
                    summary["cost_estimate_complete"]
                ),
            }
        )

    existing = {row["action"] for row in rows}

    for item in zero_actions or []:
        action = str(item.get("action") or "").strip()
        if not action or action in existing:
            continue

        rows.append(
            {
                "action": action,
                "label": str(
                    item.get("label")
                    or labels.get(
                        action,
                        action.replace("_", " ").title(),
                    )
                ),
                "note": str(item.get("note") or ""),
                "call_count": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "elapsed_seconds": 0.0,
                "estimated_total_cost_usd": 0.0,
                "unknown_cost_call_count": 0,
                "cost_estimate_complete": True,
            }
        )

    order = {
        action: index
        for index, action in enumerate(action_order or [])
    }
    rows.sort(
        key=lambda row: (
            order.get(str(row.get("action")), len(order)),
            str(row.get("label") or ""),
        )
    )
    return rows

