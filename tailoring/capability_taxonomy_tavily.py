"""Explicit administrative research transport. Never imported by scoring."""
from __future__ import annotations
import json
import math
import os
from urllib.request import Request, HTTPRedirectHandler, build_opener

ENDPOINT = "https://api.tavily.com/search"
MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Research redirects are disabled")


def _http_transport(request, *, timeout, max_bytes):
    with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Research response size limit")
    return data


class TavilyCapabilityResearchProvider:
    provider_name = "tavily"

    def __init__(self, api_key=None, *, transport=None, timeout_seconds=20):
        self._api_key = str(os.environ.get("TAVILY_API_KEY", "") if api_key is None else api_key).strip()
        if isinstance(timeout_seconds, bool) or not math.isfinite(float(timeout_seconds)) or not 1 <= float(timeout_seconds) <= 30:
            raise ValueError("Timeout must be between 1 and 30 seconds")
        self.timeout = float(timeout_seconds)
        self._transport = transport if transport is not None else _http_transport

    def search(self, query, *, administrative=False, max_results=5):
        if administrative is not True:
            raise PermissionError("Explicit administrative research action required")
        if not self._api_key:
            raise RuntimeError("Research credential unavailable")
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
            raise ValueError("Bounded research query required")
        if type(max_results) is not int or not 1 <= max_results <= 10:
            raise ValueError("Result count must be 1..10")
        body = {"query": query.strip(), "search_depth": "advanced", "max_results": max_results,
                "include_answer": False, "include_raw_content": False}
        request = Request(ENDPOINT, data=json.dumps(body).encode(), method="POST",
                          headers={"Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"})
        try:
            raw = self._transport(request, timeout=self.timeout, max_bytes=MAX_RESPONSE_BYTES)
            if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError()
            payload = json.loads(raw)
            results = payload.get("results")
            if not isinstance(results, list):
                raise ValueError()
            rows = []
            for row in results[:max_results]:
                if not isinstance(row, dict):
                    continue
                clean = lambda key, limit: str(row.get(key) or "").replace(self._api_key, "[redacted]")[:limit]
                rows.append({"title": clean("title", 300), "url": clean("url", 2048),
                             "content": clean("content", 10000), "provider": self.provider_name,
                             "trusted": False})
            return rows
        except Exception:
            raise RuntimeError("Administrative research request failed") from None
