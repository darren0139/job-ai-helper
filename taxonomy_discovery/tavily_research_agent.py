"""Tavily Research adapter for broad technology mining."""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from typing import Any, Callable, Iterable
from urllib import error, request

from database.tavily_usage_manager import record_tavily_usage
from taxonomy_discovery.tavily_account_usage import (
    TavilyUsageError,
    fetch_tavily_account_usage,
)

TAVILY_RESEARCH_AGENT_VERSION = "tqd3-tavily-research-agent-v1.0.0"
TAVILY_RESEARCH_ENDPOINT = "https://api.tavily.com/research"
TAVILY_RESEARCH_MODEL = "mini"
TAVILY_RESEARCH_SCHEMA_VERSION = (
    "tqd3-broad-technology-output-schema-v1.0.0"
)
DEFAULT_RESEARCH_TIMEOUT_SECONDS = 30.0
DEFAULT_RESEARCH_POLL_SECONDS = 1.0
DEFAULT_RESEARCH_MAX_WAIT_SECONDS = 120.0
MAX_BROAD_RESEARCH_BATCH_SEEDS = 2

ResearchTransport = Callable[
    [
        str,
        str,
        dict[str, Any] | None,
        dict[str, str],
        float,
    ],
    dict[str, Any],
]


class TavilyResearchAgentError(RuntimeError):
    pass


def tavily_api_key_from_env() -> str | None:
    value = str(os.environ.get("TAVILY_API_KEY") or "").strip()
    return value or None


def broad_technology_output_schema() -> dict[str, Any]:
    # Tavily Research output_schema permits only top-level "properties"
    # and "required". Every named property includes a non-empty description.
    return {
        "properties": {
            "technologies": {
                "type": "array",
                "description": (
                    "Concrete named technologies with broad real-world "
                    "production use in the requested software-engineering "
                    "domain."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "canonical_name": {
                            "type": "string",
                            "description": (
                                "Canonical project, product, platform, "
                                "protocol, runtime, framework, service, or "
                                "technology name."
                            ),
                        },
                        "entity_type": {
                            "type": "string",
                            "description": (
                                "Technology category such as message broker, "
                                "event streaming platform, queue service, "
                                "framework, database, runtime, protocol, or "
                                "developer tool."
                            ),
                        },
                        "primary_purpose": {
                            "type": "string",
                            "description": (
                                "Primary software-engineering purpose or use."
                            ),
                        },
                        "maintainer_vendor_or_standards_body": {
                            "type": "string",
                            "description": (
                                "Maintainer, vendor, foundation, or standards "
                                "body when applicable."
                            ),
                        },
                        "adoption_evidence": {
                            "type": "string",
                            "description": (
                                "Concise evidence indicating broad real-world "
                                "production adoption."
                            ),
                        },
                        "authoritative_source_urls": {
                            "type": "array",
                            "description": (
                                "Authoritative or primary-source URLs that "
                                "support the technology entry."
                            ),
                            "items": {
                                "type": "string",
                            },
                        },
                    },
                    "required": [
                        "canonical_name",
                        "entity_type",
                        "primary_purpose",
                        "adoption_evidence",
                    ],
                },
            }
        },
        "required": ["technologies"],
    }

def _validate_tavily_output_schema(
    schema: dict[str, Any],
) -> None:
    if set(schema) != {"properties", "required"}:
        raise ValueError(
            "Tavily Research output_schema top-level keys must be exactly "
            "'properties' and 'required'"
        )

    def visit_properties(
        properties: Any,
        *,
        path: str,
    ) -> None:
        if not isinstance(properties, dict):
            raise ValueError(
                f"Tavily Research schema properties must be an object at {path}"
            )

        for name, spec in properties.items():
            if not isinstance(spec, dict):
                raise ValueError(
                    f"Tavily Research property {path}.{name} must be an object"
                )

            description = str(spec.get("description") or "").strip()
            if not description:
                raise ValueError(
                    f"Tavily Research property {path}.{name} is missing "
                    "required description"
                )

            nested = spec.get("properties")
            if nested is not None:
                visit_properties(
                    nested,
                    path=f"{path}.{name}",
                )

            items = spec.get("items")
            if isinstance(items, dict):
                nested_items = items.get("properties")
                if nested_items is not None:
                    visit_properties(
                        nested_items,
                        path=f"{path}.{name}[]",
                    )

    visit_properties(
        schema.get("properties"),
        path="output_schema",
    )

def build_broad_research_request(
    seed: dict[str, Any],
    *,
    model: str = TAVILY_RESEARCH_MODEL,
) -> dict[str, Any]:
    target_id = str(seed.get("target_id") or "").strip()
    if not target_id:
        raise ValueError("Broad-mining seed has no target_id")
    if not bool(seed.get("tavily_eligible")):
        raise ValueError(
            f"Broad-mining seed {target_id} is not Tavily eligible"
        )

    research_question = str(
        seed.get("research_question") or ""
    ).strip()
    if not research_question:
        raise ValueError(
            f"Broad-mining seed {target_id} has no research_question"
        )

    model = str(model or "").strip()
    if model not in {"mini", "pro", "auto"}:
        raise ValueError(
            "Tavily Research model must be mini, pro, or auto"
        )

    schema = broad_technology_output_schema()
    _validate_tavily_output_schema(schema)

    return {
        "input": research_question,
        "model": model,
        "stream": False,
        "output_schema": schema,
        "citation_format": "numbered",
        "output_length": "standard",
    }

def _default_transport(
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    data = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )
    req = request.Request(
        endpoint,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TavilyResearchAgentError(
            f"Tavily Research HTTP {exc.code}: {body[:800]}"
        ) from exc
    except error.URLError as exc:
        raise TavilyResearchAgentError(
            f"Tavily Research request failed: {exc.reason}"
        ) from exc

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TavilyResearchAgentError(
            "Tavily Research returned invalid JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise TavilyResearchAgentError(
            "Tavily Research returned a non-object response"
        )
    return decoded


def _call(
    *,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None,
    api_key: str,
    timeout_seconds: float,
    transport: ResearchTransport | None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"

    result = (
        transport(
            method,
            endpoint,
            payload,
            headers,
            timeout_seconds,
        )
        if transport is not None
        else _default_transport(
            method,
            endpoint,
            payload,
            headers,
            timeout_seconds,
        )
    )
    if not isinstance(result, dict):
        raise TavilyResearchAgentError(
            "Tavily Research transport returned a non-object response"
        )
    return result


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise_sources(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = _clean(row.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(
            {
                "title": _clean(row.get("title")),
                "url": url,
                "favicon": _clean(row.get("favicon")),
                "content": "",
                "score": None,
            }
        )
    return result


def _normalise_technologies(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, dict):
        return []
    rows = content.get("technologies")
    if not isinstance(rows, list):
        return []

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _clean(row.get("canonical_name"))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)

        urls = row.get("authoritative_source_urls")
        urls = urls if isinstance(urls, list) else []
        clean_urls: list[str] = []
        url_seen: set[str] = set()
        for value in urls:
            url = _clean(value)
            if url and url not in url_seen:
                url_seen.add(url)
                clean_urls.append(url)

        result.append(
            {
                "canonical_name": name,
                "entity_type": _clean(row.get("entity_type")),
                "primary_purpose": _clean(
                    row.get("primary_purpose")
                ),
                "maintainer_vendor_or_standards_body": _clean(
                    row.get(
                        "maintainer_vendor_or_standards_body"
                    )
                ),
                "adoption_evidence": _clean(
                    row.get("adoption_evidence")
                ),
                "authoritative_source_urls": clean_urls,
            }
        )
    return result


def _key_usage(snapshot: dict[str, Any] | None) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    key = snapshot.get("key")
    if not isinstance(key, dict):
        return None
    value = key.get("usage")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _usage_delta(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> float | None:
    before_value = _key_usage(before)
    after_value = _key_usage(after)
    if before_value is None or after_value is None:
        return None
    return max(0.0, after_value - before_value)


def run_broad_research_with_tavily(
    seed: dict[str, Any],
    *,
    api_key: str | None = None,
    model: str = TAVILY_RESEARCH_MODEL,
    timeout_seconds: float = DEFAULT_RESEARCH_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_RESEARCH_POLL_SECONDS,
    max_wait_seconds: float = DEFAULT_RESEARCH_MAX_WAIT_SECONDS,
    transport: ResearchTransport | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    key = str(api_key or tavily_api_key_from_env() or "").strip()
    if not key:
        raise TavilyResearchAgentError(
            "TAVILY_API_KEY is not configured"
        )

    payload = build_broad_research_request(seed, model=model)

    before_usage = None
    if transport is None:
        try:
            before_usage = fetch_tavily_account_usage(
                api_key=key,
                timeout_seconds=min(timeout_seconds, 20.0),
            )
        except TavilyUsageError:
            before_usage = None

    created = _call(
        method="POST",
        endpoint=TAVILY_RESEARCH_ENDPOINT,
        payload=payload,
        api_key=key,
        timeout_seconds=timeout_seconds,
        transport=transport,
    )
    request_id = _clean(created.get("request_id"))
    if not request_id:
        raise TavilyResearchAgentError(
            "Tavily Research did not return a request_id"
        )

    deadline = time.monotonic() + max(1.0, float(max_wait_seconds))
    completed = None
    while time.monotonic() < deadline:
        status_row = _call(
            method="GET",
            endpoint=f"{TAVILY_RESEARCH_ENDPOINT}/{request_id}",
            payload=None,
            api_key=key,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )
        status = _clean(status_row.get("status")).lower()
        if status == "completed":
            completed = status_row
            break
        if status == "failed":
            raise TavilyResearchAgentError(
                "Tavily Research task failed: "
                + _clean(
                    status_row.get("error")
                    or status_row.get("detail")
                )
            )
        if status not in {
            "",
            "pending",
            "queued",
            "in_progress",
        }:
            raise TavilyResearchAgentError(
                f"Unexpected Tavily Research status: {status!r}"
            )
        sleep_fn(max(0.0, float(poll_seconds)))

    if completed is None:
        raise TavilyResearchAgentError(
            "Tavily Research task did not complete before timeout "
            f"(request_id={request_id})"
        )

    content = completed.get("content")
    technologies = _normalise_technologies(content)
    sources = _normalise_sources(completed.get("sources"))

    after_usage = None
    credits_delta = None
    if transport is None:
        try:
            after_usage = fetch_tavily_account_usage(
                api_key=key,
                timeout_seconds=min(timeout_seconds, 20.0),
            )
        except TavilyUsageError:
            after_usage = None
        credits_delta = _usage_delta(
            before_usage,
            after_usage,
        )

    result: dict[str, Any] = {
        "research_agent_version": TAVILY_RESEARCH_AGENT_VERSION,
        "provider": "tavily",
        "endpoint": "research",
        "provider_request_id": request_id,
        "research_model": model,
        "research_schema_version": TAVILY_RESEARCH_SCHEMA_VERSION,
        "target_id": _clean(seed.get("target_id")),
        "target_type": _clean(seed.get("target_type")),
        "target_key": _clean(seed.get("target_key")),
        "target_label": _clean(
            seed.get("label") or seed.get("target_label")
        ),
        "seed_id": _clean(seed.get("seed_id")),
        "domain": _clean(seed.get("domain")),
        "scope": _clean(seed.get("scope")),
        "research_question": _clean(
            seed.get("research_question")
        ),
        "research_question_version": _clean(
            seed.get("research_question_version")
        ),
        "query": _clean(seed.get("research_question")),
        "provider_query": _clean(seed.get("research_question")),
        "answer": deepcopy(content),
        "structured_output": {
            "technologies": technologies,
        },
        "technology_count": len(technologies),
        "sources": sources,
        "source_count": len(sources),
        "provider_content": deepcopy(content),
        "provider_response_time": completed.get("response_time"),
        "request": {
            "model": model,
            "stream": False,
            "citation_format": "numbered",
            "output_length": "standard",
            "research_schema_version": TAVILY_RESEARCH_SCHEMA_VERSION,
        },
        "usage": {
            "credits": credits_delta,
            "basis": (
                "official_key_usage_delta"
                if credits_delta is not None
                else "unavailable"
            ),
            "approximate": credits_delta is not None,
        },
        "official_usage_before": before_usage,
        "official_usage_after": after_usage,
        "governance": {
            "untrusted_research": True,
            "requires_human_review": True,
            "proposal_only": True,
            "candidate_extraction": False,
            "taxonomy_mutations": 0,
            "registry_mutations": 0,
            "scoring_influence": False,
            "automatic_promotion": False,
        },
    }

    if transport is None and credits_delta is not None:
        try:
            tracking = record_tavily_usage(result)
        except Exception as exc:
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
            "reason": (
                "custom_transport"
                if transport is not None
                else "official_usage_delta_unavailable"
            ),
        }

    return result


def research_selected_broad_mining_with_tavily(
    seeds: Iterable[dict[str, Any]],
    *,
    selected_seed_ids: Iterable[str],
    api_key: str | None = None,
    model: str = TAVILY_RESEARCH_MODEL,
    transport: ResearchTransport | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in seeds
        if isinstance(row, dict)
        and _clean(row.get("seed_id"))
    ]
    by_id = {
        _clean(row["seed_id"]): row
        for row in rows
    }

    selected: list[str] = []
    seen: set[str] = set()
    for raw in selected_seed_ids:
        seed_id = _clean(raw)
        if seed_id and seed_id not in seen:
            seen.add(seed_id)
            selected.append(seed_id)

    if not selected:
        raise ValueError(
            "Select at least one broad-mining seed domain."
        )
    if len(selected) > MAX_BROAD_RESEARCH_BATCH_SEEDS:
        raise ValueError(
            "Tavily Research broad-mining batch exceeds safety "
            f"limit {MAX_BROAD_RESEARCH_BATCH_SEEDS}."
        )

    missing = [
        seed_id
        for seed_id in selected
        if seed_id not in by_id
    ]
    if missing:
        raise ValueError(
            "Unknown broad-mining seed ID(s): "
            + ", ".join(sorted(missing))
        )

    return [
        run_broad_research_with_tavily(
            deepcopy(by_id[seed_id]),
            api_key=api_key,
            model=model,
            transport=transport,
            sleep_fn=sleep_fn,
        )
        for seed_id in selected
    ]
