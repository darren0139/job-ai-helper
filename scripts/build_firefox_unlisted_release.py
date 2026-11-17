#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser_extension"
DIST = ROOT / "dist" / "browser_extension" / "firefox"
CHROME = EXT / "manifest.json"
FIREFOX = EXT / "manifest.firefox.json"

EXPECTED_ID = "job-ai-helper-browser@job-ai-helper.local"
REQUIRED_DATA = {
    "authenticationInfo",
    "browsingActivity",
    "personallyIdentifyingInfo",
    "websiteContent",
}
COMMON_KEYS = (
    "manifest_version",
    "name",
    "version",
    "description",
    "permissions",
    "optional_permissions",
    "host_permissions",
    "optional_host_permissions",
    "action",
)
BASE_RUNTIME = {
    "popup.html",
    "popup.css",
    "popup.js",
    "batch_tabs.js",
    "content.js",
    "mapping.js",
    "jd_cleaning.js",
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object.")
    return value


def _version(value: Any) -> tuple[int, ...]:
    raw = str(value or "").strip()
    if not raw or not all(part.isdigit() for part in raw.split(".")):
        return ()
    return tuple(int(part) for part in raw.split("."))


def _runtime_files() -> set[str]:
    files = set(BASE_RUNTIME)
    html = (EXT / "popup.html").read_text(encoding="utf-8")
    popup = (EXT / "popup.js").read_text(encoding="utf-8")

    for value in re.findall(
        r'(?:src|href)=["\']([^"\']+\.(?:js|css))["\']',
        html,
        flags=re.IGNORECASE,
    ):
        if "://" not in value:
            files.add(value.lstrip("./"))

    for value in re.findall(
        r'"((?:adapters/)?[A-Za-z0-9_.\-/]+\.js)"',
        popup,
    ):
        files.add(value.lstrip("./"))

    adapters = EXT / "adapters"
    if adapters.is_dir():
        for path in adapters.glob("*.js"):
            files.add(path.relative_to(EXT).as_posix())

    return files


def release_members() -> list[tuple[str, Path]]:
    members = [("manifest.json", FIREFOX)]
    members.extend(
        (name, EXT / name)
        for name in sorted(_runtime_files())
    )
    return members


def validate_release_inputs() -> dict[str, Any]:
    chrome = _json(CHROME)
    firefox = _json(FIREFOX)

    if firefox.get("manifest_version") != 3:
        raise RuntimeError("Firefox release manifest must be Manifest V3.")

    for key in COMMON_KEYS:
        if firefox.get(key) != chrome.get(key):
            raise RuntimeError(
                f"Chrome/Firefox manifest drift for common key {key!r}."
            )

    gecko = firefox.get("browser_specific_settings", {}).get("gecko", {})
    if not isinstance(gecko, dict):
        raise RuntimeError("Missing browser_specific_settings.gecko.")

    if gecko.get("id") != EXPECTED_ID:
        raise RuntimeError("Unexpected Firefox add-on ID.")

    if _version(gecko.get("strict_min_version")) < (142, 0):
        raise RuntimeError("strict_min_version must be 142.0 or newer.")

    data = gecko.get("data_collection_permissions", {})
    required = set(data.get("required", [])) if isinstance(data, dict) else set()
    if "none" in required:
        raise RuntimeError(
            "Firefox manifest still claims required data collection 'none'."
        )
    missing = REQUIRED_DATA - required
    if missing:
        raise RuntimeError(
            "Missing Firefox data disclosures: "
            + ", ".join(sorted(missing))
        )

    if set(firefox.get("host_permissions", [])) != {
        "http://127.0.0.1/*",
        "http://localhost/*",
    }:
        raise RuntimeError(
            "Always-on host permissions must remain localhost-only."
        )

    if set(firefox.get("optional_host_permissions", [])) != {
        "http://*/*",
        "https://*/*",
    }:
        raise RuntimeError(
            "Broad HTTP(S) host access must remain optional."
        )

    members = release_members()
    names = [name for name, _ in members]
    if names.count("manifest.json") != 1:
        raise RuntimeError("Release must contain one root manifest.json.")

    for name, path in members:
        if not path.is_file():
            raise RuntimeError(f"Missing runtime file: {path}")
        if name in {
            "manifest.firefox.json",
            "README.md",
            "PRIVACY.md",
        }:
            raise RuntimeError(f"Forbidden release member: {name}")
        if name.startswith("tests/"):
            raise RuntimeError(f"Tests must not be packaged: {name}")

    if not (EXT / "PRIVACY.md").is_file():
        raise RuntimeError("browser_extension/PRIVACY.md is required.")

    return {
        "version": str(firefox.get("version") or ""),
        "gecko_id": gecko["id"],
        "strict_min_version": str(gecko["strict_min_version"]),
        "required_data": sorted(required),
        "members": members,
    }


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def build_archive(output_dir: Path = DIST) -> Path:
    report = validate_release_inputs()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / (
        f"job-ai-helper-browser-firefox-{report['version']}-unlisted.zip"
    )

    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name, source in report["members"]:
            archive.writestr(_zip_info(name), source.read_bytes())

    with zipfile.ZipFile(target, "r") as archive:
        if archive.namelist()[0] != "manifest.json":
            raise RuntimeError("manifest.json must be at archive root.")
        packaged = json.loads(
            archive.read("manifest.json").decode("utf-8")
        )
        if packaged != _json(FIREFOX):
            raise RuntimeError(
                "Packaged manifest.json does not match Firefox manifest."
            )

    return target


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--build", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_release_inputs()
    except Exception as exc:
        print(f"[FAIL] Firefox release validation failed: {exc}")
        return 2

    print("Firefox unlisted release validation: PASS")
    print(f"Version: {report['version']}")
    print(f"Gecko ID: {report['gecko_id']}")
    print(f"Minimum Firefox: {report['strict_min_version']}")
    print(
        "Required data disclosures: "
        + ", ".join(report["required_data"])
    )
    print("Archive members:")
    for name, _ in report["members"]:
        print(f"  - {name}")

    if args.check:
        print("[PASS] No files written.")
        return 0

    try:
        target = build_archive()
    except Exception as exc:
        print(f"[FAIL] Firefox release build failed: {exc}")
        return 3

    print(f"[PASS] Built: {target.relative_to(ROOT)}")
    print(f"SHA256: {sha256_file(target)}")
    print(
        "Upload this ZIP to AMO as self-distributed/unlisted. "
        "Install the Mozilla-signed .xpi returned by AMO."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
