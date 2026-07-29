"""Pure helpers for displaying the latest cost subtotal for an AI action."""

from __future__ import annotations

from typing import Any

from api_cost import summarise_api_calls


def latest_action_invocation(
    calls: list[dict[str, Any]],
    action: str,
) -> dict[str, Any]:
    matching = [
        call
        for call in calls
        if isinstance(call, dict)
        and str(call.get("action") or "") == str(action)
    ]
    if not matching:
        return {
            **summarise_api_calls([]),
            "action": action,
            "captured_at": "",
        }

    captured_at = max(
        str(call.get("captured_at") or "")
        for call in matching
    )
    if captured_at:
        matching = [
            call
            for call in matching
            if str(call.get("captured_at") or "") == captured_at
        ]
    summary = summarise_api_calls(matching)
    return {
        **summary,
        "action": action,
        "captured_at": captured_at,
    }


def build_button_cost_subtotal(
    calls: list[dict[str, Any]],
    actions: list[str],
) -> dict[str, Any]:
    rows = [
        latest_action_invocation(calls, action)
        for action in actions
    ]
    total_cost = sum(
        float(row.get("estimated_total_cost_usd", 0.0) or 0.0)
        for row in rows
    )
    return {
        "actions": rows,
        "call_count": sum(int(row.get("call_count", 0)) for row in rows),
        "input_tokens": sum(int(row.get("input_tokens", 0)) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens", 0)) for row in rows),
        "total_tokens": sum(int(row.get("total_tokens", 0)) for row in rows),
        "estimated_total_cost_usd": round(total_cost, 8),
    }


def format_usd(value: Any) -> str:
    return "${:.6f}".format(float(value or 0.0))
