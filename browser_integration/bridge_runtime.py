"""Lifecycle wrapper for the local browser bridge HTTP server."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from browser_integration.bridge_server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    JobAIBridgeServer,
)
from database.browser_bridge_settings import get_or_create_browser_bridge_token


@dataclass
class BrowserBridgeRuntime:
    server: JobAIBridgeServer
    thread: threading.Thread
    host: str
    port: int
    token: str
    started_at: str

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def is_alive(self) -> bool:
        return self.thread.is_alive()

    def update_token(self, token: str) -> None:
        cleaned = str(token or "").strip()
        if not cleaned:
            raise ValueError("Browser bridge token cannot be empty.")
        self.server.bridge_token = cleaned
        self.token = cleaned

    def stop(self) -> None:
        if self.is_alive:
            self.server.shutdown()
        self.server.server_close()
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)


def start_browser_bridge_runtime(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    token: str = "",
) -> BrowserBridgeRuntime:
    """Start one daemon bridge thread and return its runtime handle."""
    effective_token = str(token or "").strip() or get_or_create_browser_bridge_token()
    server = JobAIBridgeServer((host, int(port)), effective_token)
    actual_host, actual_port = server.server_address[:2]

    thread = threading.Thread(
        target=server.serve_forever,
        name="job-ai-helper-browser-bridge",
        daemon=True,
    )
    thread.start()

    return BrowserBridgeRuntime(
        server=server,
        thread=thread,
        host=str(actual_host),
        port=int(actual_port),
        token=effective_token,
        started_at=datetime.now().isoformat(timespec="seconds"),
    )
