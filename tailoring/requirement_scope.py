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


TECHNOLOGY_IDENTITY_CONCEPTS = ('Python', 'SQL', 'Azure', 'JavaScript', 'AWS', 'TypeScript',
            'Elasticsearch', 'Java', 'S3', 'FastAPI')
PURE_TECHNOLOGY_SCOPES = {'PURE_ATOMIC_TECHNOLOGY', 'PURE_TECHNOLOGY_AND_LIST',
        'PURE_TECHNOLOGY_OR_LIST', 'PURE_TECHNOLOGY_ONE_OF_OR_EXAMPLE_LIST'}
IDENTITY_ACTIVITY = r'\b(?:build\w*|design\w*|deploy\w*|implement\w*|secur(?:e|ing)|develop\w*|manag\w*|architect\w*)\b'

def _identity_clean(text):
    return ' '.join(str(text or '').split()).strip()


def _identity_entity(text):
    # Deliberately narrower than registry's such-as extraction: full scope only.
    text = _identity_clean(text)
    text = re.sub(r'^(?:(?:hands[- ]on|strong|working)\s+)?(?:experience|proficiency|knowledge|familiarity)\s+(?:with|in|using|of)\s+', '', text, flags=re.I)
    return text.strip(' ;')


def _identity_provenance(requirement):
    from analysis_stability.stable_evidence_scoring import _split_single_requirement_clause
    sources = requirement.get('source_provenance') or []
    if not sources:
        return False
    text = _identity_clean(requirement.get('text'))
    for source in sources:
        if not all(source.get(k) for k in ('parent_occurrence_id', 'parent_text', 'raw_parent_text', 'source')):
            return False
        if source.get('contributes_scoring_allocation', True):
            parent = _identity_clean(source['parent_text'])
            # Native allocation can retain a child while losing an activity tail.
            # Recognition cannot repair that semantic loss on behalf of its parent.
            if any(re.search(IDENTITY_ACTIVITY, _identity_clean(source[k]), re.I)
                   for k in ('parent_text', 'raw_parent_text')):
                return False
            if parent != text:
                clauses = _split_single_requirement_clause(parent, requirement.get('importance') or 'core')
                if text not in {_identity_clean(c['text']) for c in clauses}:
                    return False
    return True


def technology_identity_scope(requirement, *, registry=None):
    """One complete-scope decision; no substring lookup grants recognition."""
    from taxonomy_discovery.technology_registry import get_default_registry, resolve_requirement_text, normalise
    from tailoring.phase6d6_structured_matching import technology_requirement_structure, _PROGRAMMING_LIST, _split_alternatives
    registry = registry or get_default_registry()
    text = _identity_clean(requirement.get('atomic_focus') or requirement.get('text'))
    structure = technology_requirement_structure(requirement)
    result = {'category': 'AMBIGUOUS', 'reason': 'No bounded complete identity scope',
              'structure': structure, 'identities': [], 'identity_resolved': False,
              'capability_id': None}
    if re.search(r'(?<![\w.])net\b', text, re.I) or '\ufffd' in text or '\u200b' in text:
        return {**result, 'category': 'PARSER_OR_DECOMPOSITION_BLOCKED', 'reason': 'Corrupted or ambiguous normalization'}
    if re.search(r'\b(?:collaborat\w*|communicat\w*|teamwork|stakeholders)\b', text, re.I):
        return {**result, 'category': 'MIXED_SCOPE', 'reason': 'Behavioral and technical scope'}
    if re.search(IDENTITY_ACTIVITY, text, re.I):
        return {**result, 'category': 'TECHNOLOGY_PLUS_ACTIVITY', 'reason': 'Named activity requires independent capability resolution'}
    if re.search(r'\b(?:distributed systems|database design|cloud architecture|programming skills|backend development)\b', text, re.I):
        return {**result, 'category': 'TECHNOLOGY_PLUS_CAPABILITY', 'reason': 'Capability scope exceeds technology identity'}
    non_identity = {normalise(a) for e in registry.entries if e.get('entry_kind') == 'architecture_pattern' for a in e['aliases']}
    if normalise(_identity_entity(text)) in non_identity:
        return {**result, 'category': 'TECHNOLOGY_PLUS_CAPABILITY', 'reason': 'Registry architecture pattern is not a technology identity'}
    if not _identity_provenance(requirement):
        return {**result, 'category': 'PARSER_OR_DECOMPOSITION_BLOCKED', 'reason': 'Missing, activity-bearing, or unverifiable parent provenance'}
    aliases = {normalise(a) for e in registry.entries if e.get('entry_kind') != 'architecture_pattern' for a in e['aliases']} | {normalise(t) for t in TECHNOLOGY_IDENTITY_CONCEPTS}
    components = structure['components']
    terms = [_identity_entity(c['atomic_focus']) for c in components] if components else [_identity_entity(text)]
    if not all(normalise(t) in aliases for t in terms):
        return {**result, 'category': 'PARSER_OR_DECOMPOSITION_BLOCKED' if components or re.search(r'\b(and|or|such as|one or more)\b|[,()]', text, re.I) else 'AMBIGUOUS',
                'reason': 'Complete scope not bounded by native identity structure'}
    if components:
        # Native evidence terms alone are not proof of whole requirement scope.
        native_optional_head = re.fullmatch(r'(?:experience|knowledge|proficiency)\s+(?:in|of|with)\s+languages?\s+such\s+as\s+(?P<tail>.+)', text, re.I)
        if structure['source'] != 'native_jd_decomposition' and not (_PROGRAMMING_LIST.fullmatch(text) or native_optional_head):
            return {**result, 'category': 'PARSER_OR_DECOMPOSITION_BLOCKED', 'reason': 'Native component diagnostics do not establish whole scope'}
        if re.search(r'\b(?:is|are|would be|will be)\b', text, re.I) and not re.search(r'\b(?:is|are|would be|will be) (?:expected|required|preferred|advantageous|a plus)$', text, re.I):
            return {**result, 'category': 'MIXED_SCOPE', 'reason': 'Unbounded qualifier tail'}
        if structure['source'] != 'native_jd_decomposition':
            match = _PROGRAMMING_LIST.fullmatch(text) or native_optional_head
            expected, mode = _split_alternatives(match.group('tail'))
            if [normalise(t) for t in expected] != [normalise(t) for t in terms] or mode != structure['mode']:
                return {**result, 'category': 'PARSER_OR_DECOMPOSITION_BLOCKED', 'reason': 'Stored native terms differ from full parent alternatives'}
        optional = bool(re.search(r'\b(?:one or more of|any of|languages? such as)\b', text, re.I))
        # Native "all" for such-as examples must never become mandatory examples.
        if optional and structure['mode'] != 'any':
            return {**result, 'category': 'PARSER_OR_DECOMPOSITION_BLOCKED', 'reason': 'Native optional semantics unavailable'}
        category = 'PURE_TECHNOLOGY_ONE_OF_OR_EXAMPLE_LIST' if optional else ('PURE_TECHNOLOGY_AND_LIST' if structure['mode'] == 'all' else 'PURE_TECHNOLOGY_OR_LIST')
    else:
        category = 'PURE_ATOMIC_TECHNOLOGY'
    identities = [resolve_requirement_text(t, registry=registry) for t in terms]
    if any(len({e['technology_id'] for e in registry.entries if normalise(t) in {normalise(a) for a in e['aliases']}}) > 1 for t in terms):
        return {**result, 'reason': 'Ambiguous registry alias ownership'}
    recognized = [bool(i.get('technology_id')) and i['status'] in {'resolved', 'recognized_unmapped'} for i in identities]
    complete = any(recognized) if components and structure['mode'] == 'any' else all(recognized)
    return {**result, 'category': category, 'identities': identities,
            'identity_resolved': complete,
            'knowledge_outcome': 'RESOLVED_BY_TECHNOLOGY_IDENTITY' if complete else 'UNRESOLVED',
            'reason': 'Complete technology obligation recognized' if complete else 'Mandatory identity absent; validated proposal required'}
