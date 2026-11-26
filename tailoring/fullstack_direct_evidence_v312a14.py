"""V3.12-A1.4 opt-in native counterfactual: standalone full-stack proof guard.

No row combination, model inference, or generic frontend/backend keyword promotion.
Only a single project bullet describing implementation of an application qualifies.
This is a conservative experiment, not a definitive semantic parser.
"""
from __future__ import annotations
import re

_IMPLEMENT = re.compile(r"\b(?:built|developed|implemented|engineered|architected|created|delivered|shipped)\b", re.I)
_FRONT = re.compile(r"\b(?:frontend|front-end|react|angular|vue|user interface|ui)\b", re.I)
_BACK = re.compile(r"\b(?:backend|back-end|fastapi|django|flask|postgrest|restful? apis?|server-side|server|api|database|postgresql|supabase)\b", re.I)
_INTEGRATION = re.compile(r"\b(?:full[ -]stack|end[ -]to[ -]end|integrat\w*|connect\w*|spanning|frontend.{0,100}backend|backend.{0,100}frontend)\b", re.I)
_APPLICATION = re.compile(r"\b(?:app(?:lication)?s?|platform|service|system|tracker|product|website|portal|web[ -]app)\b", re.I)
_NEGATIVE = re.compile(
    r"\b(?:did not|didn't|never|without|no)\b.{0,90}\b(?:build|develop|implement|integrat|full[ -]stack|backend|api)\b"
    r"|\b(?:backend|api|full[ -]stack)\b.{0,50}\b(?:not implemented|not developed|not built|wasn't implemented|never implemented)\b"
    r"|\b(?:teammate|someone else|another developer)\b.{0,55}\b(?:handled|built|developed|implemented)\b.{0,40}\b(?:backend|api)\b",
    re.I,
)
_TEST_OBJECT = re.compile(r"\b(?:tests?|testing|test[ -]suite|test[ -]coverage|builds|pipelines?|scans?|checks|automation|ci/cd|github actions)\b", re.I)


def independent_fullstack_implementation(text: str) -> bool:
    """Return true only for a positive single-clause, full-stack application build.

    May return false on valid unfamiliar wording. False negatives are intentional
    for this pre-release scorer candidate. Taxonomy validation is also required.
    """
    value = " ".join(str(text or "").split())
    if _NEGATIVE.search(value):
        return False
    if not (_FRONT.search(value) and _BACK.search(value) and _INTEGRATION.search(value)):
        return False
    for clause in re.split(r"[.;]", value):
        verb = _IMPLEMENT.search(clause)
        if verb is None:
            continue
        after = clause[verb.end():]
        product = _APPLICATION.search(after)
        if product is None or product.start() > 110:
            continue
        test_object = _TEST_OBJECT.search(after)
        if test_object is not None and test_object.start() < product.start():
            continue
        if _FRONT.search(clause) and _BACK.search(clause) and _INTEGRATION.search(clause):
            return True
    return False
