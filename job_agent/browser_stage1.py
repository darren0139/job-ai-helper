"""Stage 1 browser agent: drive the installed extension's read-only actions.

No Job Finder/DB calls, profile loading, autofill, form clicks or submissions.
Bundled Chromium is isolated in an ephemeral browser profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .stage1_fixture import start_fixture

EXTENSION_ROOT = Path(__file__).resolve().parents[1] / "browser_extension"
_EXPECTED_CONTENT_VERSION = "browser-content-v4.2"
_MAX_FIELDS = 40


class Stage1Error(RuntimeError):
    """Expected fail-closed condition, safe to report to the terminal."""


def validate_target(url: str, *, allowed_host: str = "", fixture: bool = False) -> str:
    """Require explicit hostname approval; localhost is reserved for fixture mode."""
    raw = str(url or "").strip()
    if not raw or any(ord(char) < 33 for char in raw):
        raise Stage1Error("A single absolute URL without whitespace is required.")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise Stage1Error("Malformed target URL.") from exc
    host = (parsed.hostname or "").lower()
    if not host or parsed.username or parsed.password or parsed.fragment or parsed.scheme not in {"http", "https"}:
        raise Stage1Error("Unsupported target URL format (credentials and fragments forbidden).")
    if host.endswith(".") or "*" in host or "\\" in raw or (parsed.netloc and "@" in parsed.netloc):
        raise Stage1Error("Unsafe hostname or URL syntax.")
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        raise Stage1Error("Only ASCII/DNS hostnames are supported in Stage 1.")
    if fixture:
        if parsed.scheme != "http" or host != "127.0.0.1" or not port:
            raise Stage1Error("Fixture must use the local 127.0.0.1 test server.")
    else:
        if parsed.scheme != "https" or host in {"localhost", "127.0.0.1"}:
            raise Stage1Error("Live navigation requires HTTPS and a non-local host.")
        allow = str(allowed_host or "").lower().strip()
        if not allow or allow != host:
            raise Stage1Error("--allow-host must exactly match the target hostname.")
    return host


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop full JD, URL query, labels, nearby text and candidate/form values."""
    if not isinstance(raw, dict) or raw.get("ok") is not True:
        raise Stage1Error("Extension returned an unsuccessful inspection.")
    if raw.get("content_version") != _EXPECTED_CONTENT_VERSION:
        raise Stage1Error("Extension content script version mismatch.")
    extraction = _as_dict(raw.get("extraction"))
    scan = _as_dict(raw.get("scan"))
    source = _as_dict(extraction.get("source"))
    job = _as_dict(extraction.get("job"))
    fields = scan.get("fields")
    if not isinstance(fields, list):
        raise Stage1Error("Extension field scan response was missing.")
    if not isinstance(source.get("site_adapter"), str) or not source.get("site_adapter"):
        raise Stage1Error("Extension job extraction did not identify an adapter.")
    if str(scan.get("site_adapter") or "") != str(source.get("site_adapter")):
        raise Stage1Error("Extraction and field scan used different adapters.")
    limited_fields = []
    for field in fields[:_MAX_FIELDS]:
        item = _as_dict(field)
        limited_fields.append({
            "kind": str(item.get("kind") or "")[:24],
            "visible": item.get("visible") is True,
            "required": item.get("required") is True,
            "matched_key": str(item.get("matched_key") or "")[:64] or None,
        })
    title = str(job.get("job_title") or "").strip()
    company = str(job.get("company") or "").strip()
    return {
        "status": "inspected_read_only",
        "content_version": raw["content_version"],
        "adapter": str(source.get("site_adapter"))[:60],
        "adapter_version": str(source.get("site_adapter_version") or "")[:100],
        "job_title": title[:180],
        "company": company[:180],
        "jd_character_count": max(0, int(job.get("jd_character_count") or 0)),
        "capture_quality": str(job.get("capture_quality") or "")[:40],
        "availability_status": str(job.get("availability_status") or "")[:40],
        "standard_control_count": max(0, int(scan.get("standard_control_count") or 0)),
        "visible_control_count": max(0, int(scan.get("visible_standard_control_count") or 0)),
        "mapped_field_count": max(0, int(scan.get("mapped_field_count") or 0)),
        "unmatched_visible_count": max(0, int(scan.get("unmatched_visible_count") or 0)),
        "sample_fields": limited_fields,
        "field_sample_truncated": len(fields) > _MAX_FIELDS,
        "writes": 0,
        "model_calls": 0,
        "autofill_calls": 0,
        "submission_calls": 0,
    }


_FORM_SHA_JS = r"""async () => {
  const elements = [...document.querySelectorAll('input, select, textarea')];
  const state = elements.map(e => [e.tagName, e.type, e.value, Boolean(e.checked),
    e.selectedIndex ?? -1]);
  const data = new TextEncoder().encode(JSON.stringify(state));
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', data));
  return [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
}"""


def _extension_id(context: Any) -> str:
    workers = list(context.service_workers)
    if not workers:
        try:
            workers = [context.wait_for_event("serviceworker", timeout=15000)]
        except Exception as exc:
            raise Stage1Error(
                "Could not find Job AI Helper extension service worker. "
                "Install Playwright Chromium and check extension loading."
            ) from exc
    for worker in workers:
        candidate = urlsplit(worker.url)
        if candidate.scheme == "chrome-extension" and re.fullmatch(r"[a-p]{32}", candidate.hostname or ""):
            return str(candidate.hostname)
    raise Stage1Error("Unexpected extension worker URL; agent refuses to inspect tabs.")


def _ensure_extension_files(extension_dir: Path) -> None:
    required = ("manifest.json", "agent_background.js", "agent_probe.html", "agent_probe.js", "content.js", "popup.js")
    if not all((extension_dir / file).is_file() for file in required):
        raise Stage1Error("Stage 1 extension files are missing; run the patch installer first.")
    manifest = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("background", {}).get("service_worker") != "agent_background.js":
        raise Stage1Error("Unexpected extension manifest; agent will not load it.")
    if set(manifest.get("host_permissions", [])) != {"http://127.0.0.1/*", "http://localhost/*"}:
        raise Stage1Error("Extension has unexpected mandatory host permissions.")


def inspect_browser(url: str, *, allowed_host: str = "", fixture: bool = False,
                    headless: bool = False, permission_timeout_ms: int = 90000,
                    extension_dir: Path = EXTENSION_ROOT) -> dict[str, Any]:
    host = validate_target(url, allowed_host=allowed_host, fixture=fixture)
    if headless and not fixture:
        raise Stage1Error("Headless live inspection is disabled: site permission needs visible review.")
    _ensure_extension_files(extension_dir)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise Stage1Error("Install Playwright: python -m pip install playwright") from exc

    with tempfile.TemporaryDirectory(prefix="job_ai_stage1_chromium_") as profile:
        with sync_playwright() as playwright:
            try:
                context = playwright.chromium.launch_persistent_context(
                    profile,
                    channel="chromium",
                    headless=headless,
                    accept_downloads=False,
                    args=[
                        f"--disable-extensions-except={extension_dir.resolve()}",
                        f"--load-extension={extension_dir.resolve()}",
                    ],
                )
            except Exception as exc:
                raise Stage1Error(
                    "Chromium could not launch. Run: python -m playwright install chromium"
                ) from exc
            try:
                extension_id = _extension_id(context)
                page = context.new_page()
                page.set_default_timeout(20000)

                def navigation_guard(route: Any) -> None:
                    request = route.request
                    if request.is_navigation_request() and request.frame == page.main_frame:
                        try:
                            validate_target(request.url, allowed_host=allowed_host, fixture=fixture)
                        except Stage1Error:
                            route.abort()
                            return
                    route.continue_()

                page.route("**/*", navigation_guard)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as exc:
                    raise Stage1Error("Target page could not load or redirected outside its approved host.") from exc
                final_url = page.url
                validate_target(final_url, allowed_host=allowed_host, fixture=fixture)
                if urlsplit(final_url).hostname != host:
                    raise Stage1Error("Job page navigated to a different hostname.")

                before = page.evaluate(_FORM_SHA_JS)
                probe = context.new_page()
                probe.goto(f"chrome-extension://{extension_id}/agent_probe.html", wait_until="load")
                probe.evaluate("(url) => window.JobAIStage1Probe.selectTarget(url)", final_url)
                if not probe.evaluate("() => window.JobAIStage1Probe.hasAccess()"):
                    print(f"[PERMISSION] In Chromium, approve access to {host} in the Job AI Stage 1 probe tab.", file=sys.stderr)
                    probe.bring_to_front()
                    try:
                        probe.wait_for_function(
                            "() => window.JobAIStage1Probe.hasAccess()",
                            timeout=permission_timeout_ms,
                        )
                    except Exception as exc:
                        raise Stage1Error("Site permission not granted before timeout; no inspection performed.") from exc
                try:
                    raw = probe.evaluate("(url) => window.JobAIStage1Probe.inspect(url)", final_url)
                except Exception as exc:
                    # Do not print the underlying page error, which may include sensitive data.
                    raise Stage1Error("Extension extraction or field scan failed; check the site and adapter.") from exc
                after = page.evaluate(_FORM_SHA_JS)
                summary = safe_summary(raw)
                summary["form_state_unchanged"] = before == after
                summary["target_host"] = host
                if fixture and not summary["form_state_unchanged"]:
                    raise Stage1Error("Fixture form values changed during read-only inspection.")
                return summary
            finally:
                context.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    run = parser.add_mutually_exclusive_group(required=True)
    run.add_argument("--fixture", action="store_true", help="Inspect a local deterministic test job page.")
    run.add_argument("--url", help="HTTPS job page URL; requires --allow-host and site consent.")
    parser.add_argument("--allow-host", default="", help="Exact approved hostname for a live URL (no wildcards).")
    parser.add_argument("--headless", action="store_true", help="Supported only for the local fixture.")
    parser.add_argument("--json", action="store_true", help="Print redacted JSON field diagnostics.")
    args = parser.parse_args(argv)
    server = None
    thread = None
    try:
        if args.fixture:
            if args.allow_host:
                raise Stage1Error("--allow-host is not needed for the fixture.")
            server, thread, url = start_fixture()
        else:
            if not args.allow_host:
                raise Stage1Error("Live URLs require explicit --allow-host hostname.")
            url = str(args.url)
        output = inspect_browser(url, allowed_host=args.allow_host,
                                 fixture=args.fixture, headless=args.headless)
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print("[STAGE1] Extension read-only inspection: PASS")
            for key in ("target_host", "adapter", "job_title", "company", "jd_character_count",
                        "capture_quality", "standard_control_count", "visible_control_count",
                        "mapped_field_count", "unmatched_visible_count", "form_state_unchanged"):
                print(f"[{key.upper()}] {output.get(key)}")
            print("[SAFETY] No autofill, navigation clicks, application submission, DB writes or model calls")
        return 0
    except (Stage1Error, OSError, ValueError) as exc:
        print(f"[STAGE1_FAIL] {exc}", file=sys.stderr)
        return 2
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
