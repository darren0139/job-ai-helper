"""B2.19a candidate: requirement-aware evidence for already-resolved QA.
No new requirement identities, no multi-row completion, no weights changed.
Return None for genuine game QA so the existing game-domain tiers remain intact.
"""
from __future__ import annotations
import re

from tailoring.phase9f_scoring_policy_registry_v312b2190 import (
    GENERAL_SOFTWARE_TESTING_VERSION, NATIVE_POLICY_ACTIVE,
)

VERSION = 'v312b219a-software-testing-v1'
# Match explicit test modalities, not the standalone word 'system' or 'integration'.
_MODE_PATTERNS = {
    'unit': r'unit',
    'integration': r'integration',
    'system': r'system',
    'acceptance': r'(?:user\s+acceptance|acceptance|uat)',
    'regression': r'regression',
    'end_to_end': r'(?:end[ -]to[ -]end|e2e)',
    'functional': r'functional',
    'performance': r'performance',
    'security': r'security',
    'smoke': r'smoke',
    'manual': r'manual',
    'automated': r'(?:automated|automating|automation)',
}
_MODE = '(?:' + '|'.join(_MODE_PATTERNS.values()) + ')'
_TEST = r'test(?:s|ing|ed)?(?:\s+(?:cases?|suites?))?'
# Explicit shared-noun lists, e.g. unit, integration, system and UAT testing.
_LIST = re.compile(r'\b(' + _MODE + r'(?:\s*(?:,\s*(?:and\s+)?|/\s*|\s+and\s+|\s+or\s+)' + _MODE + r')+)\s+' + _TEST + r'\b', re.I)
_GAME = re.compile(r'\b(?:games?|gaming|gameplay|game\s+engine|playtesting|play\s+testing)\b', re.I)
_TESTING = re.compile(r'\b(?:tests?|testing|tested|test\s+cases?|test\s+suites?|uat|quality\s+assurance|qa|bug\s+reproduction|defect\s+verification|regression)\b', re.I)
_AUTHOR_WORD = r'(?:added|authored|created|developed|implemented|wrote|written|writing|designed|maintained)'
_EXEC_WORD = r'(?:executed|ran|running|performed|conducted|carried\s+out)'
_ACTION_WORD = '(?:' + _AUTHOR_WORD + '|' + _EXEC_WORD + ')'
# Match action-to-test spans rather than an unrelated verb elsewhere in a row.
_TEST_OBJECT = (r'\s+(?:(?:the|a|new|comprehensive|automated|manual|software|application|full)\s+)*'
                + r'(?:(?:' + _MODE + r')(?:\s*(?:,\s*(?:and\s+)?|/\s*|\s+and\s+|\s+or\s+)' + _MODE + r')*\s+)?'
                + r'(?:' + _TEST + r'|uat|qa|quality\s+assurance)\b')
_ACTION = re.compile(r'\b' + _ACTION_WORD + r'(?:\s+and\s+' + _ACTION_WORD + r')?' + _TEST_OBJECT + r'|\btested\s+(?:the\s+)?(?:software|applications?|apps?|code|api|web|features?)\b', re.I)
_EXEC = re.compile(r'\b' + _EXEC_WORD + r'(?:\s+and\s+' + _AUTHOR_WORD + r')?' + _TEST_OBJECT, re.I)
_AUTHOR = re.compile(r'\b' + _AUTHOR_WORD + r'(?:\s+and\s+' + _EXEC_WORD + r')?' + _TEST_OBJECT, re.I)
_NEGATIVE = re.compile(r'\b(?:no|not|never|without|lack(?:ed|ing)?|didn.t|haven.t|hasn.t)\b(?:[\s\W]+[\w-]+){0,5}[\s\W]+(?:tests?|testing|tested|uat|qa|quality\s+assurance)\b|\b(?:tests?|testing|uat|qa)\b(?:[\s\W]+[\w-]+){0,4}[\s\W]+(?:not|never)\s+(?:yet\s+)?(?:run|implemented|written|executed|performed|supported|completed)\b', re.I)
_HYPOTHETICAL = re.compile(r'\b(?:planned\s+to|planning\s+to|will|would|intend(?:ed)?\s+to|expected\s+to|want(?:ed)?\s+to|learn(?:ed|ing)?\s+about|tutorial|coursework|observed|watched)\b', re.I)
_THIRD_PARTY = re.compile(r'\b(?:the\s+team|qa\s+team|another\s+team|colleagues?|teammates?|third\s+party|vendor|others)\b.{0,40}\b(?:wrote|ran|executed|performed|implemented|tested|added|created)\b', re.I)
_HARDWARE = re.compile(r'\b(?:hardware|electrical|mechanical|laboratory|clinical|chemical|materials?\s+testing|usability\s+research)\b', re.I)
_SOFTWARE = re.compile(r'\b(?:software|applications?|apps?|code|api|web|python|java|javascript|pytest|junit|test\s+suite|ci|ci/cd|github\s+actions)\b', re.I)
_QUALIFIED = re.compile(r'\b(?:certif(?:ied|ication)|years?\s+of|production|commercial|professional|expert|lead(?:ership)?|manage(?:ment)?|strategy|governance|compliance|iso\s*\d+|collaborat\w*|work\s+with|partner\w*|qa\s+team|test\s+plans?|test\s+cases?|defect\s+(?:investigation|verification|management)|bug\s+reproduction|reproduc\w*)\b', re.I)


# Extend verbs only for general software-testing requirements. Named test
# modalities still need the previous explicit action-to-modality evidence.
_SOFTWARE_SCOPE = r'(?:software|applications?|apps?|frontend|front-end|backend|back-end|web|api)'
_GENERAL_TEST_OBJECT = (
    r'(?:(?:the|a|new|full|existing|automated)\s+)*'
    r'(?:(?:' + _SOFTWARE_SCOPE + r'|' + _MODE + r')(?:\s+and\s+' + _SOFTWARE_SCOPE + r')?\s+)?'
    + _TEST
)
_GENERAL_AUTHOR = re.compile(r'\b' + _AUTHOR_WORD + r'\s+' + _GENERAL_TEST_OBJECT + r'\b', re.I)
_GENERAL_EXECUTE = re.compile(
    r'\b' + _EXEC_WORD + r'\s+' + _GENERAL_TEST_OBJECT
    + r'\b|\btested\s+(?:the\s+)?' + _SOFTWARE_SCOPE + r'\b', re.I,
)
_GENERAL_AUTOMATION = re.compile(
    r'^\s*(?:[-*•]\s*)?(?:(?:I|we|independently|jointly)\s+)?automated\s+(?:(?:' + _SOFTWARE_SCOPE + r'\s+)?builds\s*,\s*(?:and\s+)?){0,2}'
    + _GENERAL_TEST_OBJECT + r'\b', re.I,
)
_GENERAL_SOFTWARE_CONTEXT = re.compile(
    r'\b(?:' + _SOFTWARE_SCOPE + r'|pytest|junit)\b', re.I,
)
_GENERAL_REQUIREMENT = re.compile(
    r'\b' + _SOFTWARE_SCOPE + r'\s+testing\b'
    r'|\b(?:write|author|create|develop|implement|design|execute|run|perform|conduct|automate)\s+'
    + _GENERAL_TEST_OBJECT + r'\b'
    r'|\btest\s+(?:the\s+)?' + _SOFTWARE_SCOPE + r'\b',
    re.I,
)
_GENERAL_BLOCKED_WORK = re.compile(
    r'\b(?:automated|authored|implemented|ran|executed|wrote)\b[^.;,]{0,90}\b(?:tests?|testing)\b'
    r'[^.;,]{0,24}\b(?:were|was)\s+(?:not|never)\s+(?:run|executed|performed)\b'
    r'|\b(?:tests?|testing)\b[^.;,]{0,35}\b(?:written|executed|authored|run)\s+by\s+'
    r'(?:the\s+)?(?:qa|another|external|vendor|third.party|teammates?)\b',
    re.I,
)


def _general_testing_activity(line):
    # A test-related verb needs a software context. CI is context for an
    # explicit test action, but CI configuration alone supplies no such action.
    if _GENERAL_BLOCKED_WORK.search(line):
        return []
    if not (_GENERAL_SOFTWARE_CONTEXT.search(line) or _SOFTWARE.search(line)):
        return []
    actions = []
    for pattern, name in ((_GENERAL_AUTHOR, 'authored'), (_GENERAL_EXECUTE, 'executed'),
                          (_GENERAL_AUTOMATION, 'automated')):
        if pattern.search(line):
            actions.append(name)
    return actions


def modalities(text: str) -> set[str]:
    result = {name for name, pattern in _MODE_PATTERNS.items()
              if re.search(r'\b(?:' + pattern + r')\s+(?:software\s+)?' + _TEST + r'\b', text, re.I)}
    if re.search(r'\bUAT\b', text, re.I):
        result.add('acceptance')
    for found in _LIST.finditer(text):
        for name, pattern in _MODE_PATTERNS.items():
            if re.search(r'\b(?:' + pattern + r')\b', found.group(1), re.I):
                result.add(name)
    # 'automated unit tests' is both automation and unit testing.
    if re.search(r'\bautomated\s+' + _MODE + r'\s+' + _TEST + r'\b', text, re.I):
        result.add('automated')
    return result


def _decision(label, reason, requested, supported):
    return {'label': label, 'reason': reason, 'concepts': ['qa_testing'],
            'qa_testing_policy_version': VERSION,
            'requested_testing_modalities': sorted(requested),
            'supported_testing_modalities': sorted(supported),
            'missing_testing_modalities': sorted(requested - supported)}


def evaluate_software_testing(requirement: dict, evidence: str) -> dict | None:
    focus = str(requirement.get('atomic_focus') or requirement.get('text') or '')
    context = ' '.join(str(requirement.get(k) or '') for k in ('text','parent_text','atomic_focus'))
    if _GAME.search(context):
        return None  # preserve existing game-specific behavior
    requested = modalities(focus)
    order = {'none': 0, 'weak': 1, 'transferable': 2, 'direct': 3}
    # Distinct evidence lines cannot complete a compound requirement together.
    rows = []
    for line in str(evidence or '').splitlines():
        if not line.strip():
            continue
        supported = modalities(line)
        matched = requested & supported
        if _NEGATIVE.search(line) or _HYPOTHETICAL.search(line) or _THIRD_PARTY.search(line):
            rows.append(_decision('none','software_testing_negative_or_unattributed_evidence',requested,set()))
            continue
        if not _TESTING.search(line):
            rows.append(_decision('none','software_testing_activity_missing',requested,set()))
            continue
        if _HARDWARE.search(line) and not _SOFTWARE.search(line):
            rows.append(_decision('none','non_software_testing_context',requested,set()))
            continue
        activities = list(_ACTION.finditer(line))
        action = bool(activities)
        acted_modes = set().union(*(modalities(m.group()) for m in activities))
        executed_modes = set().union(*(modalities(m.group()) for m in _EXEC.finditer(line)))
        authored_modes = set().union(*(modalities(m.group()) for m in _AUTHOR.finditer(line)))
        # Keep broad QA and process-specific demands conservative. A test bullet
        # alone cannot establish QA collaboration, certification or leadership.
        qualified = bool(_QUALIFIED.search(focus))
        if requested:
            if not matched:
                rows.append(_decision('weak' if action and supported else 'none','requested_testing_modalities_not_established',requested,set()))
                continue
            if not action:
                rows.append(_decision('weak','testing_knowledge_without_demonstrated_action',requested,matched))
                continue
            matched = requested & acted_modes
            if not matched:
                rows.append(_decision('weak','testing_mentioned_but_requested_action_not_demonstrated',requested,set()))
                continue
            if matched != requested:
                label = 'transferable' if len(matched)*2 >= len(requested) and not qualified else 'weak'
                rows.append(_decision(label,'partial_named_software_testing_coverage',requested,matched))
                continue
            # Only exact, unqualified named testing work may be direct. Explicit
            # alternatives remain conservative until an OR-aware parser exists.
            if qualified or re.search(r'\b(?:or|and/or)\b',focus,re.I):
                label, reason = 'weak', 'testing_present_other_requested_scope_not_established'
            elif re.search(r'\b(?:execute|run|perform|conduct)\b',focus,re.I) and not requested <= executed_modes:
                label, reason = 'transferable','testing_authorship_not_execution'
            elif re.search(r'\b(?:write|author|create|develop|implement|design)\b',focus,re.I) and not requested <= authored_modes:
                label, reason = 'transferable','testing_execution_not_authorship'
            else:
                label, reason = 'direct','explicit_named_software_testing_activity'
            rows.append(_decision(label,reason,requested,matched))
        else:
            # Broad formal QA is not interchangeable with writing tests. For a
            # plain software-testing request, actual action is transferable;
            # don't infer full lifecycle or process coverage.
            broad_qa = bool(re.search(r'\b(?:qa|quality\s+assurance)\b',focus,re.I))
            if NATIVE_POLICY_ACTIVE and not qualified and not broad_qa and _GENERAL_REQUIREMENT.search(focus):
                general_actions = _general_testing_activity(line)
                if general_actions:
                    rows.append({
                        **_decision('transferable', 'explicit_general_software_testing_activity', requested, set()),
                        'qa_testing_policy_version': GENERAL_SOFTWARE_TESTING_VERSION,
                        'software_testing_activities': general_actions,
                    })
                    continue
            concrete = action and bool(supported or _SOFTWARE.search(line))
            label = 'transferable' if concrete and not qualified and not broad_qa else ('weak' if action else 'none')
            rows.append(_decision(label,'software_testing_activity_bounded_to_requested_scope' if label != 'none' else 'testing_activity_not_demonstrated',requested,set()))
    return max(rows,key=lambda r:(order[r['label']],len(r['supported_testing_modalities'])),default=_decision('none','no_testing_evidence',requested,set()))
