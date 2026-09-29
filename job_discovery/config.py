from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config/job_discovery_sources.json")
ATS_KEYS = ("greenhouse", "lever", "ashby", "smartrecruiters")


def _target(value: Any) -> dict[str, str] | None:
    if isinstance(value, str):
        identifier = value.strip()
        return {"identifier": identifier, "company": ""} if identifier else None
    if isinstance(value, dict):
        identifier = str(
            value.get("identifier")
            or value.get("board")
            or value.get("site")
            or value.get("company_identifier")
            or ""
        ).strip()
        if not identifier:
            return None
        return {
            "identifier": identifier,
            "company": str(value.get("company") or value.get("company_name") or "").strip(),
        }
    return None


def load_job_discovery_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data = parsed
        except (OSError, json.JSONDecodeError):
            data = {}

    result = {"targets": {key: [] for key in ATS_KEYS}}
    targets = data.get("targets") if isinstance(data.get("targets"), dict) else {}
    for key in ATS_KEYS:
        values = targets.get(key, []) if isinstance(targets, dict) else []
        if not isinstance(values, list):
            continue
        for value in values:
            normalized = _target(value)
            if normalized:
                result["targets"][key].append(normalized)
    return result
