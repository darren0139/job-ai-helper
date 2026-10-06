"""Blocking overlay for long synchronous Streamlit operations."""

from __future__ import annotations

import html
from typing import Any


def render_busy_overlay(
    st: Any,
    label: str,
) -> None:
    safe_label = html.escape(str(label or "Working..."))
    st.markdown(
        f"""
        <style>
        .job-finder-busy-overlay {{
            position: fixed;
            inset: 0;
            z-index: 2147483000;
            background: rgba(8, 10, 14, 0.74);
            backdrop-filter: blur(2px);
            pointer-events: all;
            cursor: progress;
        }}
        .job-finder-busy-card {{
            position: fixed;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            z-index: 2147483001;
            min-width: 320px;
            max-width: 680px;
            padding: 20px 24px;
            border-radius: 12px;
            background: rgb(28, 31, 39);
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 16px 60px rgba(0, 0, 0, 0.45);
            color: white;
            text-align: center;
            pointer-events: all;
        }}
        </style>
        <div class="job-finder-busy-overlay"></div>
        <div class="job-finder-busy-card">
            <strong>{safe_label}</strong><br>
            <span>Please wait for this operation to finish.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
