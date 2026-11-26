"""Display-only persistence for finished Best-of comparison receipts.

A saved review can be rendered after a Streamlit reconnection. It never grants
approval, validates a document, or changes a native Job Match result. The exact
application, generation, fitted DOCX SHA and JD hash must agree on retrieval.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from typing import Any

SCHEMA = 'phase9f-bestof-display-receipt-v1'
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def _connect():
    from database import tailoring_version_manager as manager
    connection = manager._connect()
    connection.row_factory = sqlite3.Row
    return connection


def _init(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS phase9f_bestof_display_receipts (
            application_id INTEGER NOT NULL,
            generation_id TEXT NOT NULL,
            context TEXT NOT NULL,
            docx_sha256 TEXT NOT NULL,
            jd_sha256 TEXT NOT NULL,
            scorer_version TEXT NOT NULL,
            run_mode TEXT NOT NULL,
            mode_receipt_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            result_sha256 TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            PRIMARY KEY (application_id, generation_id, context)
        )
    ''')
    connection.execute('''
        CREATE INDEX IF NOT EXISTS idx_phase9f_bestof_display_latest
        ON phase9f_bestof_display_receipts(application_id, generation_id, updated_at DESC)
    ''')


def _json_detached(value: Any, active: set[int] | None = None, depth: int = 0):
    """Prepare a display snapshot, excluding stale cyclic shortlist references."""
    if active is None:
        active = set()
    if depth > 32:
        raise ValueError('Display receipt exceeds maximum nesting depth')
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    identity = id(value)
    if identity in active:
        # Some historical V3.5 proposals contain a self-referencing candidate.
        return {'cyclic_display_reference_omitted': True}
    active.add(identity)
    try:
        if isinstance(value, dict):
            return {str(k): _json_detached(v, active, depth + 1) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [_json_detached(v, active, depth + 1) for v in value]
        if isinstance(value, set):
            return sorted(_json_detached(v, active, depth + 1) for v in value)
        return str(value)
    finally:
        active.remove(identity)


def _jd_sha(raw_jd_text: str) -> str:
    return sha256(raw_jd_text.encode('utf-8')).hexdigest()


def save_bestof_display_receipt(*, application_id: int, generation_id: str,
        context: str, docx_sha256: str, raw_jd_text: str, scorer_version: str,
        run_mode: str, mode_receipt: dict, result: dict) -> bool:
    """Save only a previously computed display receipt; never run an optimizer."""
    if not (int(application_id) > 0 and generation_id and context and
            len(docx_sha256) == 64 and raw_jd_text and isinstance(result, dict) and
            result.get('status') not in ('not_run', None)):
        return False
    try:
        payload = json.dumps(_json_detached(result), ensure_ascii=False,
                             sort_keys=True, allow_nan=False, separators=(',', ':'))
        modes = json.dumps(_json_detached(mode_receipt or {}), ensure_ascii=False,
                           sort_keys=True, separators=(',', ':'))
        encoded = payload.encode('utf-8')
        if len(encoded) > MAX_RECEIPT_BYTES:
            return False
    except (TypeError, ValueError, OverflowError, RecursionError):
        return False
    connection = _connect()
    try:
        with connection:
            _init(connection)
            connection.execute('''
                INSERT INTO phase9f_bestof_display_receipts (
                    application_id, generation_id, context, docx_sha256, jd_sha256,
                    scorer_version, run_mode, mode_receipt_json, result_json,
                    result_sha256, updated_at, schema_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(application_id, generation_id, context) DO UPDATE SET
                    docx_sha256=excluded.docx_sha256, jd_sha256=excluded.jd_sha256,
                    scorer_version=excluded.scorer_version, run_mode=excluded.run_mode,
                    mode_receipt_json=excluded.mode_receipt_json,
                    result_json=excluded.result_json,
                    result_sha256=excluded.result_sha256,
                    updated_at=excluded.updated_at,
                    schema_version=excluded.schema_version
                ''', (int(application_id), str(generation_id), str(context),
                      docx_sha256, _jd_sha(raw_jd_text), str(scorer_version or ''),
                      run_mode, modes, payload, sha256(encoded).hexdigest(),
                      datetime.now(timezone.utc).isoformat(), SCHEMA))
        return True
    finally:
        connection.close()


def load_bestof_display_receipt(*, application_id: int, generation_id: str,
        docx_sha256: str, raw_jd_text: str, scorer_version: str = '') -> dict | None:
    """Load newest exact-input receipt, rejecting stale inputs and corrupt JSON."""
    connection = _connect()
    try:
        with connection:
            _init(connection)
        rows = connection.execute('''
            SELECT * FROM phase9f_bestof_display_receipts
            WHERE application_id=? AND generation_id=? AND docx_sha256=?
              AND jd_sha256=? AND scorer_version=? AND schema_version=?
            ORDER BY updated_at DESC, rowid DESC LIMIT 10
        ''', (int(application_id), str(generation_id), docx_sha256,
              _jd_sha(raw_jd_text), str(scorer_version or ''), SCHEMA)).fetchall()
        for row in rows:
            if sha256(row['result_json'].encode('utf-8')).hexdigest() != row['result_sha256']:
                continue
            try:
                result = json.loads(row['result_json'])
                mode = json.loads(row['mode_receipt_json'])
            except (ValueError, TypeError):
                continue
            if isinstance(result, dict) and isinstance(mode, dict):
                return {'context': row['context'], 'result': result,
                        'run_mode': row['run_mode'], 'mode_receipt': mode}
        return None
    finally:
        connection.close()


def has_bestof_display_receipt(application_id: int, generation_id: str) -> bool:
    """Cheap view-open hint; exact DOCX, JD and scorer still checked when read."""
    if not generation_id:
        return False
    connection = _connect()
    try:
        with connection:
            _init(connection)
        return connection.execute('''
            SELECT 1 FROM phase9f_bestof_display_receipts
            WHERE application_id=? AND generation_id=? AND schema_version=? LIMIT 1
        ''', (int(application_id), str(generation_id), SCHEMA)).fetchone() is not None
    finally:
        connection.close()


def delete_bestof_display_receipts(application_id: int, connection=None) -> int:
    """Delete review-only state with the application's existing deletion flow."""
    own = connection is None
    if own:
        connection = _connect()
    try:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase9f_bestof_display_receipts'").fetchone()
        if not exists:
            other=connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase9f_bestof_view_preferences'").fetchone()
            if other:
                connection.execute('DELETE FROM phase9f_bestof_view_preferences WHERE application_id=?', (int(application_id),))
                if own:
                    connection.commit()
            return 0
        cursor = connection.execute('DELETE FROM phase9f_bestof_display_receipts WHERE application_id=?', (int(application_id),))
        other=connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase9f_bestof_view_preferences'").fetchone()
        if other:
            connection.execute('DELETE FROM phase9f_bestof_view_preferences WHERE application_id=?', (int(application_id),))
        if own:
            connection.commit()
        return max(0, cursor.rowcount)
    finally:
        if own:
            connection.close()


def _init_view_preferences(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS phase9f_bestof_view_preferences (
            application_id INTEGER NOT NULL,
            generation_id TEXT NOT NULL,
            view_key TEXT NOT NULL,
            preferences_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (application_id, generation_id, view_key)
        )
    ''')


def load_bestof_view_preferences(application_id: int, generation_id: str, view_key: str) -> dict:
    """Restore non-authoritative checkbox/radio choices after browser refresh."""
    if not application_id or not generation_id or not view_key:
        return {}
    db = _connect()
    try:
        with db:
            _init_view_preferences(db)
        row = db.execute('''SELECT preferences_json FROM phase9f_bestof_view_preferences
            WHERE application_id=? AND generation_id=? AND view_key=?''',
            (int(application_id), str(generation_id), str(view_key))).fetchone()
        if not row:
            return {}
        item = json.loads(row['preferences_json'])
        return item if isinstance(item, dict) else {}
    except (sqlite3.Error, ValueError, TypeError):
        return {}
    finally:
        db.close()


def save_bestof_view_preferences(application_id: int, generation_id: str,
                                 view_key: str, value: dict) -> bool:
    """Only view choices, no frozen inputs/selection receipts/approval state."""
    if not application_id or not generation_id or not view_key or not isinstance(value, dict):
        return False
    try:
        payload=json.dumps(value, sort_keys=True, separators=(',', ':'))
    except (ValueError, TypeError):
        return False
    if len(payload) > 16384:
        return False
    db = _connect()
    try:
        with db:
            _init_view_preferences(db)
            existing=db.execute('''SELECT preferences_json FROM phase9f_bestof_view_preferences
                WHERE application_id=? AND generation_id=? AND view_key=?''',
                (int(application_id), str(generation_id), str(view_key))).fetchone()
            if existing and existing['preferences_json'] == payload:
                return True
            db.execute('''INSERT INTO phase9f_bestof_view_preferences
                (application_id,generation_id,view_key,preferences_json,updated_at)
                VALUES (?,?,?,?,?) ON CONFLICT(application_id,generation_id,view_key)
                DO UPDATE SET preferences_json=excluded.preferences_json,updated_at=excluded.updated_at''',
                (int(application_id),str(generation_id),str(view_key),payload,
                 datetime.now(timezone.utc).isoformat()))
        return True
    except sqlite3.Error:
        return False
    finally:
        db.close()
