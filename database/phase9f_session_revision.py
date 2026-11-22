"""Additive storage for explicitly confirmed same-session Phase 9F revisions.

Original D/F rows are never rewritten or moved. Current pointers are separate;
historical generations resolve by their frozen decision fingerprint.
"""
from __future__ import annotations

import json

VERSION = "phase9f-session-reconfirmation-v1"
CONFIRMATIONS = ("phase9f_application_confirmations", "phase9f_confirmation_revisions")
EXECUTIONS = ("phase9f_tailoring_executions", "phase9f_execution_revisions")


def exists(connection, table):
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def ensure_tables(connection):
    for original, revision in (CONFIRMATIONS, EXECUTIONS):
        if exists(connection, original) and not exists(connection, revision):
            sql = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (original,)).fetchone()[0]
            sql = sql.replace(original, revision, 1).replace("application_id INTEGER NOT NULL UNIQUE", "application_id INTEGER NOT NULL")
            connection.execute(sql)
    connection.execute("""CREATE TABLE IF NOT EXISTS phase9f_active_revision (
        application_id INTEGER PRIMARY KEY, confirmation_id TEXT NOT NULL,
        previous_confirmation_id TEXT NOT NULL, policy_version TEXT NOT NULL)""")


def confirmation_row(connection, application_id, *, confirmation_id=None, decision_fingerprint=None):
    if confirmation_id is None and decision_fingerprint is None and exists(connection, 'phase9f_active_revision'):
        active = connection.execute('SELECT * FROM phase9f_active_revision WHERE application_id=?', (application_id,)).fetchone()
        if active is not None:
            if active['policy_version'] != VERSION:
                raise ValueError('Unsupported Phase 9F session revision')
            confirmation_id = active['confirmation_id']
    for table in CONFIRMATIONS:
        if exists(connection, table):
            field, value = ('confirmation_id', confirmation_id) if confirmation_id else (('phase9e_decision_fingerprint', decision_fingerprint) if decision_fingerprint else ('application_id', application_id))
            row = connection.execute(f'SELECT * FROM {table} WHERE application_id=? AND {field}=?', (application_id, value)).fetchone()
            if row is not None:
                return row
    if confirmation_id or decision_fingerprint:
        raise ValueError('Phase 9F confirmation ownership or revision binding is missing')
    return None


def execution_table(connection, execution_id):
    for table in EXECUTIONS:
        if exists(connection, table) and connection.execute(f'SELECT 1 FROM {table} WHERE execution_id=?', (execution_id,)).fetchone():
            return table
    raise ValueError('Phase 9F execution identity is missing')



def phase9f_application_owns_generation(connection, application_id, decision_fingerprint):
    """Fail closed for approvals in a Phase 9F-confirmed application.

    Legacy approvals remain available in applications without a Phase 9F-D
    confirmation. A Phase 9F-confirmed application may only approve a draft
    whose saved Phase 9E decision belongs to one of its immutable D revisions.
    Missing/corrupted provenance is *not* grounds for legacy fallback.
    """
    # An active revision pointer remains Phase 9F-owned even if its referenced
    # row has been lost. Do not reinterpret that corruption as a legacy app.
    has_phase9f_confirmation = bool(
        exists(connection, "phase9f_active_revision")
        and connection.execute(
            "SELECT 1 FROM phase9f_active_revision WHERE application_id=?",
            (int(application_id),),
        ).fetchone()
    )
    matching_confirmation = False
    for table in CONFIRMATIONS:
        if not exists(connection, table):
            continue
        rows = connection.execute(
            f"SELECT phase9e_decision_fingerprint FROM {table} WHERE application_id=?",
            (int(application_id),),
        ).fetchall()
        if rows:
            has_phase9f_confirmation = True
        if decision_fingerprint and any(
            row[0] == decision_fingerprint for row in rows
        ):
            matching_confirmation = True
    if has_phase9f_confirmation and not matching_confirmation:
        raise ValueError(
            "Phase 9F source generation has no matching immutable confirmation; "
            "legacy approval is forbidden for this Application Session."
        )
    return matching_confirmation


_NORMAL_LIFECYCLE = "phase9f-f-normal-generation-lifecycle-v1"
_NORMAL_KINDS = (
    "phase9f_f_normal_projects_skills",
    "phase9f_f_normal_jd_rephrase",
    "phase9f_f_normal_fit",
)


def _normal_generation_execution(connection, application_id, generation_id, decision, generation):
    """Resolve a Workspace-owned F normal generation via its frozen provenance.

    An F normal execution is an immutable *source context*, not one execution
    per ordinary Workspace generation. Its execution row intentionally has a
    NULL generation_id; each normal generation owns a separately frozen
    lifecycle/provenance snapshot in application_tailoring_versions.
    """
    if not exists(connection, "application_tailoring_versions"):
        return None
    version = connection.execute(
        "SELECT generation_settings_json FROM application_tailoring_versions "
        "WHERE application_id=? AND generation_id=?",
        (application_id, generation_id),
    ).fetchone()
    if version is None:
        return None
    try:
        settings = json.loads(version["generation_settings_json"] or "{}")
    except (TypeError, ValueError):
        settings = None
    if not isinstance(settings, dict):
        raise ValueError("Phase 9F historical generation settings are corrupt")
    lifecycle = settings.get("phase9f_f_normal_lifecycle")
    if not isinstance(lifecycle, dict) or lifecycle.get("lifecycle_version") != _NORMAL_LIFECYCLE:
        return None
    if "generation_kind" not in generation.keys() or generation["generation_kind"] not in _NORMAL_KINDS:
        raise ValueError("Phase 9F normal generation kind conflicts with its frozen lifecycle")
    provenance = lifecycle.get("provenance")
    binding = settings.get("phase9e_binding")
    if not isinstance(provenance, dict) or not isinstance(binding, dict):
        raise ValueError("Phase 9F historical generation has no frozen provenance")
    if (settings.get("phase9f_f_provenance") != provenance
            or binding.get("decision_fingerprint") != decision
            or provenance.get("phase9e_decision_fingerprint") != decision):
        raise ValueError("Phase 9F historical generation decision provenance conflicts with its frozen binding")
    for key in ("execution_id", "execution_fingerprint", "confirmation_id",
                "confirmation_fingerprint", "phase9e_decision_fingerprint",
                "starting_snapshot_fingerprint", "exact_jd_identity_fingerprint",
                "evidence_snapshot_fingerprint", "section_scope_fingerprint"):
        if not isinstance(provenance.get(key), str) or not provenance[key]:
            raise ValueError("Phase 9F historical generation has incomplete frozen execution provenance")
    confirmed = confirmation_row(connection, application_id,
                                 confirmation_id=provenance["confirmation_id"])
    if (confirmed is None or confirmed["phase9e_decision_fingerprint"] != decision
            or confirmed["confirmation_fingerprint"] != provenance["confirmation_fingerprint"]):
        raise ValueError("Phase 9F historical generation confirmation conflicts with its frozen provenance")

    candidates = []
    for table in EXECUTIONS:
        if not exists(connection, table):
            continue
        rows = connection.execute(
            f"SELECT * FROM {table} WHERE application_id=? AND execution_id=?",
            (application_id, provenance["execution_id"]),
        ).fetchall()
        candidates.extend(rows)
    if len(candidates) != 1:
        raise ValueError("Phase 9F normal execution generation binding is missing or duplicate")
    row = candidates[0]
    # Private/legacy executions with an explicit generation must never be
    # adopted as normal Workspace source contexts.
    if row["generation_id"]:
        raise ValueError("Phase 9F normal execution conflicts with an explicit generation binding")
    for key in ("execution_fingerprint", "confirmation_id", "confirmation_fingerprint",
                "phase9e_decision_fingerprint", "starting_snapshot_fingerprint",
                "exact_jd_identity_fingerprint", "evidence_snapshot_fingerprint",
                "section_scope_fingerprint"):
        if row[key] != provenance[key]:
            raise ValueError("Phase 9F normal execution conflicts with the frozen generation provenance")
    try:
        outputs = json.loads(row["stage_outputs_json"] or "{}")
    except (TypeError, ValueError):
        outputs = None
    if (not isinstance(outputs, dict)
            or outputs.get("normal_lifecycle_adapter_version") != _NORMAL_LIFECYCLE):
        raise ValueError("Phase 9F normal generation cannot adopt legacy/private execution")
    return row


def active_execution_row(connection, application_id, *, generation_id=None):
    """Resolve the current source context or the exact frozen generation owner.

    Explicit historical private F generations have an execution generation_id;
    normal F generations instead bind via immutable Workspace provenance.
    Neither case may fall back to the current source when a historical id is given.
    """
    if generation_id is not None:
        if not generation_id or not exists(connection, "application_tailoring_generation_meta"):
            return None
        generation = connection.execute(
            "SELECT * FROM application_tailoring_generation_meta "
            "WHERE application_id=? AND generation_id=?",
            (int(application_id), str(generation_id)),
        ).fetchone()
        if generation is None or not generation["phase9e_decision_fingerprint"]:
            return None
        decision = generation["phase9e_decision_fingerprint"]

        matches = []
        for table in EXECUTIONS:
            if exists(connection, table):
                matches.extend(connection.execute(
                    f"SELECT * FROM {table} WHERE application_id=? AND generation_id=?",
                    (int(application_id), str(generation_id)),
                ).fetchall())
        if len(matches) > 1:
            raise ValueError("Phase 9F execution generation binding conflicts: duplicate ownership")
        if matches:
            row = matches[0]
            confirmed = confirmation_row(connection, application_id, confirmation_id=row["confirmation_id"])
            if (row["phase9e_decision_fingerprint"] != decision
                    or confirmed["phase9e_decision_fingerprint"] != decision):
                raise ValueError("Phase 9F execution generation binding conflicts with its frozen confirmation")
            return row

        normal = _normal_generation_execution(
            connection, int(application_id), str(generation_id), decision, generation,
        )
        if normal is not None:
            return normal

        # Do not silently recover a private or corrupt historical generation
        # via the currently active F execution. Missing proof stays missing.
        confirmed = confirmation_row(connection, application_id,
                                     decision_fingerprint=decision)
        for table in EXECUTIONS:
            if exists(connection, table) and connection.execute(
                f"SELECT 1 FROM {table} WHERE application_id=? AND confirmation_id=?",
                (int(application_id), confirmed["confirmation_id"]),
            ).fetchone():
                raise ValueError(
                    "Phase 9F execution generation binding conflicts with the requested historical generation"
                )
        return None

    confirmed = confirmation_row(connection, application_id)
    for table in EXECUTIONS:
        if not exists(connection, table):
            continue
        if confirmed is not None:
            row = connection.execute(
                f"SELECT * FROM {table} WHERE application_id=? AND confirmation_id=?",
                (int(application_id), confirmed["confirmation_id"]),
            ).fetchone()
        else:
            row = connection.execute(
                f"SELECT * FROM {table} WHERE application_id=?",
                (int(application_id),),
            ).fetchone()
        if row is not None:
            return row
    return None
