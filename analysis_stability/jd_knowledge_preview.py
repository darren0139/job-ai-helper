"""Display the exact-source reviewed records or ordinary JD knowledge."""
from contextlib import closing
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3


BUNDLE_SHA256 = "e1d2df5a9211017d231cff5efcb0c5fd70a0e71251884399a6e7a49847fc2868"
BUNDLE = Path(__file__).resolve().parents[1] / "reference_fixtures/reviewed_jd_knowledge_v1.json"


def load_pinned_jd(application_id, db_path):
    """Read the existing application version link and JD text only."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            """SELECT version.raw_text
               FROM application_job_links AS link
               JOIN applications AS app ON app.id=link.application_id
               JOIN job_description_versions AS version
                 ON version.job_description_id=link.job_description_id
                AND version.source_version_id=link.source_version_id
               WHERE app.id=?""",
            (int(application_id),),
        ).fetchall()
    if len(rows) != 1 or not isinstance(rows[0][0], str) or not rows[0][0].strip():
        raise ValueError("A unique pinned original JD is required.")
    return rows[0][0]


@lru_cache(maxsize=1)
def _reviewed_sources():
    # Git for Windows may convert the shipped JSON's final line ending.
    payload = BUNDLE.read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(payload).hexdigest() != BUNDLE_SHA256:
        raise ValueError("The reviewed JD knowledge bundle failed its integrity check.")
    return json.loads(payload)["sources"]


def build_jd_knowledge(raw_jd):
    source_hash = hashlib.sha256(raw_jd.encode()).hexdigest()
    reviewed = _reviewed_sources().get(source_hash)
    if reviewed is not None:
        return deepcopy(reviewed)

    from analysis_stability.stable_evidence_scoring import canonicalise_requirements
    from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
    from tailoring.phase6d6_structured_matching import technology_requirement_structure

    items = []
    for row in canonicalise_requirements({}, raw_jd)["requirements"]:
        resolved = resolve_requirement_with_production_knowledge(row)
        status = resolved["knowledge_status"]
        capability = resolved["decision"].get("capability_id")
        technology = resolved.get("technology_id")
        structure = technology_requirement_structure(row)
        components = structure.get("components", [])
        compound = None
        if components:
            compound = {
                "operator": {"all": "AND", "any": "OR"}.get(structure.get("mode"), "Unverified"),
                "children": [{"text": part["text"], "complete": False} for part in components],
                "complete": False,
            }
        items.append({
            "id": row["requirement_id"], "text": row["text"],
            "parent": row.get("parent_text") or row["text"], "importance": row.get("importance"),
            "type": row.get("semantic_type"), "basis": row.get("assessment_basis"), "status": status,
            "understanding": ("COMPLETE_MEANING_NOT_ESTABLISHED" if status == "UNRESOLVED" and not components
                              else "PARTIAL_OR_SCOPED__FULL_PARENT_UNVERIFIED"),
            "capabilities": [capability] if capability else [],
            "technologies": [technology] if technology else [], "compound": compound,
        })
    return {"requirements": items, "reviews": []}
