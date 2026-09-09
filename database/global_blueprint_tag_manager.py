"""Persistent Blueprint tag library and lane-tag metadata.

Tags are mutable metadata. Blueprint content/fingerprints remain immutable.
Lane assignments are keyed by (role_family_id, variant_id), so every immutable
version in the same lane shares the same tag metadata.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from database import tailoring_version_manager as base_manager


BLUEPRINT_TAG_LIBRARY_VERSION = "phase9d-blueprint-tag-library-v1"
BLUEPRINT_LANE_TAG_POLICY_VERSION = "phase9d-blueprint-lane-tags-v1"
GENERALIST_TAG_ID = "generalist"

DEFAULT_BLUEPRINT_TAGS: tuple[dict[str, Any], ...] = (
    {
        "tag_id": "generalist",
        "label": "Generalist",
        "category": "Lane role",
        "description": "Balanced/default lane with no narrow specialization.",
        "aliases": ["primary", "generalist", "balanced", "full-stack"],
    },
    {
        "tag_id": "backend",
        "label": "Backend",
        "category": "Engineering focus",
        "description": "Server-side services, APIs, and backend application work.",
        "aliases": ["backend", "back-end", "server-side", "api"],
    },
    {
        "tag_id": "ai",
        "label": "AI",
        "category": "Technical domain",
        "description": "LLM, RAG, machine-learning, and AI-assisted application work.",
        "aliases": ["ai", "applied ai", "llm", "rag"],
    },
    {
        "tag_id": "frontend",
        "label": "Frontend",
        "category": "Engineering focus",
        "description": "Web UI, React, TypeScript, and user-facing frontend work.",
        "aliases": ["frontend", "front-end", "react", "ui"],
    },
    {
        "tag_id": "data",
        "label": "Data",
        "category": "Technical domain",
        "description": "Databases, SQL, data modelling, and persistence.",
        "aliases": ["data", "database", "sql", "postgresql"],
    },
    {
        "tag_id": "devops",
        "label": "DevOps",
        "category": "Technical domain",
        "description": "Containers, CI/CD, deployment, and cloud operations.",
        "aliases": ["devops", "cloud", "docker", "ci/cd"],
    },
    {
        "tag_id": "qa",
        "label": "QA",
        "category": "Work focus",
        "description": "Quality assurance, automated testing, and regression work.",
        "aliases": ["qa", "quality assurance", "test automation", "testing"],
    },
    {
        "tag_id": "game_ops",
        "label": "Game Ops",
        "category": "Work focus",
        "description": "Game operations, live operations, and configuration work.",
        "aliases": ["game ops", "game operations", "live ops", "configuration"],
    },
    {
        "tag_id": "mobile",
        "label": "Mobile",
        "category": "Engineering focus",
        "description": "Android, iOS, Kotlin, Flutter, and mobile interfaces.",
        "aliases": ["mobile", "android", "ios", "kotlin"],
    },
    {
        "tag_id": "graphics",
        "label": "Graphics",
        "category": "Technical domain",
        "description": "Graphics, rendering, game engines, and engine systems.",
        "aliases": ["graphics", "engine", "unity", "unreal"],
    },
)


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _tag_id(value: Any) -> str:
    cleaned = _clean(value).lower()
    cleaned = cleaned.replace("c++", "cpp").replace("c#", "csharp")
    cleaned = cleaned.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")


def _normalise_aliases(values: Any) -> list[str]:
    if isinstance(values, str):
        raw = re.split(r"[\n,]+", values)
    elif isinstance(values, (list, tuple, set)):
        raw = list(values)
    else:
        raw = []
    seen: set[str] = set()
    output: list[str] = []
    for value in raw:
        cleaned = _clean(value)
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            output.append(cleaned)
    return output


def _safe_json_list(value: Any) -> list[str]:
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (name,),
        ).fetchone()
        is not None
    )


def _record_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    actor_label: str,
    tag_id: str = "",
    role_family_id: str = "",
    variant_id: str = "",
    before: Any = None,
    after: Any = None,
) -> None:
    event_id = uuid.uuid4().hex
    created_at = _now()
    payload = {
        "event_id": event_id,
        "event_version": BLUEPRINT_TAG_LIBRARY_VERSION,
        "event_type": str(event_type),
        "tag_id": str(tag_id or ""),
        "role_family_id": str(role_family_id or ""),
        "variant_id": str(variant_id or ""),
        "actor_label": _clean(actor_label) or "Local user",
        "before": before,
        "after": after,
        "created_at": created_at,
    }
    connection.execute(
        """
        INSERT INTO global_blueprint_tag_events (
            event_id,
            event_type,
            tag_id,
            role_family_id,
            variant_id,
            actor_label,
            created_at,
            event_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            str(event_type),
            str(tag_id or ""),
            str(role_family_id or ""),
            str(variant_id or ""),
            _clean(actor_label) or "Local user",
            created_at,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )


def _infer_legacy_lane_tag_ids(
    *,
    variant_id: str,
    variant_label: str,
) -> list[str]:
    if _clean(variant_id).lower() == "primary":
        return [GENERALIST_TAG_ID]
    text = _clean(variant_label).lower()
    rules = (
        ("backend", ("backend", "back-end", "api")),
        ("ai", ("ai", "applied ai", "llm", "rag")),
        ("frontend", ("frontend", "front-end", "react")),
        ("data", ("data", "database")),
        ("devops", ("devops", "cloud")),
        ("qa", ("qa", "automation")),
        ("game_ops", ("game ops", "game operations", "live ops")),
        ("mobile", ("mobile", "android", "ios")),
        ("graphics", ("graphics", "engine", "unity", "unreal")),
    )
    found: list[str] = []
    for tag_id, aliases in rules:
        if any(alias in text for alias in aliases):
            found.append(tag_id)
    return found


def _backfill_existing_lanes(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "global_blueprint_versions"):
        return
    rows = connection.execute(
        """
        SELECT DISTINCT
            role_family_id,
            variant_id,
            variant_label
        FROM global_blueprint_versions
        ORDER BY role_family_id, variant_id
        """
    ).fetchall()
    for row in rows:
        role_family_id = str(row["role_family_id"])
        variant_id = str(row["variant_id"] or "primary")
        existing = connection.execute(
            """
            SELECT 1
            FROM global_blueprint_lane_tags
            WHERE role_family_id = ? AND variant_id = ?
            LIMIT 1
            """,
            (role_family_id, variant_id),
        ).fetchone()
        if existing is not None:
            continue
        inferred = _infer_legacy_lane_tag_ids(
            variant_id=variant_id,
            variant_label=str(row["variant_label"] or "Primary"),
        )
        for position, tag_id in enumerate(inferred):
            connection.execute(
                """
                INSERT OR IGNORE INTO global_blueprint_lane_tags (
                    role_family_id,
                    variant_id,
                    tag_id,
                    position,
                    assigned_by,
                    assigned_at,
                    assignment_policy_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role_family_id,
                    variant_id,
                    tag_id,
                    position,
                    "System migration",
                    _now(),
                    BLUEPRINT_LANE_TAG_POLICY_VERSION,
                ),
            )


def init_global_blueprint_tag_registry() -> None:
    from database.global_blueprint_manager import init_global_blueprint_registry

    init_global_blueprint_registry()
    connection = _connect()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_blueprint_tags (
                tag_id TEXT PRIMARY KEY,
                label TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                aliases_json TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
                is_system INTEGER NOT NULL CHECK (is_system IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_blueprint_lane_tags (
                role_family_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                tag_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                assigned_by TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                assignment_policy_version TEXT NOT NULL,
                PRIMARY KEY (role_family_id, variant_id, tag_id),
                FOREIGN KEY (tag_id)
                    REFERENCES global_blueprint_tags (tag_id)
                    ON DELETE RESTRICT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_global_blueprint_lane_tags_lane
            ON global_blueprint_lane_tags (
                role_family_id,
                variant_id,
                position
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS global_blueprint_tag_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                tag_id TEXT NOT NULL,
                role_family_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                actor_label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                event_json TEXT NOT NULL
            )
            """
        )

        now = _now()
        for definition in DEFAULT_BLUEPRINT_TAGS:
            connection.execute(
                """
                INSERT OR IGNORE INTO global_blueprint_tags (
                    tag_id,
                    label,
                    category,
                    description,
                    aliases_json,
                    is_active,
                    is_system,
                    created_at,
                    updated_at,
                    updated_by
                )
                VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?)
                """,
                (
                    definition["tag_id"],
                    definition["label"],
                    definition["category"],
                    definition["description"],
                    json.dumps(definition["aliases"], ensure_ascii=False),
                    now,
                    now,
                    "System seed",
                ),
            )

        _backfill_existing_lanes(connection)
        connection.commit()
    finally:
        connection.close()


def _row_to_tag(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "tag_id": str(row["tag_id"]),
        "label": str(row["label"]),
        "category": str(row["category"]),
        "description": str(row["description"]),
        "aliases": _safe_json_list(row["aliases_json"]),
        "is_active": bool(row["is_active"]),
        "is_system": bool(row["is_system"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "updated_by": str(row["updated_by"]),
        "lane_usage_count": int(row["lane_usage_count"])
        if "lane_usage_count" in row.keys()
        else 0,
    }


def list_blueprint_tags(
    *,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    init_global_blueprint_tag_registry()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT
                tag.*,
                (
                    SELECT COUNT(*)
                    FROM global_blueprint_lane_tags AS lane
                    WHERE lane.tag_id = tag.tag_id
                ) AS lane_usage_count
            FROM global_blueprint_tags AS tag
            WHERE (? = 1 OR tag.is_active = 1)
            ORDER BY
                tag.is_system DESC,
                tag.category ASC,
                tag.label ASC
            """,
            (1 if include_inactive else 0,),
        ).fetchall()
        return [_row_to_tag(row) for row in rows]
    finally:
        connection.close()


def create_blueprint_tag(
    *,
    label: str,
    category: str,
    description: str = "",
    aliases: Any = None,
    actor_label: str = "Local user",
) -> dict[str, Any]:
    init_global_blueprint_tag_registry()
    cleaned_label = _clean(label)
    if not cleaned_label:
        raise ValueError("Tag label is required.")
    tag_id = _tag_id(cleaned_label)
    if not tag_id:
        raise ValueError("Tag label must contain letters or numbers.")
    cleaned_category = _clean(category) or "Custom"
    cleaned_aliases = _normalise_aliases(aliases)
    now = _now()

    connection = _connect()
    try:
        existing = connection.execute(
            """
            SELECT 1
            FROM global_blueprint_tags
            WHERE tag_id = ? OR lower(label) = lower(?)
            LIMIT 1
            """,
            (tag_id, cleaned_label),
        ).fetchone()
        if existing is not None:
            raise ValueError("A Blueprint tag with that ID or label already exists.")

        connection.execute(
            """
            INSERT INTO global_blueprint_tags (
                tag_id,
                label,
                category,
                description,
                aliases_json,
                is_active,
                is_system,
                created_at,
                updated_at,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?)
            """,
            (
                tag_id,
                cleaned_label,
                cleaned_category,
                _clean(description),
                json.dumps(cleaned_aliases, ensure_ascii=False),
                now,
                now,
                _clean(actor_label) or "Local user",
            ),
        )
        _record_event(
            connection,
            event_type="tag_created",
            actor_label=actor_label,
            tag_id=tag_id,
            after={
                "label": cleaned_label,
                "category": cleaned_category,
                "description": _clean(description),
                "aliases": cleaned_aliases,
                "is_active": True,
            },
        )
        connection.commit()
    finally:
        connection.close()

    return next(
        row
        for row in list_blueprint_tags(include_inactive=True)
        if row["tag_id"] == tag_id
    )


def update_blueprint_tag(
    *,
    tag_id: str,
    label: str,
    category: str,
    description: str,
    aliases: Any,
    is_active: bool,
    actor_label: str = "Local user",
) -> dict[str, Any]:
    init_global_blueprint_tag_registry()
    cleaned_id = _tag_id(tag_id)
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT
                tag.*,
                (
                    SELECT COUNT(*)
                    FROM global_blueprint_lane_tags AS lane
                    WHERE lane.tag_id = tag.tag_id
                ) AS lane_usage_count
            FROM global_blueprint_tags AS tag
            WHERE tag.tag_id = ?
            LIMIT 1
            """,
            (cleaned_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Blueprint tag was not found.")

        before = _row_to_tag(row)
        cleaned_label = _clean(label)
        if not cleaned_label:
            raise ValueError("Tag label is required.")
        if before["is_system"] and cleaned_label != before["label"]:
            raise ValueError("System tag labels are stable and cannot be renamed.")
        if before["is_system"] and not is_active:
            raise ValueError("System tags cannot be deactivated.")
        if not is_active and before["lane_usage_count"] > 0:
            raise ValueError(
                "Remove this tag from every Blueprint lane before deactivating it."
            )

        duplicate = connection.execute(
            """
            SELECT 1
            FROM global_blueprint_tags
            WHERE lower(label) = lower(?) AND tag_id <> ?
            LIMIT 1
            """,
            (cleaned_label, cleaned_id),
        ).fetchone()
        if duplicate is not None:
            raise ValueError("Another Blueprint tag already uses that label.")

        cleaned_aliases = _normalise_aliases(aliases)
        connection.execute(
            """
            UPDATE global_blueprint_tags
            SET label = ?,
                category = ?,
                description = ?,
                aliases_json = ?,
                is_active = ?,
                updated_at = ?,
                updated_by = ?
            WHERE tag_id = ?
            """,
            (
                cleaned_label,
                _clean(category) or "Custom",
                _clean(description),
                json.dumps(cleaned_aliases, ensure_ascii=False),
                1 if is_active else 0,
                _now(),
                _clean(actor_label) or "Local user",
                cleaned_id,
            ),
        )
        after = {
            **before,
            "label": cleaned_label,
            "category": _clean(category) or "Custom",
            "description": _clean(description),
            "aliases": cleaned_aliases,
            "is_active": bool(is_active),
        }
        _record_event(
            connection,
            event_type="tag_updated",
            actor_label=actor_label,
            tag_id=cleaned_id,
            before=before,
            after=after,
        )
        connection.commit()
    finally:
        connection.close()

    return next(
        row
        for row in list_blueprint_tags(include_inactive=True)
        if row["tag_id"] == cleaned_id
    )


def _lane_exists(
    connection: sqlite3.Connection,
    *,
    role_family_id: str,
    variant_id: str,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM global_blueprint_versions
            WHERE role_family_id = ? AND variant_id = ?
            LIMIT 1
            """,
            (str(role_family_id), str(variant_id)),
        ).fetchone()
        is not None
    )


def _get_lane_tags_with_connection(
    connection: sqlite3.Connection,
    *,
    role_family_id: str,
    variant_id: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            lane.position,
            lane.assigned_by,
            lane.assigned_at,
            lane.assignment_policy_version,
            tag.*,
            0 AS lane_usage_count
        FROM global_blueprint_lane_tags AS lane
        JOIN global_blueprint_tags AS tag
          ON tag.tag_id = lane.tag_id
        WHERE lane.role_family_id = ?
          AND lane.variant_id = ?
        ORDER BY lane.position ASC, tag.label ASC
        """,
        (str(role_family_id), str(variant_id)),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        tag = _row_to_tag(row)
        tag.update(
            {
                "position": int(row["position"]),
                "assigned_by": str(row["assigned_by"]),
                "assigned_at": str(row["assigned_at"]),
                "assignment_policy_version": str(
                    row["assignment_policy_version"]
                ),
            }
        )
        output.append(tag)
    return output


def get_blueprint_lane_tags(
    *,
    role_family_id: str,
    variant_id: str,
) -> list[dict[str, Any]]:
    init_global_blueprint_tag_registry()
    connection = _connect()
    try:
        return _get_lane_tags_with_connection(
            connection,
            role_family_id=str(role_family_id),
            variant_id=str(variant_id),
        )
    finally:
        connection.close()


def resolve_blueprint_tag_ids(
    labels: list[str] | tuple[str, ...],
) -> list[str]:
    tags = list_blueprint_tags(include_inactive=False)
    by_label = {row["label"].lower(): row["tag_id"] for row in tags}
    output: list[str] = []
    for label in labels:
        cleaned = _clean(label).lower()
        if not cleaned:
            continue
        tag_id = by_label.get(cleaned)
        if tag_id is None:
            raise ValueError(f"Unknown or inactive Blueprint tag: {label}")
        if tag_id not in output:
            output.append(tag_id)
    return output


def set_blueprint_lane_tags(
    *,
    role_family_id: str,
    variant_id: str,
    tag_ids: list[str] | tuple[str, ...],
    actor_label: str = "Local user",
) -> list[dict[str, Any]]:
    init_global_blueprint_tag_registry()
    role_family_id = _clean(role_family_id)
    variant_id = _clean(variant_id)
    if not role_family_id or not variant_id:
        raise ValueError("Role-family and variant lane IDs are required.")

    requested: list[str] = []
    for value in tag_ids:
        cleaned = _tag_id(value)
        if cleaned and cleaned not in requested:
            requested.append(cleaned)

    if variant_id == "primary":
        requested = [
            GENERALIST_TAG_ID,
            *[tag for tag in requested if tag != GENERALIST_TAG_ID],
        ]
    elif GENERALIST_TAG_ID in requested:
        raise ValueError("Generalist is reserved for the Primary lane.")

    if variant_id != "primary" and not requested:
        raise ValueError("A non-Primary Blueprint lane must keep at least one tag.")

    connection = _connect()
    try:
        if not _lane_exists(
            connection,
            role_family_id=role_family_id,
            variant_id=variant_id,
        ):
            raise ValueError("The Blueprint variant lane does not exist.")

        if requested:
            placeholders = ",".join("?" for _ in requested)
            rows = connection.execute(
                f"""
                SELECT tag_id, is_active
                FROM global_blueprint_tags
                WHERE tag_id IN ({placeholders})
                """,
                requested,
            ).fetchall()
            states = {str(row["tag_id"]): bool(row["is_active"]) for row in rows}
            missing = [tag for tag in requested if tag not in states]
            if missing:
                raise ValueError(
                    "Unknown Blueprint tag IDs: " + ", ".join(missing)
                )
            inactive = [tag for tag in requested if not states[tag]]
            if inactive:
                raise ValueError(
                    "Inactive Blueprint tags cannot be assigned: "
                    + ", ".join(inactive)
                )

        before = _get_lane_tags_with_connection(
            connection,
            role_family_id=role_family_id,
            variant_id=variant_id,
        )
        connection.execute(
            """
            DELETE FROM global_blueprint_lane_tags
            WHERE role_family_id = ? AND variant_id = ?
            """,
            (role_family_id, variant_id),
        )
        assigned_at = _now()
        for position, tag_id in enumerate(requested):
            connection.execute(
                """
                INSERT INTO global_blueprint_lane_tags (
                    role_family_id,
                    variant_id,
                    tag_id,
                    position,
                    assigned_by,
                    assigned_at,
                    assignment_policy_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role_family_id,
                    variant_id,
                    tag_id,
                    position,
                    _clean(actor_label) or "Local user",
                    assigned_at,
                    BLUEPRINT_LANE_TAG_POLICY_VERSION,
                ),
            )
        after = _get_lane_tags_with_connection(
            connection,
            role_family_id=role_family_id,
            variant_id=variant_id,
        )
        _record_event(
            connection,
            event_type="lane_tags_updated",
            actor_label=actor_label,
            role_family_id=role_family_id,
            variant_id=variant_id,
            before=[row["tag_id"] for row in before],
            after=[row["tag_id"] for row in after],
        )
        connection.commit()
        return after
    finally:
        connection.close()


def list_blueprint_lane_tag_usage() -> list[dict[str, Any]]:
    init_global_blueprint_tag_registry()
    connection = _connect()
    try:
        lanes = connection.execute(
            """
            SELECT
                role_family_id,
                role_family_label,
                variant_id,
                variant_label,
                version_number,
                availability_status
            FROM (
                SELECT
                    blueprint.role_family_id,
                    blueprint.role_family_label,
                    blueprint.variant_id,
                    blueprint.variant_label,
                    blueprint.version_number,
                    COALESCE(
                        availability.availability_status,
                        'available'
                    ) AS availability_status,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            blueprint.role_family_id,
                            blueprint.variant_id
                        ORDER BY
                            CASE
                                WHEN blueprint.status = 'active' THEN 0
                                ELSE 1
                            END,
                            blueprint.version_number DESC
                    ) AS row_number
                FROM global_blueprint_versions AS blueprint
                LEFT JOIN global_blueprint_availability AS availability
                  ON availability.blueprint_id = blueprint.blueprint_id
            )
            WHERE row_number = 1
            ORDER BY role_family_label, variant_label
            """
        ).fetchall()
        output: list[dict[str, Any]] = []
        for lane in lanes:
            tags = _get_lane_tags_with_connection(
                connection,
                role_family_id=str(lane["role_family_id"]),
                variant_id=str(lane["variant_id"]),
            )
            output.append(
                {
                    "role_family_id": str(lane["role_family_id"]),
                    "role_family_label": str(lane["role_family_label"]),
                    "variant_id": str(lane["variant_id"]),
                    "variant_label": str(lane["variant_label"]),
                    "version_number": int(lane["version_number"]),
                    "availability_status": str(
                        lane["availability_status"] or "available"
                    ),
                    "tags": [row["label"] for row in tags],
                    "tag_ids": [row["tag_id"] for row in tags],
                }
            )
        return output
    finally:
        connection.close()


def list_blueprint_tag_events(
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    init_global_blueprint_tag_registry()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT event_json
            FROM global_blueprint_tag_events
            ORDER BY created_at DESC, event_id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(str(row["event_json"]))
            except (TypeError, json.JSONDecodeError):
                parsed = {}
            if isinstance(parsed, dict):
                output.append(parsed)
        return output
    finally:
        connection.close()
