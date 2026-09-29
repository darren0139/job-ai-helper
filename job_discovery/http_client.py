from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class JobSourceError(RuntimeError):
    pass


class JsonHttpClient:
    def __init__(
        self,
        *,
        timeout: float = 25.0,
        user_agent: str = "JobAIHelper/1.0 (personal job discovery)",
        sleep_fn=time.sleep,
    ) -> None:
        self.timeout = float(timeout)
        self.user_agent = str(user_agent)
        self.sleep_fn = sleep_fn

    def _request(self, request: Request) -> Any:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            raise JobSourceError(
                f"HTTP {exc.code} for {request.full_url}: {body or exc.reason}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise JobSourceError(f"Request failed for {request.full_url}: {exc}") from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise JobSourceError(
                f"Expected JSON from {request.full_url}, received invalid payload."
            ) from exc

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        target = str(url)
        if params:
            encoded = urlencode(
                [(key, value) for key, value in params.items() if value is not None],
                doseq=True,
            )
            target += ("&" if "?" in target else "?") + encoded
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
        }
        request_headers.update(headers or {})
        return self._request(Request(target, headers=request_headers, method="GET"))

    def post_json(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        target = str(url)
        if params:
            target += "?" + urlencode(
                [(key, value) for key, value in params.items() if value is not None],
                doseq=True,
            )
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
        }
        request_headers.update(headers or {})
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self._request(
            Request(target, headers=request_headers, data=data, method="POST")
        )

    def pause(self, seconds: float) -> None:
        if seconds > 0:
            self.sleep_fn(float(seconds))
