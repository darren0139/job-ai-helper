"""Offline candidate for the 16 exact-source reviewed exclusions."""
from contextlib import contextmanager
from copy import deepcopy
from contextvars import ContextVar
from functools import lru_cache
import hashlib
import json
from pathlib import Path

MATCHING_POLICY_VERSION = "review419-exact-source-exclusions-v1"
MANIFEST_SHA256 = "3df3af8a45d8505ea776732cb4d572ad5b0babdf0eb55943b23ace2331b44154"
MANIFEST = Path(__file__).resolve().parents[1] / "reference_fixtures/reviewed_jd_exclusions_v1.json"
_candidate_enabled = ContextVar("reviewed_jd_exclusions_candidate_enabled", default=False)


class CandidateScoreWithheld(ValueError):
    """An existing applicant-evidence hold prevents scoring this exact source."""


@contextmanager
def reviewed_exclusions_candidate():
    """Explicit disposable evaluation only. The application has no activation switch."""
    token = _candidate_enabled.set(True)
    try:
        yield
    finally:
        _candidate_enabled.reset(token)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def _manifest():
    raw = MANIFEST.read_bytes().replace(b"\r\n", b"\n")
    if _digest(raw) != MANIFEST_SHA256:
        raise ValueError("Reviewed exclusion manifest integrity check failed")
    return json.loads(raw)


def _selected(raw_jd_text):
    if not _candidate_enabled.get():
        return ()
    source = _digest(raw_jd_text.encode("utf-8"))
    manifest = _manifest()
    if source in manifest["withheld_sources"]:
        raise CandidateScoreWithheld("Applicant score withheld pending combined knowledge evidence review.")
    return manifest["sources"].get(source, ())


def matching_policy_identity(raw_jd_text):
    if _selected(raw_jd_text):
        return f"{MATCHING_POLICY_VERSION}:{MANIFEST_SHA256}"
    return ""


def effective_scoring_version(base_version, policy_identity):
    return f"{base_version}+{policy_identity}" if policy_identity else base_version



def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def requirement_scope_sha256(rows):
    """Bind the native identities, both weight systems and source lineage in order."""
    keys = (
        "requirement_id", "text", "importance", "atomic_group_id", "group_weight_fraction",
        "parent_text", "scoring_parent_occurrence_id", "source_provenance", "sources",
        "semantic_type", "assessment_basis", "score_eligible", "evidence_eligible", "tailoring_eligible",
    )
    return _digest(_json_bytes([{key: row.get(key) for key in keys} for row in rows]))


def _scope_contract(raw_jd_text):
    sha = _digest(raw_jd_text.encode("utf-8"))
    manifest = _manifest()
    if sha not in manifest["scopes"]:
        return None
    return {
        "version": manifest["scope_version"],
        "policy_identity": f"{MATCHING_POLICY_VERSION}:{MANIFEST_SHA256}",
        "raw_jd_sha256": sha,
        **manifest["scopes"][sha],
        "excluded_requirement_ids": sorted(item["id"] for item in manifest["sources"][sha]),
    }


def active_requirement_scope(raw_jd_text):
    return _scope_contract(raw_jd_text) if _selected(raw_jd_text) else None


def verify_effective_analysis(raw_jd_text, analysis, *, require_active=False):
    """Validate a retained candidate receipt without reinterpreting historical records."""
    receipt = analysis.get("effective_requirement_scope")
    policy = analysis.get("matching_policy_identity")
    active = active_requirement_scope(raw_jd_text) if require_active else None
    if receipt is None and policy is None and active is None:
        return None
    expected = _scope_contract(raw_jd_text)
    if (not expected or receipt != expected or policy != expected["policy_identity"]
            or (require_active and active != expected)
            or not str(analysis.get("scoring_version") or "").endswith("+" + policy)
            or requirement_scope_sha256(analysis.get("canonical_requirements") or [])
            != expected["effective_requirement_scope_sha256"]):
        raise ValueError("Reviewed effective requirement scope is unverified")
    return deepcopy(expected)


def project_requirement_scope(raw_jd_text, rows, *, has_local_overrides=False):
    """Derive the effective rows from the authenticated original scope."""
    scope = active_requirement_scope(raw_jd_text)
    if scope is None:
        return rows, None
    if has_local_overrides:
        raise ValueError("Reviewed exclusions cannot be combined with local preferred overrides")
    result = apply_reviewed_exclusions(raw_jd_text, {"requirements": rows})
    return result["requirements"], result["effective_requirement_scope"]


def apply_reviewed_exclusions(raw_jd_text, canonical):
    selected = _selected(raw_jd_text)
    if not selected:
        return canonical
    targets = {entry["id"]: entry for entry in selected}
    surviving = []
    receipts = []
    for row in canonical["requirements"]:
        entry = targets.get(row["requirement_id"])
        if entry is None:
            surviving.append(row)
            continue
        wire = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if _digest(wire.encode("utf-8")) != entry["row_sha256"]:
            raise ValueError("Reviewed exclusion row differs from the approved native source")
        receipts.append({"requirement_id": row["requirement_id"], "text": row["text"],
                         "review": entry["review"], "reason": entry["reason"],
                         "score_eligible": False, "evidence_eligible": False})
    if sorted(r["requirement_id"] for r in receipts) != sorted(targets):
        raise ValueError("Reviewed exclusion row is missing or duplicated")
    scope = _scope_contract(raw_jd_text)
    if (requirement_scope_sha256(canonical["requirements"]) != scope["original_requirement_scope_sha256"]
            or requirement_scope_sha256(surviving) != scope["effective_requirement_scope_sha256"]):
        raise ValueError("Reviewed original or effective requirement scope has drifted")
    return {**canonical, "requirements": surviving, "effective_requirement_scope": scope,
            "filtered_non_requirement_rows": [*canonical.get("filtered_non_requirement_rows", ()), *receipts]}


REVIEWED_ANALYSIS_CONTRACT = "analysis-pipeline-review419-effective-scope-v1"
REVIEWED_SELECTED = "review419_selected"
REVIEWED_HISTORY = "review419_history"


def is_reviewed_analysis(report, *, contract=None, status=None):
    if str(contract or "").startswith("analysis-pipeline-review419-") or str(status or "").startswith("review419_"):
        return True
    stable = report.get("stable_analysis") or {}
    meta = report.get("meta") or {}
    authority = meta.get("document_analysis") or {}
    return bool(stable.get("matching_policy_identity") or stable.get("effective_requirement_scope")
                or MATCHING_POLICY_VERSION in str(stable.get("scoring_version") or "")
                or authority.get("effective_requirement_scope") or meta.get("review419_selection"))


def refuse_candidate_persistence(report):
    if is_reviewed_analysis(report):
        raise ValueError("Offline reviewed-exclusion scores cannot be saved through the ordinary writer")
