"""Read-only original occurrence coverage and bounded selected-source conflicts.

This ledger never supplies new scoring candidates or changes native deduplication.
Only attributable same-container, same-object/protocol denials prove conflict.
Potentially applicable uncertain scope is quarantined, never declared clean.
"""
from copy import deepcopy
import hashlib
import re

from . import coordinated_policy as policy

LEDGER_VERSION = 'coordinated-original-occurrences-v1'
POLICY_VERSION = 'coordinated-scoped-conflict-quarantine-v1'
_DENIAL = re.compile(r'\b(?P<negative>have\s+never|did\s+not|never|not)\s+'
    r'(?P<verb>maintain(?:ed)?|deploy(?:ed)?|design(?:ed)?|develop(?:ed)?|build|built|'
    r'implement(?:ed)?|create(?:d)?|author(?:ed)?)\s+(?P<object>[^.;!?\n]+)', re.I)
_TIME = re.compile(r'\b(?:before|after|until|since|during|previously|formerly|now|later|earlier|'
                   r'last\s+year|in\s+(?:19|20)\d{2})\b', re.I)
_API = re.compile(r'(?:(?P<protocol>REST(?:ful)?|gRPC)\s+)?(?:API\s+)?'
                  r'(?P<artifact>endpoints?|interfaces?|handlers?)\b(?P<tail>.*)', re.I)
_IMPLEMENT = re.compile(r'\b(?:implemented|developed|built|created|authored|added)\s+', re.I)


def _id(prefix, text):
    return prefix+'_'+hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]


def build_ledger(profile, raw_resume=''):
    """Enumerate supplied originals BEFORE the native evidence index is built."""
    from . import stable_evidence_scoring as native
    occurrences, coverage = [], []

    def add(section, source, container, value, kind):
        if not isinstance(value, str):
            coverage.append({'source': source, 'container': container, 'status': 'UNAVAILABLE_TEXT'})
            return
        text = native._clean_text(value)
        if not text:
            return
        record = {'source': source, 'section': section, 'text': text,
                  'evidence_id': native._stable_id('ev', f'{section}|{native._normalise_basic(text)}')}
        occurrences.append({**record, 'original_text': value, 'kind': kind, 'container': container,
            'container_id': _id('container', container) if container else None,
            'occurrence_id': _id('occ', source+'|'+value)})

    def unscoped(value, source, container=None, section='unindexed'):
        if isinstance(value, str):
            add(section, source, container, value, 'UNINDEXED_FIELD' if section == 'unindexed' else 'UNSCOPED_FIELD')
        elif isinstance(value, dict):
            for key in sorted(value):
                unscoped(value[key], source+'.'+str(key), container, section)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                unscoped(child, f'{source}[{i}]', container, section)
        elif value is not None:
            coverage.append({'source': source, 'container': container, 'status': 'UNAVAILABLE_TEXT'})

    for section in ('projects', 'experience'):
        items = profile.get(section, [])
        if not isinstance(items, list):
            coverage.append({'source': 'resume_profile.'+section, 'container': None, 'status': 'UNAVAILABLE_CONTAINER'})
            continue
        for i, item in enumerate(items):
            container = f'resume_profile.{section}[{i}]'
            if not isinstance(item, dict):
                coverage.append({'source': container, 'container': container, 'status': 'UNAVAILABLE_CONTAINER'})
                continue
            heading = ' — '.join(native._clean_text(item.get(k)) for k in ('title', 'company', 'date') if native._clean_text(item.get(k)))
            add(section, container, container, heading, 'HEADING')
            bullets = item.get('bullets', [])
            if not isinstance(bullets, list):
                coverage.append({'source': container+'.bullets', 'container': container, 'status': 'UNAVAILABLE_BULLETS'})
            else:
                for j, text in enumerate(bullets):
                    add(section, f'{container}.bullets[{j}]', container, text, 'BULLET')
            for key in sorted(item.keys()-{'title', 'company', 'date', 'bullets'}):
                unscoped(item[key], container+'.'+key, container)
    for key in sorted(profile.keys()-{'projects', 'experience'}):
        unscoped(profile[key], 'resume_profile.'+key, section='skills' if key == 'skills' else 'unindexed')
    for i, text in enumerate(raw_resume.splitlines()):
        add('raw_text', f'raw_resume_text[{i}]', None, text, 'RAW_TEXT')
    return {'version': LEDGER_VERSION, 'occurrences': occurrences, 'coverage': coverage}


def attach_index_coverage(ledger, index):
    """Annotate coverage, without changing either the input ledger or index."""
    from . import stable_evidence_scoring as native
    ledger = deepcopy(ledger)
    for original in ledger['occurrences']:
        exact = any(all(r.get(k) == original[k] for k in ('source', 'section', 'text', 'evidence_id')) for r in index)
        alias = any(native._normalise_basic(r['text']) == native._normalise_basic(original['text'])
                    and r['section'] == original['section'] for r in index)
        original['index_status'] = 'INDEXED_ORIGINAL' if exact else 'DUPLICATE_OTHER_ORIGIN' if alias else 'UNINDEXED_ORIGINAL'
    return ledger


def _api_scope(text):
    match = _API.fullmatch(text.strip(' ,:'))
    if not match:
        return None
    tail = match['tail'].strip(' ,:')
    route = re.fullmatch(r'(?:at|for)\s+(/[^\s]+)', tail, re.I)
    language = re.fullmatch(r'in\s+(?:Java|Python|Go|C#|C\+\+|TypeScript)', tail, re.I)
    return {'protocol': ('rest' if match['protocol'].lower().startswith('rest') else 'grpc') if match['protocol'] else None,
            'artifact': match['artifact'].lower().rstrip('s'),
            'route': route[1] if route else None,
            'uncertain_tail': bool(tail and not route and not language)}


def _api_positives(text):
    out = []
    for clause in re.finditer(r'[^.;!?\n]+', text):
        for match in _IMPLEMENT.finditer(clause[0]):
            if re.search(r'\b(?:not|never|will|learned|vendor|team|we)\b', clause[0][:match.start()], re.I):
                continue
            scope = _api_scope(clause[0][match.end():])
            if scope:
                out.append({**scope, 'span': [clause.start()+match.start(), clause.end()]})
    return out


def claims_for_parent(obligation, ledger):
    """Per-original diagnostic proofs; not scoring admission or action union."""
    verified = [{k: r[k] for k in ('source', 'section', 'text', 'evidence_id')}
                for r in ledger['occurrences'] if r['section'] in ('projects', 'experience')]
    return [{'occurrence_id': r['occurrence_id'], 'source': r['source'], 'container': r['container'],
             'index_status': r.get('index_status'), 'proof': policy.detect(obligation, r, verified),
             'api_implementation_clauses': _api_positives(r['text']),
             'lexical_denials': [{'text': m[0], 'verb': m['verb'], 'object': m['object'],
                                  'span': list(m.span())} for m in _DENIAL.finditer(r['text'])]}
            for r in ledger['occurrences']]


def inspect_selected(obligation, selected, ledger, index):
    """Assess ONE existing selected original; never select a fallback or union."""
    result = {'policy_version': POLICY_VERSION, 'ledger_version': LEDGER_VERSION,
              'status': 'NO_APPLICABLE_CONFLICT', 'quarantine': False,
              'selected_positive': deepcopy(selected), 'findings': [],
              'selection_policy': 'UNCHANGED_NATIVE_SELECTION_NO_LEDGER_FALLBACK'}
    original = next((r for r in ledger['occurrences'] if all(selected.get(k) == r[k]
                     for k in ('source', 'section', 'text', 'evidence_id'))), None)
    if (obligation.get('status') != 'SUPPORTED' or not obligation.get('raw_jd_parent_span') or not original
            or not any(all(selected.get(k) == r.get(k) for k in ('source', 'section', 'text', 'evidence_id')) for r in index)):
        return {**result, 'status': 'UNCERTAIN_SOURCE', 'quarantine': True, 'reason': 'selected_original_not_fully_verified'}
    result['selected_occurrence_id'] = original['occurrence_id']
    # Full occurrence index verifies original receipts for diagnosis only. It is
    # never passed to a native scorer, ranker, recovery or reselection function.
    occurrence_index = [{k: r[k] for k in ('source', 'section', 'text', 'evidence_id')}
                        for r in ledger['occurrences'] if r['section'] in ('projects', 'experience')]
    proof = policy.detect(obligation, selected, occurrence_index)
    positive_actions = set(proof.get('technical_supported_actions', []))
    api_positive = _api_positives(selected['text']) if obligation.get('object_family') == 'backend' else []
    for issue in ledger['coverage']:
        if issue['container'] == original['container']:
            result['findings'].append({'kind': 'SOURCE_COVERAGE', 'status': 'UNCERTAIN', 'negative_original': issue,
                                      'reason': 'unavailable_original_scope_cannot_be_declared_clean'})
    for other in ledger['occurrences']:
        if other['container'] and other['container'] != original['container']:
            continue
        for clause in re.finditer(r'[^.;!?\n]+', other['text']):
            for match in _DENIAL.finditer(clause[0]):
                prefix = clause[0][:match.start()].strip(' ,:')
                if re.search(r'\b(?:vendor|they|colleague|supplier|someone|others)\b', prefix, re.I):
                    continue  # explicit third-party denial is not candidate denial
                actor_uncertain = bool(prefix and not re.fullmatch(r'I(?:\s+personally)?', prefix, re.I))
                temporal = bool(_TIME.search(clause[0]) or _TIME.search(selected['text']))
                rhs = match['object'].strip(' ,:')
                action = policy.prior.action_kind(match['verb'])
                if action is None and match['verb'].lower().startswith(('creat', 'author')):
                    action = 'develop'  # negative creation/authorship only
                exact_object = policy.prior.normal(rhs) == policy.prior.normal(obligation['object'])
                # A qualified time is uncertainty, not a clean source or an
                # invented overlap/disjointness proof.
                stripped_time = re.split(r'\s+(?:before|after|until|since|during|in\s+(?:19|20)\d{2})\b', rhs, flags=re.I)[0]
                timed_object = temporal and policy.prior.normal(stripped_time) == policy.prior.normal(obligation['object'])
                short_object = policy.prior.normal(rhs) in ('it', 'them', 'these modules', 'the modules') or (
                    policy.prior.normal(obligation['object']).startswith(policy.prior.normal(rhs)+' ')
                    and bool(policy.technical_object(obligation, rhs)['artifact_family_proven']))
                kind = None
                uncertain = actor_uncertain or temporal or other['container'] is None or other['kind'] == 'UNINDEXED_FIELD'
                scope = None
                if action in positive_actions and (exact_object or timed_object or short_object):
                    kind = 'MANDATORY_ACTION'
                    uncertain |= not exact_object
                    scope = {'action': action, 'required_object': obligation['object'], 'denied_object': rhs}
                if kind is None and api_positive and action == 'develop':
                    negative_api = _api_scope(rhs)
                    if negative_api:
                        for positive_api in api_positive:
                            if positive_api['artifact'] != negative_api['artifact']:
                                continue
                            if positive_api['protocol'] and negative_api['protocol'] and positive_api['protocol'] != negative_api['protocol']:
                                continue
                            if positive_api['route'] and negative_api['route'] and positive_api['route'] != negative_api['route']:
                                continue
                            kind = 'API_IMPLEMENTATION'
                            uncertain |= (not positive_api['protocol'] or not negative_api['protocol']
                                or positive_api['route'] != negative_api['route']
                                or positive_api['uncertain_tail'] or negative_api['uncertain_tail'])
                            scope = {'positive_api': positive_api, 'denied_api': negative_api}
                            break
                if kind:
                    result['findings'].append({'kind': kind, 'status': 'UNCERTAIN' if uncertain else 'PROVEN_CONFLICT',
                        'relationship': 'SAME_ORIGINAL_CONTAINER' if other['container'] == original['container'] else 'UNRESOLVED_SOURCE_SCOPE',
                        'positive_occurrence_id': original['occurrence_id'], 'negative_original': deepcopy(other),
                        'negative_span': [clause.start()+match.start(), clause.start()+match.end()],
                        'scope': scope, 'reason': 'explicit_denial_of_selected_ownership' if not uncertain else 'potential_denial_scope_requires_review'})
    if result['findings']:
        proven = any(f['status'] == 'PROVEN_CONFLICT' for f in result['findings'])
        result.update(status='PROVEN_CONFLICT' if proven else 'UNCERTAIN_SCOPE', quarantine=True,
                      reason='selected_original_has_applicable_conflict' if proven else 'selected_original_scope_not_proven_clean')
    else:
        result['reason'] = 'no_applicable_denial_in_reviewed_original_occurrences'
    return result
