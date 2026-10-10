"""Bounded requirement-side rules with native, whole-sentence provenance.

These rules recognize existing capabilities; they never supply evidence tiers.
"""
import re

ROLE_FUNCTIONS = {
    "engineering": ["fellow engineers", "software engineers", "engineers", "technical lead", "architect"],
    "policy": ["policy officers", "various partner agencies", "partner agencies"],
    "design": ["ux designers", "designers", "solution architects"],
    "security": ["cybersecurity specialists"],
    "business": ["business analysts", "product owners", "project manager"],
}
CONTEXTUAL_REQUIREMENT_RULES = {
    "collaboration.cross_functional": "explicit_collaboration_with_multiple_named_functions",
}


def scope_surface(value):
    return str(value or "").replace("\u200b", "").replace("\u2019", "'").strip().rstrip(". ")


def collaboration_functions(text):
    """Validated whole-statement grammar, not a noun/keyword count."""
    roles = re.fullmatch(
        r"(?:you will |you'll )?(?:work|collaborate) closely with (.+?)(?: within an agile environment| as part of the project delivery)?",
        scope_surface(text), re.I,
    )
    if not roles:
        return []
    parts = [p.strip().lower() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", roles[1])]
    known = {name for names in ROLE_FUNCTIONS.values() for name in names}
    functions = {f for p in parts for f, names in ROLE_FUNCTIONS.items() if p in names}
    return sorted(functions) if len(functions) >= 2 and all(p in known for p in parts) else []


def complete_named_function_scope(requirement):
    """Every recorded occurrence must prove the same native sentence scope.

    Text-only callers and conflicting/missing parent grounding fail closed.
    A raw section may contain other independent sentences only when native
    grounding identifies this complete sentence within that recorded source.
    """
    text = scope_surface(requirement.get("atomic_focus") or requirement.get("text"))
    functions = collaboration_functions(text)
    provenance = requirement.get("source_provenance")
    if not functions or not isinstance(provenance, list) or not provenance:
        return None
    for parent in provenance:
        if not isinstance(parent, dict):
            return None
        grounding = parent.get("grounding") or {}
        raw = scope_surface(parent.get("raw_parent_text"))
        sentence = scope_surface(grounding.get("sentence_text"))
        if not (raw and grounding.get("kind") == "explicit_raw_section"
                and grounding.get("span_id")
                and type(grounding.get("sentence_index")) is int
                and grounding["sentence_index"] >= 1
                and sentence.casefold() == text.casefold()
                and sentence.casefold() in raw.casefold()):
            return None
        # A shortened canonical text must not conceal an uncovered obligation.
        for value in (requirement.get("text"), parent.get("parent_text")):
            if value and scope_surface(value).casefold() != text.casefold():
                return None
    return {"functions": functions, "scope": "complete_native_sentence", "provenance_required": True}
