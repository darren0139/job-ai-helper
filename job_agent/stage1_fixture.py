"""Deterministic local-only HTML fixture for read-only browser inspection."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

FIXTURE_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Platform Engineer — Example Careers</title></head>
<body>
<main>
  <h1>Platform Engineer</h1>
  <p>Example Careers — Singapore</p>
  <section><h2>Responsibilities</h2><p>
    Build reliable Python services and maintain stable API integrations.
    Work with teammates to design, test, document and improve software systems.
    Implement observability, review code and troubleshoot production issues.
    Maintain automated tests and versioned build pipelines with a strong focus on quality.
    Collaborate across teams to deliver secure, well-tested backend features.
  </p></section>
  <section><h2>Requirements</h2><p>
    Experience programming in Python, familiarity with relational databases,
    software testing and Git. Clear communication and thoughtful debugging.
  </p></section>
  <form id="application" onsubmit="event.preventDefault()">
    <h2>Application</h2>
    <label for="fname">First name</label><input id="fname" name="first_name" required>
    <label for="lname">Last name</label><input id="lname" name="last_name" required>
    <label for="email">Email address</label><input id="email" type="email" name="email" required>
    <input type="hidden" name="internal_tracking" value="fixture-token">
    <button type="submit">Submit (disabled in Stage 1)</button>
  </form>
</main>
</body></html>"""


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", "/jobs/platform-engineer"):
            self.send_error(404)
            return
        payload = FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:
        pass


def start_fixture() -> tuple[ThreadingHTTPServer, Thread, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/jobs/platform-engineer"
