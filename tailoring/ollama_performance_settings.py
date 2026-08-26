from __future__ import annotations

import os
import platform
import subprocess
from typing import Any

DEFAULT_REPHRASE_NUM_CTX = 4096
DEFAULT_REPHRASE_BATCH_MAX_BULLETS = 3
DEFAULT_REPHRASE_EVIDENCE_MAX_ITEMS = 16
DEFAULT_REPHRASE_EVIDENCE_MAX_CHARS = 4000

KV_CACHE_TYPES = ("f16", "q8_0")


def is_local_ollama_model(model: str | None) -> bool:
    cleaned = str(model or "").strip()
    return cleaned.startswith("ollama/") and ":cloud" not in cleaned


def read_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return max(1, int(default))

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return max(1, int(default))

    return max(1, value)


def apply_rephrase_runtime_settings(
    *,
    num_ctx: int,
    batch_max_bullets: int,
    evidence_max_items: int,
    evidence_max_chars: int,
) -> dict[str, str]:
    values = {
        "OLLAMA_REPHRASE_NUM_CTX": str(max(1, int(num_ctx))),
        "OLLAMA_REPHRASE_BATCH_MAX_BULLETS": str(
            max(1, int(batch_max_bullets))
        ),
        "OLLAMA_REPHRASE_PROMPT_EVIDENCE_MAX_ITEMS": str(
            max(1, int(evidence_max_items))
        ),
        "OLLAMA_REPHRASE_PROMPT_EVIDENCE_MAX_CHARS": str(
            max(1, int(evidence_max_chars))
        ),
    }

    os.environ.update(values)
    return values


def persist_ollama_server_settings_windows(
    *,
    flash_attention: bool,
    kv_cache_type: str,
) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {
            "ok": False,
            "message": (
                "Automatic persistence is currently implemented for "
                "Windows only."
            ),
        }

    normalized_cache = str(kv_cache_type or "").strip().lower()
    if normalized_cache not in KV_CACHE_TYPES:
        return {
            "ok": False,
            "message": (
                "Unsupported KV cache type. Expected one of: "
                + ", ".join(KV_CACHE_TYPES)
            ),
        }

    values = {
        "OLLAMA_FLASH_ATTENTION": "1" if flash_attention else "0",
        "OLLAMA_KV_CACHE_TYPE": normalized_cache,
    }

    try:
        for name, value in values.items():
            subprocess.run(
                ["setx", name, value],
                check=True,
                capture_output=True,
                text=True,
            )
    except (
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        return {
            "ok": False,
            "message": f"Could not save Ollama server settings: {exc}",
        }

    # Keep the Streamlit process display consistent with what was saved.
    # These values do NOT reconfigure an already-running Ollama server.
    os.environ.update(values)

    return {
        "ok": True,
        "message": (
            "Saved for future Ollama server starts. Restart Ollama for "
            "Flash Attention / KV cache changes to take effect; a laptop "
            "restart is not required."
        ),
        "values": values,
    }
