"""Token-protected localhost bridge for the Job AI Helper browser extension."""

from __future__ import annotations

import argparse
import json
import os
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from database.application_profile_manager import get_application_profile
from database.browser_bridge_settings import get_or_create_browser_bridge_token
from database.browser_capture_manager import (
    list_browser_job_captures,
    save_browser_job_capture,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY_BYTES = 2_000_000
TOKEN_HEADER = "X-Job-AI-Bridge-Token"


def _allowed_extension_origin(origin: str) -> bool:
    value = str(origin or "").strip().lower()
    return value.startswith("chrome-extension://")


class JobAIBridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], token: str):
        super().__init__(server_address, JobAIBridgeHandler)
        self.bridge_token = token


class JobAIBridgeHandler(BaseHTTPRequestHandler):
    server: JobAIBridgeServer

    def log_message(self, format: str, *args: object) -> None:
        print(f"[browser-bridge] {self.address_string()} - {format % args}")

    def _origin(self) -> str:
        return str(self.headers.get("Origin") or "").strip()

    def _send_json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        allow_origin: bool = True,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")

        origin = self._origin()
        if allow_origin and _allowed_extension_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

        self.end_headers()
        self.wfile.write(body)

    def _authorised(self) -> bool:
        supplied = str(self.headers.get(TOKEN_HEADER) or "")
        return secrets.compare_digest(supplied, self.server.bridge_token)

    def _require_extension_origin(self) -> bool:
        origin = self._origin()
        # Empty Origin is allowed for local command-line diagnostics/tests.
        return not origin or _allowed_extension_origin(origin)

    def _guard(self) -> bool:
        if not self._require_extension_origin():
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {"ok": False, "error": "Browser bridge accepts extension origins only."},
                allow_origin=False,
            )
            return False

        if not self._authorised():
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": "Invalid or missing browser bridge token."},
            )
            return False
        return True

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError as exc:
            raise ValueError("Invalid Content-Length.") from exc

        if length <= 0:
            raise ValueError("JSON body is required.")
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body exceeds local bridge limit.")

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be valid UTF-8 JSON.") from exc

        if not isinstance(payload, dict):
            raise ValueError("Request JSON must be an object.")
        return payload

    def do_OPTIONS(self) -> None:
        origin = self._origin()
        if not _allowed_extension_origin(origin):
            self.send_response(HTTPStatus.FORBIDDEN)
            self.end_headers()
            return

        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            f"Content-Type, {TOKEN_HEADER}",
        )
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/health":
            if not self._guard():
                return
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "job-ai-helper-browser-bridge",
                    "version": 2,
                },
            )
            return

        if not self._guard():
            return

        if path == "/api/v1/application-profile":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "application_profile": get_application_profile(),
                },
            )
            return

        if path == "/api/v1/jd-captures/latest":
            captures = list_browser_job_captures(limit=1)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "capture": captures[0] if captures else None,
                },
            )
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": "Unknown bridge endpoint."},
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if not self._guard():
            return

        if path == "/api/v1/jd-captures":
            try:
                payload = self._read_json_body()
                saved = save_browser_job_capture(payload)
            except ValueError as exc:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": str(exc)},
                )
                return

            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "action": "browser_jd_capture_saved",
                    "capture": {
                        "id": saved.get("id"),
                        "status": saved.get("status"),
                        "job_title": saved.get("job_title"),
                        "company": saved.get("company"),
                        "source_url": saved.get("source_url"),
                        "extraction_strategy": saved.get("extraction_strategy"),
                    },
                    "note": (
                        "Saved as a pending browser capture only. "
                        "No LLM analysis or canonical JD write was performed."
                    ),
                },
            )
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": "Unknown bridge endpoint."},
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local Job AI Helper browser bridge."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--token",
        default=os.getenv("JOB_AI_BROWSER_BRIDGE_TOKEN", ""),
        help=(
            "Optional fixed token. If omitted, a random token is generated for "
            "this bridge process."
        ),
    )
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    token = str(args.token or "").strip() or get_or_create_browser_bridge_token()
    server = JobAIBridgeServer((DEFAULT_HOST, args.port), token)

    print("Job AI Helper browser bridge")
    print(f"Listening: http://{DEFAULT_HOST}:{args.port}")
    print(f"Bridge token: {token}")
    print("This token is stable across local restarts until you rotate it in Streamlit.")
    print("Paste it into the browser extension only when pairing is required.")
    print("The bridge accepts extension-origin requests on localhost only.")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping browser bridge.")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
