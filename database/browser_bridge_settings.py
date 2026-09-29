"""Persistent local pairing settings for the Job AI Helper browser bridge."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_browser_bridge_settings_schema() -> None:
    connection = _connect()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS browser_bridge_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                pairing_token TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def get_or_create_browser_bridge_token() -> str:
    """Return one stable local pairing token, creating it on first use."""
    init_browser_bridge_settings_schema()
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT pairing_token FROM browser_bridge_settings WHERE id = 1"
        ).fetchone()
        if row is not None and str(row["pairing_token"] or "").strip():
            return str(row["pairing_token"]).strip()

        token = secrets.token_urlsafe(32)
        connection.execute(
            """
            INSERT INTO browser_bridge_settings (id, pairing_token, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                pairing_token = excluded.pairing_token,
                updated_at = excluded.updated_at
            """,
            (token, _now()),
        )
        connection.commit()
        return token
    finally:
        connection.close()


def rotate_browser_bridge_token() -> str:
    """Replace the pairing token. Existing extension pairings become invalid."""
    init_browser_bridge_settings_schema()
    token = secrets.token_urlsafe(32)
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO browser_bridge_settings (id, pairing_token, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                pairing_token = excluded.pairing_token,
                updated_at = excluded.updated_at
            """,
            (token, _now()),
        )
        connection.commit()
    finally:
        connection.close()
    return token
