"""Streamlit-managed singleton lifecycle for the local browser bridge."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st
from streamlit import runtime as streamlit_runtime

from browser_integration.bridge_runtime import (
    BrowserBridgeRuntime,
    start_browser_bridge_runtime,
)
from database.browser_bridge_settings import rotate_browser_bridge_token


@dataclass
class StreamlitBrowserBridgeResource:
    runtime: BrowserBridgeRuntime | None
    error: str = ""

    @property
    def running(self) -> bool:
        return bool(self.runtime is not None and self.runtime.is_alive)


@st.cache_resource(show_spinner=False)
def _cached_browser_bridge_resource() -> StreamlitBrowserBridgeResource:
    try:
        runtime = start_browser_bridge_runtime()
        return StreamlitBrowserBridgeResource(runtime=runtime)
    except OSError as exc:
        return StreamlitBrowserBridgeResource(
            runtime=None,
            error=(
                "Could not start the local browser bridge on 127.0.0.1:8765. "
                f"{exc}"
            ),
        )
    except Exception as exc:
        return StreamlitBrowserBridgeResource(
            runtime=None,
            error=f"Could not start the local browser bridge: {exc}",
        )


def ensure_streamlit_browser_bridge() -> StreamlitBrowserBridgeResource:
    """Start/reuse the bridge only under an actual Streamlit runtime."""
    try:
        running_under_streamlit = bool(streamlit_runtime.exists())
    except Exception:
        running_under_streamlit = False

    if not running_under_streamlit:
        return StreamlitBrowserBridgeResource(
            runtime=None,
            error="Browser bridge auto-start is inactive outside Streamlit.",
        )

    return _cached_browser_bridge_resource()


def rotate_streamlit_browser_bridge_token() -> str:
    """Rotate the persistent token and update the live server immediately."""
    resource = ensure_streamlit_browser_bridge()
    if not resource.running or resource.runtime is None:
        raise RuntimeError(resource.error or "Browser bridge is not running.")

    token = rotate_browser_bridge_token()
    resource.runtime.update_token(token)
    return token
