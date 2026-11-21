"""Bounded display diagnostics over existing, document-bound ranked evidence.

No scorer, optimizer, document renderer, model, database or network calls.
Inputs are the existing rank_bullets output, not user-assigned native scores.
"""
from functools import lru_cache
import json
import re

VERSION = 'bullet-relevance-diagnostic-v1.2'
HARD = {'core', 'required', 'deal_breaker'}
BONUS = {'preferred', 'supporting', 'bonus'}
LABELS = {'weak': 1, 'transferable': 2, 'direct': 3}
UNCERTAIN = re.compile(r'\b(?:not|never|without|plan(?:ned)?|intend|will|aspire|hope)\b', re.I)
PERFORMED = re.compile(r'\b(?:built|developed|added|implemented|wrote|performed|executed|tested|designed|automated|verified|maintained|deployed|integrated|delivered|created|managed|led|ran|run|carried|validated|configured|resolved|supported|optimized|analysed|analyzed)\b', re.I)
TEST_TERMS = {
    'unit testing': r'\bunit\s+test(?:s|ing)?\b',
    'regression testing': r'\bregression\s+test(?:s|ing)?\b',
    'integration testing': r'\bintegration\s+test(?:s|ing)?\b',
    'system testing': r'\bsystem\s+test(?:s|ing)?\b',
    'user acceptance testing': r'\b(?:user acceptance test(?:s|ing)?|UAT)\b',
}


def _text(value):
    return ' '.join(str(value).split()).casefold()


def _evidence(row, catalog):
    from tailoring.bullet_choice_estimated import action_status
    supported = {}
    warnings = []
    status = action_status(row['bullet'])
    if status == 'negated_or_nonperformed':
        return {}, ['Negated, planned or ambiguous wording: native support withheld by this diagnostic.']
    if status != 'performed_claim':
        return {}, ['No clear performed-action wording: treat terminology as lexical until independently reviewed.']
    for link in row.get('jd_links', []):
        rid = link.get('id')
        req = catalog.get(rid)
        if not req or link.get('status') != 'Native document evidence':
            continue
        if (req.get('evidence_eligible') is False or req.get('score_eligible') is False
                or req.get('importance') not in HARD | BONUS):
            warnings.append('Ineligible or unclassified requirement: diagnostic support withheld.')
            continue
        if (link.get('text'), link.get('importance')) != (req['text'], req['importance']):
            warnings.append('Requirement identity/classification mismatch; support withheld.')
            continue
        for native in link.get('native_evidence', {}).values():
            strength = native.get('strength')
            label = native.get('match_label')
            if (label in LABELS and type(strength) is int and 0 < strength <= 5
                    and _text(native.get('excerpt', '')) == _text(row['bullet'])):
                value = (LABELS[label], strength)
                supported[rid] = max(supported.get(rid, (0, 0)), value)
    return supported, warnings


def compare_ranked_bullets(base, library, catalog, selected=()):
    """One selected pair only. Caller supplies existing validated ranking records.

    Exact native excerpts indicate recorded document evidence, not independent
    source attestation or a measured causal contribution of this bullet.
    """
    if len(selected) > 2000 or sum(len(r.get('jd_links', ())) for r in [base, library, *selected]) > 4096:
        return {'version': VERSION, 'outcome': 'Insufficient verified evidence to determine a preference.',
                'reason': 'Diagnostic input bound exceeded; no portfolio was silently truncated.', 'native_impact': 'unmeasured'}
    payload = json.dumps([base, library, catalog, list(selected)], sort_keys=True, ensure_ascii=False)
    return json.loads(_compare_cached(payload))


def selection_alignment(outcome, base_selected, library_selected, recorded):
    """Explain agreement without inventing the optimizer's historical cause."""
    if not recorded:
        return 'Saved selection membership is unavailable; agreement cannot be established.'
    if base_selected and library_selected:
        return 'Both wordings were selected; neither defeated the other.'
    if not base_selected and not library_selected:
        return 'Both wordings were excluded; an individual rejection cause was not measured.'
    leader = 'Base' if outcome.startswith('Base has stronger') else 'Library' if outcome.startswith('Library has stronger') else None
    if leader is None:
        return 'No supported replacement preference is established; saved membership is a separate whole-résumé decision.'
    included = base_selected if leader == 'Base' else library_selected
    return (leader+' relevance preference agrees with saved inclusion. An individual causal win was not measured.' if included else
            leader+' has stronger recorded relevance but was excluded. Recorded whole-slate constraints are context; no isolated exclusion cause was measured.')


@lru_cache(maxsize=128)
def _compare_cached(payload):
    base, library, catalog, selected = json.loads(payload)
    result = {'version': VERSION, 'native_impact': 'unmeasured', 'units': 'requirement identities and recorded grades; no aggregate score'}
    if (base['project'] != library['project'] or 'Selected Base' not in base.get('sources', [])
            or 'Evidence Library' not in library.get('sources', [])):
        return json.dumps({**result, 'outcome': 'Not a valid competing pair.', 'reason': 'Project/source ownership does not match.'})
    a, aw = _evidence(base, catalog)
    b, bw = _evidence(library, catalog)
    elsewhere = set()
    for row in selected:
        if (row['project'], row['bullet']) not in {(base['project'], base['bullet']), (library['project'], library['bullet'])}:
            elsewhere.update(_evidence(row, catalog)[0])
    result.update(base_support=a, library_support=b, warnings=aw+bw,
        shared=sorted(a.keys() & b.keys()), base_only=sorted(a.keys()-b.keys()), library_only=sorted(b.keys()-a.keys()),
        already_supported_elsewhere=sorted((a.keys() | b.keys()) & elsewhere),
        base_new_beyond_surrounding=sorted(a.keys()-elsewhere), library_new_beyond_surrounding=sorted(b.keys()-elsewhere),
        word_counts={'base': len(base['bullet'].split()), 'library': len(library['bullet'].split())},
        technologies={'base': base.get('jd_wide_technology_cues', []), 'library': library.get('jd_wide_technology_cues', [])},
        capabilities={'base': base.get('matched_action_families', []), 'library': library.get('matched_action_families', [])})
    jd = ' '.join(r['text'] for r in catalog.values())
    terms = {name for name, pattern in TEST_TERMS.items() if re.search(pattern, jd, re.I)
             or ('testing' in jd.casefold() and re.search(r'\b'+re.escape(name.removesuffix(' testing'))+r'\b', jd, re.I))}
    result['explicit_testing_terms'] = {role: sorted(t for t in terms if re.search(TEST_TERMS[t], row['bullet'], re.I))
                                         for role, row in [('base', base), ('library', library)]}
    result['unestablished_testing_terms'] = {role: sorted(terms-set(values)) for role, values in result['explicit_testing_terms'].items()}
    result['terminology_limit'] = 'Explicit terminology does not establish performance of every activity or complete compound-requirement satisfaction.'
    if base['bullet'] == library['bullet']:
        outcome, reason = 'Comparable relevance / tie.', 'Shared Base + Library wording; no source winner.'
    elif not a and not b:
        outcome, reason = 'Insufficient verified evidence to determine a preference.', 'Only lexical/saved links or unresolved evidence are available.'
    else:
        outcome, reason = 'Comparable relevance / tie.', 'Recorded support is equivalent; shorter wording alone does not establish a relevance winner.'
        for kinds in [HARD, BONUS]:
            ids = {rid for rid in a.keys() | b.keys() if catalog[rid]['importance'] in kinds}
            better_a = any(any(x > y for x, y in zip(a.get(r, (0, 0)), b.get(r, (0, 0)))) for r in ids)
            better_b = any(any(y > x for x, y in zip(a.get(r, (0, 0)), b.get(r, (0, 0)))) for r in ids)
            if better_a and better_b:
                outcome, reason = 'Different complementary evidence — no clear replacement winner.', 'Each wording preserves recorded support the other does not establish.'
                break
            if better_a or better_b:
                role = 'Base' if better_a else 'Library'
                outcome = role+' has stronger supported JD relevance.'
                reason = role+' dominates the recorded '+('Required/Core' if kinds == HARD else 'Preferred/Supporting')+' evidence for this pair. This is not a historical selection cause or native score delta.'
                break
    result.update(outcome=outcome, reason=reason)
    return json.dumps(result, ensure_ascii=False)
