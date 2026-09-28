"""Build Chrome/Edge or Firefox packages from one shared extension source tree."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "browser_extension"
DEFAULT_OUTPUT_DIR = ROOT / "dist" / "browser_extension"
TARGET_MANIFESTS = {
    "chrome": "manifest.json",
    "firefox": "manifest.firefox.json",
}
EXCLUDED_TOP_LEVEL = {
    "README.md",
    "manifest.json",
    "manifest.firefox.json",
    "tests",
}


def _validate_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("manifest_version") != 3:
        raise ValueError(f"{path} must be Manifest V3.")
    if not str(payload.get("version") or "").strip():
        raise ValueError(f"{path} is missing a version.")
    return payload


def build_extension(target: str, output_dir: Path | None = None) -> Path:
    if target not in TARGET_MANIFESTS:
        raise ValueError(f"Unsupported browser target: {target}")

    output_root = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    manifest_path = SOURCE_DIR / TARGET_MANIFESTS[target]
    manifest = _validate_manifest(manifest_path)

    target_dir = output_root / target
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for source in SOURCE_DIR.iterdir():
        if source.name in EXCLUDED_TOP_LEVEL:
            continue
        destination = target_dir / source.name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)

    shutil.copy2(manifest_path, target_dir / "manifest.json")

    built_manifest = json.loads(
        (target_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if built_manifest != manifest:
        raise RuntimeError(f"Built {target} manifest does not match source manifest.")

    print(f"built {target}: {target_dir} (version {manifest['version']})")
    return target_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Job AI Helper browser-extension packages."
    )
    parser.add_argument(
        "--target",
        choices=("chrome", "firefox", "all"),
        default="all",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    args = parser.parse_args()

    targets = ("chrome", "firefox") if args.target == "all" else (args.target,)
    for target in targets:
        build_extension(target, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
