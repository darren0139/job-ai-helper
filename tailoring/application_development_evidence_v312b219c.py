"""B2.19c recognition of owned application implementation in one evidence record."""
from dataclasses import dataclass
import re

from tailoring.phase9f_scoring_policy_registry_v312b2190 import APPLICATION_DEVELOPMENT_VERSION as VERSION
from tailoring.technology_database_evidence_v312b219b import BLOCK, LABELS, norm, visible

_ACTION = {
    "build": "implementation", "develop": "implementation", "create": "implementation",
    "implement": "implementation", "design and develop": "implementation",
    "enhance": "enhancement", "extend": "enhancement", "improve": "enhancement",
    "maintain": "maintenance",
}
_VERBS = {
    "built": "implementation", "developed": "implementation", "created": "implementation",
    "implemented": "implementation", "engineered": "implementation", "scripted": "implementation",
    "enhanced": "enhancement", "extended": "enhancement", "improved": "enhancement",
    "maintained": "maintenance", "fixed": "maintenance", "patched": "maintenance", "refactored": "maintenance",
    "integrated": "integration", "connected": "integration",
}
_APP = r"(?:applications?|apps?|websites?|web\s+apps?|software\s+systems?|game\s+engines?|(?:mobile|video|desktop)\s+games?|(?:request|issue|ticket|task|workout)\s+trackers?)"
_FEATURE = r"(?:features?|functionality|modules?|workflows?|sessions?|(?:image|file) attachment support)"
_REQUIREMENT = re.compile(
    r"^(?:(?:experience|proficiency) (?:in|with) |responsible for )?"
    r"(?P<actions>(?:design and develop|build|develop|create|implement|enhance|extend|improve|maintain)"
    r"(?: and (?:develop|enhance|extend|improve|maintain))?) "
    r"(?:(?:new|existing|software|web|mobile|desktop|cloud|enterprise) )*"
    rf"(?P<object>{_APP}|software|application {_FEATURE}|software {_FEATURE})"
    r"(?P<specifications> to meet (?:functional and technical|technical and functional|functional|technical) specifications)?$"
)
_NOMINAL_DEVELOPMENT = re.compile(
    r"^(?:(?:experience|proficiency) (?:in|with) )?"
    r"(?:software (?:application )?development|(?:web|mobile|desktop|software) application development|"
    r"application development)$"
)
_SPECIFICATION = re.compile(
    r"\b(?:to meet|according to|in accordance with|in line with|against) "
    r"(?:the )?(?P<scope>functional and technical|technical and functional|functional|technical) specifications\b"
)
_CADENCE = re.compile(r"\b(?:regularly|continually|continuously|ongoing|weekly|monthly|across (?:multiple |successive )?releases)\b")
_OWNED = re.compile(
    r"^(?:(?:i|we) )?(?:(?:jointly|independently|successfully|regularly|continually|continuously) )*"
    rf"(?P<actions>(?:{'|'.join(_VERBS)})(?: and (?:{'|'.join(_VERBS)}))?)\s+(?P<object>.+)$"
)
_APP_IN_RECORD = re.compile(rf"\b{_APP}\b")
_FEATURE_IN_RECORD = re.compile(rf"\b{_FEATURE}\b")
_SOFTWARE_CONTEXT = re.compile(
    rf"\b(?:{_APP}|frontend|front-end|backend|back-end|user interface|ui|react|streamlit|fastapi|"
    r"django|flask|android|ios|kotlin|swift|electron|unity)\b"
)
_OTHER_OBJECT = re.compile(
    r"\b(?:tests?|testing|test suites?|ci|ci/cd|github actions|qa|audit tooling|regression tooling|"
    r"build pipelines?|deployment scripts?|monitoring|documentation|report templates?|simulation hardware)\b"
)
_UNOWNED = re.compile(
    r"\b(?:assigned to|owned by|handled by|another developer|another employee|"
    r"provided by|outsource[ds]?|planned|proposed|prototype only)\b"
)


@dataclass(frozen=True)
class DevelopmentRequirement:
    actions: frozenset[str]
    specifications: frozenset[str]
    ongoing: bool
    feature_scope: bool = False


def requirement(row):
    if (row.get("score_eligible") is False or row.get("evidence_eligible") is False
            or row.get("explicit_only_requirement") or row.get("credential_policy")):
        return None
    text = norm(row.get("text")).strip(".")
    text = re.sub(r" (?:will be an added advantage|is an added advantage|is preferred|is a plus)$", "", text)
    ongoing = text.startswith(("continually ", "continuously ", "regularly "))
    if ongoing:
        text = text.split(" ", 1)[1]
    match = _REQUIREMENT.fullmatch(text)
    if match is None:
        if not ongoing and _NOMINAL_DEVELOPMENT.fullmatch(text):
            return DevelopmentRequirement(frozenset({"implementation"}), frozenset(), False)
        return None
    verbs = match["actions"]
    verbs = verbs.replace("design and develop", "develop")
    return DevelopmentRequirement(
        frozenset(_ACTION[verb] for verb in verbs.split(" and ")),
        frozenset(re.findall(r"functional|technical", match["specifications"] or "")),
        ongoing,
        _FEATURE_IN_RECORD.search(match["object"]) is not None,
    )


def evaluate(spec, evidence):
    """Return the evidence-backed action and qualifier decision for exact wording."""
    if spec is None or not isinstance(evidence, str) or "\n" in evidence or "\r" in evidence:
        return None
    text = norm(evidence).lstrip("-•* ")
    if BLOCK.search(text) or _UNOWNED.search(text):
        return None
    # Independent clauses cannot stand in for the action that built the product.
    clause = re.split(r";|\.(?=\s)|\b(?:but|whereas|while|however)\b", text, maxsplit=1)[0].rstrip(".")
    owned = _OWNED.match(clause)
    if owned is None:
        return None
    obj = owned["object"]
    action_object = re.split(r"\b(?:for|using|with|via|about|to demonstrate|to meet)\b", obj, maxsplit=1)[0]
    product = _APP_IN_RECORD.search(action_object)
    feature = _FEATURE_IN_RECORD.search(action_object) if _SOFTWARE_CONTEXT.search(obj) else None
    if spec.feature_scope and feature is None:
        return None
    supported_object = min((match for match in (product, feature) if match), key=lambda match: match.start(), default=None)
    if supported_object is None or supported_object.start() > 115:
        return None
    separate_object = _OTHER_OBJECT.search(action_object)
    if separate_object and separate_object.start() < supported_object.start():
        return None
    actions = {_VERBS[verb] for verb in owned["actions"].split(" and ")}
    # Enhancements establish development on unqualified requirements.
    if spec.actions == {"implementation"} and "enhancement" in actions:
        actions.add("implementation")
    if not spec.actions <= actions:
        return None
    if spec.specifications:
        matched = _SPECIFICATION.search(clause)
        if not matched or not spec.specifications <= set(re.findall(r"functional|technical", matched["scope"])):
            return None
    if spec.ongoing and not _CADENCE.search(clause):
        return None
    return "direct"


def apply_policy(rows, evidence_index, raw_text):
    """Use one visible, applicant-owned row and preserve canonical geometry."""
    audit = []
    for row in rows:
        spec = requirement(row)
        if spec is None:
            continue
        matches = []
        for evidence in evidence_index:
            section = evidence.get("section")
            source = str(evidence.get("source", ""))
            if section not in {"projects", "experience", "raw_text"}:
                continue
            if section != "raw_text" and ".bullets[" not in source:
                continue
            if evaluate(spec, evidence.get("text")) and visible(evidence, raw_text):
                matches.append(evidence)
        matched = min(matches, key=lambda item: (item.get("section") == "raw_text",
                                                item.get("evidence_id", "")), default=None)
        label = "direct" if matched else "none"
        value, strength = LABELS[label]
        receipt = {"policy_version": VERSION, "requirement_id": row.get("requirement_id"),
                   "previous_label": row.get("match_label"), "label": label,
                   "actions": sorted(spec.actions), "specifications": sorted(spec.specifications),
                   "ongoing": spec.ongoing, "selected_evidence_id": matched.get("evidence_id") if matched else None}
        for key in ("capability_none_recovery", "capability_taxonomy_cap_reason", "capability_evidence_reselection"):
            row.pop(key, None)
        row.update(match_label=label, match_value=value, evidence_strength=strength,
                   evidence=[{**matched, "reason": "One visible wording establishes the requested application development work."}] if matched else [],
                   match_source="v312b219c_application_development" if matched else "missing",
                   v312b219c_policy_audit=receipt)
        audit.append(receipt)
    return audit
