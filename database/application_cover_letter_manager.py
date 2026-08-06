"""Immutable, semantically cached cover letters for persisted résumé outputs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

from api_cost import summarise_api_calls
from database import tailoring_version_manager as base_manager
from database.application_resume_output_manager import (
    ApplicationResumeOutputError,
    resolve_application_resume_output,
)
from llm import ask_text, drain_call_ledger, reset_call_ledger
from prompts import COVER_LETTER_PROMPT
from tailoring.phase9e_blueprint_selection import fingerprint_value


COVER_LETTER_RESULT_VERSION = "application-cover-letter-result-v1"
COVER_LETTER_POLICY_VERSION = "application-output-cover-letter-policy-v1"
COVER_LETTER_PROMPT_VERSION = "application-output-cover-letter-prompt-v1"
COVER_LETTER_TEMPERATURE = 0.4
COVER_LETTER_MAX_TOKENS = 900

CoverLetterGenerator = Callable[
    [str, str, str], str | tuple[str, dict[str, Any]]
]


class ApplicationCoverLetterError(ValueError):
    """Raised when cover-letter provenance or persistence fails closed."""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    connection = base_manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _dump(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, default=str,
        separators=(",", ":"),
    )


def _load(value: Any) -> Any:
    text = str(value or "").strip()
    return json.loads(text) if text else {}


def init_application_cover_letters() -> None:
    connection = _connect()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS application_cover_letter_results (
                cover_letter_id TEXT PRIMARY KEY,
                application_id INTEGER NOT NULL,
                result_version TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL UNIQUE,
                cover_letter_fingerprint TEXT NOT NULL,
                resume_output_kind TEXT NOT NULL,
                resume_output_id TEXT NOT NULL,
                resume_output_fingerprint TEXT NOT NULL,
                exact_jd_identity_fingerprint TEXT NOT NULL,
                cover_letter_policy_version TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                prompt_fingerprint TEXT NOT NULL,
                model_id TEXT NOT NULL,
                semantic_identity_json TEXT NOT NULL,
                cover_letter_text TEXT NOT NULL,
                model_provenance_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_application_cover_letters_app
            ON application_cover_letter_results(application_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS application_cover_letter_state (
                application_id INTEGER PRIMARY KEY,
                current_cover_letter_id TEXT NOT NULL,
                current_input_fingerprint TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS application_cover_letter_events (
                event_id TEXT PRIMARY KEY,
                application_id INTEGER NOT NULL,
                cover_letter_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_fingerprint TEXT NOT NULL,
                event_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def build_cover_letter_request_identity(
    *, output: dict[str, Any], model_id: str
) -> dict[str, Any]:
    model = " ".join(str(model_id or "").split()).strip()
    if not model:
        raise ApplicationCoverLetterError("A selected cover-letter model is required.")
    jd_identity = output.get("exact_jd_identity") or {}
    if not str(jd_identity.get("jd_identity_fingerprint") or ""):
        raise ApplicationCoverLetterError(
            "The exact current-JD identity fingerprint is missing."
        )
    if not str(output.get("source_id") or "") or not str(
        output.get("source_fingerprint") or ""
    ):
        raise ApplicationCoverLetterError(
            "The persisted résumé-output identity is incomplete."
        )
    prompt_fingerprint = fingerprint_value(
        {
            "prompt_version": COVER_LETTER_PROMPT_VERSION,
            "system_prompt": COVER_LETTER_PROMPT,
        }
    )
    return {
        "result_version": COVER_LETTER_RESULT_VERSION,
        "policy_version": COVER_LETTER_POLICY_VERSION,
        "application_id": int(output["application_id"]),
        "resume_output": {
            "output_kind": output["output_kind"],
            "output_id": output["source_id"],
            "output_fingerprint": output["source_fingerprint"],
            "resolved_output_fingerprint": output["output_fingerprint"],
            "resume_profile_fingerprint": output[
                "resume_profile_fingerprint"
            ],
            "resume_text_sha256": output["resume_text_sha256"],
        },
        "exact_jd_identity": deepcopy(jd_identity),
        "generation": {
            "prompt_version": COVER_LETTER_PROMPT_VERSION,
            "prompt_fingerprint": prompt_fingerprint,
            "model_id": model,
            "temperature": COVER_LETTER_TEMPERATURE,
            "max_tokens": COVER_LETTER_MAX_TOKENS,
        },
    }


def _user_prompt(output: dict[str, Any]) -> str:
    jd = output["exact_jd_snapshot"]
    return f"""
IMMUTABLE OR PERSISTED RÉSUMÉ PROFILE:
{json.dumps(output['resume_profile_snapshot'], indent=2, ensure_ascii=False)}

RÉSUMÉ TEXT SNAPSHOT:
{output['resume_text_snapshot']}

EXACT CURRENT LINKED JOB DESCRIPTION PROFILE:
{json.dumps(jd.get('jd_profile') or {}, indent=2, ensure_ascii=False)}

EXACT CURRENT LINKED JOB DESCRIPTION TEXT:
{jd.get('raw_text') or ''}

TASK:
Write a truthful tailored cover letter for this application using only the
persisted résumé evidence and exact linked job description above.
""".strip()


def _default_generator(
    system_prompt: str, user_prompt: str, model_id: str
) -> tuple[str, dict[str, Any]]:
    reset_call_ledger()
    text = ask_text(
        system_prompt,
        user_prompt,
        temperature=COVER_LETTER_TEMPERATURE,
        max_tokens=COVER_LETTER_MAX_TOKENS,
        model=model_id,
    ).strip()
    calls = drain_call_ledger()
    for call in calls:
        call["action"] = "generate_application_output_cover_letter"
    summary = summarise_api_calls(calls)
    return text, {
        "model_id": model_id,
        "calls": calls,
        "summary": summary,
        "model_calls": len(calls),
        "embedding_calls": 0,
    }


def _row_to_cover_letter(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "cover_letter_id": str(row["cover_letter_id"]),
        "application_id": int(row["application_id"]),
        "result_version": str(row["result_version"]),
        "input_fingerprint": str(row["input_fingerprint"]),
        "cover_letter_fingerprint": str(row["cover_letter_fingerprint"]),
        "resume_output_kind": str(row["resume_output_kind"]),
        "resume_output_id": str(row["resume_output_id"]),
        "resume_output_fingerprint": str(row["resume_output_fingerprint"]),
        "exact_jd_identity_fingerprint": str(
            row["exact_jd_identity_fingerprint"]
        ),
        "cover_letter_policy_version": str(
            row["cover_letter_policy_version"]
        ),
        "prompt_version": str(row["prompt_version"]),
        "prompt_fingerprint": str(row["prompt_fingerprint"]),
        "model_id": str(row["model_id"]),
        "semantic_identity": _load(row["semantic_identity_json"]),
        "cover_letter_text": str(row["cover_letter_text"]),
        "model_provenance": _load(row["model_provenance_json"]),
        "created_at": str(row["created_at"]),
    }


def _insert_event(
    connection: sqlite3.Connection,
    *, application_id: int, cover_letter_id: str, event_type: str,
    details: dict[str, Any], created_at: str,
) -> dict[str, Any]:
    event = {
        "event_id": uuid.uuid4().hex,
        "application_id": int(application_id),
        "cover_letter_id": cover_letter_id,
        "event_type": event_type,
        "details": deepcopy(details),
        "created_at": created_at,
    }
    event["event_fingerprint"] = fingerprint_value(event)
    connection.execute(
        """
        INSERT INTO application_cover_letter_events (
            event_id, application_id, cover_letter_id, event_type,
            event_fingerprint, event_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event["event_id"], int(application_id), cover_letter_id,
         event_type, event["event_fingerprint"], _dump(event), created_at),
    )
    return event


def generate_or_reuse_application_cover_letter(
    *,
    application_id: int,
    model_id: str,
    application_result_id: str = "",
    generation_id: str = "",
    allow_historical: bool = False,
    generator: CoverLetterGenerator | None = None,
) -> dict[str, Any]:
    resolved = resolve_application_resume_output(
        application_id,
        application_result_id=application_result_id,
        generation_id=generation_id,
        allow_historical=allow_historical,
    )
    identity = build_cover_letter_request_identity(
        output=resolved, model_id=model_id
    )
    input_fingerprint = fingerprint_value(identity)
    cover_letter_id = input_fingerprint[:32]
    init_application_cover_letters()
    connection = _connect()
    try:
        existing = connection.execute(
            """
            SELECT * FROM application_cover_letter_results
            WHERE input_fingerprint = ? LIMIT 1
            """,
            (input_fingerprint,),
        ).fetchone()
        if existing is not None:
            stored = _row_to_cover_letter(existing)
            connection.execute("BEGIN IMMEDIATE")
            now = _now()
            connection.execute(
                """
                INSERT INTO application_cover_letter_state (
                    application_id, current_cover_letter_id,
                    current_input_fingerprint, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(application_id) DO UPDATE SET
                    current_cover_letter_id=excluded.current_cover_letter_id,
                    current_input_fingerprint=excluded.current_input_fingerprint,
                    updated_at=excluded.updated_at
                """,
                (int(application_id), stored["cover_letter_id"],
                 input_fingerprint, now),
            )
            event = _insert_event(
                connection, application_id=application_id,
                cover_letter_id=stored["cover_letter_id"],
                event_type="cover_letter_exactly_reused",
                details={"input_fingerprint": input_fingerprint},
                created_at=now,
            )
            connection.commit()
            return {"cache_status": "hit", "cover_letter": stored,
                    "audit_event": event, "output": resolved}
    finally:
        connection.close()

    generated = (generator or _default_generator)(
        COVER_LETTER_PROMPT, _user_prompt(resolved), str(model_id)
    )
    if isinstance(generated, tuple):
        text, model_provenance = generated
    else:
        text, model_provenance = generated, {
            "model_id": str(model_id), "model_calls": 1,
            "embedding_calls": 0,
        }
    text = str(text or "").strip()
    if not text:
        raise RuntimeError("The cover-letter model returned empty text.")
    model_provenance = deepcopy(model_provenance or {})
    model_provenance.setdefault("model_id", str(model_id))
    model_provenance.setdefault("embedding_calls", 0)
    cover_letter_fingerprint = fingerprint_value(
        {"semantic_identity": identity, "cover_letter_text": text}
    )
    stored = {
        "cover_letter_id": cover_letter_id,
        "application_id": int(application_id),
        "result_version": COVER_LETTER_RESULT_VERSION,
        "input_fingerprint": input_fingerprint,
        "cover_letter_fingerprint": cover_letter_fingerprint,
        "resume_output_kind": resolved["output_kind"],
        "resume_output_id": resolved["source_id"],
        "resume_output_fingerprint": resolved["source_fingerprint"],
        "exact_jd_identity_fingerprint": resolved["exact_jd_identity"][
            "jd_identity_fingerprint"
        ],
        "cover_letter_policy_version": COVER_LETTER_POLICY_VERSION,
        "prompt_version": COVER_LETTER_PROMPT_VERSION,
        "prompt_fingerprint": identity["generation"]["prompt_fingerprint"],
        "model_id": str(model_id),
        "semantic_identity": identity,
        "cover_letter_text": text,
        "model_provenance": model_provenance,
    }
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        now = _now()
        connection.execute(
            """
            INSERT INTO application_cover_letter_results (
                cover_letter_id, application_id, result_version,
                input_fingerprint, cover_letter_fingerprint,
                resume_output_kind, resume_output_id,
                resume_output_fingerprint, exact_jd_identity_fingerprint,
                cover_letter_policy_version, prompt_version,
                prompt_fingerprint, model_id, semantic_identity_json,
                cover_letter_text, model_provenance_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (cover_letter_id, int(application_id), COVER_LETTER_RESULT_VERSION,
             input_fingerprint, cover_letter_fingerprint,
             resolved["output_kind"], resolved["source_id"],
             resolved["source_fingerprint"],
             resolved["exact_jd_identity"]["jd_identity_fingerprint"],
             COVER_LETTER_POLICY_VERSION, COVER_LETTER_PROMPT_VERSION,
             identity["generation"]["prompt_fingerprint"], str(model_id),
             _dump(identity), text, _dump(model_provenance), now),
        )
        connection.execute(
            """
            INSERT INTO application_cover_letter_state (
                application_id, current_cover_letter_id,
                current_input_fingerprint, updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(application_id) DO UPDATE SET
                current_cover_letter_id=excluded.current_cover_letter_id,
                current_input_fingerprint=excluded.current_input_fingerprint,
                updated_at=excluded.updated_at
            """,
            (int(application_id), cover_letter_id, input_fingerprint, now),
        )
        event = _insert_event(
            connection, application_id=application_id,
            cover_letter_id=cover_letter_id,
            event_type="cover_letter_generated",
            details={"input_fingerprint": input_fingerprint,
                     "model_id": str(model_id)}, created_at=now,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    stored["created_at"] = now
    return {"cache_status": "miss", "cover_letter": stored,
            "audit_event": event, "output": resolved}


def list_application_cover_letters(application_id: int) -> list[dict[str, Any]]:
    init_application_cover_letters()
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT * FROM application_cover_letter_results
            WHERE application_id = ? ORDER BY created_at DESC, cover_letter_id
            """,
            (int(application_id),),
        ).fetchall()
        return [_row_to_cover_letter(row) for row in rows]
    finally:
        connection.close()


def get_current_application_cover_letter(
    application_id: int, *, model_id: str
) -> dict[str, Any] | None:
    init_application_cover_letters()
    connection = _connect()
    try:
        state = connection.execute(
            "SELECT * FROM application_cover_letter_state WHERE application_id = ?",
            (int(application_id),),
        ).fetchone()
        if state is None:
            return None
        row = connection.execute(
            "SELECT * FROM application_cover_letter_results WHERE cover_letter_id = ?",
            (str(state["current_cover_letter_id"]),),
        ).fetchone()
        if row is None:
            raise ApplicationCoverLetterError(
                "The current persisted cover-letter row is missing."
            )
        stored = _row_to_cover_letter(row)
    finally:
        connection.close()
    try:
        output = resolve_application_resume_output(application_id)
        expected = fingerprint_value(
            build_cover_letter_request_identity(output=output, model_id=model_id)
        )
        stored["scope_status"] = (
            "current" if expected == stored["input_fingerprint"] else "stale"
        )
        stored["stale_reasons"] = (
            [] if stored["scope_status"] == "current"
            else ["The current résumé output, JD, model, prompt, or policy changed."]
        )
    except (ApplicationResumeOutputError, ApplicationCoverLetterError) as exc:
        stored["scope_status"] = "stale"
        stored["stale_reasons"] = [str(exc)]
    return stored


def delete_application_cover_letters(application_id: int) -> None:
    init_application_cover_letters()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM application_cover_letter_events WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_cover_letter_state WHERE application_id = ?",
            (int(application_id),),
        )
        connection.execute(
            "DELETE FROM application_cover_letter_results WHERE application_id = ?",
            (int(application_id),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
