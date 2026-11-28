"""Opt-in B2.22d-4b experiment. No production caller uses this policy."""
from dataclasses import dataclass
import re

from tailoring.fullstack_direct_evidence_v312a14 import independent_fullstack_implementation
from tailoring.technology_database_evidence_v312b219b import BLOCK

VERSION = "v312b222d4b-fullstack-owned-project-candidate-v1"

_NON_OWNED = re.compile(
    r"\b(?:would|could have|planned|proposed|intended|hypothetical|tutorial|"
    r"vendor[- ](?:owned|provided)|(?:built|developed|implemented) by|"
    r"(?:the vendor|another team|someone else|third party) (?:built|developed|implemented)|"
    r"did not|didn't|was not implemented|were not implemented|never implemented)\b"
)
_START = r"^(?:i |we )?(?:jointly |independently )?"
_BUILD = re.compile(_START + r"(?:built|developed|implemented|created|engineered|extended)\s+(?P<object>.+)")
_BRIDGE = re.compile(_START + r"(?:connected|integrated|wired)\s+(?P<object>.+)")
_FRONT = re.compile(r"\b(?:front[ -]?end|react|user interface|ui|angular|vue)\b")
_BACK = re.compile(r"\b(?:back[ -]?end|fastapi|django|api endpoints?|server[ -]side)\b")
_FEATURE = re.compile(
    r"\b(?:features?|endpoints?|handlers?|routes?|forms?|workflows?|pages?|views?|edit(?:or|ing)|"
    r"authentication|login|sessions?|registration|search|checkout|requests?|controls?|dashboards?)\b"
)
_ADJACENT = re.compile(
    r"\b(?:tests?|testing|ci|builds|pipelines?|deployment|configuration|scans?|audits?|probes?|"
    r"monitoring|migrations?|installation|documentation|mockups?)\b"
)
_STOP = {
    "and", "the", "this", "with", "for", "from", "into", "using", "built", "developed", "implemented",
    "created", "engineered", "extended", "connected", "integrated", "wired", "react", "fastapi", "angular",
    "vue", "django", "frontend", "backend", "front", "back", "end", "api", "application", "app",
    "endpoints", "endpoint", "features", "feature", "interface", "project", "server", "client",
    "workflows", "workflow", "system", "platform", "service", "web", "across",
}


@dataclass(frozen=True)
class Link:
    label: str
    evidence_ids: tuple[str, ...] = ()


def _parts(wording):
    text = " ".join(wording.casefold().split())
    if _NON_OWNED.search(text) or BLOCK.search(text):
        return None
    # Require the initial applicant verb to own the described work. Avoid
    # borrowing implementation terms from an unrelated trailing clause.
    clause = re.split(r";|\.(?=\s)|\b(?:but|whereas|while)\b", text, maxsplit=1)[0]
    found = _BUILD.match(clause) or _BRIDGE.match(clause)
    if not found:
        return None
    obj = found["object"]
    if _ADJACENT.search(obj):
        return None
    return clause, obj


def evaluate_wording(wording):
    """Evaluate this row alone. A project composite never makes its rows direct."""
    parts = _parts(wording)
    if not parts:
        return "none"
    clause, obj = parts
    if _BUILD.match(clause) and independent_fullstack_implementation(clause):
        return "direct"
    if _FEATURE.search(obj) and (_FRONT.search(obj) or _BACK.search(obj)):
        return "transferable"
    return "none"


def _feature_terms(text):
    return set(re.findall(r"[a-z][a-z0-9]+", text)) - _STOP


def evaluate_project(project_id, records):
    """Evaluate owned bullet/impact rows within one resolved project at a time."""
    if not project_id:
        return Link("none")
    owned = [r for r in records if r.get("project_id") == project_id
             and r.get("kind") in {"bullet", "impact"}
             and r.get("source") in {"resume", "evidence_library"}
             and r.get("evidence_id") and isinstance(r.get("text"), str)]
    direct = next((r for r in owned if evaluate_wording(r["text"]) == "direct"), None)
    if direct:
        return Link("direct", (direct["evidence_id"],))
    transferable = [r for r in owned if evaluate_wording(r["text"]) == "transferable"]
    for bridge in transferable:
        clause, obj = _parts(bridge["text"])
        if not (_BRIDGE.match(clause) and _FRONT.search(obj) and _BACK.search(obj)) or re.search(r"\bexternal\b", obj):
            continue
        terms = _feature_terms(obj)
        sides = {"front": [], "back": []}
        for record in transferable:
            if record["source"] != bridge["source"] or record is bridge:
                continue
            work, target = _parts(record["text"])
            if not _BUILD.match(work) or not terms.intersection(_feature_terms(target)):
                continue
            front, back = bool(_FRONT.search(target)), bool(_BACK.search(target))
            if front != back:
                sides["front" if front else "back"].append(record["evidence_id"])
        if sides["front"] and sides["back"]:
            return Link("direct", (sides["front"][0], sides["back"][0], bridge["evidence_id"]))
    return Link("transferable", (transferable[0]["evidence_id"],)) if transferable else Link("none")
