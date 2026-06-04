"""
database/chat_history_manager.py — persistent chat history for the app.

This stores:
- per-application analysis Q&A chat
- global Job Market Insights / RAG chat

The uploaded resume file itself is still not stored.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("data/applications.db")


def _connect() -> sqlite3.Connection:
    """Open SQLite and make sure the data folder exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_chat_history() -> None:
    """Create chat history tables if they do not exist."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def add_application_chat_message(application_id: int, role: str, content: str) -> None:
    """Add one message to a specific application session chat."""
    cleaned = content.strip()

    if not cleaned:
        raise ValueError("Chat message cannot be empty.")

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO application_chat_messages (
            application_id,
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            application_id,
            role,
            cleaned,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )

    conn.commit()
    conn.close()


def get_application_chat_messages(application_id: int, limit: int = 80) -> list[dict[str, Any]]:
    """Return saved chat messages for one application session."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content, created_at
        FROM application_chat_messages
        WHERE application_id = ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (application_id, limit),
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "role": row[0],
            "content": row[1],
            "created_at": row[2],
        }
        for row in rows
    ]


def clear_application_chat_history(application_id: int) -> None:
    """Delete saved chat history for one application session."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM application_chat_messages
        WHERE application_id = ?
        """,
        (application_id,),
    )

    conn.commit()
    conn.close()


def delete_application_chat_history(application_id: int) -> None:
    """Alias used when deleting a session."""
    clear_application_chat_history(application_id)


def add_rag_chat_message(role: str, content: str) -> None:
    """Add one message to the global RAG chat."""
    cleaned = content.strip()

    if not cleaned:
        raise ValueError("Chat message cannot be empty.")

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO rag_chat_messages (
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            role,
            cleaned,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )

    conn.commit()
    conn.close()


def get_rag_chat_messages(limit: int = 80) -> list[dict[str, Any]]:
    """Return saved global RAG chat messages."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content, created_at
        FROM rag_chat_messages
        ORDER BY id ASC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "role": row[0],
            "content": row[1],
            "created_at": row[2],
        }
        for row in rows
    ]


def clear_rag_chat_history() -> None:
    """Delete all global RAG chat history."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM rag_chat_messages")

    conn.commit()
    conn.close()
