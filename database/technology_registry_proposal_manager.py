"""Persistent imported research proposals and human decisions for TQ-D2.7."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from taxonomy_discovery.research_proposals import (
    PROPOSAL_REVIEW_DECISIONS,
    validate_proposal_bundle,
    PROPOSAL_CONTRACT_VERSION,
    build_registry_vnext_preview,
)

_ENV_DB_PATH = "TECHNOLOGY_REGISTRY_PROPOSAL_DB"


def _repo_identity() -> str:
    root = Path(__file__).resolve().parents[1]
    raw = str(root).replace("\\", "/").lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def default_proposal_db_path() -> Path:
    override = str(os.environ.get(_ENV_DB_PATH) or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (
        Path.home()
        / ".job-ai-helper"
        / f"technology_registry_proposals_{_repo_identity()}.sqlite3"
    )


def _resolved_path(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    return (
        Path(db_path).expanduser().resolve()
        if db_path is not None
        else default_proposal_db_path()
    )


def _connect(
    db_path: str | os.PathLike[str] | None = None,
    *,
    create_parent: bool,
) -> sqlite3.Connection:
    path = _resolved_path(db_path)
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_proposal_schema(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS technology_registry_proposals (
                proposal_id TEXT NOT NULL,
                proposal_bundle_version TEXT NOT NULL,
                technology_id TEXT NOT NULL,
                label TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (proposal_id, proposal_bundle_version)
            );

            CREATE TABLE IF NOT EXISTS technology_registry_proposal_reviews (
                proposal_id TEXT NOT NULL,
                proposal_bundle_version TEXT NOT NULL,
                decision TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (proposal_id, proposal_bundle_version)
            );
            CREATE TABLE IF NOT EXISTS technology_registry_publications (
                proposal_id TEXT NOT NULL,
                proposal_bundle_version TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                registry_path TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                PRIMARY KEY (proposal_id, proposal_bundle_version, source_fingerprint, registry_path)
            );
            """
        )
        conn.commit()
    return path


def import_proposal_bundle(
    bundle: dict[str, Any],
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> int:
    cleaned = validate_proposal_bundle(bundle)
    path = init_proposal_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()
    version = str(cleaned["proposal_bundle_version"])

    with closing(_connect(path, create_parent=True)) as conn:
        for proposal in cleaned["proposals"]:
            proposal["knowledge_context"] = {"taxonomy_version": cleaned["taxonomy_version"],
                                             "registry_version": cleaned["registry_version"]}
            payload_json = json.dumps(
                proposal,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            fingerprint = hashlib.sha256(
                payload_json.encode("utf-8")
            ).hexdigest()

            existing = conn.execute(
                """
                SELECT source_fingerprint
                FROM technology_registry_proposals
                WHERE proposal_id = ?
                  AND proposal_bundle_version = ?
                """,
                (
                    proposal["proposal_id"],
                    version,
                ),
            ).fetchone()
            if (
                existing is not None
                and str(existing["source_fingerprint"])
                != fingerprint
            ):
                # A human decision is only valid for the exact researched
                # proposal content that was reviewed. Any changed source,
                # target, aliases, confidence, or summary invalidates the
                # previous decision and requires explicit re-review.
                conn.execute(
                    """
                    DELETE FROM technology_registry_proposal_reviews
                    WHERE proposal_id = ?
                      AND proposal_bundle_version = ?
                    """,
                    (
                        proposal["proposal_id"],
                        version,
                    ),
                )

            conn.execute(
                """
                INSERT INTO technology_registry_proposals (
                    proposal_id,
                    proposal_bundle_version,
                    technology_id,
                    label,
                    payload_json,
                    source_fingerprint,
                    imported_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    proposal_id,
                    proposal_bundle_version
                ) DO UPDATE SET
                    technology_id = excluded.technology_id,
                    label = excluded.label,
                    payload_json = excluded.payload_json,
                    source_fingerprint = excluded.source_fingerprint,
                    updated_at = excluded.updated_at
                """,
                (
                    proposal["proposal_id"],
                    version,
                    proposal["technology_id"],
                    proposal["label"],
                    payload_json,
                    fingerprint,
                    now,
                    now,
                ),
            )
        conn.commit()

    return len(cleaned["proposals"])


def list_proposals(
    *,
    proposal_bundle_version: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    path = _resolved_path(db_path)
    if not path.exists():
        return []

    sql = """
        SELECT
            proposal_id,
            proposal_bundle_version,
            technology_id,
            label,
            payload_json,
            source_fingerprint,
            imported_at,
            updated_at
        FROM technology_registry_proposals
    """
    params: tuple[Any, ...] = ()
    if proposal_bundle_version:
        sql += " WHERE proposal_bundle_version = ?"
        params = (str(proposal_bundle_version),)
    sql += " ORDER BY label, proposal_id"

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise

    result: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        payload["proposal_bundle_version"] = str(
            row["proposal_bundle_version"]
        )
        payload["source_fingerprint"] = str(
            row["source_fingerprint"]
        )
        payload["imported_at"] = str(row["imported_at"])
        payload["updated_at"] = str(row["updated_at"])
        result.append(payload)
    return result


def list_proposal_publications(*, db_path=None) -> list[dict[str, Any]]:
    """Publication receipts extend the existing proposal store; no runtime dependency."""
    path = _resolved_path(db_path)
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        try:
            rows = conn.execute("SELECT receipt_json FROM technology_registry_publications").fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise
    return [json.loads(row[0]) for row in rows]


def _published_knowledge_present(proposal, registry) -> bool:
    from taxonomy_discovery.technology_registry import normalise
    entry = registry.by_id().get(proposal["technology_id"])
    if not entry or not {normalise(a) for a in proposal["aliases"]}.issubset(
        {normalise(a) for a in entry.get("aliases", [])}
    ):
        return False
    if proposal["proposal_classification"] == "safe_mapping_candidate":
        return any(r.get("status") == "approved" and r.get("relationship_type") == "maps_to_capability"
                   and r.get("capability_id") == proposal["proposed_capability_id"]
                   for r in entry.get("capability_relationships", []))
    return proposal["proposal_classification"] == "recognized_unmapped"


def proposal_publication_state(proposal, review, *, publications=None, registry_path=None, db_path=None):
    from taxonomy_discovery import technology_registry as production
    path = Path(registry_path or production.REGISTRY_PATH).resolve()
    registry = production.load_registry(path)
    receipts = list_proposal_publications(db_path=db_path) if publications is None else publications
    receipt = next((r for r in receipts if r["proposal_id"] == proposal["proposal_id"]
                    and r["proposal_bundle_version"] == proposal.get("proposal_bundle_version", PROPOSAL_CONTRACT_VERSION)
                    and r["source_fingerprint"] == proposal.get("source_fingerprint")
                    and r["registry_path"] == str(path)), None)
    required = {"safe_mapping_candidate": "approve_mapping", "recognized_unmapped": "approve_identity"}.get(
        proposal["proposal_classification"])
    state = "draft"
    if required and review.get("decision") == required:
        state = "human_approved"
    receipt_active = bool(receipt and _published_knowledge_present(proposal, registry))
    if receipt and (receipt.get("status", "published") == "published" or receipt_active):
        state = "production_active" if _published_knowledge_present(proposal, registry) else "explicitly_published"
    return {"state": state, "publication": receipt, "registry_version": registry.version,
            "taxonomy_version": production.get_default_taxonomy().version,
            "production_active": state == "production_active",
            "display": {"draft": "Unreviewed / not approved", "human_approved": "Approved — not yet published",
                        "explicitly_published": "Published — production knowledge changed; review required",
                        "production_active": "Published · Production resolver active"}[state]}


def publish_approved_proposal(*, proposal_id: str, explicit_publish: bool = False,
                             expected_source_fingerprint: str, expected_registry_version: str,
                             proposal_bundle_version: str = PROPOSAL_CONTRACT_VERSION,
                             db_path=None, registry_path=None) -> dict[str, Any]:
    """Explicitly promote one stored human-approved proposal through the vNext builder.

    The production JSON is the sole runtime authority. SQLite stores approval
    and promotion receipts only. This never creates capabilities or candidate evidence.
    """
    import re
    from taxonomy_discovery import technology_registry as production
    if explicit_publish is not True:
        raise ValueError("Publication requires an explicit Publish action")
    path = Path(registry_path or production.REGISTRY_PATH).resolve()
    store = init_proposal_schema(db_path)
    with closing(_connect(store, create_parent=False)) as conn:
        # Serialize review/import/publication through the existing proposal DB.
        conn.execute("BEGIN IMMEDIATE")
        saved = conn.execute("SELECT * FROM technology_registry_proposals WHERE proposal_id=? AND proposal_bundle_version=?",
                             (proposal_id, proposal_bundle_version)).fetchone()
        review = conn.execute("SELECT * FROM technology_registry_proposal_reviews WHERE proposal_id=? AND proposal_bundle_version=?",
                              (proposal_id, proposal_bundle_version)).fetchone()
        if saved is None or saved["source_fingerprint"] != expected_source_fingerprint:
            raise ValueError("Proposal changed or is missing; review the exact stored proposal again")
        proposal = json.loads(saved["payload_json"])
        required = {"safe_mapping_candidate": "approve_mapping", "recognized_unmapped": "approve_identity"}.get(
            proposal["proposal_classification"])
        if required is None:
            raise ValueError("Capability creation/rejected proposals require their separate governed workflow")
        if review is None or review["decision"] != required:
            raise ValueError("The exact proposal requires explicit human approval before publication")
        original = path.read_bytes()
        raw = json.loads(original)
        current_version = raw["registry_version"]
        existing = conn.execute("""SELECT receipt_json FROM technology_registry_publications
            WHERE proposal_id=? AND proposal_bundle_version=? AND source_fingerprint=? AND registry_path=?""",
            (proposal_id, proposal_bundle_version, expected_source_fingerprint, str(path))).fetchone()
        if existing and _published_knowledge_present(proposal, production.load_registry(path)):
            receipt = json.loads(existing[0])
            receipt["status"] = "published"
            conn.execute("""UPDATE technology_registry_publications SET receipt_json=?
                WHERE proposal_id=? AND proposal_bundle_version=? AND source_fingerprint=? AND registry_path=?""",
                (json.dumps(receipt, sort_keys=True), proposal_id, proposal_bundle_version, expected_source_fingerprint, str(path)))
            conn.commit()
            return receipt
        if existing and json.loads(existing[0]).get("status", "published") == "published":
            raise ValueError("Previously published knowledge changed; create and review a new proposal")
        if current_version != expected_registry_version:
            raise ValueError("Production registry changed; inspect the current publication preview again")
        knowledge = proposal.get("knowledge_context", {})
        if knowledge.get("taxonomy_version", production.get_default_taxonomy().version) != production.get_default_taxonomy().version:
            raise ValueError("Taxonomy changed since research import; refresh and explicitly review the proposal")
        # Revalidate the proposal against today's existing taxonomy/registry.
        validate_proposal_bundle({"proposal_bundle_version": proposal_bundle_version,
            "taxonomy_version": production.get_default_taxonomy().version, "registry_version": current_version,
            "proposals": [proposal]})
        if not proposal["sources"]:
            raise ValueError("Publication requires reviewed source evidence")
        preview = build_registry_vnext_preview([proposal], [dict(review)], registry_path=path)
        if preview["skipped"] or preview["applied_proposal_ids"] != [proposal_id]:
            raise ValueError(f"Approved proposal cannot be promoted: {preview['skipped']}")
        promoted = preview["registry_preview"]
        # Preserve production metadata, and advance the existing v1 minor scheme.
        promoted["description"] = raw.get("description", "")
        changed = sorted(raw["entries"], key=lambda e: e["technology_id"]) != promoted["entries"]
        if changed:
            version = re.fullmatch(r"technology-registry-v(\d+)\.(\d+)(?:-bootstrap)?", current_version)
            if not version:
                raise ValueError("Unsupported production registry version; explicit migration is required")
            promoted["registry_version"] = f"technology-registry-v{version[1]}.{int(version[2]) + 1}"
        else:
            promoted["registry_version"] = current_version
        production._validate_registry(promoted)
        encoded = (json.dumps(promoted, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8") if changed else original
        receipt = {
            "promotion_manifest_version": "technology-registry-promotion-manifest-v1",
            "source_preview_version": preview["preview_version"], "proposal_bundle_version": proposal_bundle_version,
            "proposal_id": proposal_id, "applied_proposal_ids": [proposal_id],
            "source_fingerprint": expected_source_fingerprint, "registry_path": str(path),
            "source_registry_version": current_version, "promoted_registry_version": promoted["registry_version"],
            "taxonomy_version": production.get_default_taxonomy().version,
            "source_registry_sha256": hashlib.sha256(original).hexdigest(),
            "published_registry_sha256": hashlib.sha256(encoded).hexdigest(),
            "published_at": datetime.now(timezone.utc).isoformat(), "explicit_publish": True,
            "human_decision": review["decision"], "promoted_entries": [proposal],
            "status": "prepared",
        }
        conn.execute("""INSERT INTO technology_registry_publications VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(proposal_id, proposal_bundle_version, source_fingerprint, registry_path)
            DO UPDATE SET receipt_json=excluded.receipt_json""",
                     (proposal_id, proposal_bundle_version, expected_source_fingerprint, str(path), json.dumps(receipt, sort_keys=True)))
        # Journal explicit intent before replacing a production file. A crash
        # after replacement can be recognized/reconciled without republishing.
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT source_fingerprint FROM technology_registry_proposals WHERE proposal_id=? AND proposal_bundle_version=?",
                               (proposal_id, proposal_bundle_version)).fetchone()
        current_review = conn.execute("SELECT decision FROM technology_registry_proposal_reviews WHERE proposal_id=? AND proposal_bundle_version=?",
                                      (proposal_id, proposal_bundle_version)).fetchone()
        if (not current or current[0] != expected_source_fingerprint or not current_review or current_review[0] != required
                or path.read_bytes() != original):
            raise ValueError("Proposal, approval, or production knowledge changed during publication; stopped")
        if changed:
            # Stage and validate before a single atomic replacement. No backup,
            # taxonomy write, or changes to unrelated production entries.
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".tqd3-publish-", suffix=".json", dir=path.parent, delete=False) as staged:
                staging_path = Path(staged.name)
                staged.write(encoded)
                staged.flush()
                os.fsync(staged.fileno())
            try:
                production.load_registry(staging_path)
                if path.read_bytes() != original:
                    raise ValueError("Production knowledge changed while staging; publication stopped")
                os.replace(staging_path, path)
            finally:
                staging_path.unlink(missing_ok=True)
            production.get_default_registry.cache_clear()
        receipt["status"] = "published"
        conn.execute("""UPDATE technology_registry_publications SET receipt_json=?
            WHERE proposal_id=? AND proposal_bundle_version=? AND source_fingerprint=? AND registry_path=?""",
            (json.dumps(receipt, sort_keys=True), proposal_id, proposal_bundle_version, expected_source_fingerprint, str(path)))
        conn.commit()
    return receipt


def list_proposal_reviews(
    *,
    proposal_bundle_version: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    path = _resolved_path(db_path)
    if not path.exists():
        return []

    sql = """
        SELECT
            proposal_id,
            proposal_bundle_version,
            decision,
            notes,
            created_at,
            updated_at
        FROM technology_registry_proposal_reviews
    """
    params: tuple[Any, ...] = ()
    if proposal_bundle_version:
        sql += " WHERE proposal_bundle_version = ?"
        params = (str(proposal_bundle_version),)
    sql += " ORDER BY proposal_id"

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise

    return [
        {
            "proposal_id": str(row["proposal_id"]),
            "proposal_bundle_version": str(
                row["proposal_bundle_version"]
            ),
            "decision": str(row["decision"]),
            "notes": str(row["notes"] or ""),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }
        for row in rows
    ]


def save_proposal_review(
    *,
    proposal_id: str,
    proposal_bundle_version: str,
    decision: str,
    notes: str = "",
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    decision = str(decision or "").strip()
    if decision not in PROPOSAL_REVIEW_DECISIONS:
        raise ValueError(
            f"Unsupported proposal review decision: {decision!r}"
        )

    path = init_proposal_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()

    with closing(_connect(path, create_parent=True)) as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM technology_registry_proposal_reviews
            WHERE proposal_id = ?
              AND proposal_bundle_version = ?
            """,
            (
                str(proposal_id),
                str(proposal_bundle_version),
            ),
        ).fetchone()
        created_at = (
            str(existing["created_at"])
            if existing is not None
            else now
        )

        conn.execute(
            """
            INSERT INTO technology_registry_proposal_reviews (
                proposal_id,
                proposal_bundle_version,
                decision,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (
                proposal_id,
                proposal_bundle_version
            ) DO UPDATE SET
                decision = excluded.decision,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                str(proposal_id),
                str(proposal_bundle_version),
                decision,
                str(notes or ""),
                created_at,
                now,
            ),
        )
        conn.commit()

    return {
        "proposal_id": str(proposal_id),
        "proposal_bundle_version": str(
            proposal_bundle_version
        ),
        "decision": decision,
        "notes": str(notes or ""),
        "created_at": created_at,
        "updated_at": now,
    }
