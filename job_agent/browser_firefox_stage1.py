"""Stage 1 read-only Firefox runner using the *existing* extension adapter stack.

Firefox does not expose Chromium's extension service worker to Playwright.
Selenium/GeckoDriver installs a *temporary*, Firefox-specific Manifest V3 bundle
in a new isolated Firefox session. The add-on opens its read-only probe page;
the runner invokes only the existing extract/scan actions, never autofill.

No persisted browser profile, job-finder/database access, model calls or submission.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from .browser_stage1 import (
    EXTENSION_ROOT,
    Stage1Error,
    _FORM_SHA_JS,
    _ensure_extension_files,
    safe_summary,
    validate_target,
)
from .stage1_fixture import start_fixture

_FIREFOX_BACKGROUND = "agent_background_firefox.js"
_PROBE_PATH = "/agent_probe.html"
_EXTENSION_ROOT_FILES = {
    "agent_probe.html", "agent_probe.js", "agent_background_firefox.js",
    "popup.html", "popup.css", "popup.js", "batch_tabs.js", "content.js",
    "mapping.js", "jd_cleaning.js", "agent_background.js",
}
_MAX_FILE = 2_000_000
_MAX_BUNDLE = 10_000_000


def make_firefox_bundle(extension_dir: Path, destination: Path) -> dict[str, Any]:
    """Package a Firefox-only manifest overlay; do NOT edit Chromium manifest."""
    _ensure_extension_files(extension_dir)
    background_file = extension_dir / _FIREFOX_BACKGROUND
    if not background_file.is_file() or background_file.is_symlink():
        raise Stage1Error("Firefox read-only background script is missing.")
    original = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))
    if original.get("manifest_version") != 3:
        raise Stage1Error("Expected the current Manifest V3 extension.")
    manifest = dict(original)
    manifest["background"] = {"scripts": [_FIREFOX_BACKGROUND]}
    manifest["browser_specific_settings"] = {
        "gecko": {"id": "job-ai-helper-stage1@job-ai-helper.invalid"}
    }
    if (
        manifest.get("permissions") != original.get("permissions")
        or manifest.get("optional_permissions") != original.get("optional_permissions")
        or manifest.get("host_permissions") != original.get("host_permissions")
        or manifest.get("optional_host_permissions") != original.get("optional_host_permissions")
    ):
        raise Stage1Error("Firefox manifest unexpectedly changed extension permissions.")

    files = {}
    for source in extension_dir.rglob("*"):
        relative = source.relative_to(extension_dir)
        # A deliberate allowlist: never ship tests, debug records, arbitrary
        # JSON, user files, backups, secrets, or nested source directories.
        selected = (
            (len(relative.parts) == 1 and relative.name in _EXTENSION_ROOT_FILES)
            or (len(relative.parts) == 2 and relative.parts[0] == "adapters"
                and relative.suffix == ".js" and not relative.name.startswith("."))
        )
        if source.is_symlink():
            raise Stage1Error("Symlink not allowed in Firefox extension directory.")
        if not selected or not source.is_file():
            continue
        data = source.read_bytes()
        if len(data) > _MAX_FILE:
            raise Stage1Error("Firefox extension contains an oversized source file.")
        files[relative.as_posix()] = data
    required = {
        "agent_probe.html", "agent_probe.js", "agent_background_firefox.js",
        "popup.html", "popup.js", "content.js", "mapping.js", "jd_cleaning.js",
        "adapters/registry.js", "adapters/greenhouse.js", "adapters/generic.js",
    }
    if not required.issubset(files):
        raise Stage1Error("Firefox extension bundle is missing an existing adapter or probe dependency.")
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if sum(map(len, files.values())) > _MAX_BUNDLE:
        raise Stage1Error("Firefox extension source bundle exceeds its size limit.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            archive.writestr(path, content)
    return {"manifest": manifest, "file_count": len(files)}


def _probe_window(driver: Any, original_window: str, *, timeout_seconds: int = 18) -> str:
    """Discover the probe tab opened *by the temporary Firefox extension*."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for window in driver.window_handles:
            if window == original_window:
                continue
            try:
                driver.switch_to.window(window)
                url = str(driver.current_url or "")
            except Exception:
                continue
            if re.fullmatch(r"moz-extension://[0-9a-f-]{36}" + re.escape(_PROBE_PATH) + r"/?", url):
                return window
        time.sleep(0.25)
    raise Stage1Error(
        "Firefox did not open the temporary extension's probe tab. "
        "Check Firefox/GeckoDriver extension installation or the extension's background-page errors."
    )


def _call_probe(driver: Any, action: str, value: Any = None) -> Any:
    if action not in {"selectTarget", "hasAccess", "inspect"}:
        raise Stage1Error("Firefox probe action is not read-only and permitted.")
    script = """
    const done = arguments[arguments.length - 1];
    const action = arguments[0];
    const arg = arguments[1];
    const api = window.JobAIStage1Probe;
    if (!api || typeof api[action] !== 'function') { done({ok:false}); return; }
    Promise.resolve().then(() => arg === null ? api[action]() : api[action](arg))
      .then(result => done({ok:true, result}), () => done({ok:false}));
    """
    response = driver.execute_async_script(script, action, value)
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise Stage1Error("Firefox extension probe failed its read-only request.")
    return response.get("result")


def _form_digest(driver: Any) -> str:
    js = (
        "const done=arguments[arguments.length-1]; (" + _FORM_SHA_JS + ")()"
        ".then(value=>done({ok:true,value}),()=>done({ok:false}));"
    )
    answer = driver.execute_async_script(js)
    if not isinstance(answer, dict) or answer.get("ok") is not True:
        raise Stage1Error("Could not calculate a read-only form integrity fingerprint.")
    digest = str(answer.get("value") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise Stage1Error("Unexpected form integrity fingerprint format.")
    return digest


def _install_temp_addon(driver: Any, addon: Path) -> None:
    # Explicitly temporary on either API: never install an unsigned add-on
    # permanently into the user's ordinary Firefox profile.
    if callable(getattr(driver, "install_web_extension", None)):
        driver.install_web_extension(str(addon), permanent=False)
    else:
        driver.install_addon(str(addon), temporary=True)


def inspect_firefox(url: str, *, allowed_host: str = "", fixture: bool = False,
                    permission_timeout_seconds: int = 90,
                    extension_dir: Path = EXTENSION_ROOT) -> dict[str, Any]:
    """Open one approved URL, ask Firefox extension to extract JD & scan fields."""
    host = validate_target(url, allowed_host=allowed_host, fixture=fixture)
    if not 1 <= permission_timeout_seconds <= 300:
        raise Stage1Error("--permission-timeout must be from 1 to 300 seconds.")
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
    except ImportError as exc:
        raise Stage1Error("Install Selenium: python -m pip install -U selenium") from exc
    with tempfile.TemporaryDirectory(prefix="job_ai_stage1_firefox_") as working:
        xpi = Path(working) / "job-ai-helper-stage1-firefox.xpi"
        make_firefox_bundle(extension_dir, xpi)
        options = Options()
        # Always headed: the extension must request explicit permission from the user.
        options.add_argument("-new-instance")
        try:
            driver = webdriver.Firefox(options=options)
        except Exception as exc:
            raise Stage1Error(
                "Firefox/GeckoDriver could not launch. Install Firefox and run "
                "python -m pip install -U selenium (Selenium Manager provisions GeckoDriver)."
            ) from exc
        try:
            driver.set_script_timeout(35)
            driver.set_page_load_timeout(40)
            original_window = driver.current_window_handle
            try:
                _install_temp_addon(driver, xpi)
                probe_window = _probe_window(driver, original_window)
            except Stage1Error:
                raise
            except Exception as exc:
                raise Stage1Error("Firefox could not install the temporary Job AI Helper add-on.") from exc

            driver.switch_to.window(original_window)
            try:
                driver.get(url)
                final_url = driver.current_url
                validate_target(final_url, allowed_host=allowed_host, fixture=fixture)
                before = _form_digest(driver)
            except Stage1Error:
                raise
            except Exception as exc:
                raise Stage1Error("Firefox could not load or inspect the approved target page.") from exc
            # Selenium follows server redirects before we can inspect final_url.
            # Never inspect a redirected host, even if the browser briefly visited it.
            driver.switch_to.window(probe_window)
            try:
                _call_probe(driver, "selectTarget", final_url)
                if not _call_probe(driver, "hasAccess"):
                    print(
                        f"[PERMISSION] In the Firefox probe tab, click 'Grant access' for {host}; "
                        "approve Firefox's site permission prompt.",
                        file=sys.stderr,
                    )
                    deadline = time.monotonic() + permission_timeout_seconds
                    while time.monotonic() < deadline and not _call_probe(driver, "hasAccess"):
                        time.sleep(0.5)
                    if not _call_probe(driver, "hasAccess"):
                        raise Stage1Error("Firefox site permission was not granted; inspection cancelled.")
                raw = _call_probe(driver, "inspect", final_url)
            except Stage1Error:
                raise
            except Exception as exc:
                raise Stage1Error("Firefox extension extraction/scan failed.") from exc
            driver.switch_to.window(original_window)
            try:
                after = _form_digest(driver)
            except Stage1Error:
                raise
            except Exception as exc:
                raise Stage1Error("Could not verify form integrity after Firefox inspection.") from exc
            summary = safe_summary(raw)
            summary["browser"] = "firefox"
            summary["target_host"] = host
            summary["form_state_unchanged"] = before == after
            if fixture and not summary["form_state_unchanged"]:
                raise Stage1Error("Fixture form changed during read-only Firefox inspection.")
            return summary
        finally:
            driver.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    run = parser.add_mutually_exclusive_group(required=True)
    run.add_argument("--fixture", action="store_true", help="Inspect local example application form.")
    run.add_argument("--url", help="HTTPS job application URL; requires explicit host approval.")
    parser.add_argument("--allow-host", default="", help="Exact approved hostname (no wildcard).")
    parser.add_argument("--permission-timeout", type=int, default=90, help="Seconds to approve Firefox site access.")
    parser.add_argument("--json", action="store_true", help="Print redacted field diagnostics.")
    args = parser.parse_args(argv)
    server = None
    thread = None
    try:
        if args.fixture:
            if args.allow_host:
                raise Stage1Error("--allow-host is not needed for fixture mode.")
            server, thread, target = start_fixture()
        else:
            if not args.allow_host:
                raise Stage1Error("Live URL requires --allow-host.")
            target = args.url
        result = inspect_firefox(
            target, allowed_host=args.allow_host, fixture=args.fixture,
            permission_timeout_seconds=args.permission_timeout,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("[STAGE1 FIREFOX]", result["status"])
            for key in ("adapter", "job_title", "capture_quality", "mapped_field_count", "visible_control_count", "form_state_unchanged"):
                print(f"  {key}: {result.get(key)}")
        return 0
    except Stage1Error as exc:
        print("[FAILED]", exc, file=sys.stderr)
        return 2
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
