"""B2.19b project adapter for exact frozen project evidence records."""
from tailoring.technology_database_evidence_v312b219b import LABELS, evaluate, requirement

VERSION = "v312b219b2-project-technology-evidence-v1"


def technology_spec(requirement_row):
    if (requirement_row.get("score_eligible") is False
            or requirement_row.get("evidence_eligible") is False
            or requirement_row.get("explicit_only_requirement")
            or requirement_row.get("credential_policy")):
        return None
    return requirement(requirement_row.get("text"))


def evaluate_project_technology(spec, records):
    """Choose one supporting record from this project's frozen sources."""
    candidates = []
    for record in records:
        if record.get("source") not in {"resume", "evidence_library"}:
            continue
        kind = record.get("kind")
        if kind == "bullet":
            decision = evaluate_technology_bullet(spec, record.get("text"))
        elif kind in {"tool", "skill"}:
            decision = evaluate(spec, {"section": "skills", "text": record.get("text")})
        else:
            continue
        if decision is not None:
            candidates.append((decision, record))
    if not candidates:
        return None
    # Same strength order and evidence-ID tie break as the native policy.
    return min(candidates, key=lambda pair: (-LABELS[pair[0][0]][0], pair[1]["evidence_id"]))


def evaluate_technology_bullet(spec, wording):
    if spec is None or not isinstance(wording, str) or "\n" in wording or "\r" in wording:
        return None
    return evaluate(spec, {"section": "projects", "source": "frozen_project.bullets[0]", "text": wording})
