"""Offline human-review preparation, never a producer of inferred gold labels."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

from taxonomy_discovery import unresolved_adjudication as a

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'tests/fixtures/unresolved_adjudication_benchmark_v1.json'
REVIEW_VERSION = 'unresolved-human-gold-review-v2'

# Editorial questions about the frozen selection, not route rules or gold labels.
# Indexing is checked against the sealed original selection before use.
QUESTIONS = {
    1: ('RELATIONSHIP / STRUCTURAL', False, 'Persistence, search and alternative products are different scopes. MongoDB identity cannot establish database.design. Review original JD scope before choosing a primary route.'),
    4: ('NOT_TAXONOMY_ADDRESSABLE / UNKNOWN', True, 'Learning aspiration versus a concrete architecture/security obligation; do not equate the historical bucket with an exact route.'),
    5: ('NOT_TAXONOMY_ADDRESSABLE / CAPABILITY / UNKNOWN', False, 'Project context may hide a real development obligation; retrieve original responsibility section.'),
    6: ('NOT_TAXONOMY_ADDRESSABLE', True, 'Public-service motivation, not a bounded technical capability.'),
    7: ('NOT_TAXONOMY_ADDRESSABLE / CAPABILITY', True, 'Professional-growth responsibility may be leadership; review technical-taxonomy boundary, not scoring eligibility.'),
    8: ('NOT_TAXONOMY_ADDRESSABLE / UNKNOWN', True, 'Broad market familiarity has no bounded technical predicate in this text.'),
    9: ('NOT_TAXONOMY_ADDRESSABLE', True, 'Learning speed is not a named technical capability.'),
    10: ('STRUCTURAL / TECH_ID', False, 'Leading list item and database examples: original parent and AND/OR intent are needed. SQL does not imply querying; MongoDB does not imply schema design.'),
    11: ('STRUCTURAL / RELATIONSHIP', True, 'Example cloud services plus warehousing/lakehouse activity: distinguish examples from obligations. AWS identity cannot imply architecture.'),
    12: ('STRUCTURAL / TECH_ID', True, 'Explicit one-or-more alternatives; Node.js identity cannot imply API implementation.'),
    13: ('STRUCTURAL / TECH_ID', True, 'Multiple language examples plus programming activity; C# cannot imply backend development. Reviewer must decide parent versus component route.'),
    14: ('STRUCTURAL / TECH_ID', True, 'ROS 2 plus simulation platforms: whole requirement is not a pure identity. Separate named identity from example/compound scope.'),
    15: ('RELATIONSHIP / STRUCTURAL / UNKNOWN', False, 'ROS-based maintenance may be robotics implementation, not an identity gap alone; original activity/parent source needed.'),
    16: ('STRUCTURAL', True, 'Explicit OR across portfolio, AI/ML, SLAM/motion planning, CI/CD and simulation. Identity bucket alone is misleading.'),
    17: ('TECH_ID / STRUCTURAL', False, 'CSS is recognizable but native parent provenance is missing. Review parent before treating a decomposed child as atomic.'),
    18: ('TECH_ID / STRUCTURAL', False, 'HTML is recognizable but native parent provenance is missing. Identity recognition alone cannot establish frontend work.'),
    19: ('STRUCTURAL / UNKNOWN', True, 'DevOps, networking and cloud are broad mixed activity families, not one technology identity.'),
    20: ('RELATIONSHIP / CAPABILITY / STRUCTURAL', False, 'Python identity exists; internal tools/modules are not a universal backend mapping. Resolve parent/source provenance first.'),
    21: ('RELATIONSHIP / CAPABILITY', True, 'Java identity exists and web application activity is explicit; verify the exact existing capability predicate, not Java-to-backend universally.'),
    22: ('CAPABILITY / RELATIONSHIP / STRUCTURAL', False, 'UI activity is explicit with React, but native provenance blocks scope. Inspect parent and frontend predicate before labeling recovery.'),
    23: ('CAPABILITY / RELATIONSHIP / STRUCTURAL', True, 'Programming/application knowledge is explicit; Python is an example, not a universal capability relationship.'),
    24: ('TECH_ID / RELATIONSHIP / STRUCTURAL', False, 'Azure familiarity does not prove cloud architecture. Native scope provenance is blocked; inspect parent/source.'),
    25: ('STRUCTURAL / RELATIONSHIP', True, 'Code, APIs, bug fixes and monitoring are multiple obligations. C# supports identity only; no universal backend mapping.'),
    26: ('UNKNOWN / CAPABILITY / TRUE_GAP_CANDIDATE', False, 'Security protocols are too broad to establish a reusable missing capability; need bounded activity and overlap review.'),
    27: ('STRUCTURAL / CAPABILITY', True, 'Ingest, transform and serve with stream/batch context; decide coherent pipeline scope versus independent obligations.'),
    28: ('STRUCTURAL / CAPABILITY / UNKNOWN', True, 'Performance analysis and robustness/reliability improvement: adjudicate coherent autonomy scope versus decomposition.'),
    29: ('UNKNOWN / CAPABILITY', False, 'Broad autonomy deployment needs bounded activity/source scope; cannot infer a missing reusable capability.'),
    30: ('CAPABILITY / RELATIONSHIP / STRUCTURAL', False, 'Exploratory GenAI orchestration versus implementation; original parent/source and existing integration predicate needed.'),
    31: ('CAPABILITY / RELATIONSHIP / STRUCTURAL', False, 'Exploratory integration statement may be coherent scope; need original source and predicate review.'),
    32: ('STRUCTURAL / TECH_ID', True, 'JavaScript/TypeScript ecosystem: preserve paired scope. JavaScript does not imply frontend development.'),
    33: ('STRUCTURAL / RELATIONSHIP', True, 'Persistence, retrieval, transactions and CRUD do not prove schema design; preserve MongoDB/Elasticsearch activity boundaries.'),
    34: ('CAPABILITY / STRUCTURAL', True, 'Explicit RESTful API building; framework alternatives are examples, not independent API obligations. Check backend.api_development predicate.'),
    35: ('STRUCTURAL / CAPABILITY / TECH_ID', True, 'Explicit OR between tools, application development, APIs and integration; do not convert examples into simultaneous obligations.'),
    36: ('CAPABILITY / UNKNOWN', False, 'Generic production software quality needs exact existing predicate/parent review, not a new gap by default.'),
    37: ('NOT_TAXONOMY_ADDRESSABLE / CAPABILITY / UNKNOWN', False, 'Pride/failsafe aspiration versus testable safety obligation: original context needed.'),
    38: ('CAPABILITY / UNKNOWN', False, 'Security by Design needs explicit boundary and existing security predicate review.'),
    39: ('STRUCTURAL / CAPABILITY / NOT_TAXONOMY_ADDRESSABLE', True, 'Testing and documentation are named; determine technical obligations versus engineering ethos, not a new capability by default.'),
    40: ('CAPABILITY / UNKNOWN', False, 'Broad quality/security/maintainability requires predicate/source review; no missing capability proven.'),
}


def seal(value):
    value['fingerprint'] = a.fingerprint({k: v for k, v in value.items() if k != 'fingerprint'})
    return value


def original():
    value = json.loads(ORIGINAL.read_text(encoding='utf-8'))
    if value['fingerprint'] != a.fingerprint({k: v for k, v in value.items() if k != 'fingerprint'}):
        raise ValueError('Original manifest integrity mismatch')
    return value


def validate(manifest, parent=None, cases=None):
    """Structural provenance validation; cannot authenticate a human's identity."""
    parent = parent or original()
    if manifest.get('review_version') != REVIEW_VERSION or manifest.get('parent_fingerprint') != parent['fingerprint']:
        raise ValueError('Human review must preserve the frozen parent')
    if manifest.get('fingerprint') != a.fingerprint({k: v for k, v in manifest.items() if k != 'fingerprint'}):
        raise ValueError('Human manifest integrity mismatch')
    expected_keys = [e['key'] for e in parent['expectations']]
    if [e['key'] for e in manifest['expectations']] != expected_keys:
        raise ValueError('Human review cannot replace, duplicate or reorder frozen cases')
    for field in ('schema_version', 'prompt_version', 'source_path', 'source_fingerprint'):
        if manifest[field] != parent[field]:
            raise ValueError('Frozen source identity changed')
    for old, new in zip(parent['expectations'], manifest['expectations']):
        unchanged = {k: v for k, v in new.items() if k not in ('acceptable_routes', 'human_review')}
        if unchanged != {k: v for k, v in old.items() if k != 'acceptable_routes'}:
            raise ValueError('Frozen expectation/control identity changed')
        review = new['human_review']
        state = review.get('state')
        if state == 'INHERITED_CONFIRMED':
            if not old['acceptable_routes'] or new['acceptable_routes'] != old['acceptable_routes'] or review != {
                'state': 'INHERITED_CONFIRMED', 'parent_fingerprint': parent['fingerprint'],
                'original_review_reason': old['review_reason']}:
                raise ValueError('Only original explicit labels may be inherited')
        elif state == 'PENDING':
            if new['acceptable_routes'] or old['acceptable_routes'] or review != {'state': 'PENDING'}:
                raise ValueError('Pending interpretations are not gold labels')
        elif state in ('CONFIRMED', 'DEFERRED'):
            receipt = review.get('receipt', {})
            if receipt.get('origin') != 'INDEPENDENT_HUMAN' or receipt.get('independent_of_model_predictions') is not True:
                raise ValueError('Independent human provenance required')
            for field in ('reviewer', 'reviewed_at', 'rationale', 'source_reference'):
                if not isinstance(receipt.get(field), str) or not receipt[field].strip():
                    raise ValueError('Human receipt fields required')
            stamp = datetime.fromisoformat(receipt['reviewed_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Timezone-aware review timestamp required')
            if receipt.get('key') != new['key'] or receipt.get('input_fingerprint') != new['input_fingerprint'] or receipt.get('source_fingerprint') != parent['source_fingerprint']:
                raise ValueError('Human receipt must bind exact frozen input and source')
            routes = new['acceptable_routes']
            if receipt.get('acceptable_routes') != routes or not isinstance(routes, list) or len(set(routes)) != len(routes) or any(r not in a.ROUTES or r == 'UNKNOWN' for r in routes):
                raise ValueError('Explicit non-UNKNOWN route decision required')
            if (state == 'CONFIRMED') != bool(routes):
                raise ValueError('Deferred decisions cannot become actionable labels')
            spans = receipt.get('source_spans')
            if not isinstance(spans, list) or not spans or any(not isinstance(s, str) or not s for s in spans):
                raise ValueError('Human source spans required')
            if cases is not None:
                text = next(c['requirement_text'] for c in cases if [c['job_id'], c['requirement_id']] == new['key'])
                if any(s not in text for s in spans):
                    raise ValueError('Review spans must be exact frozen requirement substrings')
        else:
            raise ValueError('Unknown human review state')


def versioned_manifest(parent, receipts, cases):
    """Apply explicit receipts only. Empty receipts add zero new gold labels."""
    result = deepcopy(parent)
    result.update(review_version=REVIEW_VERSION, parent_fingerprint=parent['fingerprint'],
                  review_state='INDEPENDENT_HUMAN_REVIEW_PENDING')
    by_key = {tuple(c['key']): c for c in receipts}
    if len(by_key) != len(receipts):
        raise ValueError('Duplicate human receipt')
    known = {tuple(e['key']) for e in parent['expectations']}
    if set(by_key) - known:
        raise ValueError('Unknown human receipt case')
    texts = {(c['job_id'], c['requirement_id']): c['requirement_text'] for c in cases}
    for row in result['expectations']:
        receipt = by_key.get(tuple(row['key']))
        if receipt is not None:
            if any(not isinstance(s, str) or not s or s not in texts[tuple(row['key'])] for s in receipt.get('source_spans', [])):
                raise ValueError('Review spans must be exact frozen requirement substrings')
            row['acceptable_routes'] = deepcopy(receipt.get('acceptable_routes'))
            row['human_review'] = {'state': 'CONFIRMED' if row['acceptable_routes'] else 'DEFERRED', 'receipt': deepcopy(receipt)}
        elif row['acceptable_routes']:
            row['human_review'] = {'state': 'INHERITED_CONFIRMED', 'parent_fingerprint': parent['fingerprint'],
                                   'original_review_reason': row['review_reason']}
        else:
            row['human_review'] = {'state': 'PENDING'}
    seal(result)
    validate(result, parent, cases)
    return result


def summary(manifest):
    counts = Counter(e['acceptable_routes'][0] for e in manifest['expectations'] if e['acceptable_routes'])
    pending = [e['key'] for e in manifest['expectations'] if not e['acceptable_routes']]
    critical = [e['key'] for e in manifest['expectations'] if e['critical'] and not e['acceptable_routes']]
    return {'total_cases': len(manifest['expectations']), 'confirmed': sum(counts.values()),
            'pending': len(pending), 'coverage': {r: counts[r] for r in a.ROUTES},
            'critical_pending': critical, 'labeling_prerequisite_satisfied': sum(counts.values()) >= 20 and len(counts) >= 4 and not critical}


def worksheet(parent, cases, occurrences):
    """Human-readable evidence inventory. Questions never populate expectations."""
    by_key = {(o['job_id'], o['requirement']['requirement_id']): o for o in occurrences}
    if [e['key'] for e in parent['expectations']] != [e['key'] for e in original()['expectations']]:
        raise ValueError('Editorial questions require original frozen case order')
    lines = ['# Independent human gold-label review — frozen 40-case selection', '',
        'No new gold labels have been assigned. Two NAC expectations are inherited; 38 exact routes remain pending.', '',
        'Historical buckets, resolver diagnostics and token-overlap candidates are evidence to review, not human gold. '
        'A text-ready case can support a human decision or explicit deferral; it is not automatically actionable.', '',
        f"Parent manifest: `{parent['fingerprint']}`. Source: `{parent['source_path']}`; `{parent['source_fingerprint']}`.", '',
        'The frozen corpus has no independent exact-route reviewer ledger (reviewed_requirement_keys is empty). '
        'Original reviewer name/date are unavailable for inherited expectations; none have been invented. '
        'Full JD/nearby source lines are unavailable. Parent/list context must be reviewed separately when noted. '
        'No applicant evidence, predictions or synthetic answers are used.', '',
        '## Route choices', '',
        '| Route | Human decision boundary |', '|---|---|',
        '| CAPABILITY | Explicit bounded activity fits an existing capability predicate; identify it and check exclusions. |',
        '| TECH_ID | Identity-only knowledge route; preserve parent scope; identity cannot imply capability. |',
        '| RELATIONSHIP | Named technology plus bounded activity requires governed mapping review, not global mapping. |',
        '| STRUCTURAL | Parent/child, alternatives, normalization or mixed obligations block safe atomic interpretation. |',
        '| NOT_TAXONOMY_ADDRESSABLE | Not a bounded technical-taxonomy obligation; does not change scoring eligibility. |',
        '| TRUE_GAP_CANDIDATE | Bounded reusable activity with existing predicates shown insufficient; never publication. |',
        '| UNKNOWN | Evidence cannot support a route; explicitly defer rather than force a category. |', '',
        '## Review method', '',
        'Review before seeing model predictions. Read exact text, native scope and historical proof. '
        'Record primary route first, reviewed alternatives only, exact supporting substrings, rationale, '
        'reviewer identity, timezone-aware timestamp and source reference. A blank decision stays pending. '
        'If additional JD context is necessary, retrieve it through human source review, record its reference '
        'in the rationale, and defer until confirmed. Source text changes require a new frozen input, not editing v1.', '',
        'The JSON receipt template has blank reviewer/time/rationale fields and no proposed gold routes. '
        'Only completed explicitly reviewed receipts should be imported. Validation checks provenance structure '
        'and grounding; it cannot authenticate the reviewer or prove an independence attestation is truthful.', '',
        '## Priority inventory', '', '| # | Job / requirement | Review readiness | Proposed discussion routes (NOT gold) |', '|---:|---|---|---|']
    items = []
    for i, (e, case) in enumerate(zip(parent['expectations'], cases), 1):
        key = tuple(e['key']); occ = by_key[key]
        if key in a.NAC:
            choices, ready, note = ('TRUE_GAP_CANDIDATE', True, 'Previously confirmed NAC control. Historical gap contract distinguishes network admission from database authorization, packet capture and DNS/DHCP. Native provenance diagnostic conflicts with historical semantic adjudication; do not silently relabel it.')
        else:
            choices, ready, note = QUESTIONS[i]
        item = {'number': i, 'key': e['key'], 'input': case, 'expectation': e,
                'review_readiness': 'TEXT_READY_FOR_HUMAN_DECISION' if ready else 'FURTHER_SOURCE_OR_PREDICATE_REVIEW',
                'proposed_discussion_routes_not_gold': choices, 'question': note,
                'original_review': occ['review'],
                'native_source_context': {k: deepcopy(occ['requirement'][k]) for k in
                    ('source_provenance', 'decomposition', 'parent_requirement_id', 'scope') if k in occ['requirement']},
                'source_manifest': occ['source_manifest']}
        items.append(item)
        lines.append(f"| {i} | {key[0]} / {key[1]} | {item['review_readiness']} | {choices} |")
    lines += ['', f"Text-ready for human decision: {sum(i['review_readiness'] == 'TEXT_READY_FOR_HUMAN_DECISION' for i in items)}; further source/predicate review: {sum(i['review_readiness'] != 'TEXT_READY_FOR_HUMAN_DECISION' for i in items)}.", '',
        'Prioritize explicit alternatives/mixed obligations (STRUCTURAL), bounded activity predicates (CAPABILITY/RELATIONSHIP), '
        'and motivation/familiarity boundaries (NOT_TAXONOMY_ADDRESSABLE), alongside NAC. '
        'Twenty actionable labels across four categories is a review target, not a claim established by this worksheet. '
        'Pure CSS/HTML and Azure cases need parent provenance; do not force TECH_ID to reach category coverage.', '']
    for item in items:
        e = item['expectation']; c = item['input']
        lines += [f"## {item['number']}. Job {c['job_id']} — {c['requirement_id']}", '',
            'Exact stored requirement (JSON string preserves invisible characters):', '',
            '```json', json.dumps(c['requirement_text'], ensure_ascii=True), '```', '',
            f"Importance: {c['importance']}. Input fingerprint: `{e['input_fingerprint']}`.", '',
            f"Confirmed expectation: {e['acceptable_routes'] or 'NONE — human decision pending'}.",
            f"Original provenance: {e['review_reason']}", '',
            f"Historical classification: {e['review_bucket']} / {e['primary_blocker']}.",
            f"Critical control: {e['critical']}; non-gap control: {e['non_gap_control']}.", '',
            f"Readiness: {item['review_readiness']}.",
            f"Proposed discussion routes, NOT gold: {item['proposed_discussion_routes_not_gold']}.",
            item['question'], '', 'Native deterministic resolver:', '', '```json', json.dumps(c['resolver'], indent=2), '```', '',
            'Existing bounded taxonomy candidates (token overlap ONLY, not resolver matches):', '',
            '```json', json.dumps(c['taxonomy_candidates'], ensure_ascii=True, indent=2), '```', '',
            'Exact alias-mentioned registry identities (not capability mappings):', '',
            '```json', json.dumps(c['registry_candidates'], ensure_ascii=True, indent=2), '```', '',
            'Stored source context/provenance (empty means unavailable, never inferred from adjacent rows):', '',
            '```json', json.dumps(item['native_source_context'], ensure_ascii=True, indent=2), '```', '',
            'Original review proof:', '', '```json', json.dumps(item['original_review'].get('proof', {}), ensure_ascii=True, indent=2), '```', '',
            'Human decision: **PENDING** (or reconfirm inherited NAC). Reviewer / date / route / exact spans / rationale / source reference: ______', '']
    return '\n'.join(lines), items
