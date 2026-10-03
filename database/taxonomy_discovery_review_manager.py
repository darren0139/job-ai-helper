from __future__ import annotations

from contextlib import closing

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def list_governed_research_results(*, db_path=None):
    """Read-only reload; a missing store must not be created on render."""
    path = _resolved_path(db_path)
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_research_results'").fetchone():
            return []
        return [{"result":json.loads(r[0]), "review":json.loads(r[1]) if r[1] else {"decision":"undecided"},
                 "draft":json.loads(r[2]) if r[2] else None}
                for r in conn.execute("SELECT result_json,review_json,draft_json FROM governed_research_results ORDER BY result_id")]


def save_governed_research_result(result, *, db_path=None):
    from taxonomy_discovery.governed_research import validate_result
    validate_result(result)
    with closing(_connect(_resolved_path(db_path), create_parent=True)) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS governed_research_results (
            result_id TEXT PRIMARY KEY, cache_key TEXT UNIQUE NOT NULL,
            result_fingerprint TEXT NOT NULL, result_json TEXT NOT NULL,
            review_json TEXT, draft_json TEXT)""")
        existing = conn.execute("SELECT result_json FROM governed_research_results WHERE cache_key=?",(result["cache_key"],)).fetchone()
        if existing:
            saved = json.loads(existing[0])
            if saved["research"]["evidence_fingerprint"] != result["research"]["evidence_fingerprint"]:
                raise ValueError("Immutable research cache identity conflict")
            return saved
        conn.execute("INSERT INTO governed_research_results VALUES (?,?,?,?,NULL,NULL)",
            (result["research_result_id"], result["cache_key"], result["result_fingerprint"], json.dumps(result,sort_keys=True)))
        conn.commit()
    return result


def save_governed_research_review(result_id, *, result_fingerprint, decision, reviewer, notes="", draft=None, regression=None, db_path=None):
    """Separate human decision/draft receipt; no approval in other queues or publication."""
    from taxonomy_discovery.taxonomy_evolution import DECISIONS
    from taxonomy_discovery.governed_research import validate_result
    if decision not in DECISIONS or not str(reviewer).strip():
        raise ValueError("Explicit human decision and reviewer required")
    with closing(_connect(_resolved_path(db_path),create_parent=False)) as conn:
        row = conn.execute("SELECT result_json,result_fingerprint,draft_json FROM governed_research_results WHERE result_id=?",(result_id,)).fetchone()
        if not row or row[1] != result_fingerprint:
            raise ValueError("Research review fingerprint stale/missing")
        validate_result(json.loads(row[0]))
        saved_draft = json.loads(row[2]) if row[2] else None
        if draft is not None and draft != saved_draft:
            raise ValueError("Review cannot create or replace a draft")
        if decision == "approve_for_publication":
            from taxonomy_discovery.governed_research import knowledge_fingerprint
            from taxonomy_discovery.corpus_expansion import fingerprint
            from job_discovery.matching import current_match_versions
            if not saved_draft or not regression or regression.get("draft_fingerprint") != fingerprint(saved_draft):
                raise ValueError("Human approval requires the saved draft and its temporary impact report")
            if regression.get("regression_fingerprint") != fingerprint({k:v for k,v in regression.items() if k != "regression_fingerprint"}):
                raise ValueError("Temporary impact report edited")
            if regression.get("current_versions") != current_match_versions() or regression.get("knowledge_fingerprint") != knowledge_fingerprint():
                raise ValueError("Temporary impact knowledge stale")
            if not regression.get("jobs") or any(not j.get("available") or j.get("duplicate_credit_violations") or j.get("classification") == "hard_regression/invariant_violation" for j in regression["jobs"]):
                raise ValueError("Temporary impact is unavailable or has invariant failures")
        review = {"decision":decision, "reviewer":str(reviewer).strip(), "notes":notes,
                  "result_fingerprint":result_fingerprint, "regression":regression,
                  "updated_at":datetime.now(timezone.utc).isoformat(), "publication":False}
        conn.execute("UPDATE governed_research_results SET review_json=?,draft_json=? WHERE result_id=?",
            (json.dumps(review,sort_keys=True), json.dumps(draft,sort_keys=True) if draft else row[2], result_id))
        conn.commit()
    return review


def save_governed_research_draft(result, draft, *, db_path=None, proposal_db_path=None):
    """Explicit native proposal persistence followed by an H.1 receipt; no decision."""
    from taxonomy_discovery.governed_research import validate_result
    validate_result(result)
    provenance = draft.get("governed_research") if draft.get("kind") == "resolver_improvement" else draft.get("proposal",{}).get("governed_research") if draft.get("kind") == "capability" else draft["proposal_bundle"]["proposals"][0].get("governed_research")
    if not provenance or provenance.get("result_fingerprint") != result["result_fingerprint"]:
        raise ValueError("Draft research provenance mismatch")
    with closing(sqlite3.connect(_resolved_path(db_path).as_uri()+"?mode=ro",uri=True)) as conn:
        row = conn.execute("SELECT result_fingerprint,draft_json FROM governed_research_results WHERE result_id=?",(result["research_result_id"],)).fetchone()
        if not row or row[0] != result["result_fingerprint"]:
            raise ValueError("Saved research result required")
        if row[1] and json.loads(row[1]) != draft:
            raise ValueError("Existing draft receipt differs; create a separate research review")
    if draft["kind"] == "resolver_improvement":
        from taxonomy_discovery.resolver_improvement import resolver_overlay
        resolver_overlay(draft)  # Validate, then persist only the separate draft receipt below.
    elif draft["kind"] == "capability":
        save_taxonomy_evolution_proposal(draft["proposal"],db_path=db_path)
    else:
        from database.technology_registry_proposal_manager import import_proposal_bundle
        import_proposal_bundle(draft["proposal_bundle"],db_path=proposal_db_path)
    with closing(_connect(_resolved_path(db_path),create_parent=False)) as conn:
        row = conn.execute("SELECT result_fingerprint,draft_json FROM governed_research_results WHERE result_id=?",(result["research_result_id"],)).fetchone()
        if not row or row[0] != result["result_fingerprint"]:
            raise ValueError("Saved research result required")
        if row[1] and json.loads(row[1]) != draft:
            raise ValueError("Existing draft receipt differs; create a separate research review")
        conn.execute("UPDATE governed_research_results SET draft_json=? WHERE result_id=?",(json.dumps(draft,sort_keys=True),result["research_result_id"]))
        conn.commit()


def save_taxonomy_evolution_proposal(proposal, *, db_path=None):
    """Explicit immutable proposal-only persistence; never updates knowledge."""
    from taxonomy_discovery.taxonomy_evolution import temporary_overlay
    temporary_overlay([proposal])
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS taxonomy_evolution_proposals (
                proposal_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                proposal_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS taxonomy_evolution_reviews (
                proposal_id TEXT PRIMARY KEY, review_json TEXT NOT NULL,
                updated_at TEXT NOT NULL);
        """)
        row=conn.execute("SELECT fingerprint FROM taxonomy_evolution_proposals WHERE proposal_id=?",(proposal["proposal_id"],)).fetchone()
        if row and row["fingerprint"] != proposal["proposal_fingerprint"]:
            raise ValueError("Proposal identity conflict; edited semantics need a new draft")
        conn.execute("INSERT OR IGNORE INTO taxonomy_evolution_proposals VALUES (?,?,?,?)",
            (proposal["proposal_id"],proposal["proposal_fingerprint"],json.dumps(proposal,sort_keys=True),proposal["created_at"]))
        conn.commit()
    return proposal["proposal_id"]


def list_taxonomy_evolution_proposals(*, db_path=None):
    path=_resolved_path(db_path)
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as conn:
        conn.row_factory=sqlite3.Row
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='taxonomy_evolution_proposals'").fetchone():
            return []
        result=[]
        for row in conn.execute("SELECT * FROM taxonomy_evolution_proposals ORDER BY proposal_id"):
            review=conn.execute("SELECT review_json FROM taxonomy_evolution_reviews WHERE proposal_id=?",(row["proposal_id"],)).fetchone()
            result.append({"proposal":json.loads(row["proposal_json"]),"review":json.loads(review[0]) if review else {"decision":"undecided"}})
        return result


def save_taxonomy_evolution_review(proposal_id, *, proposal_fingerprint, decision, reviewer,
                                   regression=None, notes="", db_path=None):
    from taxonomy_discovery.taxonomy_evolution import DECISIONS
    if decision not in DECISIONS or not str(reviewer).strip():
        raise ValueError("Explicit valid human decision and reviewer identity required")
    path=_resolved_path(db_path)
    # No create path: review cannot fabricate/import a missing draft implicitly.
    with closing(_connect(path,create_parent=False)) as conn:
        row=conn.execute("SELECT fingerprint FROM taxonomy_evolution_proposals WHERE proposal_id=?",(proposal_id,)).fetchone()
        if not row or row["fingerprint"] != proposal_fingerprint:
            raise ValueError("Review proposal fingerprint stale/missing")
        review={"decision":decision,"reviewer":str(reviewer).strip(),"notes":notes,"proposal_fingerprint":proposal_fingerprint,
            "regression_fingerprint":(regression or {}).get("regression_fingerprint"),"regression":regression,
            "updated_at":datetime.now(timezone.utc).isoformat(),"publication":False}
        conn.execute("INSERT INTO taxonomy_evolution_reviews VALUES (?,?,?) ON CONFLICT(proposal_id) DO UPDATE SET review_json=excluded.review_json,updated_at=excluded.updated_at",
            (proposal_id,json.dumps(review,sort_keys=True),review["updated_at"]))
        conn.commit()
    return review


def init_focused_verification_schema(db_path=None) -> Path:
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS focused_verification_results (
                artifact_id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                provider_request_id TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS focused_verification_decisions (
                artifact_id TEXT PRIMARY KEY,
                decision TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(artifact_id) REFERENCES focused_verification_results(artifact_id)
            );
        """)
        conn.commit()
    return path


def save_focused_verification_result(result: dict[str, Any], *, db_path=None) -> dict[str, Any]:
    """Immutable, idempotent provider-request evidence, separate from derived drafts."""
    for field in ("target_id", "candidate_id", "provider", "provider_request_id"):
        if not str(result.get(field) or "").strip():
            raise ValueError(f"Missing focused verification {field}")
    if not isinstance(result.get("raw_provider_response"), dict):
        raise ValueError("Raw provider evidence is required")
    identity = result["provider"] + "|" + result["provider_request_id"]
    artifact_id = "tqd3fv_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
    payload = json.dumps(result, sort_keys=True, ensure_ascii=False)
    path = init_focused_verification_schema(db_path)
    with closing(_connect(path, create_parent=False)) as conn:
        existing = conn.execute(
            "SELECT * FROM focused_verification_results WHERE artifact_id=?", (artifact_id,)
        ).fetchone()
        if existing is not None:
            saved = json.loads(existing["result_json"])
            if any(saved.get(key) != result.get(key) for key in (
                "target_id", "candidate_id", "raw_provider_response", "request_payload", "target"
            )):
                raise ValueError("Provider request ID conflicts with immutable saved evidence")
        else:
            conn.execute(
                "INSERT INTO focused_verification_results VALUES (?, ?, ?, ?, ?, ?)",
                (artifact_id, result["target_id"], result["candidate_id"],
                 result["provider_request_id"], payload, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
    return next(row for row in list_focused_verification_results(db_path=path)
                if row["artifact_id"] == artifact_id)


def list_focused_verification_results(*, db_path=None) -> list[dict[str, Any]]:
    """Reload without creating a DB/schema, changing evidence, or calling a provider."""
    path = _resolved_path(db_path)
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='focused_verification_results'").fetchone():
            return []
        rows = conn.execute("""
            SELECT r.*, d.decision, d.draft_json FROM focused_verification_results r
            LEFT JOIN focused_verification_decisions d ON d.artifact_id=r.artifact_id
            ORDER BY r.created_at DESC, r.artifact_id
        """).fetchall()
    return [{"artifact_id": row["artifact_id"], "created_at": row["created_at"],
             "result": json.loads(row["result_json"]), "decision": row["decision"],
             "review_draft": json.loads(row["draft_json"]) if row["draft_json"] else None}
            for row in rows]


def save_focused_verification_decision(*, artifact_id: str, decision: str,
                                       draft: dict[str, Any], db_path=None) -> None:
    if decision not in {"send_to_review", "research_more", "no_change"}:
        raise ValueError("Unsupported focused verification decision")
    if draft.get("status") != "draft" or draft.get("requires_human_approval") is not True:
        raise ValueError("Only governed drafts may be saved")
    path = init_focused_verification_schema(db_path)
    with closing(_connect(path, create_parent=False)) as conn:
        row = conn.execute("SELECT result_json FROM focused_verification_results WHERE artifact_id=?",
                           (artifact_id,)).fetchone()
        evidence = json.loads(row[0]) if row else {}
        if row is None or any(evidence.get(key) != draft.get(key) for key in (
            "target_id", "candidate_id", "provider_request_id"
        )):
            raise ValueError("Draft must belong to saved verification evidence")
        conn.execute("""INSERT INTO focused_verification_decisions VALUES (?, ?, ?, ?)
            ON CONFLICT(artifact_id) DO UPDATE SET decision=excluded.decision,
            draft_json=excluded.draft_json, updated_at=excluded.updated_at""",
            (artifact_id, decision, json.dumps(draft, sort_keys=True), datetime.now(timezone.utc).isoformat()))
        conn.commit()

from taxonomy_discovery.triage import TRIAGE_STATUSES, TRIAGE_VERSION

_ENV_DB_PATH = "TAXONOMY_DISCOVERY_REVIEW_DB"


def _repo_identity() -> str:
    root = Path(__file__).resolve().parents[1]
    raw = str(root).replace("\\", "/").lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def default_review_db_path() -> Path:
    override = str(os.environ.get(_ENV_DB_PATH) or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    base = Path.home() / ".job-ai-helper"
    return base / f"taxonomy_discovery_reviews_{_repo_identity()}.sqlite3"


def _resolved_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    return (
        Path(db_path).expanduser().resolve()
        if db_path is not None
        else default_review_db_path()
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


def init_review_schema(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS taxonomy_discovery_reviews (
                candidate_id TEXT NOT NULL,
                taxonomy_version TEXT NOT NULL,
                triage_version TEXT NOT NULL,
                triage_status TEXT NOT NULL,
                target_capability_id TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (candidate_id, taxonomy_version)
            )
            """
        )
        conn.commit()
    return path


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "candidate_id": str(row["candidate_id"]),
        "taxonomy_version": str(row["taxonomy_version"]),
        "triage_version": str(row["triage_version"]),
        "triage_status": str(row["triage_status"]),
        "target_capability_id": (
            str(row["target_capability_id"])
            if row["target_capability_id"]
            else None
        ),
        "notes": str(row["notes"] or ""),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def list_reviews(
    *,
    taxonomy_version: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    path = _resolved_path(db_path)
    if not path.exists():
        return []

    sql = """
        SELECT
            candidate_id,
            taxonomy_version,
            triage_version,
            triage_status,
            target_capability_id,
            notes,
            created_at,
            updated_at
        FROM taxonomy_discovery_reviews
    """
    params: tuple[Any, ...] = ()
    if taxonomy_version:
        sql += " WHERE taxonomy_version = ?"
        params = (str(taxonomy_version),)
    sql += " ORDER BY candidate_id, taxonomy_version"

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise
    return [_decode(row) for row in rows]


def get_review(
    candidate_id: str,
    taxonomy_version: str,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    path = _resolved_path(db_path)
    if not path.exists():
        return None

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            row = conn.execute(
                """
                SELECT
                    candidate_id,
                    taxonomy_version,
                    triage_version,
                    triage_status,
                    target_capability_id,
                    notes,
                    created_at,
                    updated_at
                FROM taxonomy_discovery_reviews
                WHERE candidate_id = ? AND taxonomy_version = ?
                """,
                (str(candidate_id), str(taxonomy_version)),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return None
            raise
    return _decode(row) if row is not None else None


def save_review(
    *,
    candidate_id: str,
    taxonomy_version: str,
    triage_status: str,
    target_capability_id: str | None = None,
    notes: str = "",
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    candidate_id = str(candidate_id or "").strip()
    taxonomy_version = str(taxonomy_version or "").strip()
    triage_status = str(triage_status or "").strip()
    target_capability_id = str(target_capability_id or "").strip() or None

    if not candidate_id:
        raise ValueError("candidate_id is required.")
    if not taxonomy_version:
        raise ValueError("taxonomy_version is required.")
    if triage_status not in TRIAGE_STATUSES:
        raise ValueError(
            f"Unsupported triage_status {triage_status!r}. "
            f"Expected one of: {', '.join(TRIAGE_STATUSES)}"
        )
    if (
        triage_status == "existing_taxonomy_near_miss"
        and not target_capability_id
    ):
        raise ValueError(
            "existing_taxonomy_near_miss requires target_capability_id."
        )

    path = init_review_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()

    with closing(_connect(path, create_parent=True)) as conn:
        conn.execute(
            """
            INSERT INTO taxonomy_discovery_reviews (
                candidate_id,
                taxonomy_version,
                triage_version,
                triage_status,
                target_capability_id,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id, taxonomy_version)
            DO UPDATE SET
                triage_version = excluded.triage_version,
                triage_status = excluded.triage_status,
                target_capability_id = excluded.target_capability_id,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                candidate_id,
                taxonomy_version,
                TRIAGE_VERSION,
                triage_status,
                target_capability_id,
                str(notes or ""),
                now,
                now,
            ),
        )
        conn.commit()

    saved = get_review(
        candidate_id,
        taxonomy_version,
        db_path=path,
    )
    if saved is None:
        raise RuntimeError("Review was written but could not be reloaded.")
    return saved


def delete_review(
    candidate_id: str,
    taxonomy_version: str,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> bool:
    path = _resolved_path(db_path)
    if not path.exists():
        return False

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            cursor = conn.execute(
                """
                DELETE FROM taxonomy_discovery_reviews
                WHERE candidate_id = ? AND taxonomy_version = ?
                """,
                (str(candidate_id), str(taxonomy_version)),
            )
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return False
            raise
        conn.commit()
        return bool(cursor.rowcount)

BROAD_MINING_RESEARCH_STORE_VERSION = (
    "tqd3-broad-mining-research-store-v1.0.0"
)


def init_broad_mining_research_schema(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS broad_mining_research_artifacts (
                artifact_id TEXT PRIMARY KEY,
                store_version TEXT NOT NULL,
                provider TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                provider_request_id TEXT,
                seed_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                research_model TEXT NOT NULL,
                technology_count INTEGER NOT NULL,
                source_count INTEGER NOT NULL,
                raw_result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_broad_mining_research_seed_updated
            ON broad_mining_research_artifacts (
                seed_id,
                updated_at DESC
            )
            """
        )
        conn.commit()
    return path


def _broad_mining_artifact_id(
    result: dict[str, Any],
) -> str:
    provider = str(result.get("provider") or "").strip()
    request_id = str(
        result.get("provider_request_id") or ""
    ).strip()
    if request_id:
        identity = f"{provider}|{request_id}"
    else:
        identity = json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:24]
    return f"tqdminres_{digest}"


def _broad_mining_counts(
    result: dict[str, Any],
) -> tuple[int, int]:
    structured = result.get("structured_output")
    technologies = (
        structured.get("technologies")
        if isinstance(structured, dict)
        else []
    )
    sources = result.get("sources")
    return (
        len(technologies)
        if isinstance(technologies, list)
        else 0,
        len(sources)
        if isinstance(sources, list)
        else 0,
    )


def save_broad_mining_research_result(
    result: dict[str, Any],
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise TypeError("result must be a dict")

    seed_id = str(result.get("seed_id") or "").strip()
    domain = str(result.get("domain") or "").strip()
    if not seed_id:
        raise ValueError("Broad Mining result has no seed_id")
    if not domain:
        raise ValueError("Broad Mining result has no domain")

    artifact_id = _broad_mining_artifact_id(result)
    technology_count, source_count = _broad_mining_counts(
        result
    )
    raw_result_json = json.dumps(
        result,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    now = datetime.now(timezone.utc).isoformat()
    path = init_broad_mining_research_schema(db_path)

    with closing(_connect(path, create_parent=True)) as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM broad_mining_research_artifacts
            WHERE artifact_id = ?
            """,
            (artifact_id,),
        ).fetchone()
        created_at = (
            str(existing["created_at"])
            if existing is not None
            else now
        )

        conn.execute(
            """
            INSERT INTO broad_mining_research_artifacts (
                artifact_id,
                store_version,
                provider,
                endpoint,
                provider_request_id,
                seed_id,
                domain,
                research_model,
                technology_count,
                source_count,
                raw_result_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_id)
            DO UPDATE SET
                store_version = excluded.store_version,
                provider = excluded.provider,
                endpoint = excluded.endpoint,
                provider_request_id = excluded.provider_request_id,
                seed_id = excluded.seed_id,
                domain = excluded.domain,
                research_model = excluded.research_model,
                technology_count = excluded.technology_count,
                source_count = excluded.source_count,
                raw_result_json = excluded.raw_result_json,
                updated_at = excluded.updated_at
            """,
            (
                artifact_id,
                BROAD_MINING_RESEARCH_STORE_VERSION,
                str(result.get("provider") or "").strip(),
                str(result.get("endpoint") or "").strip(),
                (
                    str(
                        result.get("provider_request_id")
                        or ""
                    ).strip()
                    or None
                ),
                seed_id,
                domain,
                str(
                    result.get("research_model")
                    or result.get("model")
                    or ""
                ).strip(),
                technology_count,
                source_count,
                raw_result_json,
                created_at,
                now,
            ),
        )
        conn.commit()

    return {
        "artifact_id": artifact_id,
        "store_version": BROAD_MINING_RESEARCH_STORE_VERSION,
        "seed_id": seed_id,
        "domain": domain,
        "technology_count": technology_count,
        "source_count": source_count,
        "created_at": created_at,
        "updated_at": now,
    }


def save_broad_mining_research_results(
    results: list[dict[str, Any]],
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, dict):
            saved.append(
                save_broad_mining_research_result(
                    result,
                    db_path=db_path,
                )
            )
    return saved


def _decode_broad_mining_summary(
    row: sqlite3.Row,
) -> dict[str, Any]:
    return {
        "artifact_id": str(row["artifact_id"]),
        "store_version": str(row["store_version"]),
        "provider": str(row["provider"]),
        "endpoint": str(row["endpoint"]),
        "provider_request_id": (
            str(row["provider_request_id"])
            if row["provider_request_id"]
            else None
        ),
        "seed_id": str(row["seed_id"]),
        "domain": str(row["domain"]),
        "research_model": str(
            row["research_model"] or ""
        ),
        "technology_count": int(
            row["technology_count"] or 0
        ),
        "source_count": int(
            row["source_count"] or 0
        ),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def list_broad_mining_research_artifacts(
    *,
    limit: int = 100,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    limit = int(limit)
    if limit < 1:
        return []

    path = _resolved_path(db_path)
    if not path.exists():
        return []

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(
                """
                SELECT
                    artifact_id,
                    store_version,
                    provider,
                    endpoint,
                    provider_request_id,
                    seed_id,
                    domain,
                    research_model,
                    technology_count,
                    source_count,
                    created_at,
                    updated_at
                FROM broad_mining_research_artifacts
                ORDER BY updated_at DESC, artifact_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise

    return [
        _decode_broad_mining_summary(row)
        for row in rows
    ]


def get_broad_mining_research_result(
    artifact_id: str,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    artifact_id = str(artifact_id or "").strip()
    if not artifact_id:
        return None

    path = _resolved_path(db_path)
    if not path.exists():
        return None

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            row = conn.execute(
                """
                SELECT raw_result_json
                FROM broad_mining_research_artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return None
            raise

    if row is None:
        return None

    payload = json.loads(
        str(row["raw_result_json"])
    )
    if not isinstance(payload, dict):
        raise ValueError(
            "Saved Broad Mining research artifact is not an object"
        )
    return payload


def load_latest_broad_mining_research_results(
    *,
    limit: int = 100,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    summaries = list_broad_mining_research_artifacts(
        limit=limit,
        db_path=db_path,
    )

    selected: list[dict[str, Any]] = []
    seen_seeds: set[str] = set()
    for summary in summaries:
        seed_id = str(summary.get("seed_id") or "")
        if not seed_id or seed_id in seen_seeds:
            continue
        payload = get_broad_mining_research_result(
            str(summary["artifact_id"]),
            db_path=db_path,
        )
        if payload is not None:
            selected.append(payload)
            seen_seeds.add(seed_id)

    return selected

BROAD_MINING_CANDIDATE_REVIEW_VERSION = (
    "tqd3-broad-mining-candidate-review-v1.0.0"
)

BROAD_MINING_CANDIDATE_REVIEW_DECISIONS = (
    "research_further",
    "defer",
    "reject",
)


def init_broad_mining_candidate_review_schema(
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Create the local human-review table for mined Broad Mining candidates.

    This table stores explicit reviewer decisions only. It does not create
    technology-registry proposals, mutate taxonomy/registry production data,
    influence scoring, or call any external provider.
    """
    path = _resolved_path(db_path)
    with closing(_connect(path, create_parent=True)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS broad_mining_candidate_reviews (
                candidate_id TEXT PRIMARY KEY,
                review_version TEXT NOT NULL,
                decision TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                candidate_status TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                candidate_snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_broad_mining_candidate_review_decision
            ON broad_mining_candidate_reviews (
                decision,
                updated_at DESC
            )
            """
        )
        conn.commit()
    return path


def _decode_broad_mining_candidate_review(
    row: sqlite3.Row,
) -> dict[str, Any]:
    snapshot = json.loads(
        str(row["candidate_snapshot_json"])
    )
    if not isinstance(snapshot, dict):
        snapshot = {}
    return {
        "candidate_id": str(row["candidate_id"]),
        "review_version": str(row["review_version"]),
        "decision": str(row["decision"]),
        "canonical_name": str(row["canonical_name"]),
        "candidate_status": str(row["candidate_status"]),
        "notes": str(row["notes"] or ""),
        "candidate_snapshot": snapshot,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def list_broad_mining_candidate_reviews(
    *,
    decision: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    path = _resolved_path(db_path)
    if not path.exists():
        return []

    sql = """
        SELECT
            candidate_id,
            review_version,
            decision,
            canonical_name,
            candidate_status,
            notes,
            candidate_snapshot_json,
            created_at,
            updated_at
        FROM broad_mining_candidate_reviews
    """
    params: tuple[Any, ...] = ()
    if decision:
        decision = str(decision).strip()
        if decision not in BROAD_MINING_CANDIDATE_REVIEW_DECISIONS:
            raise ValueError(
                f"Unsupported candidate review decision {decision!r}."
            )
        sql += " WHERE decision = ?"
        params = (decision,)
    sql += " ORDER BY updated_at DESC, candidate_id"

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise
    return [
        _decode_broad_mining_candidate_review(row)
        for row in rows
    ]


def get_broad_mining_candidate_review(
    candidate_id: str,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        return None

    path = _resolved_path(db_path)
    if not path.exists():
        return None

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            row = conn.execute(
                """
                SELECT
                    candidate_id,
                    review_version,
                    decision,
                    canonical_name,
                    candidate_status,
                    notes,
                    candidate_snapshot_json,
                    created_at,
                    updated_at
                FROM broad_mining_candidate_reviews
                WHERE candidate_id = ?
                """,
                (candidate_id,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return None
            raise

    return (
        _decode_broad_mining_candidate_review(row)
        if row is not None
        else None
    )


def save_broad_mining_candidate_review(
    *,
    candidate: dict[str, Any],
    decision: str,
    notes: str = "",
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a dict")

    candidate_id = str(
        candidate.get("candidate_id") or ""
    ).strip()
    canonical_name = str(
        candidate.get("canonical_name") or ""
    ).strip()
    candidate_status = str(
        candidate.get("status") or ""
    ).strip()
    decision = str(decision or "").strip()

    if not candidate_id:
        raise ValueError("candidate_id is required")
    if not canonical_name:
        raise ValueError("canonical_name is required")
    if candidate_status not in {
        "possible_new_technology",
        "ambiguous_registry_match",
    }:
        raise ValueError(
            "Only possible_new_technology or "
            "ambiguous_registry_match candidates may enter this review queue."
        )
    if decision not in BROAD_MINING_CANDIDATE_REVIEW_DECISIONS:
        raise ValueError(
            f"Unsupported candidate review decision {decision!r}. "
            "Expected one of: "
            + ", ".join(
                BROAD_MINING_CANDIDATE_REVIEW_DECISIONS
            )
        )

    snapshot_json = json.dumps(
        candidate,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    path = init_broad_mining_candidate_review_schema(
        db_path
    )
    now = datetime.now(timezone.utc).isoformat()

    with closing(_connect(path, create_parent=True)) as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM broad_mining_candidate_reviews
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        created_at = (
            str(existing["created_at"])
            if existing is not None
            else now
        )

        conn.execute(
            """
            INSERT INTO broad_mining_candidate_reviews (
                candidate_id,
                review_version,
                decision,
                canonical_name,
                candidate_status,
                notes,
                candidate_snapshot_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id)
            DO UPDATE SET
                review_version = excluded.review_version,
                decision = excluded.decision,
                canonical_name = excluded.canonical_name,
                candidate_status = excluded.candidate_status,
                notes = excluded.notes,
                candidate_snapshot_json = excluded.candidate_snapshot_json,
                updated_at = excluded.updated_at
            """,
            (
                candidate_id,
                BROAD_MINING_CANDIDATE_REVIEW_VERSION,
                decision,
                canonical_name,
                candidate_status,
                str(notes or ""),
                snapshot_json,
                created_at,
                now,
            ),
        )
        conn.commit()

    saved = get_broad_mining_candidate_review(
        candidate_id,
        db_path=path,
    )
    if saved is None:
        raise RuntimeError(
            "Candidate review was written but could not be reloaded."
        )
    return saved


def delete_broad_mining_candidate_review(
    candidate_id: str,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> bool:
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        return False

    path = _resolved_path(db_path)
    if not path.exists():
        return False

    with closing(_connect(path, create_parent=False)) as conn:
        try:
            cursor = conn.execute(
                """
                DELETE FROM broad_mining_candidate_reviews
                WHERE candidate_id = ?
                """,
                (candidate_id,),
            )
            conn.commit()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return False
            raise
    return bool(cursor.rowcount)
