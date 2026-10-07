from __future__ import annotations

import json
import os
from copy import deepcopy
from collections.abc import Callable, Iterable
from typing import Any
from urllib import error, request

from database.tavily_usage_manager import record_tavily_usage


TAVILY_RESEARCH_VERSION = "tqd3-tavily-research-adapter-v1.0.0"
TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
TAVILY_API_KEY_ENV = "TAVILY_API_KEY"
DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BATCH_TARGETS = 10

_FORBIDDEN_INTERNAL_DECISION_PHRASES = (
    "should it be represented in the technology registry",
    "should the known technology",
    "materially distinct from the existing canonical taxonomy",
)


def _validate_external_only_question(question: str) -> None:
    normalized = " ".join(question.lower().split())
    for phrase in _FORBIDDEN_INTERNAL_DECISION_PHRASES:
        if phrase in normalized:
            raise ValueError(
                "research_question asks Tavily to make an internal governance "
                f"decision: {phrase}"
            )


class TavilyResearchError(RuntimeError):
    """Raised when a Tavily research request cannot be completed safely."""


Transport = Callable[
    [str, dict[str, Any], dict[str, str], float],
    dict[str, Any],
]


def tavily_api_key_from_env() -> str:
    return str(os.environ.get(TAVILY_API_KEY_ENV) or "").strip()


def build_tavily_search_request(
    target: dict[str, Any],
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ValueError("target must be a dictionary")

    target_id = str(target.get("target_id") or "").strip()
    if not target_id:
        raise ValueError("target_id is required")

    if not bool(target.get("tavily_eligible", False)):
        raise ValueError(
            f"Research target {target_id} is not Tavily-eligible"
        )

    research_question = str(
        target.get("research_question") or ""
    ).strip()
    if not research_question:
        raise ValueError(
            f"Research target {target_id} has no research_question"
        )

    _validate_external_only_question(research_question)

    if not 1 <= int(max_results) <= 20:
        raise ValueError("max_results must be between 1 and 20")

    provider_query = str(
        target.get("search_query") or research_question
    ).strip()
    if not provider_query:
        raise ValueError(
            f"Research target {target_id} has no provider query"
        )

    payload = {
        "query": provider_query,
        "search_depth": "basic",
        "max_results": int(max_results),
        "topic": "general",
        "include_answer": True,
        "include_raw_content": False,
        "include_images": False,
        "include_favicon": False,
        "include_usage": True,
        "safe_search": True,
    }
    if target.get("research_profile") == "first_party_definition_rescue_v1":
        payload.update(search_depth="advanced", include_raw_content="text")
        domains = target.get("include_domains") or []
        if domains:
            payload["include_domains"] = list(domains)
    return payload


def _default_transport(
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    encoded = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=encoded,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(
            req,
            timeout=float(timeout_seconds),
        ) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise TavilyResearchError(
            f"Tavily HTTP {exc.code}: {detail}"
        ) from exc
    except error.URLError as exc:
        raise TavilyResearchError(
            f"Tavily network error: {exc.reason}"
        ) from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TavilyResearchError(
            "Tavily returned invalid JSON"
        ) from exc

    if not isinstance(parsed, dict):
        raise TavilyResearchError(
            "Tavily returned a non-object response"
        )
    return parsed


def _normalise_sources(
    raw_results: Any,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for row in raw_results or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        score = row.get("score")
        sources.append(
            {
                "title": str(row.get("title") or "").strip(),
                "url": url,
                "content": str(row.get("content") or "").strip(),
                "score": (
                    float(score)
                    if isinstance(score, (int, float))
                    else None
                ),
            }
        )
    return sources


def normalise_tavily_search_response(
    *,
    target: dict[str, Any],
    request_payload: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise TavilyResearchError(
            "Tavily response must be a dictionary"
        )

    target_id = str(target.get("target_id") or "").strip()
    sources = _normalise_sources(response.get("results"))

    return {
        "research_version": TAVILY_RESEARCH_VERSION,
        "provider": "tavily",
        "endpoint": "search",
        "target_id": target_id,
        "target_type": str(target.get("target_type") or ""),
        "target_key": str(target.get("target_key") or ""),
        "target_label": str(target.get("label") or ""),
        "research_question": str(
            target.get("research_question") or ""
        ),
        "research_question_version": str(
            target.get("research_question_version") or ""
        ),
        "research_profile": str(
            target.get("research_profile") or ""
        ),
        "requested_facts": list(
            target.get("requested_facts") or []
        ),
        "query": str(
            response.get("query")
            or request_payload.get("query")
            or ""
        ),
        "provider_query": str(
            request_payload.get("query") or ""
        ),
        "research_query_version": str(
            target.get("research_query_version") or ""
        ),
        "answer": (
            str(response.get("answer"))
            if response.get("answer") is not None
            else None
        ),
        "sources": sources,
        "source_count": len(sources),
        "provider_request_id": str(
            response.get("request_id") or ""
        ),
        "provider_response_time": response.get("response_time"),
        "usage": (
            response.get("usage")
            if isinstance(response.get("usage"), dict)
            else {}
        ),
        "request": {
            "search_depth": request_payload.get("search_depth"),
            "max_results": request_payload.get("max_results"),
            "topic": request_payload.get("topic"),
            "include_answer": request_payload.get(
                "include_answer"
            ),
        },
        "governance": {
            "untrusted_research": True,
            "requires_human_review": True,
            "proposal_only": True,
            "taxonomy_mutations": 0,
            "registry_mutations": 0,
            "scoring_influence": False,
            "automatic_promotion": False,
        },
    }


def research_target_with_tavily(
    target: dict[str, Any],
    *,
    api_key: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    transport: Transport | None = None,
    preserve_raw_response: bool = False,
) -> dict[str, Any]:
    key = str(api_key or tavily_api_key_from_env()).strip()
    if not key:
        raise TavilyResearchError(
            f"Missing Tavily API key. Set {TAVILY_API_KEY_ENV} "
            "or pass api_key explicitly."
        )

    payload = build_tavily_search_request(
        target,
        max_results=max_results,
    )
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    sender = transport or _default_transport
    response = sender(
        TAVILY_SEARCH_ENDPOINT,
        payload,
        headers,
        float(timeout_seconds),
    )
    result = normalise_tavily_search_response(
        target=target,
        request_payload=payload,
        response=response,
    )
    if preserve_raw_response:
        result["raw_provider_response"] = deepcopy(response)
        result["request_payload"] = deepcopy(payload)

    # Persist only real adapter network calls. Unit/smoke tests pass an
    # explicit custom transport and therefore never touch the local ledger.
    if transport is None:
        try:
            tracking = record_tavily_usage(result)
        except Exception as exc:
            # Usage tracking is supplemental and must never turn a successful
            # research response into a failed research action.
            result["usage_tracking"] = {
                "recorded": False,
                "scope": "local_job_ai_helper_installation",
                "error": str(exc),
            }
        else:
            result["usage_tracking"] = {
                "recorded": True,
                **tracking,
            }
    else:
        result["usage_tracking"] = {
            "recorded": False,
            "scope": "local_job_ai_helper_installation",
            "reason": "custom_transport",
        }

    return result


def research_selected_targets_with_tavily(
    targets: Iterable[dict[str, Any]],
    *,
    selected_target_ids: Iterable[str],
    api_key: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_batch_targets: int = DEFAULT_MAX_BATCH_TARGETS,
    transport: Transport | None = None,
) -> list[dict[str, Any]]:
    ordered_targets = [
        row for row in targets if isinstance(row, dict)
    ]
    by_id = {
        str(row.get("target_id") or ""): row
        for row in ordered_targets
        if str(row.get("target_id") or "")
    }

    selected: list[str] = []
    seen: set[str] = set()
    for raw_id in selected_target_ids:
        target_id = str(raw_id or "").strip()
        if target_id and target_id not in seen:
            seen.add(target_id)
            selected.append(target_id)

    if not selected:
        raise ValueError("Select at least one research target")

    if len(selected) > int(max_batch_targets):
        raise ValueError(
            f"Batch exceeds max_batch_targets={max_batch_targets}"
        )

    missing = [
        target_id
        for target_id in selected
        if target_id not in by_id
    ]
    if missing:
        raise ValueError(
            "Unknown research target ID(s): "
            + ", ".join(sorted(missing))
        )

    results: list[dict[str, Any]] = []
    for target_id in selected:
        target = by_id[target_id]
        if not bool(target.get("tavily_eligible", False)):
            raise ValueError(
                f"Research target {target_id} is not Tavily-eligible"
            )
        results.append(
            research_target_with_tavily(
                target,
                api_key=api_key,
                max_results=max_results,
                timeout_seconds=timeout_seconds,
                transport=transport,
            )
        )
    return results
